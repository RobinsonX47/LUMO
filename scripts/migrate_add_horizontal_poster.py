"""Small migration script to add `horizontal_poster_path` column to `movies` table.

Usage:
    python scripts\migrate_add_horizontal_poster.py

It will:
 - read the DATABASE URI from `config.Config.SQLALCHEMY_DATABASE_URI`
 - extract the sqlite file path
 - backup the DB to `cine_sphere.db.bak` (in the same folder)
 - run: ALTER TABLE movies ADD COLUMN horizontal_poster_path VARCHAR(255);

This is safe for SQLite (ADD COLUMN is supported). If the column already exists,
it will print a message and exit.
"""
import os
import sqlite3
import shutil
import sys

# Import config from project (ensure project root is on sys.path when running from repo root)
try:
    from config import Config
except Exception as e:
    print("Unable to import Config from config.py:", e)
    sys.exit(1)

if not Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
    print('This script only supports sqlite:/// URIs. Found:', Config.SQLALCHEMY_DATABASE_URI)
    sys.exit(1)

db_path = Config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
if not os.path.isabs(db_path):
    db_path = os.path.abspath(db_path)

if not os.path.exists(db_path):
    print('Database file not found at', db_path)
    sys.exit(1)

# Backup
bak_path = db_path + '.bak'
print(f'Backing up DB: {db_path} -> {bak_path}')
shutil.copy2(db_path, bak_path)

# Run ALTER TABLE
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE movies ADD COLUMN horizontal_poster_path VARCHAR(255);")
    conn.commit()
    print('Added column horizontal_poster_path to movies table.')
except sqlite3.OperationalError as e:
    # This may appear if column already exists or other issues
    msg = str(e).lower()
    if 'duplicate column name' in msg or 'has no column named' in msg or 'duplicate' in msg:
        print('Column may already exist or cannot be added:', e)
    elif 'table movies has no column named' in msg:
        print('Unexpected error:', e)
    else:
        print('OperationalError:', e)
finally:
    conn.close()

print('Done.')
