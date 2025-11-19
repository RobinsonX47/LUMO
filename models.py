from datetime import datetime
from flask_login import UserMixin
from extensions import db, login_manager

class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    release_year = db.Column(db.Integer)
    duration_minutes = db.Column(db.Integer)
    trailer_url = db.Column(db.String(255))
    poster_path = db.Column(db.String(255))
    tmdb_id = db.Column(db.Integer, unique=True, index=True)
    horizontal_poster_path = db.Column(db.String(255))
    avg_rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship("Review", backref="movie", lazy=True, cascade="all, delete-orphan")
    genres = db.relationship("MovieGenreMap", backref="movie", lazy=True, cascade="all, delete-orphan")
    watchlist_entries = db.relationship("Watchlist", backref="movie", lazy=True, cascade="all, delete-orphan")
    views = db.relationship("ViewLog", backref="movie", lazy=True, cascade="all, delete-orphan")


class Genre(db.Model):
    __tablename__ = "genres"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class MovieGenreMap(db.Model):
    __tablename__ = "movie_genre_map"

    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), primary_key=True)
    genre_id = db.Column(db.Integer, db.ForeignKey("genres.id"), primary_key=True)


class ViewLog(db.Model):
    __tablename__ = "views_log"

    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(255))
    role = db.Column(db.String(10), default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship("Review", backref="user", lazy=True, cascade="all, delete-orphan")
    watchlist = db.relationship("Watchlist", backref="user", lazy=True, cascade="all, delete-orphan")


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add unique constraint so user can only review a movie once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'movie_id', name='unique_user_movie_review'),
    )


class Watchlist(db.Model):
    __tablename__ = "watchlist"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), primary_key=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))