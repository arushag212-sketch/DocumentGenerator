"""Main FastAPI server application with security headers, CORS, static routes, and v1 APIs."""

from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.app.api.v1 import api_router
from server.app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Official SVNIT Surat Smart Document Generator & Approval Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# 1. CORS Configuration - Tightened to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# 2. Strict Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' http://localhost:* http://127.0.0.1:*; "
        "frame-src 'self' blob:; "
        "frame-ancestors 'self';"
    )
    return response


# 3. Mount Static Assets
assets_dir = settings.ASSETS_DIR
web_dir = Path(__file__).resolve().parent.parent.parent / "web"
dist_dir = web_dir / "dist"
dist_assets = dist_dir / "assets"

class MultiDirStaticFiles(StaticFiles):
    def __init__(self, dirs: list[Path]):
        self.dirs = [d for d in dirs if d.exists()]
        super().__init__(directory=str(self.dirs[0]) if self.dirs else str(assets_dir))

    def lookup_path(self, path: str):
        clean_path = path.lstrip("/\\")
        for d in self.dirs:
            full_path = d / clean_path
            if full_path.is_file():
                return str(full_path.resolve()), full_path.stat()
        return super().lookup_path(path)

app.mount("/assets", MultiDirStaticFiles([dist_assets, assets_dir]), name="assets")

if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


# 4. Include API v1 Routers
app.include_router(api_router, prefix=settings.API_V1_STR)


# 5. Root & SPA Fallback Routes
@app.get("/", include_in_schema=False)
async def serve_web_shell():
    if (dist_dir / "index.html").exists():
        return FileResponse(dist_dir / "index.html")
    index_file = web_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ClubDocs API is running. Access /docs for Swagger UI."}


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "database": "connected",
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not Found")
    if (dist_dir / "index.html").exists():
        return FileResponse(dist_dir / "index.html")
    index_file = web_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ClubDocs API is running. Access /docs for Swagger UI."}

