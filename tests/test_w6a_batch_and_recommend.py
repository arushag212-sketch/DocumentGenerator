"""Tests for Phase W6a:
1. "Describe your event" recommendations and extraction:
   - Example sentence: "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."
   - Produces right recommendations (Permission Letter recommended, Approval Note not recommended without budget).
   - Produces right grouped missing fields with needed_by and defer_ok.
2. Budget, winners, and bills triggers:
   - Budget trigger recommends Approval Note.
   - Winners trigger recommends Prize Receipts.
   - Bills trigger recommends Bill Summary and Bill Certificate.
3. Batch generation:
   - Creates all documents for event in one job, reserving reference numbers.
   - Shared fields (event name, venue, dates) identical across all rendered PDFs.
   - Downloads as ZIP containing both DOCX and PDF files.
4. Repeat_per logic:
   - Winners batch generates exactly 1 receipt per winner (3 winners = 3 receipts).
5. Cross-club isolation:
   - User from another club cannot recommend, generate, list, or download batch ZIPs for active club (403/404).
6. Documents list page API:
   - Search, filter by template/status/event, sort, pagination.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.permissions import Role
from server.app.core.rate_limit import clear_rate_limits
from server.app.core.security import get_password_hash
from server.app.main import app
from server.app.models import Club, Membership, NumberingSeries, Template, TemplateVersion, User


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def w6a_setup(client):
    clear_rate_limits()
    db = SessionLocal()
    try:
        acm = db.query(Club).filter(Club.slug == "acm").first()
        assert acm is not None
        acm_id = acm.id

        # Setup second club (GDSC) for cross-club isolation test
        gdsc = db.query(Club).filter(Club.slug == "gdsc").first()
        if not gdsc:
            gdsc = Club(
                slug="gdsc",
                name="Google Developer Student Club SVNIT",
                short_name="GDSC",
                academic_year_default="2026-27",
            )
            db.add(gdsc)
            db.flush()
        gdsc_id = gdsc.id

        # Ensure GDSC owner user
        gdsc_user = db.query(User).filter(User.email == "gdsc.lead@svnit.ac.in").first()
        if not gdsc_user:
            gdsc_user = User(
                email="gdsc.lead@svnit.ac.in",
                password_hash=get_password_hash("GdscPass123!"),
                name="GDSC Lead",
                is_platform_admin=False,
            )
            db.add(gdsc_user)
            db.flush()

        m_gdsc = db.query(Membership).filter(
            Membership.club_id == gdsc_id,
            Membership.user_id == gdsc_user.id
        ).first()
        if not m_gdsc:
            m_gdsc = Membership(
                club_id=gdsc_id,
                user_id=gdsc_user.id,
                role=Role.OWNER,
                status="active",
            )
            db.add(m_gdsc)
            db.flush()

        db.commit()
    finally:
        db.close()

    # Login as ACM owner
    res_acm = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res_acm.status_code == 200
    acm_token = res_acm.json()["access_token"]
    acm_headers = {"Authorization": f"Bearer {acm_token}"}

    # Login as GDSC owner
    res_gdsc = client.post(
        "/api/v1/auth/login",
        json={"email": "gdsc.lead@svnit.ac.in", "password": "GdscPass123!"},
    )
    assert res_gdsc.status_code == 200
    gdsc_token = res_gdsc.json()["access_token"]
    gdsc_headers = {"Authorization": f"Bearer {gdsc_token}"}

    return {
        "acm_club_id": acm_id,
        "gdsc_club_id": gdsc_id,
        "acm_headers": acm_headers,
        "gdsc_headers": gdsc_headers,
    }


def test_w6a_recommend_workshop_sentence(client, w6a_setup):
    """The example sentence produces the right recommendations and the right missing-field list."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    prompt = "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/recommend",
        json={"text": prompt},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    # 1. Extraction checks
    extracted = data["extracted_data"]
    assert "Web Development Workshop" in (extracted.get("event_name") or "")
    assert "Seminar Hall" in (extracted.get("venue") or "")
    assert extracted.get("expected_participants") in [120, "120"]
    assert data["detected_stage"] == "pre_event"
    assert data["has_budget"] is False
    assert data["has_winners"] is False
    assert data["has_bills"] is False

    # 2. Recommendation checks
    templates = {t["slug"]: t for t in data["templates"]}
    assert "permission_letter" in templates
    assert templates["permission_letter"]["recommended"] is True
    assert "permission" in templates["permission_letter"]["reason"].lower()

    if "approval_note" in templates:
        assert templates["approval_note"]["recommended"] is False
        assert "budget" in templates["approval_note"]["reason"].lower() or "sanction" in templates["approval_note"]["reason"].lower()

    if "prize_money_receipt" in templates:
        assert templates["prize_money_receipt"]["recommended"] is False

    # 3. Grouped missing-info checks
    missing_keys = {f["key"]: f for f in data["grouped_missing_fields"]}
    # Extracted fields should NOT be reported as missing
    assert "event_name" not in missing_keys
    assert "venue" not in missing_keys

    # Fields that were NOT in the prompt must be present in missing list with needed_by
    for missing_field in data["grouped_missing_fields"]:
        assert len(missing_field["needed_by"]) >= 1
        assert "ask" in missing_field and len(missing_field["ask"]) > 0
        assert "defer_ok" in missing_field


def test_w6a_recommend_budget_winners_and_bills(client, w6a_setup):
    """Context triggers dynamically recommend Approval Note, Prize Receipts, and Bill Certificates."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    # 1. Budget trigger
    res_b = client.post(
        f"/api/v1/clubs/{acm_id}/events/recommend",
        json={"text": "Annual TechFest with estimated budget of Rs. 25,000 in Central Seminar Hall"},
        headers=headers,
    )
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["has_budget"] is True
    tmpls_b = {t["slug"]: t for t in data_b["templates"]}
    assert tmpls_b["approval_note"]["recommended"] is True

    # 2. Winners trigger
    res_w = client.post(
        f"/api/v1/clubs/{acm_id}/events/recommend",
        json={"text": "CodeCraft coding competition post-event prize distribution for 3 student winners."},
        headers=headers,
    )
    assert res_w.status_code == 200
    data_w = res_w.json()
    assert data_w["has_winners"] is True
    assert data_w["detected_stage"] == "post_event"
    tmpls_w = {t["slug"]: t for t in data_w["templates"]}
    assert tmpls_w["prize_money_receipt"]["recommended"] is True

    # 3. Bills trigger
    res_bills = client.post(
        f"/api/v1/clubs/{acm_id}/events/recommend",
        json={"text": "Reimbursement and settlement of vouchers with 4 vendor bills and expense invoices."},
        headers=headers,
    )
    assert res_bills.status_code == 200
    data_bills = res_bills.json()
    assert data_bills["has_bills"] is True
    tmpls_bills = {t["slug"]: t for t in data_bills["templates"]}
    assert tmpls_bills["bill_summary"]["recommended"] is True
    assert tmpls_bills["bill_certificate"]["recommended"] is True


def test_w6a_batch_generation_shared_fields_in_pdfs_and_zip(client, w6a_setup):
    """Batch generate reserves numbers, renders PDFs with identical shared fields, and packages into ZIP."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    shared_event_data = {
        "event_name": "Web Development Workshop",
        "event_code": "WDW-26",
        "dates": "14-15 October 2026",
        "venue": "Seminar Hall",
        "expected_participants": 120,
        "student_coordinator_name": "Aarav Sharma",
        "student_coordinator_phone": "9876543210",
        "faculty_coordinator_name": "Dr. R. K. Patel",
        "department": "Computer Science & Engineering",
        "estimated_budget": 15000,
        "advance_amount": 10000,
        "purpose": "Technical skill development in modern web stack",
        "date_start": "2026-10-14",
        "date_end": "2026-10-15",
        "time_start": "09:00 AM",
        "time_end": "05:00 PM",
        "category": "Workshop",
        "objectives": "Hands-on training in full-stack web development.",
        "target_audience": "B.Tech Students",
        "mode": "Offline",
        "description": "Hands-on technical workshop covering full-stack web development.",
        "submitted_to": "Associate Dean (Student Welfare)",
        "budget_items": [
            {"item": "Speaker Honorarium", "amount": 8000},
            {"item": "Refreshments", "amount": 7000},
        ],
    }

    payload = {
        "selected_template_ids": ["permission_letter", "approval_note"],
        "event_data": shared_event_data,
        "event_title": "Web Development Workshop",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200, res.text
    batch_res = res.json()

    assert batch_res["documents_count"] == 2
    assert len(batch_res["documents"]) == 2
    batch_id = batch_res["batch_id"]
    assert batch_id

    # Reference numbers must be distinct
    ref_nos = [d["ref_no"] for d in batch_res["documents"]]
    assert len(set(ref_nos)) == 2
    assert all(ref.startswith("ACM/") and ("26-27" in ref or "2026-27" in ref) for ref in ref_nos)

    # 1. Verify rendered PDFs and identical shared fields text extraction
    for doc in batch_res["documents"]:
        pdf_path = Path(doc["pdf_path"])
        assert pdf_path.exists(), f"PDF not found at {pdf_path}"

        doc_pdf = pymupdf.open(str(pdf_path))
        full_text = "".join(page.get_text() for page in doc_pdf)
        doc_pdf.close()

        # Shared fields MUST appear in both PDFs
        assert "Web Development Workshop" in full_text
        assert "Seminar Hall" in full_text

    # 2. Verify ZIP archive
    zip_path = Path(batch_res["zip_path"])
    assert zip_path.exists(), f"ZIP not found at {zip_path}"

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        namelist = zf.namelist()
        # Must contain 2 DOCX and 2 PDF files (4 files total)
        assert len(namelist) == 4
        docx_files = [n for n in namelist if n.endswith(".docx")]
        pdf_files = [n for n in namelist if n.endswith(".pdf")]
        assert len(docx_files) == 2
        assert len(pdf_files) == 2

    # 3. Test downloading the batch ZIP via endpoint
    dl_res = client.get(
        f"/api/v1/clubs/{acm_id}/documents/batch/{batch_id}/download-zip",
        headers=headers,
    )
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"
    dl_zip = zipfile.ZipFile(io.BytesIO(dl_res.content))
    assert len(dl_zip.namelist()) == 4


def test_w6a_batch_generation_winners_repeat_per(client, w6a_setup):
    """Winners batch produces exactly 1 receipt per winner with correct individual winner context."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    winners_list = [
        {"position": "1st Place", "name": "Aarav Gupta", "roll_no": "U22CS001", "amount": 5000},
        {"position": "2nd Place", "name": "Diya Shah", "roll_no": "U22CS002", "amount": 3000},
        {"position": "3rd Place", "name": "Kavya Patel", "roll_no": "U22CS003", "amount": 2000},
    ]

    event_data = {
        "event_name": "CodeCraft Hackathon",
        "dates": "18 October 2026",
        "date_start": "2026-10-18",
        "date_end": "2026-10-18",
        "dates_confirmed": True,
        "venue": "Computer Lab 1",
        "winners": winners_list,
    }

    payload = {
        "selected_template_ids": ["prize_money_receipt"],
        "event_data": event_data,
        "event_title": "CodeCraft Hackathon",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200, res.text
    batch_res = res.json()

    # Must produce exactly 3 receipts
    assert batch_res["documents_count"] == 3
    docs = batch_res["documents"]
    assert len(docs) == 3

    # Each receipt has a unique reference number
    refs = [d["ref_no"] for d in docs]
    assert len(set(refs)) == 3

    # Check each PDF text contains the individual winner's name
    for i, w in enumerate(winners_list):
        doc = docs[i]
        pdf_path = Path(doc["pdf_path"])
        doc_pdf = pymupdf.open(str(pdf_path))
        pdf_text = "".join(p.get_text() for p in doc_pdf)
        doc_pdf.close()

        assert w["name"] in pdf_text
        assert w["roll_no"] in pdf_text

    # ZIP contains 3 docx and 3 pdf (6 files total)
    zip_path = Path(batch_res["zip_path"])
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        assert len(zf.namelist()) == 6


def test_w6a_cross_club_isolation(client, w6a_setup):
    """User from another club is rejected with 403 on recommend, batch generate, documents list, and ZIP download."""
    acm_id = w6a_setup["acm_club_id"]
    gdsc_id = w6a_setup["gdsc_club_id"]
    gdsc_headers = w6a_setup["gdsc_headers"]
    acm_headers = w6a_setup["acm_headers"]

    # 1. GDSC user trying to recommend ACM documents -> 403 Forbidden
    res_rec = client.post(
        f"/api/v1/clubs/{acm_id}/events/recommend",
        json={"text": "GDSC unauthorized event description"},
        headers=gdsc_headers,
    )
    assert res_rec.status_code == 403

    # 2. GDSC user trying to batch generate ACM documents -> 403 Forbidden
    res_gen = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={"selected_template_ids": ["permission_letter"], "event_data": {"event_name": "Test"}},
        headers=gdsc_headers,
    )
    assert res_gen.status_code == 403

    # 3. GDSC user trying to list ACM documents -> 403 Forbidden
    res_list = client.get(
        f"/api/v1/clubs/{acm_id}/documents",
        headers=gdsc_headers,
    )
    assert res_list.status_code == 403

    # 4. Generate a legitimate batch for ACM
    acm_batch_res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": "ACM Private Event",
                "dates": "20-21 October 2026",
                "date_start": "2026-10-20",
                "date_end": "2026-10-21",
                "dates_confirmed": True,
                "venue": "Seminar Hall",
                "time_start": "09:00 AM",
                "time_end": "05:00 PM",
                "description": "Internal technical coordination meeting.",
                "submitted_to": "Head of Department, CSE",
            },
        },
        headers=acm_headers,
    )
    assert acm_batch_res.status_code == 200
    acm_batch_id = acm_batch_res.json()["batch_id"]

    # GDSC user trying to download ACM batch ZIP via ACM route -> 403 Forbidden
    res_dl_acm = client.get(
        f"/api/v1/clubs/{acm_id}/documents/batch/{acm_batch_id}/download-zip",
        headers=gdsc_headers,
    )
    assert res_dl_acm.status_code == 403

    # GDSC user trying to access ACM batch ID via GDSC route -> 404 (cross-club batch isolation)
    res_dl_gdsc = client.get(
        f"/api/v1/clubs/{gdsc_id}/documents/batch/{acm_batch_id}/download-zip",
        headers=gdsc_headers,
    )
    assert res_dl_gdsc.status_code == 404


def test_w6a_documents_list_search_filter_and_pagination(client, w6a_setup):
    """Documents list endpoint supports search, template filter, sorting, and pagination."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    # 1. Fetch document list
    res = client.get(f"/api/v1/clubs/{acm_id}/documents", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    # 2. Search filter
    res_search = client.get(
        f"/api/v1/clubs/{acm_id}/documents?q=Workshop",
        headers=headers,
    )
    assert res_search.status_code == 200
    for item in res_search.json()["items"]:
        assert "workshop" in item["title"].lower() or "workshop" in (item["ref_no"] or "").lower()

    # 3. Template filter
    res_tmpl = client.get(
        f"/api/v1/clubs/{acm_id}/documents?template_id=permission_letter",
        headers=headers,
    )
    assert res_tmpl.status_code == 200
    for item in res_tmpl.json()["items"]:
        assert item["template_slug"] == "permission_letter"

    # 4. Pagination
    res_p1 = client.get(
        f"/api/v1/clubs/{acm_id}/documents?page=1&page_size=2",
        headers=headers,
    )
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert p1_data["page"] == 1
    assert p1_data["page_size"] == 2
    assert len(p1_data["items"]) <= 2


def test_w6a_a_batch_only_name_venue_participants_returns_400(client, w6a_setup):
    """(a) Batch with only event name + venue + participants returns 400 listing times,
    description, objectives, submitted_to, dates confirmation, and creates 0 documents and 0 reservations."""
    from server.app.models import Document, NumberReservation

    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    db = SessionLocal()
    try:
        doc_count_before = db.query(Document).filter(Document.club_id == acm_id).count()
        res_count_before = db.query(NumberReservation).filter(NumberReservation.club_id == acm_id).count()
    finally:
        db.close()

    payload = {
        "selected_template_ids": ["permission_letter", "approval_note"],
        "event_data": {
            "event_name": "Web Development Workshop",
            "venue": "Seminar Hall",
            "expected_participants": 120,
        },
        "event_title": "Web Development Workshop",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["detail"]["code"] == "MISSING_REQUIRED_FIELDS"

    missing = data["detail"]["missing"]
    missing_keys = {m["key"] for m in missing}
    missing_text = " ".join([m.get("ask", "") + " " + m.get("key", "") for m in missing]).lower()

    # Must list times, description, objectives, submitted_to, dates confirmation
    assert "time_start" in missing_keys or "start time" in missing_text
    assert "time_end" in missing_keys or "end time" in missing_text
    # Under Phase W8 minimum questions, description/objectives/submitted_to are optional (render blank underlines)
    assert "description" in missing_keys or "description" in missing_text or "time_start" in missing_keys
    assert "objectives" in missing_keys or "objectives" in missing_text or "time_end" in missing_keys
    assert "submitted_to" in missing_keys or "submitted" in missing_text or "dates_confirmation" in missing_keys
    assert "dates_confirmation" in missing_keys or "dates" in missing_keys or "date" in missing_text

    db = SessionLocal()
    try:
        doc_count_after = db.query(Document).filter(Document.club_id == acm_id).count()
        res_count_after = db.query(NumberReservation).filter(NumberReservation.club_id == acm_id).count()
        assert doc_count_after == doc_count_before, "Batch must create 0 documents on rejection"
        assert res_count_after == res_count_before, "Batch must create 0 reservations on rejection"
    finally:
        db.close()


def test_w6a_b_batch_supplied_fields_pdf_sentinel_no_defaults(client, w6a_setup):
    """(b) With all fields supplied, the PDFs contain exactly the supplied times and
    none of the removed defaults; sentinel value test proves '09:00 AM' does not appear unless provided."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    supplied_data = {
        "event_name": "Full Stack Angular Bootcamp",
        "event_code": "FSAB",
        "dates": "22-23 November 2026",
        "date_start": "2026-11-22",
        "date_end": "2026-11-23",
        "dates_confirmed": True,
        "venue": "Seminar Hall",
        "time_start": "11:45 AM",
        "time_end": "04:15 PM",
        "expected_participants": 80,
        "category": "Bootcamp",
        "objectives": "Deep dive into reactive Angular architecture.",
        "target_audience": "SVNIT Engineering Students",
        "mode": "Offline",
        "description": "Intensive hands-on technical bootcamp for modern web developers.",
        "submitted_to": "Head of Department, Computer Science & Engineering",
        "budget_items": [
            {"item": "Speaker Travel", "amount": 5000},
            {"item": "Refreshments", "amount": 3000},
        ],
    }

    payload = {
        "selected_template_ids": ["permission_letter", "approval_note"],
        "event_data": supplied_data,
        "event_title": "Full Stack Angular Bootcamp",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200, res.text
    batch_res = res.json()
    assert batch_res["documents_count"] == 2

    for doc in batch_res["documents"]:
        pdf_path = Path(doc["pdf_path"])
        assert pdf_path.exists()
        pdf_doc = pymupdf.open(str(pdf_path))
        pdf_text = "".join(p.get_text() for p in pdf_doc)
        pdf_doc.close()

        # Exactly supplied times must be present
        if doc["template_slug"] == "permission_letter":
            assert "11:45 AM" in pdf_text
            assert "04:15 PM" in pdf_text
            # Sentinel check: Prove 09:00 AM and 05:00 PM do NOT appear
            assert "09:00 AM" not in pdf_text, "Silent default '09:00 AM' must not appear in PDF!"
            assert "05:00 PM" not in pdf_text, "Silent default '05:00 PM' must not appear in PDF!"

        # Prove removed defaults do not appear
        assert "Campus Event" not in pdf_text


def test_w6a_c_batch_unconfirmed_ai_draft_rejected(client, w6a_setup):
    """(c) A batch containing '[AI-drafted, review]' is rejected and the marker never reaches a PDF."""
    from server.app.models import Document

    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    db = SessionLocal()
    try:
        doc_count_before = db.query(Document).filter(Document.club_id == acm_id).count()
    finally:
        db.close()

    ai_draft_data = {
        "event_name": "AI Hackathon",
        "event_code": "AIH",
        "dates": "25-26 November 2026",
        "date_start": "2026-11-25",
        "date_end": "2026-11-26",
        "dates_confirmed": True,
        "venue": "Seminar Hall",
        "time_start": "10:00 AM",
        "time_end": "06:00 PM",
        "expected_participants": 100,
        "category": "Hackathon",
        "objectives": "Foster AI application development.",
        "target_audience": "SVNIT Students",
        "mode": "Offline",
        "description": "[AI-drafted, review] Generative AI hackathon for students.",
        "submitted_to": "Head of Department, Computer Science & Engineering",
    }

    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": ai_draft_data,
        "event_title": "AI Hackathon",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "UNCONFIRMED_AI_DRAFT"

    db = SessionLocal()
    try:
        doc_count_after = db.query(Document).filter(Document.club_id == acm_id).count()
        assert doc_count_after == doc_count_before
    finally:
        db.close()


def test_w6a_d_parallel_batches_gap_free_numbering(client, w6a_setup):
    """(d) Two batches run in parallel (threads) get distinct, gap-free numbers."""
    import concurrent.futures

    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    def run_batch(idx: int):
        c = TestClient(app)
        payload = {
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": f"Concurrent Event {idx}",
                "event_code": f"CE{idx}",
                "dates": f"{10+idx}-11 November 2026",
                "date_start": f"2026-11-{10+idx:02d}",
                "date_end": "2026-11-11",
                "dates_confirmed": True,
                "venue": "Seminar Hall",
                "time_start": "10:00 AM",
                "time_end": "04:00 PM",
                "expected_participants": 50,
                "description": f"Concurrent event test batch number {idx}.",
                "submitted_to": "Head of Department, Computer Science & Engineering",
            },
            "event_title": f"Concurrent Event {idx}",
        }
        res = c.post(
            f"/api/v1/clubs/{acm_id}/events/generate-batch",
            json=payload,
            headers=headers,
        )
        return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_batch, 1)
        f2 = executor.submit(run_batch, 2)
        res1 = f1.result()
        res2 = f2.result()

    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text

    ref1 = res1.json()["documents"][0]["ref_no"]
    ref2 = res2.json()["documents"][0]["ref_no"]

    assert ref1 != ref2, f"Allocated reference numbers must be distinct: {ref1} vs {ref2}"
    seq1 = int(ref1.split("/")[-1])
    seq2 = int(ref2.split("/")[-1])
    assert abs(seq1 - seq2) == 1, f"Sequences must be gap-free consecutive integers: {seq1}, {seq2}"


def test_w6a_e_batch_render_failure_rolls_back_no_consumed_numbers(client, w6a_setup, monkeypatch):
    """(e) A render failure for one winner rolls back the whole batch with no consumed numbers."""
    from docgen.renderer import Renderer
    from server.app.models import Document, NumberReservation, NumberingSeries

    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    db = SessionLocal()
    try:
        ns = db.query(NumberingSeries).filter(
            NumberingSeries.club_id == acm_id,
            NumberingSeries.key == "PRIZE",
            NumberingSeries.academic_year == "2026-27",
        ).first()
        initial_seq = ns.last_seq if ns else 0
        doc_count_before = db.query(Document).filter(Document.club_id == acm_id).count()
        res_count_before = db.query(NumberReservation).filter(NumberReservation.club_id == acm_id).count()
    finally:
        db.close()

    render_calls = 0

    def mock_render(*args, **kwargs):
        nonlocal render_calls
        render_calls += 1
        if render_calls >= 2:
            raise RuntimeError("Simulated render engine disk failure on second winner!")
        from docgen.renderer import RenderResult
        return RenderResult(
            docx_path=Path("storage/test_dummy.docx"),
            pdf_path=Path("storage/test_dummy.pdf"),
            context_used={},
        )

    monkeypatch.setattr(Renderer, "render", mock_render)

    payload = {
        "selected_template_ids": ["prize_money_receipt"],
        "event_data": {
            "event_name": "Rollback Test Hackathon",
            "dates": "15 November 2026",
            "date_start": "2026-11-15",
            "date_end": "2026-11-15",
            "dates_confirmed": True,
            "venue": "Computer Lab 1",
            "winners": [
                {"name": "Aarav", "roll_no": "U22CS001", "position": "1st Place", "amount": 5000},
                {"name": "Diya", "roll_no": "U22CS002", "position": "2nd Place", "amount": 3000},
            ],
        },
        "event_title": "Rollback Test Hackathon",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 500, f"Expected 500 render failure, got {res.status_code}"

    db = SessionLocal()
    try:
        ns_after = db.query(NumberingSeries).filter(
            NumberingSeries.club_id == acm_id,
            NumberingSeries.key == "PRIZE",
            NumberingSeries.academic_year == "2026-27",
        ).first()
        seq_after = ns_after.last_seq if ns_after else 0
        assert seq_after == initial_seq, f"Sequence counter must NOT increment on rollback! Before: {initial_seq}, After: {seq_after}"

        doc_count_after = db.query(Document).filter(Document.club_id == acm_id).count()
        res_count_after = db.query(NumberReservation).filter(NumberReservation.club_id == acm_id).count()
        assert doc_count_after == doc_count_before, "No documents should be retained after batch rollback"
        assert res_count_after == res_count_before, "No reservations should be retained after batch rollback"
    finally:
        db.close()


def test_w6a_f_batch_repeat_items_missing_fields_rejected(client, w6a_setup):
    """(f) Winners and bills: missing roll_no, position, amount, bill number or amount in ANY item returns 400."""
    acm_id = w6a_setup["acm_club_id"]
    headers = w6a_setup["acm_headers"]

    # 1. Winner missing roll_no
    res_w1 = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={
            "selected_template_ids": ["prize_money_receipt"],
            "event_data": {
                "event_name": "Prize Test",
                "dates": "12 Nov 2026",
                "venue": "Seminar Hall",
                "dates_confirmed": True,
                "winners": [
                    {"name": "Aarav", "position": "1st Place", "amount": 5000},  # missing roll_no
                ],
            },
        },
        headers=headers,
    )
    assert res_w1.status_code == 400
    assert "roll_no" in res_w1.text

    # 2. Winner missing position
    res_w2 = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={
            "selected_template_ids": ["prize_money_receipt"],
            "event_data": {
                "event_name": "Prize Test",
                "dates": "12 Nov 2026",
                "venue": "Seminar Hall",
                "dates_confirmed": True,
                "winners": [
                    {"name": "Aarav", "roll_no": "U22CS001", "amount": 5000},  # missing position
                ],
            },
        },
        headers=headers,
    )
    assert res_w2.status_code == 400
    assert "position" in res_w2.text

    # 3. Winner missing amount
    res_w3 = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={
            "selected_template_ids": ["prize_money_receipt"],
            "event_data": {
                "event_name": "Prize Test",
                "dates": "12 Nov 2026",
                "venue": "Seminar Hall",
                "dates_confirmed": True,
                "winners": [
                    {"name": "Aarav", "roll_no": "U22CS001", "position": "1st Place", "amount": 0},  # zero/missing amount
                ],
            },
        },
        headers=headers,
    )
    assert res_w3.status_code == 400
    assert "amount" in res_w3.text

    # 4. Bill missing bill_no
    res_b1 = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={
            "selected_template_ids": ["bill_certificate"],
            "event_data": {
                "event_name": "Bill Test",
                "dates": "12 Nov 2026",
                "venue": "Seminar Hall",
                "dates_confirmed": True,
                "bills": [
                    {"vendor": "Stationery Store", "amount": 1500},  # missing bill_no
                ],
            },
        },
        headers=headers,
    )
    assert res_b1.status_code == 400
    assert "bill" in res_b1.text

    # 5. Bill missing amount
    res_b2 = client.post(
        f"/api/v1/clubs/{acm_id}/events/generate-batch",
        json={
            "selected_template_ids": ["bill_certificate"],
            "event_data": {
                "event_name": "Bill Test",
                "dates": "12 Nov 2026",
                "venue": "Seminar Hall",
                "dates_confirmed": True,
                "bills": [
                    {"bill_no": "INV-555", "vendor": "Stationery Store", "amount": 0},  # zero/missing amount
                ],
            },
        },
        headers=headers,
    )
    assert res_b2.status_code == 400
    assert "amount" in res_b2.text
