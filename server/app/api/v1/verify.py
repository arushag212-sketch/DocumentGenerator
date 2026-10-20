"""Public verification of approved documents (no login needed).

An approved PDF carries a verification code. Anyone can look the code up to see what was
approved, by whom and when, and upload the file to confirm it is the unaltered copy.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.rate_limit import check_rate_limit
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Club, Document, DocumentReview

router = APIRouter(prefix="/verify", tags=["verify"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class VerificationOut(BaseModel):
    valid: bool
    document_title: str
    ref_no: Optional[str] = None
    club_name: str
    version_no: int
    approved_by: str
    approved_at: str
    sha256: Optional[str] = None
    file_matches: Optional[bool] = None


def _lookup(db: Session, code: str, request: Request) -> tuple[DocumentReview, Document, Club]:
    client = request.client.host if request.client else "unknown"
    check_rate_limit(f"verify:{client}", max_requests=60, window_seconds=600)
    review = (
        db.query(DocumentReview)
        .filter(DocumentReview.verification_code == code.strip().upper(), DocumentReview.action == "approved")
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="No approved document has this verification code.")
    # The review row names its club, so the document lookup stays scoped to that club
    doc = ScopedRepository(db, Document, club_id=review.club_id).get(review.document_id)
    club = db.query(Club).filter(Club.id == review.club_id).first()
    if doc is None or club is None:
        raise HTTPException(status_code=404, detail="The approved document no longer exists.")
    return review, doc, club


def _out(review: DocumentReview, doc: Document, club: Club, file_matches: Optional[bool] = None) -> VerificationOut:
    return VerificationOut(
        valid=True,
        document_title=doc.title,
        ref_no=doc.ref_no,
        club_name=club.name,
        version_no=review.version_no,
        approved_by=review.user.name if review.user else "Unknown",
        approved_at=review.created_at.strftime("%d/%m/%Y %H:%M UTC"),
        sha256=review.pdf_sha256,
        file_matches=file_matches,
    )


@router.get("/{code}", response_model=VerificationOut)
def verify_code(code: str, request: Request, db: Session = Depends(get_db)):
    review, doc, club = _lookup(db, code, request)
    return _out(review, doc, club)


@router.post("/{code}", response_model=VerificationOut)
async def verify_file(code: str, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    review, doc, club = _lookup(db, code, request)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large.")
    matches = bool(review.pdf_sha256) and hashlib.sha256(data).hexdigest() == review.pdf_sha256
    return _out(review, doc, club, file_matches=matches)
