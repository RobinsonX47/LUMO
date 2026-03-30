"""Create watch_progress table and indexes for embedded player progress tracking."""
import sys
sys.path.insert(0, '.')

from app import app
from extensions import db
from sqlalchemy import inspect
from models import WatchProgress


def migrate():
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        if 'watch_progress' in tables:
            print("✓ watch_progress table already exists")
            return

        try:
            WatchProgress.__table__.create(bind=db.engine, checkfirst=True)
            db.session.commit()
            print("✓ watch_progress table created")
        except Exception as exc:
            db.session.rollback()
            print(f"✗ Migration failed: {exc}")
            raise


if __name__ == '__main__':
    migrate()
