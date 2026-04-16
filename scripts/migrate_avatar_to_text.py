#!/usr/bin/env python
"""
Migration script to ensure users.avatar can store DB-backed image payloads.

For PostgreSQL, this script upgrades users.avatar from VARCHAR(255) to TEXT.
For SQLite, no change is required because SQLite does not enforce VARCHAR length.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


def migrate_avatar_column() -> None:
	app = create_app()

	with app.app_context():
		print("=" * 60)
		print("LUMO - Avatar Column Migration")
		print("=" * 60)

		inspector = inspect(db.engine)
		dialect = db.engine.dialect.name

		if "users" not in inspector.get_table_names():
			print("Users table not found; creating schema first...")
			db.create_all()
			inspector = inspect(db.engine)

		user_columns = {col["name"]: col for col in inspector.get_columns("users")}
		if "avatar" not in user_columns:
			print("Avatar column not found; adding TEXT avatar column...")
			db.session.execute(text("ALTER TABLE users ADD COLUMN avatar TEXT"))
			db.session.commit()
			print("Added avatar column as TEXT")
			return

		if dialect == "postgresql":
			print("PostgreSQL detected, converting users.avatar to TEXT...")
			db.session.execute(text("ALTER TABLE users ALTER COLUMN avatar TYPE TEXT"))
			db.session.commit()
			print("users.avatar converted to TEXT")
			return

		if dialect == "sqlite":
			print("SQLite detected; VARCHAR length is not strictly enforced. No change needed.")
			return

		print(f"Database dialect '{dialect}' detected. No automatic migration applied.")
		print("Run a manual ALTER TABLE to set users.avatar to a large text type.")


if __name__ == "__main__":
	try:
		migrate_avatar_column()
	except Exception as exc:
		print(f"Migration failed: {exc}")
		sys.exit(1)
