"""Authentication, password hashing, Fernet field encryption, and token utilities."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from server.app.core.config import settings

# Strict Argon2 hashing configuration
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)

# Common passwords list for strict password policy enforcement
COMMON_PASSWORDS = {
    "password123",
    "password1234",
    "1234567890",
    "12345678901",
    "qwertyuiop",
    "admin12345",
    "admin123456",
    "svnit12345",
    "welcome1234",
    "letmein1234",
    "changeme123",
    "iloveyou123",
}


def validate_password_policy(password: str) -> None:
    """Validate password length and reject common passwords."""
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long.")
    if password.lower() in COMMON_PASSWORDS or password in COMMON_PASSWORDS:
        raise ValueError("Password is too common and easily guessed. Please choose a stronger password.")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored Argon2 hash."""
    if not hashed_password or hashed_password.startswith("!"):
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password with Argon2 after validating policy."""
    validate_password_policy(password)
    return pwd_context.hash(password)


# ---------------- FIELD-LEVEL ENCRYPTION (Fernet / AES-GCM) ----------------


def _get_fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise RuntimeError("FIELD_ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_field(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a sensitive plaintext string at rest using Fernet."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    encrypted_bytes = f.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_field(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a Fernet-encrypted ciphertext string."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    try:
        decrypted_bytes = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception):
        # Fallback if value was stored plaintext before encryption was enabled
        return ciphertext


def mask_sensitive_field(value: Optional[str], visible_chars: int = 4) -> str:
    """Mask sensitive identifiers leaving only the last visible_chars (default 4)."""
    if not value:
        return ""
    clean_val = str(value).strip()
    if len(clean_val) <= visible_chars:
        return "*" * len(clean_val)
    return "*" * (len(clean_val) - visible_chars) + clean_val[-visible_chars:]


# ---------------- TOKEN & SESSION UTILITIES ----------------


def create_access_token(user_id: str, email: str, token_version: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived (15-30 min) JWT access token with token_version for server-side revocation."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "token_version": token_version,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, token_version: int) -> str:
    """Create a 7-day refresh token for rotating access tokens."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "token_version": token_version,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# ---------------- CSRF PROTECTION ----------------


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random token for CSRF double-submit."""
    return secrets.token_urlsafe(32)


# ---------------- SINGLE-USE PASSWORD RESET TOKENS ----------------


def hash_token(raw_token: str) -> str:
    """Hash a token using SHA-256 for safe database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_reset_token() -> tuple[str, str]:
    """Generate a single-use random reset token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash
