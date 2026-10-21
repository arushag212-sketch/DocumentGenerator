"""Application configuration settings with strict secret enforcement and dev-mode fallbacks."""

from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _load_env_file():
    """Load key-value pairs from .env in BASE_DIR into os.environ if not already present."""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


_load_env_file()

KNOWN_INSECURE_DEFAULTS = {
    "c1ubd0cs-svnit-s3cur3-k3y-ph4s3-w2-k33p-s3cr3t-pr0ducti0n",
    "svnit-docgen-aes256-key-32bytes-secret!",
    "secret",
    "changeme",
    "generate-a-secure-random-jwt-secret-in-production",
    "generate-a-valid-fernet-key-in-production",
}


class Settings(BaseModel):
    PROJECT_NAME: str = "ClubDocs"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Environment mode: 'development', 'test', 'production'
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development").lower()

    # Security Secrets
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Short-lived access tokens (15-30 min)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30  # Password reset tokens expire in 30 mins

    # Password Policy
    MIN_PASSWORD_LENGTH: int = 10

    # Field-level Encryption Key (Fernet key)
    FIELD_ENCRYPTION_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    # Storage paths
    STORAGE_DIR: Path = BASE_DIR / "storage"
    ASSETS_DIR: Path = BASE_DIR / "assets"
    DATA_DIR: Path = BASE_DIR / "data"

    # Google OAuth & Email Domain Policy
    GOOGLE_CLIENT_ID: str = ""
    ALLOWED_EMAIL_DOMAIN: str = ""
    # Google-verified emails that become platform admins on sign-in (comma-separated env var)
    PLATFORM_ADMIN_EMAILS: list[str] = []

    def __init__(self, **data):
        super().__init__(**data)
        self._initialize_secrets()

    def _initialize_secrets(self):
        env_mode = self.ENVIRONMENT
        jwt_key = os.environ.get("JWT_SECRET_KEY", "").strip()
        field_key = os.environ.get("FIELD_ENCRYPTION_KEY", "").strip()

        is_dev = env_mode in ("development", "test", "dev")

        # Validation for JWT_SECRET_KEY
        if not jwt_key or jwt_key in KNOWN_INSECURE_DEFAULTS:
            if not is_dev:
                raise RuntimeError(
                    f"FATAL: In non-development mode ({env_mode}), JWT_SECRET_KEY environment variable "
                    f"must be explicitly provided and cannot use a known default placeholder."
                )
            generated_jwt = secrets.token_urlsafe(32)
            warnings.warn(
                f"[DEV WARNING] JWT_SECRET_KEY not set in env for '{env_mode}'. Generated ephemeral per-run secret.",
                RuntimeWarning,
            )
            self.JWT_SECRET_KEY = generated_jwt
        else:
            self.JWT_SECRET_KEY = jwt_key

        # Validation for FIELD_ENCRYPTION_KEY (must be valid Fernet base64 key)
        if not field_key or field_key in KNOWN_INSECURE_DEFAULTS:
            if not is_dev:
                raise RuntimeError(
                    f"FATAL: In non-development mode ({env_mode}), FIELD_ENCRYPTION_KEY environment variable "
                    f"must be explicitly provided as a valid Fernet key and cannot use a placeholder."
                )
            generated_fernet = Fernet.generate_key().decode()
            warnings.warn(
                f"[DEV WARNING] FIELD_ENCRYPTION_KEY not set in env for '{env_mode}'. Generated ephemeral Fernet key.",
                RuntimeWarning,
            )
            self.FIELD_ENCRYPTION_KEY = generated_fernet
        else:
            # Validate Fernet key format
            try:
                Fernet(field_key.encode())
                self.FIELD_ENCRYPTION_KEY = field_key
            except Exception as e:
                if not is_dev:
                    raise RuntimeError(f"FATAL: FIELD_ENCRYPTION_KEY is invalid for Fernet: {e}")
                generated_fernet = Fernet.generate_key().decode()
                self.FIELD_ENCRYPTION_KEY = generated_fernet

        # Validation for ALLOWED_EMAIL_DOMAIN in production
        allowed_domain = os.environ.get("ALLOWED_EMAIL_DOMAIN", "").strip().lower()
        if not allowed_domain and not is_dev:
            raise RuntimeError(
                f"FATAL: In non-development mode ({env_mode}), ALLOWED_EMAIL_DOMAIN environment variable "
                f"must be explicitly provided."
            )
        self.ALLOWED_EMAIL_DOMAIN = allowed_domain

        # Google OAuth Client ID
        self.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()

        self.PLATFORM_ADMIN_EMAILS = [
            e.strip().lower() for e in os.environ.get("PLATFORM_ADMIN_EMAILS", "").split(",") if e.strip()
        ]

        # Allowed browser origins, comma-separated (e.g. the Vercel site). Replaces the local defaults.
        cors_env = os.environ.get("CORS_ORIGINS", "").strip()
        if cors_env:
            self.CORS_ORIGINS = [o.strip().rstrip("/") for o in cors_env.split(",") if o.strip()]


settings = Settings()
