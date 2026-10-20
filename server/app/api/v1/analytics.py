"""Club usage dashboard: what the club produces and how much manual work it saved."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.permissions import ClubContext, Role, require_club_access
from server.app.models import AIRequest, Document, DocumentReview, Event, Membership, Template

router = APIRouter(prefix="/clubs/{club_id}/analytics", tags=["analytics"])

# Conservative estimate of hand-preparing one official document (typing, formatting,
# numbering, checking) versus generating it.
MINUTES_SAVED_PER_DOCUMENT = 25


@router.get("")
def club_analytics(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    club_id = ctx.club.id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    docs = db.query(Document.id, Document.template_id, Document.status, Document.created_at).filter(
        Document.club_id == club_id
    ).all()
    template_names = dict(
        db.query(Template.id, Template.name).filter(Template.id.in_({d.template_id for d in docs})).all()
    ) if docs else {}

    by_template = Counter(template_names.get(d.template_id, "Other") for d in docs)
    by_status = Counter(d.status for d in docs)

    months = []
    for i in range(5, -1, -1):
        # Calendar arithmetic: step back i whole months (31-day steps skip short months)
        y, m = divmod(month_start.year * 12 + month_start.month - 1 - i, 12)
        start = month_start.replace(year=y, month=m + 1)
        end = (start + timedelta(days=32)).replace(day=1)
        months.append({
            "month": start.strftime("%b %Y"),
            "documents": sum(1 for d in docs if start <= d.created_at < end),
        })

    approvals = db.query(func.count(DocumentReview.id)).filter(
        DocumentReview.club_id == club_id, DocumentReview.action == "approved"
    ).scalar() or 0
    ai_requests = db.query(func.count(AIRequest.id)).filter(AIRequest.club_id == club_id).scalar() or 0
    events = db.query(func.count(Event.id)).filter(Event.club_id == club_id).scalar() or 0
    members = db.query(func.count(Membership.id)).filter(
        Membership.club_id == club_id, Membership.status == "active"
    ).scalar() or 0
    club_templates = db.query(func.count(Template.id)).filter(
        Template.club_id == club_id, Template.status == "published"
    ).scalar() or 0

    return {
        "documents_total": len(docs),
        "documents_this_month": sum(1 for d in docs if d.created_at >= month_start),
        "events_total": events,
        "members": members,
        "club_templates": club_templates,
        "approvals": approvals,
        "awaiting_review": by_status.get("submitted", 0),
        "ai_requests": ai_requests,
        "hours_saved": round(len(docs) * MINUTES_SAVED_PER_DOCUMENT / 60, 1),
        "by_month": months,
        "by_template": [{"name": n, "count": c} for n, c in by_template.most_common(8)],
        "by_status": dict(by_status),
    }
