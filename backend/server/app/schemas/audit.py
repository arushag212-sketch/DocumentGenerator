"""Pydantic schema for audit log entries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    club_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    meta: dict[str, Any] = {}
    ip: Optional[str] = None
    created_at: datetime
    # Who did it (filled in by the API; empty for system actions)
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
