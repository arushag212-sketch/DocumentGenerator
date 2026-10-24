"""Notifications: an in-app notice for each person concerned, plus a best-effort email.

Email never blocks the action that triggered it: if sending fails, the in-app notice still exists.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from server.app.models import Membership, Notification, User

logger = logging.getLogger("clubdocs.notifications")


def club_admin_ids(db: Session, club_id: str, exclude: Optional[str] = None) -> list[str]:
    """Active owners and admins of a club (the people who review and approve)."""
    rows = (
        db.query(Membership.user_id)
        .filter(Membership.club_id == club_id, Membership.status == "active", Membership.role.in_(("owner", "admin")))
        .all()
    )
    return [r[0] for r in rows if r[0] != exclude]


def notify(
    db: Session,
    user_ids: Iterable[str],
    *,
    club_id: Optional[str],
    kind: str,
    title: str,
    body: str = "",
    link: Optional[str] = None,
    email: bool = True,
) -> int:
    """Create one notification per user (duplicates removed) and email them. Returns how many were created."""
    ids = list(dict.fromkeys(u for u in user_ids if u))
    if not ids:
        return 0
    for uid in ids:
        db.add(Notification(user_id=uid, club_id=club_id, kind=kind, title=title[:255], body=(body or "")[:1000], link=link))
    db.flush()
    if email:
        _email(db, ids, title, body, link)
    return len(ids)


def _email(db: Session, user_ids: list[str], title: str, body: str, link: Optional[str]) -> None:
    from server.app.core.email import email_delivery_configured, get_email_sender

    if not email_delivery_configured():
        return
    sender = get_email_sender()
    base = os.environ.get("APP_BASE_URL", "http://localhost:5173").rstrip("/")
    text = f"{body}\n\n" if body else ""
    if link:
        text += f"Open it in ClubDocs: {base}{link}\n\n"
    text += "You are getting this because of your role in a club on SVNIT ClubDocs."
    for user in db.query(User).filter(User.id.in_(user_ids)).all():
        try:
            sender.send_notification(user.email, f"{title} - SVNIT ClubDocs", text)
        except Exception as exc:  # the in-app notice is enough if email fails
            logger.warning("Notification email to %s failed: %s", user.email, exc)
