import os
import secrets
from urllib.parse import urlsplit, urlunsplit

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalize_database_url(raw_url):
    """Normalize DATABASE_URL for SQLAlchemy + psycopg and validate host format."""
    db_url = (raw_url or "").strip()
    if not db_url:
        return ""

    # Normalize driver prefix for SQLAlchemy 2 + psycopg3.
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    parsed = urlsplit(db_url)
    host = parsed.hostname or ""

    # If DATABASE_URL is incomplete but PG* variables are available (common on hosted
    # platforms), rebuild using the explicit PGHOST/PGPORT/PGDATABASE values.
    if host.startswith("dpg-") and "." not in host:
        pg_host = (os.environ.get("PGHOST") or "").strip()
        pg_port = (os.environ.get("PGPORT") or "").strip()
        pg_db = (os.environ.get("PGDATABASE") or "").strip()
        pg_user = (os.environ.get("PGUSER") or parsed.username or "").strip()
        pg_password = os.environ.get("PGPASSWORD") or parsed.password
        pg_sslmode = (os.environ.get("PGSSLMODE") or "require").strip()

        if pg_host and pg_port and pg_db:
            auth = ""
            if pg_user:
                auth = pg_user
                if pg_password is not None:
                    auth = f"{auth}:{pg_password}"
                auth = f"{auth}@"

            path = f"/{pg_db}"
            query = parsed.query
            if pg_sslmode and "sslmode=" not in query:
                query = f"sslmode={pg_sslmode}" if not query else f"{query}&sslmode={pg_sslmode}"

            rebuilt_netloc = f"{auth}{pg_host}:{pg_port}"
            db_url = urlunsplit((parsed.scheme, rebuilt_netloc, path, query, parsed.fragment))
            parsed = urlsplit(db_url)
            host = parsed.hostname or ""

    # Some deployments provide shortened Render hostnames like dpg-<id>-a
    # without the region suffix. Attempt to complete these automatically.
    if host.startswith("dpg-") and "." not in host:
        host_suffix = (os.environ.get("RENDER_POSTGRES_HOST_SUFFIX") or "").strip(". ")
        if host_suffix:
            username = parsed.username or ""
            password = parsed.password
            auth = ""
            if username:
                auth = username
                if password is not None:
                    auth = f"{auth}:{password}"
                auth = f"{auth}@"

            port = f":{parsed.port}" if parsed.port else ""
            completed_host = f"{host}.{host_suffix}"
            netloc = f"{auth}{completed_host}{port}"
            db_url = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
            parsed = urlsplit(db_url)
            host = parsed.hostname or ""

    if not host:
        raise RuntimeError("DATABASE_URL is set but invalid: hostname is missing")

    if host.startswith("dpg-") and "." not in host:
        raise RuntimeError(
            "DATABASE_URL hostname appears incomplete. Set full Render hostname "
            "(for example dpg-...<region>-postgres.render.com) or set RENDER_POSTGRES_HOST_SUFFIX."
        )

    return db_url

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
    SESSION_COOKIE_SAMESITE = "Strict"  # CSRF protection - Use Strict unless OAuth flows break easily
    PERMANENT_SESSION_LIFETIME = 2592000  # 30 days in seconds
    
    # Security Headers
    SECURITY_HEADERS = True
    SECURITY_HEADERS_ENABLED = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
    ENFORCE_HTTPS = os.environ.get("ENFORCE_HTTPS", "false").lower() == "true"
    
    # ========================================
    # DATABASE CONFIGURATION
    # ========================================
    
    # Use PostgreSQL on Render (DATABASE_URL), fallback to SQLite locally
    if os.environ.get("DATABASE_URL"):
        # Render PostgreSQL with connection pooling (psycopg v3 driver)
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get("DATABASE_URL"))
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 10,
            "pool_recycle": 280,  # Avoid connection drops on aggressive cloud hosts
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

    # LLM Recommendations
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or ""
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"

    # Embedded player provider (must be a licensed source you control/access)
    EMBED_PROVIDER_BASE_URL = (os.environ.get("EMBED_PROVIDER_BASE_URL") or "https://www.vidking.net").strip()
    _embed_enabled_raw = os.environ.get("EMBED_PROVIDER_ENABLED")
    EMBED_PROVIDER_ENABLED = (
        EMBED_PROVIDER_BASE_URL != ""
        if _embed_enabled_raw is None
        else _embed_enabled_raw.lower() == "true"
    )
    EMBED_PROVIDER_ALLOWED_ORIGIN = os.environ.get("EMBED_PROVIDER_ALLOWED_ORIGIN") or "https://www.vidking.net"
    EMBED_PROVIDER_ALLOWED_ORIGINS = [
        origin.strip() for origin in (os.environ.get("EMBED_PROVIDER_ALLOWED_ORIGINS") or EMBED_PROVIDER_ALLOWED_ORIGIN).split(",")
        if origin.strip()
    ]
    EMBED_PROVIDER_COLOR = os.environ.get("EMBED_PROVIDER_COLOR") or "a855f7"
    EMBED_PROVIDER_AUTOPLAY = os.environ.get("EMBED_PROVIDER_AUTOPLAY", "false").lower() == "true"
    DEV_ALLOW_ANY_HTTPS_EMBED = os.environ.get("DEV_ALLOW_ANY_HTTPS_EMBED", "false").lower() == "true"
    
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