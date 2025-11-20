from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from extensions import db
from models import Review, Watchlist
from tmdb_service import TMDBService
from sqlalchemy import func
import requests
import json

movies_bp = Blueprint("movies", __name__)

@movies_bp.route("/")
def movie_list():
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    
    if query:
        movies = TMDBService.search_all(query, page)
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
        flash("Movie not found", "error")
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

@movies_bp.route("/tv/<int:tv_id>")
def tv_detail(tv_id):
    """TV show detail page"""
    show = TMDBService.get_tv_details(tv_id)
    
    if not show:
        flash("TV show not found", "error")
        return redirect(url_for("main.series_section"))
    
    # Get reviews from local database
    reviews = Review.query.filter_by(tmdb_movie_id=tv_id).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating
    local_avg = db.session.query(func.avg(Review.rating)).filter_by(tmdb_movie_id=tv_id).scalar()
    show['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
    show['local_review_count'] = len(reviews)
    
    # Check if in watchlist
    in_watchlist = False
    user_review = None
    if current_user.is_authenticated:
        in_watchlist = Watchlist.query.filter_by(
            user_id=current_user.id,
            tmdb_movie_id=tv_id
        ).first() is not None
        
        user_review = Review.query.filter_by(
            user_id=current_user.id,
            tmdb_movie_id=tv_id
        ).first()
    
    return render_template(
        "movies/detail.html",
        movie=show,
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
        flash("Review text is required", "error")
        return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))
    
    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5", "error")
        return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))
    
    # Check if user already reviewed
    review = Review.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    if review:
        review.rating = rating
        review.review_text = text
        flash("Review updated successfully!", "success")
    else:
        review = Review(
            user_id=current_user.id,
            tmdb_movie_id=movie_id,
            rating=rating,
            review_text=text
        )
        db.session.add(review)
        flash("Review added successfully!", "success")
    
    db.session.commit()
    return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))

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
        flash("Review deleted successfully!", "success")
    
    return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))

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
        flash("Removed from watchlist", "success")
    else:
        # Get movie/show title from TMDB for storage
        movie = TMDBService.get_movie_details(movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(movie_id)
        
        if movie:
            new_entry = Watchlist(
                user_id=current_user.id,
                tmdb_movie_id=movie_id,
                movie_title=movie.get('title', 'Unknown'),
                poster_path=movie.get('poster_path')
            )
            db.session.add(new_entry)
            db.session.commit()
            flash("Added to watchlist", "success")
    
    return redirect(request.referrer or url_for("movies.movie_detail", movie_id=movie_id))

@movies_bp.route("/recommendations")
@login_required
def recommendations():
    """AI-powered recommendations based on user's watchlist"""
    
    # Get user's watchlist
    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).limit(20).all()
    
    if not watchlist_entries:
        flash("Add some movies to your watchlist first to get personalized recommendations!", "info")
        return redirect(url_for("users.profile"))
    
    # Get details for watchlist items
    watchlist_titles = []
    for entry in watchlist_entries:
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(entry.tmdb_movie_id)
        if movie:
            watchlist_titles.append(movie.get('title', 'Unknown'))
    
    # Get AI recommendations
    recommended_items = get_ai_recommendations(watchlist_titles[:10])
    
    return render_template(
        "movies/recommendations.html",
        recommendations=recommended_items,
        watchlist_count=len(watchlist_entries)
    )

def get_ai_recommendations(watchlist_titles):
    """Use Claude API to get personalized recommendations"""
    
    if not watchlist_titles:
        return []
    
    try:
        # Prepare prompt for Claude
        watchlist_str = ", ".join(watchlist_titles)
        
        prompt = f"""Based on a user's watchlist containing: {watchlist_str}

Please recommend 10 movies, TV shows, or anime that this user would enjoy. Consider their taste and suggest diverse options.

Respond ONLY with a JSON array in this exact format:
[
  {{"title": "Movie Name", "year": 2020, "type": "movie"}},
  {{"title": "Show Name", "year": 2019, "type": "tv"}},
  ...
]

No other text, just the JSON array."""

        # Call Claude API (using the Anthropic API endpoint)
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get('content', [{}])[0].get('text', '')
            
            # Parse JSON from response
            try:
                # Clean up response - remove markdown code blocks if present
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()
                
                recommendations = json.loads(content)
                
                # Search for each recommendation on TMDB
                results = []
                for rec in recommendations[:10]:
                    title = rec.get('title')
                    if title:
                        # Search TMDB
                        movies = TMDBService.search_all(title, 1)
                        if movies:
                            # Find best match
                            for movie in movies[:3]:
                                movie_title = movie.get('title', '')
                                if title.lower() in movie_title.lower() or movie_title.lower() in title.lower():
                                    results.append(movie)
                                    break
                            else:
                                # If no exact match, add first result
                                if movies:
                                    results.append(movies[0])
                
                return results[:10]
            except json.JSONDecodeError:
                print(f"Failed to parse AI response: {content}")
                return []
        else:
            print(f"AI API error: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error getting AI recommendations: {e}")
        return []
    
    # Fallback: return popular movies if AI fails
    return TMDBService.get_popular_movies(1)[:10]