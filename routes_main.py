from flask import Blueprint, render_template, request
from tmdb_service import TMDBService

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    # Get hero carousel movies (5 random popular movies)
    hero_movies = TMDBService.get_random_hero_movies(5)
    
    # Get trending movies of the week
    trending_movies = TMDBService.get_trending_movies('week')
    
    # Get top rated movies of all time
    top_rated_movies = TMDBService.get_top_rated_movies()
    
    # Get all genres for genre selection
    genres = TMDBService.get_genres()
    
    return render_template(
        "index.html",
        hero_movies=hero_movies,
        trending=trending_movies,
        top_rated=top_rated_movies,
        genres=genres
    )

@main_bp.route("/genre/<int:genre_id>")
def movies_by_genre(genre_id):
    page = request.args.get('page', 1, type=int)
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