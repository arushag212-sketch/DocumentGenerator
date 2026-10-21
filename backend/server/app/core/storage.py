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
        self.base_dir = Path(base_dir or os.environ.get("STORAGE_LOCAL_ROOT", "storage")).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def normalize_key(self, path: str) -> str:
        """Return a storage-relative key and accept keys from older releases.

        Older database rows stored ``storage/foo`` (and occasionally an
        absolute path), while the storage abstraction returns ``foo``.  Keep
        reads backward-compatible but write only canonical relative keys.
        """

        raw = str(path or "")
        candidate = Path(raw)
        if candidate.is_absolute():
            try:
                return candidate.resolve().relative_to(self.base_dir).as_posix()
            except ValueError:
                # Absolute key from before the storage folder moved (another checkout path or
                # machine): keep the part after its own storage folder. _resolve_safe_path
                # still confines the result to base_dir. Anything else is rejected there.
                parts = candidate.parts
                names = [p.lower() for p in parts]
                folder = self.base_dir.name.lower()
                if folder in names:
                    idx = len(names) - 1 - names[::-1].index(folder)
                    rest = parts[idx + 1:]
                    if rest:
                        return Path(*rest).as_posix()
                return raw
        clean = candidate.as_posix().lstrip("/\\")
        base_name = self.base_dir.name
        if clean == base_name:
            return ""
        if clean.startswith(f"{base_name}/"):
            clean = clean[len(base_name) + 1 :]
        # The default database used the literal ``storage/`` prefix.
        if clean.startswith("storage/"):
            clean = clean[len("storage/") :]
        return clean

    def local_path(self, path: str) -> Path:
        """Resolve a key to a local path for response/renderer integrations."""

        return self._resolve_safe_path(path)

    def _resolve_safe_path(self, path: str) -> Path:
        """Ensure no directory traversal escaping base_dir."""
        clean = self.normalize_key(path)
        resolved = (self.base_dir / clean).resolve()
        if resolved != self.base_dir and self.base_dir not in resolved.parents:
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
        clean = self.normalize_key(path)
        return f"/storage/{clean}"


class S3Storage(Storage):
    """S3-compatible storage backend (AWS S3, Supabase S3, Cloudflare R2)."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
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
                    from botocore.config import Config  # type: ignore

                    kwargs["endpoint_url"] = self.endpoint_url
                    # Supabase Storage and most S3-compatible services need path-style URLs
                    kwargs["config"] = Config(s3={"addressing_style": os.environ.get("S3_ADDRESSING_STYLE", "path")})
                self.s3_client = boto3.client("s3", **kwargs)
            except Exception as e:
                logger.warning("boto3 client initialization error: %s", e)
                self.s3_client = None

    @staticmethod
    def _clean_key(path: str) -> str:
        """Normalize legacy local-style keys and reject traversal keys."""
        clean = Path(str(path or "")).as_posix().lstrip("/\\")
        if clean.startswith("storage/"):
            clean = clean[len("storage/") :]
        if not clean or any(part in ("", ".", "..") for part in clean.split("/")):
            raise ValueError(f"Invalid storage key '{path}'")
        return clean

    def save(self, path: str, data: bytes) -> str:
        clean_key = self._clean_key(path)
        if self.s3_client is None:
            raise RuntimeError("S3 client is not available. Please verify boto3 and S3 credentials.")
        self.s3_client.put_object(Bucket=self.bucket, Key=clean_key, Body=data)
        return clean_key

    def load(self, path: str) -> bytes:
        clean_key = self._clean_key(path)
        if self.s3_client is None:
            raise RuntimeError("S3 client is not available.")
        resp = self.s3_client.get_object(Bucket=self.bucket, Key=clean_key)
        return resp["Body"].read()

    def delete(self, path: str) -> bool:
        clean_key = self._clean_key(path)
        if self.s3_client is None:
            return False
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=clean_key)
            return True
        except Exception as e:
            logger.warning("Failed to delete S3 object '%s': %s", clean_key, e)
            return False

    def exists(self, path: str) -> bool:
        clean_key = self._clean_key(path)
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
        clean_prefix = self._clean_key(prefix)
        clean_key = f"{clean_prefix}/sha256_{sha}.{clean_ext}"
        if not self.exists(clean_key):
            self.save(clean_key, data)
        return clean_key, sha

    def cleanup_expired(self, subfolder: str, max_age_seconds: float) -> int:
        if self.s3_client is None:
            return 0
        clean_prefix = self._clean_key(subfolder)
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
        clean_key = self._clean_key(path)
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{clean_key}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{clean_key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{clean_key}"


class SyncedDiskStorage(LocalDiskStorage):
    """Local disk as a working copy, mirrored to S3-compatible storage (e.g. Supabase Storage).

    Rendering needs real files on disk, so all code keeps using local paths. Files that
    records point at are uploaded after each commit (see ``register_persistence_hooks``), and
    a missing local copy (for example after a free host restarts with an empty disk) is
    downloaded the first time it is needed. Caches and thumbnails stay local and are rebuilt.
    """

    PERSISTENT_PREFIXES = ("assets/", "templates/", "documents/", "thumbnails/")

    def __init__(self, base_dir: Optional[Path | str] = None, remote: Optional[S3Storage] = None):
        super().__init__(base_dir)
        self.remote = remote or S3Storage()

    def _is_persistent(self, key: str) -> bool:
        return key.startswith(self.PERSISTENT_PREFIXES)

    def _fetch(self, key: str, target: Path) -> None:
        """Download a persistent file that is missing locally; quietly skip if the bucket lacks it too."""
        if target.exists() or not key or not self._is_persistent(key):
            return
        try:
            data = self.remote.load(key)
        except Exception:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)

    def local_path(self, path: str) -> Path:
        target = self._resolve_safe_path(path)
        self._fetch(self.normalize_key(path), target)
        return target

    def push(self, path: str) -> bool:
        """Upload one local file to the bucket. Returns False if it could not be uploaded."""
        key = self.normalize_key(path)
        if not key or not self._is_persistent(key):
            return False
        try:
            target = self._resolve_safe_path(path)
        except ValueError:
            return False
        if not target.is_file():
            return False
        try:
            self.remote.save(key, target.read_bytes())
            return True
        except Exception as e:
            logger.warning("Upload to remote storage failed for '%s': %s", key, e)
            return False

    def save(self, path: str, data: bytes) -> str:
        key = super().save(path, data)
        self.push(key)
        return key

    def save_content_addressed(self, prefix: str, data: bytes, ext: str = "docx") -> Tuple[str, str]:
        key, sha = super().save_content_addressed(prefix, data, ext)
        self.push(key)
        return key, sha

    def load(self, path: str) -> bytes:
        self.local_path(path)  # brings the file back from the bucket if needed
        return super().load(path)

    def exists(self, path: str) -> bool:
        try:
            return self.local_path(path).is_file()
        except Exception:
            return False

    def delete(self, path: str) -> bool:
        ok = super().delete(path)
        key = self.normalize_key(path)
        if key and self._is_persistent(key):
            ok = self.remote.delete(key) and ok
        return ok


_active_storage: Optional[Storage] = None


def get_storage() -> Storage:
    global _active_storage
    if _active_storage is not None:
        return _active_storage

    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    if backend in ("s3", "cloud", "supabase"):
        # Rendering works on local files, so S3 is used as a mirror of the local working copy
        _active_storage = SyncedDiskStorage()
    elif backend in ("local", "filesystem", "disk"):
        _active_storage = LocalDiskStorage()
    else:
        raise RuntimeError(
            f"Unsupported STORAGE_BACKEND={backend!r}; choose 'local' or 's3'."
        )

    return _active_storage


def register_persistence_hooks(session_factory) -> None:
    """Upload the files that saved records point at, once their transaction commits.

    About a dozen code paths write templates, documents and logos straight to disk; hooking
    the session covers all of them. With plain local storage this does nothing.
    """
    from sqlalchemy import event

    def _collect(session, flush_context):
        if not isinstance(get_storage(), SyncedDiskStorage):
            return
        from server.app.models import Asset, DocumentVersion, TemplateVersion

        pending = session.info.setdefault("storage_push", set())
        for obj in list(session.new) + list(session.dirty):
            if isinstance(obj, Asset):
                keys = (obj.storage_key,)
            elif isinstance(obj, TemplateVersion):
                keys = (obj.docx_storage_key,)
            elif isinstance(obj, DocumentVersion):
                keys = (obj.docx_key, obj.pdf_key)
            else:
                continue
            pending.update(k for k in keys if k)

    def _push(session):
        keys = session.info.pop("storage_push", None)
        active = get_storage()
        if not keys or not isinstance(active, SyncedDiskStorage):
            return
        for key in keys:
            active.push(key)

    def _discard(session):
        session.info.pop("storage_push", None)

    event.listen(session_factory, "after_flush", _collect)
    event.listen(session_factory, "after_commit", _push)
    event.listen(session_factory, "after_rollback", _discard)


def set_storage(storage_instance: Optional[Storage]) -> None:
    global _active_storage
    _active_storage = storage_instance


class StorageProxy:
    def __getattr__(self, name: str):
        return getattr(get_storage(), name)


storage = StorageProxy()


def require_local_storage() -> LocalDiskStorage:
    """Return the local backend or fail explicitly for local-only workflows."""

    active = get_storage()
    if not isinstance(active, LocalDiskStorage):
        raise RuntimeError(
            "This document-rendering operation requires STORAGE_BACKEND=local. "
            "Configure a local storage root or use an S3-aware worker before enabling S3."
        )
    return active
