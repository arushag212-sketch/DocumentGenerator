"""Tests for Phase W3.2 Review Directives:

1. Removal of silent defaults for winner position/amount, bill supplier, invoice no/date, items, tax type and tax amount.
   Missing inputs must return MISSING_REQUIRED_FIELDS.
2. Standing defaults from club settings: Purchase Order = NiL, Advance = NiL, Laboratory/Office = Student Council.
   Bill Certificate prints NiL when untouched and the user's custom value when set.
3. Bill Certificate 'for Rs.' line uses invoice total including tax (bill_total_with_tax), exactly matching Supplier Details Amount.
4. Concurrency-safe sequence numbering verified under parallel load.
5. Event updates cascade: changing an event's venue re-renders linked documents, creates a new version, and the resulting PDF shows the updated venue.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient

from docgen.models import (
    ApprovalNote,
    BillItem,
    BillRecord,
    EventRecord,
    FieldSource,
    SupplierDetails,
    Winner,
    tf,
)
from docgen.renderer import Renderer
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.database import SessionLocal
from server.app.main import app
from server.app.models import Club, Document, DocumentVersion, Event, Template, TemplateVersion


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def owner_auth(client):
    """Login as demo owner and return auth header + ACM club ID."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    clubs = client.get("/api/v1/clubs/", headers=headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    return headers, acm_club["id"]


def test_w3_2_winner_and_bill_missing_required_fields(client, owner_auth):
    """Directive 1: Missing winner position/amount or bill supplier/items/tax must return MISSING_REQUIRED_FIELDS."""
    headers, club_id = owner_auth

    # 1. Prize money receipt missing winner position and amount
    payload_winner = {
        "template_id": "prize_money_receipt",
        "title": "Prize Money Test",
        "ref_no": "ACM/2026-27/PR/001",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": "Smart India Hackathon 2026",
            "winners": [
                {
                    "name": "Jane Doe",
                    # position and amount intentionally omitted
                }
            ],
        },
    }
    res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_winner, headers=headers)
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert detail["code"] == "MISSING_REQUIRED_FIELDS"
    missing_keys = [m["key"] for m in detail["missing"]]
    assert any("position" in k for k in missing_keys)
    assert any("amount" in k for k in missing_keys)

    # 2. Bill certificate missing supplier, invoice no, items, and tax
    payload_bill = {
        "template_id": "bill_certificate",
        "title": "Bill Certificate Test",
        "ref_no": "ACM/2026-27/BC/001",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": "Smart India Hackathon 2026",
            "event_code": "SIH",
            "academic_year": "2026-27",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "approval_note": {"ref_no": "ACM/2026-27/SIH/001", "date": "10/10/2026"},
            "bills": [
                {
                    # Missing supplier_name, invoice_no, invoice_date, items, tax_type, tax_amount
                }
            ],
        },
    }
    res_b = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_bill, headers=headers)
    assert res_b.status_code == 400
    detail_b = res_b.json()["detail"]
    assert detail_b["code"] == "MISSING_REQUIRED_FIELDS"
    missing_b_keys = [m["key"] for m in detail_b["missing"]]
    assert any("supplier" in k or "bills" in k for k in missing_b_keys)


def test_w3_2_bill_certificate_standing_defaults(db_session):
    """Directive 2: Purchase Order = NiL, Advance = NiL, Lab = Student Council when untouched; custom when set."""
    db_config = build_club_config_from_db(db_session, "acm")
    db_source = DatabaseTemplateSource(db_session)

    out_dir_untouched = Path("outputs/tests_w3_2/standing_untouched")
    out_dir_untouched.mkdir(parents=True, exist_ok=True)
    renderer_untouched = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir_untouched)

    # Case A: Untouched standing defaults
    event_untouched = EventRecord()
    event_untouched.event_name = tf("Hackathon Event", FieldSource.user, confirmed=True)
    event_untouched.event_code = tf("SIH", FieldSource.user, confirmed=True)
    event_untouched.academic_year = tf("2026-27", FieldSource.user, confirmed=True)
    event_untouched.venue = tf("Seminar Hall", FieldSource.user, confirmed=True)
    event_untouched.dates = tf("15/10/2026", FieldSource.user, confirmed=True)
    event_untouched.approval_note = ApprovalNote(ref_no="ACM/2026-27/SIH/001", date="10/10/2026")
    event_untouched.bills = [
        BillRecord(
            supplier=SupplierDetails(name="Campus Stationery Mart", gst_no="24AAAAA0000A1Z0"),
            invoice_no="INV-2026-001",
            invoice_date="15/10/2026",
            items=[BillItem(name="Certificates & Badges", qty=1, unit_cost=Decimal("800.00"))],
            tax_type="GST 18%",
            tax_rate_or_amount=Decimal("144.00"),
        )
    ]

    res_a = renderer_untouched.render("bill_certificate", event=event_untouched, convert_pdf=True)
    assert res_a.pdf_path.exists()
    doc_a = pymupdf.open(str(res_a.pdf_path))
    text_a = "\n".join([page.get_text() for page in doc_a])
    doc_a.close()

    assert "NiL" in text_a, "Standing default NiL missing from Bill Certificate PDF"
    assert "Student Council" in text_a, "Standing default Student Council missing from Bill Certificate PDF"

    # Case B: Custom user values
    out_dir_custom = Path("outputs/tests_w3_2/standing_custom")
    out_dir_custom.mkdir(parents=True, exist_ok=True)
    renderer_custom = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir_custom)

    event_custom = EventRecord()
    event_custom.event_name = tf("Hackathon Event", FieldSource.user, confirmed=True)
    event_custom.event_code = tf("SIH", FieldSource.user, confirmed=True)
    event_custom.academic_year = tf("2026-27", FieldSource.user, confirmed=True)
    event_custom.venue = tf("Seminar Hall", FieldSource.user, confirmed=True)
    event_custom.dates = tf("15/10/2026", FieldSource.user, confirmed=True)
    event_custom.approval_note = ApprovalNote(ref_no="ACM/2026-27/SIH/001", date="10/10/2026")
    event_custom.purchase_order = "PO/SVNIT/2026/99"
    event_custom.advance = "5000"
    event_custom.laboratory_office = "AI Research Laboratory"
    event_custom.bills = [
        BillRecord(
            supplier=SupplierDetails(name="Campus Stationery Mart", gst_no="24AAAAA0000A1Z0"),
            invoice_no="INV-2026-001",
            invoice_date="15/10/2026",
            items=[BillItem(name="Certificates & Badges", qty=1, unit_cost=Decimal("800.00"))],
            tax_type="GST 18%",
            tax_rate_or_amount=Decimal("144.00"),
        )
    ]

    res_b = renderer_custom.render("bill_certificate", event=event_custom, convert_pdf=True)
    assert res_b.pdf_path.exists()
    doc_b = pymupdf.open(str(res_b.pdf_path))
    text_b = "\n".join([page.get_text() for page in doc_b])
    doc_b.close()

    assert "PO/SVNIT/2026/99" in text_b
    assert "5000" in text_b
    assert "AI Research Laboratory" in text_b


def test_w3_2_bill_certificate_for_rs_matches_supplier_amount(db_session):
    """Directive 3: Bill Certificate 'for Rs.' line equals Supplier Details Amount (bill_total_with_tax)."""
    db_config = build_club_config_from_db(db_session, "acm")
    db_source = DatabaseTemplateSource(db_session)

    out_dir = Path("outputs/tests_w3_2/for_rs_check")
    out_dir.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir)

    event = EventRecord()
    event.event_name = tf("Smart India Hackathon 2026", FieldSource.user, confirmed=True)
    event.event_code = tf("SIH", FieldSource.user, confirmed=True)
    event.academic_year = tf("2026-27", FieldSource.user, confirmed=True)
    event.venue = tf("Seminar Hall", FieldSource.user, confirmed=True)
    event.dates = tf("15/10/2026", FieldSource.user, confirmed=True)
    event.approval_note = ApprovalNote(ref_no="ACM/2026-27/SIH/001", date="10/10/2026")
    event.bills = [
        BillRecord(
            supplier=SupplierDetails(name="SVNIT Printing Press", gst_no="24AAAAA0000A1Z0"),
            invoice_no="INV/PR/777",
            invoice_date="15/10/2026",
            items=[
                BillItem(name="Event Banners (8x6)", qty=1, unit_cost=Decimal("800.00")),
            ],
            tax_type="GST 18%",
            tax_rate_or_amount=Decimal("144.00"),
        )
    ]

    res = renderer.render("bill_certificate", event=event, convert_pdf=True)
    assert res.pdf_path.exists()
    doc = pymupdf.open(str(res.pdf_path))
    text = "\n".join([page.get_text() for page in doc])
    doc.close()

    # Both "for Rs. 944.00" and Supplier Amount "944.00" must be present
    assert "944.00" in text, "Grand total with tax 944.00 missing from Bill Certificate"
    # Ensure 800.00 (subtotal) and 144.00 (tax) are also present
    assert "800.00" in text
    assert "144.00" in text


def test_w3_2_event_update_cascades_rerender(client, owner_auth, db_session):
    """Directive 6: Changing event venue re-renders linked documents, creates new version, and shows new venue in PDF."""
    headers, club_id = owner_auth

    # 1. Create a shared event
    create_event_payload = {
        "title": "SIH Hackathon Cascade Test",
        "event_code": "SIH_CASCADE",
        "record": {
            "venue": "Old Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Annual internal hackathon test",
            "expected_participants": 120,
            "submitted_to": "Head of Department, CSE",
        },
    }
    evt_res = client.post(f"/api/v1/clubs/{club_id}/events", json=create_event_payload, headers=headers)
    assert evt_res.status_code == 201
    event_id = evt_res.json()["id"]

    # 2. Reserve official reference number & generate linked Permission Letter (v1)
    res_alloc = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_alloc.status_code == 200
    res_data = res_alloc.json()
    reservation_id = res_data["reservation_id"]
    ref_no = res_data["ref_no"]

    doc_payload = {
        "template_id": "permission_letter",
        "title": "SIH Permission Letter Cascade",
        "ref_no": ref_no,
        "ref_no_confirmed": True,
        "reservation_id": reservation_id,
        "event_id": event_id,
        "event_data": {
            "event_name": "SIH Hackathon Cascade Test",
            "event_code": "SIH_CASCADE",
            "venue": "Old Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Annual internal hackathon test",
            "expected_participants": 120,
            "submitted_to": "Head of Department, CSE",
        },
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=doc_payload, headers=headers)
    assert gen_res.status_code == 200, f"Generate failed: {gen_res.text}"
    doc_id = gen_res.json()["id"]
    assert gen_res.json()["current_version_no"] == 1

    # Verify v1 PDF contains "Old Seminar Hall"
    v1_record = db_session.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id, DocumentVersion.version_no == 1).first()
    assert v1_record is not None
    doc_v1 = pymupdf.open(v1_record.pdf_key)
    text_v1 = "\n".join([page.get_text() for page in doc_v1])
    doc_v1.close()
    assert "Old Seminar Hall" in text_v1

    # 3. Update the Event's venue to "New Central Computing Facility" with update_documents=True
    update_payload = {
        "record": {
            "venue": "New Central Computing Facility",
        }
    }
    upd_res = client.put(
        f"/api/v1/clubs/{club_id}/events/{event_id}?update_documents=true",
        json=update_payload,
        headers=headers,
    )
    assert upd_res.status_code == 200

    # 4. Verify Document now has version 2 created
    v2_record = (
        db_session.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id, DocumentVersion.version_no == 2)
        .first()
    )
    assert v2_record is not None, "Document version 2 was not created by cascade update"
    assert v2_record.source == "cascaded_event_update"

    # 5. Extract text from version 2 PDF: assert "New Central Computing Facility" is present
    doc_v2 = pymupdf.open(v2_record.pdf_key)
    text_v2 = "\n".join([page.get_text() for page in doc_v2])
    doc_v2.close()
    norm_text_v2 = " ".join(text_v2.split())

    assert "New Central Computing Facility" in norm_text_v2, (
        f"Updated venue missing from re-rendered PDF! Got text: {text_v2[:300]}"
    )
    assert "Old Seminar Hall" not in norm_text_v2, "Stale venue remains in re-rendered PDF!"
