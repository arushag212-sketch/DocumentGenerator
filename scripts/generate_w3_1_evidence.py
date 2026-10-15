"""Generate complete evidence for all six documents and UI states for W3.1 gate."""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.core.database import SessionLocal
from server.app.models import Club, User
from server.app.core.security import get_password_hash

EVIDENCE_DIR = Path("docs/screenshots/w3_1")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

def generate_all_six_evidence():
    client = TestClient(app)
    db = SessionLocal()
    try:
        club = db.query(Club).filter(Club.short_name == "ACM").first()
        assert club, "ACM club must exist"
        club_id = club.id

        owner = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
        if not owner:
            owner = User(
                email="demo.owner@svnit.ac.in",
                name="Demo Owner",
                password_hash=get_password_hash("DemoOwnerPass123!"),
            )
            db.add(owner)
            db.commit()
    finally:
        db.close()

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    event_title = "Smart India Hackathon 2026 Internal Hackathon"
    event_date = "15/10/2026"
    appr_ref_no = "ACM/2026-27/SIH/001"

    # 1. Permission Letter
    print("-> Generating 1/6: Permission Letter...")
    perm_payload = {
        "template_id": "permission_letter",
        "title": f"Permission Letter - {event_title}",
        "ref_no": "ACM/2026-27/ROOM/001",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": event_title,
            "venue": "Seminar Hall",
            "dates": event_date,
            "date_start": event_date,
            "date_end": event_date,
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Internal hackathon to shortlist top teams for the national Smart India Hackathon.",
            "objectives": "To evaluate problem statements, test prototype feasibility, and select institute teams.",
            "expected_participants": 120,
            "submitted_to": "Head of Department, Computer Science & Engineering",
        },
        "confirmed_fields": ["description", "objectives"],
    }
    perm_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=perm_payload, headers=headers)
    assert perm_res.status_code == 200, f"Perm Letter failed: {perm_res.text}"
    save_doc_evidence("01_permission_letter", perm_res.json(), client, headers)

    # 2. Approval Note
    print("-> Generating 2/6: Approval Note...")
    appr_payload = {
        "template_id": "approval_note",
        "title": event_title,
        "ref_no": appr_ref_no,
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": event_title,
            "event_code": "SIH",
            "category": "Hackathon",
            "target_audience": "UG/PG Engineering Students",
            "document_date": event_date,
            "dates": event_date,
            "venue": "Seminar Hall",
            "budget_items": [
                {"item": "Event Banners (8x6)", "amount": 800},
                {"item": "Stationery & Refreshments", "amount": 2500},
                {"item": "Cash Prizes for Winners", "amount": 5000},
            ],
            "description": "Proposal for conducting Smart India Hackathon 2026 Internal Hackathon with financial sanction.",
            "objectives": "To foster innovation, problem solving, and shortlisting institute finalists.",
            "expected_participants": 120,
        },
        "confirmed_fields": ["description", "objectives"],
    }
    appr_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=appr_payload, headers=headers)
    assert appr_res.status_code == 200, f"Approval Note failed: {appr_res.text}"
    save_doc_evidence("02_approval_note", appr_res.json(), client, headers)

    # 3. Prize Money Receipt
    print("-> Generating 3/6: Prize Money Receipt...")
    prize_payload = {
        "template_id": "prize_money_receipt",
        "title": f"Prize Money Receipt - {event_title}",
        "ref_no": "ACM/2026-27/PRIZE/001",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": event_title,
            "document_date": event_date,
            "dates": event_date,
            "venue": "Seminar Hall",
            "winner_name": "Arshad Khatib",
            "winner_roll_no": "U24AI112",
            "winner_course_semester": "B.Tech AI 3rd Semester",
            "winner_mobile": "9876543210",
            "winner_amount": 5000,
            "winner_position": "1st Prize",
            "winner_bank_name_as_per_bank": "Arshad Khatib",
            "winner_account_no": "39874102938",
            "winner_bank_name": "State Bank of India",
            "winner_bank_branch": "SVNIT Campus",
            "winner_ifsc": "SBIN0003320",
            "winner_pan": "ABCDE1234F",
        },
    }
    prize_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=prize_payload, headers=headers)
    assert prize_res.status_code == 200, f"Prize Receipt failed: {prize_res.text}"
    save_doc_evidence("03_prize_money_receipt", prize_res.json(), client, headers)

    # 4. Bill Summary
    print("-> Generating 4/6: Bill Summary...")
    summary_payload = {
        "template_id": "bill_summary",
        "title": f"Bill Summary - {event_title}",
        "ref_no": "ACM/2026-27/SUMMARY/001",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": event_title,
            "document_date": event_date,
            "winners": [
                {
                    "position": "1st",
                    "name": "Arshad Khatib",
                    "roll_no": "U24AI112",
                    "course_semester": "B.Tech AI",
                    "mobile": "9876543210",
                    "amount": 5000,
                    "bank": {
                        "name_as_per_bank": "Arshad Khatib",
                        "bank_name": "State Bank of India",
                        "branch": "SVNIT Campus",
                        "account_no": "39874102938",
                        "ifsc": "SBIN0003320",
                    },
                }
            ],
            "other_reimbursements": [
                {
                    "name": "Ansh Gupta",
                    "account_no": "10293847561",
                    "ifsc": "SBIN0003320",
                    "amount": 3300,
                }
            ],
        },
    }
    summary_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=summary_payload, headers=headers)
    assert summary_res.status_code == 200, f"Bill Summary failed: {summary_res.text}"
    save_doc_evidence("04_bill_summary", summary_res.json(), client, headers)

    # 5. Bill Certificate
    print("-> Generating 5/6: Bill Certificate...")
    cert_payload = {
        "template_id": "bill_certificate",
        "title": f"Bill Certificate - {event_title}",
        "ref_no": "INV-2026-1059",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": event_title,
            "document_date": event_date,
            "approval_note_no": appr_ref_no,
            "approval_note_date": event_date,
            "supplier_name": "SVNIT Printing & Stationery Works",
            "supplier_gst": "24AAAAA0000A1Z5",
            "invoice_no": "INV-2026-1059",
            "invoice_date": event_date,
            "bill_amount": 800,
            "bill_items": [
                {"name": "Stage Flex Banner (8x6)", "qty": 1, "unit_cost": 800}
            ],
            "tax_type": "GST",
            "tax_amount": 144,
        },
        "deferred_fields": [
            "certifier_name",
            "supplier_gst",
            "payment_party",
            "payment_account_no",
            "payment_holder",
            "payment_bank",
            "payment_branch",
            "payment_ifsc",
        ],
    }
    cert_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=cert_payload, headers=headers)
    assert cert_res.status_code == 200, f"Bill Certificate failed: {cert_res.text}"
    save_doc_evidence("05_bill_certificate", cert_res.json(), client, headers)

    # 6. Minutes of Meeting (MoM)
    print("-> Generating 6/6: Minutes of Meeting...")
    mom_payload = {
        "template_id": "mom",
        "title": f"MoM - SIH Planning Meeting",
        "ref_no": "ACM/26-27/MOM/001",
        "ref_no_confirmed": True,
        "event_data": {
            "meeting_title": "SIH 2026 Core Executive Committee Planning Meeting",
            "meeting_date": event_date,
            "meeting_start_time": "05:00 PM",
            "meeting_end_time": "06:30 PM",
            "venue": "Seminar Hall",
            "chaired_by": "Dr. Sankita Patel",
            "attendees": ["Dr. Sankita Patel", "Dr. Balu Parne", "Ansh Gupta", "Arshad Khatib"],
            "absentees": [],
            "agenda_items": [
                {
                    "topic": "SIH Internal Hackathon Logistics & Evaluation",
                    "discussion": "Reviewed laboratory bookings, power backups, and mentor invitations.",
                    "decision": "Finalized Seminar Hall for hackathon schedule.",
                }
            ],
            "action_items": [
                {
                    "task": "Issue formal room permission letter to HoD CSE",
                    "owner": "Ansh Gupta",
                    "deadline": "12/10/2026",
                }
            ],
            "prepared_by": "Ansh Gupta",
            "approved_by": "Dr. Sankita Patel",
        },
    }
    mom_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=mom_payload, headers=headers)
    assert mom_res.status_code == 200, f"MoM failed: {mom_res.text}"
    save_doc_evidence("06_mom", mom_res.json(), client, headers)

    print("\n[SUCCESS] ALL SIX DOCUMENTS GENERATED AND VERIFIED SUCCESSFULLY!")


def save_doc_evidence(slug: str, doc_data: dict, client: TestClient, headers: dict):
    pdf_res = client.get(doc_data["pdf_url"], headers=headers)
    assert pdf_res.status_code == 200

    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    full_text = ""
    for i, page in enumerate(pdf_doc):
        page_text = page.get_text()
        full_text += f"--- Page {i+1} ---\n{page_text}\n"
        pix = page.get_pixmap(dpi=150)
        png_path = EVIDENCE_DIR / f"{slug}_page_{i+1}.png"
        pix.save(str(png_path))

    txt_path = EVIDENCE_DIR / f"{slug}_text.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    page_count = len(pdf_doc)
    pdf_doc.close()
    print(f"  Saved {slug}: {page_count} page(s) rasterized, text written to {txt_path.name}")


if __name__ == "__main__":
    generate_all_six_evidence()
