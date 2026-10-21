"""Unit tests for Phase 5: Storage and Email abstractions."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from server.app.core.email import ConsoleEmailSender, SMTPEmailSender, get_email_sender, set_email_sender
from server.app.core.storage import LocalDiskStorage, S3Storage, SyncedDiskStorage, get_storage, set_storage


def test_console_email_sender():
    sender = ConsoleEmailSender()
    sender.send_activation("student@svnit.ac.in", "ACM", "https://clubdocs.svnit.ac.in/activate?token=123")
    sender.send_invitation("member@svnit.ac.in", "ACM", "https://clubdocs.svnit.ac.in/join?token=456")
    sender.send_password_reset("owner@svnit.ac.in", "reset789")

    assert len(sender.sent_messages) == 3
    assert sender.sent_messages[0]["type"] == "activation"
    assert sender.sent_messages[0]["to_email"] == "student@svnit.ac.in"
    assert "activate?token=123" in sender.sent_messages[0]["link"]

    assert sender.sent_messages[1]["type"] == "invitation"
    assert sender.sent_messages[2]["type"] == "password_reset"
    assert sender.sent_messages[2]["token"] == "reset789"


@patch("smtplib.SMTP")
def test_smtp_email_sender(mock_smtp_class):
    mock_smtp_instance = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance

    sender = SMTPEmailSender(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="secretpassword",
        from_email="noreply@svnit.ac.in",
        use_tls=True,
    )

    sender.send_activation("student@svnit.ac.in", "ACM", "https://test.link/act")
    assert mock_smtp_instance.starttls.called
    assert mock_smtp_instance.login.called
    assert mock_smtp_instance.sendmail.called


def test_email_sender_factory_env(monkeypatch):
    set_email_sender(None)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    default_s = get_email_sender()
    assert isinstance(default_s, ConsoleEmailSender)

    set_email_sender(None)
    monkeypatch.setenv("SMTP_HOST", "mail.svnit.ac.in")
    smtp_s = get_email_sender()
    assert isinstance(smtp_s, SMTPEmailSender)
    set_email_sender(None)


def test_local_disk_storage(tmp_path):
    storage = LocalDiskStorage(base_dir=tmp_path)

    test_bytes = b"Hello SVNIT ClubDocs Document Generator!"
    saved_path = storage.save("docs/test_doc.txt", test_bytes)
    assert storage.exists(saved_path)

    loaded_bytes = storage.load(saved_path)
    assert loaded_bytes == test_bytes

    url = storage.public_url(saved_path)
    assert url == "/storage/docs/test_doc.txt"

    assert storage.delete(saved_path) is True
    assert not storage.exists(saved_path)

    with pytest.raises(ValueError, match="path traversal"):
        storage.save("../../escape.txt", b"evil")


def test_s3_storage_mock():
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"s3_content")}
    mock_client.head_object.return_value = {"ContentLength": 10}

    s3 = S3Storage(
        bucket_name="my-bucket",
        endpoint_url="https://s3.example.com",
        client=mock_client,
    )

    saved = s3.save("folder/doc.pdf", b"test_pdf")
    assert saved == "folder/doc.pdf"
    assert mock_client.put_object.called

    assert s3.load("folder/doc.pdf") == b"s3_content"
    assert s3.exists("folder/doc.pdf") is True
    assert s3.delete("folder/doc.pdf") is True
    assert s3.public_url("folder/doc.pdf") == "https://s3.example.com/my-bucket/folder/doc.pdf"


def test_storage_factory_env(monkeypatch, tmp_path):
    set_storage(None)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    s_local = get_storage()
    assert isinstance(s_local, LocalDiskStorage)

    set_storage(None)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    s_s3 = get_storage()
    # S3 mirrors a local working copy, because rendering needs files on disk
    assert isinstance(s_s3, SyncedDiskStorage)
    assert isinstance(s_s3.remote, S3Storage)
    set_storage(None)


def test_check_database_schema_passes():
    from scripts.check_db import check_database_schema
    assert check_database_schema() is True


def test_alembic_offline_postgresql_migration():
    import subprocess
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/clubdocs"
    res = subprocess.run(["alembic", "upgrade", "head", "--sql"], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"Alembic migration failed: {res.stderr}"
    assert "ALTER TABLE documents ADD CONSTRAINT uq_document_club_ref_no UNIQUE" in res.stdout



def test_absolute_keys_from_an_old_location_map_into_the_current_root(tmp_path):
    """Keys saved as full paths keep working after the storage folder moves; escapes are still refused."""
    store = LocalDiskStorage(base_dir=tmp_path / "storage")
    store.save("documents/d1/v1/a.pdf", b"pdf")
    old_key = r"C:\Users\someone\Old\DocumentGenerator\storage\documents\d1\v1\a.pdf"
    assert store.load(old_key) == b"pdf"
    with pytest.raises(ValueError):
        store.local_path(r"C:\Windows\System32\drivers\etc\hosts")
