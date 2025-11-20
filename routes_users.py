from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from extensions import db
from models import User, Review, Watchlist
from tmdb_service import TMDBService
import os
import uuid

users_bp = Blueprint("users", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@users_bp.route("/profile")
@login_required
def profile():
    user = current_user
    
    # Get user's reviews with movie details from TMDB
    reviews = Review.query.filter_by(user_id=user.id).order_by(Review.created_at.desc()).all()
    reviewed_movies = []
    for review in reviews:
        # Try movie first, then TV
        movie = TMDBService.get_movie_details(review.tmdb_movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(review.tmdb_movie_id)
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
        if not movie:
            movie = TMDBService.get_tv_details(entry.tmdb_movie_id)
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
            flash("Name is required", "error")
            return redirect(url_for("users.edit_profile"))
        
        current_user.name = name
        current_user.bio = bio
        
        # Handle avatar upload
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            if allowed_file(avatar_file.filename):
                # Create upload directory if it doesn't exist
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
                os.makedirs(upload_folder, exist_ok=True)
                
                # Generate unique filename
                filename = secure_filename(avatar_file.filename)
                unique_filename = f"avatar_{current_user.id}_{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                
                # Save file
                avatar_file.save(filepath)
                
                # Delete old avatar if exists
                if current_user.avatar and current_user.avatar.startswith('/static/uploads'):
                    old_path = os.path.join(current_app.root_path, current_user.avatar.lstrip('/'))
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass
                
                # Update user avatar path
                current_user.avatar = f"/static/uploads/avatars/{unique_filename}"
            else:
                flash("Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF, WEBP)", "error")
                return redirect(url_for("users.edit_profile"))
        
        # Update password if provided
        new_password = request.form.get("password", "").strip()
        if new_password:
            if len(new_password) < 6:
                flash("Password must be at least 6 characters", "error")
                return redirect(url_for("users.edit_profile"))
            current_user.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("users.profile"))
    
    return render_template("users/edit_profile.html", user=current_user)