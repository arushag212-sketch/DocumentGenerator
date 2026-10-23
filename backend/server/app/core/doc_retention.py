"""Document version retention and on-demand regeneration module.

Policy:
- Keep physical files (DOCX + PDF) for the latest KEEP_VERSION_FILES versions (default 3).
- For older versions, keep the database row, record snapshot, and overrides intact.
- Prune physical files of older versions to save disk space.
- Regenerate older pruned versions on demand from the immutable template version + snapshot.
- Never regenerate silently on download of the latest version (source of truth).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from docgen.models import EventRecord
from docgen.renderer import Renderer
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.storage import KEEP_VERSION_FILES, require_local_storage
from server.app.models import Club, Document, DocumentVersion, Template, TemplateVersion

logger = logging.getLogger("clubdocs.retention")


def prune_document_versions(db: Session, doc_id: str, keep_count: int = KEEP_VERSION_FILES) -> int:
    """Keep physical files for latest keep_count versions. Older versions retain DB row and snapshot, files are unlinked."""
    local_storage = require_local_storage()
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_no.desc())
        .all()
    )
    if len(versions) <= keep_count:
        return 0

    freed_bytes = 0
    # Versions from index keep_count onwards are older versions
    for old_v in versions[keep_count:]:
        for key_attr in ("docx_key", "pdf_key"):
            key_val = getattr(old_v, key_attr)
            if key_val:
                fp = local_storage.local_path(key_val)
                if fp.exists():
                    try:
                        sz = fp.stat().st_size
                        fp.unlink(missing_ok=True)
                        freed_bytes += sz
                    except Exception as e:
                        logger.warning("Error deleting pruned version file %s: %s", fp, e)
    return freed_bytes


def regenerate_document_version(
    db: Session,
    doc_id: str,
    version_no: int,
    *,
    club_id: Optional[str] = None,
) -> Tuple[Path, Path]:
    """Regenerate DOCX and PDF on demand for an older version from its immutable template version and snapshot.
    
    Guarantees that the regenerated document text exactly matches the original generation.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError(f"Document with id '{doc_id}' not found")
    if club_id is not None and doc.club_id != club_id:
        raise ValueError("Document does not belong to the requested club")

    ver = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id, DocumentVersion.version_no == version_no)
        .first()
    )
    if not ver:
        raise ValueError(f"Document version v{version_no} not found for document '{doc_id}'")

    tmpl = db.query(Template).filter(Template.id == doc.template_id).first()
    if not tmpl:
        raise ValueError(f"Template for document '{doc_id}' not found")

    local_storage = require_local_storage()
    out_dir = local_storage.base_dir / "documents" / doc.id / f"v{version_no}"
    docx_path = (
        local_storage.local_path(ver.docx_key)
        if ver.docx_key
        else out_dir / f"{tmpl.slug or 'document'}.docx"
    )
    pdf_path = (
        local_storage.local_path(ver.pdf_key)
        if ver.pdf_key
        else out_dir / f"{tmpl.slug or 'document'}.pdf"
    )

    if docx_path.exists() and pdf_path.exists():
        return docx_path, pdf_path

    out_dir.mkdir(parents=True, exist_ok=True)

    tmpl_ver: Optional[TemplateVersion] = None
    # New rows carry the exact revision.  Legacy rows are safely backfilled
    # from Document.template_version_id rather than the mutable current
    # template pointer; only a last-resort legacy fallback uses current_id.
    template_version_id = getattr(ver, "template_version_id", None) or doc.template_version_id
    if template_version_id:
        tmpl_ver = (
            db.query(TemplateVersion)
            .filter(
                TemplateVersion.id == template_version_id,
                TemplateVersion.template_id == tmpl.id,
            )
            .first()
        )
    if not tmpl_ver and tmpl.current_version_id:
        tmpl_ver = (
            db.query(TemplateVersion)
            .filter(
                TemplateVersion.id == tmpl.current_version_id,
                TemplateVersion.template_id == tmpl.id,
            )
            .first()
        )

    src_docx = None
    schema_yaml = ""
    if tmpl_ver:
        if tmpl_ver.docx_storage_key:
            candidate = local_storage.local_path(tmpl_ver.docx_storage_key)
            if candidate.exists():
                src_docx = candidate
        schema_yaml = tmpl_ver.schema_yaml or ""

    if not src_docx:
        fallback_path = Path("templates") / tmpl.slug / "template.docx"
        if fallback_path.exists():
            src_docx = fallback_path

    if not src_docx or not src_docx.exists():
        raise FileNotFoundError(f"Template source DOCX not found for template '{tmpl.slug}'")

    club = db.query(Club).filter(Club.id == doc.club_id).first()
    club_slug = club.slug if club else "acm"
    try:
        db_config = build_club_config_from_db(db, club_slug)
    except Exception:
        from docgen.config import load_config
        db_config = load_config()

    db_source = DatabaseTemplateSource({tmpl.slug: (schema_yaml, src_docx)})
    renderer = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir)

    snapshot = ver.record_snapshot or {}
    event_rec = EventRecord.from_flat_dict(snapshot)

    render_result = renderer.render(
        template_id=tmpl.slug,
        event=event_rec,
        extra_context=snapshot,
        output_dir=out_dir,
        version=version_no,
        convert_pdf=True,
        allow_blanks=True,
        # The rebuilt copy prints the version's own code, so it still verifies
        verification_code=ver.verification_code,
    )

    ver.template_version_id = tmpl_ver.id if tmpl_ver else template_version_id
    ver.docx_key = str(render_result.docx_path)
    ver.pdf_key = str(render_result.pdf_path)
    if not ver.verification_code:
        ver.verification_code = render_result.verification_code
    if not ver.pdf_sha256:
        ver.pdf_sha256 = render_result.pdf_sha256
    # Let the request/background job own the transaction boundary.  The
    # regenerated files and their metadata are one unit of work; committing
    # here could make a partial regeneration durable before a later failure.
    db.flush()

    return render_result.docx_path, render_result.pdf_path
