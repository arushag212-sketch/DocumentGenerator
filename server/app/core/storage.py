"""Cloud and local disk storage abstraction for documents, batches, and assets."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import hashlib
import time
from typing import Optional, Tuple

logger = logging.getLogger("clubdocs.storage")

PREVIEW_TTL_DAYS = int(os.environ.get("PREVIEW_TTL_DAYS", "7"))
BATCH_TTL_HOURS = int(os.environ.get("BATCH_TTL_HOURS", "24"))
KEEP_VERSION_FILES = int(os.environ.get("KEEP_VERSION_FILES", "3"))
STORAGE_GC_ENABLED = os.environ.get("STORAGE_GC_ENABLED", "true").lower() in ("true", "1", "yes")


class Storage(ABC):
    """Abstract interface for file persistence."""

    @abstractmethod
    def save(self, path: str, data: bytes) -> str:
        """Save raw bytes to the given relative path and return its canonical identifier/path."""
        pass

    @abstractmethod
    def save_content_addressed(self, prefix: str, data: bytes, ext: str = "docx") -> Tuple[str, str]:
        """Save data addressed by SHA-256 to {prefix}/sha256_{hash}.{ext}. Returns (relative_path, sha256)."""
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

    @abstractmethod
    def cleanup_expired(self, subfolder: str, max_age_seconds: float) -> int:
        """Delete files older than max_age_seconds in subfolder. Returns freed bytes."""
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

    def save_content_addressed(self, prefix: str, data: bytes, ext: str = "docx") -> Tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        clean_ext = ext.lstrip(".")
        clean_prefix = Path(prefix).as_posix().lstrip("/\\")
        rel_path = f"{clean_prefix}/sha256_{sha}.{clean_ext}"
        target = self._resolve_safe_path(rel_path)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return Path(target.relative_to(self.base_dir)).as_posix(), sha

    def cleanup_expired(self, subfolder: str, max_age_seconds: float) -> int:
        target_dir = self._resolve_safe_path(subfolder)
        if not target_dir.exists():
            return 0
        cutoff = time.time() - max_age_seconds
        freed_bytes = 0
        for root, dirs, files in os.walk(target_dir, topdown=False):
            for f in files:
                fp = Path(root) / f
                try:
                    st = fp.stat()
                    if st.st_mtime < cutoff:
                        freed_bytes += st.st_size
                        fp.unlink()
                except Exception as e:
                    logger.warning("Error removing expired file %s: %s", fp, e)
            for d in dirs:
                dp = Path(root) / d
                try:
                    if not any(dp.iterdir()):
                        dp.rmdir()
                except Exception:
                    pass
        return freed_bytes

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

    def save_content_addressed(self, prefix: str, data: bytes, ext: str = "docx") -> Tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        clean_ext = ext.lstrip(".")
        clean_prefix = Path(prefix).as_posix().lstrip("/\\")
        clean_key = f"{clean_prefix}/sha256_{sha}.{clean_ext}"
        if not self.exists(clean_key):
            self.save(clean_key, data)
        return clean_key, sha

    def cleanup_expired(self, subfolder: str, max_age_seconds: float) -> int:
        if self.s3_client is None:
            return 0
        clean_prefix = Path(subfolder).as_posix().lstrip("/\\")
        cutoff = time.time() - max_age_seconds
        freed = 0
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=clean_prefix):
                for obj in page.get("Contents", []):
                    last_mod = obj["LastModified"].timestamp()
                    if last_mod < cutoff:
                        freed += obj["Size"]
                        self.s3_client.delete_object(Bucket=self.bucket, Key=obj["Key"])
        except Exception as e:
            logger.warning("Failed to cleanup expired S3 objects: %s", e)
        return freed

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


def set_storage(storage_instance: Optional[Storage]) -> None:
    global _active_storage
    _active_storage = storage_instance


class StorageProxy:
    def __getattr__(self, name: str):
        return getattr(get_storage(), name)


storage = StorageProxy()
