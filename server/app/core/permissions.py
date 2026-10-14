"""Permission enforcement layer for users, clubs, roles, and scoped actions."""

from __future__ import annotations

from typing import Annotated, Optional
from fastapi import Cookie, Depends, Header, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.security import decode_access_token
from server.app.models import Club, Membership, User

security_bearer = HTTPBearer(auto_error=False)


class Role:
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


ROLE_RANKS = {
    Role.VIEWER: 10,
    Role.EDITOR: 20,
    Role.ADMIN: 30,
    Role.OWNER: 40,
}


class ClubContext:
    """Context holding the authenticated user, resolved club, and effective role."""

    def __init__(self, user: User, club: Club, role: str, membership: Optional[Membership] = None):
        self.user = user
        self.club = club
        self.role = role
        self.membership = membership

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER or self.user.is_platform_admin

    @property
    def is_admin(self) -> bool:
        return ROLE_RANKS.get(self.role, 0) >= ROLE_RANKS[Role.ADMIN] or self.user.is_platform_admin

    @property
    def is_editor(self) -> bool:
        return ROLE_RANKS.get(self.role, 0) >= ROLE_RANKS[Role.EDITOR] or self.user.is_platform_admin

    @property
    def is_viewer(self) -> bool:
        return ROLE_RANKS.get(self.role, 0) >= ROLE_RANKS[Role.VIEWER] or self.user.is_platform_admin


def get_token_from_request(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    token_cookie: Optional[str] = Cookie(default=None, alias="access_token"),
    auth_header: Optional[str] = Header(default=None, alias="Authorization"),
) -> str:
    """Extract JWT token from Bearer header or cookie."""
    if bearer and bearer.credentials:
        return bearer.credentials
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    if token_cookie:
        return token_cookie
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Missing authentication credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(get_token_from_request),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate current user from JWT token."""
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User no longer exists"},
        )
    if user.disabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "USER_DISABLED", "message": "Account has been deactivated"},
        )
    return user


def require_platform_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the user is a platform administrator."""
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Platform administrator access required"},
        )
    return current_user


def require_club_access(min_role: str = Role.VIEWER):
    """Dependency factory checking that the user belongs to the requested club and satisfies min_role."""

    def _dependency(
        club_id: str = Path(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> ClubContext:
        # Check club exists
        club = db.query(Club).filter(Club.id == club_id).first()
        if not club or club.disabled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CLUB_NOT_FOUND", "message": "Club not found or deactivated"},
            )

        # Platform admins have full superuser rights over all clubs
        if current_user.is_platform_admin:
            return ClubContext(user=current_user, club=club, role=Role.OWNER, membership=None)

        # Lookup membership
        membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == current_user.id,
                Membership.club_id == club_id,
                Membership.status == "active",
            )
            .first()
        )

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "NOT_A_MEMBER", "message": "You are not an active member of this club"},
            )

        user_role = membership.role
        user_rank = ROLE_RANKS.get(user_role, 0)
        req_rank = ROLE_RANKS.get(min_role, 0)

        if user_rank < req_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_ROLE",
                    "message": f"Action requires at least '{min_role}' role (current: '{user_role}')",
                },
            )

        return ClubContext(user=current_user, club=club, role=user_role, membership=membership)

    return _dependency
