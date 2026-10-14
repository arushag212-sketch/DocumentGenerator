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
) -> AuditLog:
    """Record an audit trail event in the audit_log table."""
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
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
