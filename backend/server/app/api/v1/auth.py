"""Authentication API routes with strict security, rate limiting, and cookie transport."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import uuid
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.config import settings
from server.app.core.database import get_db
from server.app.core.demo_club import join_demo_club
from server.app.core.email import get_email_sender
from server.app.core.permissions import get_current_user
from server.app.core.rate_limit import check_rate_limit
from server.app.core.scoped_repo import ScopedRepository
from server.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    generate_csrf_token,
    generate_reset_token,
    get_password_hash,
    hash_token,
    validate_password_policy,
    verify_password,
    is_allowed_email,
    EMAIL_DOMAIN_ERROR_CODE,
    EMAIL_DOMAIN_REJECTION_MESSAGE,
)
from server.app.models import Club, Invite, Membership, User
from server.app.schemas.auth import (
    ClubMembershipSummary,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserLogin,
    UserOut,
    UserRegister,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_secure_cookie() -> bool:
    return settings.ENVIRONMENT not in ("development", "test", "dev")


def _build_user_out(user: User, db: Session) -> UserOut:
    """Build UserOut with current active club memberships."""
    summaries = []
    for m in user.memberships:
        if m.status == "active":
            club = db.query(Club).filter(Club.id == m.club_id).first()
            if club:
                summaries.append(
                    ClubMembershipSummary(
                        club_id=club.id,
                        club_name=club.name,
                        club_slug=club.slug,
                        club_short=club.short_name,
                        role=m.role,
                        position=m.position,
                        status=m.status,
                    )
                )

    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        is_platform_admin=user.is_platform_admin,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        memberships=summaries,
        has_password=bool(user.password_hash),
        uses_google=bool(user.google_sub),
        demo_club_slug=settings.DEMO_CLUB_SLUG or None,
    )


def _set_auth_cookies(response: Response, user: User) -> tuple[str, str, str]:
    """Set secure httpOnly access and refresh tokens, and readable CSRF cookie."""
    access_token = create_access_token(user.id, user.email, user.token_version)
    refresh_token = create_refresh_token(user.id, user.token_version)
    csrf_token = generate_csrf_token()

    secure_flag = _is_secure_cookie()

    # Access Token (15-30 min, httpOnly)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=secure_flag,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Refresh Token (7 days, httpOnly)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=secure_flag,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )

    # CSRF Token (Readable by browser JavaScript to send in X-CSRF-Token header)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=secure_flag,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )

    return access_token, refresh_token, csrf_token


@router.get("/csrf")
def get_csrf(response: Response):
    """Retrieve or rotate CSRF token cookie."""
    token = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        samesite="lax",
        secure=_is_secure_cookie(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    return {"csrf_token": token}


def _validate_invite_code(
    invite_code: Optional[str],
    db: Session,
    client_ip: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Optional[Invite]:
    """Validate an invite code for registration or Google sign-in."""
    if not invite_code or not invite_code.strip():
        return None

    clean_inv = invite_code.strip()
    inv_hash = hashlib.sha256(clean_inv.encode("utf-8")).hexdigest()
    invite_obj = (
        db.query(Invite)
        .filter((Invite.code_hash == inv_hash) | (Invite.code == inv_hash) | (Invite.code == clean_inv))
        .first()
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        not invite_obj
        or invite_obj.revoked
        or (invite_obj.expires_at and invite_obj.expires_at < now)
        or (invite_obj.max_uses > 0 and invite_obj.use_count >= invite_obj.max_uses)
    ):
        log_audit(
            db=db,
            action="invite_failed",
            entity_type="invite",
            entity_id=invite_obj.id if invite_obj else None,
            club_id=invite_obj.club_id if invite_obj else None,
            user_id=None,
            meta={"code_hash": inv_hash[:16], "reason": "invalid_or_expired"},
            ip=client_ip,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_OR_EXPIRED_INVITE", "message": "Invalid or expired invite"},
        )

    # If invite is tied to a specific email, verify match
    if invite_obj.email_or_code and "@" in invite_obj.email_or_code and user_email:
        if invite_obj.email_or_code.strip().lower() != user_email.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "EMAIL_MISMATCH", "message": "This invite was created for a different email address."},
            )

    return invite_obj


def _apply_invite_to_user(
    invite_obj: Invite,
    user: User,
    db: Session,
    client_ip: Optional[str] = None,
) -> Membership:
    """Create or update club membership from invite and record audit log."""
    repo = ScopedRepository(db, Membership, club_id=invite_obj.club_id)
    existing_m = repo.find_first(Membership.user_id == user.id)
    if existing_m:
        if existing_m.status != "active":
            existing_m.status = "active"
            existing_m.role = invite_obj.role
            m = existing_m
        else:
            from server.app.core.permissions import ROLE_RANKS
            if ROLE_RANKS.get(invite_obj.role, 0) > ROLE_RANKS.get(existing_m.role, 0):
                existing_m.role = invite_obj.role
            m = existing_m
    else:
        m = repo.create(
            user_id=user.id,
            role=invite_obj.role,
            status="active",
        )

    invite_obj.use_count += 1
    if invite_obj.max_uses > 0 and invite_obj.use_count >= invite_obj.max_uses:
        invite_obj.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()

    log_audit(
        db=db,
        action="invite_accepted",
        entity_type="membership",
        entity_id=m.id,
        club_id=invite_obj.club_id,
        user_id=user.id,
        meta={"code": invite_obj.code, "role": invite_obj.role, "email": user.email},
        ip=client_ip,
    )
    return m


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    """Register a new user account with rate limiting, password policy, and domain check."""
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting: max 10 registrations per hour per IP
    check_rate_limit(f"reg_ip_{client_ip}", max_requests=60, window_seconds=3600, db=db)

    clean_email = payload.email.lower().strip()

    invite_obj = _validate_invite_code(payload.invite_code, db, client_ip, user_email=clean_email)

    # Reject emails failing institution domain policy
    if not is_allowed_email(clean_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": EMAIL_DOMAIN_ERROR_CODE, "message": EMAIL_DOMAIN_REJECTION_MESSAGE},
        )

    try:
        validate_password_policy(payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WEAK_PASSWORD", "message": str(e)},
        )

    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_EXISTS", "message": "Email is already registered"},
        )

    user = User(
        email=clean_email,
        name=payload.name.strip(),
        password_hash=get_password_hash(payload.password),
        email_verified_at=datetime.now(timezone.utc),
        token_version=1,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    join_demo_club(db, user, client_ip)

    if invite_obj:
        _apply_invite_to_user(invite_obj, user, db, client_ip)

    log_audit(
        db=db,
        action="user_registered",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        meta={"email": user.email, "name": user.name},
        ip=client_ip,
    )

    access_token, refresh_token, csrf_token = _set_auth_cookies(response, user)
    user_out = _build_user_out(user, db)

    # Return tokens for API/client storage; browser client also sets secure cookies
    return TokenResponse(
        user=user_out,
        csrf_token=csrf_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/google", response_model=TokenResponse)
def google_auth(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Sign in or register using Google OAuth ID token (SVNIT emails only)."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "GOOGLE_AUTH_NOT_CONFIGURED", "message": "Google sign-in is not configured"},
        )

    client_ip = request.client.host if request.client else "unknown"

    # 1. Rate limit with existing check_rate_limit, like /login (per IP)
    check_rate_limit(f"login_ip_{client_ip}", max_requests=60, window_seconds=60, db=db)

    # 2. Verify ID token with google-auth
    import google.auth.transport.requests
    import google.oauth2.id_token

    try:
        transport_req = google.auth.transport.requests.Request()
        claims = google.oauth2.id_token.verify_oauth2_token(
            payload.credential,
            transport_req,
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Google sign-in failed, please try again"},
        )

    # 3. Require claims["iss"] in {"accounts.google.com", "https://accounts.google.com"} and email_verified is True
    iss = claims.get("iss")
    if iss not in {"accounts.google.com", "https://accounts.google.com"} or claims.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Google sign-in failed, please try again"},
        )

    # 4. Apply is_allowed_email(claims["email"]) -> 403 with rejection message
    google_email = (claims.get("email") or "").strip().lower()
    if not is_allowed_email(google_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": EMAIL_DOMAIN_ERROR_CODE, "message": EMAIL_DOMAIN_REJECTION_MESSAGE},
        )

    # If invite_code is given, validate it upfront (before modifying database)
    invite_obj = None
    if payload.invite_code:
        invite_obj = _validate_invite_code(payload.invite_code, db, client_ip, user_email=google_email)

    # 5. Find the user:
    #    - first by google_sub == claims["sub"]
    #    - else by lowercased email
    sub = str(claims["sub"])
    user = db.query(User).filter(User.google_sub == sub).first()
    is_new_user = False

    if not user:
        user = db.query(User).filter(User.email == google_email).first()
        if user:
            if not user.google_sub:
                user.google_sub = sub
                db.flush()
            elif user.google_sub != sub:
                # Same address, different Google identity (e.g. the mailbox was re-issued)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "GOOGLE_ACCOUNT_MISMATCH",
                        "message": "This email is linked to a different Google account. Please contact your platform admin.",
                    },
                )
        else:
            is_new_user = True
            name = (claims.get("name") or google_email.split("@")[0]).strip()
            user = User(
                email=google_email,
                name=name,
                password_hash=None,
                email_verified_at=datetime.now(timezone.utc),
                token_version=1,
                google_sub=sub,
            )
            db.add(user)
            db.flush()
            db.refresh(user)
            join_demo_club(db, user, client_ip)

    # 6. Respect existing account states the same way /login does (disabled, locked)
    now = datetime.now(timezone.utc)
    if not is_new_user:
        if user.locked_until:
            locked_until_dt = user.locked_until
            if locked_until_dt.tzinfo is None:
                locked_until_dt = locked_until_dt.replace(tzinfo=timezone.utc)
            if locked_until_dt > now:
                remaining = int((locked_until_dt - now).total_seconds())
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "ACCOUNT_LOCKED",
                        "message": f"Account temporarily locked due to repeated failed logins. Retry in {remaining} seconds.",
                    },
                )
            else:
                user.locked_until = None
                user.failed_login_attempts = 0

        if user.disabled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_DISABLED", "message": "Account has been deactivated"},
            )

    # 7. Apply invite code if provided
    if invite_obj:
        _apply_invite_to_user(invite_obj, user, db, client_ip)

    # First admins on a fresh deployment (no shell on free hosts to run create_admin)
    if google_email in settings.PLATFORM_ADMIN_EMAILS and not user.is_platform_admin:
        user.is_platform_admin = True
        log_audit(
            db=db,
            action="platform_admin_granted",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            meta={"source": "PLATFORM_ADMIN_EMAILS", "email": user.email},
            ip=client_ip,
        )

    # 8. Reset lockout/failure counters, update last_login_at, write audit logs
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.flush()

    if is_new_user:
        log_audit(
            db=db,
            action="user_registered",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            meta={"method": "google", "email": user.email, "name": user.name},
            ip=client_ip,
        )
    else:
        log_audit(
            db=db,
            action="user_login",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            meta={"method": "google", "email": user.email},
            ip=client_ip,
        )

    # 9. Log in with existing _set_auth_cookies(response, user) and return TokenResponse
    access_token, refresh_token, csrf_token = _set_auth_cookies(response, user)
    user_out = _build_user_out(user, db)

    return TokenResponse(
        user=user_out,
        csrf_token=csrf_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate with rate limiting, account lockout, and httpOnly cookie delivery."""
    client_ip = request.client.host if request.client else "unknown"
    clean_email = payload.email.lower().strip()

    # Rate limiting: max 5 login attempts per minute per IP, and per email
    check_rate_limit(f"login_ip_{client_ip}", max_requests=60, window_seconds=60, db=db)
    check_rate_limit(f"login_email_{clean_email}", max_requests=10, window_seconds=60, db=db)

    # Reject non-institute emails before looking up user
    if not is_allowed_email(clean_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": EMAIL_DOMAIN_ERROR_CODE, "message": EMAIL_DOMAIN_REJECTION_MESSAGE},
        )

    user = db.query(User).filter(User.email == clean_email).first()

    now = datetime.now(timezone.utc)

    if user:
        # Google-only accounts do not have a password
        if user.password_hash is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "GOOGLE_AUTH_REQUIRED",
                    "message": "This account uses Google sign-in. Please use 'Sign in with Google'.",
                },
            )

        # Check lockout
        if user.locked_until:
            # Handle timezone-naive datetimes from SQLite
            locked_until_dt = user.locked_until
            if locked_until_dt.tzinfo is None:
                locked_until_dt = locked_until_dt.replace(tzinfo=timezone.utc)
            if locked_until_dt > now:
                remaining = int((locked_until_dt - now).total_seconds())
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "ACCOUNT_LOCKED",
                        "message": f"Account temporarily locked due to repeated failed logins. Retry in {remaining} seconds.",
                    },
                )
            else:
                user.locked_until = None
                user.failed_login_attempts = 0

    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                log_audit(
                    db=db,
                    action="account_lockout_triggered",
                    entity_type="user",
                    entity_id=user.id,
                    user_id=user.id,
                    meta={"failed_attempts": user.failed_login_attempts},
                    ip=client_ip,
                )
            db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    if user.disabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "Account has been deactivated"},
        )

    # Reset failure tracking
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.flush()

    log_audit(
        db=db,
        action="user_login",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        meta={"email": user.email},
        ip=client_ip,
    )

    access_token, refresh_token, csrf_token = _set_auth_cookies(response, user)
    user_out = _build_user_out(user, db)

    return TokenResponse(
        user=user_out,
        csrf_token=csrf_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/token", response_model=TokenResponse)
async def login_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """OAuth2 compatible form login."""
    form_data = await request.form()
    username = form_data.get("username") or form_data.get("email")
    password = form_data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INPUT", "message": "Username and password required"})
    payload = UserLogin(email=str(username), password=str(password))
    return login(payload, request, response, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    refresh_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
    auth_refresh: Optional[str] = Header(default=None, alias="X-Refresh-Token"),
    db: Session = Depends(get_db),
):
    """Rotate access token using valid httpOnly refresh token cookie, payload, or header."""
    raw_token = refresh_token or (payload.refresh_token if payload else None) or auth_refresh
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MISSING_REFRESH_TOKEN", "message": "Refresh token required"},
        )

    token_payload = decode_access_token(raw_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"},
        )

    user = db.query(User).filter(User.id == token_payload.get("sub")).first()
    if not user or user.disabled_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "UNAUTHORIZED"})

    if token_payload.get("token_version") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_REVOKED", "message": "Session revoked. Please sign in again."},
        )

    access_token, new_refresh_token, csrf_token = _set_auth_cookies(response, user)
    return TokenResponse(
        user=_build_user_out(user, db),
        csrf_token=csrf_token,
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current authenticated user profile and club memberships."""
    return _build_user_out(current_user, db)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UpdateProfileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the display name shown in the app and on audit entries."""
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "NAME_REQUIRED", "message": "Enter your name."})
    old_name = current_user.name
    current_user.name = name
    db.flush()
    log_audit(
        db=db,
        action="profile_updated",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        meta={"old_name": old_name, "new_name": name},
        ip=request.client.host if request.client else None,
    )
    return _build_user_out(current_user, db)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change (or, for Google-only accounts, set) the password.

    Signs out every other session; this browser gets fresh tokens and stays signed in.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"change_password_{current_user.id}", max_requests=5, window_seconds=900, db=db)

    if current_user.password_hash:
        if not payload.current_password or not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WRONG_PASSWORD", "message": "Your current password is not correct."},
            )
        if verify_password(payload.new_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SAME_PASSWORD", "message": "Choose a password different from the current one."},
            )
    try:
        validate_password_policy(payload.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "WEAK_PASSWORD", "message": str(e)})

    had_password = bool(current_user.password_hash)
    current_user.password_hash = get_password_hash(payload.new_password)
    current_user.token_version += 1
    db.flush()
    log_audit(
        db=db,
        action="password_changed" if had_password else "password_set",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        ip=client_ip,
    )

    access_token, refresh_token, csrf_token = _set_auth_cookies(response, current_user)
    return TokenResponse(
        user=_build_user_out(current_user, db),
        csrf_token=csrf_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/sign-out-others", response_model=TokenResponse)
def sign_out_other_devices(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End every other session (lost phone, shared lab computer); this browser stays signed in."""
    current_user.token_version += 1
    db.flush()
    log_audit(
        db=db,
        action="sessions_revoked",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
    access_token, refresh_token, csrf_token = _set_auth_cookies(response, current_user)
    return TokenResponse(
        user=_build_user_out(current_user, db),
        csrf_token=csrf_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke user sessions server-side and clear authentication cookies."""
    # Increment token_version to immediately revoke all existing JWTs for this user
    current_user.token_version += 1
    db.flush()

    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    response.delete_cookie(key="csrf_token", path="/")

    log_audit(
        db=db,
        action="user_logout",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        meta={"revoked_token_version": current_user.token_version},
    )
    return {"message": "Logged out successfully. All sessions revoked."}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generate and dispatch a single-use 30-minute password reset token via EmailSender.

    NEVER returns the token in the response JSON. Returns an identical enumeration-safe message.
    """
    clean_email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()

    # Do not send reset emails to Google-only accounts or non-allowed domains
    if user and user.password_hash and is_allowed_email(user.email):
        raw_token, token_hash = generate_reset_token()
        now = datetime.now(timezone.utc)
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
        user.password_reset_used_at = None
        db.flush()

        # Dispatch via EmailSender (logs reset link to server log in dev)
        sender = get_email_sender()
        sender.send_password_reset(user.email, raw_token)

        log_audit(
            db=db,
            action="password_reset_requested",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            meta={"email": user.email},
        )

    # Identical message returned whether email exists or not to prevent user enumeration
    return {"message": "If this email is registered, password reset instructions have been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using single-use reset token, enforcing 30-min expiry and revoking sessions."""
    try:
        validate_password_policy(payload.new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WEAK_PASSWORD", "message": str(e)},
        )

    incoming_hash = hash_token(payload.token.strip())
    user = db.query(User).filter(User.password_reset_token_hash == incoming_hash).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RESET_TOKEN", "message": "Invalid or expired password reset token"},
        )

    if user.password_reset_used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TOKEN_ALREADY_USED", "message": "This password reset token has already been used."},
        )

    now = datetime.now(timezone.utc)
    expires_at = user.password_reset_expires_at
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "TOKEN_EXPIRED", "message": "Password reset token has expired (30 minute limit)."},
            )

    # Update password
    user.password_hash = get_password_hash(payload.new_password)
    user.password_reset_used_at = now
    user.password_reset_token_hash = None
    # Invalidate existing sessions
    user.token_version += 1
    db.flush()

    log_audit(
        db=db,
        action="password_reset_completed",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
    )

    return {"message": "Password has been successfully updated. Please sign in with your new password."}
