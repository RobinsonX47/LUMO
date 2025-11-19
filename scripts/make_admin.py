#!/usr/bin/env python
r"""
Utility script to promote an existing user to admin or create a new admin user.

Usage examples (PowerShell):

# Promote an existing user to admin (interactive confirmation)
python scripts/make_admin.py --email user@example.com

# Promote without prompt
python scripts/make_admin.py --email user@example.com --yes

# Create a new admin user with a password you provide
python scripts/make_admin.py --create --email admin@example.com --name "Site Admin" --password "ChangeMe123!"

# Create with a specific id (be careful)
python scripts/make_admin.py --create --email admin2@example.com --name "Admin Two" --password "pw" --id 42

"""
import argparse
import getpass
import os
import sys

# Ensure project root is on sys.path so imports like `from app import create_app`
# work whether the script is run from the project root or from the `scripts/`
# directory directly.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser(description='Promote/create an admin user for LUMO')
    parser.add_argument('--email', required=True, help='Email of the user')
    parser.add_argument('--create', action='store_true', help='Create the user if it does not exist')
    parser.add_argument('--name', help='Name for new user (required with --create)')
    parser.add_argument('--password', help='Password for new user (will prompt if not provided when creating)')
    parser.add_argument('--id', type=int, help='Optional id for new user (use with caution)')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=args.email).first()

        if user and not args.create:
            # Promote existing user
            if not args.yes:
                confirm = input(f"Promote existing user {args.email} (id={user.id}) to admin? [y/N]: ")
                if confirm.lower() != 'y':
                    print('Aborted')
                    return

            user.role = 'admin'
            db.session.commit()
            print(f"User {user.email} (id={user.id}) promoted to admin")
            return

        if user and args.create:
            print(f"User with email {args.email} already exists (id={user.id}). Setting role to admin.")
            user.role = 'admin'
            if args.password:
                user.password_hash = generate_password_hash(args.password)
            db.session.commit()
            print(f"Updated user {user.email} (id={user.id}) and set role=admin")
            return

        # At this point user does not exist
        if not args.create:
            print(f"User with email {args.email} not found. Use --create to create a new admin user.")
            return

        # Creating new user
        if not args.name:
            print('When creating a user you must provide --name')
            return

        password = args.password
        if not password:
            # prompt for password twice
            while True:
                pw = getpass.getpass('Enter password for new user: ')
                if not pw:
                    print('Password cannot be empty')
                    continue
                pw2 = getpass.getpass('Confirm password: ')
                if pw != pw2:
                    print('Passwords do not match, try again')
                    continue
                password = pw
                break

        # Final confirmation
        if not args.yes:
            confirm = input(f"Create new admin user {args.email} with name '{args.name}'? [y/N]: ")
            if confirm.lower() != 'y':
                print('Aborted')
                return

        new_user = User(id=args.id if args.id else None,
                        name=args.name,
                        email=args.email,
                        password_hash=generate_password_hash(password),
                        role='admin')
        db.session.add(new_user)
        db.session.commit()
        print(f"Created admin user {new_user.email} (id={new_user.id})")


if __name__ == '__main__':
    main()
