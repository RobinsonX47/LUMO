from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from extensions import db
from models import User, Review, Watchlist
from tmdb_service import TMDBService

users_bp = Blueprint("users", __name__)

@users_bp.route("/profile")
@login_required
def profile():
    user = current_user
    
    # Get user's reviews with movie details from TMDB
    reviews = Review.query.filter_by(user_id=user.id).order_by(Review.created_at.desc()).all()
    reviewed_movies = []
    for review in reviews:
        movie = TMDBService.get_movie_details(review.tmdb_movie_id)
        if movie:
            reviewed_movies.append({
                'movie': movie,
                'review': review
            })
    
    # Get user's watchlist with movie details from TMDB
    watchlist_entries = Watchlist.query.filter_by(user_id=user.id).order_by(Watchlist.added_at.desc()).all()
    watchlist_movies = []
    for entry in watchlist_entries:
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        if movie:
            watchlist_movies.append(movie)
    
    return render_template(
        "users/profile.html",
        user=user,
        reviewed_movies=reviewed_movies,
        watchlist=watchlist_movies
    )

@users_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        bio = request.form.get("bio", "").strip()
        
        if not name:
            flash("Name is required")
            return redirect(url_for("users.edit_profile"))
        
        current_user.name = name
        current_user.bio = bio
        
        # Update password if provided
        new_password = request.form.get("password", "").strip()
        if new_password:
            if len(new_password) < 6:
                flash("Password must be at least 6 characters")
                return redirect(url_for("users.edit_profile"))
            current_user.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        db.session.commit()
        flash("Profile updated successfully!")
        return redirect(url_for("users.profile"))
    
    return render_template("users/edit_profile.html", user=current_user)