"""Club management, memberships, people, and setup wizard using strict ScopedRepository access."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import (
    ClubContext,
    Role,
    get_current_user,
    require_club_access,
)
import re
from server.app.core.scoped_repo import ScopedRepository
from server.app.core.security import decrypt_field, encrypt_field, mask_sensitive_field
from server.app.core.storage import LocalDiskStorage, get_storage
from server.app.core.tenancy import (
    get_asset_for_club,
    letterhead_is_visible_to_club,
    validate_letterhead_asset_refs,
)
from server.app.models import (
    Asset,
    AuditLog,
    Club,
    Invite,
    JoinRequest,
    Letterhead,
    Membership,
    NumberingSeries,
    NumberReservation,
    Person,
    RoleHeld,
    Template,
    TemplateVersion,
    User,
    Venue,
)
from server.app.schemas.audit import AuditLogOut
from server.app.schemas.club import (
    AddMemberRequest,
    ApproveJoinRequest,
    AssetOut,
    ClubCreate,
    ClubMemberOut,
    ClubOut,
    ClubPermissionsOut,
    ClubSearchOut,
    ClubUpdate,
    InviteCreate,
    InviteOut,
    JoinRequestCreate,
    JoinRequestOut,
    LetterheadCreate,
    LetterheadOut,
    LetterheadUpdate,
    NumberingSeriesCreate,
    NumberingSeriesOut,
    NumberingSeriesUpdate,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    RoleHeldCreate,
    RoleHeldOut,
    RoleHeldUpdate,
    SetupWizardRequest,
    UpdateMemberRoleRequest,
    UpdatePositionRequest,
    VenueCreate,
    VenueOut,
    VenueUpdate,
)

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _club_to_out(club: Club, my_role: Optional[str], db: Session) -> ClubOut:
    membership_repo = ScopedRepository(db, Membership, club_id=club.id)
    member_count = membership_repo.count(Membership.status == "active")

    series_repo = ScopedRepository(db, NumberingSeries, club_id=club.id)
    all_series = {s.key: s.last_seq for s in series_repo.all()}

    settings_dict = club.settings or {}
    ay = club.academic_year_default or (settings_dict.get("academic_year") if isinstance(settings_dict, dict) else None)
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
        department=settings_dict.get("department", ""),
        academic_year=ay,
        room_counter=all_series.get("ROOM", 0),
        event_counter=all_series.get("EVT", all_series.get("EVENT", 0)),
        mom_counter=all_series.get("MOM", 0),
    )


from sqlalchemy import func

from server.app.core.club_positions import POSITIONS

FIXED_POSITIONS: dict[str, str] = {
    p["label"]: p["key"] for p in POSITIONS
}
# Backward compatibility mappings for legacy stored positions / alternative spacing:
FIXED_POSITIONS.setdefault("Student Head / Chairperson", "student_head")
FIXED_POSITIONS.setdefault("Core member", "core_member")
FIXED_POSITIONS.setdefault("Member", "member")
FIXED_POSITIONS["Other"] = "member"

SIGNATORY_ROLES: set[str] = {
    p["key"] for p in POSITIONS if p.get("signs")
}


def validate_and_normalize_position(raw_position: str) -> tuple[str, str, Optional[str]]:
    """Validate and normalize user-provided position.
    
    Returns: (stored_position, role_key, display_note)
    - If in FIXED_POSITIONS: returns normalized position and mapped role_key.
    - If 'Other' or custom text: validates max 60 chars, letters/spaces/-&/ only.
      Role key is ALWAYS 'member' and NEVER maps to a signatory role.
    """
    if not raw_position or not str(raw_position).strip():
        return ("Member", "member", None)
    
    pos = str(raw_position).strip()
    if pos in FIXED_POSITIONS:
        if pos == "Other":
            return ("Other", "member", None)
        return (pos, FIXED_POSITIONS[pos], None)
    
    # Custom / 'Other' note (e.g. 'Other: Head of Marketing' or 'Head of Marketing')
    note = pos.split(":", 1)[1].strip() if pos.lower().startswith("other:") else pos
    if len(note) > 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_POSITION",
                "message": "Custom position note must not exceed 60 characters.",
            },
        )
    if not re.match(r"^[A-Za-z\s\-&/]+$", note):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_POSITION",
                "message": "Custom position note can only contain letters, spaces, hyphens, ampersands, or slashes.",
            },
        )
    return (f"Other: {note}", "member", note)


def sync_membership_position_to_role_held(
    db: Session,
    club: Club,
    user: User,
    position: Optional[str],
    is_signatory: bool = False,
    signatory_role: Optional[str] = None,
    conflict_resolution: Optional[str] = None,
) -> Optional[RoleHeld]:
    """Map a member's position into Person and RoleHeld records for signature blocks.
    
    Rules:
    - Only signatory roles (student_head, student_secretary, treasurer, faculty_chairman, faculty_co_chairman)
      create or update a Person and RoleHeld.
    - ONLY when is_signatory is True (ticked by admin).
    - Members with non-signatory positions create NO Person record.
    - 'Other' never maps to a signatory role.
    - If another active holder exists for the academic year:
      - Admin must explicitly choose 'replace' or 'keep_both'.
      - Otherwise 409 conflict is raised.
    - Uses club.academic_year_default (no hardcoded fallback). Fails clearly if not configured.
    """
    if not is_signatory:
        return None

    stored_pos, mapped_role, note = validate_and_normalize_position(position or "Member")
    target_role = signatory_role or mapped_role

    if target_role not in SIGNATORY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SIGNATORY_POSITION",
                "message": f"Position '{position}' cannot be designated as an official signatory.",
            },
        )

    ay = club.academic_year_default
    if not ay or not str(ay).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ACADEMIC_YEAR_REQUIRED",
                "message": f"Club '{club.name}' has no configured academic year for signatories.",
            },
        )

    # Active existing holders of this role in the club for the academic year
    active_holders = (
        db.query(RoleHeld)
        .filter(
            RoleHeld.club_id == club.id,
            RoleHeld.role_key == target_role,
            RoleHeld.academic_year == ay,
            RoleHeld.valid_to.is_(None),
        )
        .all()
    )

    person_repo = ScopedRepository(db, Person, club_id=club.id)
    user_person = person_repo.find_first((Person.email == user.email) | (Person.full_name == user.name))

    other_holders = [ah for ah in active_holders if not user_person or ah.person_id != user_person.id]

    if other_holders:
        if not conflict_resolution:
            other_person = person_repo.get(other_holders[0].person_id)
            existing_name = other_person.full_name if other_person else "Existing holder"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SIGNATORY_ROLE_CONFLICT",
                    "existing_holder": existing_name,
                    "role_key": target_role,
                    "academic_year": ay,
                    "message": f"{existing_name} already holds the '{target_role}' signatory role for {ay}. Please explicitly choose to replace {existing_name} or keep both.",
                },
            )
        elif conflict_resolution == "replace":
            now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
            for ah in other_holders:
                ah.valid_to = now_dt
            db.flush()

    # Create Person record only when is_signatory is True
    if not user_person:
        user_person = Person(
            club_id=club.id,
            full_name=user.name,
            email=user.email,
        )
        db.add(user_person)
        db.flush()

    if target_role == "student_head":
        label = f"Chairperson, {club.short_name}"
    elif target_role == "student_secretary":
        label = f"Student Secretary, {club.short_name}"
    elif target_role == "treasurer":
        label = f"Treasurer, {club.short_name}"
    elif target_role == "faculty_chairman":
        label = f"Chairman, {club.name}"
    elif target_role == "faculty_co_chairman":
        label = f"Co-Chairman, {club.name}"
    else:
        label = f"{target_role.replace('_', ' ').title()}, {club.short_name}"

    existing_for_this_user = [ah for ah in active_holders if user_person and ah.person_id == user_person.id]
    if existing_for_this_user:
        existing_rh = existing_for_this_user[0]
        existing_rh.designation_label = label
        existing_rh.valid_to = None
        db.flush()
        return existing_rh
    else:
        new_rh = RoleHeld(
            club_id=club.id,
            person_id=user_person.id,
            role_key=target_role,
            designation_label=label,
            academic_year=ay,
            valid_from=datetime.now(timezone.utc).replace(tzinfo=None),
            valid_to=None,
        )
        db.add(new_rh)
        db.flush()
        return new_rh


@router.get("/search", response_model=list[ClubSearchOut])
def search_clubs(
    q: str = Query("", description="Search term for club name, short name or slug"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Searchable list of clubs with current user's membership and join request status."""
    query = db.query(Club).filter(Club.disabled_at.is_(None))
    term = q.strip().lower()
    if term:
        like_term = f"%{term}%"
        query = query.filter(
            (Club.name.ilike(like_term)) |
            (Club.short_name.ilike(like_term)) |
            (Club.slug.ilike(like_term)) |
            (Club.chapter_code.ilike(like_term))
        )
    clubs = query.order_by(Club.name.asc()).all()

    # Pre-fetch user's memberships and join requests
    memberships = {m.club_id: m for m in db.scalars(select(Membership).where(Membership.user_id == current_user.id)).all()}
    join_requests = {jr.club_id: jr for jr in db.query(JoinRequest).filter(JoinRequest.user_id == current_user.id).order_by(JoinRequest.created_at.desc()).all()}

    results = []
    for c in clubs:
        m = memberships.get(c.id)
        jr = join_requests.get(c.id)
        m_repo = ScopedRepository(db, Membership, club_id=c.id)
        m_count = m_repo.count(Membership.status == "active")

        # Find an admin / owner name for the club
        admin_membership = m_repo.find_first(
            Membership.status == "active",
            Membership.role.in_(["owner", "admin"]),
        )
        admin_name = None
        if admin_membership:
            admin_user = db.query(User).filter(User.id == admin_membership.user_id).first()
            if admin_user:
                admin_name = admin_user.name

        results.append(
            ClubSearchOut(
                id=c.id,
                name=c.name,
                short_name=c.short_name,
                slug=c.slug,
                chapter_code=c.chapter_code,
                academic_year_default=c.academic_year_default,
                members_count=m_count,
                membership_role=m.role if (m and m.status == "active") else None,
                membership_status=m.status if m else None,
                membership_position=m.position if m else None,
                join_request_status=jr.status if jr else None,
                admin_name=admin_name,
                has_logo=_active_logo_asset(db, c) is not None,
            )
        )
    return results


@router.get("", response_model=list[ClubOut])
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

    # Standard user: list clubs where user is an active member or has a pending join request
    active_memberships = [m for m in current_user.memberships if m.status == "active"]
    clubs_out = []
    included_ids = set()
    for m in active_memberships:
        club = db.query(Club).filter(Club.id == m.club_id, Club.disabled_at.is_(None)).first()
        if club:
            clubs_out.append(_club_to_out(club, m.role, db))
            included_ids.add(club.id)

    pending_jrs = db.query(JoinRequest).filter(
        JoinRequest.user_id == current_user.id,
        JoinRequest.status == "pending",
    ).all()
    for jr in pending_jrs:
        if jr.club_id not in included_ids:
            club = db.query(Club).filter(Club.id == jr.club_id, Club.disabled_at.is_(None)).first()
            if club:
                clubs_out.append(_club_to_out(club, None, db))
                included_ids.add(club.id)

    return clubs_out


@router.get("/positions")
def list_positions_catalog(current_user: User = Depends(get_current_user)):
    """Club positions available across clubs (who signs which documents). Requires authentication."""
    return POSITIONS


@router.post("", response_model=ClubOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ClubOut, status_code=status.HTTP_201_CREATED)
def create_club(
    payload: ClubCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new club. The creator is assigned 'owner' via ScopedRepository immediately."""
    # 1. Name uniqueness (case-insensitive)
    name_stripped = payload.name.strip()
    existing_name = db.query(Club).filter(func.lower(Club.name) == name_stripped.lower()).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CLUB_NAME_EXISTS",
                "message": f"A club named '{name_stripped}' already exists. Did you mean to join it instead?",
            },
        )

    # 2. Rate limit: maximum 3 clubs created per user per day
    one_day_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    clubs_created_24h = (
        db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == current_user.id,
                AuditLog.action == "club_created",
                AuditLog.created_at >= one_day_ago,
            )
        )
        or 0
    )
    if clubs_created_24h >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Club creation limit exceeded (maximum 3 clubs per day).",
            },
        )

    # 3. Position validation
    stored_pos, mapped_role, note = validate_and_normalize_position(payload.position or "Student Head/Chairperson")

    slug = payload.slug
    if not slug or not slug.strip():
        base_slug = re.sub(r'[^a-z0-9]+', '-', (payload.short_name or payload.name).lower()).strip('-')
        slug = base_slug or "club"
        counter = 1
        while db.query(Club).filter(Club.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
    else:
        slug = slug.lower().strip()
        existing_slug = db.query(Club).filter(Club.slug == slug).first()
        if existing_slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SLUG_EXISTS", "message": f"Club with identifier '{slug}' already exists"},
            )

    club = Club(
        name=name_stripped,
        short_name=payload.short_name.strip(),
        slug=slug,
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
        position=stored_pos,
        status="active",
    )
    if payload.is_signatory:
        sync_membership_position_to_role_held(
            db=db,
            club=club,
            user=current_user,
            position=stored_pos,
            is_signatory=True,
        )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="club_created",
        entity_type="club",
        entity_id=club.id,
        club_id=club.id,
        user_id=current_user.id,
        meta={"name": club.name, "slug": club.slug, "position": stored_pos},
        ip=client_ip,
    )

    db.commit()
    db.refresh(club)

    return _club_to_out(club, Role.OWNER, db)


# ---------------- JOIN REQUEST ENDPOINTS ----------------


def _join_request_out(
    jr: JoinRequest,
    club: Club,
    user: Optional[User],
    admin_user: Optional[User] = None,
) -> JoinRequestOut:
    return JoinRequestOut(
        id=jr.id,
        club_id=club.id,
        club_name=club.name,
        user_id=jr.user_id,
        user_name=user.name if user else "Unknown",
        user_email=user.email if user else "unknown@svnit.ac.in",
        position=jr.position,
        requested_role=jr.requested_role or Role.EDITOR,
        message=jr.message,
        status=jr.status,
        admin_name=admin_user.name if admin_user else None,
        reviewed_by=jr.reviewed_by,
        reviewed_at=jr.reviewed_at,
        created_at=jr.created_at,
    )


def _club_admin_user(db: Session, club_id: str) -> Optional[User]:
    admin_membership = ScopedRepository(db, Membership, club_id=club_id).find_first(
        Membership.status == "active", Membership.role.in_([Role.OWNER, Role.ADMIN])
    )
    if not admin_membership:
        return None
    return db.query(User).filter(User.id == admin_membership.user_id).first()


@router.post("/{club_id}/join-requests", response_model=JoinRequestOut, status_code=status.HTTP_201_CREATED)
def create_join_request(
    club_id: str,
    payload: JoinRequestCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a join request with a chosen position for the club."""
    club = db.query(Club).filter(Club.id == club_id, Club.disabled_at.is_(None)).first()
    if not club:
        raise HTTPException(status_code=404, detail={"code": "CLUB_NOT_FOUND", "message": "Club not found"})

    # 1. Position validation & normalization
    stored_pos, mapped_role, note = validate_and_normalize_position(payload.position)

    # 2. Rate limits: maximum 5/hour, 20/day per user
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)

    hourly_requests = db.query(JoinRequest).filter(
        JoinRequest.user_id == current_user.id,
        JoinRequest.created_at >= one_hour_ago,
    ).count()
    if hourly_requests >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Join request hourly rate limit exceeded (maximum 5 requests per hour).",
            },
        )

    daily_requests = db.query(JoinRequest).filter(
        JoinRequest.user_id == current_user.id,
        JoinRequest.created_at >= one_day_ago,
    ).count()
    if daily_requests >= 20:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Join request daily rate limit exceeded (maximum 20 requests per day).",
            },
        )

    # 3. 24-hour cooldown after rejection
    last_rejection = (
        db.query(JoinRequest)
        .filter(
            JoinRequest.club_id == club.id,
            JoinRequest.user_id == current_user.id,
            JoinRequest.status == "rejected",
        )
        .order_by(JoinRequest.reviewed_at.desc(), JoinRequest.created_at.desc())
        .first()
    )
    if last_rejection and last_rejection.reviewed_at:
        seconds_since = (now - last_rejection.reviewed_at).total_seconds()
        if seconds_since < 24 * 3600:
            hours_left = int((24 * 3600 - seconds_since) // 3600) + 1
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REJECTION_COOLDOWN",
                    "message": f"You can submit a new join request 24 hours after a previous rejection (please wait {hours_left} more hour(s)).",
                },
            )

    # Check if already an active member
    m_repo = ScopedRepository(db, Membership, club_id=club_id)
    m = m_repo.find_first(Membership.user_id == current_user.id, Membership.status == "active")
    if m:
        raise HTTPException(status_code=400, detail={"code": "ALREADY_MEMBER", "message": "You are already an active member of this club"})

    # Check existing pending join request
    existing_jr = db.query(JoinRequest).filter(
        JoinRequest.club_id == club_id,
        JoinRequest.user_id == current_user.id,
        JoinRequest.status == "pending",
    ).first()
    if existing_jr:
        return _join_request_out(existing_jr, club, current_user, _club_admin_user(db, club.id))

    jr = JoinRequest(
        club_id=club.id,
        user_id=current_user.id,
        position=stored_pos,
        requested_role=payload.requested_role,
        message=(payload.message or "").strip() or None,
        status="pending",
    )
    db.add(jr)
    db.flush()

    admin_user = _club_admin_user(db, club.id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="join_request_created",
        entity_type="join_request",
        entity_id=jr.id,
        club_id=club.id,
        user_id=current_user.id,
        meta={"position": jr.position, "requested_role": jr.requested_role},
        ip=client_ip,
    )
    from server.app.core.notifications import club_admin_ids, notify

    notify(
        db, club_admin_ids(db, club.id), club_id=club.id, kind="join_request",
        title=f"New join request: {current_user.name}",
        body=f"{current_user.name} ({current_user.email}) asked to join {club.name} as {jr.position or 'a member'}.",
        link="/join-requests",
    )

    db.commit()
    db.refresh(jr)

    return _join_request_out(jr, club, current_user, admin_user)


@router.get("/{club_id}/join-requests/my", response_model=Optional[JoinRequestOut])
def get_my_join_request(
    club_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve current user's latest join request for this club."""
    club = db.query(Club).filter(Club.id == club_id, Club.disabled_at.is_(None)).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    jr = (
        db.query(JoinRequest)
        .filter(JoinRequest.club_id == club_id, JoinRequest.user_id == current_user.id)
        .order_by(JoinRequest.created_at.desc())
        .first()
    )
    if not jr:
        return None

    return _join_request_out(jr, club, current_user, _club_admin_user(db, club.id))


@router.get("/{club_id}/join-requests", response_model=list[JoinRequestOut])
def list_join_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """List join requests for the club (admins only)."""
    query = db.query(JoinRequest).filter(JoinRequest.club_id == ctx.club.id)
    if status_filter:
        query = query.filter(JoinRequest.status == status_filter)
    requests = query.order_by(JoinRequest.created_at.desc()).all()

    user_ids = {r.user_id for r in requests}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return [_join_request_out(r, ctx.club, users.get(r.user_id)) for r in requests]


@router.post("/{club_id}/join-requests/{request_id}/approve", response_model=JoinRequestOut)
def approve_join_request(
    club_id: str,
    request_id: str,
    payload: ApproveJoinRequest,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Approve a pending join request with an assigned role (admin+)."""
    jr = db.query(JoinRequest).filter(JoinRequest.id == request_id, JoinRequest.club_id == ctx.club.id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Join request not found")
    if jr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Join request is already {jr.status}")

    from server.app.core.permissions import ROLE_RANKS
    granted_role = payload.role or jr.requested_role or Role.EDITOR
    if ROLE_RANKS.get(granted_role, 0) > ROLE_RANKS.get(ctx.role, 0) and not ctx.user.is_platform_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot grant role '{granted_role}' which exceeds your own role '{ctx.role}'",
        )

    target_user = db.query(User).filter(User.id == jr.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    final_position = jr.position
    if payload.position is not None:
        stored_pos, mapped_role, note = validate_and_normalize_position(payload.position)
        final_position = stored_pos

    # If signatory is ticked, sync before approving so conflict raises 409 and request stays pending
    if payload.is_signatory:
        sync_membership_position_to_role_held(
            db=db,
            club=ctx.club,
            user=target_user,
            position=final_position,
            is_signatory=True,
            signatory_role=payload.signatory_role,
            conflict_resolution=payload.conflict_resolution,
        )

    jr.status = "approved"
    jr.reviewed_by = ctx.user.id
    jr.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create or update membership
    membership_repo = ScopedRepository(db, Membership, club_id=ctx.club.id)
    m = membership_repo.find_first(Membership.user_id == jr.user_id)
    if m:
        m.role = granted_role
        m.status = "active"
        m.position = final_position
    else:
        membership_repo.create(
            user_id=jr.user_id,
            role=granted_role,
            position=final_position,
            status="active",
        )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="join_request_approved",
        entity_type="join_request",
        entity_id=jr.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={
            "assigned_role": granted_role,
            "requested_role": jr.requested_role,
            "position": final_position,
            "requested_position": jr.position,
            "approved_position": final_position,
            "target_user_id": jr.user_id,
        },
        ip=client_ip,
    )

    db.commit()

    return _join_request_out(jr, ctx.club, target_user)


@router.post("/{club_id}/join-requests/{request_id}/reject", response_model=JoinRequestOut)
def reject_join_request(
    club_id: str,
    request_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Reject a pending join request (admin+)."""
    jr = db.query(JoinRequest).filter(JoinRequest.id == request_id, JoinRequest.club_id == ctx.club.id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Join request not found")
    if jr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Join request is already {jr.status}")

    jr.status = "rejected"
    jr.reviewed_by = ctx.user.id
    jr.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    target_user = db.query(User).filter(User.id == jr.user_id).first()
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="join_request_rejected",
        entity_type="join_request",
        entity_id=jr.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"target_user_id": jr.user_id},
        ip=client_ip,
    )

    return _join_request_out(jr, ctx.club, target_user)


@router.post("/{club_id}/join-requests/{request_id}/cancel", response_model=JoinRequestOut)
def cancel_join_request(
    club_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User cancels their own pending join request."""
    jr = db.query(JoinRequest).filter(
        JoinRequest.id == request_id,
        JoinRequest.club_id == club_id,
        JoinRequest.user_id == current_user.id,
    ).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Join request not found")
    if jr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel request with status '{jr.status}'")

    jr.status = "cancelled"
    db.flush()

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return _join_request_out(jr, club, current_user)


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
    is_member = membership is not None
    if is_member:
        role = membership.role
        position = membership.position
    else:
        role = "owner"
        position = None

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
        is_member=is_member,
        role=role,
        is_owner=(role == Role.OWNER),
        can_edit_members=can_edit_members,
        can_edit_settings=can_edit_settings,
        can_create_documents=can_create_documents,
        can_finalize_documents=can_finalize_documents,
        can_view_sensitive=can_view_sensitive,
        position=position,
    )


@router.put("/{club_id}/position")
def update_my_position(
    club_id: str,
    payload: UpdatePositionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow active club member to set or update their position in the club."""
    club = db.query(Club).filter(Club.id == club_id, Club.disabled_at.is_(None)).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    membership_repo = ScopedRepository(db, Membership, club_id=club_id)
    membership = membership_repo.find_first(
        Membership.user_id == current_user.id,
        Membership.status == "active",
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_A_MEMBER", "message": "You are not an active member of this club"},
        )

    pos = payload.position.strip()
    if not pos:
        raise HTTPException(status_code=400, detail="Position cannot be empty")

    membership.position = pos
    db.commit()
    db.refresh(membership)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="member_position_updated",
        entity_type="membership",
        entity_id=membership.id,
        club_id=club_id,
        user_id=current_user.id,
        meta={"position": pos},
        ip=client_ip,
    )

    return {"status": "success", "position": membership.position}



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
        club.chapter_code = payload.chapter_code.strip() if payload.chapter_code else None
    if payload.head_of_account is not None:
        club.head_of_account = payload.head_of_account.strip() if payload.head_of_account else None
    if payload.academic_year_default is not None:
        club.academic_year_default = payload.academic_year_default.strip()
    if payload.department is not None:
        curr = dict(club.settings or {})
        curr["department"] = payload.department.strip()
        club.settings = curr
    if payload.settings is not None:
        curr = dict(club.settings or {})
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
                    position=m.position,
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
    if payload.position and payload.position.strip():
        membership.position = payload.position.strip()

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

    if membership.role == Role.OWNER and payload.role != Role.OWNER:
        other_owners = membership_repo.count(Membership.role == Role.OWNER, Membership.user_id != user_id)
        if other_owners == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SOLE_OWNER", "message": "A club needs at least one owner. Make someone else owner first."},
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


@router.get("/{club_id}/people/{person_id}/sensitive")
def reveal_person_mobile(
    person_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Show one official's full mobile number to a club admin; every reveal is recorded."""
    person = ScopedRepository(db, Person, club_id=ctx.club.id).get(person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    log_audit(
        db=db,
        action="sensitive_field_revealed",
        entity_type="person",
        entity_id=person.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"field": "mobile", "person": person.full_name},
        ip=request.client.host if request.client else None,
    )
    return {"field": "mobile", "value": decrypt_field(person.mobile) if person.mobile else None}


@router.get("/{club_id}/positions")
def list_positions(ctx: ClubContext = Depends(require_club_access(Role.VIEWER))):
    """Club positions people can hold (who signs which documents). Separate from app access roles."""
    from server.app.core.club_positions import POSITIONS

    return POSITIONS


@router.get("/{club_id}/people", response_model=list[PersonOut])
def list_people(
    reveal: bool = Query(False, description="Reveal plaintext sensitive fields (requires admin)"),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List people strictly through ScopedRepository with field masking and reveal permission."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    role_repo = ScopedRepository(db, RoleHeld, club_id=ctx.club.id)

    people = person_repo.all()
    all_roles = role_repo.all()

    roles_by_person: dict[str, list[RoleHeldOut]] = {}
    for r in all_roles:
        roles_by_person.setdefault(r.person_id, []).append(
            RoleHeldOut(
                id=r.id,
                person_id=r.person_id,
                role_key=r.role_key,
                designation_label=r.designation_label,
                academic_year=r.academic_year,
                created_at=r.created_at,
            )
        )

    can_reveal = reveal and ctx.is_admin

    out = []
    for p in people:
        decrypted_mobile = decrypt_field(p.mobile)
        display_mobile = decrypted_mobile if can_reveal else mask_sensitive_field(decrypted_mobile)
        p_roles = roles_by_person.get(p.id, [])
        primary_desig = p_roles[0].designation_label if p_roles else (p.notes or p.department)

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
                designation=primary_desig,
                mobile=display_mobile,
                email=p.email,
                notes=p.notes,
                roles=p_roles,
                created_at=p.created_at,
            )
        )
    return out


@router.post("/{club_id}/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a person with mobile encrypted at rest via ScopedRepository (admin only)."""
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

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="person_created",
        entity_type="person",
        entity_id=person.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"full_name": person.full_name, "department": person.department},
        ip=client_ip,
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
        roles=[],
        created_at=person.created_at,
    )


@router.put("/{club_id}/people/{person_id}", response_model=PersonOut)
def update_person(
    club_id: str,
    person_id: str,
    payload: PersonUpdate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update person details (admin only)."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    person = person_repo.get(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PERSON_NOT_FOUND", "message": "Person not found in this club"},
        )

    if payload.full_name is not None:
        person.full_name = payload.full_name.strip()
    if payload.roll_no is not None:
        person.roll_no = payload.roll_no.strip() if payload.roll_no else None
    if payload.branch is not None:
        person.branch = payload.branch.strip() if payload.branch else None
    if payload.department is not None:
        person.department = payload.department.strip() if payload.department else None
    if payload.email is not None:
        person.email = payload.email.strip() if payload.email else None
    if payload.notes is not None:
        person.notes = payload.notes
    if payload.mobile is not None:
        person.mobile = encrypt_field(payload.mobile) if payload.mobile else None

    db.commit()
    db.refresh(person)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="person_updated",
        entity_type="person",
        entity_id=person.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"full_name": person.full_name},
        ip=client_ip,
    )

    dec_mob = decrypt_field(person.mobile)
    return PersonOut(
        id=person.id,
        club_id=person.club_id,
        full_name=person.full_name,
        roll_no=person.roll_no,
        branch=person.branch,
        department=person.department,
        mobile=mask_sensitive_field(dec_mob) if dec_mob else None,
        email=person.email,
        notes=person.notes,
        roles=[
            RoleHeldOut(id=r.id, person_id=r.person_id, role_key=r.role_key, designation_label=r.designation_label,
                        academic_year=r.academic_year, created_at=r.created_at)
            for r in ScopedRepository(db, RoleHeld, club_id=ctx.club.id).all() if r.person_id == person.id
        ],
        created_at=person.created_at,
    )


@router.delete("/{club_id}/people/{person_id}")
def delete_person(
    club_id: str,
    person_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Delete a person and associated role assignments (admin only)."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    person = person_repo.get(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PERSON_NOT_FOUND", "message": "Person not found in this club"},
        )

    # Delete roles held first
    role_repo = ScopedRepository(db, RoleHeld, club_id=ctx.club.id)
    roles = role_repo.all(RoleHeld.person_id == person_id)
    for r in roles:
        db.delete(r)

    person_repo.delete(person_id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="person_deleted",
        entity_type="person",
        entity_id=person_id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"deleted_person_id": person_id},
        ip=client_ip,
    )
    return {"message": "Person deleted successfully"}


@router.post("/{club_id}/roles", response_model=RoleHeldOut, status_code=status.HTTP_201_CREATED)
def assign_role_held(
    club_id: str,
    payload: RoleHeldCreate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Assign a signatory role and designation label to a person (admin only)."""
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    person = person_repo.get(payload.person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PERSON_NOT_FOUND", "message": "Person not found in this club"},
        )

    role_repo = ScopedRepository(db, RoleHeld, club_id=ctx.club.id)
    r = role_repo.create(
        person_id=payload.person_id,
        role_key=payload.role_key.strip(),
        designation_label=payload.designation_label.strip(),
        academic_year=payload.academic_year.strip(),
    )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="role_assigned",
        entity_type="role_held",
        entity_id=r.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"role_key": r.role_key, "person_id": r.person_id, "designation": r.designation_label},
        ip=client_ip,
    )

    return RoleHeldOut(
        id=r.id,
        person_id=r.person_id,
        role_key=r.role_key,
        designation_label=r.designation_label,
        academic_year=r.academic_year,
        created_at=r.created_at,
    )


@router.put("/{club_id}/roles/{role_id}", response_model=RoleHeldOut)
def update_role_held(
    club_id: str,
    role_id: str,
    payload: RoleHeldUpdate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update a role assignment designation or academic year (admin only)."""
    role_repo = ScopedRepository(db, RoleHeld, club_id=ctx.club.id)
    r = role_repo.get(role_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_NOT_FOUND", "message": "Role assignment not found in this club"},
        )

    if payload.role_key is not None:
        r.role_key = payload.role_key.strip()
    if payload.designation_label is not None:
        r.designation_label = payload.designation_label.strip()
    if payload.academic_year is not None:
        r.academic_year = payload.academic_year.strip()

    db.commit()
    db.refresh(r)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="role_updated",
        entity_type="role_held",
        entity_id=r.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"role_key": r.role_key, "designation": r.designation_label},
        ip=client_ip,
    )

    return RoleHeldOut(
        id=r.id,
        person_id=r.person_id,
        role_key=r.role_key,
        designation_label=r.designation_label,
        academic_year=r.academic_year,
        created_at=r.created_at,
    )


@router.delete("/{club_id}/roles/{role_id}")
def delete_role_held(
    club_id: str,
    role_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Delete a role assignment (admin only)."""
    role_repo = ScopedRepository(db, RoleHeld, club_id=ctx.club.id)
    r = role_repo.get(role_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_NOT_FOUND", "message": "Role assignment not found in this club"},
        )
    role_repo.delete(role_id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="role_removed",
        entity_type="role_held",
        entity_id=role_id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"role_id": role_id},
        ip=client_ip,
    )
    return {"message": "Role assignment deleted successfully"}


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
            addressee_default=f"The Head of Department, {payload.chairman_dept}" if payload.chairman_dept else "The Head of Department",
        )

    # 6. Numbering Series from template schemas
    ay = payload.academic_year or ctx.club.academic_year_default
    from docgen.schema import load_all_schemas
    all_schemas = load_all_schemas()
    for s in all_schemas.values():
        if s.numbering and s.numbering.format:
            s_key = s.numbering.series or "EVENT"
            existing_s = num_repo.find_first(
                NumberingSeries.key == s_key,
                NumberingSeries.academic_year == ay,
            )
            if not existing_s:
                num_repo.create(
                    key=s_key,
                    format=s.numbering.format,
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
    from server.app.core.numbering_service import reserve_number_for_document

    academic_year = ctx.club.academic_year_default or (ctx.club.settings or {}).get("academic_year") or ""
    club_prefix = ctx.club.short_name or ctx.club.slug.upper()

    format_pattern = None
    if payload and payload.template_id:
        try:
            tmpl_row = db.query(Template).filter(
                (Template.id == payload.template_id) | (Template.slug == payload.template_id)
            ).first()
            if tmpl_row:
                ver = (
                    db.query(TemplateVersion)
                    .filter(TemplateVersion.template_id == tmpl_row.id)
                    .order_by(TemplateVersion.version_no.desc())
                    .first()
                )
                if ver and ver.schema_yaml:
                    import yaml
                    s_dict = yaml.safe_load(ver.schema_yaml)
                    num_cfg = s_dict.get("numbering", {})
                    if num_cfg and num_cfg.get("format"):
                        format_pattern = num_cfg["format"]
            if not format_pattern:
                tmpl_schema = load_schema(payload.template_id)
                if tmpl_schema.numbering and tmpl_schema.numbering.format:
                    format_pattern = tmpl_schema.numbering.format
        except Exception:
            pass

    event_code_val = (payload.event_code if payload and payload.event_code else series_key)
    try:
        reservation, ref_no = reserve_number_for_document(
            db=db,
            club_id=ctx.club.id,
            user_id=ctx.user.id,
            series_key=series_key,
            academic_year=academic_year,
            event_code=event_code_val,
            format_pattern=format_pattern,
            expiry_minutes=30,
            status="reserved",
            allow_create=True,
        )
        db.commit()
        db.refresh(reservation)
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NUMBERING_SERIES_NOT_FOUND", "message": str(e)},
        )

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
    """View audit trail strictly via ScopedRepository, with the name and email of who acted."""
    audit_repo = ScopedRepository(db, AuditLog, club_id=ctx.club.id)
    entries = audit_repo.list(skip=skip, limit=limit, order_by=AuditLog.created_at.desc())
    user_ids = {e.user_id for e in entries if e.user_id}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    out = []
    for e in entries:
        item = AuditLogOut.model_validate(e, from_attributes=True)
        actor = users.get(e.user_id)
        if actor:
            item.actor_name, item.actor_email = actor.name, actor.email
        out.append(item)
    return out


@router.post("/{club_id}/logo")
async def upload_club_logo(
    club_id: str,
    file: UploadFile = File(...),
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Upload and normalize a club logo (compositing RGBA onto white canvas)."""
    import hashlib
    from pathlib import Path
    from server.app.models import Asset, Letterhead
    from server.app.core.template_compiler import normalize_logo_image

    # Read at most one byte past the limit so a huge upload cannot exhaust memory
    content = await file.read(2 * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Uploaded file exceeds 2 MB limit")

    try:
        normalized_bytes = normalize_logo_image(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")

    storage = get_storage()
    storage_rel_path, sha256 = storage.save_content_addressed("assets", normalized_bytes, "png")
    # Storage implementations return a canonical relative key.  Do not prefix
    # it with ``storage/``: that made S3 keys unreadable and produced
    # ``storage/storage/...`` on local reads.
    dest_path = storage_rel_path

    # Check if this club already has an asset with this sha256
    existing_asset = (
        db.query(Asset)
        .filter(Asset.club_id == ctx.club.id, Asset.sha256 == sha256)
        .first()
    )

    if existing_asset:
        asset = existing_asset
    else:
        asset_id = str(uuid.uuid4())
        asset = Asset(
            id=asset_id,
            club_id=ctx.club.id,
            kind="logo",
            filename=file.filename or "logo.png",
            mime="image/png",
            sha256=sha256,
            size=len(normalized_bytes),
            storage_key=storage_rel_path,
            uploaded_by=ctx.user.id,
            is_system=False,
        )
        db.add(asset)
        db.flush()

    # The letterhead is generated from this logo; no letterhead record is kept.
    settings_dict = dict(ctx.club.settings or {})
    settings_dict["logo_asset_id"] = asset.id
    ctx.club.settings = settings_dict

    db.commit()
    db.refresh(asset)

    log_audit(
        db=db,
        action="club_logo_uploaded",
        entity_type="asset",
        entity_id=asset.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"filename": asset.filename, "size": asset.size},
    )

    return {
        "asset_id": asset.id,
        "filename": asset.filename,
        "url": f"/api/v1/assets/{asset.id}/content",
        "letterhead_id": None,  # the letterhead is generated from the logo
    }


class BrandingIn(BaseModel):
    logo_asset_id: Optional[str] = None


@router.put("/{club_id}/branding")
def set_club_branding(
    club_id: str,
    payload: BrandingIn,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Choose the club logo and/or letterhead banner from images already uploaded (admin only)."""
    from server.app.core.tenancy import get_asset_for_club

    settings = dict(ctx.club.settings or {})
    for field, value in (("logo_asset_id", payload.logo_asset_id),):
        if value is None:
            continue
        if value == "":
            settings.pop(field, None)
            continue
        if not get_asset_for_club(db, value, ctx.club.id):
            raise HTTPException(status_code=404, detail="Image not found for this club.")
        settings[field] = value
    ctx.club.settings = settings
    db.commit()
    log_audit(db=db, action="club_branding_updated", entity_type="club", entity_id=ctx.club.id, club_id=ctx.club.id,
              user_id=ctx.user.id, meta=payload.model_dump(exclude_none=True),
              ip=request.client.host if request.client else None)
    return {"logo_asset_id": settings.get("logo_asset_id")}


@router.get("/{club_id}/letterhead-banner")
def get_club_letterhead_banner(
    club_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """The letterhead banner this club's documents carry (uploaded, or composed from its logo)."""
    import os
    from pathlib import Path

    from fastapi.responses import FileResponse

    from docgen.letterhead_banner import club_banner_path
    from docgen.sources import build_club_config_from_db

    cfg = build_club_config_from_db(db, ctx.club.slug)
    banner = club_banner_path(
        Path(os.environ.get("STORAGE_LOCAL_ROOT", "storage")).resolve() / "cache" / "banners",
        cfg.letterhead_title or cfg.club_name,
        cfg.letterhead_subtitle or cfg.institute_name.split("(")[0],
        logo_path=cfg.club_logo_path,
        color=cfg.brand_color,
    )
    if not Path(banner).exists():
        raise HTTPException(status_code=404, detail="Banner not available")
    return FileResponse(str(banner), media_type="image/png", headers={"Cache-Control": "private, max-age=60"})


def _active_logo_asset(db: Session, club: Club):
    """The club's own logo: the one chosen in settings, else its letterhead logo, else the newest upload."""
    from server.app.models import Asset, Letterhead

    logo_asset_id = (club.settings or {}).get("logo_asset_id")
    asset = None
    if logo_asset_id:
        asset = db.query(Asset).filter(
            Asset.id == logo_asset_id, (Asset.club_id == club.id) | (Asset.club_id.is_(None))
        ).first()
    if not asset:
        lh = db.query(Letterhead).filter(Letterhead.club_id == club.id).first()
        if lh and lh.right_logo_asset_id:
            asset = db.query(Asset).filter(Asset.id == lh.right_logo_asset_id, Asset.club_id == club.id).first()
    if not asset:
        asset = db.query(Asset).filter(Asset.club_id == club.id, Asset.kind == "logo").order_by(Asset.created_at.desc()).first()
    return asset


def _serve_asset_image(asset):
    from fastapi.responses import FileResponse, Response
    from server.app.core.storage import LocalDiskStorage

    try:
        active_storage = get_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if isinstance(active_storage, LocalDiskStorage):
        f_path = active_storage.local_path(asset.storage_key)
        if not f_path.is_file():
            raise HTTPException(status_code=404, detail="Club logo file not found on storage")
        return FileResponse(str(f_path), media_type=asset.mime or "image/png", headers={"Cache-Control": "private, max-age=300"})
    try:
        return Response(content=active_storage.load(asset.storage_key), media_type=asset.mime or "image/png")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Club logo file not found on storage")


@router.get("/{club_id}/public-logo")
def get_club_public_logo(
    club_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A club's logo for any signed-in user (shown on the club list before joining)."""
    club = db.query(Club).filter(Club.id == club_id, Club.disabled_at.is_(None)).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    asset = _active_logo_asset(db, club)
    if not asset:
        raise HTTPException(status_code=404, detail="Club logo not found")
    return _serve_asset_image(asset)


@router.get("/{club_id}/logo")
def get_club_logo(
    club_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Serve the active logo asset for the club."""
    asset = _active_logo_asset(db, ctx.club)
    if not asset:
        raise HTTPException(status_code=404, detail="Club logo not found")
    return _serve_asset_image(asset)


# ---------------- INVITES (Club Admins create/list/revoke) ----------------


@router.post("/{club_id}/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def create_club_invite(
    club_id: str,
    payload: InviteCreate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create an invite (link/code with role and expiry, single-use or limited uses). Admin only."""
    import secrets
    from server.app.core.permissions import ROLE_RANKS

    from server.app.core.security import is_allowed_email, EMAIL_DOMAIN_ERROR_CODE, EMAIL_DOMAIN_REJECTION_MESSAGE
    target_email = payload.email.strip().lower() if payload.email else None
    if target_email and not is_allowed_email(target_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": EMAIL_DOMAIN_ERROR_CODE, "message": EMAIL_DOMAIN_REJECTION_MESSAGE},
        )

    target_role = payload.role.lower().strip()
    inviter_rank = ROLE_RANKS.get(ctx.role, 0)
    target_rank = ROLE_RANKS.get(target_role, 0)
    if not ctx.user.is_platform_admin and target_rank > inviter_rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROLE_EXCEEDS_INVITER", "message": "Cannot create an invite with a role higher than your own role."},
        )

    import hashlib
    raw_code = secrets.token_urlsafe(16)
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    expiry_days = payload.expiry_days or 7
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=expiry_days)
    max_uses = payload.max_uses if (payload.max_uses and payload.max_uses > 0) else 1

    invite = Invite(
        id=str(uuid.uuid4()),
        club_id=ctx.club.id,
        code_hash=code_hash,
        code=None,
        email_or_code=target_email,
        role=target_role,
        created_by=ctx.user.id,
        max_uses=max_uses,
        use_count=0,
        revoked=False,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="invite_created",
        entity_type="invite",
        entity_id=invite.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"code_hash": code_hash[:16], "role": invite.role, "max_uses": invite.max_uses, "expires_at": str(invite.expires_at)},
        ip=client_ip,
    )

    emailed, email_error = (None, None)
    if target_email:
        emailed, email_error = _email_invite(target_email, ctx, invite, raw_code)

    return InviteOut(
        id=invite.id,
        club_id=invite.club_id,
        code=raw_code,
        role=invite.role,
        created_by=invite.created_by,
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        revoked=invite.revoked,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        invite_link=f"/?invite={raw_code}",
        created_at=invite.created_at,
        emailed=emailed,
        email_error=email_error,
    )


def _email_invite(to_email: str, ctx: ClubContext, invite: Invite, raw_code: str) -> tuple[bool, Optional[str]]:
    """Email the invite link to the invited address. Best effort: the invite exists either way."""
    import logging
    import os
    from urllib.parse import quote

    from server.app.core.email import email_delivery_configured, get_email_sender

    if not email_delivery_configured():
        return False, "Email is not set up on this server, so copy the link and send it yourself."
    base = os.environ.get("APP_BASE_URL", "http://localhost:5173").rstrip("/")
    link = f"{base}/login?invite={quote(raw_code)}"
    inviter = ctx.user.name or ctx.user.email
    expires = invite.expires_at.strftime("%d/%m/%Y") if invite.expires_at else None
    details = f"{inviter} invited you as {invite.role}." + (f" The link works until {expires}." if expires else "")
    try:
        get_email_sender().send_invitation(to_email, ctx.club.name, link, details)
        return True, None
    except Exception as exc:
        logging.getLogger("clubdocs.invites").warning("Invite email to %s failed: %s", to_email, exc)
        return False, "The email could not be sent, so copy the link and send it yourself."


@router.get("/{club_id}/invites", response_model=list[InviteOut])
def list_club_invites(
    club_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """List all invites for the club. Admin only."""
    invites = (
        db.query(Invite)
        .filter(Invite.club_id == ctx.club.id)
        .order_by(Invite.created_at.desc())
        .all()
    )
    return [
        InviteOut(
            id=i.id,
            club_id=i.club_id,
            code=f"{i.code_hash[:8]}..." if i.code_hash else (i.code or "••••••••"),
            role=i.role,
            created_by=i.created_by,
            max_uses=i.max_uses,
            use_count=i.use_count,
            revoked=i.revoked,
            expires_at=i.expires_at,
            accepted_at=i.accepted_at,
            invite_link=f"/?invite={i.code_hash[:8]}...",
            created_at=i.created_at,
        )
        for i in invites
    ]


@router.post("/{club_id}/invites/{invite_id}/revoke")
def revoke_club_invite(
    club_id: str,
    invite_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Revoke an invite. Admin only."""
    invite = (
        db.query(Invite)
        .filter(Invite.id == invite_id, Invite.club_id == ctx.club.id)
        .first()
    )
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INVITE_NOT_FOUND", "message": "Invite not found in this club"},
        )
    invite.revoked = True
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="invite_revoked",
        entity_type="invite",
        entity_id=invite.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"code": invite.code},
        ip=client_ip,
    )
    return {"message": "Invite revoked successfully"}


# ---------------- VENUES (Editors view, Admins change) ----------------


@router.get("/{club_id}/venues", response_model=list[VenueOut])
def list_venues(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List venues for the club (editors/viewers can view)."""
    venue_repo = ScopedRepository(db, Venue, club_id=ctx.club.id)
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    venues = venue_repo.all()
    people = {p.id: p.full_name for p in person_repo.all()}

    return [
        VenueOut(
            id=v.id,
            club_id=v.club_id,
            name=v.name,
            short_name=v.short_name,
            location=v.short_name,
            addressee_default=v.addressee_default,
            addressee=v.addressee_default,
            tech_assistant_person_id=v.tech_assistant_person_id,
            tech_assistant_name=people.get(v.tech_assistant_person_id) if v.tech_assistant_person_id else None,
            tech_assistant=people.get(v.tech_assistant_person_id) if v.tech_assistant_person_id else None,
            faculty_incharge_person_id=v.faculty_incharge_person_id,
            faculty_incharge_name=people.get(v.faculty_incharge_person_id) if v.faculty_incharge_person_id else None,
            faculty_in_charge=people.get(v.faculty_incharge_person_id) if v.faculty_incharge_person_id else None,
            created_at=v.created_at,
        )
        for v in venues
    ]


@router.post("/{club_id}/venues", response_model=VenueOut, status_code=status.HTTP_201_CREATED)
def create_venue(
    club_id: str,
    payload: VenueCreate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a new venue (admin only)."""
    venue_repo = ScopedRepository(db, Venue, club_id=ctx.club.id)
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)

    raw_short = payload.short_name or payload.location
    raw_addressee = payload.addressee_default or payload.addressee

    venue = venue_repo.create(
        name=payload.name.strip(),
        short_name=raw_short.strip() if raw_short else None,
        addressee_default=raw_addressee.strip() if raw_addressee else None,
        tech_assistant_person_id=payload.tech_assistant_person_id,
        faculty_incharge_person_id=payload.faculty_incharge_person_id,
    )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="venue_created",
        entity_type="venue",
        entity_id=venue.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"name": venue.name},
        ip=client_ip,
    )

    ta = person_repo.get(venue.tech_assistant_person_id) if venue.tech_assistant_person_id else None
    fi = person_repo.get(venue.faculty_incharge_person_id) if venue.faculty_incharge_person_id else None

    return VenueOut(
        id=venue.id,
        club_id=venue.club_id,
        name=venue.name,
        short_name=venue.short_name,
        location=venue.short_name,
        addressee_default=venue.addressee_default,
        addressee=venue.addressee_default,
        tech_assistant_person_id=venue.tech_assistant_person_id,
        tech_assistant_name=ta.full_name if ta else None,
        tech_assistant=ta.full_name if ta else None,
        faculty_incharge_person_id=venue.faculty_incharge_person_id,
        faculty_incharge_name=fi.full_name if fi else None,
        faculty_in_charge=fi.full_name if fi else None,
        created_at=venue.created_at,
    )


@router.put("/{club_id}/venues/{venue_id}", response_model=VenueOut)
def update_venue(
    club_id: str,
    venue_id: str,
    payload: VenueUpdate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update venue details (admin only)."""
    venue_repo = ScopedRepository(db, Venue, club_id=ctx.club.id)
    person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
    venue = venue_repo.get(venue_id)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VENUE_NOT_FOUND", "message": "Venue not found in this club"},
        )

    if payload.name is not None:
        venue.name = payload.name.strip()
    raw_short = payload.short_name if payload.short_name is not None else payload.location
    if raw_short is not None:
        venue.short_name = raw_short.strip() if raw_short else None
    raw_addressee = payload.addressee_default if payload.addressee_default is not None else payload.addressee
    if raw_addressee is not None:
        venue.addressee_default = raw_addressee.strip() if raw_addressee else None
    if payload.tech_assistant_person_id is not None:
        venue.tech_assistant_person_id = payload.tech_assistant_person_id or None
    if payload.faculty_incharge_person_id is not None:
        venue.faculty_incharge_person_id = payload.faculty_incharge_person_id or None

    db.commit()
    db.refresh(venue)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="venue_updated",
        entity_type="venue",
        entity_id=venue.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"name": venue.name},
        ip=client_ip,
    )

    ta = person_repo.get(venue.tech_assistant_person_id) if venue.tech_assistant_person_id else None
    fi = person_repo.get(venue.faculty_incharge_person_id) if venue.faculty_incharge_person_id else None

    return VenueOut(
        id=venue.id,
        club_id=venue.club_id,
        name=venue.name,
        short_name=venue.short_name,
        location=venue.short_name,
        addressee_default=venue.addressee_default,
        addressee=venue.addressee_default,
        tech_assistant_person_id=venue.tech_assistant_person_id,
        tech_assistant_name=ta.full_name if ta else None,
        tech_assistant=ta.full_name if ta else None,
        faculty_incharge_person_id=venue.faculty_incharge_person_id,
        faculty_incharge_name=fi.full_name if fi else None,
        faculty_in_charge=fi.full_name if fi else None,
        created_at=venue.created_at,
    )


@router.delete("/{club_id}/venues/{venue_id}")
def delete_venue(
    club_id: str,
    venue_id: str,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Delete a venue (admin only)."""
    venue_repo = ScopedRepository(db, Venue, club_id=ctx.club.id)
    venue = venue_repo.get(venue_id)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VENUE_NOT_FOUND", "message": "Venue not found in this club"},
        )
    venue_repo.delete(venue_id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="venue_deleted",
        entity_type="venue",
        entity_id=venue_id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"venue_id": venue_id},
        ip=client_ip,
    )
    return {"message": "Venue deleted successfully"}


# ---------------- NUMBERING SERIES (Editors view, Admins change) ----------------


@router.get("/{club_id}/numbering", response_model=list[NumberingSeriesOut])
def list_numbering_series(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List all numbering series, current counter values, and format patterns (editors/viewers can view)."""
    series_repo = ScopedRepository(db, NumberingSeries, club_id=ctx.club.id)
    series = series_repo.all()
    used_by = _series_template_names(db, ctx.club.id)
    return [
        NumberingSeriesOut(
            id=s.id,
            club_id=s.club_id,
            key=s.key,
            series_key=s.key,
            format=s.format,
            academic_year=s.academic_year,
            last_seq=s.last_seq,
            current_counter=s.last_seq,
            description=", ".join(used_by.get(s.key.upper(), [])) or LEGACY_SERIES_NAMES.get(s.key.upper()),
            used_by=used_by.get(s.key.upper(), []),
            created_at=s.created_at,
        )
        for s in series
    ]


# Series keys that are not tied to one template's schema
LEGACY_SERIES_NAMES = {
    "DOC": "General documents",
    "EVT": "Events",
    "EVENT": "Events",
}


def _series_template_names(db: Session, club_id: str) -> dict[str, list[str]]:
    """Series key (upper case) -> names of the club's and built-in templates that number with it."""
    import yaml

    from server.app.models import Template, TemplateVersion

    out: dict[str, list[str]] = {}
    templates = db.query(Template).filter(
        (Template.club_id == club_id) | (Template.club_id.is_(None)), Template.status != "archived"
    ).all()
    for t in templates:
        ver = db.query(TemplateVersion).filter(TemplateVersion.id == t.current_version_id).first()
        try:
            schema = yaml.safe_load(ver.schema_yaml) if ver and ver.schema_yaml else {}
        except Exception:
            schema = {}
        # Some series are keyed by the template slug (e.g. approval_note numbers by event code)
        key = ((schema or {}).get("numbering") or {}).get("series") or t.slug
        if key:
            names = out.setdefault(str(key).upper(), [])
            if t.name not in names:
                names.append(t.name)
    return out


@router.post("/{club_id}/numbering", response_model=NumberingSeriesOut, status_code=status.HTTP_201_CREATED)
def create_numbering_series(
    club_id: str,
    payload: NumberingSeriesCreate,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a new numbering series (admin only)."""
    series_repo = ScopedRepository(db, NumberingSeries, club_id=ctx.club.id)
    existing = series_repo.find_first(
        NumberingSeries.key == payload.key.strip(),
        NumberingSeries.academic_year == payload.academic_year.strip(),
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SERIES_EXISTS", "message": f"Numbering series '{payload.key}' already exists for academic year '{payload.academic_year}'"},
        )

    s = series_repo.create(
        key=payload.key.strip(),
        format=payload.format.strip(),
        academic_year=payload.academic_year.strip(),
        last_seq=payload.last_seq,
    )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="numbering_series_created",
        entity_type="numbering_series",
        entity_id=s.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"key": s.key, "format": s.format, "academic_year": s.academic_year},
        ip=client_ip,
    )

    return NumberingSeriesOut(
        id=s.id,
        club_id=s.club_id,
        key=s.key,
        format=s.format,
        academic_year=s.academic_year,
        last_seq=s.last_seq,
        created_at=s.created_at,
    )


@router.put("/{club_id}/numbering/{series_key}", response_model=NumberingSeriesOut)
def update_numbering_series_format(
    club_id: str,
    series_key: str,
    payload: NumberingSeriesUpdate,
    academic_year: Optional[str] = Query(None),
    request: Request = None,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Update format pattern of a numbering series. Changing format NEVER rewrites existing numbers (admin only)."""
    ay = academic_year or ctx.club.academic_year_default or ""
    series_repo = ScopedRepository(db, NumberingSeries, club_id=ctx.club.id)
    s = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == ay,
    )
    if not s:
        matches = series_repo.filter(NumberingSeries.key == series_key)
        if matches:
            s = matches[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SERIES_NOT_FOUND", "message": f"Numbering series '{series_key}' not found"},
            )

    old_format = s.format
    s.format = payload.format.strip()
    db.commit()
    db.refresh(s)

    client_ip = request.client.host if request and request.client else None
    log_audit(
        db=db,
        action="numbering_series_format_updated",
        entity_type="numbering_series",
        entity_id=s.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"key": s.key, "old_format": old_format, "new_format": s.format},
        ip=client_ip,
    )

    return NumberingSeriesOut(
        id=s.id,
        club_id=s.club_id,
        key=s.key,
        series_key=s.key,
        format=s.format,
        academic_year=s.academic_year,
        last_seq=s.last_seq,
        current_counter=s.last_seq,
        created_at=s.created_at,
    )


# ---------------- LETTERHEADS & ASSETS (Editors view, Admins change) ----------------


@router.get("/{club_id}/assets", response_model=list[AssetOut])
def list_club_assets(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List club and system assets (logos, letterhead crests). Editors/viewers can view."""
    assets = (
        db.query(Asset)
        .filter(
            (Asset.club_id == ctx.club.id)
            | ((Asset.is_system.is_(True)) & (Asset.club_id.is_(None)))
        )
        .order_by(Asset.created_at.desc())
        .all()
    )
    return [
        AssetOut(
            id=a.id,
            club_id=a.club_id,
            kind=a.kind,
            filename=a.filename,
            mime=a.mime,
            size=a.size,
            is_system=a.is_system,
            url=f"/api/v1/assets/{a.id}/content",
            created_at=a.created_at,
        )
        for a in assets
    ]


@router.get("/{club_id}/storage-stats")
def get_club_storage_stats(
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Return storage metrics and retention configuration for the current club."""
    from server.app.models import Document, DocumentVersion, Template, TemplateVersion
    from server.app.core.storage import KEEP_VERSION_FILES, PREVIEW_TTL_DAYS, BATCH_TTL_HOURS, require_local_storage
    from pathlib import Path

    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    from server.app.core.scoped_repo import ScopedRepository
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    doc_ids = [d.id for d in doc_repo.all()]
    doc_bytes = 0
    doc_files = 0
    preview_bytes = 0
    preview_files = 0

    if doc_ids:
        versions = db.query(DocumentVersion).filter(DocumentVersion.document_id.in_(doc_ids)).all()
        for v in versions:
            for k in (v.docx_key, v.pdf_key):
                if k:
                    fp = local_storage.local_path(k)
                    if fp.exists():
                        doc_files += 1
                        doc_bytes += fp.stat().st_size

        cache_prev = local_storage.base_dir / "cache" / "previews"
        if cache_prev.exists():
            for d_id in doc_ids:
                for pf in cache_prev.glob(f"{d_id}_*"):
                    if pf.is_file():
                        preview_files += 1
                        preview_bytes += pf.stat().st_size

    tmpl_bytes = 0
    tmpl_files = 0
    club_tmpls = db.query(Template).filter(Template.club_id == ctx.club.id).all()
    for t in club_tmpls:
        t_vers = db.query(TemplateVersion).filter(TemplateVersion.template_id == t.id).all()
        for tv in t_vers:
            if tv.docx_storage_key:
                fp = local_storage.local_path(tv.docx_storage_key)
                if fp.exists():
                    tmpl_files += 1
                    tmpl_bytes += fp.stat().st_size

    total_bytes = doc_bytes + preview_bytes + tmpl_bytes

    return {
        "club_id": ctx.club.id,
        "club_name": ctx.club.name,
        "usage": {
            "documents_bytes": doc_bytes,
            "documents_files": doc_files,
            "previews_bytes": preview_bytes,
            "previews_files": preview_files,
            "templates_bytes": tmpl_bytes,
            "templates_files": tmpl_files,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
        },
        "retention_settings": {
            "keep_version_files": KEEP_VERSION_FILES,
            "preview_ttl_days": PREVIEW_TTL_DAYS,
            "batch_ttl_hours": BATCH_TTL_HOURS,
            "description": "Latest 3 versions of each document are preserved on disk. Older versions are pruned safely and can be regenerated on-demand from original snapshots. Previews cache expires after 7 days.",
        },
    }


@router.post("/{club_id}/storage-gc")
def run_club_storage_gc(
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Run a safe storage garbage collection pass for this club."""
    from server.scripts.storage_gc import run_storage_gc
    report = run_storage_gc(apply=True, club_id=ctx.club.id)
    return {
        "message": f"Storage cleanup completed. Reclaimed {round(report.total_bytes_freed / 1024, 2)} KB.",
        "freed_bytes": report.total_bytes_freed,
        "orphans_removed": report.orphans_count,
        "expired_previews_removed": report.expired_previews_count,
        "expired_batches_removed": report.expired_batches_count,
        "pruned_versions_removed": report.pruned_versions_count,
    }
