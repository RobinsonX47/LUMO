from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User
from oauth_handler import GoogleOAuth

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Email/password login with basic validation and next support."""
    if request.method == "POST":
        email = (request.form.get("email", "") or "").strip().lower()
        password = request.form.get("password", "") or ""

        if not email or not password:
            flash("Please provide both email and password.", "error")
            return render_template("auth/login.html")

        user = User.query.filter_by(email=email).first()

        # Disallow password login for OAuth-only accounts
        if user and not user.password_hash and user.oauth_provider:
            flash("This account is linked with Google. Please use Google Sign-In.", "error")
            return render_template("auth/login.html")

        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.home"))

        flash("Invalid email or password.", "error")
        return render_template("auth/login.html")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Simple registration with validation and duplicate check."""
    if request.method == "POST":
        name = (request.form.get("name", "") or "").strip()
        email = (request.form.get("email", "") or "").strip().lower()
        password = request.form.get("password", "") or ""

        if not name or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("auth/register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("auth/register.html")

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash("Account created! Welcome to LUMO.", "success")
        return redirect(url_for("main.home"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))


# Google OAuth Routes
@auth_bp.route("/login/google")
def google_login():
    """Redirect to Google for authentication"""
    authorization_url = GoogleOAuth.get_authorization_url()
    return redirect(authorization_url)


@auth_bp.route("/callback/google")
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
                # Create new user
                user = User(
                    name=name,
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