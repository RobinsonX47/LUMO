#!/usr/bin/env python
"""
Migration script to add username field to existing users
Run this before deploying to production
"""

import sys
import os
import re

# Add parent directory to path so we can import from root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import User
from sqlalchemy import text

def generate_unique_username(name):
    """Generate a unique username from name"""
    base_username = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    if not base_username:
        base_username = "user"
    
    if not User.query.filter_by(username=base_username).first():
        return base_username
    
    counter = 1
    while True:
        username = f"{base_username}{counter}"
        if not User.query.filter_by(username=username).first():
            return username
        counter += 1

def migrate_usernames():
    """Migrate existing users by generating usernames"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("LUMO - Username Migration Script")
        print("=" * 60)
        
        # Ensure all tables are created
        print("\n📦 Creating database schema if needed...")
        db.create_all()
        print("✅ Database schema ready")
        
        # Check if username column exists, if not add it
        inspector = db.inspect(db.engine)
        users_columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Add missing columns
        if 'username' not in users_columns:
            print("📝 Adding 'username' column to users table...")
            try:
                db.session.execute(text('ALTER TABLE users ADD COLUMN username VARCHAR(50)'))
                db.session.commit()
                print("✅ Username column added")
            except Exception as e:
                if "Duplicate column name" not in str(e):
                    print(f"⚠️ Error adding username: {e}")
        
        if 'updated_at' not in users_columns:
            print("📝 Adding 'updated_at' column to users table...")
            try:
                db.session.execute(text('ALTER TABLE users ADD COLUMN updated_at DATETIME'))
                db.session.commit()
                print("✅ Updated_at column added")
            except Exception as e:
                if "Duplicate column name" not in str(e):
                    print(f"⚠️ Error adding updated_at: {e}")
        
        # Find users without usernames
        users_without_username = User.query.filter(
            (User.username == None) | (User.username == '')
        ).all()
        
        if not users_without_username:
            print("✅ All users already have usernames!")
            return
        
        print(f"\n📝 Found {len(users_without_username)} users without usernames")
        print("Generating usernames...\n")
        
        migrated = 0
        for user in users_without_username:
            username = generate_unique_username(user.name)
            user.username = username
            migrated += 1
            print(f"  ✓ {user.name} ({user.email}) → @{username}")
        
        db.session.commit()
        print(f"\n✅ Migration complete! {migrated} users updated.")
        print("=" * 60)

if __name__ == "__main__":
    try:
        migrate_usernames()
    except Exception as e:
        print(f"\n❌ Error during migration: {str(e)}")
        sys.exit(1)
