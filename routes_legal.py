from flask import Blueprint, render_template

legal_bp = Blueprint("legal", __name__)

@legal_bp.route("/privacy")
def privacy_policy():
    """Privacy policy page"""
    return render_template("legal/privacy.html")

@legal_bp.route("/terms")
def terms_of_service():
    """Terms of service page"""
    return render_template("legal/terms.html")

@legal_bp.route("/cookies")
def cookie_policy():
    """Cookie policy page"""
    return render_template("legal/cookies.html")
