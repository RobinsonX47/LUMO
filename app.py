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

# Load environment variables from .env file
load_dotenv()

# === ONE-TIME DATABASE INITIALIZATION FLAG ===
_first_request_done = False


def datetime_difference(dt):
    """Calculate time difference between now and given datetime."""
    if not dt:
        return 'Just now'
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return 'Just now'
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f'{minutes}m ago'
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f'{hours}h ago'
    elif seconds < 2592000:  # 30 days
        days = int(seconds // 86400)
        return f'{days}d ago'
    else:
        months = int(seconds // 2592000)
        return f'{months}mo ago'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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
    # Only enforce HTTPS in production
    if os.environ.get("FLASK_ENV") == "production":
        Talisman(app, 
            force_https=True,
            strict_transport_security=True,
            content_security_policy={
                'default-src': ["'self'"],
                'script-src': ["'self'", "'unsafe-inline'", "https://www.google.com", "https://www.gstatic.com"],
                'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
                'img-src': ["'self'", "data:", "https:", "http:"],
                'font-src': ["'self'", "https://fonts.gstatic.com"],
                'connect-src': ["'self'", "https://api.themoviedb.org"],
            },
            content_security_policy_nonce_in=['script-src']
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
            count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            return {'unread_notifications_count': count}
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

    # Background cache warming (non-blocking)
    def warm_cache_async():
        with app.app_context():
            TMDBService.warm_cache()

    warming_thread = threading.Timer(2.0, warm_cache_async)
    warming_thread.daemon = True
    warming_thread.start()

    return app


# === APP INSTANCE CREATED HERE FOR GUNICORN ===
app = create_app()


# === FLASK 3 COMPATIBLE FIRST-RUN DATABASE INIT ===
@app.before_request
def initialize_database_once():
    global _first_request_done
    if not _first_request_done:
        with app.app_context():
            db.create_all()
        _first_request_done = True


# === LOCAL DEVELOPMENT ENTRY ===
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🎬 LUMO Movie Platform Starting...")
    print("=" * 60)
    print(f"✅ Database: {Config.SQLALCHEMY_DATABASE_URI}")
    print(f"✅ TMDB API: {'Configured' if Config.TMDB_API_KEY != 'YOUR_TMDB_API_KEY_HERE' else '⚠️ NOT CONFIGURED'}")
    print(f"🔥 Cache warming will start in 2 seconds...")
    print(f"🌐 Running on: http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
