"""
Migration script to update the database schema for TMDB integration
Run this script from the project root: python scripts/migrate_to_tmdb.py
"""
import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import shutil

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / 'instance' / 'cine_sphere.db'

def backup_database():
    """Create a backup of the database"""
    if not DB_PATH.exists():
        print("❌ Database not found at", DB_PATH)
        print("Creating new database...")
        return False
    
    backup_path = DB_PATH.with_suffix(f".db.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    print(f"📦 Backing up database to {backup_path.name}")
    shutil.copy2(DB_PATH, backup_path)
    print("✅ Backup created successfully")
    return True

def column_exists(conn, table, column):
    """Check if a column exists in a table"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def migrate_database():
    """Run all database migrations"""
    # Ensure instance directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Backup if exists
    had_backup = backup_database()
    
    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        print("\n🔧 Running migrations...\n")
        
        # Migration 1: Add tmdb_movie_id to reviews
        if not column_exists(conn, 'reviews', 'tmdb_movie_id'):
            print("📝 Adding tmdb_movie_id column to reviews table...")
            cursor.execute("ALTER TABLE reviews ADD COLUMN tmdb_movie_id INTEGER")
            print("✅ Added tmdb_movie_id to reviews")
        else:
            print("✓ tmdb_movie_id already exists in reviews")
        
        # Migration 2: Add tmdb_movie_id to watchlist
        if not column_exists(conn, 'watchlist', 'tmdb_movie_id'):
            print("📝 Adding tmdb_movie_id column to watchlist table...")
            cursor.execute("ALTER TABLE watchlist ADD COLUMN tmdb_movie_id INTEGER")
            print("✅ Added tmdb_movie_id to watchlist")
        else:
            print("✓ tmdb_movie_id already exists in watchlist")
        
        # Migration 3: Add movie_title to watchlist (for caching)
        if not column_exists(conn, 'watchlist', 'movie_title'):
            print("📝 Adding movie_title column to watchlist table...")
            cursor.execute("ALTER TABLE watchlist ADD COLUMN movie_title VARCHAR(200)")
            print("✅ Added movie_title to watchlist")
        else:
            print("✓ movie_title already exists in watchlist")
        
        # Migration 4: Add poster_path to watchlist (for caching)
        if not column_exists(conn, 'watchlist', 'poster_path'):
            print("📝 Adding poster_path column to watchlist table...")
            cursor.execute("ALTER TABLE watchlist ADD COLUMN poster_path VARCHAR(255)")
            print("✅ Added poster_path to watchlist")
        else:
            print("✓ poster_path already exists in watchlist")
        
        # Migration 5: Make movie_id nullable in reviews (for TMDB-only reviews)
        print("📝 Reviews table already allows nullable movie_id")
        
        # Migration 6: Add id column to watchlist if it doesn't have one
        if not column_exists(conn, 'watchlist', 'id'):
            print("📝 Recreating watchlist table with id column...")
            # Create new table with id
            cursor.execute("""
                CREATE TABLE watchlist_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER,
                    tmdb_movie_id INTEGER,
                    movie_title VARCHAR(200),
                    poster_path VARCHAR(255),
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (movie_id) REFERENCES movies(id),
                    UNIQUE(user_id, tmdb_movie_id)
                )
            """)
            
            # Copy data from old table
            cursor.execute("""
                INSERT INTO watchlist_new (user_id, movie_id, tmdb_movie_id, movie_title, poster_path, added_at)
                SELECT user_id, movie_id, tmdb_movie_id, movie_title, poster_path, added_at
                FROM watchlist
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE watchlist")
            cursor.execute("ALTER TABLE watchlist_new RENAME TO watchlist")
            print("✅ Recreated watchlist table with id column")
        else:
            print("✓ id column already exists in watchlist")
        
        # Commit all changes
        conn.commit()
        print("\n✅ All migrations completed successfully!")
        
        # Show table structure
        print("\n📊 Current table structures:")
        for table in ['reviews', 'watchlist']:
            print(f"\n{table.upper()}:")
            cursor.execute(f"PRAGMA table_info({table})")
            for row in cursor.fetchall():
                print(f"  - {row[1]} ({row[2]})")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        if had_backup:
            print("💡 You can restore from the backup if needed")
        sys.exit(1)
    finally:
        conn.close()
    
    print("\n🎉 Database migration complete!")
    print("\n💡 Next steps:")
    print("1. Set your TMDB_API_KEY in config.py or environment variable")
    print("2. Run: python app.py")
    print("3. Visit http://localhost:5000")

if __name__ == "__main__":
    print("=" * 60)
    print("LUMO Database Migration Script")
    print("=" * 60)
    print()
    
    migrate_database()