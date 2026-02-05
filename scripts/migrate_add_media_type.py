"""
Migration script to add media_type column to Watchlist table
Run this once to update existing database
"""
import sys
sys.path.insert(0, '.')

from app import create_app
from extensions import db

def migrate():
    app = create_app()
    
    with app.app_context():
        # Check if column already exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('watchlist')]
        
        if 'media_type' in columns:
            print("✓ media_type column already exists")
            return
        
        print("Adding media_type column to watchlist table...")
        
        try:
            # Add the new column
            db.session.execute(db.text(
                "ALTER TABLE watchlist ADD COLUMN media_type VARCHAR(10) DEFAULT 'movie'"
            ))
            db.session.commit()
            print("✓ Successfully added media_type column")
            
            # Update existing entries - try to infer media_type from TMDB
            print("Updating existing watchlist entries...")
            from models import Watchlist
            from tmdb_service import TMDBService
            
            entries = Watchlist.query.all()
            updated = 0
            
            for entry in entries:
                # Try movie first
                movie = TMDBService.get_movie_details(entry.tmdb_movie_id)
                if movie and entry.movie_title:
                    movie_title = (movie.get('title') or '').strip().lower()
                    stored_title = (entry.movie_title or '').strip().lower()
                    if movie_title == stored_title:
                        entry.media_type = 'movie'
                        updated += 1
                        continue
                
                # Try TV
                tv = TMDBService.get_tv_details(entry.tmdb_movie_id)
                if tv and entry.movie_title:
                    tv_title = (tv.get('name') or '').strip().lower()
                    stored_title = (entry.movie_title or '').strip().lower()
                    if tv_title == stored_title:
                        entry.media_type = 'tv'
                        updated += 1
                        continue
                
                # Default to movie
                entry.media_type = 'movie'
                updated += 1
            
            db.session.commit()
            print(f"✓ Updated {updated} watchlist entries")
            
        except Exception as e:
            print(f"✗ Error during migration: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate()
