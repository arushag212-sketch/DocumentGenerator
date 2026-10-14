"""API v1 router bundle."""

from __future__ import annotations

from fastapi import APIRouter
from server.app.api.v1.auth import router as auth_router
from server.app.api.v1.clubs import router as clubs_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(clubs_router)
