"""Demo club: every new account joins it as an editor so people can try the app straight away."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.config import settings
from server.app.models import Club, Membership, User

DEMO_POSITION = "Member"


def demo_club(db: Session) -> Optional[Club]:
    slug = settings.DEMO_CLUB_SLUG
    if not slug:
        return None
    return db.query(Club).filter(Club.slug == slug).first()


def join_demo_club(db: Session, user: User, ip: Optional[str] = None) -> bool:
    """Add a new account to the demo club as an editor. Returns True if a membership was added."""
    club = demo_club(db)
    if club is None:
        return False
    if db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == user.id).first():
        return False
    db.add(Membership(user_id=user.id, club_id=club.id, role="editor", position=DEMO_POSITION, status="active"))
    db.flush()
    log_audit(
        db=db,
        action="demo_club_joined",
        entity_type="club",
        entity_id=club.id,
        club_id=club.id,
        user_id=user.id,
        meta={"email": user.email, "role": "editor"},
        ip=ip,
    )
    return True
