"""Seed demo SVNIT clubs, accounts and club templates through the public API.

Everything goes through the same endpoints a real club uses (register, create club, upload
logo, join requests and approvals, people, venues, AI template drafting, review and publish),
so the demo is created the way a club would set itself up. Safe to re-run.

    python -m server.scripts.seed_demo_clubs            # with AI-drafted club templates
    python -m server.scripts.seed_demo_clubs --no-ai    # skip AI template drafting

Development only. Credentials are written to docs/DEMO_ACCOUNTS.md.
"""

from __future__ import annotations

import argparse
import json
import sys
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
        return self.call("POST", "/auth/register", json={"email": email, "password": password, "name": name})["access_token"]


def _email(slug: str, role: str, domain: str) -> str:
    return f"{slug}.{role}@{domain}"


def _club_by_slug(api: Api, token: str, slug: str) -> Optional[dict]:
    return next((c for c in api.call("GET", "/clubs/search?q=", token) if c["slug"] == slug), None)


def seed(no_ai: bool = False) -> list[dict[str, str]]:
    from server.app.core.rate_limit import clear_rate_limits

    data = json.loads(DATA.read_text(encoding="utf-8"))
    password, domain, ay = data["password"], data["email_domain"], data["academic_year"]
    api = Api()
    accounts: list[dict[str, str]] = []
    report: list[str] = []

    for spec in data["clubs"]:
        clear_rate_limits()
        slug = spec["slug"]

        # 1. Owner and club
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
            # AI may name a re-draft differently, so a club that already has its templates is left alone
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

    _write_accounts(accounts, password)
    print("\n".join(report))
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
    args = parser.parse_args()
    sys.exit(0 if seed(no_ai=args.no_ai) is not None else 1)
