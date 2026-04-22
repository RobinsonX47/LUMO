from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session, g
from flask_login import current_user, login_required
from ...core.extensions import db
from ...core.models import Review, Watchlist, WatchProgress
from ...services.tmdb_service import TMDBService
from ...services.embed_provider_service import build_movie_embed_url, build_tv_embed_url, normalize_provider_base_url
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from collections import Counter
import requests
import json
import time
from datetime import datetime, timedelta


def build_ai_style_recommendations(base_item, media_type):
    """Rank high-quality related titles using TMDB similar + recommendations data."""
    if not base_item:
        return []
    
    try:
        similar_block = base_item.get('similar', {})
        recommended_block = base_item.get('recommendations', {})

        similar_candidates = similar_block.get('results', []) if isinstance(similar_block, dict) else []
        recommended_candidates = recommended_block.get('results', []) if isinstance(recommended_block, dict) else []
        candidates = list(similar_candidates) + list(recommended_candidates)
        if not candidates:
            return []
        
        # Get base data for scoring (already in base_item)
        base_year = None
        release_field = base_item.get('release_date') or base_item.get('first_air_date')
        if release_field and len(release_field) >= 4:
            try:
                base_year = int(release_field[:4])
            except ValueError:
                pass
        
        base_genre_ids = set(g.get('id') for g in base_item.get('genres', []) if g.get('id'))
        
        scored_by_id = {}
        for cand in candidates[:30]:
            if not cand.get('id') or cand.get('id') == base_item.get('id'):
                continue

            cand_media_type = cand.get('media_type') or ('tv' if (cand.get('name') and not cand.get('title')) else 'movie')
            if cand_media_type != media_type:
                continue

            vote = float(cand.get('vote_average') or 0)
            vote_count = int(cand.get('vote_count') or 0)
            if vote < 5.5 or vote_count < 40:
                continue
            
            # Calculate year proximity
            cand_year = None
            rel_field = cand.get('release_date') or cand.get('first_air_date')
            if rel_field and len(rel_field) >= 4:
                try:
                    cand_year = int(rel_field[:4])
                except ValueError:
                    pass
            
            era_score = 0
            if base_year and cand_year:
                diff = abs(base_year - cand_year)
                era_score = max(0, 10 - diff) / 10
            
            # Genre overlap (using genre_ids from candidate if available)
            cand_genre_ids = set(cand.get('genre_ids', []))
            genre_overlap = len(base_genre_ids & cand_genre_ids) if cand_genre_ids else 0
            
            popularity = float(cand.get('popularity') or 0)
            popularity_score = min(popularity / 100.0, 1.0)
            source_bonus = 0.5 if cand in recommended_candidates else 0.0

            score = (genre_overlap * 3.5) + (era_score * 1.5) + (vote / 2.0) + popularity_score + source_bonus

            cand['media_type'] = cand_media_type

            existing = scored_by_id.get(cand['id'])
            if not existing or score > existing['score']:
                scored_by_id[cand['id']] = {'data': cand, 'score': score}

        scored = sorted(scored_by_id.values(), key=lambda x: x['score'], reverse=True)
        return [s['data'] for s in scored[:8]]
    
    except Exception as e:
        print(f"Error in recommendations: {e}")
        # Fallback: return first 6 similar items
        similar_block = base_item.get('similar', {})
        if isinstance(similar_block, dict):
            results = similar_block.get('results', [])[:6]
            for r in results:
                r['media_type'] = r.get('media_type') or (
                    'tv' if (r.get('name') and not r.get('title')) else 'movie'
                )
            return results
        return []


def _is_anime_from_details(details):
    genre_ids = {g.get('id') for g in details.get('genres', []) if g.get('id') is not None}
    if 16 not in genre_ids:
        return False
    origin_countries = set(details.get('origin_country') or [])
    original_language = (details.get('original_language') or '').lower()
    return original_language == 'ja' or 'JP' in origin_countries


def _is_anime_candidate(item):
    genre_ids = set(item.get('genre_ids') or [])
    if 16 not in genre_ids:
        return False
    origin_countries = set(item.get('origin_country') or [])
    original_language = (item.get('original_language') or '').lower()
    return original_language == 'ja' or 'JP' in origin_countries


def _candidate_bucket(item):
    media_type = item.get('media_type')
    if media_type == 'anime':
        return 'anime'
    if media_type == 'tv':
        return 'anime' if _is_anime_candidate(item) else 'tv'
    return 'movie'


def _compute_target_mix(seed, limit):
    media_counts = seed.get('media_counts') or {}
    movie_count = int(media_counts.get('movie', 0))
    tv_count = int(media_counts.get('tv', 0))
    anime_count = int(media_counts.get('anime', 0))
    tv_non_anime = max(0, tv_count - anime_count)

    weighted = {
        'movie': float(movie_count),
        'tv': float(tv_non_anime),
        'anime': float(anime_count) * 1.2,
    }
    total_weight = sum(weighted.values())
    if total_weight <= 0:
        return {'movie': limit, 'tv': 0, 'anime': 0}

    raw = {k: (weighted[k] / total_weight) * limit for k in weighted}
    base = {k: int(raw[k]) for k in raw}
    remaining = max(0, limit - sum(base.values()))
    order = sorted(raw.keys(), key=lambda k: (raw[k] - base[k]), reverse=True)
    for key in order[:remaining]:
        base[key] += 1

    dominant_cap = max(1, int(limit * 0.65))
    dominant_bucket = max(base.keys(), key=lambda k: base[k])
    if base[dominant_bucket] > dominant_cap:
        excess = base[dominant_bucket] - dominant_cap
        base[dominant_bucket] = dominant_cap
        recipients = [k for k in ('movie', 'tv', 'anime') if k != dominant_bucket]
        for recipient in recipients:
            if excess <= 0:
                break
            base[recipient] += 1
            excess -= 1
        idx = 0
        while excess > 0 and recipients:
            base[recipients[idx % len(recipients)]] += 1
            idx += 1
            excess -= 1

    for bucket, source_count in (('movie', movie_count), ('anime', anime_count)):
        if source_count > 0 and base[bucket] == 0 and limit >= 3:
            donor = max(base.keys(), key=lambda k: base[k])
            if donor != bucket and base[donor] > 1:
                base[donor] -= 1
                base[bucket] += 1

    return base


def _apply_media_mix(candidates, seed, limit=24, exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = set()

    quotas = _compute_target_mix(seed, limit)
    buckets = {'anime': [], 'tv': [], 'movie': []}
    unique_candidates = []
    seen = set(exclude_ids)

    for item in candidates:
        item_id = item.get('id')
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)

        bucket = _candidate_bucket(item)
        if bucket == 'anime':
            item['media_type'] = 'anime'
        elif bucket == 'tv':
            item['media_type'] = 'tv'
        else:
            item['media_type'] = 'movie'

        buckets[bucket].append(item)
        unique_candidates.append(item)

    selected = []
    selected_ids = set()

    for bucket in ('anime', 'tv', 'movie'):
        for item in buckets[bucket][:quotas.get(bucket, 0)]:
            item_id = item.get('id')
            if item_id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item_id)

    if len(selected) < limit:
        remaining = sorted(
            [item for item in unique_candidates if item.get('id') not in selected_ids],
            key=lambda m: float(m.get('vote_average') or 0.0),
            reverse=True,
        )
        for item in remaining:
            selected.append(item)
            selected_ids.add(item.get('id'))
            if len(selected) >= limit:
                break

    return selected[:limit]


def _get_watchlist_recommendation_seed(watchlist_entries, max_title_items=15, max_genre_items=8):
    """Build recommendation seed and media preference profile from watchlist."""
    watchlist_titles = []
    watchlist_genres = []
    watchlist_ids = []
    media_counts = Counter()
    movie_genre_counts = Counter()
    tv_genre_counts = Counter()
    anime_genre_counts = Counter()

    details_cache = {}
    seeded_entries = watchlist_entries[:max_title_items]

    for idx, entry in enumerate(seeded_entries):
        if getattr(entry, 'tmdb_movie_id', None):
            watchlist_ids.append(entry.tmdb_movie_id)
        entry_media_type = (getattr(entry, 'media_type', 'movie') or 'movie').strip().lower()
        if entry_media_type not in {'movie', 'tv'}:
            entry_media_type = 'movie'
        media_counts[entry_media_type] += 1

        needs_details = idx < max_genre_items or not (entry.movie_title or '').strip()
        details = None

        if needs_details:
            cache_key = (entry.tmdb_movie_id, entry_media_type)
            details = details_cache.get(cache_key)
            if details is None:
                fetch_details = TMDBService.get_tv_details if entry_media_type == 'tv' else TMDBService.get_movie_details
                details = fetch_details(entry.tmdb_movie_id)
                details_cache[cache_key] = details

        title = (entry.movie_title or '').strip()
        if title:
            watchlist_titles.append(title)
        elif details:
            watchlist_titles.append((details.get('title') or details.get('name') or 'Unknown').strip())

        if idx < max_genre_items and details and details.get('genres'):
            for genre in details.get('genres', []):
                genre_name = (genre.get('name') or '').strip()
                genre_id = genre.get('id')
                if not genre_name:
                    continue
                watchlist_genres.append(genre_name)

                if entry_media_type == 'movie':
                    movie_genre_counts[genre_name] += 1
                else:
                    tv_genre_counts[genre_name] += 1

                if genre_id == 16 and _is_anime_from_details(details):
                    anime_genre_counts[genre_name] += 1

        if entry_media_type == 'tv' and details and _is_anime_from_details(details):
            media_counts['anime'] += 1

    if media_counts.get('anime', 0) > media_counts.get('tv', 0):
        media_counts['anime'] = media_counts.get('tv', 0)

    return {
        'titles': watchlist_titles,
        'genres': watchlist_genres,
        'watchlist_ids': watchlist_ids,
        'media_counts': dict(media_counts),
        'movie_genres': [name for name, _ in movie_genre_counts.most_common(6)],
        'tv_genres': [name for name, _ in tv_genre_counts.most_common(6)],
        'anime_genres': [name for name, _ in anime_genre_counts.most_common(6)],
    }


def _call_anthropic_recommendation(prompt):
    """Call Anthropic recommendations API and return parsed JSON list or None."""
    api_key = current_app.config.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        return None

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": current_app.config.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514'),
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if response.status_code != 200:
            current_app.logger.warning("Anthropic recommendations returned status %s", response.status_code)
            return None

        data = response.json()
        content = data.get('content', [{}])[0].get('text', '').strip()
        if '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        return json.loads(content)
    except Exception as exc:
        current_app.logger.warning("Anthropic recommendation call failed: %s", exc)
        return None

movies_bp = Blueprint("movies", __name__)


def _get_allowed_embed_origins():
    configured = current_app.config.get("EMBED_PROVIDER_ALLOWED_ORIGINS", [])
    if isinstance(configured, str):
        configured = [configured]
    return {origin.strip().lower().rstrip("/") for origin in configured if origin.strip()}


def _is_allowed_embed_origin(url):
    normalized = normalize_provider_base_url(url)
    if not normalized:
        return False
    return normalized.lower().rstrip("/") in _get_allowed_embed_origins()


def _log_route_perf(route_name, started_at):
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    tmdb_calls = getattr(g, "tmdb_api_calls", 0)
    current_app.logger.info("%s took %sms (tmdb_api_calls=%s)", route_name, duration_ms, tmdb_calls)


def _safe_db_call(fn, default):
    """Return fallback value when DB is unavailable so public pages can still render."""
    try:
        return fn()
    except Exception as exc:
        current_app.logger.warning("DB operation failed, using fallback: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
        return default


def _track_recently_viewed(item_id, media_type):
    """Track recently viewed items in session for quick home-page retrieval."""
    recent = session.get('recently_viewed', [])
    filtered = [x for x in recent if not (x.get('id') == item_id and x.get('media_type') == media_type)]
    filtered.insert(0, {'id': item_id, 'media_type': media_type})
    session['recently_viewed'] = filtered[:12]
    session.modified = True


def _build_recently_viewed_snapshot(item, media_type, item_id):
    """Store only the fields the homepage needs so the session stays small."""
    title = (item.get('title') or item.get('name') or '').strip()
    release_date = item.get('release_date') or item.get('first_air_date') or ''

    return {
        'id': item_id,
        'media_type': media_type,
        'title': title,
        'name': title,
        'poster_path': item.get('poster_path'),
        'release_date': release_date,
        'vote_average': item.get('vote_average', 0.0),
    }


def _build_player_context(media_type, tmdb_id, season=None, episode=None):
    session_base_url = normalize_provider_base_url(session.get("embed_provider_base_url") or "")
    session_origin = normalize_provider_base_url(session.get("embed_provider_allowed_origin") or "")
    config_base_url = normalize_provider_base_url(current_app.config.get("EMBED_PROVIDER_BASE_URL", ""))
    config_origin = normalize_provider_base_url(current_app.config.get("EMBED_PROVIDER_ALLOWED_ORIGIN", ""))

    base_url = session_base_url or config_base_url
    enabled = bool(base_url) and (
        current_app.config.get("EMBED_PROVIDER_ENABLED", False) or bool(session_base_url)
    )
    if not enabled or not base_url:
        return {
            "enabled": False,
            "url": None,
            "base_url": base_url,
            "allowed_origin": session_origin or config_origin,
        }

    color = current_app.config.get("EMBED_PROVIDER_COLOR", "e50914")
    # Force manual playback start to avoid unexpected auto-playing media.
    auto_play = False

    if media_type == "tv":
        if season is None:
            season = request.args.get("season", 1, type=int)
        if episode is None:
            episode = request.args.get("episode", 1, type=int)
        progress = request.args.get("progress", None, type=int)
        embed_url = build_tv_embed_url(
            base_url=base_url,
            tmdb_id=tmdb_id,
            season=season,
            episode=episode,
            color=color,
            auto_play=auto_play,
            next_episode=True,
            episode_selector=True,
            progress=progress,
        )
        return {
            "enabled": True,
            "url": embed_url,
            "media_type": "tv",
            "season": max(season, 1),
            "episode": max(episode, 1),
            "base_url": base_url,
            "allowed_origin": session_origin or config_origin,
        }

    progress = request.args.get("progress", None, type=int)
    embed_url = build_movie_embed_url(
        base_url=base_url,
        tmdb_id=tmdb_id,
        color=color,
        auto_play=auto_play,
        progress=progress,
    )
    return {
        "enabled": True,
        "url": embed_url,
        "media_type": "movie",
        "season": None,
        "episode": None,
        "base_url": base_url,
        "allowed_origin": session_origin or config_origin,
    }


@movies_bp.route("/player-config", methods=["POST"])
@login_required
def set_player_config():
    """Allow configuring embed provider at runtime (session-scoped) for local setup."""
    is_production = current_app.config.get("ENV") == "production"
    if is_production and getattr(current_user, "role", "user") != "admin":
        flash("Only admins can change player configuration in production.", "error")
        return redirect(request.referrer or url_for("main.home"))

    base_url = normalize_provider_base_url(request.form.get("embed_provider_base_url") or "")
    allowed_origin = (request.form.get("embed_provider_allowed_origin") or "").strip()

    if not base_url:
        flash("Embed provider URL must be a valid https URL", "error")
        return redirect(request.referrer or url_for("main.home"))

    if not _is_allowed_embed_origin(base_url):
        flash("This provider origin is not in the allowlist.", "error")
        return redirect(request.referrer or url_for("main.home"))

    if allowed_origin:
        if normalize_provider_base_url(allowed_origin) != allowed_origin.rstrip("/"):
            flash("Allowed origin must be a valid https origin URL.", "error")
            return redirect(request.referrer or url_for("main.home"))
        if not _is_allowed_embed_origin(allowed_origin):
            flash("Allowed origin is not in the configured allowlist.", "error")
            return redirect(request.referrer or url_for("main.home"))

    session["embed_provider_base_url"] = base_url.rstrip("/")
    session["embed_provider_allowed_origin"] = allowed_origin.rstrip("/") if allowed_origin else base_url.rstrip("/")
    session.modified = True

    flash("Player provider configured for this browser session.", "success")
    return redirect(request.referrer or url_for("main.home"))

@movies_bp.route("/")
def movie_list():
    started_at = time.perf_counter()
    query = request.args.get("q", "", type=str).strip()
    page = request.args.get("page", 1, type=int)
    media_type = request.args.get("media_type", "movie", type=str).strip().lower()
    sort_by = request.args.get("sort", "popularity", type=str).strip().lower()
    year = request.args.get("year", "", type=str).strip()

    if media_type not in {"movie", "tv", "all"}:
        media_type = "movie"

    def _matches_year(item):
        if not year:
            return True
        release_value = item.get("release_date") or item.get("first_air_date") or ""
        return release_value.startswith(year)

    def _normalise_items(items):
        normalised = []
        for item in items:
            item_type = item.get("media_type") or ("tv" if item.get("name") and not item.get("title") else "movie")
            if media_type != "all" and item_type != media_type:
                continue
            if not _matches_year(item):
                continue

            item["media_type"] = item_type
            if item_type == "tv":
                item["title"] = item.get("title") or item.get("name")
                item["release_date"] = item.get("release_date") or item.get("first_air_date")
            elif not item.get("title"):
                item["title"] = item.get("name") or "Untitled"
            normalised.append(item)

        if sort_by == "rating":
            normalised.sort(key=lambda item: item.get("vote_average") or 0, reverse=True)
        elif sort_by == "latest":
            normalised.sort(key=lambda item: item.get("release_date") or item.get("first_air_date") or "", reverse=True)
        elif sort_by == "title":
            normalised.sort(key=lambda item: (item.get("title") or item.get("name") or "").lower())
        return normalised

    if query:
        if media_type == "movie":
            movies = TMDBService.search_movies(query, page)
        else:
            movies = TMDBService.search_all(query, page)
        movies = _normalise_items(movies)
    else:
        if media_type == "tv":
            movies = TMDBService.get_popular_tv(page)
        elif media_type == "all":
            movies = TMDBService.get_popular_movies(page) + TMDBService.get_popular_tv(page)
            movies = _normalise_items(movies)
        else:
            movies = TMDBService.get_popular_movies(page)
            movies = _normalise_items(movies)

    filters = {
        "media_type": media_type,
        "sort": sort_by,
        "year": year,
    }

    try:
        return render_template(
            "movies/list.html",
            movies=movies,
            query=query,
            page=page,
            filters=filters,
        )
    finally:
        _log_route_perf("movies.movie_list", started_at)

@movies_bp.route("/<int:movie_id>")
def movie_detail(movie_id):
    started_at = time.perf_counter()
    try:
        movie = TMDBService.get_movie_details(movie_id)
        
        if not movie:
            tv_fallback = TMDBService.get_tv_details(movie_id)
            if tv_fallback:
                return redirect(url_for("movies.tv_detail", tv_id=movie_id))

            current_app.logger.warning("Movie not found: %s", movie_id)
            return render_template("errors/404.html"), 404
        
        review_page = request.args.get("review_page", 1, type=int)
        if review_page < 1:
            review_page = 1

        review_query = Review.query.options(selectinload(Review.user)).filter_by(tmdb_movie_id=movie_id).order_by(Review.created_at.desc())
        reviews_pagination = _safe_db_call(
            lambda: review_query.paginate(page=review_page, per_page=20, error_out=False),
            None,
        )
        reviews = reviews_pagination.items if reviews_pagination else []

        local_stats = _safe_db_call(
            lambda: db.session.query(func.avg(Review.rating), func.count(Review.id)).filter_by(tmdb_movie_id=movie_id).first(),
            (None, 0),
        )
        local_avg = local_stats[0] if local_stats else None
        local_review_count = int(local_stats[1] or 0) if local_stats else 0
        movie['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
        movie['local_review_count'] = local_review_count
        
        in_watchlist = False
        user_review = None
        if current_user.is_authenticated:
            in_watchlist = _safe_db_call(
                lambda: Watchlist.query.filter_by(
                    user_id=current_user.id,
                    tmdb_movie_id=movie_id
                ).first() is not None,
                False,
            )

            user_review = _safe_db_call(
                lambda: Review.query.filter_by(
                    user_id=current_user.id,
                    tmdb_movie_id=movie_id
                ).first(),
                None,
            )
        
        # Build recommendations (lightweight, no extra API calls)
        smart_recs = build_ai_style_recommendations(movie, media_type="movie")
        _track_recently_viewed(movie_id, 'movie')
        recent = session.get('recently_viewed', [])
        if recent:
            recent[0] = _build_recently_viewed_snapshot(movie, 'movie', movie_id)
            session['recently_viewed'] = recent
            session.modified = True
        player_embed = _build_player_context("movie", movie_id)

        existing_progress = None
        if current_user.is_authenticated:
            existing_progress = _safe_db_call(
                lambda: WatchProgress.query.filter_by(
                    user_id=current_user.id,
                    tmdb_id=movie_id,
                    media_type='movie',
                ).first(),
                None,
            )

        if current_user.is_authenticated:
            watchlist_ids = {
                row.tmdb_movie_id
                for row in Watchlist.query.with_entities(Watchlist.tmdb_movie_id).filter_by(user_id=current_user.id).all()
                if row.tmdb_movie_id is not None
            }
            smart_recs = [item for item in smart_recs if item.get('id') not in watchlist_ids]

        return render_template(
            "movies/detail.html",
            movie=movie,
            reviews=reviews,
            in_watchlist=in_watchlist,
            user_review=user_review,
            media_type="movie",
            smart_recs=smart_recs,
            player_embed=player_embed,
            saved_progress=existing_progress,
            reviews_pagination=reviews_pagination,
            embed_allowed_origin=player_embed.get("allowed_origin", ""),
        )
    except Exception as e:
        current_app.logger.exception("Error loading movie details for %s", movie_id)
        return render_template("errors/500.html"), 500
    finally:
        _log_route_perf("movies.movie_detail", started_at)

@movies_bp.route("/tv/<int:tv_id>")
def tv_detail(tv_id):
    started_at = time.perf_counter()
    try:
        show = TMDBService.get_tv_details(tv_id)
        
        if not show:
            movie_fallback = TMDBService.get_movie_details(tv_id)
            if movie_fallback:
                return redirect(url_for("movies.movie_detail", movie_id=tv_id))

            current_app.logger.warning("TV show not found: %s", tv_id)
            return render_template("errors/404.html"), 404
        
        review_page = request.args.get("review_page", 1, type=int)
        if review_page < 1:
            review_page = 1

        review_query = Review.query.options(selectinload(Review.user)).filter_by(tmdb_movie_id=tv_id).order_by(Review.created_at.desc())
        reviews_pagination = _safe_db_call(
            lambda: review_query.paginate(page=review_page, per_page=20, error_out=False),
            None,
        )
        reviews = reviews_pagination.items if reviews_pagination else []

        local_stats = _safe_db_call(
            lambda: db.session.query(func.avg(Review.rating), func.count(Review.id)).filter_by(tmdb_movie_id=tv_id).first(),
            (None, 0),
        )
        local_avg = local_stats[0] if local_stats else None
        local_review_count = int(local_stats[1] or 0) if local_stats else 0
        show['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
        show['local_review_count'] = local_review_count
        
        in_watchlist = False
        user_review = None
        if current_user.is_authenticated:
            in_watchlist = _safe_db_call(
                lambda: Watchlist.query.filter_by(
                    user_id=current_user.id,
                    tmdb_movie_id=tv_id
                ).first() is not None,
                False,
            )

            user_review = _safe_db_call(
                lambda: Review.query.filter_by(
                    user_id=current_user.id,
                    tmdb_movie_id=tv_id
                ).first(),
                None,
            )
        
        tv_seasons = []
        for season in show.get("seasons") or []:
            season_number = season.get("season_number")
            episode_count = season.get("episode_count")
            if not isinstance(season_number, int) or season_number < 1:
                continue
            if not isinstance(episode_count, int) or episode_count < 1:
                continue
            tv_seasons.append(
                {
                    "season_number": season_number,
                    "episode_count": episode_count,
                    "name": season.get("name") or "",
                }
            )

        if not tv_seasons:
            fallback_count = max(int(show.get("number_of_seasons") or 1), 1)
            tv_seasons = [
                {"season_number": season_number, "episode_count": 1, "name": ""}
                for season_number in range(1, fallback_count + 1)
            ]

        tv_seasons.sort(key=lambda season: season["season_number"])
        valid_season_numbers = {season["season_number"] for season in tv_seasons}

        requested_season = request.args.get("season", type=int)
        selected_season = requested_season if requested_season in valid_season_numbers else tv_seasons[0]["season_number"]

        selected_season_meta = next(
            (season for season in tv_seasons if season["season_number"] == selected_season),
            tv_seasons[0],
        )
        max_episodes = max(int(selected_season_meta.get("episode_count") or 1), 1)

        requested_episode = request.args.get("episode", type=int)
        if isinstance(requested_episode, int):
            selected_episode = min(max(requested_episode, 1), max_episodes)
        else:
            selected_episode = 1

        tv_episode_options = list(range(1, max_episodes + 1))

        # Build recommendations (lightweight, no extra API calls)
        smart_recs = build_ai_style_recommendations(show, media_type="tv")
        _track_recently_viewed(tv_id, 'tv')
        recent = session.get('recently_viewed', [])
        if recent:
            recent[0] = _build_recently_viewed_snapshot(show, 'tv', tv_id)
            session['recently_viewed'] = recent
            session.modified = True
        player_embed = _build_player_context("tv", tv_id, season=selected_season, episode=selected_episode)

        existing_progress = None
        if current_user.is_authenticated:
            existing_progress = _safe_db_call(
                lambda: WatchProgress.query.filter_by(
                    user_id=current_user.id,
                    tmdb_id=tv_id,
                    media_type='tv',
                    season=player_embed.get('season'),
                    episode=player_embed.get('episode'),
                ).first(),
                None,
            )

        if current_user.is_authenticated:
            watchlist_ids = {
                row.tmdb_movie_id
                for row in Watchlist.query.with_entities(Watchlist.tmdb_movie_id).filter_by(user_id=current_user.id).all()
                if row.tmdb_movie_id is not None
            }
            smart_recs = [item for item in smart_recs if item.get('id') not in watchlist_ids]

        return render_template(
            "movies/detail.html",
            movie=show,
            reviews=reviews,
            in_watchlist=in_watchlist,
            user_review=user_review,
            media_type="tv",
            smart_recs=smart_recs,
            player_embed=player_embed,
            tv_seasons=tv_seasons,
            tv_episode_options=tv_episode_options,
            saved_progress=existing_progress,
            reviews_pagination=reviews_pagination,
            embed_allowed_origin=player_embed.get("allowed_origin", ""),
        )
    except Exception as e:
        current_app.logger.exception("Error loading TV show details for %s", tv_id)
        return render_template("errors/500.html"), 500
    finally:
        _log_route_perf("movies.tv_detail", started_at)


@movies_bp.route("/progress", methods=["POST"])
@login_required
def save_watch_progress():
    payload = request.get_json(silent=True) or {}

    media_type = (payload.get("mediaType") or payload.get("type") or "").strip().lower()
    if media_type not in {"movie", "tv"}:
        return jsonify({"success": False, "error": "Invalid media type"}), 400

    try:
        tmdb_id = int(payload.get("id") or payload.get("tmdb_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid content id"}), 400

    try:
        current_time = max(int(float(payload.get("currentTime", 0))), 0)
        duration = max(int(float(payload.get("duration", 0))), 0)
        progress_percent = float(payload.get("progress", 0.0) or 0.0)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid progress payload"}), 400

    season = payload.get("season")
    episode = payload.get("episode")
    try:
        season = int(season) if season not in (None, "") else None
        episode = int(episode) if episode not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid season/episode values"}), 400

    last_event = (payload.get("event") or "").strip().lower()[:30]

    record = WatchProgress.query.filter_by(
        user_id=current_user.id,
        tmdb_id=tmdb_id,
        media_type=media_type,
        season=season,
        episode=episode,
    ).first()

    if not record:
        record = WatchProgress(
            user_id=current_user.id,
            tmdb_id=tmdb_id,
            media_type=media_type,
            season=season,
            episode=episode,
        )
        db.session.add(record)
    else:
        # Throttle high-frequency player heartbeats to avoid frequent DB commits that can lag desktop mode.
        same_event = (record.last_event or "") == last_event
        if last_event == "timeupdate" and same_event:
            recently_updated = bool(record.updated_at and (datetime.utcnow() - record.updated_at) < timedelta(seconds=8))
            small_time_delta = abs((record.current_time or 0) - current_time) < 3
            small_progress_delta = abs(float(record.progress_percent or 0.0) - float(progress_percent)) < 0.4
            if recently_updated and small_time_delta and small_progress_delta:
                return jsonify({"success": True, "throttled": True})

    record.current_time = current_time
    record.duration = duration
    record.progress_percent = max(min(progress_percent, 100.0), 0.0)
    record.last_event = last_event

    db.session.commit()
    return jsonify({"success": True})

@movies_bp.route("/<int:movie_id>/review", methods=["POST"])
@login_required
def add_review(movie_id):
    rating = int(request.form.get("rating"))
    text = request.form.get("review_text", "").strip()
    
    if not text:
        flash("Review text is required", "error")
        return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))
    
    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5", "error")
        return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))
    
    review = Review.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    if review:
        review.rating = rating
        review.review_text = text
        flash("Review updated successfully!", "success")
    else:
        review = Review(
            user_id=current_user.id,
            tmdb_movie_id=movie_id,
            rating=rating,
            review_text=text
        )
        db.session.add(review)
        flash("Review added successfully!", "success")
    
    db.session.commit()
    return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))

@movies_bp.route("/<int:movie_id>/review/delete", methods=["POST"])
@login_required
def delete_review(movie_id):
    review = Review.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    if review:
        db.session.delete(review)
        db.session.commit()
        flash("Review deleted successfully!", "success")
    
    return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))


# =====================================================================
# ✅ UPDATED WATCHLIST FUNCTION (Your newer version merged here)
# =====================================================================
@movies_bp.route("/<int:movie_id>/watchlist", methods=["POST"])
@login_required
def toggle_watchlist(movie_id):
    from flask import jsonify

    payload = request.get_json(silent=True) or {}
    media_type = payload.get("media_type") or payload.get("type")

    # Fallback detection when media_type is missing
    if media_type not in ("movie", "tv"):
        media_type = "tv" if (request.referrer and "/tv/" in request.referrer) else "movie"

    entry = Watchlist.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    # REMOVE FROM WATCHLIST
    if entry:
        db.session.delete(entry)
        db.session.commit()
        
        # JSON response (default now)
        return jsonify({'success': True, 'in_watchlist': False})
    
    else:
        # Fetch title from TMDB
        fetch_details = TMDBService.get_tv_details if media_type == "tv" else TMDBService.get_movie_details
        movie = fetch_details(movie_id)
        
        if movie:
            new_entry = Watchlist(
                user_id=current_user.id,
                tmdb_movie_id=movie_id,
                movie_title=movie.get('title', movie.get('name', 'Unknown')),
                poster_path=movie.get('poster_path'),
                media_type=media_type
            )
            db.session.add(new_entry)
            db.session.commit()
            
            # JSON response (default now)
            return jsonify({'success': True, 'in_watchlist': True})
        
        return jsonify({'success': False, 'message': 'Could not fetch movie details'})


@movies_bp.route("/watchlist")
@login_required
def watchlist():
    entries = (
        Watchlist.query
        .filter_by(user_id=current_user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )

    def build_watchlist_card(entry):
        title = (entry.movie_title or '').strip() or 'Unknown'
        media_type = getattr(entry, 'media_type', 'movie') or 'movie'
        return {
            'id': entry.tmdb_movie_id,
            'title': title,
            'name': title,
            'poster_path': entry.poster_path,
            'poster_url': TMDBService.get_image_url(entry.poster_path),
            'media_type': media_type,
            'release_date': '',
            'first_air_date': '',
            'vote_average': 0.0,
        }

    def resolve_entry(entry):
        """Get movie/TV details using stored media_type for better performance."""
        if not getattr(entry, 'tmdb_movie_id', None):
            return None

        media_type = getattr(entry, 'media_type', 'movie')
        if media_type == 'tv':
            details = TMDBService.get_tv_details(entry.tmdb_movie_id)
            return details or TMDBService.get_movie_details(entry.tmdb_movie_id)
        details = TMDBService.get_movie_details(entry.tmdb_movie_id)
        return details or TMDBService.get_tv_details(entry.tmdb_movie_id)

    watchlist_items = []
    enrich_limit = 8
    for idx, entry in enumerate(entries):
        base_item = build_watchlist_card(entry)

        if idx < enrich_limit:
            try:
                item = resolve_entry(entry)
                if item:
                    item['media_type'] = item.get('media_type') or base_item['media_type']
                    watchlist_items.append(item)
                    continue
            except Exception as e:
                current_app.logger.warning("Error resolving watchlist entry %s: %s", entry.tmdb_movie_id, e)

        watchlist_items.append(base_item)

    return render_template(
        "movies/watchlist.html",
        watchlist=watchlist_items
    )


@movies_bp.route("/recommendations")
@login_required
def recommendations():
    if current_app.config.get("DESKTOP_MODE", False):
        return redirect(url_for("main.home"))

    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).limit(20).all()
    
    if not watchlist_entries:
        flash("Add some movies to your watchlist first to get personalized recommendations!", "info")
        return redirect(url_for("users.profile"))
    
    recommendation_seed = _get_watchlist_recommendation_seed(watchlist_entries)
    watchlist_ids = set(recommendation_seed.get('watchlist_ids', []))
    
    try:
        # Get 24 initial recommendations
        recommended_items = get_personalized_recommendations(
            recommendation_seed,
            batch=0,
            items_per_batch=24,
            exclude_ids=watchlist_ids,
        )
    except Exception as e:
        print(f"Recommendation generation error: {e}")
        recommended_items = get_fallback_recommendations(recommendation_seed, limit=24, exclude_ids=watchlist_ids)
    
    # Store seen IDs in session to prevent duplicates on load-more
    session['seen_recommendation_ids'] = list(watchlist_ids) + [item.get('id') for item in recommended_items]
    
    return render_template(
        "movies/recommendations.html",
        recommendations=recommended_items,
        watchlist_count=len(watchlist_entries)
    )


@movies_bp.route("/recommendations/load-more", methods=["POST"])
@login_required
def load_more_recommendations():
    if current_app.config.get("DESKTOP_MODE", False):
        return jsonify({"items": [], "error": "Recommendations unavailable in desktop mode"}), 404

    data = request.get_json()
    items_per_batch = 16
    
    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).limit(20).all()
    
    if not watchlist_entries:
        return jsonify({"items": [], "error": "No watchlist"}), 400

    recommendation_seed = _get_watchlist_recommendation_seed(watchlist_entries)
    watchlist_ids = set(recommendation_seed.get('watchlist_ids', []))
    
    # Get previously seen IDs from session
    seen_ids = set(session.get('seen_recommendation_ids', [])) | watchlist_ids
    
    try:
        # Request a large batch and filter out seen items
        recommended_items = get_personalized_recommendations_paginated(
            recommendation_seed,
            exclude_ids=seen_ids,
            limit=items_per_batch
        )
    except Exception as e:
        print(f"Load more recommendation error: {e}")
        recommended_items = get_fallback_recommendations(recommendation_seed, limit=items_per_batch, exclude_ids=seen_ids)
    
    # Update session with newly seen IDs
    new_ids = [item.get('id') for item in recommended_items]
    session['seen_recommendation_ids'] = list(seen_ids) + new_ids
    session.modified = True
    
    # Format items for JSON response
    items_data = []
    for item in recommended_items:
        items_data.append({
            'id': item.get('id'),
            'title': item.get('title'),
            'poster_url': item.get('poster_url'),
            'media_type': item.get('media_type', 'movie'),
            'release_date': item.get('release_date', ''),
            'vote_average': item.get('vote_average', 0)
        })
    
    return jsonify({"items": items_data}), 200

def get_personalized_recommendations(seed, batch=0, items_per_batch=24, exclude_ids=None):
    watchlist_titles = seed.get('titles', [])
    watchlist_genres = seed.get('genres', [])
    media_counts = seed.get('media_counts', {})

    if exclude_ids is None:
        exclude_ids = set()

    if not watchlist_titles:
        return get_fallback_recommendations(seed, limit=items_per_batch, exclude_ids=exclude_ids)
    
    try:
        titles_str = ", ".join(watchlist_titles[:15])
        genres_str = ", ".join(set(watchlist_genres[:15]))
        media_pref = (
            f"Movies: {media_counts.get('movie', 0)}, "
            f"Series: {media_counts.get('tv', 0)}, "
            f"Anime: {media_counts.get('anime', 0)}"
        )
        
        prompt = f"""Based on a user who enjoys these movies/shows: {titles_str}

Their favorite genres are: {genres_str}

    Watchlist media preference profile: {media_pref}

    Recommend {items_per_batch * 3} movies and TV shows that match their taste. Focus on:
1. Similar plots and themes
2. Same genres
3. Similar tone and style
4. Well-reviewed titles
    5. Strictly follow the media preference profile; if anime count is highest, prioritize anime/JP animated series.
    6. Avoid western kids/3D family cartoons unless they strongly match the seed titles.

Return ONLY valid JSON array:
[
  {{"title": "Movie/Show Name", "year": 2020}},
  ...
]"""

        recommendations = _call_anthropic_recommendation(prompt)
        if not recommendations:
            return get_fallback_recommendations(seed, limit=items_per_batch, exclude_ids=exclude_ids)
        
        results = []
        seen_ids = set(exclude_ids)
        for rec in recommendations:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 1)
            
            if movies:
                for movie in movies:
                    if movie['id'] not in seen_ids:
                        seen_ids.add(movie['id'])
                        results.append(movie)
                        if len(results) >= items_per_batch * 4:
                            break
            
            if len(results) >= items_per_batch * 4:
                break

        mixed = _apply_media_mix(results, seed, limit=items_per_batch, exclude_ids=exclude_ids)
        return mixed if mixed else get_fallback_recommendations(seed, limit=items_per_batch, exclude_ids=exclude_ids)
    
    except Exception as e:
        current_app.logger.warning("AI recommendation error: %s", e)
        return get_fallback_recommendations(seed, limit=items_per_batch, exclude_ids=exclude_ids)


def get_personalized_recommendations_paginated(seed, exclude_ids=None, limit=16):
    """Get paginated recommendations excluding previously seen IDs"""
    if exclude_ids is None:
        exclude_ids = set()

    watchlist_titles = seed.get('titles', [])
    watchlist_genres = seed.get('genres', [])
    media_counts = seed.get('media_counts', {})
    
    if not watchlist_titles:
        return get_fallback_recommendations(seed, limit=limit, exclude_ids=exclude_ids)
    
    try:
        titles_str = ", ".join(watchlist_titles[:15])
        genres_str = ", ".join(set(watchlist_genres[:15]))
        media_pref = (
            f"Movies: {media_counts.get('movie', 0)}, "
            f"Series: {media_counts.get('tv', 0)}, "
            f"Anime: {media_counts.get('anime', 0)}"
        )
        
        prompt = f"""Based on a user who enjoys these movies/shows: {titles_str}

Their favorite genres are: {genres_str}

    Watchlist media preference profile: {media_pref}

    Recommend {limit * 4} DIFFERENT movies and TV shows (completely different from previous recommendations). Focus on:
1. Different themes but similar quality
2. Same genres but lesser-known titles
3. Similar tone but different stories
4. Well-reviewed hidden gems
    5. Follow the media preference profile; if anime count is highest, return mostly anime/JP animated series.
    6. Avoid western kids/3D family cartoons unless highly relevant.

Return ONLY valid JSON array:
[
  {{"title": "Movie/Show Name", "year": 2020}},
  ...
]"""

        recommendations = _call_anthropic_recommendation(prompt)
        if not recommendations:
            return get_fallback_recommendations(seed, limit=limit, exclude_ids=exclude_ids)
        
        results = []
        temp_seen = set(exclude_ids)
        for rec in recommendations:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 1)
            
            if movies:
                for movie in movies:
                    movie_id = movie.get('id')
                    if movie_id and movie_id not in temp_seen:
                        temp_seen.add(movie_id)
                        results.append(movie)
                        if len(results) >= limit * 4:
                            break
            
            if len(results) >= limit * 4:
                break

        mixed = _apply_media_mix(results, seed, limit=limit, exclude_ids=exclude_ids)
        return mixed if mixed else get_fallback_recommendations(seed, limit=limit, exclude_ids=exclude_ids)
    
    except Exception as e:
        current_app.logger.warning("AI paginated recommendation error: %s", e)
        return get_fallback_recommendations(seed, limit=limit, exclude_ids=exclude_ids)


def get_fallback_recommendations(seed, limit=24, exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = set()
    
    try:
        genres = seed.get('genres', [])
        movie_genres = seed.get('movie_genres', [])
        tv_genres = seed.get('tv_genres', [])
        anime_genres = seed.get('anime_genres', [])
        all_genres = TMDBService.get_genres()

        results = []

        anime_pool = []
        for item in TMDBService.get_trending_anime(page=1)[:24] + TMDBService.get_top_rated_anime(page=1)[:24]:
            item['media_type'] = 'anime'
            anime_pool.append(item)

        tv_pool = TMDBService.get_trending_tv('week', page=1, limit=24)[:24] + TMDBService.get_top_rated_tv(page=1, limit=24)[:24]
        movie_pool = TMDBService.get_popular_movies(1)[:24] + TMDBService.get_top_rated_movies(page=1, limit=24)[:24]

        if all_genres and genres:
            genre_counts = Counter(genres)
            top_genre_names = [name for name, _ in genre_counts.most_common(6)]
            if movie_genres:
                top_genre_names = movie_genres[:3] + top_genre_names
            if tv_genres:
                top_genre_names = tv_genres[:3] + top_genre_names
            if anime_genres:
                top_genre_names = anime_genres[:3] + top_genre_names

            top_genre_names = list(dict.fromkeys(top_genre_names))[:6]
            genre_ids = [g['id'] for g in all_genres if g['name'] in top_genre_names]
            for gid in genre_ids[:4]:
                movie_pool.extend(TMDBService.get_movies_by_genre(gid, 1)[:12])

        results.extend(anime_pool)
        results.extend(tv_pool)
        results.extend(movie_pool)

        mixed = _apply_media_mix(results, seed, limit=limit, exclude_ids=exclude_ids)
        if mixed:
            return mixed

        popular = TMDBService.get_popular_movies(1)[:limit * 2]
        filtered = [m for m in popular if m.get('id') not in exclude_ids]
        return filtered[:limit]
        
    except Exception as e:
        print(f"Fallback recommendation error: {e}")
        popular = TMDBService.get_popular_movies(1)[:limit*2]
        filtered = [m for m in popular if m['id'] not in exclude_ids]
        return filtered[:limit]
