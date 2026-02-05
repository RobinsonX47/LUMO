from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from extensions import db
from models import User, Review, Watchlist, Notification, user_followers
from tmdb_service import TMDBService
from sqlalchemy import or_, and_, func
import os
import uuid
import re

users_bp = Blueprint("users", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_username(username):
    """Validate username format"""
    pattern = r'^[a-zA-Z0-9_-]{3,30}$'
    return re.match(pattern, username) is not None

# ============= OWN PROFILE =============

@users_bp.route("/profile")
@login_required
def profile():
    """Display current user's profile"""
    user = current_user
    
    # Get user's reviews with movie details from TMDB
    reviews = Review.query.filter_by(user_id=user.id).order_by(Review.created_at.desc()).limit(6).all()
    reviewed_movies = []
    for review in reviews:
        movie = TMDBService.get_movie_details(review.tmdb_movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(review.tmdb_movie_id)
        if movie:
            reviewed_movies.append({
                'movie': movie,
                'review': review
            })
    
    # Get user's watchlist with movie details from TMDB
    watchlist_entries = (
        Watchlist.query
        .filter_by(user_id=user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )

    def resolve_entry(entry):
        """Try movie first, then TV only if needed to reduce API calls."""
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        
        target_title = (entry.movie_title or "").strip().casefold()
        if movie and target_title:
            movie_title = (movie.get('title') or "").strip().casefold()
            if movie_title == target_title:
                return movie
        
        tv = TMDBService.get_tv_details(entry.tmdb_movie_id)
        if tv and target_title:
            tv_title = (tv.get('name') or "").strip().casefold()
            if tv_title == target_title:
                return tv
        
        return movie or tv

    watchlist_movies = []
    for entry in watchlist_entries:
        movie = resolve_entry(entry)
        if movie:
            movie['media_type'] = movie.get('media_type') or (
                'tv' if (movie.get('name') and not movie.get('title')) else 'movie'
            )
            watchlist_movies.append(movie)
    
    # Get followers and following counts
    followers_count = user.followers.count()
    following_count = user.following.count()
    
    # Get unread notifications count
    unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    
    return render_template(
        "users/profile.html",
        user=user,
        reviewed_movies=reviewed_movies,
        watchlist=watchlist_movies,
        followers_count=followers_count,
        following_count=following_count,
        is_own_profile=True,
        unread_notifications=unread_notifications
    )

@users_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Edit current user's profile including username"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        bio = request.form.get("bio", "").strip()
        
        if not name:
            flash("Name is required", "error")
            return redirect(url_for("users.edit_profile"))
        
        if len(name) < 2:
            flash("Name must be at least 2 characters", "error")
            return redirect(url_for("users.edit_profile"))
        
        # Check username if changed
        if username != current_user.username:
            if not is_valid_username(username):
                flash("Username must be 3-30 characters, using only letters, numbers, hyphens, and underscores.", "error")
                return redirect(url_for("users.edit_profile"))
            
            if User.query.filter_by(username=username).first():
                flash("Username already taken. Please choose another.", "error")
                return redirect(url_for("users.edit_profile"))
            
            current_user.username = username
        
        current_user.name = name
        current_user.bio = bio
        
        # Handle avatar upload
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            if allowed_file(avatar_file.filename):
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
                os.makedirs(upload_folder, exist_ok=True)
                
                filename = secure_filename(avatar_file.filename)
                unique_filename = f"avatar_{current_user.id}_{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(upload_folder, unique_filename)
                
                avatar_file.save(filepath)
                
                # Delete old avatar if exists
                if current_user.avatar and current_user.avatar.startswith('/static/uploads'):
                    old_path = os.path.join(current_app.root_path, current_user.avatar.lstrip('/'))
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass
                
                current_user.avatar = f"/static/uploads/avatars/{unique_filename}"
            else:
                flash("Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF, WEBP)", "error")
                return redirect(url_for("users.edit_profile"))
        
        # Update password if provided
        new_password = request.form.get("password", "").strip()
        if new_password:
            if len(new_password) < 6:
                flash("Password must be at least 6 characters", "error")
                return redirect(url_for("users.edit_profile"))
            current_user.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("users.profile"))
    
    return render_template("users/edit_profile.html", user=current_user)

# ============= PUBLIC PROFILES =============

@users_bp.route("/u/<username>")
def public_profile(username):
    """Display public profile of another user"""
    username = username.lower()
    user = User.query.filter_by(username=username).first_or_404()
    
    # Prevent viewing deleted or suspended accounts
    if user.role == "suspended":
        flash("This account is no longer available.", "error")
        return redirect(url_for("main.home"))
    
    # Get user's reviews (public)
    reviews = Review.query.filter_by(user_id=user.id).order_by(Review.created_at.desc()).limit(6).all()
    reviewed_movies = []
    for review in reviews:
        movie = TMDBService.get_movie_details(review.tmdb_movie_id)
        if not movie:
            movie = TMDBService.get_tv_details(review.tmdb_movie_id)
        if movie:
            reviewed_movies.append({
                'movie': movie,
                'review': review
            })
    
    # Get user's watchlist (public)
    watchlist_entries = Watchlist.query.filter_by(user_id=user.id).order_by(Watchlist.added_at.desc()).limit(8).all()

    def resolve_entry_public(entry):
        """Try movie first, then TV only if needed to reduce API calls."""
        movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
        
        target_title = (entry.movie_title or "").strip().casefold()
        if movie and target_title:
            movie_title = (movie.get('title') or "").strip().casefold()
            if movie_title == target_title:
                return movie
        
        tv = TMDBService.get_tv_details(entry.tmdb_movie_id)
        if tv and target_title:
            tv_title = (tv.get('name') or "").strip().casefold()
            if tv_title == target_title:
                return tv
        
        return movie or tv

    watchlist_movies = []
    for entry in watchlist_entries:
        movie = resolve_entry_public(entry)
        if movie:
            movie['media_type'] = movie.get('media_type') or (
                'tv' if (movie.get('name') and not movie.get('title')) else 'movie'
            )
            watchlist_movies.append(movie)
    
    # Get followers and following counts
    followers_count = user.followers.count()
    following_count = user.following.count()
    
    # Check if current user is following
    is_following = False
    if current_user.is_authenticated:
        is_following = current_user.following.filter_by(id=user.id).first() is not None
    
    is_own_profile = current_user.is_authenticated and current_user.id == user.id
    
    return render_template(
        "users/public_profile.html",
        user=user,
        reviewed_movies=reviewed_movies,
        watchlist=watchlist_movies,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        is_own_profile=is_own_profile
    )

# ============= FOLLOW/UNFOLLOW =============

@users_bp.route("/<int:user_id>/follow", methods=["POST"])
@login_required
def follow_user(user_id):
    """Follow a user"""
    if user_id == current_user.id:
        return jsonify({"error": "You cannot follow yourself"}), 400
    
    user_to_follow = User.query.get_or_404(user_id)
    
    if current_user.following.filter_by(id=user_id).first():
        return jsonify({"error": "Already following"}), 400
    
    # Add follow relationship
    current_user.following.append(user_to_follow)
    
    # Create notification for the followed user
    notification = Notification(
        user_id=user_to_follow.id,
        actor_id=current_user.id,
        notification_type='follow'
    )
    
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Now following {user_to_follow.name}"})

@users_bp.route("/<int:user_id>/unfollow", methods=["POST"])
@login_required
def unfollow_user(user_id):
    """Unfollow a user"""
    user_to_unfollow = User.query.get_or_404(user_id)
    
    if not current_user.following.filter_by(id=user_id).first():
        return jsonify({"error": "Not following"}), 400
    
    current_user.following.remove(user_to_unfollow)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Unfollowed {user_to_unfollow.name}"})

# ============= FOLLOWERS/FOLLOWING =============

@users_bp.route("/<username>/followers")
def followers_list(username):
    """List followers of a user"""
    username = username.lower()
    user = User.query.filter_by(username=username).first_or_404()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()
    
    query = user.followers
    
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    
    followers = query.paginate(page=page, per_page=12)
    
    # Check which followers current user is following
    following_ids = set()
    if current_user.is_authenticated:
        following_ids = set([u.id for u in current_user.following])
    
    return render_template(
        "users/followers_list.html",
        user=user,
        followers=followers,
        search=search,
        following_ids=following_ids
    )

@users_bp.route("/<username>/following")
def following_list(username):
    """List users that a user is following"""
    username = username.lower()
    user = User.query.filter_by(username=username).first_or_404()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()
    
    query = user.following
    
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    
    following = query.paginate(page=page, per_page=12)
    
    # Check which users current user is following
    following_ids = set()
    if current_user.is_authenticated:
        following_ids = set([u.id for u in current_user.following])
    
    return render_template(
        "users/following_list.html",
        user=user,
        following=following,
        search=search,
        following_ids=following_ids
    )

# ============= USER SEARCH =============

@users_bp.route("/search")
def search_users():
    """Search for users"""
    query = request.args.get('q', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    
    results = None
    if query:
        if len(query) < 2:
            flash("Search must be at least 2 characters", "warning")
        else:
            # Search by name or username
            results = User.query.filter(
                or_(
                    User.name.ilike(f"%{query}%"),
                    User.username.ilike(f"%{query}%")
                )
            ).paginate(page=page, per_page=12)
            
            # Check which users current user is following
            following_ids = set()
            if current_user.is_authenticated:
                following_ids = set([u.id for u in current_user.following])
    
    return render_template(
        "users/search_results.html",
        query=query,
        results=results,
        following_ids=following_ids if results else set()
    )

# ============= USER DIRECTORY =============

@users_bp.route("/directory")
def directory():
    """Browse all users (sorted by followers)"""
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'followers', type=str)
    
    query = User.query.filter(User.role != 'suspended')
    
    if sort_by == 'newest':
        query = query.order_by(User.created_at.desc())
    elif sort_by == 'alphabetical':
        query = query.order_by(User.name.asc())
    else:  # followers (default)
        # Order by number of followers using a subquery
        follower_count = db.func.count(user_followers.c.follower_id).label('follower_count')
        subquery = db.session.query(
            user_followers.c.user_id,
            follower_count
        ).group_by(user_followers.c.user_id).subquery()
        
        query = query.outerjoin(
            subquery,
            User.id == subquery.c.user_id
        ).order_by(db.func.coalesce(subquery.c.follower_count, 0).desc())
    
    users = query.paginate(page=page, per_page=12)
    
    # Check which users current user is following
    following_ids = set()
    if current_user.is_authenticated:
        following_ids = set([u.id for u in current_user.following])
    
    return render_template(
        "users/directory.html",
        users=users,
        sort_by=sort_by,
        following_ids=following_ids
    )

# ============= NOTIFICATIONS =============

@users_bp.route("/notifications")
@login_required
def notifications():
    """Display user notifications"""
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all', type=str)
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'follows':
        query = query.filter_by(notification_type='follow')
    
    notifications_list = query.order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template(
        "users/notifications.html",
        notifications=notifications_list,
        filter_type=filter_type
    )

@users_bp.route("/notifications/mark-as-read", methods=["POST"])
@login_required
def mark_notifications_as_read():
    """Mark all notifications as read"""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return jsonify({"success": True})

@users_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_as_read(notification_id):
    """Mark specific notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({"success": True})

# ============= API ENDPOINTS =============

@users_bp.route("/api/check-username", methods=["GET"])
def check_username():
    """Check if username is available (AJAX)"""
    username = request.args.get('username', '').strip().lower()
    
    if not username:
        return jsonify({"available": False, "message": "Username required"})
    
    if not is_valid_username(username):
        return jsonify({"available": False, "message": "Invalid username format"})
    
    existing = User.query.filter_by(username=username).first()
    available = existing is None
    
    return jsonify({
        "available": available,
        "message": "Username available" if available else "Username already taken"
    })

@users_bp.route("/api/search-users", methods=["GET"])
def api_search_users():
    """API endpoint for user search (for autocomplete)"""
    query = request.args.get('q', '', type=str).strip()
    limit = request.args.get('limit', 5, type=int)
    
    if len(query) < 2:
        return jsonify([])
    
    users = User.query.filter(
        or_(
            User.name.ilike(f"%{query}%"),
            User.username.ilike(f"%{query}%")
        ),
        User.role != 'suspended'
    ).limit(limit).all()
    
    return jsonify([
        {
            'id': user.id,
            'name': user.name,
            'username': user.username,
            'avatar': user.avatar or '/static/images/default-avatar.png'
        }
        for user in users
    ])

@users_bp.route("/api/user/<username>/stats", methods=["GET"])
def user_stats(username):
    """Get user statistics (followers, reviews, watchlist)"""
    username = username.lower()
    user = User.query.filter_by(username=username).first_or_404()
    
    followers_count = user.followers.count()
    following_count = user.following.count()
    reviews_count = Review.query.filter_by(user_id=user.id).count()
    watchlist_count = Watchlist.query.filter_by(user_id=user.id).count()
    
    return jsonify({
        'followers': followers_count,
        'following': following_count,
        'reviews': reviews_count,
        'watchlist': watchlist_count
    })