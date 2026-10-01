"""
Create an admin user for Legacy CRM.

Usage:
    docker compose exec -e ADMIN_PASSWORD=<choose-one> backend python create_user.py
"""

import os
import sys

from app.database import SessionLocal
from app.models.user import User
from app.utils.auth import hash_password

# Credentials come from the environment so none live in the repo.
NAME = os.environ.get("ADMIN_NAME", "Dale")
EMAIL = os.environ.get("ADMIN_EMAIL", "dale@legacy-roofing.example")
PASSWORD = os.environ.get("ADMIN_PASSWORD")
ROLE = "admin"


def main():
    if not PASSWORD:
        print("Set ADMIN_PASSWORD before running this script.")
        sys.exit(1)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == EMAIL).first()
        if existing:
            print(f"User '{EMAIL}' already exists (id={existing.id}). Skipping.")
            return

        user = User(
            email=EMAIL,
            full_name=NAME,
            password_hash=hash_password(PASSWORD),
            role=ROLE,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created admin user: {NAME} <{EMAIL}> (id={user.id})")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
