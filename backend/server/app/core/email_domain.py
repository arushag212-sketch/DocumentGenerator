"""Email domain validation policy for SVNIT ClubDocs."""

from __future__ import annotations

from typing import Optional
from server.app.core.config import settings

EMAIL_DOMAIN_REJECTION_MESSAGE = "Please sign in with your SVNIT email (@svnit.ac.in)."
EMAIL_DOMAIN_ERROR_CODE = "EMAIL_DOMAIN_NOT_ALLOWED"


def is_allowed_email(email: Optional[str]) -> bool:
    """Validate whether an email belongs to the allowed institution domain.

    - Lowercase and strip the email, take the part after the last '@'.
    - Allowed if domain == ALLOWED_EMAIL_DOMAIN or ends with '.' + ALLOWED_EMAIL_DOMAIN.
    - If ALLOWED_EMAIL_DOMAIN is empty and ENVIRONMENT is dev/test, allow any domain.
    """
    if not email:
        return False

    clean_email = email.strip().lower()
    if "@" not in clean_email:
        return False

    domain = clean_email.rsplit("@", 1)[1].strip()
    if not domain:
        return False

    allowed = (settings.ALLOWED_EMAIL_DOMAIN or "").strip().lower()
    if not allowed:
        if settings.ENVIRONMENT in ("development", "test", "dev"):
            return True
        return False

    return domain == allowed or domain.endswith("." + allowed)
