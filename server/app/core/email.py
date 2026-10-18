"""Email sender interface, SMTP implementation, and development console fallback."""

from __future__ import annotations

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("clubdocs.email")


class EmailSender(ABC):
    """Abstract interface for sending transactional emails."""

    @abstractmethod
    def send_activation(self, to_email: str, club_name: str, activation_link: str) -> None:
        """Send club / account activation link."""
        pass

    @abstractmethod
    def send_invitation(self, to_email: str, club_name: str, invite_link: str) -> None:
        """Send member invitation link."""
        pass

    @abstractmethod
    def send_password_reset(self, to_email: str, reset_token: str) -> None:
        """Send password reset token / link."""
        pass


class ConsoleEmailSender(EmailSender):
    """Development and test email sender that prints visible links to logger/console."""

    def __init__(self):
        self.sent_messages: list[dict[str, str]] = []

    def send_activation(self, to_email: str, club_name: str, activation_link: str) -> None:
        msg = {
            "type": "activation",
            "to_email": to_email,
            "club_name": club_name,
            "link": activation_link,
        }
        self.sent_messages.append(msg)
        logger.info(
            "\n"
            "==================== TRANSACTIONAL EMAIL [CONSOLE] ====================\n"
            f"[ACTIVATION LINK] To: {to_email} | Club: {club_name}\n"
            f"Link: {activation_link}\n"
            "=======================================================================\n"
        )

    def send_invitation(self, to_email: str, club_name: str, invite_link: str) -> None:
        msg = {
            "type": "invitation",
            "to_email": to_email,
            "club_name": club_name,
            "link": invite_link,
        }
        self.sent_messages.append(msg)
        logger.info(
            "\n"
            "==================== TRANSACTIONAL EMAIL [CONSOLE] ====================\n"
            f"[INVITATION LINK] To: {to_email} | Club: {club_name}\n"
            f"Link: {invite_link}\n"
            "=======================================================================\n"
        )

    def send_password_reset(self, to_email: str, reset_token: str) -> None:
        reset_link = f"/reset-password?token={reset_token}"
        msg = {
            "type": "password_reset",
            "to_email": to_email,
            "token": reset_token,
            "link": reset_link,
        }
        self.sent_messages.append(msg)
        logger.info(
            "\n"
            "==================== TRANSACTIONAL EMAIL [CONSOLE] ====================\n"
            f"[PASSWORD RESET LINK] To: {to_email}\n"
            f"Reset Link: {reset_link}\n"
            f"Token (expires in 30m): {reset_token}\n"
            "=======================================================================\n"
        )


# Backward-compatible alias
LoggingEmailSender = ConsoleEmailSender


class SMTPEmailSender(EmailSender):
    """Production SMTP email sender using Python's standard smtplib."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: str = "noreply@svnit.ac.in",
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def _send(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.sendmail(self.from_email, [to_email], msg.as_string())

    def send_activation(self, to_email: str, club_name: str, activation_link: str) -> None:
        subject = f"Activate your account for {club_name} - SVNIT ClubDocs"
        text = (
            f"Hello,\n\n"
            f"Please activate your account for {club_name} by visiting:\n"
            f"{activation_link}\n\n"
            f"Regards,\nSVNIT ClubDocs"
        )
        self._send(to_email, subject, text)

    def send_invitation(self, to_email: str, club_name: str, invite_link: str) -> None:
        subject = f"You are invited to join {club_name} on SVNIT ClubDocs"
        text = (
            f"Hello,\n\n"
            f"You have been invited to join {club_name}. Accept your invitation here:\n"
            f"{invite_link}\n\n"
            f"Regards,\nSVNIT ClubDocs"
        )
        self._send(to_email, subject, text)

    def send_password_reset(self, to_email: str, reset_token: str) -> None:
        subject = "Reset your ClubDocs SVNIT account password"
        reset_link = f"/reset-password?token={reset_token}"
        text = (
            f"Hello,\n\n"
            f"You requested a password reset. Use the link below (valid for 30 minutes):\n"
            f"{reset_link}\n\n"
            f"Token: {reset_token}\n\n"
            f"Regards,\nSVNIT ClubDocs"
        )
        self._send(to_email, subject, text)


_default_sender: Optional[EmailSender] = None


def get_email_sender() -> EmailSender:
    global _default_sender
    if _default_sender is not None:
        return _default_sender

    smtp_host = os.environ.get("SMTP_HOST")
    if smtp_host and smtp_host.strip():
        port = int(os.environ.get("SMTP_PORT", "587"))
        user = os.environ.get("SMTP_USER") or os.environ.get("SMTP_USERNAME")
        password = os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS")
        from_email = os.environ.get("SMTP_FROM", "noreply@svnit.ac.in")
        use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
        _default_sender = SMTPEmailSender(
            host=smtp_host.strip(),
            port=port,
            username=user,
            password=password,
            from_email=from_email,
            use_tls=use_tls,
        )
    else:
        _default_sender = ConsoleEmailSender()

    return _default_sender


def set_email_sender(sender: Optional[EmailSender]) -> None:
    global _default_sender
    _default_sender = sender
