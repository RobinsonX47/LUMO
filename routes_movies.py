from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from extensions import db
from models import Review, Watchlist
from tmdb_service import TMDBService
from sqlalchemy import func

movies_bp = Blueprint("movies", __name__)

@movies_bp.route("/")
def movie_list():
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    
    if query:
        movies = TMDBService.search_movies(query, page)
    else:
        movies = TMDBService.get_popular_movies(page)
    
    return render_template(
        "movies/list.html",
        movies=movies,
        query=query,
        page=page
    )

@movies_bp.route("/<int:movie_id>")
def movie_detail(movie_id):
    # Get movie details from TMDB
    movie = TMDBService.get_movie_details(movie_id)
    
    if not movie:
        flash("Movie not found")
        return redirect(url_for("movies.movie_list"))
    
    # Get reviews from local database
    reviews = Review.query.filter_by(tmdb_movie_id=movie_id).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating from local reviews
    local_avg = db.session.query(func.avg(Review.rating)).filter_by(tmdb_movie_id=movie_id).scalar()
    movie['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
    movie['local_review_count'] = len(reviews)
    
    # Check if in watchlist
    in_watchlist = False
    user_review = None
    if current_user.is_authenticated:
        in_watchlist = Watchlist.query.filter_by(
            user_id=current_user.id,
            tmdb_movie_id=movie_id
        ).first() is not None
        
        user_review = Review.query.filter_by(
            user_id=current_user.id,
            tmdb_movie_id=movie_id
        ).first()
    
    return render_template(
        "movies/detail.html",
        movie=movie,
        reviews=reviews,
        in_watchlist=in_watchlist,
        user_review=user_review
    )

@movies_bp.route("/<int:movie_id>/review", methods=["POST"])
@login_required
def add_review(movie_id):
    rating = int(request.form.get("rating"))
    text = request.form.get("review_text", "").strip()
    
    if not text:
        flash("Review text is required")
        return redirect(url_for("movies.movie_detail", movie_id=movie_id))
    
    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5")
        return redirect(url_for("movies.movie_detail", movie_id=movie_id))
    
    # Check if user already reviewed
    review = Review.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    if review:
        # Update existing review
        review.rating = rating
        review.review_text = text
        flash("Review updated successfully!")
    else:
        # Create new review
        review = Review(
            user_id=current_user.id,
            tmdb_movie_id=movie_id,
            rating=rating,
            review_text=text
        )
        db.session.add(review)
        flash("Review added successfully!")
    
    db.session.commit()
    return redirect(url_for("movies.movie_detail", movie_id=movie_id))

@movies_bp.route("/<int:movie_id>/review/delete", methods=["POST"])
@login_required
def delete_review(movie_id):
    review = Review.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    if review:
        db.session.delete(review)
        db.session.commit()
        flash("Review deleted successfully!")
    
    return redirect(url_for("movies.movie_detail", movie_id=movie_id))

@movies_bp.route("/<int:movie_id>/watchlist", methods=["POST"])
@login_required
def toggle_watchlist(movie_id):
    entry = Watchlist.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash("Removed from watchlist")
    else:
        # Get movie title from TMDB for storage
        movie = TMDBService.get_movie_details(movie_id)
        if movie:
            new_entry = Watchlist(
                user_id=current_user.id,
                tmdb_movie_id=movie_id,
                movie_title=movie.get('title', 'Unknown'),
                poster_path=movie.get('poster_path')
            )
            db.session.add(new_entry)
            db.session.commit()
            flash("Added to watchlist")
    
    return redirect(url_for("movies.movie_detail", movie_id=movie_id))