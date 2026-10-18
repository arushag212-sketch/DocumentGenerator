"""API v1 router bundle."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.app.core.database import get_db
from server.app.api.v1.auth import router as auth_router
from server.app.api.v1.clubs import router as clubs_router
from server.app.api.v1.documents import router as documents_router
from server.app.api.v1.events import router as events_router
from server.app.api.v1.home import router as home_router
from server.app.api.v1.invites import router as invites_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(clubs_router)
api_router.include_router(documents_router)
api_router.include_router(events_router)
api_router.include_router(home_router)
api_router.include_router(invites_router)


@api_router.get("/assets/{asset_id}/content")
def serve_global_asset_content(
    asset_id: str,
    db: Session = Depends(get_db),
):
    """Serve asset binary content by ID."""
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from server.app.models import Asset

    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    f_path = Path(asset.storage_key)
    if not f_path.exists():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")
    return FileResponse(str(f_path), media_type=asset.mime)

