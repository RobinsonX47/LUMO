from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, limiter
from models import User
from oauth_handler import GoogleOAuth
from forms import LoginForm, RegisterForm
import re

auth_bp = Blueprint("auth", __name__)

def is_valid_username(username):
    """Validate username format (alphanumeric, underscores, hyphens, 3-30 chars)"""
    pattern = r'^[a-zA-Z0-9_-]{3,30}$'
    return re.match(pattern, username) is not None

def generate_unique_username(name):
    """Generate a unique username from name"""
    # Remove non-alphanumeric characters except spaces
    base_username = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    if not base_username:
        base_username = "user"
    
    # Check if base username is available
    if not User.query.filter_by(username=base_username).first():
        return base_username
    
    # Add numbers until we find an available username
    counter = 1
    while True:
        username = f"{base_username}{counter}"
        if not User.query.filter_by(username=username).first():
            return username
        counter += 1

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")  # Prevent brute force attacks
def login():
    """Email/password login with WTForms validation and CSRF protection"""
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        
        user = User.query.filter_by(email=email).first()

        # Disallow password login for OAuth-only accounts
        if user and not user.password_hash and user.oauth_provider:
            flash("This account is linked with Google. Please use Google Sign-In.", "error")
            return render_template("auth/login.html", form=form)

        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user, remember=form.remember.data)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.home"))

        flash("Invalid email or password.", "error")
        return render_template("auth/login.html", form=form)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour")  # Prevent spam registrations
def register():
    """Registration with WTForms validation, CSRF protection, and strong password policy"""
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Create user
        user = User(
            name=form.name.data.strip(),
            username=form.username.data.strip().lower(),
            email=form.email.data.strip().lower(),
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user, remember=True)
        flash("Account created! Welcome to LUMO.", "success")
        return redirect(url_for("main.home"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))


# Google OAuth Routes
@auth_bp.route("/login/google")
@limiter.limit("10 per minute")
def google_login():
    """Redirect to Google for authentication"""
    authorization_url = GoogleOAuth.get_authorization_url()
    return redirect(authorization_url)


@auth_bp.route("/callback/google")
@limiter.limit("10 per minute")
def google_callback():
    """Handle Google OAuth callback"""
    code = request.args.get("code")
    
    if not code:
        flash("Failed to get authorization code from Google")
        return redirect(url_for("auth.login"))
    
    try:
        # Exchange code for token
        tokens = GoogleOAuth.exchange_code_for_token(code)
        
        # Get user info
        user_info = GoogleOAuth.get_user_info(tokens.get("access_token"))
        
        # Extract user information
        google_id = user_info.get("sub")
        email = user_info.get("email")
        name = user_info.get("name", email.split("@")[0])
        picture = user_info.get("picture")
        
        # Check if user exists
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if email already exists
            existing_user = User.query.filter_by(email=email).first()
            
            if existing_user:
                # Link Google account to existing user
                existing_user.google_id = google_id
                existing_user.oauth_provider = "google"
                if picture:
                    existing_user.avatar = picture
                db.session.commit()
                user = existing_user
            else:
                # Create new user with auto-generated username
                username = generate_unique_username(name)
                user = User(
                    name=name,
                    username=username,
                    email=email,
                    google_id=google_id,
                    oauth_provider="google",
                    avatar=picture
                )
                db.session.add(user)
                db.session.commit()
        
        # Log in user
        login_user(user)
        flash(f"Welcome, {user.name}!", "success")
        return redirect(url_for("main.home"))
    
    except Exception as e:
        flash(f"An error occurred during Google login: {str(e)}")
        return redirect(url_for("auth.login"))