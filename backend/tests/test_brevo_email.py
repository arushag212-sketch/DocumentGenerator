"""Brevo HTTPS sender: chosen when BREVO_API_KEY is set, sends the right payload, reports failures."""

from __future__ import annotations

import base64

import pytest

from server.app.core import email as email_module


class _Resp:
    def __init__(self, status: int, text: str = "{}"):
        self.status_code, self.text = status, text


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return _Resp(201)

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def test_brevo_chosen_when_key_set(monkeypatch):
    monkeypatch.setattr(email_module, "_default_sender", None)
    monkeypatch.setenv("BREVO_API_KEY", "xkeysib-test")
    monkeypatch.setenv("EMAIL_FROM", "svnitclubdocs@gmail.com")
    sender = email_module.get_email_sender()
    assert isinstance(sender, email_module.BrevoEmailSender)
    assert sender.from_email == "svnitclubdocs@gmail.com"
    assert email_module.email_delivery_configured()
    monkeypatch.setattr(email_module, "_default_sender", None)


def test_document_payload(captured):
    sender = email_module.BrevoEmailSender("xkeysib-test", "svnitclubdocs@gmail.com")
    sender.send_document(["hod@example.com"], "Permission Letter", "Please find attached.",
                         [("letter.pdf", b"%PDF-1.7", "application/pdf")], reply_to="student@svnit.ac.in")
    call = captured[-1]
    assert call["url"] == email_module.BrevoEmailSender.API_URL
    assert call["headers"]["api-key"] == "xkeysib-test"
    body = call["json"]
    assert body["sender"] == {"name": "SVNIT ClubDocs", "email": "svnitclubdocs@gmail.com"}
    assert body["to"] == [{"email": "hod@example.com"}]
    assert body["replyTo"] == {"email": "student@svnit.ac.in"}
    assert body["attachment"][0]["name"] == "letter.pdf"
    assert base64.b64decode(body["attachment"][0]["content"]) == b"%PDF-1.7"


def test_password_reset_uses_https_too(captured):
    email_module.BrevoEmailSender("k", "svnitclubdocs@gmail.com").send_password_reset("u@svnit.ac.in", "tok123")
    assert "reset_token=tok123" in captured[-1]["json"]["textContent"]


def test_brevo_error_is_raised(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(400, '{"message":"sender not valid"}'))
    with pytest.raises(RuntimeError, match="sender not valid"):
        email_module.BrevoEmailSender("k", "x@gmail.com").send_document(["a@b.com"], "s", "b", [])
