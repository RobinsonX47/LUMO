from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from extensions import db
from models import Review, Watchlist
from tmdb_service import TMDBService
from sqlalchemy import func
import requests
import json


def build_ai_style_recommendations(base_item, media_type):
    """Lightweight recommendations using TMDB similar data only - no extra API calls."""
    if not base_item:
        return []
    
    try:
        # Use TMDB's similar results directly - they're already good
        similar_block = base_item.get('similar', {})
        if not similar_block or not isinstance(similar_block, dict):
            return []
        
        candidates = similar_block.get('results', []) or []
        if not candidates:
            return []
        
        # Get base data for scoring (already in base_item)
        base_year = None
        release_field = base_item.get('release_date') or base_item.get('first_air_date')
        if release_field and len(release_field) >= 4:
            try:
                base_year = int(release_field[:4])
            except ValueError:
                pass
        
        base_genre_ids = set(g.get('id') for g in base_item.get('genres', []) if g.get('id'))
        
        # Score candidates using only data already available
        scored = []
        for cand in candidates[:12]:  # Only process first 12 similar items
            if not cand.get('id') or cand.get('id') == base_item.get('id'):
                continue
            
            # Calculate year proximity
            cand_year = None
            rel_field = cand.get('release_date') or cand.get('first_air_date')
            if rel_field and len(rel_field) >= 4:
                try:
                    cand_year = int(rel_field[:4])
                except ValueError:
                    pass
            
            era_score = 0
            if base_year and cand_year:
                diff = abs(base_year - cand_year)
                era_score = max(0, 10 - diff) / 10
            
            # Genre overlap (using genre_ids from candidate if available)
            cand_genre_ids = set(cand.get('genre_ids', []))
            genre_overlap = len(base_genre_ids & cand_genre_ids) if cand_genre_ids else 0
            
            vote = cand.get('vote_average', 0)
            
            # Simple scoring: genre match + era + rating
            score = genre_overlap * 3 + era_score * 2 + (vote / 10)
            
            # Set media type
            cand['media_type'] = cand.get('media_type') or (
                'tv' if (cand.get('name') and not cand.get('title')) else 'movie'
            )
            
            scored.append({'data': cand, 'score': score})
        
        # Sort and return top 6
        scored.sort(key=lambda x: x['score'], reverse=True)
        return [s['data'] for s in scored[:6]]
    
    except Exception as e:
        print(f"Error in recommendations: {e}")
        # Fallback: return first 6 similar items
        similar_block = base_item.get('similar', {})
        if isinstance(similar_block, dict):
            results = similar_block.get('results', [])[:6]
            for r in results:
                r['media_type'] = r.get('media_type') or (
                    'tv' if (r.get('name') and not r.get('title')) else 'movie'
                )
            return results
        return []

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
    try:
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
        
        # Build recommendations (lightweight, no extra API calls)
        smart_recs = build_ai_style_recommendations(movie, media_type="movie")

        return render_template(
            "movies/detail.html",
            movie=movie,
            reviews=reviews,
            in_watchlist=in_watchlist,
            user_review=user_review,
            media_type="movie",
            smart_recs=smart_recs
        )
    except Exception as e:
        print(f"Error loading movie {movie_id}: {e}")
        flash("Error loading movie details", "error")
        return redirect(url_for("movies.movie_list"))

@movies_bp.route("/tv/<int:tv_id>")
def tv_detail(tv_id):
    try:
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
        
        # Build recommendations (lightweight, no extra API calls)
        smart_recs = build_ai_style_recommendations(show, media_type="tv")

        return render_template(
            "movies/detail.html",
            movie=show,
            reviews=reviews,
            in_watchlist=in_watchlist,
            user_review=user_review,
            media_type="tv",
            smart_recs=smart_recs
        )
    except Exception as e:
        print(f"Error loading TV show {tv_id}: {e}")
        flash("Error loading TV show details", "error")
        return redirect(url_for("main.series_section"))

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

    payload = request.get_json(silent=True) or {}
    media_type = payload.get("media_type") or payload.get("type")

    # Fallback detection when media_type is missing
    if media_type not in ("movie", "tv"):
        media_type = "tv" if (request.referrer and "/tv/" in request.referrer) else "movie"

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
        fetch_details = TMDBService.get_tv_details if media_type == "tv" else TMDBService.get_movie_details
        movie = fetch_details(movie_id)
        
        if movie:
            new_entry = Watchlist(
                user_id=current_user.id,
                tmdb_movie_id=movie_id,
                movie_title=movie.get('title', movie.get('name', 'Unknown')),
                poster_path=movie.get('poster_path'),
                media_type=media_type
            )
            db.session.add(new_entry)
            db.session.commit()
            
            # JSON response (default now)
            return jsonify({'success': True, 'in_watchlist': True})
        
        return jsonify({'success': False, 'message': 'Could not fetch movie details'})


@movies_bp.route("/watchlist")
@login_required
def watchlist():
    entries = (
        Watchlist.query
        .filter_by(user_id=current_user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )

    def resolve_entry(entry):
        """Get movie/TV details using stored media_type for better performance."""
        try:
            # Use stored media_type if available (new entries have it)
            media_type = getattr(entry, 'media_type', 'movie')
            
            if media_type == 'tv':
                details = TMDBService.get_tv_details(entry.tmdb_movie_id)
            else:
                details = TMDBService.get_movie_details(entry.tmdb_movie_id)
            
            # If first attempt fails, try the other type (for old entries without media_type)
            if not details:
                if media_type == 'tv':
                    details = TMDBService.get_movie_details(entry.tmdb_movie_id)
                else:
                    details = TMDBService.get_tv_details(entry.tmdb_movie_id)
            
            return details
        except Exception as e:
            print(f"Error resolving watchlist entry {entry.tmdb_movie_id}: {e}")
            return None

    watchlist_items = []
    for entry in entries:
        item = resolve_entry(entry)
        if not item:
            continue

        # Ensure media_type is set
        if 'media_type' not in item:
            item['media_type'] = getattr(entry, 'media_type', 'movie')
        watchlist_items.append(item)

    return render_template(
        "movies/watchlist.html",
        watchlist=watchlist_items
    )


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
        # Get 24 initial recommendations
        recommended_items = get_personalized_recommendations(watchlist_titles, watchlist_genres, batch=0, items_per_batch=24)
    except Exception as e:
        print(f"Recommendation generation error: {e}")
        recommended_items = get_fallback_recommendations(watchlist_genres, limit=24)
    
    # Store seen IDs in session to prevent duplicates on load-more
    from flask import session
    session['seen_recommendation_ids'] = [item.get('id') for item in recommended_items]
    
    return render_template(
        "movies/recommendations.html",
        recommendations=recommended_items,
        watchlist_count=len(watchlist_entries)
    )


@movies_bp.route("/recommendations/load-more", methods=["POST"])
@login_required
def load_more_recommendations():
    import json
    from flask import session
    
    data = request.get_json()
    items_per_batch = 16
    
    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).limit(20).all()
    
    if not watchlist_entries:
        return json.dumps({"items": [], "error": "No watchlist"}), 400
    
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
    
    # Get previously seen IDs from session
    seen_ids = set(session.get('seen_recommendation_ids', []))
    
    try:
        # Request a large batch and filter out seen items
        recommended_items = get_personalized_recommendations_paginated(
            watchlist_titles, 
            watchlist_genres, 
            exclude_ids=seen_ids,
            limit=items_per_batch
        )
    except Exception as e:
        print(f"Load more recommendation error: {e}")
        recommended_items = get_fallback_recommendations(watchlist_genres, limit=items_per_batch, exclude_ids=seen_ids)
    
    # Update session with newly seen IDs
    new_ids = [item.get('id') for item in recommended_items]
    session['seen_recommendation_ids'] = list(seen_ids) + new_ids
    session.modified = True
    
    # Format items for JSON response
    items_data = []
    for item in recommended_items:
        items_data.append({
            'id': item.get('id'),
            'title': item.get('title'),
            'poster_url': item.get('poster_url'),
            'media_type': item.get('media_type', 'movie'),
            'release_date': item.get('release_date', ''),
            'vote_average': item.get('vote_average', 0)
        })
    
    return json.dumps({"items": items_data}), 200, {'Content-Type': 'application/json'}

def get_personalized_recommendations(watchlist_titles, watchlist_genres, batch=0, items_per_batch=24):
    if not watchlist_titles:
        return get_fallback_recommendations(watchlist_genres, limit=items_per_batch)
    
    try:
        titles_str = ", ".join(watchlist_titles[:15])
        genres_str = ", ".join(set(watchlist_genres[:15]))
        
        prompt = f"""Based on a user who enjoys these movies/shows: {titles_str}

Their favorite genres are: {genres_str}

Recommend {items_per_batch * 2} movies and TV shows that match their taste. Focus on:
1. Similar plots and themes
2. Same genres
3. Similar tone and style
4. Well-reviewed titles

Return ONLY valid JSON array:
[
  {{"title": "Movie/Show Name", "year": 2020}},
  ...
]"""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return get_fallback_recommendations(watchlist_genres, limit=items_per_batch)
        
        data = response.json()
        content = data['content'][0].get('text', '').strip()
        
        if '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        recommendations = json.loads(content)
        
        results = []
        seen_ids = set()
        for rec in recommendations:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 3)
            
            if movies:
                for movie in movies:
                    if movie['id'] not in seen_ids:
                        seen_ids.add(movie['id'])
                        results.append(movie)
                        if len(results) >= items_per_batch * 2:
                            break
            
            if len(results) >= items_per_batch * 2:
                break
        
        return results[:items_per_batch] if results else get_fallback_recommendations(watchlist_genres, limit=items_per_batch)
    
    except Exception as e:
        print(f"AI recommendation error: {e}")
        return get_fallback_recommendations(watchlist_genres, limit=items_per_batch)


def get_personalized_recommendations_paginated(watchlist_titles, watchlist_genres, exclude_ids=None, limit=16):
    """Get paginated recommendations excluding previously seen IDs"""
    if exclude_ids is None:
        exclude_ids = set()
    
    if not watchlist_titles:
        return get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)
    
    try:
        titles_str = ", ".join(watchlist_titles[:15])
        genres_str = ", ".join(set(watchlist_genres[:15]))
        
        prompt = f"""Based on a user who enjoys these movies/shows: {titles_str}

Their favorite genres are: {genres_str}

Recommend {limit * 3} DIFFERENT movies and TV shows (completely different from previous recommendations). Focus on:
1. Different themes but similar quality
2. Same genres but lesser-known titles
3. Similar tone but different stories
4. Well-reviewed hidden gems

Return ONLY valid JSON array:
[
  {{"title": "Movie/Show Name", "year": 2020}},
  ...
]"""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)
        
        data = response.json()
        content = data['content'][0].get('text', '').strip()
        
        if '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        recommendations = json.loads(content)
        
        results = []
        for rec in recommendations:
            if not rec.get('title'):
                continue
            
            title = rec['title']
            movies = TMDBService.search_all(title, 3)
            
            if movies:
                for movie in movies:
                    if movie['id'] not in exclude_ids:
                        results.append(movie)
                        if len(results) >= limit:
                            break
            
            if len(results) >= limit:
                break
        
        return results[:limit] if results else get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)
    
    except Exception as e:
        print(f"AI paginated recommendation error: {e}")
        return get_fallback_recommendations(watchlist_genres, limit=limit, exclude_ids=exclude_ids)


def get_fallback_recommendations(genres, limit=24, exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = set()
    
    try:
        all_genres = TMDBService.get_genres()
        
        if not genres or not all_genres:
            popular = TMDBService.get_popular_movies(1)[:limit*2]
            filtered = [m for m in popular if m['id'] not in exclude_ids]
            return filtered[:limit]
        
        genre_counts = {}
        for g in genres:
            genre_counts[g] = genre_counts.get(g, 0) + 1
        
        top_genre_names = [g[0] for g in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:4]]
        
        genre_ids = [g['id'] for g in all_genres if g['name'] in top_genre_names]
        
        results = []
        
        # Get movies from top genres with increased page sampling
        for gid in genre_ids[:4]:
            for page in range(1, 5):
                movies = TMDBService.get_movies_by_genre(gid, page)
                for movie in movies[:10]:
                    if movie['id'] not in exclude_ids:
                        results.append(movie)
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
        
        # If still not enough, add popular movies
        if len(results) < limit:
            popular = TMDBService.get_popular_movies(1)[:20]
            for movie in popular:
                if movie['id'] not in exclude_ids:
                    results.append(movie)
                    if len(results) >= limit:
                        break
        
        return results[:limit]
        
    except Exception as e:
        print(f"Fallback recommendation error: {e}")
        popular = TMDBService.get_popular_movies(1)[:limit*2]
        filtered = [m for m in popular if m['id'] not in exclude_ids]
        return filtered[:limit]
