"""Seed demo SVNIT clubs, accounts and club templates through the public API.

Everything goes through the same endpoints a real club uses (register, create club, upload
logo, join requests and approvals, people, venues, AI template drafting, review and publish),
so the demo is created the way a club would set itself up. Safe to re-run.

    python -m server.scripts.seed_demo_clubs            # with AI-drafted club templates
    python -m server.scripts.seed_demo_clubs --no-ai    # skip AI template drafting
    python -m server.scripts.seed_demo_clubs --owners-only  # one-time production setup: 5 clubs, logos and owners

Development only for full mode. --owners-only is allowed in production.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "demo" / "clubs.json"
ACCOUNTS_DOC = ROOT.parent / "docs" / "DEMO_ACCOUNTS.md"
ROLE_POSITIONS = {"admin": "Secretary", "editor": "Executive Member", "viewer": "Executive Member"}


class Api:
    def __init__(self):
        from fastapi.testclient import TestClient

        from server.app.main import app

        self.client = TestClient(app)

    def call(self, method: str, path: str, token: Optional[str] = None, expect=(200, 201), **kwargs) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        res = self.client.request(method, f"/api/v1{path}", headers=headers, **kwargs)
        if res.status_code not in expect:
            raise RuntimeError(f"{method} {path} -> {res.status_code}: {res.text[:300]}")
        return res.json() if res.content else None

    def account(self, email: str, name: str, password: str) -> str:
        """Log in, registering the account first if needed. Returns an access token."""
        res = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        if res.status_code == 200:
            return res.json()["access_token"]
        reg_res = self.client.post("/api/v1/auth/register", json={"email": email, "password": password, "name": name})
        if reg_res.status_code in (200, 201):
            return reg_res.json()["access_token"]
        from server.app.core.database import SessionLocal
        from server.app.models import User
        from server.app.core.security import create_access_token

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            if user:
                return create_access_token(user.id, user.email, user.token_version)
        raise RuntimeError(f"POST /auth/register -> {reg_res.status_code}: {reg_res.text[:300]}")


def _email(slug: str, role: str, domain: str) -> str:
    return f"{slug}.{role}@{domain}"


def _club_by_slug(api: Api, token: str, slug: str) -> Optional[dict]:
    return next((c for c in api.call("GET", "/clubs/search?q=", token) if c["slug"] == slug), None)


def _get_acm_spec() -> dict:
    cfg_file = ROOT / "config" / "club_config.yaml"
    cfg = {}
    if cfg_file.exists():
        try:
            import yaml

            cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

    sh = cfg.get("student_head", {})
    ss = cfg.get("student_secretary", {})
    fc = cfg.get("faculty_chairman", {})
    fcc = cfg.get("faculty_co_chairman", {})
    venues_cfg = cfg.get("venues", {})

    people = []
    sh_name = sh.get("name", "Demo Student Head")
    people.append({
        "full_name": sh_name,
        "roll_no": sh.get("admission_no", "DEMO-001"),
        "branch": sh.get("branch", "Artificial Intelligence"),
        "role_key": "student_head",
        "designation": "Student Head",
    })
    ss_name = ss.get("name", "Demo Student Secretary")
    people.append({
        "full_name": ss_name,
        "roll_no": ss.get("admission_no", "DEMO-002"),
        "branch": ss.get("branch", "Artificial Intelligence"),
        "role_key": "student_secretary",
        "designation": "Student Secretary",
    })
    fc_name = fc.get("name", "Demo Faculty Chairman")
    people.append({
        "full_name": fc_name,
        "department": fc.get("department", "Computer Science & Engineering"),
        "role_key": "faculty_chairman",
        "designation": fc.get("designation", "Chairman, ACM Student Chapter SVNIT"),
    })
    fcc_name = fcc.get("name", "Demo Faculty Co-Chairman")
    people.append({
        "full_name": fcc_name,
        "department": fcc.get("department", "Computer Science & Engineering"),
        "role_key": "faculty_co_chairman",
        "designation": fcc.get("designation", "Co-Chairman, ACM Student Chapter SVNIT"),
    })

    venues = []
    sem_hall = venues_cfg.get("Seminar Hall", {})
    venues.append({
        "name": sem_hall.get("full_name", "Seminar Hall 402, Department of Computer Science & Engineering"),
        "short_name": sem_hall.get("short_name", "Seminar Hall 402"),
        "addressee_default": sem_hall.get("default_addressee", "HoD(CSE Dept.)"),
    })
    lab1 = venues_cfg.get("Lab 1", {})
    venues.append({
        "name": lab1.get("full_name", "Computer Center Lab 1"),
        "short_name": lab1.get("short_name", "CC Lab 1"),
        "addressee_default": lab1.get("default_addressee", "Head, Computer Center"),
    })

    return {
        "slug": "acm",
        "name": cfg.get("club_name", "ACM Student Chapter, SVNIT"),
        "short_name": cfg.get("club_short", "ACM"),
        "chapter_code": cfg.get("chapter_code", "6/52"),
        "logo": "assets/clubs/acm.png",
        "brand_color": "#007799",
        "department": cfg.get("department", "Computer Science & Engineering"),
        "department_short": cfg.get("department_short", "CSE"),
        "footer_text": "ACM Student Chapter · SVNIT Surat",
        "owner": {
            "name": sh_name,
            "position": "Chairperson",
        },
        "people": people,
        "venues": venues,
    }


def _restore_missing_logo(club_id: str, spec: dict) -> bool:
    """Give an existing demo club its logo when it has none, or its logo file never reached storage.

    Only the logo is touched, written the same way the logo upload endpoint does, so a club whose
    logo was uploaded but lost (for example when the bucket upload failed) recovers on the next start.
    """
    from server.app.core.database import SessionLocal
    from server.app.core.storage import get_storage
    from server.app.core.template_compiler import normalize_logo_image
    from server.app.models import Asset, Club

    logo = ROOT / spec["logo"] if spec.get("logo") else None
    if logo is None or not logo.exists():
        return False
    storage = get_storage()
    with SessionLocal() as db:
        club = db.query(Club).filter(Club.id == club_id).first()
        if club is None:
            return False
        settings = dict(club.settings or {})
        current = None
        if settings.get("logo_asset_id"):
            current = db.query(Asset).filter(Asset.id == settings["logo_asset_id"]).first()
        if current is None:
            current = (
                db.query(Asset)
                .filter(Asset.club_id == club.id, Asset.kind == "logo")
                .order_by(Asset.created_at.desc())
                .first()
            )
        if current is not None and storage.exists(current.storage_key):
            return False

        data = normalize_logo_image(logo.read_bytes())
        key, sha256 = storage.save_content_addressed("assets", data, "png")
        asset = db.query(Asset).filter(Asset.club_id == club.id, Asset.sha256 == sha256).first()
        if asset is None:
            asset = Asset(
                id=str(uuid.uuid4()), club_id=club.id, kind="logo", filename=logo.name, mime="image/png",
                sha256=sha256, size=len(data), storage_key=key, is_system=False,
            )
            db.add(asset)
            db.flush()
        settings["logo_asset_id"] = asset.id
        club.settings = settings
        db.commit()
        return True


def seed(no_ai: bool = False, owners_only: bool = False) -> list[dict[str, str]] | None:
    from server.app.core.rate_limit import clear_rate_limits
    from server.app.core.database import SessionLocal
    from server.app.models import Club

    is_production = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    if is_production and not owners_only:
        print("Error: full demo seeding is blocked when ENVIRONMENT=production. Use --owners-only.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA.read_text(encoding="utf-8"))
    domain, ay = data["email_domain"], data["academic_year"]

    if owners_only:
        password = os.environ.get("DEMO_OWNER_PASSWORD", "").strip()
        if not password or len(password) < 12:
            print("Error: DEMO_OWNER_PASSWORD environment variable is required and must be at least 12 characters long.", file=sys.stderr)
            sys.exit(1)
    else:
        password = data["password"]

    api = Api()
    accounts: list[dict[str, str]] = []
    report: list[str] = []
    has_failures = False

    for spec in data["clubs"]:
        clear_rate_limits()
        slug = spec["slug"]

        if owners_only:
            with SessionLocal() as db:
                existing_club = db.query(Club).filter(Club.slug == slug).first()

            owner_email = _email(slug, "owner", domain)
            if existing_club is not None:
                if _restore_missing_logo(existing_club.id, spec):
                    print(f"{existing_club.name}: logo was missing, added")
                print(f"{existing_club.name} ({owner_email}): already set up, skipped")
                report.append(f"{slug}: already set up, skipped")
                continue

            if slug == "acm" and "name" not in spec:
                spec = {**_get_acm_spec(), **spec}

            owner_name = spec.get("owner", {}).get("name", f"{spec.get('short_name', slug.upper())} Owner")
            owner_pos = spec.get("owner", {}).get("position", "Student Head/Chairperson")
            club_created_id = None
            try:
                owner_token = api.account(owner_email, owner_name, password)
                club = api.call("POST", "/clubs", owner_token, json={
                    "name": spec["name"], "short_name": spec["short_name"], "slug": slug,
                    "chapter_code": spec.get("chapter_code"), "academic_year_default": ay,
                    "position": owner_pos, "is_signatory": False,
                })
                club_created_id = club["id"]
                api.call("PUT", f"/clubs/{club['id']}", owner_token, json={
                    "department": spec.get("department") or "",
                    "settings": {
                        "department": spec.get("department") or "",
                        "department_short": spec.get("department_short") or "",
                        "brand_color": spec.get("brand_color"),
                        "footer_text": spec.get("footer_text") or "",
                        "institute_short": "SVNIT",
                        "institute_name": "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)",
                    },
                })
                for person in spec.get("people", []):
                    p = api.call("POST", f"/clubs/{club['id']}/people", owner_token, json={
                        k: person.get(k) for k in ("full_name", "roll_no", "branch", "department")
                    })
                    api.call("POST", f"/clubs/{club['id']}/roles", owner_token, json={
                        "person_id": p["id"], "role_key": person["role_key"],
                        "designation_label": person["designation"], "academic_year": ay,
                    })
                for venue in spec.get("venues", []):
                    api.call("POST", f"/clubs/{club['id']}/venues", owner_token, json=venue)

                if spec.get("logo"):
                    logo = ROOT / spec["logo"]
                    if logo.exists():
                        api.call("POST", f"/clubs/{club['id']}/logo", owner_token,
                                 files={"file": (logo.name, logo.read_bytes(), "image/png")})

                print(f"{spec['name']} ({owner_email}): created")
                report.append(f"{slug}: created")
                accounts.append({"club": spec["name"], "role": "owner", "email": owner_email})
            except Exception as exc:
                if club_created_id:
                    try:
                        with SessionLocal() as db_clean:
                            c = db_clean.query(Club).filter(Club.id == club_created_id).first()
                            if c:
                                db_clean.delete(c)
                                db_clean.commit()
                    except Exception:
                        pass
                print(f"Error setting up {slug}: {exc}", file=sys.stderr)
                report.append(f"{slug}: setup failed ({exc})")
                has_failures = True
            continue

        # 1. Owner and club (development full mode)
        if spec.get("existing"):
            owner_email, owner_password = "demo.owner@svnit.ac.in", "DemoOwnerPass123!"
            owner_token = api.account(owner_email, "Demo Club Head", owner_password)
            club = _club_by_slug(api, owner_token, slug)
            if club is None:
                report.append(f"{slug}: club not found, skipped (run the main seed first)")
                continue
            accounts.append({"club": club["name"], "role": "owner", "email": owner_email, "password": owner_password})
        else:
            owner_email = _email(slug, "owner", domain)
            owner_token = api.account(owner_email, spec["owner"]["name"], password)
            club = _club_by_slug(api, owner_token, slug)
            if club is None:
                club = api.call("POST", "/clubs", owner_token, json={
                    "name": spec["name"], "short_name": spec["short_name"], "slug": slug,
                    "chapter_code": spec.get("chapter_code"), "academic_year_default": ay,
                    "position": spec["owner"]["position"], "is_signatory": False,
                })
                api.call("PUT", f"/clubs/{club['id']}", owner_token, json={
                    "department": spec.get("department") or "",
                    "settings": {
                        "department": spec.get("department") or "",
                        "department_short": spec.get("department_short") or "",
                        "brand_color": spec.get("brand_color"),
                        "footer_text": spec.get("footer_text") or "",
                        "institute_short": "SVNIT",
                        "institute_name": "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)",
                    },
                })
                people_ids = {}
                for person in spec.get("people", []):
                    p = api.call("POST", f"/clubs/{club['id']}/people", owner_token, json={
                        k: person.get(k) for k in ("full_name", "roll_no", "branch", "department")
                    })
                    people_ids[person["full_name"]] = p["id"]
                    api.call("POST", f"/clubs/{club['id']}/roles", owner_token, json={
                        "person_id": p["id"], "role_key": person["role_key"],
                        "designation_label": person["designation"], "academic_year": ay,
                    })
                for venue in spec.get("venues", []):
                    api.call("POST", f"/clubs/{club['id']}/venues", owner_token, json=venue)
                report.append(f"{slug}: club created")
            accounts.append({"club": club["name"], "role": "owner", "email": owner_email, "password": password})

        # Logo from the club's own entry (uploading the same file again is a no-op)
        if spec.get("logo"):
            logo = ROOT / spec["logo"]
            api.call("POST", f"/clubs/{club['id']}/logo", owner_token,
                     files={"file": (logo.name, logo.read_bytes(), "image/png")})

        # 2. Members join and are approved with their access level
        pending = {jr["user_email"]: jr for jr in api.call("GET", f"/clubs/{club['id']}/join-requests?status=pending", owner_token)}
        for role, name in spec.get("users", {}).items():
            email = _email(slug, role, domain)
            token = api.account(email, name, password)
            perms = api.client.get(f"/api/v1/clubs/{club['id']}/permissions", headers={"Authorization": f"Bearer {token}"})
            if perms.status_code != 200:
                if email not in pending:
                    jr = api.call("POST", f"/clubs/{club['id']}/join-requests", token, json={
                        "position": ROLE_POSITIONS[role],
                        "requested_role": "viewer" if role == "viewer" else "editor",
                        "message": "Demo account",
                    })
                    pending[email] = jr
                api.call("POST", f"/clubs/{club['id']}/join-requests/{pending[email]['id']}/approve", owner_token,
                         json={"role": role, "is_signatory": False})
            accounts.append({"club": club["name"], "role": role, "email": email, "password": password})

        # 3. One applicant left pending so owners can try the approval flow
        applicant_email = _email(slug, "applicant", domain)
        applicant_token = api.account(applicant_email, f"New Member ({spec.get('short_name', slug.upper())})", password)
        if api.client.get(f"/api/v1/clubs/{club['id']}/permissions",
                          headers={"Authorization": f"Bearer {applicant_token}"}).status_code != 200 \
                and applicant_email not in pending:
            api.call("POST", f"/clubs/{club['id']}/join-requests", applicant_token, json={
                "position": "Executive Member", "requested_role": "editor",
                "message": "I would like to help prepare event documents.",
            })
        accounts.append({"club": club["name"], "role": "applicant (pending)", "email": applicant_email, "password": password})

        # 4. Club templates drafted by AI from plain-English descriptions, reviewed and published
        if not no_ai:
            existing = {t["name"] for t in api.call("GET", f"/clubs/{club['id']}/documents/templates", owner_token)
                        if not t.get("is_system")}
            wanted = spec.get("templates", [])
            if len(existing) >= len(wanted):
                wanted = []
                report.append(f"{slug}: club templates already present")
            for description in wanted:
                try:
                    clear_rate_limits()
                    draft = api.call("POST", f"/clubs/{club['id']}/documents/templates/ai-draft", owner_token,
                                     json={"description": description})
                    tmpl = draft["template"]
                    if tmpl["name"] in existing:
                        api.call("DELETE", f"/clubs/{club['id']}/documents/templates/{tmpl['id']}", owner_token, expect=(200, 204))
                        report.append(f"{slug}: template '{tmpl['name']}' already existed")
                        continue
                    api.call("POST", f"/clubs/{club['id']}/documents/templates/{tmpl['id']}/review-ai", owner_token, json={"all": True})
                    api.call("POST", f"/clubs/{club['id']}/documents/templates/{tmpl['id']}/publish", owner_token)
                    existing.add(tmpl["name"])
                    report.append(f"{slug}: published AI template '{tmpl['name']}'")
                except Exception as exc:  # AI may be rate-limited; demo still works without these
                    report.append(f"{slug}: AI template skipped ({str(exc)[:160]})")

    if not owners_only:
        _write_accounts(accounts, password)
        print("\n".join(report))

    if has_failures:
        return None
    return accounts


def _write_accounts(accounts: list[dict[str, str]], password: str) -> None:
    lines = [
        "# Demo accounts (development only)",
        "",
        "Created by `python -m server.scripts.seed_demo_clubs`. Club names and logos are from",
        "[SVNIT's Chapters | Clubs | Society page](https://www.svnit.ac.in/web/Student_Chapter);",
        "the people and accounts are fictional. Do not use these in production.",
        "",
        f"All demo accounts except the ACM owner use the password `{password}`.",
        "",
        "| Club | Role | Email | Password |",
        "|---|---|---|---|",
    ]
    for a in accounts:
        lines.append(f"| {a['club']} | {a['role']} | `{a['email']}` | `{a['password']}` |")
    lines += [
        "",
        "Roles: **owner/admin** approve members and documents; **editor** creates documents and templates;",
        "**viewer** can only read; **applicant** has a pending join request for the owner to approve.",
        "",
    ]
    ACCOUNTS_DOC.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-ai", action="store_true", help="skip AI-drafted club templates")
    parser.add_argument("--owners-only", action="store_true", help="one-time setup: 5 clubs, logos and owners only")
    args = parser.parse_args()
    res = seed(no_ai=args.no_ai, owners_only=args.owners_only)
    sys.exit(0 if res is not None else 1)
