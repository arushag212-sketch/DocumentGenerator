"""Garbage collector script for ClubDocs storage.

Safely removes:
1. Orphan files not referenced by any database row (legacy leftovers, test debris).
2. Expired preview images (PREVIEW_TTL_DAYS, default 7).
3. Expired batch ZIP archives (BATCH_TTL_HOURS, default 24).
4. Pruned document version files beyond KEEP_VERSION_FILES retention (default 3).

Guarantees:
- Never deletes files referenced by a document's latest version or published template.
- Never touches any files outside the storage/ directory.
- Logs every deleted file and total bytes freed.
- Defaults to --dry-run unless --apply is passed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

from server.app.core.storage import (
    BATCH_TTL_HOURS,
    KEEP_VERSION_FILES,
    PREVIEW_TTL_DAYS,
    LocalDiskStorage,
    get_storage,
)


@dataclass
class GCReport:
    dry_run: bool = True
    orphans_count: int = 0
    orphans_bytes: int = 0
    expired_previews_count: int = 0
    expired_previews_bytes: int = 0
    expired_batches_count: int = 0
    expired_batches_bytes: int = 0
    pruned_versions_count: int = 0
    pruned_versions_bytes: int = 0
    total_bytes_freed: int = 0
    deleted_paths: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)


def get_db_protected_and_referenced_paths(club_id: Optional[str] = None) -> Tuple[Set[str], Set[str]]:
    """Return (all_referenced_keys, protected_latest_keys) resolved to canonical paths.

    References are always collected for every club: the orphan scan walks the whole storage
    folder, so a club-scoped reference set would make other clubs' files look orphaned.
    ``club_id`` is accepted for compatibility and ignored here. Raises if the database cannot
    be read, so the caller never deletes files on an empty reference set.
    """
    club_id = None
    referenced: Set[str] = set()
    protected: Set[str] = set()

    active_storage = get_storage()
    if not isinstance(active_storage, LocalDiskStorage):
        return referenced, protected

    try:
        from server.app.core.database import SessionLocal
        from server.app.models import Asset, Document, DocumentVersion, Template, TemplateVersion

        db = SessionLocal()

        # 1. Assets
        q_assets = db.query(Asset)
        if club_id:
            q_assets = q_assets.filter((Asset.club_id == club_id) | (Asset.club_id.is_(None)))
        for a in q_assets.all():
            if a.storage_key:
                p = active_storage.local_path(a.storage_key)
                referenced.add(str(p))
                referenced.add(Path(a.storage_key).as_posix())
                protected.add(str(p))
                protected.add(Path(a.storage_key).as_posix())

        # 2. Template Versions
        from server.app.models import Club

        club_ids = [c.id for c in db.query(Club).all()]
        q_tmpls = db.query(Template)
        if club_id:
            q_tmpls = q_tmpls.filter((Template.club_id == club_id) | (Template.club_id.is_(None)))
        for tmpl in q_tmpls.all():
            for tv in db.query(TemplateVersion).filter(TemplateVersion.template_id == tmpl.id).all():
                # Gallery thumbnails are named after the version id and have no DB column;
                # without this every thumbnail is "orphaned" and deleted on each startup.
                for ext in ("webp", "png"):
                    thumb = active_storage.local_path(f"thumbnails/{tv.id}.{ext}")
                    referenced.add(str(thumb))
                    protected.add(str(thumb))
                    if tmpl.club_id is None:  # built-in: one preview per club
                        for club_id in club_ids:
                            per_club = active_storage.local_path(f"thumbnails/{tv.id}_{club_id}.{ext}")
                            referenced.add(str(per_club))
                            protected.add(str(per_club))
                if tv.docx_storage_key:
                    p = active_storage.local_path(tv.docx_storage_key)
                    referenced.add(str(p))
                    referenced.add(Path(tv.docx_storage_key).as_posix())
                    # Published or current versions are protected
                    if tmpl.status == "published" or tmpl.current_version_id == tv.id:
                        protected.add(str(p))
                        protected.add(Path(tv.docx_storage_key).as_posix())

        # 3. Documents and Document Versions
        q_docs = db.query(Document)
        if club_id:
            q_docs = q_docs.filter(Document.club_id == club_id)
        for doc in q_docs.all():
            versions = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == doc.id)
                .order_by(DocumentVersion.version_no.desc())
                .all()
            )
            # Latest KEEP_VERSION_FILES are protected
            for idx, dv in enumerate(versions):
                for k in (dv.docx_key, dv.pdf_key):
                    if k:
                        p = active_storage.local_path(k)
                        referenced.add(str(p))
                        referenced.add(Path(k).as_posix())
                        if idx < KEEP_VERSION_FILES or dv.id == doc.current_version_id:
                            protected.add(str(p))
                            protected.add(Path(k).as_posix())

        db.close()
    except Exception as e:
        raise RuntimeError(f"Could not read file references from the database: {e}") from e

    # Shared fallback image used for templates without a rendered thumbnail.
    placeholder = active_storage.local_path("thumbnails/neutral_placeholder.png")
    referenced.add(str(placeholder))
    protected.add(str(placeholder))

    return referenced, protected


def run_storage_gc(apply: bool = False, club_id: Optional[str] = None) -> GCReport:
    """Run safe storage garbage collection pass."""
    report = GCReport(dry_run=not apply)
    active_storage = get_storage()
    if not isinstance(active_storage, LocalDiskStorage):
        report.logs.append(
            "Storage GC is local-filesystem only; configure STORAGE_BACKEND=local before running it."
        )
        return report
    base_storage = active_storage.base_dir
    if not base_storage.exists():
        report.logs.append("Storage directory storage/ does not exist. Nothing to clean.")
        return report

    try:
        referenced_keys, protected_keys = get_db_protected_and_referenced_paths(club_id)
    except RuntimeError as exc:
        # Without the reference set every file would look orphaned: delete nothing.
        report.logs.append(f"Cleanup skipped: {exc}")
        return report
    now = time.time()
    preview_ttl_seconds = PREVIEW_TTL_DAYS * 86400
    batch_ttl_seconds = BATCH_TTL_HOURS * 3600

    # 1. Clean Expired Previews (both cache/previews and storage/previews)
    preview_dirs = [base_storage / "cache" / "previews", base_storage / "previews"]
    for p_dir in preview_dirs:
        if p_dir.exists():
            for root, dirs, files in os.walk(p_dir, topdown=False):
                for f in files:
                    fp = Path(root) / f
                    try:
                        st = fp.stat()
                        age = now - st.st_mtime
                        if age > preview_ttl_seconds or p_dir.name == "previews":
                            # Previews older than TTL (or legacy storage/previews) are cleaned
                            report.expired_previews_count += 1
                            report.expired_previews_bytes += st.st_size
                            report.total_bytes_freed += st.st_size
                            report.deleted_paths.append(fp.as_posix())
                            if apply:
                                fp.unlink(missing_ok=True)
                    except Exception as e:
                        report.logs.append(f"Error examining preview {fp}: {e}")

    # 2. Clean Expired Batches (both cache/batches and storage/batches)
    batch_dirs = [base_storage / "cache" / "batches", base_storage / "batches"]
    for b_dir in batch_dirs:
        if b_dir.exists():
            for root, dirs, files in os.walk(b_dir, topdown=False):
                for f in files:
                    fp = Path(root) / f
                    try:
                        st = fp.stat()
                        age = now - st.st_mtime
                        if age > batch_ttl_seconds or b_dir.name == "batches":
                            report.expired_batches_count += 1
                            report.expired_batches_bytes += st.st_size
                            report.total_bytes_freed += st.st_size
                            report.deleted_paths.append(fp.as_posix())
                            if apply:
                                fp.unlink(missing_ok=True)
                    except Exception as e:
                        report.logs.append(f"Error examining batch {fp}: {e}")

    # 3. Clean Pruned Document Versions (> KEEP_VERSION_FILES)
    try:
        from server.app.core.database import SessionLocal
        from server.app.models import Document, DocumentVersion

        db = SessionLocal()
        q_docs = db.query(Document)
        if club_id:
            q_docs = q_docs.filter(Document.club_id == club_id)
        for doc in q_docs.all():
            versions = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == doc.id)
                .order_by(DocumentVersion.version_no.desc())
                .all()
            )
            if len(versions) > KEEP_VERSION_FILES:
                for old_ver in versions[KEEP_VERSION_FILES:]:
                    for key_attr in ("docx_key", "pdf_key"):
                        val = getattr(old_ver, key_attr)
                        if val:
                            fp = active_storage.local_path(val)
                            if fp.exists():
                                try:
                                    sz = fp.stat().st_size
                                    report.pruned_versions_count += 1
                                    report.pruned_versions_bytes += sz
                                    report.total_bytes_freed += sz
                                    report.deleted_paths.append(fp.as_posix())
                                    if apply:
                                        fp.unlink(missing_ok=True)
                                except Exception as e:
                                    report.logs.append(f"Error pruning version file {fp}: {e}")
        db.close()
    except Exception as e:
        report.logs.append(f"Error checking document version retention: {e}")

    # 4. Remove Orphan Files in storage/ (documents, templates, assets, thumbnails, temp_*)
    scanned_subdirs = ["documents", "templates", "assets", "thumbnails", "temp_thumbnails", "temp"]
    for s_name in scanned_subdirs:
        s_dir = base_storage / s_name
        if s_dir.exists():
            for root, dirs, files in os.walk(s_dir, topdown=False):
                for f in files:
                    fp = Path(root) / f
                    res_p = str(fp.resolve())
                    posix_p = fp.as_posix()
                    norm_rel = fp.relative_to(base_storage.parent).as_posix() if base_storage.parent in fp.parents else posix_p

                    # CRITICAL SAFETY: Never delete protected files or files outside storage/
                    if not str(fp.resolve()).startswith(str(base_storage)):
                        continue
                    if res_p in protected_keys or posix_p in protected_keys or norm_rel in protected_keys:
                        continue
                    # Full-page previews ({card}_p{n}.webp) live and die with their card preview
                    if s_name == "thumbnails" and "_p" in fp.stem:
                        card = fp.with_name(fp.stem.rsplit("_p", 1)[0] + ".webp")
                        if str(card.resolve()) in protected_keys or str(card) in protected_keys:
                            continue

                    # If not referenced in database, it is an orphan!
                    is_referenced = (
                        res_p in referenced_keys
                        or posix_p in referenced_keys
                        or norm_rel in referenced_keys
                    )
                    if not is_referenced or s_name in ("temp_thumbnails", "temp"):
                        try:
                            sz = fp.stat().st_size
                            report.orphans_count += 1
                            report.orphans_bytes += sz
                            report.total_bytes_freed += sz
                            report.deleted_paths.append(fp.as_posix())
                            if apply:
                                fp.unlink(missing_ok=True)
                        except Exception as e:
                            report.logs.append(f"Error unlinking orphan {fp}: {e}")

    # 5. Clean empty subdirectories in storage/
    if apply:
        for root, dirs, files in os.walk(base_storage, topdown=False):
            for d in dirs:
                dp = Path(root) / d
                try:
                    if dp != base_storage and not any(dp.iterdir()):
                        dp.rmdir()
                except Exception:
                    pass

    return report


def main():
    parser = argparse.ArgumentParser(description="Safely collect garbage and prune expired storage files.")
    parser.add_argument("--apply", action="store_true", help="Apply file deletions (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate run without deleting (default)")
    parser.add_argument("--club-id", type=str, default=None, help="Scope GC pass to a specific club")
    args = parser.parse_args()

    should_apply = args.apply and not args.dry_run
    mode_str = "APPLY (REAL DELETION)" if should_apply else "DRY RUN (NO FILES TOUCHED)"
    print(f"=== ClubDocs Storage Garbage Collector [{mode_str}] ===\n")

    report = run_storage_gc(apply=should_apply, club_id=args.club_id)

    print(f"Orphan files:           {report.orphans_count:,} ({report.orphans_bytes / (1024*1024):.2f} MB)")
    print(f"Expired previews:       {report.expired_previews_count:,} ({report.expired_previews_bytes / (1024*1024):.2f} MB)")
    print(f"Expired batch ZIPs:     {report.expired_batches_count:,} ({report.expired_batches_bytes / (1024*1024):.2f} MB)")
    print(f"Pruned older versions:  {report.pruned_versions_count:,} ({report.pruned_versions_bytes / (1024*1024):.2f} MB)")
    print("-" * 55)
    print(f"TOTAL RECLAIMABLE/FREED: {report.total_bytes_freed / (1024*1024):.2f} MB ({report.total_bytes_freed:,} bytes)")
    print(f"Total files identified:  {len(report.deleted_paths):,}")

    if report.logs:
        print("\nWarnings/Logs:")
        for l in report.logs[:10]:
            print(f"  {l}")

    if not should_apply:
        print("\n[NOTE] This was a dry run. To execute deletions, run with --apply")


if __name__ == "__main__":
    main()
