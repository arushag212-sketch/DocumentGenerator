"""Authentication, password hashing, and token utilities using Argon2 and JWT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

from server.app.core.config import settings

# Strict Argon2 hashing configuration
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored Argon2 hash."""
    if not hashed_password or hashed_password.startswith("!"):
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password with Argon2."""
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a signed JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def mask_sensitive_field(value: Optional[str], visible_chars: int = 4) -> str:
    """Mask sensitive identifiers (bank account, mobile, PAN) leaving only the last 4 characters visible."""
    if not value:
        return ""
    clean_val = str(value).strip()
    if len(clean_val) <= visible_chars:
        return "*" * len(clean_val)
    return "*" * (len(clean_val) - visible_chars) + clean_val[-visible_chars:]
