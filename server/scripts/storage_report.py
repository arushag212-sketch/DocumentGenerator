"""Storage and repository size audit reporting script.

Measures:
1. Size and file count per tracked folder:
   - storage/documents, storage/previews, storage/batches, storage/thumbnails, storage/templates
   - outputs
   - data temp databases
   - docs/screenshots
   - visual test artifacts
2. Top 20 largest files
3. Duplicate files by SHA256
4. Orphan files in storage/ (not referenced in DB)
5. Size guard (--check): exits non-zero if repo > 40 MB (excl .git/node_modules/.venv) or storage/ > 100 MB
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".eggs", "egg-info"}


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB ({size:,} bytes)"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB ({size:,} bytes)"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB ({size:,} bytes)"


def get_dir_stats(path: Path) -> Tuple[int, int]:
    """Return (file_count, total_size_bytes) for a directory."""
    if not path.exists():
        return 0, 0
    if path.is_file():
        return 1, path.stat().st_size
    count = 0
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
                count += 1
            except OSError:
                pass
    return count, total


def get_data_temp_db_stats() -> Tuple[int, int]:
    """Return stats for temporary test / temp database files in data/."""
    data_dir = Path("data")
    if not data_dir.exists():
        return 0, 0
    count = 0
    total = 0
    for f in data_dir.glob("*"):
        if f.is_file():
            name = f.name.lower()
            if "temp_" in name or "test_" in name or name.endswith("-wal") or name.endswith("-shm"):
                total += f.stat().st_size
                count += 1
    return count, total


def get_repo_stats(root_dir: Path) -> Tuple[int, int]:
    """Return (file_count, total_bytes) for entire repo excluding git/node_modules/.venv."""
    count = 0
    total = 0
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
                count += 1
            except OSError:
                pass
    return count, total


def get_referenced_db_storage_keys() -> Set[str]:
    """Query database for all referenced storage keys."""
    referenced: Set[str] = set()
    try:
        from server.app.core.database import SessionLocal
        from server.app.models import Asset, DocumentVersion, TemplateVersion

        db = SessionLocal()
        for a in db.query(Asset).all():
            if a.storage_key:
                referenced.add(str(Path(a.storage_key).resolve()))
                referenced.add(str(a.storage_key).replace("\\", "/"))

        for tv in db.query(TemplateVersion).all():
            if tv.docx_storage_key:
                referenced.add(str(Path(tv.docx_storage_key).resolve()))
                referenced.add(str(tv.docx_storage_key).replace("\\", "/"))

        for dv in db.query(DocumentVersion).all():
            if dv.docx_key:
                referenced.add(str(Path(dv.docx_key).resolve()))
                referenced.add(str(dv.docx_key).replace("\\", "/"))
            if dv.pdf_key:
                referenced.add(str(Path(dv.pdf_key).resolve()))
                referenced.add(str(dv.pdf_key).replace("\\", "/"))
        db.close()
    except Exception as e:
        print(f"[WARN] Failed to query database for referenced keys: {e}")
    return referenced


def generate_report(check_limits: bool = False) -> str:
    lines: List[str] = []
    lines.append("# Storage and Repository Size Report\n")

    # 1. Tracked Folders
    tracked_folders = [
        ("storage/documents", Path("storage/documents")),
        ("storage/previews", Path("storage/previews")),
        ("storage/batches", Path("storage/batches")),
        ("storage/thumbnails", Path("storage/thumbnails")),
        ("storage/templates", Path("storage/templates")),
        ("storage/assets", Path("storage/assets")),
        ("storage (TOTAL)", Path("storage")),
        ("outputs", Path("outputs")),
        ("data temp databases", Path("data")),
        ("docs/screenshots", Path("docs/screenshots")),
        ("tests_visual", Path("tests") / "visual"),
    ]

    lines.append("## 1. Tracked Folder Breakdown\n")
    lines.append("| Tracked Folder | Files | Size |")
    lines.append("| :--- | :---: | :--- |")

    folder_stats = {}
    for name, path in tracked_folders:
        if name == "data temp databases":
            count, size = get_data_temp_db_stats()
        else:
            count, size = get_dir_stats(path)
        folder_stats[name] = (count, size)
        lines.append(f"| `{name}` | {count:,} | {format_bytes(size)} |")

    repo_files, repo_bytes = get_repo_stats(Path("."))
    lines.append(f"| **Repository Total (excl .git/.venv/node_modules)** | **{repo_files:,}** | **{format_bytes(repo_bytes)}** |")
    lines.append("")

    # 2. 20 Largest Files
    all_files: List[Tuple[int, str]] = []
    for root, dirs, files in os.walk(Path(".")):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in files:
            fp = Path(root) / f
            try:
                all_files.append((fp.stat().st_size, fp.as_posix()))
            except OSError:
                pass

    all_files.sort(key=lambda x: x[0], reverse=True)
    top_20 = all_files[:20]

    lines.append("## 2. Top 20 Largest Files\n")
    lines.append("| Rank | File Path | Size |")
    lines.append("| :---: | :--- | :--- |")
    for rank, (size, path) in enumerate(top_20, 1):
        lines.append(f"| {rank} | `{path}` | {format_bytes(size)} |")
    lines.append("")

    # 3. Duplicate files by SHA-256
    hash_map: Dict[str, List[Tuple[str, int]]] = {}
    for size, path in all_files:
        if size > 1024:  # Check duplicates > 1KB
            try:
                h = compute_sha256(Path(path))
                hash_map.setdefault(h, []).append((path, size))
            except Exception:
                pass

    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}

    lines.append("## 3. Duplicate Files by SHA-256\n")
    if duplicates:
        lines.append(f"Found **{len(duplicates)}** set(s) of identical duplicate files:\n")
        lines.append("| SHA-256 (prefix) | Size | Duplicate Paths |")
        lines.append("| :--- | :--- | :--- |")
        for h, items in sorted(duplicates.items(), key=lambda x: x[1][0][1] * len(x[1]), reverse=True)[:15]:
            size = items[0][1]
            path_list = "<br>".join([f"`{p}`" for p, _ in items])
            lines.append(f"| `{h[:12]}...` | {format_bytes(size)} | {path_list} |")
    else:
        lines.append("No duplicate files found.")
    lines.append("")

    # 4. Orphan Files in storage/
    referenced = get_referenced_db_storage_keys()
    orphan_files: List[Tuple[str, int]] = []
    storage_dir = Path("storage")
    if storage_dir.exists():
        for root, dirs, files in os.walk(storage_dir):
            for f in files:
                fp = Path(root) / f
                res_path = str(fp.resolve())
                norm_path = fp.as_posix()
                if res_path not in referenced and norm_path not in referenced:
                    # Ignore active temporary cache folders if intended, but report orphans
                    orphan_files.append((norm_path, fp.stat().st_size))

    lines.append("## 4. Orphan Files in storage/\n")
    if orphan_files:
        total_orphan_bytes = sum(s for _, s in orphan_files)
        lines.append(f"Found **{len(orphan_files)}** orphan files in `storage/` ({format_bytes(total_orphan_bytes)}):\n")
        lines.append("| Orphan File Path | Size |")
        lines.append("| :--- | :--- |")
        for path, size in orphan_files[:25]:
            lines.append(f"| `{path}` | {format_bytes(size)} |")
        if len(orphan_files) > 25:
            lines.append(f"| *...and {len(orphan_files) - 25} more orphan files* | |")
    else:
        lines.append("No orphan files detected in `storage/`.")
    lines.append("")

    report_text = "\n".join(lines)

    if check_limits:
        # Check repo limit (< 40 MB) and storage limit (< 100 MB)
        _, storage_bytes = folder_stats.get("storage (TOTAL)", (0, 0))
        repo_mb = repo_bytes / (1024 * 1024)
        storage_mb = storage_bytes / (1024 * 1024)
        print(f"Size Guard Check: Repo={repo_mb:.2f} MB (limit 40 MB), Storage={storage_mb:.2f} MB (limit 100 MB)")
        failed = False
        if repo_mb > 40.0:
            print(f"[FAIL] Repository size ({repo_mb:.2f} MB) exceeds limit of 40 MB!")
            failed = True
        else:
            print(f"[PASS] Repository size ({repo_mb:.2f} MB) within 40 MB limit.")
        if storage_mb > 100.0:
            print(f"[FAIL] Storage size ({storage_mb:.2f} MB) exceeds limit of 100 MB!")
            failed = True
        else:
            print(f"[PASS] Storage size ({storage_mb:.2f} MB) within 100 MB limit.")
        if failed:
            sys.exit(1)

    return report_text


def main():
    parser = argparse.ArgumentParser(description="Audit and report repository and storage directory sizes.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if repo > 40MB or storage > 100MB")
    parser.add_argument("--output", type=str, default="", help="Optional file path to write report markdown")
    args = parser.parse_args()

    report = generate_report(check_limits=args.check)
    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
