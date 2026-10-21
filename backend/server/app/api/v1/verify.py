"""Public verification of documents (no login needed).

Every generated document carries a verification code in its footer.
Anyone can look the code up to verify document metadata, approval status,
and upload a PDF copy to confirm it is unaltered.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.rate_limit import check_rate_limit
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Club, Document, DocumentReview, DocumentVersion

router = APIRouter(prefix="/verify", tags=["verify"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class VerificationOut(BaseModel):
    valid: bool
    ref_no: Optional[str] = None
    document_title: str
    club_name: str
    version_no: int
    date_generated: Optional[str] = None
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    sha256: Optional[str] = None
    file_matches: Optional[bool] = None
    message: Optional[str] = None


def _lookup(
    db: Session, code: str, request: Request
) -> tuple[Optional[DocumentVersion], Optional[DocumentReview], Document, Club]:
    client = request.client.host if request.client else "unknown"
    check_rate_limit(f"verify:{client}", max_requests=60, window_seconds=600, db=db)

    clean_code = re.sub(r"\s+", "", code).upper()

    # 1. Look up by DocumentVersion first
    ver = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.verification_code == clean_code)
        .order_by(DocumentVersion.version_no.desc())
        .first()
    )

    review: Optional[DocumentReview] = None
    doc: Optional[Document] = None
    club: Optional[Club] = None

    if ver is not None:
        doc = db.get(Document, ver.document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="The document no longer exists.")
        club = db.query(Club).filter(Club.id == doc.club_id).first()
        if club is None:
            raise HTTPException(status_code=404, detail="The club no longer exists.")

        review = (
            db.query(DocumentReview)
            .filter(
                DocumentReview.document_id == doc.id,
                DocumentReview.version_no == ver.version_no,
                DocumentReview.action == "approved",
            )
            .order_by(DocumentReview.created_at.desc())
            .first()
        )
        return ver, review, doc, club

    # 2. Fall back to existing DocumentReview approval codes
    review = (
        db.query(DocumentReview)
        .filter(
            DocumentReview.verification_code == clean_code,
            DocumentReview.action == "approved",
        )
        .order_by(DocumentReview.created_at.desc())
        .first()
    )
    if review is not None:
        doc = ScopedRepository(db, Document, club_id=review.club_id).get(review.document_id)
        club = db.query(Club).filter(Club.id == review.club_id).first()
        if doc is None or club is None:
            raise HTTPException(status_code=404, detail="The approved document no longer exists.")
        ver = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.version_no == review.version_no,
            )
            .first()
        )
        return ver, review, doc, club

    # 3. Not found
    raise HTTPException(
        status_code=404,
        detail="No ClubDocs document has this verification code. Check the code printed in the footer of the document.",
    )


def _out(
    ver: Optional[DocumentVersion],
    review: Optional[DocumentReview],
    doc: Document,
    club: Club,
    file_matches: Optional[bool] = None,
    message: Optional[str] = None,
) -> VerificationOut:
    is_approved = review is not None
    status_str = "approved" if is_approved else "generated, not yet approved"

    date_gen_dt = (ver.created_at if ver and ver.created_at else None) or (
        review.created_at if review and review.created_at else doc.created_at
    )
    date_gen_str = date_gen_dt.strftime("%d/%m/%Y %H:%M UTC") if date_gen_dt else None

    approved_by = review.user.name if (review and review.user) else ("Unknown" if is_approved else None)
    approved_at = review.created_at.strftime("%d/%m/%Y %H:%M UTC") if (review and review.created_at) else None

    pdf_sha = (review.pdf_sha256 if review and review.pdf_sha256 else None) or (
        ver.pdf_sha256 if ver and ver.pdf_sha256 else None
    )

    version_no = ver.version_no if ver else (review.version_no if review else doc.current_version_no or 1)

    return VerificationOut(
        valid=True,
        ref_no=doc.ref_no,
        document_title=doc.title,
        club_name=club.name,
        version_no=version_no,
        date_generated=date_gen_str,
        status=status_str,
        approved_by=approved_by,
        approved_at=approved_at,
        sha256=pdf_sha,
        file_matches=file_matches,
        message=message,
    )


@router.get("/{code}", response_model=VerificationOut)
def verify_code(code: str, request: Request, db: Session = Depends(get_db)):
    ver, review, doc, club = _lookup(db, code, request)
    return _out(ver, review, doc, club)


@router.post("/{code}", response_model=VerificationOut)
async def verify_file(
    code: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ver, review, doc, club = _lookup(db, code, request)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large.")

    upload_sha256 = hashlib.sha256(data).hexdigest()

    matches = False
    if ver and ver.pdf_sha256 and upload_sha256 == ver.pdf_sha256:
        matches = True
    elif review and review.pdf_sha256 and upload_sha256 == review.pdf_sha256:
        matches = True

    msg = "matches" if matches else "does not match the copy generated by ClubDocs"
    return _out(ver, review, doc, club, file_matches=matches, message=msg)
