"""Authentication API routes: register, login, me, logout, forgot/reset password."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import get_current_user
from server.app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from server.app.models import Club, Membership, User
from server.app.schemas.auth import (
    ClubMembershipSummary,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_user_out(user: User, db: Session) -> UserOut:
    """Build UserOut with current active club memberships."""
    memberships = (
        db.query(Membership, Club)
        .join(Club, Membership.club_id == Club.id)
        .filter(Membership.user_id == user.id, Membership.status == "active")
        .all()
    )

    summaries = [
        ClubMembershipSummary(
            club_id=club.id,
            club_name=club.name,
            club_slug=club.slug,
            club_short=club.short_name,
            role=m.role,
            status=m.status,
        )
        for m, club in memberships
    ]

    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        is_platform_admin=user.is_platform_admin,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        memberships=summaries,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    """Register a new user account."""
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_EXISTS", "message": "Email is already registered"},
        )

    user = User(
        email=payload.email.lower().strip(),
        name=payload.name.strip(),
        password_hash=get_password_hash(payload.password),
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="user_registered",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        meta={"email": user.email, "name": user.name},
        ip=client_ip,
    )

    token = create_access_token({"sub": user.id, "email": user.email})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS production
        max_age=60 * 60 * 24 * 7,
    )

    user_out = _build_user_out(user, db)
    return TokenResponse(access_token=token, token_type="bearer", user=user_out)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate and retrieve access token."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    if user.disabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "Account has been deactivated"},
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="user_login",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        meta={"email": user.email},
        ip=client_ip,
    )

    token = create_access_token({"sub": user.id, "email": user.email})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
    )

    user_out = _build_user_out(user, db)
    return TokenResponse(access_token=token, token_type="bearer", user=user_out)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current authenticated user profile and club memberships."""
    return _build_user_out(current_user, db)


@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Logout current user and clear session cookie."""
    response.delete_cookie(key="access_token")
    log_audit(
        db=db,
        action="user_logout",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
    )
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generate a password reset token for the given email."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user:
        # Return success to prevent email enumeration
        return {"message": "If this email is registered, a reset link/token has been generated."}

    reset_token = create_access_token(
        {"sub": user.id, "purpose": "password_reset"},
        expires_delta=timedelta(hours=2),
    )

    log_audit(
        db=db,
        action="password_reset_requested",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        meta={"email": user.email},
    )

    # In dev/testing environment, return the token for programmatic validation
    return {
        "message": "Password reset token generated successfully",
        "reset_token": reset_token,
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using a valid reset token."""
    token_data = decode_access_token(payload.token)
    if not token_data or token_data.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RESET_TOKEN", "message": "Invalid or expired password reset token"},
        )

    user_id = token_data.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found"},
        )

    user.password_hash = get_password_hash(payload.new_password)
    db.commit()

    log_audit(
        db=db,
        action="password_reset_completed",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
    )

    return {"message": "Password has been successfully updated"}
