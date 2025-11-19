from flask import Blueprint, render_template
from extensions import db
from models import Movie, ViewLog
from sqlalchemy import func
from datetime import datetime, timedelta

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    top_rated = Movie.query.order_by(Movie.avg_rating.desc()).limit(6).all()

    week_ago = datetime.utcnow() - timedelta(days=7)
    trending_query = (
        db.session.query(Movie, func.count(ViewLog.id).label("views"))
        .join(ViewLog)
        .filter(ViewLog.viewed_at >= week_ago)
        .group_by(Movie.id)
        .order_by(func.count(ViewLog.id).desc())
        .limit(6)
        .all()
    )

    trending_movies = [t[0] for t in trending_query] if trending_query else []

    return render_template("index.html", top_rated=top_rated, trending=trending_movies)