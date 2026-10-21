"""Pre-render built-in template thumbnails and preview pages at image build time.

Renders real thumbnails for all system/library templates (club_id is None) using
neutral SVNIT letterhead into backend/static_thumbnails/<template_slug>.webp.
Uses a temporary SQLite database seeded with built-in templates and cleans it up afterwards.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


def main() -> None:
    # Ensure current working directory is backend root (where assets/ and templates/ live)
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    if (backend_dir / "templates").exists():
        os.chdir(backend_dir)
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    out_dir = backend_dir / "static_thumbnails"
    out_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = tempfile.mkdtemp(prefix="prerender_db_")
    temp_db = Path(temp_dir) / "prerender.db"

    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db.as_posix()}"
    os.environ["ENVIRONMENT"] = "production"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_LOCAL_ROOT"] = str(Path(temp_dir) / "storage")
    os.environ["LOW_MEMORY_MODE"] = "false"

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from server.app.core import database as db_core
        import server.app.models

        # Bind database engine and session to the temporary SQLite database
        engine = create_engine(
            f"sqlite:///{temp_db.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        db_core.engine = engine
        db_core.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_core.Base.metadata.create_all(bind=engine)

        # Seed system templates and library templates into temporary DB
        from server.scripts.seed import seed
        seed(clean=False, demo_users=False)

        from server.app.models import Template, TemplateVersion
        from server.app.core.dummy_thumbnail import _render_thumbnail, _template_docx
        from server.app.core.storage import require_local_storage

        db = db_core.SessionLocal()
        local_storage = require_local_storage()

        templates = db.query(Template).filter(Template.club_id.is_(None)).all()
        print(f"[prerender] Found {len(templates)} built-in templates to pre-render into {out_dir}")

        success_count = 0
        for tmpl in templates:
            ver = (
                db.query(TemplateVersion)
                .filter(TemplateVersion.template_id == tmpl.id)
                .order_by(TemplateVersion.version_no.desc())
                .first()
            )
            if not ver:
                print(f"[prerender] Skipping {tmpl.slug}: no template version found")
                continue

            docx_path = _template_docx(tmpl, ver, local_storage)
            if not docx_path or not docx_path.exists():
                print(f"[prerender] Skipping {tmpl.slug}: template DOCX not found")
                continue

            thumb_path = out_dir / f"{tmpl.slug}.webp"
            print(f"[prerender] Rendering thumbnail for {tmpl.slug}...")
            try:
                _render_thumbnail(
                    db=db,
                    tmpl=tmpl,
                    ver=ver,
                    club_slug="",
                    docx_path=docx_path,
                    thumb_path=thumb_path,
                    local_storage=local_storage,
                    render_pages=True,
                )
                if thumb_path.exists():
                    success_count += 1
                    print(f"[prerender] Successfully generated {thumb_path.name}")
            except Exception as exc:
                print(f"[prerender] Warning: Failed to render {tmpl.slug}: {exc}")

        print(f"[prerender] Completed: {success_count}/{len(templates)} templates pre-rendered.")
        db.close()
        engine.dispose()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[prerender] Warning: Pre-rendering thumbnails failed: {exc}")
        sys.exit(0)
