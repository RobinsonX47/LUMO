from flask import Flask, render_template
from config import Config
from extensions import db, login_manager
from tmdb_service import TMDBService
from flask_login import current_user
import os
import threading
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

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Register blueprints
    from routes_main import main_bp
    from routes_auth import auth_bp
    from routes_movies import movies_bp
    from routes_users import users_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(movies_bp, url_prefix="/movies")
    app.register_blueprint(users_bp, url_prefix="/users")

    # Admin optional
    try:
        from routes_admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix="/admin")
    except Exception as e:
        print("⚠️ Admin blueprint not loaded:", e)

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
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('errors/400.html'), 400

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
