"""The signed-in user's notifications (the bell): list, mark one read, mark all read."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.permissions import get_current_user
from server.app.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _out(n: Notification) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "club_id": n.club_id,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat() + "Z",
    }


@router.get("")
def list_notifications(
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    unread = q.filter(Notification.read_at.is_(None)).count()
    items = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return {"unread": unread, "items": [_out(n) for n in items]}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: _now()}, synchronize_session=False)
    )
    db.commit()
    return {"marked": count}


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.read_at is None:
        n.read_at = _now()
        db.commit()
    return _out(n)
