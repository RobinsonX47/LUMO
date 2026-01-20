from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from extensions import db
from models import Review, Watchlist
from tmdb_service import TMDBService
from sqlalchemy import func
import requests
import json


def build_ai_style_recommendations(base_item, media_type):
    """Curate 6 strong recs using era, genres, cast overlap, and TMDB similar."""
    if not base_item:
        return []

    base_year = None
    release_field = base_item.get('release_date') or base_item.get('first_air_date')
    if release_field and len(release_field) >= 4:
        try:
            base_year = int(release_field[:4])
        except ValueError:
            base_year = None

    base_genre_ids = [g.get('id') for g in base_item.get('genres', []) if g.get('id')]
    base_cast = []
    if base_item.get('credits') and isinstance(base_item['credits'], dict):
        base_cast = [c.get('name') for c in base_item['credits'].get('cast', [])[:6] if c.get('name')]

    candidates = []
    similar_block = base_item.get('similar', {})
    if isinstance(similar_block, dict):
        candidates.extend(similar_block.get('results', []) or [])

    # Add top genre picks to widen pool
    for gid in base_genre_ids[:2]:
        genre_movies = TMDBService.get_movies_by_genre(gid, 1) or []
        candidates.extend(genre_movies[:10])

    seen_ids = set()
    scored = []

    for cand in candidates:
        cid = cand.get('id')
        if not cid or cid == base_item.get('id'):
            continue
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        ctype = cand.get('media_type') or ('tv' if (cand.get('name') and not cand.get('title')) else 'movie')

        cand_detail = cand
        needs_detail = not cand.get('genres') or not cand.get('credits') or not cand.get('release_date') and not cand.get('first_air_date')
        if needs_detail:
            detail = TMDBService.get_tv_details(cid) if ctype == 'tv' else TMDBService.get_movie_details(cid)
            if detail:
                cand_detail = {**cand, **detail}

        cand_genres = [g.get('id') for g in cand_detail.get('genres', []) if g.get('id')]
        genre_overlap = len(set(base_genre_ids) & set(cand_genres))

        cand_year = None
        rel_field = cand_detail.get('release_date') or cand_detail.get('first_air_date')
        if rel_field and len(rel_field) >= 4:
            try:
                cand_year = int(rel_field[:4])
            except ValueError:
                cand_year = None

        era_score = 0
        if base_year and cand_year:
            diff = abs(base_year - cand_year)
            era_score = max(0, 10 - diff) / 10  # closer years score higher

        cand_cast = []
        if cand_detail.get('credits') and isinstance(cand_detail['credits'], dict):
            cand_cast = [c.get('name') for c in cand_detail['credits'].get('cast', [])[:6] if c.get('name')]
        cast_overlap = len(set(base_cast) & set(cand_cast))

        vote = cand_detail.get('vote_average') or cand.get('vote_average') or 0
        score = genre_overlap * 2 + cast_overlap * 3 + era_score + (vote / 10)

        cand_detail['media_type'] = ctype
        scored.append({'data': cand_detail, 'score': score})

    scored.sort(key=lambda x: x['score'], reverse=True)
    top = [s['data'] for s in scored[:6]]
    return top

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
                poster_path=movie.get('poster_path')
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
        """Fetch the correct TMDB payload, disambiguating movie vs TV by stored title."""
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        tv = TMDBService.get_tv_details(entry.tmdb_movie_id)

        # Prefer exact title/name match with cached title if available
        target_title = (entry.movie_title or "").strip().casefold()
        candidates = [c for c in [movie, tv] if c]
        if target_title and candidates:
            for c in candidates:
                candidate_title = (c.get("title") or c.get("name") or "").strip().casefold()
                if candidate_title == target_title:
                    return c

        # Fallback: prefer movie over tv if only one exists
        return movie or tv

    watchlist_items = []
    for entry in entries:
        item = resolve_entry(entry)
        if not item:
            continue

        item["media_type"] = item.get("media_type") or (
            "tv" if (item.get("name") and not item.get("title")) else "movie"
        )
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
