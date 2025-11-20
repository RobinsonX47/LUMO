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
    watchlist_genres = []
    
    for entry in watchlist_entries[:15]:  # Use top 15 for better context
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(entry.tmdb_movie_id)
        if movie:
            watchlist_titles.append(movie.get('title', 'Unknown'))
            if 'genres' in movie and movie['genres']:
                watchlist_genres.extend([g['name'] for g in movie['genres']])
    
    # Get AI recommendations with better error handling
    try:
        recommended_items = get_ai_recommendations(watchlist_titles, watchlist_genres)
    except Exception as e:
        print(f"AI Recommendation error: {e}")
        # Fallback to genre-based recommendations
        recommended_items = get_fallback_recommendations(watchlist_genres)
    
    return render_template(
        "movies/recommendations.html",
        recommendations=recommended_items,
        watchlist_count=len(watchlist_entries)
    )

def get_ai_recommendations(watchlist_titles, watchlist_genres):
    """Use Claude API to get personalized recommendations - OPTIMIZED"""
    
    if not watchlist_titles:
        return get_fallback_recommendations(watchlist_genres)
    
    try:
        # Create more specific prompt with genre context
        titles_str = ", ".join(watchlist_titles[:10])
        genres_str = ", ".join(set(watchlist_genres[:10]))
        
        prompt = f"""Based on a user who enjoys these movies: {titles_str}

Their favorite genres appear to be: {genres_str}

Recommend 10 movies or TV shows they would enjoy. Focus on:
- Similar themes and styles
- Mix of popular and hidden gems
- Variety across their favorite genres
- Recent releases (2015-2024)

Return ONLY a valid JSON array with NO other text, markdown, or formatting:
[
  {{"title": "Movie Name", "year": 2020}},
  {{"title": "Show Name", "year": 2021}}
]"""

        # Call Claude API
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
        
        if response.status_code != 200:
            print(f"API returned status {response.status_code}: {response.text}")
            return get_fallback_recommendations(watchlist_genres)
        
        data = response.json()
        
        if 'content' not in data or not data['content']:
            print("No content in API response")
            return get_fallback_recommendations(watchlist_genres)
        
        content = data['content'][0].get('text', '').strip()
        
        # Clean up the response
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        # Remove any leading/trailing whitespace
        content = content.strip()
        
        # Parse JSON
        try:
            recommendations = json.loads(content)
        except json.JSONDecodeError as je:
            print(f"JSON parse error: {je}")
            print(f"Content was: {content[:200]}")
            return get_fallback_recommendations(watchlist_genres)
        
        # Search TMDB for each recommendation
        results = []
        for rec in recommendations[:12]:  # Get a few extra in case some fail
            if not rec.get('title'):
                continue
                
            title = rec['title']
            
            # Search TMDB
            movies = TMDBService.search_all(title, 1)
            
            if movies:
                # Find best match based on title similarity and year
                best_match = None
                rec_year = rec.get('year')
                
                for movie in movies[:3]:
                    movie_title = movie.get('title', '').lower()
                    search_title = title.lower()
                    
                    # Check title match
                    if search_title in movie_title or movie_title in search_title:
                        # If year specified, prefer matching year
                        if rec_year:
                            movie_year = movie.get('release_date', '')[:4]
                            if movie_year == str(rec_year):
                                best_match = movie
                                break
                        
                        if not best_match:
                            best_match = movie
                
                if best_match and best_match not in results:
                    results.append(best_match)
                    
                if len(results) >= 10:
                    break
        
        # If we got good results, return them
        if len(results) >= 5:
            return results[:10]
        else:
            # Not enough results, supplement with fallback
            fallback = get_fallback_recommendations(watchlist_genres)
            combined = results + fallback
            # Remove duplicates
            seen = set()
            unique = []
            for item in combined:
                if item['id'] not in seen:
                    seen.add(item['id'])
                    unique.append(item)
            return unique[:10]
            
    except Exception as e:
        print(f"Error in get_ai_recommendations: {e}")
        import traceback
        traceback.print_exc()
        return get_fallback_recommendations(watchlist_genres)

def get_fallback_recommendations(genres):
    """Get genre-based recommendations as fallback"""
    try:
        # Get popular movies from favorite genres
        all_genres = TMDBService.get_genres()
        
        if not genres or not all_genres:
            # If no genre data, just return popular movies
            return TMDBService.get_popular_movies(1)[:10]
        
        # Find genre IDs
        genre_counts = {}
        for g in genres:
            genre_counts[g] = genre_counts.get(g, 0) + 1
        
        # Get top 2 genres
        top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        top_genre_names = [g[0] for g in top_genres]
        
        # Find matching genre IDs
        genre_ids = []
        for genre in all_genres:
            if genre['name'] in top_genre_names:
                genre_ids.append(genre['id'])
        
        # Get movies from these genres
        results = []
        for genre_id in genre_ids[:2]:
            movies = TMDBService.get_movies_by_genre(genre_id, 1)
            results.extend(movies[:5])
        
        # Remove duplicates and return
        seen = set()
        unique = []
        for movie in results:
            if movie['id'] not in seen:
                seen.add(movie['id'])
                unique.append(movie)
        
        return unique[:10]
        
    except Exception as e:
        print(f"Fallback error: {e}")
        # Last resort: return popular movies
        return TMDBService.get_popular_movies(1)[:10]