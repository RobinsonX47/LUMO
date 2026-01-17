"""
Migration script to add Google OAuth fields to the User model.
Run this after updating your database schema.
"""
import sqlite3
import os

def migrate():
    # Get database path
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'cine_sphere.db')
    
    if not os.path.exists(db_path):
        print("❌ Database not found at:", db_path)
        return
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get existing columns
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add google_id column if it doesn't exist (without UNIQUE constraint)
        if 'google_id' not in columns:
            print("Adding google_id column...")
            cursor.execute('ALTER TABLE users ADD COLUMN google_id VARCHAR(255) DEFAULT NULL')
            print("✅ google_id column added")
        else:
            print("✅ google_id column already exists")
        
        # Add oauth_provider column if it doesn't exist
        if 'oauth_provider' not in columns:
            print("Adding oauth_provider column...")
            cursor.execute('ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50) DEFAULT NULL')
            print("✅ oauth_provider column added")
        else:
            print("✅ oauth_provider column already exists")
        
        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("   You can now use Google OAuth!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
