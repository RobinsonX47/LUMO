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
    movie = TMDBService.get_movie_details(movie_id)
    
    if not movie:
        flash("Movie not found", "error")
        return redirect(url_for("movies.movie_list"))
    
    reviews = Review.query.filter_by(tmdb_movie_id=movie_id).order_by(Review.created_at.desc()).all()
    
    local_avg = db.session.query(func.avg(Review.rating)).filter_by(tmdb_movie_id=movie_id).scalar()
    movie['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
    movie['local_review_count'] = len(reviews)
    
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
    show = TMDBService.get_tv_details(tv_id)
    
    if not show:
        flash("TV show not found", "error")
        return redirect(url_for("main.series_section"))
    
    reviews = Review.query.filter_by(tmdb_movie_id=tv_id).order_by(Review.created_at.desc()).all()
    
    local_avg = db.session.query(func.avg(Review.rating)).filter_by(tmdb_movie_id=tv_id).scalar()
    show['local_avg_rating'] = round(float(local_avg), 1) if local_avg else None
    show['local_review_count'] = len(reviews)
    
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


# =====================================================================
# ✅ UPDATED WATCHLIST FUNCTION (Your newer version merged here)
# =====================================================================
@movies_bp.route("/<int:movie_id>/watchlist", methods=["POST"])
@login_required
def toggle_watchlist(movie_id):
    from flask import jsonify
    
    # Detect movie vs TV by checking referer
    is_tv = '/tv/' in request.referrer if request.referrer else False
    
    entry = Watchlist.query.filter_by(
        user_id=current_user.id,
        tmdb_movie_id=movie_id
    ).first()
    
    # REMOVE FROM WATCHLIST
    if entry:
        db.session.delete(entry)
        db.session.commit()
        
        # JSON response (default now)
        return jsonify({'success': True, 'in_watchlist': False})
    
    else:
        # Fetch title from TMDB
        if is_tv:
            movie = TMDBService.get_tv_details(movie_id)
        else:
            movie = TMDBService.get_movie_details(movie_id)
        
        if movie:
            new_entry = Watchlist(
                user_id=current_user.id,
                tmdb_movie_id=movie_id,
                movie_title=movie.get('title', movie.get('name', 'Unknown')),
                poster_path=movie.get('poster_path')
            )
            db.session.add(new_entry)
            db.session.commit()
            
            # JSON response (default now)
            return jsonify({'success': True, 'in_watchlist': True})
        
        return jsonify({'success': False, 'message': 'Could not fetch movie details'})


@movies_bp.route("/recommendations")
@login_required
def recommendations():
    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).limit(20).all()
    
    if not watchlist_entries:
        flash("Add some movies to your watchlist first to get personalized recommendations!", "info")
        return redirect(url_for("users.profile"))
    
    watchlist_titles = []
    watchlist_genres = []
    
    for entry in watchlist_entries[:15]:
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(entry.tmdb_movie_id)
        if movie:
            watchlist_titles.append(movie.get('title', 'Unknown'))
            if 'genres' in movie and movie['genres']:
                watchlist_genres.extend([g['name'] for g in movie['genres']])
    
    try:
        recommended_items = get_personalized_recommendations(watchlist_titles, watchlist_genres)
    except Exception as e:
        print(f"Recommendation generation error: {e}")
        recommended_items = get_fallback_recommendations(watchlist_genres)
    
    return render_template(
        "movies/recommendations.html",
        recommendations=recommended_items,
        watchlist_count=len(watchlist_entries)
    )

def get_personalized_recommendations(watchlist_titles, watchlist_genres):
    if not watchlist_titles:
        return get_fallback_recommendations(watchlist_genres)
    
    try:
        titles_str = ", ".join(watchlist_titles[:10])
        genres_str = ", ".join(set(watchlist_genres[:10]))
        
        prompt = f"""Based on a user who enjoys these movies: {titles_str}

Their favorite genres appear to be: {genres_str}

Recommend 10 movies or TV shows they would enjoy.

Return ONLY JSON:
[
  {{"title": "Movie Name", "year": 2020}}
]"""

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
            return get_fallback_recommendations(watchlist_genres)
        
        data = response.json()
        content = data['content'][0].get('text', '').strip()
        
        if '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        recommendations = json.loads(content)
        
        results = []
        for rec in recommendations[:12]:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 1)
            
            if movies:
                best_match = movies[0]
                results.append(best_match)
                
                if len(results) >= 10:
                    break
        
        return results if results else get_fallback_recommendations(watchlist_genres)
    
    except:
        return get_fallback_recommendations(watchlist_genres)


def get_fallback_recommendations(genres):
    try:
        all_genres = TMDBService.get_genres()
        
        if not genres or not all_genres:
            return TMDBService.get_popular_movies(1)[:10]
        
        genre_counts = {}
        for g in genres:
            genre_counts[g] = genre_counts.get(g, 0) + 1
        
        top_genre_names = [g[0] for g in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:2]]
        
        genre_ids = [g['id'] for g in all_genres if g['name'] in top_genre_names]
        
        results = []
        for gid in genre_ids[:2]:
            results.extend(TMDBService.get_movies_by_genre(gid, 1)[:5])
        
        unique = []
        seen = set()
        for movie in results:
            if movie['id'] not in seen:
                seen.add(movie['id'])
                unique.append(movie)
        
        return unique[:10]
        
    except:
        return TMDBService.get_popular_movies(1)[:10]
