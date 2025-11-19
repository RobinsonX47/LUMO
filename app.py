from flask import Flask
from config import Config
from extensions import db, login_manager
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Create instance folder for SQLite DB
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
    from routes_admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(movies_bp, url_prefix="/movies")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Create database tables
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
