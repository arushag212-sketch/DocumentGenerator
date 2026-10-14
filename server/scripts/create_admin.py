"""CLI utility to create or update a Platform Admin with a secure Argon2 password."""

from __future__ import annotations

import getpass
import sys
from passlib.context import CryptContext

from server.app.core.database import SessionLocal, Base, engine
from server.app.models import User

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("=" * 60)
    print(" ClubDocs: Create/Update Platform Admin")
    print("=" * 60)

    email = input("Admin Email: ").strip()
    if not email:
        print("Error: Email is required.")
        sys.exit(1)

    name = input("Admin Name (default: 'Platform Admin'): ").strip() or "Platform Admin"

    password = getpass.getpass("Password: ")
    if not password:
        print("Error: Password is required.")
        sys.exit(1)

    confirm_password = getpass.getpass("Confirm Password: ")
    if password != confirm_password:
        print("Error: Passwords do not match.")
        sys.exit(1)

    pw_hash = hash_password(password)

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.password_hash = pw_hash
        user.name = name
        user.is_platform_admin = True
        print(f"[OK] Updated existing user '{email}' as platform admin with Argon2 password.")
    else:
        user = User(
            email=email,
            password_hash=pw_hash,
            name=name,
            is_platform_admin=True,
        )
        db.add(user)
        print(f"[OK] Created new platform admin '{email}' with Argon2 password.")

    db.commit()
    db.close()


if __name__ == "__main__":
    main()
