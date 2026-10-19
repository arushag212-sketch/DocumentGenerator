"""Audit logging helper for security tracking and compliance."""

from __future__ import annotations

from typing import Any, Optional
from sqlalchemy.orm import Session
from server.app.models import AuditLog


def log_audit(
    db: Session,
    action: str,
    entity_type: str,
    user_id: Optional[str] = None,
    club_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    ip: Optional[str] = None,
    *,
    commit: bool = False,
) -> AuditLog:
    """Record an audit trail event in the current transaction.

    Audit entries must commit with the operation they describe.  Historically
    this helper committed immediately, which left orphan audit rows when a
    subsequent write failed and also committed unrelated pending changes.  It
    now only flushes by default; isolated callers may explicitly request a
    commit when they truly own the transaction.
    """
    audit_entry = AuditLog(
        club_id=club_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta=meta or {},
        ip=ip,
    )
    db.add(audit_entry)
    db.flush()
    if commit:
        db.commit()
    db.refresh(audit_entry)
    return audit_entry
