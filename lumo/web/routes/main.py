from flask import Blueprint, render_template, request, session, current_app
from flask_login import current_user
from ...services.tmdb_service import TMDBService
from ...core.models import WatchProgress
from concurrent.futures import ThreadPoolExecutor
import threading
import time

main_bp = Blueprint("main", __name__)

MAX_TMDB_ROUTE_WORKERS = 5


def _run_parallel(fetchers):
    """Run independent callables concurrently and return a name->result map."""
    if not fetchers:
        return {}

    app = current_app._get_current_object()

    def run_with_app_context(callable_fn):
        with app.app_context():
            return callable_fn()

    max_workers = min(MAX_TMDB_ROUTE_WORKERS, len(fetchers))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            name: executor.submit(run_with_app_context, callable_fn)
            for name, callable_fn in fetchers.items()
        }
        return {name: future.result() for name, future in futures.items()}


def _get_cached_public_payload(cache_key, builder, ttl_seconds=None):
    """Short-lived in-process cache for non-user-specific route payloads."""
    ttl = int(ttl_seconds or current_app.config.get("PUBLIC_FRAGMENT_CACHE_SECONDS", 120) or 120)
    cache_version = current_app.config.get("PUBLIC_FRAGMENT_CACHE_VERSION", "v1")
    max_entries = int(current_app.config.get("PUBLIC_FRAGMENT_CACHE_MAX_ENTRIES", 512) or 512)
    storage = current_app.extensions.setdefault("public_fragment_cache", {})
    lock = current_app.extensions.setdefault("public_fragment_cache_lock", threading.Lock())
    namespaced_key = f"{cache_version}:{cache_key}"
    now_ts = time.time()

    with lock:
        cached = storage.get(namespaced_key)
        if cached and cached[0] > now_ts:
            return cached[1]
        if cached and cached[0] <= now_ts:
            storage.pop(namespaced_key, None)

    value = builder()
    with lock:
        # Opportunistically prune expired entries first.
        expired_keys = [k for k, (expires_at, _) in storage.items() if expires_at <= now_ts]
        for expired_key in expired_keys:
            storage.pop(expired_key, None)

        # Keep memory usage bounded when many cache keys are created.
        while len(storage) >= max_entries:
            storage.pop(next(iter(storage)), None)

        storage[namespaced_key] = (now_ts + ttl, value)
    return value

@main_bp.route("/")
def home():
    """Optimized home page - only load carousel to reduce API calls"""
    # Get hero carousel movies (5 random popular movies)
    hero_movies = _get_cached_public_payload(
        "home:hero_movies:5",
        lambda: TMDBService.get_random_hero_movies(5),
        ttl_seconds=current_app.config.get("PUBLIC_HERO_CACHE_SECONDS"),
    )

    recently_viewed = []
    for item in session.get('recently_viewed', [])[:8]:
        item_id = item.get('id')
        media_type = item.get('media_type', 'movie')
        if not item_id:
            continue

        # Prefer the compact session snapshot to avoid a fresh TMDB request.
        title = (item.get('title') or item.get('name') or '').strip()
        poster_path = item.get('poster_path')
        release_date = item.get('release_date') or item.get('first_air_date') or ''
        vote_average = item.get('vote_average')

        if title and (poster_path or release_date or vote_average is not None):
            recently_viewed.append({
                'id': item_id,
                'media_type': media_type,
                'title': title,
                'name': title,
                'poster_path': poster_path,
                'poster_url': TMDBService.get_image_url(poster_path) if poster_path else None,
                'release_date': release_date,
                'vote_average': vote_average if vote_average is not None else 0.0,
            })
            continue

        details = TMDBService.get_tv_card_details(item_id) if media_type == 'tv' else TMDBService.get_movie_card_details(item_id)
        if details:
            recently_viewed.append(details)

    continue_watching = []
    if current_user.is_authenticated:
        progress_entries = (
            WatchProgress.query
            .filter_by(user_id=current_user.id)
            .order_by(WatchProgress.updated_at.desc())
            .limit(4)
            .all()
        )
        for progress in progress_entries:
            if float(progress.progress_percent or 0.0) >= 95.0 and (progress.last_event or "") in {"ended", "complete", "finished"}:
                continue

            details = TMDBService.get_tv_card_details(progress.tmdb_id) if progress.media_type == 'tv' else TMDBService.get_movie_card_details(progress.tmdb_id)
            if not details:
                continue

            details['media_type'] = progress.media_type
            details['progress_percent'] = float(progress.progress_percent or 0.0)
            details['saved_progress'] = progress
            continue_watching.append(details)
    
    return render_template(
        "index.html",
        hero_movies=hero_movies,
        recently_viewed=recently_viewed,
        continue_watching=continue_watching,
    )

@main_bp.route("/movies")
def movies_section():
    """Dedicated movies section with trending and top rated"""
    def build_payload():
        base_sections = _run_parallel({
            'trending': lambda: TMDBService.get_trending_movies('week'),
            'top_rated': TMDBService.get_top_rated_movies,
            'popular': lambda: TMDBService.get_popular_movies(1, limit=24),
            'genres': TMDBService.get_genres,
        })

        trending_movies = base_sections.get('trending') or []
        top_rated_movies = base_sections.get('top_rated') or []
        popular_movies = base_sections.get('popular') or []
        genre_list = base_sections.get('genres') or []

        action_genre_id = 28
        comedy_genre_id = 35
        for genre in genre_list:
            name = genre.get('name', '').lower()
            if name == 'action':
                action_genre_id = genre.get('id')
            elif name == 'comedy':
                comedy_genre_id = genre.get('id')

        genre_sections = _run_parallel({
            'action': lambda: TMDBService.get_movies_by_genre(action_genre_id, 1, limit=24),
            'comedy': lambda: TMDBService.get_movies_by_genre(comedy_genre_id, 1, limit=24),
        })

        return {
            'trending': trending_movies,
            'top_rated': top_rated_movies,
            'popular': popular_movies,
            'action': genre_sections.get('action') or [],
            'comedy': genre_sections.get('comedy') or [],
        }

    payload = _get_cached_public_payload(
        "sections:movies",
        build_payload,
        ttl_seconds=current_app.config.get("PUBLIC_DISCOVERY_CACHE_SECONDS"),
    )
    
    return render_template(
        "sections/movies.html",
        trending=payload['trending'],
        top_rated=payload['top_rated'],
        popular=payload['popular'],
        action=payload['action'],
        comedy=payload['comedy']
    )

@main_bp.route("/movies/trending")
def movies_trending():
    """Trending movies page"""
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    if page > 500:
        page = 500

    trending_movies = _get_cached_public_payload(
        f"sections:movies_trending:page:{page}",
        lambda: TMDBService.get_trending_movies('week', page=page, limit=20),
        ttl_seconds=current_app.config.get("PUBLIC_DISCOVERY_CACHE_SECONDS"),
    )

    return render_template(
        "sections/movies_trending.html",
        movies=trending_movies,
        page=page,
    )

@main_bp.route("/movies/top-rated")
def movies_top_rated():
    """Top rated movies and shows page"""
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    if page > 500:
        page = 500

    top_rated_items = _get_cached_public_payload(
        f"sections:movies_top_rated:page:{page}",
        lambda: TMDBService.get_top_rated_all(limit=20, page=page),
        ttl_seconds=current_app.config.get("PUBLIC_DISCOVERY_CACHE_SECONDS"),
    )

    return render_template(
        "sections/movies_top_rated.html",
        items=top_rated_items,
        page=page,
    )

@main_bp.route("/anime")
def anime_section():
    """Dedicated anime section"""
    anime_sections = _get_cached_public_payload(
        "sections:anime",
        lambda: _run_parallel({
            'trending': TMDBService.get_trending_anime,
            'top_rated': TMDBService.get_top_rated_anime,
        }),
        ttl_seconds=current_app.config.get("PUBLIC_DISCOVERY_CACHE_SECONDS"),
    )
    trending_anime = anime_sections.get('trending') or []
    top_rated_anime = anime_sections.get('top_rated') or []
    
    return render_template(
        "sections/anime.html",
        trending=trending_anime,
        top_rated=top_rated_anime
    )

@main_bp.route("/series")
def series_section():
    """Dedicated TV series section"""
    series_sections = _get_cached_public_payload(
        "sections:series",
        lambda: _run_parallel({
            'trending': TMDBService.get_trending_tv,
            'top_rated': TMDBService.get_top_rated_tv,
        }),
        ttl_seconds=current_app.config.get("PUBLIC_DISCOVERY_CACHE_SECONDS"),
    )
    trending_series = series_sections.get('trending') or []
    top_rated_series = series_sections.get('top_rated') or []
    
    return render_template(
        "sections/series.html",
        trending=trending_series,
        top_rated=top_rated_series
    )

@main_bp.route("/genres")
def genres_page():
    """Separate genres browsing page"""
    genres = _get_cached_public_payload(
        "sections:genres",
        TMDBService.get_genres,
        ttl_seconds=current_app.config.get("PUBLIC_GENRES_CACHE_SECONDS"),
    )
    
    return render_template(
        "sections/genres.html",
        genres=genres
    )

@main_bp.route("/genre/<int:genre_id>")
def movies_by_genre(genre_id):
    """Movies filtered by genre"""
    page = request.args.get('page', 1, type=int)
    # Cap pagination to prevent hitting downstream API errors
    if page > 500:
        page = 500
    movies = _get_cached_public_payload(
        f"sections:genre:{genre_id}:page:{page}",
        lambda: TMDBService.get_movies_by_genre(genre_id, page),
        ttl_seconds=current_app.config.get("PUBLIC_DISCOVERY_CACHE_SECONDS"),
    )
    genres = _get_cached_public_payload(
        "sections:genres",
        TMDBService.get_genres,
        ttl_seconds=current_app.config.get("PUBLIC_GENRES_CACHE_SECONDS"),
    )
    
    # Find genre name
    genre_name = "Movies"
    for genre in genres:
        if genre['id'] == genre_id:
            genre_name = genre['name']
            break
    
    return render_template(
        "movies/genre.html",
        movies=movies,
        genres=genres,
        current_genre_id=genre_id,
        genre_name=genre_name,
        page=page
    )