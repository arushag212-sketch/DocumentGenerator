"""API v1 router bundle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from server.app.core.database import get_db
from server.app.core.permissions import get_current_user
from server.app.core.storage import LocalDiskStorage, get_storage
from server.app.core.tenancy import user_can_access_asset
from server.app.api.v1.auth import router as auth_router
from server.app.api.v1.clubs import router as clubs_router
from server.app.api.v1.document_trash import router as document_trash_router
from server.app.api.v1.documents import router as documents_router
from server.app.api.v1.events import router as events_router
from server.app.api.v1.home import router as home_router
from server.app.api.v1.invites import router as invites_router
from server.app.api.v1.editor_assistant import router as editor_assistant_router
from server.app.api.v1.verify import router as verify_router
from server.app.api.v1.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(clubs_router)
# Before documents_router so /trash and /bulk-delete aren't read as a document id
api_router.include_router(document_trash_router)
api_router.include_router(documents_router)
api_router.include_router(events_router)
api_router.include_router(home_router)
api_router.include_router(invites_router)
api_router.include_router(editor_assistant_router)
api_router.include_router(verify_router)
api_router.include_router(analytics_router)


@api_router.get("/assets/{asset_id}/content")
def serve_global_asset_content(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Serve system assets or assets owned by the authenticated user's club."""
    from server.app.models import Asset

    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not user_can_access_asset(db, asset, current_user):
        # Do not reveal whether a foreign-club asset exists.
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        active_storage = get_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if isinstance(active_storage, LocalDiskStorage):
        f_path = active_storage.local_path(asset.storage_key)
        if not f_path.is_file():
            raise HTTPException(status_code=404, detail="Asset file not found on storage")
        return FileResponse(str(f_path), media_type=asset.mime)

    try:
        return Response(content=active_storage.load(asset.storage_key), media_type=asset.mime)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Asset file not found on storage")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
