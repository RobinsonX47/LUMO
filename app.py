from flask import Flask, render_template, jsonify
from config import Config
from extensions import db, login_manager, csrf, limiter
from tmdb_service import TMDBService
from flask_login import current_user
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFError
from flask_limiter.util import get_remote_address
import os
import threading
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
import humanize

# Load environment variables from .env file
load_dotenv()

def datetime_difference(dt):
    """Calculate time difference between now and given datetime using humanize."""
    if not dt:
        return 'Just now'
    
    # Use humanize for better natural time formatting
    now = datetime.utcnow()
    return humanize.naturaltime(now - dt)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
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

    # Ensure instance folder exists (important on Render)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

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
        # Create logs directory
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # File handler for errors
        file_handler = RotatingFileHandler(
            'logs/lumo.log', 
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

    # Bootstrap schema for fresh deployments (idempotent: only creates missing tables).
    # This prevents runtime failures (e.g., OAuth callback) when a new managed DB is attached.
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database schema ensured")
        except Exception as exc:
            app.logger.error("Failed to initialize database schema: %s", exc)
            raise

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    # Register blueprints
    from routes_main import main_bp
    from routes_auth import auth_bp
    from routes_movies import movies_bp
    from routes_users import users_bp
    from routes_legal import legal_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(movies_bp, url_prefix="/movies")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(legal_bp, url_prefix="/legal")

    # Admin optional
    try:
        from routes_admin import admin_bp
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

    # Context processor for notifications
    @app.context_processor
    def get_unread_notifications_count():
        if current_user.is_authenticated:
            from models import Notification
            try:
                count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
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
        return render_template('errors/429.html', 
                             retry_after=error.description), 429
    
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        """Handle CSRF token errors"""
        app.logger.warning(f'CSRF error: {str(error)}')
        return render_template('errors/400.html', 
                             error_message="Security token expired. Please refresh and try again."), 400

    # Removed background cache warming from app startup to prevent background thread
    # duplication in multi-worker WSGI environments. Cache should be warmed via a 
    # separate background job (e.g. Celery, clock process) if desired.

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
