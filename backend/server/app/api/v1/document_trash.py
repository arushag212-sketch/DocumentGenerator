"""Document Trash: delete (recoverable for 30 days), restore, bulk delete, and cancel approved documents.

Approved documents are never deleted: they may already be printed and verified, so they are cancelled
instead and the public verify page says so. Reference numbers are never reused, because numbering
counters only move forward.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import ClubContext, Role, require_club_access
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Document, DocumentReview, DocumentVersion, User

router = APIRouter(prefix="/clubs/{club_id}/documents", tags=["documents"])

TRASH_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _docs(db: Session, club_id: str, *, include_deleted: bool = False) -> ScopedRepository:
    return ScopedRepository(db, Document, club_id=club_id, include_deleted=include_deleted)


def _find(db: Session, ctx: ClubContext, doc_id: str, *, include_deleted: bool = False) -> Document:
    doc = _docs(db, ctx.club.id, include_deleted=include_deleted).get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _why_not_deletable(ctx: ClubContext, doc: Document) -> Optional[str]:
    """None when this user may move the document to the Trash, else the reason."""
    if doc.status == "approved":
        return "Approved documents can't be deleted. Cancel it instead, so the verify page shows it was withdrawn."
    if doc.status == "cancelled":
        return "This document is already cancelled."
    if not (ctx.is_admin or doc.created_by == ctx.user.id):
        return "Only the person who created this document or a club admin can delete it."
    if doc.status == "submitted" and not ctx.is_admin:
        return "This document is waiting for review. Ask a club admin to delete it, or wait for the review."
    return None


def _trash(db: Session, ctx: ClubContext, doc: Document, ip: Optional[str]) -> None:
    doc.deleted_at = _now()
    doc.deleted_by = ctx.user.id
    log_audit(db=db, action="document_deleted", entity_type="document", entity_id=doc.id, club_id=ctx.club.id,
              user_id=ctx.user.id, meta={"title": doc.title, "ref_no": doc.ref_no, "status": doc.status}, ip=ip)


def purge_expired(db: Session, club_id: str) -> int:
    """Remove documents that have been in the Trash for more than 30 days. Cancelled (approved)
    documents are kept for good so their verification code keeps answering. Their files become
    unreferenced and are removed by the storage clean-up job."""
    cutoff = _now() - timedelta(days=TRASH_DAYS)
    docs = _docs(db, club_id, include_deleted=True).all(
        Document.deleted_at.isnot(None), Document.deleted_at < cutoff, Document.status != "cancelled"
    )
    for doc in docs:
        db.query(DocumentReview).filter(DocumentReview.document_id == doc.id).delete(synchronize_session=False)
        db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).delete(synchronize_session=False)
        db.delete(doc)
    return len(docs)


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.get("/trash")
def list_trash(ctx: ClubContext = Depends(require_club_access(Role.VIEWER)), db: Session = Depends(get_db)):
    """Deleted documents (restorable for 30 days) and cancelled approved documents."""
    if purge_expired(db, ctx.club.id):
        db.commit()
    docs = sorted(
        _docs(db, ctx.club.id, include_deleted=True).all(Document.deleted_at.isnot(None)),
        key=lambda d: d.deleted_at,
        reverse=True,
    )
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_({d.deleted_by for d in docs if d.deleted_by}))}
    out = []
    for d in docs:
        cancelled = d.status == "cancelled"
        out.append({
            "id": d.id,
            "title": d.title,
            "ref_no": d.ref_no,
            "status": d.status,
            "deleted_at": d.deleted_at.isoformat() + "Z",
            "deleted_by": names.get(d.deleted_by),
            "cancel_reason": d.cancel_reason,
            "cancelled": cancelled,
            "purge_on": None if cancelled else (d.deleted_at + timedelta(days=TRASH_DAYS)).date().isoformat(),
            "can_restore": (not cancelled) and (ctx.is_admin or d.created_by == ctx.user.id),
        })
    return out


@router.post("/bulk-delete")
def bulk_delete(payload: BulkDeleteRequest, request: Request,
                ctx: ClubContext = Depends(require_club_access(Role.EDITOR)), db: Session = Depends(get_db)):
    """Move several documents to the Trash; ones that can't be deleted are reported, not failed."""
    ip = request.client.host if request.client else None
    docs = {d.id: d for d in _docs(db, ctx.club.id).all(Document.id.in_(payload.ids))}
    deleted, skipped = [], []
    for doc_id in dict.fromkeys(payload.ids):
        doc = docs.get(doc_id)
        if doc is None:
            skipped.append({"id": doc_id, "reason": "Document not found"})
            continue
        reason = _why_not_deletable(ctx, doc)
        if reason:
            skipped.append({"id": doc_id, "title": doc.title, "reason": reason})
            continue
        _trash(db, ctx, doc, ip)
        deleted.append(doc_id)
    db.commit()
    return {"deleted": deleted, "skipped": skipped}


@router.delete("/{doc_id}")
def delete_document(doc_id: str, request: Request,
                    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)), db: Session = Depends(get_db)):
    """Move a document to the Trash (restorable for 30 days)."""
    doc = _find(db, ctx, doc_id)
    reason = _why_not_deletable(ctx, doc)
    if reason:
        status = 403 if "Only the person" in reason else 409
        raise HTTPException(status_code=status, detail=reason)
    _trash(db, ctx, doc, request.client.host if request.client else None)
    db.commit()
    return {"deleted": doc.id, "purge_on": (doc.deleted_at + timedelta(days=TRASH_DAYS)).date().isoformat()}


@router.post("/{doc_id}/restore")
def restore_document(doc_id: str, request: Request,
                     ctx: ClubContext = Depends(require_club_access(Role.EDITOR)), db: Session = Depends(get_db)):
    """Bring a document back from the Trash."""
    doc = _find(db, ctx, doc_id, include_deleted=True)
    if doc.deleted_at is None:
        raise HTTPException(status_code=409, detail="This document isn't in the Trash.")
    if doc.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled documents can't be restored. Create a new one instead.")
    if not (ctx.is_admin or doc.created_by == ctx.user.id):
        raise HTTPException(status_code=403, detail="Only the person who created this document or a club admin can restore it.")
    doc.deleted_at = None
    doc.deleted_by = None
    log_audit(db=db, action="document_restored", entity_type="document", entity_id=doc.id, club_id=ctx.club.id,
              user_id=ctx.user.id, meta={"title": doc.title, "ref_no": doc.ref_no},
              ip=request.client.host if request.client else None)
    db.commit()
    return {"restored": doc.id}


@router.post("/{doc_id}/cancel")
def cancel_document(doc_id: str, payload: CancelRequest, request: Request,
                    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)), db: Session = Depends(get_db)):
    """Withdraw an approved document. It leaves the list, and its verification code now reports
    that the club cancelled it, so a printed copy can't pass as current."""
    doc = _find(db, ctx, doc_id)
    if doc.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved documents are cancelled. Delete other documents instead.")
    doc.status = "cancelled"
    doc.cancel_reason = payload.reason.strip()
    doc.deleted_at = _now()
    doc.deleted_by = ctx.user.id
    log_audit(db=db, action="document_cancelled", entity_type="document", entity_id=doc.id, club_id=ctx.club.id,
              user_id=ctx.user.id, meta={"title": doc.title, "ref_no": doc.ref_no, "reason": doc.cancel_reason},
              ip=request.client.host if request.client else None)
    db.commit()
    return {"cancelled": doc.id}
