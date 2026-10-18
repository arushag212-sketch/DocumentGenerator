"""Demo script for Part A Storage Diet verification.

Simulates:
- Create 20 documents
- Edit 10 of them twice (generating 3 versions each)
- Make 3 batches (ZIP archives)
- Fork 3 templates
Measures isolated storage size before and after GC.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from server.app.core.database import SessionLocal
from server.app.core.security import create_access_token
from server.app.main import app
from server.app.models import Club, Document, DocumentVersion, Template, User
from server.scripts.storage_gc import run_storage_gc


def run_demo():
    print("=== Running Part A Storage Diet Simulation ===")
    client = TestClient(app)
    db = SessionLocal()

    club = db.query(Club).first()
    owner = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
    token = create_access_token(user_id=owner.id, email=owner.email, token_version=owner.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create 20 documents
    created_docs = []
    print("Creating 20 documents...")
    for i in range(20):
        # Reserve room ref
        res_resp = client.post(
            f"/api/v1/clubs/{club.id}/numbering/ROOM/reserve",
            headers=headers,
            json={"template_id": "permission_letter"},
        )
        res_data = res_resp.json()
        res_id = res_data.get("reservation_id")
        ref_no = res_data.get("ref_no")

        resp = client.post(
            f"/api/v1/clubs/{club.id}/documents/generate",
            headers=headers,
            json={
                "template_id": "permission_letter",
                "reservation_id": res_id,
                "ref_no": ref_no,
                "event_data": {
                    "event_name": f"Diet Test Workshop {i+1}",
                    "dates": "2026-11-20",
                    "time_start": "09:00 AM",
                    "time_end": "12:00 PM",
                    "venue": "Main Seminar Hall",
                },
                "confirmed_fields": ["event_name", "dates", "time_start", "time_end", "venue"],
            },
        )
        if resp.status_code == 200:
            created_docs.append(resp.json()["id"])
        else:
            print(f"Failed doc {i}: {resp.status_code} {resp.text}")

    print(f"Created {len(created_docs)} documents.")

    # 2. Edit 10 of them twice (creating versions v2 and v3)
    print("Editing 10 documents twice...")
    for doc_id in created_docs[:10]:
        doc_obj = db.query(Document).filter(Document.id == doc_id).first()
        for v in (2, 3):
            # Create a new version
            v_dir = Path("storage/documents") / doc_id / f"v{v}"
            v_dir.mkdir(parents=True, exist_ok=True)
            v_file = v_dir / "permission_letter.docx"
            v_file.write_bytes(b"Simulated version payload " * 100)
            dv = DocumentVersion(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                version_no=v,
                record_snapshot={"event_name": f"Edited {v}", "venue": "Main Seminar Hall"},
                docx_key=str(v_file),
                pdf_key=None,
                created_by=owner.id,
                source="edit",
            )
            db.add(dv)
            doc_obj.current_version_id = dv.id
        db.commit()

    # 3. Make 3 batches
    print("Creating 3 batches...")
    batch_dir = Path("storage/cache/batches")
    batch_dir.mkdir(parents=True, exist_ok=True)
    for b_idx in range(3):
        b_folder = batch_dir / f"batch_{b_idx+1}"
        b_folder.mkdir(parents=True, exist_ok=True)
        (b_folder / "batch_export.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    # 4. Fork 3 templates
    print("Forking 3 templates...")
    for f_idx in range(3):
        fork_resp = client.post(
            f"/api/v1/clubs/{club.id}/documents/templates/permission_letter/fork",
            headers=headers,
            json={"name": f"Forked Permission Diet {f_idx+1}"},
        )
        if fork_resp.status_code not in (200, 201):
            print(f"Failed fork {f_idx}: {fork_resp.status_code} {fork_resp.text}")

    # Measure before GC
    def dir_size(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    storage_before = dir_size(Path("storage"))
    print(f"\nStorage size BEFORE GC: {storage_before / (1024*1024):.2f} MB ({storage_before} bytes)")

    # Run GC
    gc_rep = run_storage_gc(apply=True)
    storage_after = dir_size(Path("storage"))
    print(f"Storage size AFTER GC: {storage_after / (1024*1024):.2f} MB ({storage_after} bytes)")
    print(f"Freed: {gc_rep.total_bytes_freed / (1024*1024):.2f} MB ({gc_rep.total_bytes_freed} bytes) across {len(gc_rep.deleted_paths)} files.")

    db.close()


if __name__ == "__main__":
    run_demo()
