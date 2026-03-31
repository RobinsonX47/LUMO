from flask import Blueprint, render_template, request, session
from tmdb_service import TMDBService

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

        details = TMDBService.get_tv_details(item_id) if media_type == 'tv' else TMDBService.get_movie_details(item_id)
        if details:
            recently_viewed.append(details)
    
    return render_template(
        "index.html",
        hero_movies=hero_movies,
        recently_viewed=recently_viewed
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
    trending_movies = TMDBService.get_trending_movies('week', limit=56)

    return render_template(
        "sections/movies_trending.html",
        movies=trending_movies
    )

@main_bp.route("/movies/top-rated")
def movies_top_rated():
    """Top rated movies and shows page"""
    top_rated_items = TMDBService.get_top_rated_all(limit=104)

    return render_template(
        "sections/movies_top_rated.html",
        items=top_rated_items
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