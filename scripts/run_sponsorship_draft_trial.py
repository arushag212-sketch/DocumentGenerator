"""Run real template-draft endpoint for sponsorship request letter and output field names & block types."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env
from server.app.core.config import _load_env_file
_load_env_file()

# CRITICAL: Isolate from data/clubdocs.db
TEMP_DB = Path("data/temp_w6cd_trial.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"

from fastapi.testclient import TestClient
from docgen.llm import GeminiLLMClient, set_llm_client
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.scripts.seed import seed
from server.app.core.database import SessionLocal
from server.app.models import Club


def main():
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception:
            pass

    seed(clean=True)
    clear_rate_limits()

    # Configure live Gemini client with configured model
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    gemini_client = GeminiLLMClient(api_key=api_key, model=model)
    set_llm_client(gemini_client)

    client = TestClient(app)

    # 1. Login as demo owner
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get ACM club id
    db = SessionLocal()
    club = db.query(Club).filter(Club.slug == "acm").first()
    club_id = club.id
    db.close()

    # 3. Request AI draft
    prompt = (
        "A sponsorship request letter to a company with event name, date, venue, "
        "a table of sponsorship tiers with an amount for each, and signatures for the coordinator and the faculty advisor."
    )

    res = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/ai-draft",
        json={"description": prompt},
        headers=headers,
    )

    if res.status_code != 201:
        print(f"ERROR {res.status_code}: {res.text}")
        sys.exit(1)

    data = res.json()
    draft = data.get("draft", {})
    editor_json = draft.get("editor_json", {})
    blocks = editor_json.get("content", [])
    fields = draft.get("fields", [])

    field_names = [f.get("key") for f in fields]
    block_types = [b.get("type") for b in blocks]

    print("--- TRIAL RESULT ---")
    print(f"FIELD NAMES: {json.dumps(field_names)}")
    print(f"BLOCK TYPES: {json.dumps(block_types)}")

    # Cleanup temp db
    if TEMP_DB.exists():
        try:
            TEMP_DB.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
