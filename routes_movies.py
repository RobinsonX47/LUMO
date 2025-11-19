from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user, login_required
from app import db
from models import Movie, Review, ViewLog, Watchlist
from sqlalchemy import func

movies_bp = Blueprint("movies", __name__)

@movies_bp.route("/")
def movie_list():
    query = Movie.query
    q = request.args.get("q")
    if q:
        query = query.filter(Movie.title.ilike(f"%{q}%"))
    movies = query.order_by(Movie.created_at.desc()).all()
    return render_template("movies/list.html", movies=movies)


@movies_bp.route("/<int:movie_id>")
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)

    # log view
    view = ViewLog(
        movie_id=movie.id,
        user_id=current_user.id if current_user.is_authenticated else None
    )
    db.session.add(view)
    db.session.commit()

    reviews = Review.query.filter_by(movie_id=movie.id).order_by(Review.created_at.desc()).all()
    return render_template("movies/detail.html", movie=movie, reviews=reviews)


@movies_bp.route("/<int:movie_id>/review", methods=["POST"])
@login_required
def add_review(movie_id):
    rating = int(request.form["rating"])
    text = request.form["review_text"]

    # check if user already reviewed -> update
    review = Review.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    if review:
        review.rating = rating
        review.review_text = text
    else:
        review = Review(user_id=current_user.id, movie_id=movie_id,
                        rating=rating, review_text=text)
        db.session.add(review)

    # recompute average rating
    db.session.flush()  # ensure review is written for avg calculation
    avg = db.session.query(func.avg(Review.rating)).filter_by(movie_id=movie_id).scalar()
    movie = Movie.query.get(movie_id)
    movie.avg_rating = round(float(avg), 1) if avg is not None else 0.0

    db.session.commit()
    return redirect(url_for("movies.movie_detail", movie_id=movie_id))


@movies_bp.route("/<int:movie_id>/watchlist", methods=["POST"])
@login_required
def toggle_watchlist(movie_id):
    entry = Watchlist.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    if entry:
        db.session.delete(entry)
    else:
        db.session.add(Watchlist(user_id=current_user.id, movie_id=movie_id))
    db.session.commit()
    return redirect(url_for("movies.movie_detail", movie_id=movie_id))
