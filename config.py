import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "change-this-secret-key-in-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "cine_sphere.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # TMDB API Configuration
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "YOUR_TMDB_API_KEY_HERE"
    TMDB_BASE_URL = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
    TMDB_POSTER_SIZE = "w500"  # Options: w92, w154, w185, w342, w500, w780, original
    TMDB_BACKDROP_SIZE = "w1280"  # Options: w300, w780, w1280, original