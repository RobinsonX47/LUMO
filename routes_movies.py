from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session, g
from flask_login import current_user, login_required
from extensions import db
from models import Review, Watchlist, WatchProgress
from tmdb_service import TMDBService
from embed_provider_service import build_movie_embed_url, build_tv_embed_url, normalize_provider_base_url
from sqlalchemy import func
import requests
import json
import time
from datetime import datetime, timedelta


def build_ai_style_recommendations(base_item, media_type):
    """Lightweight recommendations using TMDB similar data only - no extra API calls."""
    if not base_item:
        return []
    
    try:
        # Use TMDB's similar results directly - they're already good
        similar_block = base_item.get('similar', {})
        if not similar_block or not isinstance(similar_block, dict):
            return []
        
        candidates = similar_block.get('results', []) or []
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
        
        # Score candidates using only data already available
        scored = []
        for cand in candidates[:12]:  # Only process first 12 similar items
            if not cand.get('id') or cand.get('id') == base_item.get('id'):
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
            
            vote = cand.get('vote_average', 0)
            
            # Simple scoring: genre match + era + rating
            score = genre_overlap * 3 + era_score * 2 + (vote / 10)
            
            # Set media type
            cand['media_type'] = cand.get('media_type') or (
                'tv' if (cand.get('name') and not cand.get('title')) else 'movie'
            )
            
            scored.append({'data': cand, 'score': score})
        
        # Sort and return top 6
        scored.sort(key=lambda x: x['score'], reverse=True)
        return [s['data'] for s in scored[:6]]
    
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


def _get_watchlist_recommendation_seed(watchlist_entries, max_title_items=15, max_genre_items=8):
    """Build recommendation seed data while limiting expensive TMDB detail lookups."""
    watchlist_titles = []
    watchlist_genres = []

    for idx, entry in enumerate(watchlist_entries[:max_title_items]):
        title = (entry.movie_title or "").strip()
        if title:
            watchlist_titles.append(title)
        else:
            fetch_details = TMDBService.get_tv_details if getattr(entry, 'media_type', 'movie') == 'tv' else TMDBService.get_movie_details
            details = fetch_details(entry.tmdb_movie_id)
            if details:
                watchlist_titles.append(details.get('title') or details.get('name') or 'Unknown')

        # Pull genre signals from only the first few entries to cap network overhead.
        if idx < max_genre_items:
            fetch_details = TMDBService.get_tv_details if getattr(entry, 'media_type', 'movie') == 'tv' else TMDBService.get_movie_details
            details = fetch_details(entry.tmdb_movie_id)
            if details and details.get('genres'):
                watchlist_genres.extend([g['name'] for g in details['genres'] if g.get('name')])

    return watchlist_titles, watchlist_genres


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
    auto_play = current_app.config.get("EMBED_PROVIDER_AUTOPLAY", False)

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
        
        reviews = _safe_db_call(
            lambda: Review.query.filter_by(tmdb_movie_id=movie_id).order_by(Review.created_at.desc()).all(),
            [],
        )

        local_avg = _safe_db_call(
            lambda: db.session.query(func.avg(Review.rating)).filter_by(tmdb_movie_id=movie_id).scalar(),
            None,
        )
        movie['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
        movie['local_review_count'] = len(reviews)
        
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
        
        reviews = _safe_db_call(
            lambda: Review.query.filter_by(tmdb_movie_id=tv_id).order_by(Review.created_at.desc()).all(),
            [],
        )

        local_avg = _safe_db_call(
            lambda: db.session.query(func.avg(Review.rating)).filter_by(tmdb_movie_id=tv_id).scalar(),
            None,
        )
        show['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
        show['local_review_count'] = len(reviews)
        
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
    
    watchlist_titles, watchlist_genres = _get_watchlist_recommendation_seed(watchlist_entries)
    
    try:
        # Get 24 initial recommendations
        recommended_items = get_personalized_recommendations(watchlist_titles, watchlist_genres, batch=0, items_per_batch=24)
    except Exception as e:
        print(f"Recommendation generation error: {e}")
        recommended_items = get_fallback_recommendations(watchlist_genres, limit=24)
    
    # Store seen IDs in session to prevent duplicates on load-more
    session['seen_recommendation_ids'] = [item.get('id') for item in recommended_items]
    
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

    watchlist_titles, watchlist_genres = _get_watchlist_recommendation_seed(watchlist_entries)
    
    # Get previously seen IDs from session
    seen_ids = set(session.get('seen_recommendation_ids', []))
    
    try:
        # Request a large batch and filter out seen items
        recommended_items = get_personalized_recommendations_paginated(
            watchlist_titles, 
            watchlist_genres, 
            exclude_ids=seen_ids,
            limit=items_per_batch
        )
    except Exception as e:
        print(f"Load more recommendation error: {e}")
        recommended_items = get_fallback_recommendations(watchlist_genres, limit=items_per_batch, exclude_ids=seen_ids)
    
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

def get_personalized_recommendations(watchlist_titles, watchlist_genres, batch=0, items_per_batch=24):
    if not watchlist_titles:
        return get_fallback_recommendations(watchlist_genres, limit=items_per_batch)
    
    try:
        titles_str = ", ".join(watchlist_titles[:15])
        genres_str = ", ".join(set(watchlist_genres[:15]))
        
        prompt = f"""Based on a user who enjoys these movies/shows: {titles_str}

Their favorite genres are: {genres_str}

Recommend {items_per_batch * 2} movies and TV shows that match their taste. Focus on:
1. Similar plots and themes
2. Same genres
3. Similar tone and style
4. Well-reviewed titles

Return ONLY valid JSON array:
[
  {{"title": "Movie/Show Name", "year": 2020}},
  ...
]"""

        recommendations = _call_anthropic_recommendation(prompt)
        if not recommendations:
            return get_fallback_recommendations(watchlist_genres, limit=items_per_batch)
        
        results = []
        seen_ids = set()
        for rec in recommendations:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 3)
            
            if movies:
                for movie in movies:
                    if movie['id'] not in seen_ids:
                        seen_ids.add(movie['id'])
                        results.append(movie)
                        if len(results) >= items_per_batch * 2:
                            break
            
            if len(results) >= items_per_batch * 2:
                break
        
        return results[:items_per_batch] if results else get_fallback_recommendations(watchlist_genres, limit=items_per_batch)
    
    except Exception as e:
        current_app.logger.warning("AI recommendation error: %s", e)
        return get_fallback_recommendations(watchlist_genres, limit=items_per_batch)


def get_personalized_recommendations_paginated(watchlist_titles, watchlist_genres, exclude_ids=None, limit=16):
    """Get paginated recommendations excluding previously seen IDs"""
    if exclude_ids is None:
        exclude_ids = set()
    
    if not watchlist_titles:
        return get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)
    
    try:
        titles_str = ", ".join(watchlist_titles[:15])
        genres_str = ", ".join(set(watchlist_genres[:15]))
        
        prompt = f"""Based on a user who enjoys these movies/shows: {titles_str}

Their favorite genres are: {genres_str}

Recommend {limit * 3} DIFFERENT movies and TV shows (completely different from previous recommendations). Focus on:
1. Different themes but similar quality
2. Same genres but lesser-known titles
3. Similar tone but different stories
4. Well-reviewed hidden gems

Return ONLY valid JSON array:
[
  {{"title": "Movie/Show Name", "year": 2020}},
  ...
]"""

        recommendations = _call_anthropic_recommendation(prompt)
        if not recommendations:
            return get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)
        
        results = []
        for rec in recommendations:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 3)
            
            if movies:
                for movie in movies:
                    if movie['id'] not in exclude_ids:
                        results.append(movie)
                        if len(results) >= limit:
                            break
            
            if len(results) >= limit:
                break
        
        return results[:limit] if results else get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)
    
    except Exception as e:
        current_app.logger.warning("AI paginated recommendation error: %s", e)
        return get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)


def get_fallback_recommendations(genres, limit=24, exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = set()
    
    try:
        all_genres = TMDBService.get_genres()
        
        if not genres or not all_genres:
            popular = TMDBService.get_popular_movies(1)[:limit*2]
            filtered = [m for m in popular if m['id'] not in exclude_ids]
            return filtered[:limit]
        
        genre_counts = {}
        for g in genres:
            genre_counts[g] = genre_counts.get(g, 0) + 1
        
        top_genre_names = [g[0] for g in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:4]]
        
        genre_ids = [g['id'] for g in all_genres if g['name'] in top_genre_names]
        
        results = []
        
        # Get movies from top genres with increased page sampling
        for gid in genre_ids[:4]:
            for page in range(1, 5):
                movies = TMDBService.get_movies_by_genre(gid, page)
                for movie in movies[:10]:
                    if movie['id'] not in exclude_ids:
                        results.append(movie)
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
        
        # If still not enough, add popular movies
        if len(results) < limit:
            popular = TMDBService.get_popular_movies(1)[:20]
            for movie in popular:
                if movie['id'] not in exclude_ids:
                    results.append(movie)
                    if len(results) >= limit:
                        break
        
        return results[:limit]
        
    except Exception as e:
        print(f"Fallback recommendation error: {e}")
        popular = TMDBService.get_popular_movies(1)[:limit*2]
        filtered = [m for m in popular if m['id'] not in exclude_ids]
        return filtered[:limit]
