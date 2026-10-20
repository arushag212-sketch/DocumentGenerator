"""CLI utility to create or update a Platform Admin with a secure Argon2 password."""

from __future__ import annotations

import argparse
import getpass
import sys
from passlib.context import CryptContext

from server.app.core.database import SessionLocal
from server.app.models import User

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_platform_admin(email: str, password: str, name: str = "Platform Admin"):
    """Create or update a platform admin user."""
    db = SessionLocal()
    try:
        pw_hash = hash_password(password)
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if user:
            user.password_hash = pw_hash
            user.name = name.strip()
            user.is_platform_admin = True
            db.commit()
            print(f"[OK] Updated existing user '{email}' as platform admin with Argon2 password.")
        else:
            user = User(
                email=email.strip().lower(),
                password_hash=pw_hash,
                name=name.strip(),
                is_platform_admin=True,
            )
            db.add(user)
            db.commit()
            print(f"[OK] Created new platform admin '{email}' with Argon2 password.")
        return user
    finally:
        db.close()


def main():
    # Tables come from Alembic migrations (python -m server.scripts.migrate), never create_all
    parser = argparse.ArgumentParser(description="Create or update Platform Admin")
    parser.add_argument("--email", help="Admin email address")
    parser.add_argument("--password", help="Admin password")
    parser.add_argument("--name", default="Platform Admin", help="Admin display name")
    args = parser.parse_args()

    email = args.email
    password = args.password
    name = args.name

    if not email or not password:
        print("=" * 60)
        print(" ClubDocs: Create/Update Platform Admin")
        print("=" * 60)

        if not email:
            email = input("Admin Email: ").strip()
            if not email:
                print("Error: Email is required.")
                sys.exit(1)

        if not name or name == "Platform Admin":
            name = input("Admin Name (default: 'Platform Admin'): ").strip() or "Platform Admin"

        if not password:
            password = getpass.getpass("Password: ")
            if not password:
                print("Error: Password is required.")
                sys.exit(1)

            confirm_password = getpass.getpass("Confirm Password: ")
            if password != confirm_password:
                print("Error: Passwords do not match.")
                sys.exit(1)

    create_platform_admin(email=email, password=password, name=name)


if __name__ == "__main__":
    main()
