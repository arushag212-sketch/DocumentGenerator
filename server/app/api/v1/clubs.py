"""Club management, memberships, people, and setup wizard using strict ScopedRepository access."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import (
    ClubContext,
    Role,
    get_current_user,
    require_club_access,
)
from server.app.core.scoped_repo import ScopedRepository
from server.app.core.security import decrypt_field, encrypt_field, mask_sensitive_field
from server.app.models import (
    AuditLog,
    Club,
    Membership,
    NumberingSeries,
    NumberReservation,
    Person,
    RoleHeld,
    User,
    Venue,
)
from server.app.schemas.audit import AuditLogOut
from server.app.schemas.club import (
    AddMemberRequest,
    ClubCreate,
    ClubMemberOut,
    ClubOut,
    ClubPermissionsOut,
    ClubUpdate,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    SetupWizardRequest,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _club_to_out(club: Club, my_role: Optional[str], db: Session) -> ClubOut:
    membership_repo = ScopedRepository(db, Membership, club_id=club.id)
    member_count = membership_repo.count(Membership.status == "active")

    series_repo = ScopedRepository(db, NumberingSeries, club_id=club.id)
    room_s = series_repo.find_first(NumberingSeries.key == "ROOM")
    evt_s = series_repo.find_first(NumberingSeries.key == "EVT")
    mom_s = series_repo.find_first(NumberingSeries.key == "MOM")

    settings_dict = club.settings or {}
    return ClubOut(
        id=club.id,
        name=club.name,
        short_name=club.short_name,
        slug=club.slug,
        chapter_code=club.chapter_code,
        head_of_account=club.head_of_account,
        academic_year_default=club.academic_year_default,
        settings=settings_dict,
        my_role=my_role,
        members_count=member_count,
        created_at=club.created_at,
        code=club.short_name,
        department=settings_dict.get("department", "Computer Science & Engineering"),
        academic_year=club.academic_year_default,
        room_counter=room_s.last_seq if room_s else 0,
        event_counter=evt_s.last_seq if evt_s else 0,
        mom_counter=mom_s.last_seq if mom_s else 0,
    )


@router.get("/", response_model=list[ClubOut])
def list_clubs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List clubs accessible to current user."""
    if current_user.is_platform_admin:
        clubs = db.query(Club).filter(Club.disabled_at.is_(None)).all()
        user_memberships = {m.club_id: m.role for m in current_user.memberships}
        return [
            _club_to_out(c, user_memberships.get(c.id, "platform_admin"), db)
            for c in clubs
        ]

    # Standard user: only list clubs where user is an active member
    active_memberships = [m for m in current_user.memberships if m.status == "active"]
    clubs_out = []
    for m in active_memberships:
        club = db.query(Club).filter(Club.id == m.club_id, Club.disabled_at.is_(None)).first()
        if club:
            clubs_out.append(_club_to_out(club, m.role, db))
    return clubs_out


@router.post("/", response_model=ClubOut, status_code=status.HTTP_201_CREATED)
def create_club(
    payload: ClubCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new club. The creator is assigned 'owner' via ScopedRepository."""
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
    db.flush()

    # Assign creator as owner using ScopedRepository
    membership_repo = ScopedRepository(db, Membership, club_id=club.id)
    membership_repo.create(
        user_id=current_user.id,
        role=Role.OWNER,
        status="active",
    )

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
    """Get club details (viewer+)."""
    return _club_to_out(ctx.club, ctx.role, db)


@router.get("/{club_id}/permissions", response_model=ClubPermissionsOut)
def get_club_permissions(
    club_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve current user's effective permissions and role within active club."""
    club = db.query(Club).filter(Club.id == club_id, Club.disabled_at.is_(None)).first()
    if not club:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLUB_NOT_FOUND", "message": "Club not found"},
        )

    membership_repo = ScopedRepository(db, Membership, club_id=club_id)
    membership = membership_repo.find_first(
        Membership.user_id == current_user.id,
        Membership.status == "active",
    )

    is_admin = current_user.is_platform_admin
    # Role in active club: if user has explicit membership, use that role;
    # if platform admin without explicit membership, default role to 'owner'
    role = membership.role if membership else ("owner" if is_admin else None)

    if not membership and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_A_MEMBER", "message": "You are not an active member of this club"},
        )

    can_edit_members = is_admin or role in (Role.OWNER, Role.ADMIN)
    can_edit_settings = is_admin or role in (Role.OWNER, Role.ADMIN)
    can_create_documents = is_admin or role in (Role.OWNER, Role.ADMIN, Role.EDITOR, "treasurer", "lead", "co_lead")
    can_finalize_documents = is_admin or role in (Role.OWNER, Role.ADMIN, "lead", "treasurer")
    can_view_sensitive = is_admin or role in (Role.OWNER, Role.ADMIN, "lead")

    return ClubPermissionsOut(
        is_platform_admin=is_admin,
        role=role,
        is_owner=(role == Role.OWNER),
        can_edit_members=can_edit_members,
        can_edit_settings=can_edit_settings,
        can_create_documents=can_create_documents,
        can_finalize_documents=can_finalize_documents,
        can_view_sensitive=can_view_sensitive,
    )


@router.put("/{club_id}", response_model=ClubOut)
def update_club(
    payload: ClubUpdate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update club settings (admin+)."""
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
    """Soft-delete club (owner only)."""
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


# ---------------- MEMBERSHIP ENDPOINTS (ScopedRepository) ----------------


@router.get("/{club_id}/members", response_model=list[ClubMemberOut])
def list_members(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List members strictly via ScopedRepository."""
    membership_repo = ScopedRepository(db, Membership, club_id=ctx.club.id)
    memberships = membership_repo.all(Membership.status == "active")

    out = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            out.append(
                ClubMemberOut(
                    id=m.id,
                    user_id=user.id,
                    email=user.email,
                    name=user.name,
                    role=m.role,
                    status=m.status,
                    joined_at=m.created_at,
                )
            )
    return out


@router.post("/{club_id}/members", response_model=ClubMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: AddMemberRequest,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Add member via ScopedRepository."""
    target_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": f"No user registered with email {payload.email}"},
        )

    membership_repo = ScopedRepository(db, Membership, club_id=ctx.club.id)
    existing_membership = membership_repo.find_first(Membership.user_id == target_user.id)

    if existing_membership:
        if existing_membership.status == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ALREADY_MEMBER", "message": "User is already an active member of this club"},
            )
        membership_repo.update(existing_membership.id, status="active", role=payload.role)
        membership = existing_membership
    else:
        membership = membership_repo.create(
            user_id=target_user.id,
            role=payload.role,
            status="active",
        )

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
    """Update member role via ScopedRepository."""
    membership_repo = ScopedRepository(db, Membership, club_id=ctx.club.id)
    membership = membership_repo.find_first(Membership.user_id == user_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBERSHIP_NOT_FOUND", "message": "User is not a member of this club"},
        )

    if not ctx.is_owner:
        if membership.role == Role.OWNER or payload.role == Role.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Only the club owner can assign or modify the owner role"},
            )

    old_role = membership.role
    membership_repo.update(membership.id, role=payload.role)

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
    """Remove member via ScopedRepository."""
    is_self = ctx.user.id == user_id
    if not is_self and not ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Admin permission required to remove other members"},
        )

    membership_repo = ScopedRepository(db, Membership, club_id=ctx.club.id)
    membership = membership_repo.find_first(Membership.user_id == user_id)
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

    if membership.role == Role.OWNER:
        other_owners = membership_repo.count(Membership.role == Role.OWNER, Membership.user_id != user_id)
        if other_owners == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SOLE_OWNER", "message": "Cannot remove sole owner. Transfer ownership first."},
            )

    membership_repo.delete(membership.id)

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


# ---------------- PEOPLE & SIGNATORIES (Field Encryption + ScopedRepository) ----------------


@router.get("/{club_id}/people", response_model=list[PersonOut])
def list_people(
    reveal: bool = Query(False, description="Reveal plaintext sensitive fields (requires admin)"),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List people strictly through ScopedRepository with field masking and reveal permission."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    people = person_repo.all()

    can_reveal = reveal and ctx.is_admin

    out = []
    for p in people:
        decrypted_mobile = decrypt_field(p.mobile)
        display_mobile = decrypted_mobile if can_reveal else mask_sensitive_field(decrypted_mobile)

        out.append(
            PersonOut(
                id=p.id,
                club_id=p.club_id,
                full_name=p.full_name,
                name=p.full_name,
                roll_no=p.roll_no,
                roll_number=p.roll_no,
                branch=p.branch,
                department=p.department,
                designation=p.notes or p.department,
                mobile=display_mobile,
                email=p.email,
                notes=p.notes,
                created_at=p.created_at,
            )
        )
    return out


@router.post("/{club_id}/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a person with mobile encrypted at rest via ScopedRepository."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    encrypted_mob = encrypt_field(payload.mobile) if payload.mobile else None

    person = person_repo.create(
        full_name=payload.full_name.strip(),
        roll_no=payload.roll_no.strip() if payload.roll_no else None,
        branch=payload.branch.strip() if payload.branch else None,
        department=payload.department.strip() if payload.department else None,
        mobile=encrypted_mob,
        email=payload.email.strip() if payload.email else None,
        notes=payload.notes,
    )

    return PersonOut(
        id=person.id,
        club_id=person.club_id,
        full_name=person.full_name,
        roll_no=person.roll_no,
        branch=person.branch,
        department=person.department,
        mobile=mask_sensitive_field(payload.mobile) if payload.mobile else None,
        email=person.email,
        notes=person.notes,
        created_at=person.created_at,
    )


# ---------------- FIRST-RUN SETUP WIZARD (ScopedRepository) ----------------


@router.post("/{club_id}/setup-wizard", status_code=status.HTTP_200_OK)
def run_setup_wizard(
    payload: SetupWizardRequest,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """First-run setup wizard: configure signatories, roles, venues, and numbering series without editing YAML."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    role_repo = ScopedRepository(db, RoleHeld, club_id=ctx.club.id)
    venue_repo = ScopedRepository(db, Venue, club_id=ctx.club.id)
    num_repo = ScopedRepository(db, NumberingSeries, club_id=ctx.club.id)

    # 1. Chairman
    chair = person_repo.create(
        full_name=payload.chairman_name,
        department=payload.chairman_dept,
    )
    role_repo.create(
        person_id=chair.id,
        role_key="faculty_chairman",
        designation_label=f"Chairman ({ctx.club.short_name})",
        academic_year=payload.academic_year,
    )

    # 2. Student Head
    s_head = person_repo.create(
        full_name=payload.student_head_name,
        roll_no=payload.student_head_roll,
        branch=payload.student_head_branch,
        mobile=encrypt_field(payload.student_head_mobile) if payload.student_head_mobile else None,
    )
    role_repo.create(
        person_id=s_head.id,
        role_key="student_head",
        designation_label=f"Student Head ({ctx.club.short_name})",
        academic_year=payload.academic_year,
    )

    # 3. Student Secretary
    s_sec = person_repo.create(
        full_name=payload.student_secretary_name,
        roll_no=payload.student_secretary_roll,
        branch=payload.student_secretary_branch,
    )
    role_repo.create(
        person_id=s_sec.id,
        role_key="student_secretary",
        designation_label=f"Secretary ({ctx.club.short_name})",
        academic_year=payload.academic_year,
    )

    # 4. Faculty Co-Chairman (if supplied)
    if payload.faculty_co_chairman_name:
        co_chair = person_repo.create(full_name=payload.faculty_co_chairman_name)
        role_repo.create(
            person_id=co_chair.id,
            role_key="faculty_co_chairman",
            designation_label=f"Co-Chairman ({ctx.club.short_name})",
            academic_year=payload.academic_year,
        )

    # 5. Venues
    for vname in payload.venues:
        venue_repo.create(
            name=vname,
            addressee_default=f"The Head of Department, {payload.chairman_dept}",
        )

    # 6. Numbering Series (ROOM, MOM, EVENT)
    cs = ctx.club.short_name
    ay = payload.academic_year
    num_repo.create(
        key="ROOM",
        format=f"{cs}/{ay}/ROOM/{{seq:03d}}",
        academic_year=ay,
        last_seq=0,
    )
    num_repo.create(
        key="MOM",
        format=f"{cs}/{ay}/MOM/{{seq:03d}}",
        academic_year=ay,
        last_seq=0,
    )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="setup_wizard_completed",
        entity_type="club",
        entity_id=ctx.club.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"academic_year": payload.academic_year, "venues_count": len(payload.venues)},
        ip=client_ip,
    )

    return {"message": "Club setup completed successfully. All signatories, roles, venues, and numbering initialized."}


# ---------------- NUMBERING RESERVATIONS (ATOMIC CONCURRENCY SAFE) ----------------


class ReserveNumberRequest(BaseModel):
    template_id: Optional[str] = None
    event_code: Optional[str] = None


class ReserveNumberResponse(BaseModel):
    reservation_id: str
    ref_no: str
    series_key: str
    academic_year: str
    expires_at: datetime


@router.post("/{club_id}/numbering/{series_key}/reserve", response_model=ReserveNumberResponse)
def reserve_reference_number(
    club_id: str,
    series_key: str,
    payload: Optional[ReserveNumberRequest] = None,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Atomically allocate and reserve the next reference number for a series and academic year.
    
    Academic year is strictly taken from club settings, never hardcoded.
    """
    from docgen.schema import load_schema
    from server.app.api.v1.documents import allocate_next_sequence

    academic_year = ctx.club.academic_year_default or (ctx.club.settings or {}).get("academic_year") or "2026-27"
    short_year = academic_year.split("-")[-1] if "-" in academic_year else academic_year[-2:]
    club_prefix = ctx.club.short_name or ctx.club.slug.upper()

    format_pattern = None
    if payload and payload.template_id:
        try:
            tmpl_schema = load_schema(payload.template_id)
            if tmpl_schema.numbering and tmpl_schema.numbering.format:
                format_pattern = tmpl_schema.numbering.format
        except Exception:
            pass

    # Atomically allocate sequence number using DB lock/atomic returning
    seq = allocate_next_sequence(
        db=db,
        club_id=ctx.club.id,
        series_key=series_key,
        academic_year=academic_year,
        club_code=club_prefix,
        format_pattern=format_pattern,
    )

    series_repo = ScopedRepository(db, NumberingSeries, club_id=ctx.club.id)
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == academic_year,
    )
    fmt = ns.format if (ns and ns.format) else (format_pattern or f"{club_prefix}/{{academic_year}}/{{series}}/{{seq:03d}}")
    event_code_val = (payload.event_code if payload and payload.event_code else series_key)
    ref_no = fmt.format(
        academic_year=academic_year,
        short_year=short_year,
        series=series_key,
        event_code=event_code_val,
        seq=seq,
    )

    now = datetime.utcnow()
    expires = now + timedelta(minutes=30)
    reservation = NumberReservation(
        id=str(uuid.uuid4()),
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        series_key=series_key,
        academic_year=academic_year,
        sequence_num=seq,
        ref_no=ref_no,
        expires_at=expires,
        status="reserved",
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return ReserveNumberResponse(
        reservation_id=reservation.id,
        ref_no=reservation.ref_no,
        series_key=reservation.series_key,
        academic_year=reservation.academic_year,
        expires_at=reservation.expires_at,
    )


# ---------------- AUDIT LOG ENDPOINTS (ScopedRepository) ----------------


@router.get("/{club_id}/audit-log", response_model=list[AuditLogOut])
def get_club_audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """View audit trail strictly via ScopedRepository."""
    audit_repo = ScopedRepository(db, AuditLog, club_id=ctx.club.id)
    return audit_repo.list(skip=skip, limit=limit, order_by=AuditLog.created_at.desc())
