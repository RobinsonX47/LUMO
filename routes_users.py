from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Review, Watchlist, Movie
from werkzeug.utils import secure_filename
import os

# Allowed image extensions for avatar uploads
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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


@users_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user: User = current_user

    if request.method == "POST":
        # Update bio
        bio = request.form.get("bio")
        if bio is not None:
            user.bio = bio

        # Handle avatar upload
        file = request.files.get("avatar")
        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # prefix filename to avoid collisions
                filename = f"user_{user.id}_{filename}"
                upload_folder = os.path.join(current_app.root_path, "static", "uploads")
                os.makedirs(upload_folder, exist_ok=True)
                dest = os.path.join(upload_folder, filename)
                file.save(dest)
                user.avatar = filename
            else:
                flash("Invalid file type for avatar. Allowed: png, jpg, jpeg, gif.", "warning")

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("users.profile"))

    return render_template("users/edit_profile.html", user=user)
