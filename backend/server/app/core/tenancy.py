"""Small helpers for enforcing club ownership on shared resources.

System resources are deliberately represented as rows with ``club_id`` set to
NULL and ``is_system`` set to true.  They remain available to authenticated
club members, while a club-owned row is never visible outside its club.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.app.models import Asset, Letterhead, Membership, User


def asset_is_visible_to_club(asset: Optional[Asset], club_id: str) -> bool:
    """Return whether an asset may be referenced by ``club_id``.

    ``is_system`` alone is not sufficient: a malformed or compromised row
    marked system but owned by a club must not become globally readable.
    """

    if asset is None:
        return False
    return asset.club_id == club_id or (asset.is_system and asset.club_id is None)


def get_asset_for_club(db: Session, asset_id: Optional[str], club_id: str) -> Optional[Asset]:
    """Fetch an asset only when it belongs to the club or is a system asset."""

    if not asset_id:
        return None
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    return asset if asset_is_visible_to_club(asset, club_id) else None


def letterhead_is_visible_to_club(letterhead: Optional[Letterhead], club_id: str) -> bool:
    """Return whether a letterhead row can be used by a club."""

    return bool(letterhead and (letterhead.club_id is None or letterhead.club_id == club_id))


def validate_letterhead_asset_refs(
    db: Session,
    club_id: str,
    *,
    letterhead: Optional[Letterhead] = None,
    left_logo_asset_id: Optional[str] = None,
    right_logo_asset_id: Optional[str] = None,
    institute_logo_asset_id: Optional[str] = None,
) -> None:
    """Validate a letterhead and all referenced assets for one club.

    Raises a 400 for a bad reference and a 403 for a letterhead owned by a
    different club.  System letterheads and their system assets remain valid.
    """

    if letterhead is not None and not letterhead_is_visible_to_club(letterhead, club_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LETTERHEAD_FORBIDDEN", "message": "Letterhead belongs to another club"},
        )

    ids = {
        value
        for value in (
            left_logo_asset_id if left_logo_asset_id is not None else getattr(letterhead, "left_logo_asset_id", None),
            right_logo_asset_id if right_logo_asset_id is not None else getattr(letterhead, "right_logo_asset_id", None),
            institute_logo_asset_id
            if institute_logo_asset_id is not None
            else getattr(letterhead, "institute_logo_asset_id", None),
        )
        if value
    }
    for asset_id in ids:
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ASSET_NOT_FOUND", "message": f"Asset '{asset_id}' was not found"},
            )
        if not asset_is_visible_to_club(asset, club_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ASSET_FORBIDDEN", "message": "Asset belongs to another club"},
            )


def user_can_access_asset(db: Session, asset: Asset, user: User) -> bool:
    """Check authenticated access for the global asset-content endpoint."""

    if asset.is_system and asset.club_id is None:
        return True
    if not asset.club_id:
        return False
    if user.is_platform_admin:
        return True
    return (
        db.query(Membership)
        .filter(
            Membership.club_id == asset.club_id,
            Membership.user_id == user.id,
            Membership.status == "active",
        )
        .first()
        is not None
    )
