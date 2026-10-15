"""Email sender interface and development logger."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("clubdocs.email")


class EmailSender(ABC):
    """Abstract interface for sending transactional emails."""

    @abstractmethod
    def send_password_reset(self, to_email: str, reset_token: str) -> None:
        pass


class LoggingEmailSender(EmailSender):
    """Dev and test email sender that logs password reset links to server logs."""

    def __init__(self):
        self.sent_messages: list[dict[str, str]] = []

    def send_password_reset(self, to_email: str, reset_token: str) -> None:
        self.sent_messages.append({"to_email": to_email, "token": reset_token})
        reset_link = f"/reset-password?token={reset_token}"
        logger.info(
            f"\n"
            f"==================== TRANSACTIONAL EMAIL [DEV] ====================\n"
            f"To: {to_email}\n"
            f"Subject: Reset your ClubDocs SVNIT account password\n"
            f"Reset Link: {reset_link}\n"
            f"Token (expires in 30m): {reset_token}\n"
            f"===================================================================\n"
        )


_default_sender: Optional[EmailSender] = None


def get_email_sender() -> EmailSender:
    global _default_sender
    if _default_sender is None:
        _default_sender = LoggingEmailSender()
    return _default_sender


def set_email_sender(sender: EmailSender) -> None:
    global _default_sender
    _default_sender = sender
