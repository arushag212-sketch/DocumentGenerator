"""Public and user invite endpoints for previewing and accepting club invites."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import ROLE_RANKS, get_current_user
from server.app.core.rate_limit import check_rate_limit
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Club, Invite, Membership, User
from server.app.schemas.club import AcceptInviteRequest, InvitePreview

router = APIRouter(prefix="/invites", tags=["invites"])

GENERIC_INVITE_ERROR = {
    "code": "INVALID_OR_EXPIRED_INVITE",
    "message": "Invalid or expired invite",
}


@router.get("/{code}", response_model=InvitePreview)
def get_invite_preview(code: str, request: Request, db: Session = Depends(get_db)):
    """Preview club invite details and validity status before registration or acceptance."""
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    clean_code = code.strip()

    # Rate limiting: 10 per minute per IP and per code
    check_rate_limit(f"invite_preview:ip:{client_ip}", max_requests=10, window_seconds=60, db=db)
    check_rate_limit(f"invite_preview:code:{clean_code}", max_requests=10, window_seconds=60, db=db)

    target_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
    invite = (
        db.query(Invite)
        .filter((Invite.code_hash == target_hash) | (Invite.code == target_hash) | (Invite.code == clean_code))
        .first()
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_invalid = False
    reason = None

    if not invite:
        is_invalid = True
        reason = "unknown_code"
    elif invite.revoked:
        is_invalid = True
        reason = "revoked"
    elif invite.expires_at and invite.expires_at < now:
        is_invalid = True
        reason = "expired"
    elif invite.max_uses > 0 and invite.use_count >= invite.max_uses:
        is_invalid = True
        reason = "used_up"

    if is_invalid:
        log_audit(
            db=db,
            action="invite_failed",
            entity_type="invite",
            entity_id=invite.id if invite else None,
            club_id=invite.club_id if invite else None,
            user_id=None,
            meta={"code_hash": target_hash[:16], "reason": reason},
            ip=client_ip,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_INVITE_ERROR,
        )

    club = db.query(Club).filter(Club.id == invite.club_id).first()
    if not club:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_INVITE_ERROR,
        )

    return InvitePreview(
        code=clean_code,
        club_id=club.id,
        club_name=club.name,
        club_slug=club.slug,
        role=invite.role,
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        is_valid=True,
        status="active",
    )


@router.post("/{code}/accept")
def accept_invite(
    code: str,
    payload: Optional[AcceptInviteRequest] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept an invite and join the club with assigned role."""
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    clean_code = code.strip()

    # Rate limiting: 10 per minute per IP and per code
    check_rate_limit(f"invite_accept:ip:{client_ip}", max_requests=10, window_seconds=60, db=db)
    check_rate_limit(f"invite_accept:code:{clean_code}", max_requests=10, window_seconds=60, db=db)

    target_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
    invite = (
        db.query(Invite)
        .filter((Invite.code_hash == target_hash) | (Invite.code == target_hash) | (Invite.code == clean_code))
        .first()
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_invalid = False
    reason = None

    if not invite:
        is_invalid = True
        reason = "unknown_code"
    elif invite.revoked:
        is_invalid = True
        reason = "revoked"
    elif invite.expires_at and invite.expires_at < now:
        is_invalid = True
        reason = "expired"
    elif invite.max_uses > 0 and invite.use_count >= invite.max_uses:
        is_invalid = True
        reason = "used_up"

    if is_invalid:
        log_audit(
            db=db,
            action="invite_failed",
            entity_type="invite",
            entity_id=invite.id if invite else None,
            club_id=invite.club_id if invite else None,
            user_id=current_user.id,
            meta={"code_hash": target_hash[:16], "reason": reason},
            ip=client_ip,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_INVITE_ERROR,
        )

    # Cross-club mismatch check: another club's invite cannot be used with a different club's id
    if payload and payload.club_id:
        if payload.club_id != invite.club_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_CLUB_INVITE",
                    "message": "This invite belongs to a different club and cannot be accepted for the specified club ID.",
                },
            )

    club = db.query(Club).filter(Club.id == invite.club_id).first()
    if not club:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLUB_NOT_FOUND", "message": "Associated club not found"},
        )

    # Check existing membership via ScopedRepository
    membership_repo = ScopedRepository(db, Membership, club_id=invite.club_id)
    existing_m = membership_repo.find_first(Membership.user_id == current_user.id)

    if existing_m:
        if existing_m.status == "active":
            target_rank = ROLE_RANKS.get(invite.role, 0)
            curr_rank = ROLE_RANKS.get(existing_m.role, 0)
            if target_rank > curr_rank:
                existing_m.role = invite.role
                membership_rec = existing_m
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "ALREADY_MEMBER", "message": "User is already an active member of this club"},
                )
        else:
            existing_m.status = "active"
            existing_m.role = invite.role
            membership_rec = existing_m
    else:
        membership_rec = membership_repo.create(
            user_id=current_user.id,
            role=invite.role,
            status="active",
        )

    # Increment invite usage
    invite.use_count += 1
    if invite.use_count >= invite.max_uses:
        invite.accepted_at = now

    db.flush()
    db.refresh(membership_rec)

    client_ip = request.client.host if request and request.client else None
    log_audit(
        db=db,
        action="invite_accepted",
        entity_type="membership",
        entity_id=membership_rec.id,
        club_id=invite.club_id,
        user_id=current_user.id,
        meta={
            "code": invite.code,
            "role": invite.role,
            "user_email": current_user.email,
            "use_count": invite.use_count,
            "max_uses": invite.max_uses,
        },
        ip=client_ip,
    )

    return {
        "message": f"Successfully joined {club.name} as {invite.role}",
        "club_id": club.id,
        "club_name": club.name,
        "club_slug": club.slug,
        "role": invite.role,
        "membership_id": membership_rec.id,
    }
