from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from extensions import db
from models import Movie
from werkzeug.utils import secure_filename
import os
import uuid

admin_bp = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required():
    if not current_user.is_authenticated or getattr(current_user, 'role', 'user') != 'admin':
        abort(403)


@admin_bp.route('/')
@login_required
def admin_index():
    admin_required()
    return redirect(url_for('admin.movies'))


@admin_bp.route('/movies')
@login_required
def movies():
    admin_required()
    movies = Movie.query.order_by(Movie.created_at.desc()).all()
    return render_template('admin/movies_list.html', movies=movies)


@admin_bp.route('/movies/add', methods=['GET', 'POST'])
@login_required
def add_movie():
    admin_required()

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        release_year = request.form.get('release_year') or None
        duration_minutes = request.form.get('duration_minutes') or None
        trailer_url = request.form.get('trailer_url') or None

        if not title:
            flash('Title is required', 'warning')
            return redirect(url_for('admin.add_movie'))

        movie = Movie(
            title=title,
            description=description,
            release_year=int(release_year) if release_year else None,
            duration_minutes=int(duration_minutes) if duration_minutes else None,
            trailer_url=trailer_url,
        )

        # Handle poster upload (square/vertical poster)
        file = request.files.get('poster')
        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique = f"movie_{uuid.uuid4().hex}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                dest = os.path.join(upload_folder, unique)
                file.save(dest)
                # store a static path so templates can use it directly
                movie.poster_path = f"/static/uploads/{unique}"
            else:
                flash('Invalid poster file type', 'warning')

        # Handle horizontal poster upload (wide poster for hero/carousel)
        file_h = request.files.get('poster_h')
        if file_h and file_h.filename:
            if allowed_file(file_h.filename):
                filename_h = secure_filename(file_h.filename)
                unique_h = f"movie_h_{uuid.uuid4().hex}_{filename_h}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                dest_h = os.path.join(upload_folder, unique_h)
                file_h.save(dest_h)
                movie.horizontal_poster_path = f"/static/uploads/{unique_h}"
            else:
                flash('Invalid horizontal poster file type', 'warning')

        db.session.add(movie)
        db.session.commit()
        flash('Movie added', 'success')
        return redirect(url_for('admin.movies'))

    return render_template('admin/add_movie.html')
