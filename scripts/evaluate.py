"""End-to-end evaluation against the Track 1 criteria.

Sends realistic natural-language requests from the demo clubs' editor accounts through the
real API (as the web app does), answers the questions the system asks the way a club member
would, generates the documents and checks the PDFs. Results go to docs/EVALUATION.md.

    python scripts/evaluate.py            # needs the demo clubs (server/scripts/seed_demo_clubs.py)

Uses the configured LLM (Gemini) for extraction fallback and template drafting.
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402

PASSWORD = "ClubDocs@123"
DOMAIN = "demo.svnit.ac.in"
BAD_TOKENS = ["{{", "}}", "{%", "%}", "None", "null", "undefined", "[AI-drafted"]


@dataclass
class DocCase:
    club: str
    text: str
    expect_docs: list[str]                       # template names that must be recommended (exactly)
    answers: dict[str, Any]                      # what the member types into the asked questions
    must_contain: list[str]                      # facts that must appear in the generated PDFs
    must_not_contain: list[str] = field(default_factory=list)  # facts nobody stated (no fabrication)
    rows: Optional[list[dict[str, str]]] = None  # per-row batch (e.g. certificates)
    expect_pages: Optional[int] = None


@dataclass
class TemplateCase:
    club: str
    description: str
    expect_fields: list[str]                     # field keys (or key fragments) the template should have
    expect_landscape: bool = False


DOC_CASES = [
    DocCase(
        "acm",
        "We are conducting a two-day Web Development Workshop on 14–15 October in Seminar Hall for around 120 students.",
        ["Permission Letter", "Event Proposal"],
        {"time_start": "10:00", "time_end": "17:00", "submitted_to": "Head of Department, Computer Science & Engineering"},
        ["Web Development Workshop", "Seminar Hall", "120", "10:00 AM", "05:00 PM", "Head of Department"],
        ["Rs.", "₹", "Dr. "],
    ),
    DocCase(
        "gdgc",
        "We're organising a Flutter Forward study jam on 8 November 2026 from 2 PM to 5 PM in CC Lab 2 for 60 students.",
        ["Permission Letter", "Event Proposal"],
        {"submitted_to": "Head, Computer Centre"},
        ["Flutter Forward", "CC Lab 2", "60", "02:00 PM", "GDGC"],
        ["Seminar Hall"],
    ),
    DocCase(
        "raag",
        "Write a sponsorship letter to Yamaha Music India for our annual concert Swar Sandhya. About 400 attendees, at the SAC Auditorium on 12 January 2027.",
        ["Sponsorship Request Letter"],
        {"company_name": "Yamaha Music India", "contact_name": "Aarohi Deshpande"},
        ["Yamaha Music India", "Swar Sandhya", "SAC Auditorium", "400", "Raag"],
        ["Mahindra", "₹"],
    ),
    DocCase(
        "chrd",
        "Need certificates of participation for the Garba Night held on 20 October 2026.",
        ["Certificate of Participation"],
        {},
        ["Riya Patel", "Aman Verma", "Zoya Sheikh", "Garba Night", "CERTIFICATE OF PARTICIPATION"],
        [],
        rows=[{"recipient_name": "Riya Patel"}, {"recipient_name": "Aman Verma"}, {"recipient_name": "Zoya Sheikh"}],
        expect_pages=1,
    ),
    DocCase(
        "drishti",
        "Post a notice about recruitment for the Drishti robotics team. Registrations close on 30 November 2026.",
        ["Notice / Circular"],
        {"notice_title": "Robotics Team Recruitment",
         "notice_body": "Drishti is recruiting first and second year students for its robotics team. Registrations close on 30 November 2026."},
        ["Robotics Team Recruitment", "30 November 2026", "Drishti"],
        ["Venue:", "Auditorium"],
    ),
    DocCase(
        "acm",
        "Minutes of the core committee meeting held on 18 October 2026 in the ACM Lab to plan the hackathon logistics.",
        ["Minutes of Meeting"],
        # The member answers the questions the system asks for minutes
        {"meeting_title": "Core Committee Meeting", "meeting_date": "18/10/2026", "venue": "ACM Lab",
         "attendees": ["Riya Desai", "Kabir Shah", "Neha Iyer"],
         "agenda_items": [{"topic": "Hackathon logistics", "discussion": "Venue, food and Wi-Fi for 200 participants",
                           "decision": "Kabir Shah to book the venue by 25 October"}]},
        ["Core Committee Meeting", "Riya Desai", "Hackathon logistics", "Kabir Shah to book the venue"],
        ["Seminar Hall"],
    ),
]

TEMPLATE_CASES = [
    TemplateCase("acm", "create a certificate for acm summer challenge 2026 for the first palce name arush agrawal with a golden border and the sign of 3 judges",
                 ["recipient", "position", "event"], expect_landscape=True),
    TemplateCase("drishti", "A gate pass letter to the Chief Security Officer to take equipment out of campus for an exhibition, with exhibition name, dates, a table of items with quantity and serial number, and signatures of the convener and faculty in-charge",
                 ["exhibition", "item", "date"]),
    TemplateCase("gdgc", "An attendance sheet for a workshop with workshop name, date, venue and a table of attendees with roll number, name and signature",
                 ["workshop", "attendee", "venue"]),
]


class Api:
    def __init__(self):
        from fastapi.testclient import TestClient

        from server.app.main import app

        self.client = TestClient(app)
        self.tokens: dict[str, str] = {}

    def token(self, email: str, password: str) -> str:
        if email not in self.tokens:
            res = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
            res.raise_for_status()
            self.tokens[email] = res.json()["access_token"]
        return self.tokens[email]

    def call(self, method, path, email, password=PASSWORD, **kw):
        res = self.client.request(method, f"/api/v1{path}", headers={"Authorization": f"Bearer {self.token(email, password)}"}, **kw)
        is_json = res.content and res.headers.get("content-type", "").startswith("application/json")
        return res.status_code, (res.json() if is_json else res.content)


def club_id(api: Api, slug: str, email: str) -> str:
    _, clubs = api.call("GET", "/clubs/search?q=", email)
    return next(c["id"] for c in clubs if c["slug"] == slug)


def run_doc_case(api: Api, case: DocCase) -> dict[str, Any]:
    from server.app.core.rate_limit import clear_rate_limits

    clear_rate_limits()
    email = f"{case.club}.editor@{DOMAIN}"
    cid = club_id(api, case.club, email)
    started = time.time()
    result: dict[str, Any] = {"club": case.club, "text": case.text, "errors": []}

    _, und = api.call("POST", f"/clubs/{cid}/home/understand", email, json={"text": case.text})
    recommended = [d["name"] for d in und["recommended_documents"] if d["recommended"]]
    result["recommended"] = recommended
    result["recommend_ok"] = sorted(recommended) == sorted(case.expect_docs)
    selected = [d["template_id"] for d in und["recommended_documents"] if d["name"] in case.expect_docs]
    if not selected:
        result["errors"].append("expected documents not available")
        return result

    # Re-understand for the selected documents to get their questions
    _, und = api.call("POST", f"/clubs/{cid}/home/understand", email, json={"text": case.text, "selected_template_ids": selected})
    understood = und["understood"]
    questions = [q for q in und["missing_questions"] if q["key"] not in ("dates_confirmation",)]
    result["auto_filled"] = sorted(k for k, v in understood.items() if v and k != "raw")
    result["asked"] = [q["key"] for q in questions]

    event_data = dict(understood.get("raw") or {})
    for k in ("event_name", "venue", "date_start", "date_end", "time_start", "time_end", "participants", "description", "objectives"):
        if understood.get(k):
            event_data[k] = understood[k]
    for q in questions:  # prefilled values the member accepts
        if q.get("current_value") not in (None, ""):
            event_data[q["key"]] = q["current_value"]
    event_data.update(case.answers)
    for k in ("description", "objectives"):  # the member accepts or edits AI drafts explicitly
        if isinstance(event_data.get(k), str):
            event_data[k] = event_data[k].replace("[AI-drafted, review]", "").strip()
    if understood.get("date_start") and understood.get("date_end"):
        event_data["dates_confirmed"] = True
    elif understood.get("dates"):
        event_data["dates"] = understood["dates"]
        event_data["dates_confirmed"] = True
    if case.rows:
        event_data["rows"] = case.rows

    status, gen = api.call("POST", f"/clubs/{cid}/home/generate", email, json={
        "selected_template_ids": selected, "event_data": event_data, "ref_numbers_accepted": True,
        "event_title": understood.get("event_name") or "Evaluation",
    })
    result["seconds"] = round(time.time() - started, 1)
    if status != 200:
        result["errors"].append(f"generate {status}: {json.dumps(gen)[:300]}")
        return result

    texts, pages = [], []
    for d in gen["documents"]:
        s, pdf = api.call("GET", d["pdf_url"].replace("/api/v1", ""), email)
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        texts.append("".join(p.get_text() for p in doc))
        pages.append(len(doc))
    all_text = "\n".join(texts)
    result["documents"] = [d["title"] for d in gen["documents"]]
    result["ref_nos"] = [d["ref_no"] for d in gen["documents"]]
    result["pages"] = pages
    result["missing_facts"] = [f for f in case.must_contain if f not in all_text]
    result["fabricated"] = [f for f in case.must_not_contain if f in all_text]
    result["artefacts"] = sorted({t for t in BAD_TOKENS if t in all_text})
    result["pages_ok"] = case.expect_pages is None or all(p == case.expect_pages for p in pages)
    return result


def run_template_case(api: Api, case: TemplateCase) -> dict[str, Any]:
    from server.app.core.rate_limit import clear_rate_limits

    clear_rate_limits()
    email = f"{case.club}.editor@{DOMAIN}"
    cid = club_id(api, case.club, email)
    started = time.time()
    status, draft = api.call("POST", f"/clubs/{cid}/documents/templates/ai-draft", email, json={"description": case.description})
    out: dict[str, Any] = {"club": case.club, "description": case.description, "seconds": round(time.time() - started, 1)}
    if status not in (200, 201):
        out["error"] = f"{status}: {json.dumps(draft)[:200]}"
        return out
    ej = draft["draft"]["editor_json"]
    keys = [f["key"] for f in draft["draft"].get("fields", [])]
    out["name"] = draft["template"]["name"]
    out["fields"] = keys
    out["blocks"] = [b.get("type") for b in ej.get("content", [])]
    def all_keys(node):  # field keys plus table column keys anywhere in the document
        if isinstance(node, dict):
            yield from ([node["key"]] if isinstance(node.get("key"), str) else [])
            for v in node.values():
                yield from all_keys(v)
        elif isinstance(node, list):
            for v in node:
                yield from all_keys(v)
    every_key = set(keys) | set(all_keys(ej))
    out["fields_ok"] = all(any(frag in k for k in every_key) for frag in case.expect_fields)
    out["landscape_ok"] = (not case.expect_landscape) or (ej.get("design_settings") or {}).get("orientation") == "landscape"
    out["valid"] = bool((draft["draft"].get("validation_report") or {}).get("is_valid", True))
    # Clean up: evaluation drafts are not kept
    api.call("DELETE", f"/clubs/{cid}/documents/templates/{draft['template']['id']}", email)
    return out


def write_report(docs: list[dict], tmpls: list[dict]) -> None:
    def yes(b):  # noqa: ANN001
        return "Yes" if b else "No"

    lines = ["# Evaluation", "",
             "Generated by `python scripts/evaluate.py` against the demo clubs, through the same API the web app uses.",
             "Each request is plain English from a club member; the member then answers only the questions the system asks.", "",
             "## Document generation", "",
             "| Club | Request | Recommended | Right docs | Asked | Facts present | Unstated facts | Artefacts | Pages | Time |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in docs:
        if r.get("errors"):
            lines.append(f"| {r['club']} | {r['text'][:60]}… | {', '.join(r.get('recommended', []))} | – | – | – | – | {'; '.join(r['errors'])[:80]} | – | – |")
            continue
        lines.append(
            f"| {r['club']} | {r['text'][:60]}… | {', '.join(r['recommended'])} | {yes(r['recommend_ok'])} | "
            f"{', '.join(r['asked']) or 'nothing'} | {'all' if not r['missing_facts'] else 'missing: ' + ', '.join(r['missing_facts'])} | "
            f"{'none' if not r['fabricated'] else ', '.join(r['fabricated'])} | {'none' if not r['artefacts'] else ', '.join(r['artefacts'])} | "
            f"{', '.join(map(str, r['pages']))} | {r['seconds']}s |")
    lines += ["", "## Template generation from a description", "",
              "| Club | Description | Template | Fields | Expected fields | Layout | Time |", "|---|---|---|---|---|---|---|"]
    for t in tmpls:
        if t.get("error"):
            lines.append(f"| {t['club']} | {t['description'][:60]}… | error: {t['error']} | – | – | – | {t['seconds']}s |")
            continue
        lines.append(f"| {t['club']} | {t['description'][:60]}… | {t['name']} | {', '.join(t['fields'])} | {yes(t['fields_ok'])} | "
                     f"{'landscape' if t['landscape_ok'] and 'certificate' in t['description'] else 'ok' if t['landscape_ok'] else 'wrong'} | {t['seconds']}s |")
    ok_docs = [r for r in docs if not r.get("errors")]
    lines += ["", "## Summary against the evaluation criteria", "",
              f"- **Practical club utility / automatic detection**: {sum(r['recommend_ok'] for r in ok_docs)}/{len(docs)} requests got exactly the right documents.",
              f"- **Accuracy**: {sum(not r['missing_facts'] for r in ok_docs)}/{len(ok_docs)} with every stated fact present; "
              f"{sum(not r['fabricated'] for r in ok_docs)}/{len(ok_docs)} with no unstated facts.",
              f"- **Document quality**: {sum(not r['artefacts'] for r in ok_docs)}/{len(ok_docs)} free of template artefacts; "
              f"{sum(r['pages_ok'] for r in ok_docs)}/{len(ok_docs)} with the expected page count.",
              f"- **Template flexibility**: {sum(1 for t in tmpls if not t.get('error') and t['fields_ok'])}/{len(tmpls)} templates drafted from a sentence with the expected fields.",
              f"- **Reliability**: {len(ok_docs)}/{len(docs)} generation runs completed without errors.", ""]
    (ROOT / "docs" / "EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    api = Api()
    docs = []
    for case in DOC_CASES:
        try:
            docs.append(run_doc_case(api, case))
        except Exception as exc:  # report and continue
            docs.append({"club": case.club, "text": case.text, "errors": [f"{type(exc).__name__}: {str(exc)[:200]}"]})
        print(json.dumps(docs[-1], default=str)[:600])
    tmpls = []
    for case in TEMPLATE_CASES:
        try:
            tmpls.append(run_template_case(api, case))
        except Exception as exc:
            tmpls.append({"club": case.club, "description": case.description, "error": str(exc)[:200], "seconds": 0})
        print(json.dumps(tmpls[-1], default=str)[:600])
    write_report(docs, tmpls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
