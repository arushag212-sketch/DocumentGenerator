"""Application configuration settings."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseModel):
    PROJECT_NAME: str = "ClubDocs"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Security & Tokens
    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "c1ubd0cs-svnit-s3cur3-k3y-ph4s3-w2-k33p-s3cr3t-pr0ducti0n"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Password hashing algorithm (Argon2)
    PASSWORD_HASH_SCHEME: str = "argon2"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Storage paths
    STORAGE_DIR: Path = BASE_DIR / "storage"
    ASSETS_DIR: Path = BASE_DIR / "assets"
    DATA_DIR: Path = BASE_DIR / "data"

    # Sensitive fields encryption key (for mobile/bank details)
    FIELD_ENCRYPTION_KEY: str = os.environ.get(
        "FIELD_ENCRYPTION_KEY", "svnit-docgen-aes256-key-32bytes-secret!"
    )


settings = Settings()
