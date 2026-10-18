"""Cloud and local disk storage abstraction for documents, batches, and assets."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clubdocs.storage")


class Storage(ABC):
    """Abstract interface for file persistence."""

    @abstractmethod
    def save(self, path: str, data: bytes) -> str:
        """Save raw bytes to the given relative path and return its canonical identifier/path."""
        pass

    @abstractmethod
    def load(self, path: str) -> bytes:
        """Load and return the raw bytes from the given path."""
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete file at path. Returns True if deleted or already absent."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file exists at path."""
        pass

    @abstractmethod
    def public_url(self, path: str) -> str:
        """Return public or internal download/view URL for the given path."""
        pass


class LocalDiskStorage(Storage):
    """Local filesystem storage writing to a root directory (default 'storage/')."""

    def __init__(self, base_dir: Optional[Path | str] = None):
        self.base_dir = Path(base_dir or "storage").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, path: str) -> Path:
        """Ensure no directory traversal escaping base_dir."""
        clean = Path(path).as_posix().lstrip("/\\")
        resolved = (self.base_dir / clean).resolve()
        if not str(resolved).startswith(str(self.base_dir)):
            raise ValueError(f"Security violation: path traversal detected '{path}'")
        return resolved

    def save(self, path: str, data: bytes) -> str:
        target = self._resolve_safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target.relative_to(self.base_dir))

    def load(self, path: str) -> bytes:
        target = self._resolve_safe_path(path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: '{path}'")
        return target.read_bytes()

    def delete(self, path: str) -> bool:
        try:
            target = self._resolve_safe_path(path)
            if target.exists():
                target.unlink()
            return True
        except Exception as e:
            logger.warning("Failed to delete local file '%s': %s", path, e)
            return False

    def exists(self, path: str) -> bool:
        try:
            target = self._resolve_safe_path(path)
            return target.is_file()
        except Exception:
            return False

    def public_url(self, path: str) -> str:
        clean = Path(path).as_posix().lstrip("/\\")
        return f"/storage/{clean}"


class S3Storage(Storage):
    """S3-compatible storage backend (AWS S3, Supabase S3, Cloudflare R2)."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: str = "auto",
        public_base_url: Optional[str] = None,
        client: Optional[object] = None,
    ):
        self.bucket = bucket_name or os.environ.get("S3_BUCKET", "clubdocs")
        self.endpoint_url = endpoint_url or os.environ.get("S3_ENDPOINT_URL")
        self.access_key = access_key_id or os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("S3_ACCESS_KEY")
        self.secret_key = secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("S3_SECRET_KEY")
        self.region = region_name or os.environ.get("AWS_REGION", "auto")
        self.public_base_url = public_base_url or os.environ.get("S3_PUBLIC_URL")

        if client is not None:
            self.s3_client = client
        else:
            try:
                import boto3  # type: ignore
                kwargs: dict[str, object] = {
                    "aws_access_key_id": self.access_key,
                    "aws_secret_access_key": self.secret_key,
                    "region_name": self.region,
                }
                if self.endpoint_url:
                    kwargs["endpoint_url"] = self.endpoint_url
                self.s3_client = boto3.client("s3", **kwargs)
            except Exception as e:
                logger.warning("boto3 client initialization error: %s", e)
                self.s3_client = None

    def save(self, path: str, data: bytes) -> str:
        clean_key = Path(path).as_posix().lstrip("/\\")
        if self.s3_client is None:
            raise RuntimeError("S3 client is not available. Please verify boto3 and S3 credentials.")
        self.s3_client.put_object(Bucket=self.bucket, Key=clean_key, Body=data)
        return clean_key

    def load(self, path: str) -> bytes:
        clean_key = Path(path).as_posix().lstrip("/\\")
        if self.s3_client is None:
            raise RuntimeError("S3 client is not available.")
        resp = self.s3_client.get_object(Bucket=self.bucket, Key=clean_key)
        return resp["Body"].read()

    def delete(self, path: str) -> bool:
        clean_key = Path(path).as_posix().lstrip("/\\")
        if self.s3_client is None:
            return False
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=clean_key)
            return True
        except Exception as e:
            logger.warning("Failed to delete S3 object '%s': %s", clean_key, e)
            return False

    def exists(self, path: str) -> bool:
        clean_key = Path(path).as_posix().lstrip("/\\")
        if self.s3_client is None:
            return False
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=clean_key)
            return True
        except Exception:
            return False

    def public_url(self, path: str) -> str:
        clean_key = Path(path).as_posix().lstrip("/\\")
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{clean_key}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{clean_key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{clean_key}"


_active_storage: Optional[Storage] = None


def get_storage() -> Storage:
    global _active_storage
    if _active_storage is not None:
        return _active_storage

    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    if backend in ("s3", "cloud"):
        _active_storage = S3Storage()
    else:
        _active_storage = LocalDiskStorage()

    return _active_storage


def set_storage(storage: Optional[Storage]) -> None:
    global _active_storage
    _active_storage = storage
