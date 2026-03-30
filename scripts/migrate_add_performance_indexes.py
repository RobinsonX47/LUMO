"""
Migration script to add performance-oriented indexes.
Run once after deploying model/index changes.
"""
import sys
sys.path.insert(0, '.')

from app import app
from extensions import db
from sqlalchemy import inspect


def migrate():
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())

            desired_indexes = [
                ("reviews", ["user_id", "created_at"], "ix_reviews_user_created"),
                ("reviews", ["tmdb_movie_id", "created_at"], "ix_reviews_tmdb_created"),
                ("watchlist", ["user_id", "added_at"], "ix_watchlist_user_added"),
                ("watchlist", ["user_id", "media_type"], "ix_watchlist_user_media"),
                ("notifications", ["user_id", "is_read", "created_at"], "ix_notifications_user_read_created"),
                ("notifications", ["actor_id", "created_at"], "ix_notifications_actor_created"),
            ]

            for table_name, columns, index_name in desired_indexes:
                if table_name not in existing_tables:
                    print(f"- Skipping {index_name}: table '{table_name}' does not exist")
                    continue

                existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
                missing_columns = [col for col in columns if col not in existing_columns]
                if missing_columns:
                    print(f"- Skipping {index_name}: missing columns {missing_columns}")
                    continue

                column_sql = ", ".join(columns)
                statement = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_sql})"
                db.session.execute(db.text(statement))

            db.session.commit()
            print("✓ Performance indexes created (or already existed)")
        except Exception as exc:
            db.session.rollback()
            print(f"✗ Failed to create indexes: {exc}")
            raise


if __name__ == '__main__':
    migrate()
