"""
WTForms - Secure form validation with CSRF protection
All forms include automatic CSRF token generation and validation
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, BooleanField
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, ValidationError, Optional, NumberRange
)
from models import User
import re


class LoginForm(FlaskForm):
    """Login form with email and password validation"""
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address"),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required")
    ])
    remember = BooleanField('Remember Me')


class RegisterForm(FlaskForm):
    """Registration form with strong password validation"""
    name = StringField('Name', validators=[
        DataRequired(message="Name is required"),
        Length(min=2, max=100, message="Name must be between 2-100 characters")
    ])
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=30, message="Username must be between 3-30 characters")
    ])
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address"),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        EqualTo('password', message="Passwords must match")
    ])
    
    def validate_username(self, username):
        """Custom validation for username format and uniqueness"""
        # Check format (alphanumeric, underscores, hyphens only)
        pattern = r'^[a-zA-Z0-9_-]{3,30}$'
        if not re.match(pattern, username.data):
            raise ValidationError(
                "Username must contain only letters, numbers, hyphens, and underscores"
            )
        
        # Check uniqueness
        user = User.query.filter_by(username=username.data.lower()).first()
        if user:
            raise ValidationError("Username already taken. Please choose another.")
    
    def validate_email(self, email):
        """Custom validation for email uniqueness"""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError("Email already registered. Please log in instead.")
    
    def validate_password(self, password):
        """Enforce strong password policy"""
        pwd = password.data
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError("Password must contain at least one uppercase letter")
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', pwd):
            raise ValidationError("Password must contain at least one lowercase letter")
        
        # Check for at least one digit
        if not re.search(r'\d', pwd):
            raise ValidationError("Password must contain at least one number")


class ReviewForm(FlaskForm):
    """Movie review form with rating and text validation"""
    rating = IntegerField('Rating', validators=[
        DataRequired(message="Please select a rating"),
        NumberRange(min=1, max=5, message="Rating must be between 1 and 5 stars")
    ])
    review_text = TextAreaField('Review', validators=[
        DataRequired(message="Review text is required"),
        Length(min=10, max=2000, message="Review must be between 10-2000 characters")
    ])


class ProfileUpdateForm(FlaskForm):
    """User profile update form"""
    name = StringField('Name', validators=[
        DataRequired(message="Name is required"),
        Length(min=2, max=100, message="Name must be between 2-100 characters")
    ])
    bio = TextAreaField('Bio', validators=[
        Optional(),
        Length(max=500, message="Bio must be less than 500 characters")
    ])


class PasswordChangeForm(FlaskForm):
    """Password change form with current password verification"""
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message="Current password is required")
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message="New password is required"),
        Length(min=8, message="Password must be at least 8 characters")
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message="Please confirm your new password"),
        EqualTo('new_password', message="Passwords must match")
    ])
    
    def validate_new_password(self, new_password):
        """Enforce strong password policy"""
        pwd = new_password.data
        
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', pwd):
            raise ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', pwd):
            raise ValidationError("Password must contain at least one number")
