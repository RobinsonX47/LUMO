from flask import Flask
from config import Config
from extensions import db, login_manager
from tmdb_service import TMDBService
import os
import threading


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure instance folder exists
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

    # Optional admin
    try:
        from routes_admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix="/admin")
    except:
        pass

    # Create DB + Warm cache
    with app.app_context():
        db.create_all()

        def warm_cache_async():
            with app.app_context():
                TMDBService.warm_cache()

        thread = threading.Timer(2.0, warm_cache_async)
        thread.daemon = True
        thread.start()

    # ---- BEFORE FIRST REQUEST ----
    @app.before_first_request
    def setup_before_first_request():
        db.create_all()

    return app


# Make app visible to gunicorn (Render)
app = create_app()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🎬 LUMO Movie Platform Starting...")
    print("=" * 60)
    print(f"✅ Database: {Config.SQLALCHEMY_DATABASE_URI}")
    print(f"🔥 Cache warming will start in 2 seconds...")
    print(f"🌐 Running on: http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
