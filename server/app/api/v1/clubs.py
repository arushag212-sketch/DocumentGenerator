"""Club management, memberships, and roles API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import (
    ClubContext,
    Role,
    get_current_user,
    require_club_access,
)
from server.app.models import AuditLog, Club, Membership, User
from server.app.schemas.audit import AuditLogOut
from server.app.schemas.club import (
    AddMemberRequest,
    ClubCreate,
    ClubMemberOut,
    ClubOut,
    ClubUpdate,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _club_to_out(club: Club, my_role: Optional[str], db: Session) -> ClubOut:
    member_count = (
        db.query(Membership)
        .filter(Membership.club_id == club.id, Membership.status == "active")
        .count()
    )
    return ClubOut(
        id=club.id,
        name=club.name,
        short_name=club.short_name,
        slug=club.slug,
        chapter_code=club.chapter_code,
        head_of_account=club.head_of_account,
        academic_year_default=club.academic_year_default,
        settings=club.settings or {},
        my_role=my_role,
        members_count=member_count,
        created_at=club.created_at,
    )


@router.get("/", response_model=list[ClubOut])
def list_clubs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List clubs that the current user belongs to, or all clubs if platform administrator."""
    if current_user.is_platform_admin:
        clubs = db.query(Club).filter(Club.disabled_at.is_(None)).all()
        # Find user's specific roles where applicable
        user_memberships = {
            m.club_id: m.role
            for m in db.query(Membership).filter(Membership.user_id == current_user.id).all()
        }
        return [
            _club_to_out(c, user_memberships.get(c.id, "platform_admin"), db)
            for c in clubs
        ]

    # Standard user: only list clubs where user is an active member
    memberships = (
        db.query(Membership, Club)
        .join(Club, Membership.club_id == Club.id)
        .filter(
            Membership.user_id == current_user.id,
            Membership.status == "active",
            Club.disabled_at.is_(None),
        )
        .all()
    )
    return [_club_to_out(club, m.role, db) for m, club in memberships]


@router.post("/", response_model=ClubOut, status_code=status.HTTP_201_CREATED)
def create_club(
    payload: ClubCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new club. The creator is automatically assigned as 'owner'."""
    existing_slug = db.query(Club).filter(Club.slug == payload.slug.lower().strip()).first()
    if existing_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SLUG_EXISTS", "message": f"Club with identifier '{payload.slug}' already exists"},
        )

    club = Club(
        name=payload.name.strip(),
        short_name=payload.short_name.strip(),
        slug=payload.slug.lower().strip(),
        chapter_code=payload.chapter_code,
        head_of_account=payload.head_of_account,
        academic_year_default=payload.academic_year_default,
        settings={},
    )
    db.add(club)
    db.flush()  # populate club.id

    # Assign creator as owner
    owner_membership = Membership(
        user_id=current_user.id,
        club_id=club.id,
        role=Role.OWNER,
        status="active",
    )
    db.add(owner_membership)
    db.commit()
    db.refresh(club)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="club_created",
        entity_type="club",
        entity_id=club.id,
        club_id=club.id,
        user_id=current_user.id,
        meta={"name": club.name, "slug": club.slug},
        ip=client_ip,
    )

    return _club_to_out(club, Role.OWNER, db)


@router.get("/{club_id}", response_model=ClubOut)
def get_club(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Get details of a specific club (accessible to all members with viewer role and above)."""
    return _club_to_out(ctx.club, ctx.role, db)


@router.put("/{club_id}", response_model=ClubOut)
def update_club(
    payload: ClubUpdate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update club configuration (accessible to club admin and owner)."""
    club = ctx.club
    if payload.name is not None:
        club.name = payload.name.strip()
    if payload.short_name is not None:
        club.short_name = payload.short_name.strip()
    if payload.chapter_code is not None:
        club.chapter_code = payload.chapter_code
    if payload.head_of_account is not None:
        club.head_of_account = payload.head_of_account
    if payload.academic_year_default is not None:
        club.academic_year_default = payload.academic_year_default
    if payload.settings is not None:
        curr = club.settings or {}
        curr.update(payload.settings)
        club.settings = curr

    db.commit()
    db.refresh(club)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="club_updated",
        entity_type="club",
        entity_id=club.id,
        club_id=club.id,
        user_id=ctx.user.id,
        meta=payload.model_dump(exclude_unset=True),
        ip=client_ip,
    )

    return _club_to_out(club, ctx.role, db)


@router.delete("/{club_id}")
def delete_club(
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.OWNER)),
    db: Session = Depends(get_db),
):
    """Soft-delete a club (accessible only to club owner or platform admin)."""
    club = ctx.club
    club.disabled_at = datetime.now(timezone.utc)
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="club_soft_deleted",
        entity_type="club",
        entity_id=club.id,
        club_id=club.id,
        user_id=ctx.user.id,
        ip=client_ip,
    )

    return {"message": f"Club '{club.name}' has been deactivated"}


# ---------------- MEMBERSHIP ENDPOINTS ----------------


@router.get("/{club_id}/members", response_model=list[ClubMemberOut])
def list_members(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List all members of the club (viewer and above)."""
    memberships = (
        db.query(Membership, User)
        .join(User, Membership.user_id == User.id)
        .filter(Membership.club_id == ctx.club.id, Membership.status == "active")
        .all()
    )

    return [
        ClubMemberOut(
            id=m.id,
            user_id=u.id,
            email=u.email,
            name=u.name,
            role=m.role,
            status=m.status,
            joined_at=m.created_at,
        )
        for m, u in memberships
    ]


@router.post("/{club_id}/members", response_model=ClubMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: AddMemberRequest,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Add a member to the club by email (admin and above)."""
    target_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": f"No user registered with email {payload.email}"},
        )

    existing_membership = (
        db.query(Membership)
        .filter(Membership.user_id == target_user.id, Membership.club_id == ctx.club.id)
        .first()
    )

    if existing_membership:
        if existing_membership.status == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ALREADY_MEMBER", "message": "User is already an active member of this club"},
            )
        # Reactivate
        existing_membership.status = "active"
        existing_membership.role = payload.role
        db.commit()
        db.refresh(existing_membership)
        membership = existing_membership
    else:
        membership = Membership(
            user_id=target_user.id,
            club_id=ctx.club.id,
            role=payload.role,
            status="active",
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="member_added",
        entity_type="membership",
        entity_id=membership.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"added_user_id": target_user.id, "email": target_user.email, "role": payload.role},
        ip=client_ip,
    )

    return ClubMemberOut(
        id=membership.id,
        user_id=target_user.id,
        email=target_user.email,
        name=target_user.name,
        role=membership.role,
        status=membership.status,
        joined_at=membership.created_at,
    )


@router.put("/{club_id}/members/{user_id}", response_model=ClubMemberOut)
def update_member_role(
    user_id: str,
    payload: UpdateMemberRoleRequest,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update a member's role (admin can manage editor/viewer; owner can manage all)."""
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.club_id == ctx.club.id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBERSHIP_NOT_FOUND", "message": "User is not a member of this club"},
        )

    # An admin cannot promote someone to owner or alter an owner's role
    if not ctx.is_owner:
        if membership.role == Role.OWNER or payload.role == Role.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Only the club owner can assign or modify the owner role"},
            )

    old_role = membership.role
    membership.role = payload.role
    db.commit()
    db.refresh(membership)

    user = db.query(User).filter(User.id == user_id).first()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="member_role_updated",
        entity_type="membership",
        entity_id=membership.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"target_user_id": user_id, "old_role": old_role, "new_role": payload.role},
        ip=client_ip,
    )

    return ClubMemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        status=membership.status,
        joined_at=membership.created_at,
    )


@router.delete("/{club_id}/members/{user_id}")
def remove_member(
    user_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Remove a member from the club. Users can leave themselves, admins can remove non-owners, owners can remove anyone."""
    is_self = ctx.user.id == user_id
    if not is_self and not ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Admin permission required to remove other members"},
        )

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.club_id == ctx.club.id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBERSHIP_NOT_FOUND", "message": "Member not found in this club"},
        )

    if membership.role == Role.OWNER and not ctx.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot remove the club owner"},
        )

    # Disallow leaving if user is the sole owner
    if membership.role == Role.OWNER:
        other_owners = (
            db.query(Membership)
            .filter(
                Membership.club_id == ctx.club.id,
                Membership.role == Role.OWNER,
                Membership.user_id != user_id,
                Membership.status == "active",
            )
            .count()
        )
        if other_owners == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SOLE_OWNER", "message": "Cannot remove the sole club owner. Transfer ownership first."},
            )

    db.delete(membership)
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="member_removed",
        entity_type="membership",
        entity_id=membership.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"removed_user_id": user_id, "is_self": is_self},
        ip=client_ip,
    )

    return {"message": "Member removed successfully"}


# ---------------- AUDIT LOG ENDPOINTS ----------------


@router.get("/{club_id}/audit-log", response_model=list[AuditLogOut])
def get_club_audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """View audit trail for this club (accessible to admin and owner)."""
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.club_id == ctx.club.id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs
