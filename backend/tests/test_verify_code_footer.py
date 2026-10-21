"""Tests for verification code in footer of every generated document and public verification."""

from __future__ import annotations

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Document, DocumentReview, User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def auth_setup(client: TestClient):
    clear_rate_limits()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    clubs = client.get("/api/v1/clubs/search?q=", headers=headers).json()
    acm = next(c for c in clubs if c["slug"] == "acm")
    return {"headers": headers, "club_id": acm["id"]}


def test_verify_code_per_version_and_docx_footer_xml(client: TestClient, auth_setup):
    """Generating a document creates a unique code per version and puts it (and the ref no) in the DOCX footer XML."""
    headers = auth_setup["headers"]
    club_id = auth_setup["club_id"]

    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Footer Code Test Event",
            "venue": "Seminar Hall",
            "participants": 50,
            "date_start": "2026-11-10",
            "date_end": "2026-11-10",
            "time_start": "10:00",
            "time_end": "12:00",
            "submitted_to": "Head of Department",
            "description": "Footer test.",
            "objectives": "Verify footer in XML.",
        },
        "ref_numbers_accepted": True,
        "event_title": "Footer Code Test Event",
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/home/generate", json=payload, headers=headers)
    assert gen_res.status_code == 200, gen_res.text
    doc_info = gen_res.json()["documents"][0]
    doc_id = doc_info["id"]

    # Retrieve document detail to check verification code
    detail_res = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}", headers=headers)
    assert detail_res.status_code == 200
    doc_detail = detail_res.json()
    code_v1 = doc_detail.get("verification_code")
    assert code_v1, "v1 must have a verification_code"
    ref_no = doc_detail.get("ref_no")

    # Download DOCX and check its footer XML
    docx_res = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}/download?format=docx", headers=headers)
    assert docx_res.status_code == 200
    docx_zip = zipfile.ZipFile(io.BytesIO(docx_res.content))
    footer_xmls = [
        docx_zip.read(name).decode("utf-8")
        for name in docx_zip.namelist()
        if "word/footer" in name
    ]
    assert footer_xmls, "DOCX must contain footer XML parts"
    combined_footer_xml = "".join(footer_xmls)
    assert code_v1 in combined_footer_xml, f"Verification code {code_v1} must be in DOCX footer XML"
    if ref_no:
        assert ref_no in combined_footer_xml, f"Reference number {ref_no} must be in DOCX footer XML"

    # Now revise the document to produce version 2
    revise_res = client.post(
        f"/api/v1/clubs/{club_id}/documents/{doc_id}/revise",
        json={"changes": {"venue": "Computer Center Hall 2"}},
        headers=headers,
    )
    assert revise_res.status_code == 200

    detail_res2 = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}", headers=headers)
    assert detail_res2.status_code == 200
    code_v2 = detail_res2.json().get("verification_code")
    assert code_v2, "v2 must have a verification code"
    assert code_v1 != code_v2, "Each version must have a unique verification code"


def test_unapproved_verify_and_approved_verify(client: TestClient, auth_setup):
    """GET with code of unapproved document -> 200, status 'generated, not yet approved'.
    After approval -> 200 with approver and time, same code."""
    headers = auth_setup["headers"]
    club_id = auth_setup["club_id"]

    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Approval Verify Test",
            "venue": "Seminar Hall",
            "participants": 30,
            "date_start": "2026-11-12",
            "date_end": "2026-11-12",
            "time_start": "14:00",
            "time_end": "16:00",
            "submitted_to": "Head of Department",
            "description": "Approval test.",
            "objectives": "Verify status before and after approval.",
        },
        "ref_numbers_accepted": True,
        "event_title": "Approval Verify Test",
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/home/generate", json=payload, headers=headers)
    assert gen_res.status_code == 200
    doc_id = gen_res.json()["documents"][0]["id"]

    detail = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}", headers=headers).json()
    code = detail["verification_code"]
    assert code

    # 1. Unapproved document verification
    unapproved_ver = client.get(f"/api/v1/verify/{code}")
    assert unapproved_ver.status_code == 200
    data = unapproved_ver.json()
    assert data["valid"] is True
    assert data["status"] == "generated, not yet approved"
    assert data["approved_by"] is None
    assert data["approved_at"] is None
    assert data["document_title"] == detail["title"]
    assert data["club_name"]
    assert data["version_no"] == 1
    assert data["date_generated"]

    # 2. Submit and approve
    base = f"/api/v1/clubs/{club_id}/documents/{doc_id}"
    assert client.post(f"{base}/submit", json={"comment": "Ready for approval"}, headers=headers).status_code == 200
    appr_res = client.post(f"{base}/approve", json={"comment": "Approved!"}, headers=headers)
    assert appr_res.status_code == 200
    # Approval flow reuses the version's code
    assert appr_res.json().get("verification_code") == code

    # 3. After approval verification (same code)
    approved_ver = client.get(f"/api/v1/verify/{code}")
    assert approved_ver.status_code == 200
    appr_data = approved_ver.json()
    assert appr_data["valid"] is True
    assert appr_data["status"] == "approved"
    assert appr_data["approved_by"]  # has approver name
    assert appr_data["approved_at"]  # has approver time


def test_old_approval_code_still_verifies(client: TestClient, auth_setup):
    """An old approval code (DocumentReview row) still verifies."""
    headers = auth_setup["headers"]
    club_id = auth_setup["club_id"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
        doc = db.query(Document).filter(Document.club_id == club_id).first()
        assert doc is not None

        old_code = "LEGACY01-TESTCODE"
        review = DocumentReview(
            club_id=club_id,
            document_id=doc.id,
            version_no=1,
            action="approved",
            user_id=user.id,
            comment="Legacy approval",
            verification_code=old_code,
            pdf_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )
        db.add(review)
        db.commit()

        # Query public verify endpoint with old code
        res = client.get(f"/api/v1/verify/{old_code}")
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["status"] == "approved"
        assert data["document_title"] == doc.title
        assert data["approved_by"] == user.name
    finally:
        # Clean up legacy test review
        db.query(DocumentReview).filter(DocumentReview.verification_code == "LEGACY01-TESTCODE").delete()
        db.commit()
        db.close()


def test_upload_pdf_match_and_no_match(client: TestClient, auth_setup):
    """Uploading the generated PDF -> matches; another PDF -> no match."""
    headers = auth_setup["headers"]
    club_id = auth_setup["club_id"]

    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "PDF Hash Test Event",
            "venue": "Seminar Hall",
            "participants": 25,
            "date_start": "2026-11-15",
            "date_end": "2026-11-15",
            "time_start": "09:00",
            "time_end": "11:00",
            "submitted_to": "Head of Department",
            "description": "Testing hash matches.",
            "objectives": "Compare sha256.",
        },
        "ref_numbers_accepted": True,
        "event_title": "PDF Hash Test Event",
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/home/generate", json=payload, headers=headers)
    assert gen_res.status_code == 200
    doc_id = gen_res.json()["documents"][0]["id"]

    detail = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}", headers=headers).json()
    code = detail["verification_code"]
    assert code

    pdf_res = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}/download?format=pdf", headers=headers)
    assert pdf_res.status_code == 200
    pdf_bytes = pdf_res.content

    # 1. Upload exact matching PDF
    match_res = client.post(
        f"/api/v1/verify/{code}",
        files={"file": ("document.pdf", pdf_bytes, "application/pdf")},
    )
    assert match_res.status_code == 200
    match_data = match_res.json()
    assert match_data["file_matches"] is True
    assert match_data["message"] == "matches"

    # 2. Upload altered/tampered PDF
    no_match_res = client.post(
        f"/api/v1/verify/{code}",
        files={"file": ("document.pdf", pdf_bytes + b"tampered_bytes", "application/pdf")},
    )
    assert no_match_res.status_code == 200
    no_match_data = no_match_res.json()
    assert no_match_data["file_matches"] is False
    assert no_match_data["message"] == "does not match the copy generated by ClubDocs"


def test_unknown_code_and_no_field_values_leaked(client: TestClient, auth_setup):
    """Unknown code -> 404; the response never contains field values."""
    # 1. Unknown code
    res_404 = client.get("/api/v1/verify/NONEXISTENT-CODE")
    assert res_404.status_code == 404
    assert res_404.json()["detail"] == (
        "No ClubDocs document has this verification code. Check the code printed in the footer of the document."
    )

    # 2. Field values never contained in response
    headers = auth_setup["headers"]
    club_id = auth_setup["club_id"]
    secret_description = "SUPER_SECRET_INTERNAL_BUDGET_NOTE_12345"
    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Leak Check Event",
            "venue": "Confidential Room 404",
            "participants": 10,
            "date_start": "2026-11-20",
            "date_end": "2026-11-20",
            "time_start": "10:00",
            "time_end": "11:00",
            "submitted_to": "Secret Panel",
            "description": secret_description,
            "objectives": "Check no leakage.",
        },
        "ref_numbers_accepted": True,
        "event_title": "Leak Check Event",
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/home/generate", json=payload, headers=headers)
    assert gen_res.status_code == 200
    doc_id = gen_res.json()["documents"][0]["id"]
    code = client.get(f"/api/v1/clubs/{club_id}/documents/{doc_id}", headers=headers).json()["verification_code"]

    verify_res = client.get(f"/api/v1/verify/{code}")
    assert verify_res.status_code == 200
    resp_text = verify_res.text
    resp_data = verify_res.json()

    assert secret_description not in resp_text
    assert "Confidential Room 404" not in resp_text
    assert "Secret Panel" not in resp_text
    forbidden_keys = {"record_snapshot", "editable_fields", "content", "overrides", "fields", "members"}
    for k in forbidden_keys:
        assert k not in resp_data, f"Forbidden key '{k}' must never be returned by public verify"
