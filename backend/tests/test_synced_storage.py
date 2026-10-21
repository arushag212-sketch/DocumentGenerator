"""Local working copy mirrored to S3-compatible storage (used on hosts whose disk is wiped on restart)."""

from __future__ import annotations

import io
import uuid

import pytest

from server.app.core import storage as storage_module
from server.app.core.database import SessionLocal
from server.app.core.storage import S3Storage, SyncedDiskStorage


class FakeS3Client:
    """Minimal in-memory stand-in for the boto3 S3 client methods the app uses."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


@pytest.fixture
def synced(tmp_path):
    client = FakeS3Client()
    store = SyncedDiskStorage(base_dir=tmp_path / "storage", remote=S3Storage(bucket_name="test", client=client))
    previous = storage_module._active_storage
    storage_module.set_storage(store)
    try:
        yield store, client
    finally:
        storage_module.set_storage(previous)


def test_save_uploads_and_missing_local_copy_is_restored(synced):
    store, client = synced
    key = store.save("templates/letter_v1.docx", b"docx-bytes")
    assert client.objects["templates/letter_v1.docx"] == b"docx-bytes"

    # Simulate a restart that wiped the local disk
    store.local_path(key).unlink()
    assert store.local_path(key).read_bytes() == b"docx-bytes"
    assert store.load(key) == b"docx-bytes"


def test_caches_stay_local(synced):
    store, client = synced
    store.save("cache/previews/p1.jpg", b"jpg")
    assert client.objects == {}


def test_delete_removes_both_copies(synced):
    store, client = synced
    key = store.save("documents/d1/v1/a.pdf", b"pdf")
    assert store.delete(key)
    assert key not in client.objects
    assert not store.local_path(key).exists()


def test_commit_uploads_files_written_directly_to_disk(synced):
    """Most render paths write files themselves and only store the key; the commit hook uploads them."""
    from server.app.models import Asset

    store, client = synced
    rel_key = f"assets/test/{uuid.uuid4().hex}.png"
    target = store.local_path(rel_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"png")

    db = SessionLocal()
    try:
        asset = Asset(kind="logo", filename="logo.png", size=3, storage_key=str(target), mime="image/png", sha256=uuid.uuid4().hex)
        db.add(asset)
        db.commit()
        assert client.objects.get(rel_key) == b"png"
        db.delete(asset)
        db.commit()
    finally:
        db.close()


def test_rollback_does_not_upload(synced):
    from server.app.models import Asset

    store, client = synced
    rel_key = f"assets/test/{uuid.uuid4().hex}.png"
    target = store.local_path(rel_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"png")

    db = SessionLocal()
    try:
        db.add(Asset(kind="logo", filename="logo.png", size=3, storage_key=rel_key, mime="image/png", sha256=uuid.uuid4().hex))
        db.flush()
        db.rollback()
    finally:
        db.close()
    assert rel_key not in client.objects
