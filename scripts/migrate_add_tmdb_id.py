"""
Safe migration to add `tmdb_id` column to the `movies` table for existing SQLite DBs.

This script will:
 - back up the existing DB to `instance/cine_sphere.db.bak` (timestamped)
 - add a nullable `tmdb_id` integer column to `movies` if it does not exist
 - create a unique index on `tmdb_id` (if possible)

Usage:
    python scripts\migrate_add_tmdb_id.py

Run this from the project root. The script assumes the SQLite DB is at `instance/cine_sphere.db`.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'instance' / 'cine_sphere.db'

if not DB_PATH.exists():
    print('Database not found at', DB_PATH)
    sys.exit(1)

def column_exists(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

backup_path = DB_PATH.with_suffix(f".db.bak.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
print('Backing up DB to', backup_path)
shutil.copy2(DB_PATH, backup_path)

conn = sqlite3.connect(str(DB_PATH))
try:
    if column_exists(conn, 'movies', 'tmdb_id'):
        print('tmdb_id column already exists — nothing to do')
    else:
        print('Adding tmdb_id column to movies table...')
        conn.execute('ALTER TABLE movies ADD COLUMN tmdb_id INTEGER;')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_movies_tmdb_id ON movies (tmdb_id);')
        conn.commit()
        print('Migration complete — tmdb_id added and index created')
finally:
    conn.close()
