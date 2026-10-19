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


@app.middleware("http")
async def log_errors_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            print(f"[HTTP {response.status_code}] {request.method} {request.url.path}")
        return response
    except Exception as exc:
        import traceback
        print(f"[HTTP EXCEPTION] {request.method} {request.url.path}: {exc}")
        traceback.print_exc()
        raise


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


@app.get("/health/liveness", tags=["system"])
async def health_liveness():
    return {"status": "alive"}


@app.get("/health/readiness", tags=["system"])
async def health_readiness():
    try:
        from server.app.core.database import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "error": str(exc)})


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


import logging
import threading
import time

logger = logging.getLogger("clubdocs.main")
_gc_thread: threading.Thread | None = None


def _daily_gc_worker():
    while True:
        try:
            time.sleep(86400)
            from server.scripts.storage_gc import run_storage_gc
            logger.info("Running daily background storage GC...")
            run_storage_gc(apply=True)
        except Exception as e:
            logger.warning("Daily background GC failed: %s", e)


@app.on_event("startup")
def on_startup_gc():
    from server.app.core.storage import STORAGE_GC_ENABLED
    if STORAGE_GC_ENABLED:
        try:
            from server.scripts.storage_gc import run_storage_gc
            logger.info("Running startup light storage GC pass...")
            run_storage_gc(apply=True)
        except Exception as e:
            logger.warning("Startup storage GC failed: %s", e)

        global _gc_thread
        if _gc_thread is None or not _gc_thread.is_alive():
            _gc_thread = threading.Thread(target=_daily_gc_worker, daemon=True, name="storage-gc-worker")
            _gc_thread.start()


def check_db_schema_up_to_date(target_engine=None) -> bool:
    import sqlalchemy as sa
    from server.app.core.database import engine as default_engine
    eng = target_engine or default_engine
    try:
        with eng.connect() as conn:
            inspector = sa.inspect(conn)
            tables = set(inspector.get_table_names())
            if not tables:
                return True
            if "rate_limit_buckets" not in tables:
                return False
            if "document_versions" in tables:
                cols = {c["name"] for c in inspector.get_columns("document_versions")}
                if "template_version_id" not in cols:
                    return False
            if "join_requests" in tables:
                cols = {c["name"] for c in inspector.get_columns("join_requests")}
                if "requested_role" not in cols:
                    return False
            return True
    except Exception as exc:
        logger.warning("Schema check failed during inspection: %s", exc)
        return True


@app.on_event("startup")
def on_startup_database_check():
    import os
    from server.app.core.database import engine

    # Do not auto-migrate or mutate dev DB when running within pytest
    if "PYTEST_CURRENT_TEST" in os.environ:
        return

    if os.environ.get("AUTO_MIGRATE", "true").lower() in ("1", "true", "yes"):
        try:
            from server.scripts.migrate import run_migrations
            run_migrations()
        except Exception as e:
            logger.warning("Startup auto-migration skipped or failed: %s", e)

    if not check_db_schema_up_to_date(engine):
        msg = "Your database is out of date. Run: python -m server.scripts.migrate"
        print(f"\n[FATAL] {msg}\n")
        raise RuntimeError(msg)

