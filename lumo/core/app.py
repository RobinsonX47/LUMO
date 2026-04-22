from flask import Flask, render_template, jsonify, g
from .extensions import db, login_manager, csrf, limiter
from ..services.tmdb_service import TMDBService
from flask_login import current_user
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFError
from flask_limiter.util import get_remote_address
import os
import sys
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
import humanize
from pathlib import Path

def _load_environment_variables() -> None:
    """Load .env from deterministic locations for source and frozen desktop builds."""
    env_candidates = []

    runtime_root = os.environ.get("LUMO_RUNTIME_ROOT")
    if runtime_root:
        env_candidates.append(Path(runtime_root) / ".env")

    if getattr(sys, "frozen", False):
        env_candidates.append(Path(sys.executable).resolve().parent / ".env")

    # Local development fallback.
    env_candidates.append(Path(__file__).resolve().parent / ".env")

    loaded_any = False
    seen = set()
    for candidate in env_candidates:
        candidate_str = str(candidate)
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=False)
            loaded_any = True

    if not loaded_any:
        # Keep default behavior as a last resort.
        load_dotenv(override=False)


# Load environment variables before configuration is imported.
_load_environment_variables()

from .config import Config

def datetime_difference(dt):
    """Calculate time difference between now and given datetime using humanize."""
    if not dt:
        return 'Just now'
    
    # Use humanize for better natural time formatting
    now = datetime.utcnow()
    return humanize.naturaltime(now - dt)


def truncate_words(value, max_words=6):
    """Truncate text by word count and append ellipsis for long titles."""
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    words = text.split()
    if len(words) <= max_words:
        return text

    return " ".join(words[:max_words]) + "..."


def _ensure_avatar_column_capacity(app):
    """Ensure Postgres users.avatar can store DB-backed image payloads."""
    if db.engine.dialect.name != "postgresql":
        return

    try:
        result = db.session.execute(
            db.text(
                """
                SELECT data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                  AND column_name = 'avatar'
                """
            )
        ).mappings().first()

        if not result:
            return

        data_type = (result.get("data_type") or "").lower()
        max_length = result.get("character_maximum_length")
        if data_type in {"character varying", "varchar"} and (max_length or 0) <= 255:
            db.session.execute(db.text("ALTER TABLE users ALTER COLUMN avatar TYPE TEXT"))
            db.session.commit()
            app.logger.info("Expanded users.avatar column to TEXT")
    except Exception as exc:
        db.session.rollback()
        app.logger.warning("Could not auto-upgrade users.avatar column: %s", exc)


def _startup_tmdb_warmup(app):
    """Run TMDB warmup at startup with lock/cooldown to avoid duplicate work."""
    if not app.config.get("TMDB_WARMUP_ON_STARTUP", True):
        app.logger.info("TMDB startup warmup disabled")
        return

    if not app.config.get("TMDB_API_KEY") or app.config.get("TMDB_API_KEY") == "YOUR_TMDB_API_KEY_HERE":
        app.logger.info("TMDB startup warmup skipped: TMDB API key not configured")
        return

    # Skip Flask reloader parent process to avoid duplicate startup work in debug mode.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    instance_base_dir = os.environ.get("LUMO_DESKTOP_DATA_DIR") or str(Path(__file__).resolve().parents[2])
    instance_dir = Path(instance_base_dir) / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)

    lock_file = instance_dir / "tmdb_warmup.lock"
    state_file = instance_dir / "tmdb_warmup.last"
    now_ts = time.time()
    cooldown = int(app.config.get("TMDB_WARMUP_COOLDOWN_SECONDS", 900) or 900)

    if state_file.exists():
        try:
            last_ts = float(state_file.read_text(encoding="utf-8").strip() or "0")
            if now_ts - last_ts < cooldown:
                app.logger.info("TMDB startup warmup skipped: cooldown active")
                return
        except Exception:
            pass

    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(now_ts))
    except FileExistsError:
        app.logger.info("TMDB startup warmup skipped: another process is warming cache")
        return

    def run_warmup():
        try:
            with app.app_context():
                TMDBService.warm_cache(
                    profile=app.config.get("TMDB_WARMUP_PROFILE", "quick"),
                    genre_count=app.config.get("TMDB_WARMUP_GENRE_COUNT", 3),
                )
                state_file.write_text(str(time.time()), encoding="utf-8")
        except Exception as exc:
            app.logger.warning("TMDB startup warmup failed: %s", exc)
        finally:
            try:
                if lock_file.exists():
                    lock_file.unlink()
            except Exception:
                pass

    if app.config.get("TMDB_WARMUP_BLOCKING", False):
        run_warmup()
    else:
        threading.Thread(target=run_warmup, daemon=True, name="tmdb-startup-warmup").start()
        app.logger.info(
            "TMDB startup warmup scheduled (profile=%s)",
            app.config.get("TMDB_WARMUP_PROFILE", "quick"),
        )

def create_app():
    runtime_root = os.environ.get("LUMO_RUNTIME_ROOT")
    project_root = Path(__file__).resolve().parents[2]
    flask_kwargs = {}

    candidate_roots = []
    if runtime_root:
        candidate_roots.append(Path(runtime_root))
    candidate_roots.append(project_root)

    for candidate_root in candidate_roots:
        candidate_templates = candidate_root / "templates"
        if candidate_templates.is_dir():
            flask_kwargs["template_folder"] = str(candidate_templates)
            break

    for candidate_root in candidate_roots:
        candidate_static = candidate_root / "static"
        if candidate_static.is_dir():
            flask_kwargs["static_folder"] = str(candidate_static)
            break

    app = Flask(__name__, **flask_kwargs)
    app.config.from_object(Config)
    app.config["DESKTOP_MODE"] = os.environ.get("LUMO_DESKTOP_MODE") == "1"
    app.config["DESKTOP_PRIVATE_SESSION"] = os.environ.get("LUMO_DESKTOP_PRIVATE_SESSION", "0").lower() in {"1", "true", "yes", "on"}
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Fail fast on required secrets in production.
    is_production = os.environ.get("FLASK_ENV") == "production"
    if is_production:
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production")
        if not app.config.get("TMDB_API_KEY") or app.config["TMDB_API_KEY"] == "YOUR_TMDB_API_KEY_HERE":
            raise RuntimeError("TMDB_API_KEY must be configured in production")
        # Ensure Google OAuth keys are set if they're used. Could just check if they are the default "YOUR_..."
        if app.config.get("GOOGLE_CLIENT_ID") == "YOUR_GOOGLE_CLIENT_ID" or app.config.get("GOOGLE_CLIENT_SECRET") == "YOUR_GOOGLE_CLIENT_SECRET":
            app.logger.warning("Google OAuth credentials are not fully configured in production. OAuth may fail.")

    # Ensure instance folder exists and prefer desktop data directory when configured.
    instance_base_dir = os.environ.get("LUMO_DESKTOP_DATA_DIR") or app.root_path
    os.makedirs(os.path.join(instance_base_dir, "instance"), exist_ok=True)

    # ========================================
    # INITIALIZE SECURITY EXTENSIONS
    # ========================================
    
    # CSRF Protection
    csrf.init_app(app)
    
    # Rate Limiting with storage from config
    app.config['RATELIMIT_STORAGE_URL'] = Config.RATELIMIT_STORAGE_URL
    limiter.init_app(app)
    
    # Security Headers (Talisman)
    if app.config.get("SECURITY_HEADERS_ENABLED", True):
        csp = {
            'default-src': ["'self'"],
            'script-src': [
                "'self'",
                "'unsafe-inline'",
                "https://www.google.com",
                "https://www.gstatic.com",
                "https://www.youtube.com",
                "https://www.youtube-nocookie.com",
                "https://s.ytimg.com",
                "https://*.ytimg.com",
            ],
            'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            'img-src': ["'self'", "data:", "https:", "http:"],
            'font-src': ["'self'", "https://fonts.gstatic.com"],
            'connect-src': [
                "'self'",
                "https://api.themoviedb.org",
                "https://www.youtube.com",
                "https://www.youtube-nocookie.com",
                "https://*.googlevideo.com",
                "https://*.ytimg.com",
            ],
            'frame-src': ["'self'", "https://www.youtube.com", "https://www.youtube-nocookie.com"],
            'child-src': ["'self'", "https://www.youtube.com", "https://www.youtube-nocookie.com"],
            'media-src': ["'self'", "https://*.googlevideo.com", "https://*.youtube.com"],
            'object-src': ["'none'"],
        }

        provider_origins = app.config.get("EMBED_PROVIDER_ALLOWED_ORIGINS", [])
        if isinstance(provider_origins, str):
            provider_origins = [provider_origins]

        for origin in provider_origins:
            safe_origin = (origin or "").strip()
            if not safe_origin:
                continue
            csp['frame-src'].append(safe_origin)
            csp['child-src'].append(safe_origin)
            csp['connect-src'].append(safe_origin)

        if (not provider_origins) and (not is_production) and app.config.get("DEV_ALLOW_ANY_HTTPS_EMBED", False):
            # Optional local-dev override for rapid embed testing.
            csp['frame-src'].append("https:")
            csp['child-src'].append("https:")
            csp['connect-src'].append("https:")

        Talisman(app, 
            force_https=(is_production or app.config.get("ENFORCE_HTTPS", False)),
            strict_transport_security=is_production,
            content_security_policy=csp,
        )
    
    # ========================================
    # CONFIGURE LOGGING
    # ========================================
    
    if not app.debug:
        # Keep logs alongside desktop data when running packaged desktop app.
        logs_base_dir = os.environ.get("LUMO_DESKTOP_DATA_DIR") or os.getcwd()
        logs_dir = os.path.join(logs_base_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # File handler for errors
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'lumo.log'), 
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('LUMO startup')

    # Initialize database and login manager
    db.init_app(app)

    # Import models before create_all so SQLAlchemy metadata is populated.
    # Without this, fresh deployments can miss tables like `users`.
    import models  # noqa: F401

    # Bootstrap schema for fresh deployments (idempotent: only creates missing tables).
    # This prevents runtime failures (e.g., OAuth callback) when a new managed DB is attached.
    with app.app_context():
        try:
            db.create_all()
            _ensure_avatar_column_capacity(app)
            app.logger.info("Database schema ensured")
        except Exception as exc:
            app.logger.error("Failed to initialize database schema: %s", exc)
            raise

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    # Register blueprints
    from ..web.routes.main import main_bp
    from ..web.routes.auth import auth_bp
    from ..web.routes.movies import movies_bp
    from ..web.routes.users import users_bp
    from ..web.routes.legal import legal_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(movies_bp, url_prefix="/movies")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(legal_bp, url_prefix="/legal")

    # Admin optional
    try:
        from ..web.routes.admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix="/admin")
    except Exception as e:
        print("⚠️ Admin blueprint not loaded:", e)
    
    # ========================================
    # HEALTH CHECK & MONITORING ENDPOINTS
    # ========================================
    
    @app.route('/health')
    @limiter.exempt  # Don't rate limit health checks
    def health_check():
        """Health check endpoint for monitoring"""
        try:
            # Check database connection
            db.session.execute(db.text('SELECT 1'))
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        except Exception as e:
            app.logger.error(f'Health check failed: {str(e)}')
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 503
    
    @app.route('/ready')
    @limiter.exempt
    def readiness_check():
        """Readiness check for load balancers"""
        return jsonify({'status': 'ready'}), 200

    # Register Jinja2 filters
    app.jinja_env.filters['datetime_difference'] = datetime_difference
    app.jinja_env.filters['truncate_words'] = truncate_words

    # Context processor for notifications
    @app.context_processor
    def get_unread_notifications_count():
        if current_user.is_authenticated:
            from models import Notification
            try:
                cached_count = getattr(g, 'unread_notifications_count', None)
                if cached_count is not None:
                    return {'unread_notifications_count': cached_count}

                count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
                g.unread_notifications_count = count
                return {'unread_notifications_count': count}
            except Exception as exc:
                app.logger.warning('Notification count unavailable: %s', exc)
                return {'unread_notifications_count': 0}
        return {'unread_notifications_count': 0}

    # Error handlers for production
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Internal server error: {str(error)}')
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        """Handle rate limit exceeded"""
        app.logger.warning(f'Rate limit exceeded: {get_remote_address()}')
        retry_after = getattr(error, "retry_after", None)
        rate_limit_description = str(getattr(error, "description", "") or "")
        return render_template(
            'errors/429.html',
            retry_after=retry_after,
            rate_limit_description=rate_limit_description,
        ), 429
    
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        """Handle CSRF token errors"""
        app.logger.warning(f'CSRF error: {str(error)}')
        return render_template('errors/400.html', 
                             error_message="Security token expired. Please refresh and try again."), 400

    _startup_tmdb_warmup(app)

    return app


# === APP INSTANCE CREATED HERE FOR GUNICORN ===
app = create_app()


# === LOCAL DEVELOPMENT ENTRY ===
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LUMO Movie Platform Starting...")
    print("=" * 60)
    print(f"✅ Database: {Config.SQLALCHEMY_DATABASE_URI}")
    print(f"✅ TMDB API: {'Configured' if Config.TMDB_API_KEY != 'YOUR_TMDB_API_KEY_HERE' else '⚠️ NOT CONFIGURED'}")
    print(f"🌐 Running on: http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
