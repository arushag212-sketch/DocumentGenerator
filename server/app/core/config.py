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


settings = Settings()
