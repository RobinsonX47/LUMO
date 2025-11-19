from flask import Blueprint, render_template
from flask_login import login_required, current_user
from extensions import db
from models import User, Review, Watchlist, Movie

users_bp = Blueprint("users", __name__)

@users_bp.route("/profile")
@login_required
def profile():
    user: User = current_user

    # Watched = movies the user has reviewed
    watched = (
        db.session.query(Movie, Review)
        .join(Review, Review.movie_id == Movie.id)
        .filter(Review.user_id == user.id)
        .order_by(Review.created_at.desc())
        .all()
    )

    # Watchlist
    watchlist_entries = (
        db.session.query(Movie)
        .join(Watchlist, Watchlist.movie_id == Movie.id)
        .filter(Watchlist.user_id == user.id)
        .all()
    )

    return render_template(
        "users/profile.html",
        user=user,
        watched=watched,
        watchlist=watchlist_entries
    )
