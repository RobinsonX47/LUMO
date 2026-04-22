from flask import Blueprint, render_template, request, session
from flask_login import current_user
from ...services.tmdb_service import TMDBService
from ...core.models import WatchProgress

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    """Optimized home page - only load carousel to reduce API calls"""
    # Get hero carousel movies (5 random popular movies)
    hero_movies = TMDBService.get_random_hero_movies(5)

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
    trending_movies = TMDBService.get_trending_movies('week')
    top_rated_movies = TMDBService.get_top_rated_movies()
    popular_movies = TMDBService.get_popular_movies(1)
    
    # We dynamically find the genre IDs for Action and Comedy so we aren't hardcoded to TMDB keys
    action_genre_id = 28
    comedy_genre_id = 35
    for genre in TMDBService.get_genres():
        name = genre.get('name', '').lower()
        if name == 'action': action_genre_id = genre.get('id')
        elif name == 'comedy': comedy_genre_id = genre.get('id')
        
    action_movies = TMDBService.get_movies_by_genre(action_genre_id, 1)
    comedy_movies = TMDBService.get_movies_by_genre(comedy_genre_id, 1)
    
    return render_template(
        "sections/movies.html",
        trending=trending_movies,
        top_rated=top_rated_movies,
        popular=popular_movies,
        action=action_movies,
        comedy=comedy_movies
    )

@main_bp.route("/movies/trending")
def movies_trending():
    """Trending movies page"""
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    if page > 500:
        page = 500

    trending_movies = TMDBService.get_trending_movies('week', page=page, limit=20)

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

    top_rated_items = TMDBService.get_top_rated_all(limit=20, page=page)

    return render_template(
        "sections/movies_top_rated.html",
        items=top_rated_items,
        page=page,
    )

@main_bp.route("/anime")
def anime_section():
    """Dedicated anime section"""
    trending_anime = TMDBService.get_trending_anime()
    top_rated_anime = TMDBService.get_top_rated_anime()
    
    return render_template(
        "sections/anime.html",
        trending=trending_anime,
        top_rated=top_rated_anime
    )

@main_bp.route("/series")
def series_section():
    """Dedicated TV series section"""
    trending_series = TMDBService.get_trending_tv()
    top_rated_series = TMDBService.get_top_rated_tv()
    
    return render_template(
        "sections/series.html",
        trending=trending_series,
        top_rated=top_rated_series
    )

@main_bp.route("/genres")
def genres_page():
    """Separate genres browsing page"""
    genres = TMDBService.get_genres()
    
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
    movies = TMDBService.get_movies_by_genre(genre_id, page)
    genres = TMDBService.get_genres()
    
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