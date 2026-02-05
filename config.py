import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # ========================================
    # SECURITY CONFIGURATION
    # ========================================
    
    # Generate a secure random key if not provided
    # In production, ALWAYS set SECRET_KEY environment variable
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    
    # CSRF Protection (Flask-WTF)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # CSRF tokens don't expire (better UX)
    WTF_CSRF_SSL_STRICT = os.environ.get("FLASK_ENV") == "production"
    
    # Session Security
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 2592000  # 30 days in seconds
    
    # Security Headers
    SECURITY_HEADERS = True
    
    # ========================================
    # DATABASE CONFIGURATION
    # ========================================
    
    # Use PostgreSQL on Render (DATABASE_URL), fallback to SQLite locally
    if os.environ.get("DATABASE_URL"):
        # Render PostgreSQL with connection pooling
        SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 10,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
            "max_overflow": 20
        }
    else:
        # Local SQLite (WARNING: NOT for production at scale)
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "cine_sphere.db")
        SQLALCHEMY_ENGINE_OPTIONS = {}
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ========================================
    # RATE LIMITING CONFIGURATION
    # ========================================
    
    # Redis for rate limiting (fallback to memory for local dev)
    REDIS_URL = os.environ.get("REDIS_URL") or None
    RATELIMIT_STORAGE_URL = REDIS_URL or "memory://"
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    
    # Default rate limits
    RATELIMIT_DEFAULT = "200 per hour"
    RATELIMIT_LOGIN = "5 per minute"
    RATELIMIT_REGISTER = "3 per hour"
    RATELIMIT_API = "100 per hour"
    
    # ========================================
    # TMDB API CONFIGURATION
    # ========================================
    
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "YOUR_TMDB_API_KEY_HERE"
    TMDB_BASE_URL = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
    TMDB_POSTER_SIZE = "w500"  # Options: w92, w154, w185, w342, w500, w780, original
    TMDB_BACKDROP_SIZE = "w1280"  # Options: w300, w780, w1280, original
    
    # ========================================
    # GOOGLE OAUTH CONFIGURATION
    # ========================================
    
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or "YOUR_GOOGLE_CLIENT_ID"
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or "YOUR_GOOGLE_CLIENT_SECRET"
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    
    # ========================================
    # PASSWORD POLICY
    # ========================================
    
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_PASSWORD_UPPERCASE = True
    REQUIRE_PASSWORD_LOWERCASE = True
    REQUIRE_PASSWORD_DIGIT = True
    REQUIRE_PASSWORD_SPECIAL = False  # Optional for better UX