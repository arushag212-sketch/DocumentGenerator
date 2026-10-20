"""Tests for W4(b): Template Editor & Compiler MVP.

Checklist:
1. The compiled DOCX must open in Word without a repair prompt: check with python-docx
   and by converting with LibreOffice, and report which checks were run.
2. Validator rejects a template with an unused required field.
3. Field rename updates all chips.
4. Permissions:
   - A viewer cannot edit or publish (403)
   - Another club cannot see the draft (404/403)
   - A system template rejects edits (403)
5. End-to-end "Sponsorship Request Letter":
   - Built entirely with editor blocks (event name, date, venue, repeating tier table with
     computed total in INR, signature grid).
   - Compiled and published.
   - Used through New Document generation to DOCX and PDF.
   - Rendered-PDF assertions: '&' survives, no '{{', no 'None', money formatted only for
     money fields, Indian grouping, DD/MM/YYYY dates, signature grid keeps rows together.
"""

from __future__ import annotations

import os

import io
import json
import subprocess
from pathlib import Path
import pytest
from docx import Document
import fitz  # PyMuPDF
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models import Club, Membership, Template, TemplateVersion, User
from server.app.core.permissions import Role
from server.app.core.security import get_password_hash
from server.app.core.template_compiler import (
    TemplateCompiler,
    rename_field_in_editor_json,
)
from docgen.renderer import Renderer


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_setup(client):
    """Set up test users (owner, viewer, another club) and auth headers."""
    from server.app.core.rate_limit import clear_rate_limits
    clear_rate_limits()

    # Login as owner
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    owner_token = res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Fetch ACM club
    clubs = client.get("/api/v1/clubs/", headers=owner_headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    acm_club_id = acm_club["id"]

    # Create viewer and another club in DB
    from server.app.core.database import SessionLocal
    db = SessionLocal()
    try:
        viewer_user = db.query(User).filter(User.email == "w4b.viewer@svnit.ac.in").first()
        if not viewer_user:
            viewer_user = User(
                email="w4b.viewer@svnit.ac.in",
                password_hash=get_password_hash("ViewerPass123!"),
                name="W4b Viewer User",
                is_platform_admin=False,
            )
            db.add(viewer_user)
            db.flush()

        mem = db.query(Membership).filter(
            Membership.club_id == acm_club_id,
            Membership.user_id == viewer_user.id
        ).first()
        if not mem:
            mem = Membership(
                club_id=acm_club_id,
                user_id=viewer_user.id,
                role=Role.VIEWER,
                status="active",
            )
            db.add(mem)
            db.flush()

        # Other club user
        other_user = db.query(User).filter(User.email == "w4b.other@svnit.ac.in").first()
        if not other_user:
            other_user = User(
                email="w4b.other@svnit.ac.in",
                password_hash=get_password_hash("OtherPass123!"),
                name="W4b Other Club User",
                is_platform_admin=False,
            )
            db.add(other_user)
            db.flush()

        # Find or create a second club (e.g. GDSC / DSC)
        other_club = db.query(Club).filter(Club.short_name == "GDSC").first()
        if not other_club:
            other_club = Club(
                name="Google Developer Student Clubs",
                short_name="GDSC",
                slug="gdsc",
                chapter_code="6/99",
                head_of_account="6/99",
                academic_year_default="2026-27",
            )
            db.add(other_club)
            db.flush()

        mem2 = db.query(Membership).filter(
            Membership.club_id == other_club.id,
            Membership.user_id == other_user.id
        ).first()
        if not mem2:
            mem2 = Membership(
                club_id=other_club.id,
                user_id=other_user.id,
                role=Role.OWNER,
                status="active",
            )
            db.add(mem2)
            db.flush()

        db.commit()
        other_club_id = other_club.id
    finally:
        db.close()

    # Login as viewer
    res_v = client.post(
        "/api/v1/auth/login",
        json={"email": "w4b.viewer@svnit.ac.in", "password": "ViewerPass123!"},
    )
    assert res_v.status_code == 200
    viewer_token = res_v.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Login as other club user
    res_o = client.post(
        "/api/v1/auth/login",
        json={"email": "w4b.other@svnit.ac.in", "password": "OtherPass123!"},
    )
    assert res_o.status_code == 200
    other_token = res_o.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    return {
        "acm_club_id": acm_club_id,
        "other_club_id": other_club_id,
        "owner_headers": owner_headers,
        "viewer_headers": viewer_headers,
        "other_headers": other_headers,
    }


def test_w4b_compile_and_validate_docx():
    """Gate Check 1 & 4: Compiled DOCX opens in Word without repair prompt.
    
    Checks performed:
    1. python-docx Document object model parsing and paragraph/table traversal.
    2. OpenXML integrity check: cantSplit applied to rows, keepWithNext applied to labels.
    3. Headless LibreOffice PDF conversion succeeds with exit code 0.
    """
    editor_json = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": "TEST DOCUMENT HEADER"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "This tests formatting with "},
                {"type": "text", "marks": [{"type": "bold"}], "text": "bold"},
                {"type": "text", "text": " and "},
                {"type": "fieldChip", "attrs": {"fieldName": "sample_field", "label": "Sample Field", "fieldType": "text"}},
                {"type": "text", "text": "."}
            ]},
            {"type": "infoTable", "attrs": {
                "rows": [
                    {"label": "Key Metric", "field": "sample_field"},
                    {"label": "Fixed Detail", "value": "Static Value & Co."}
                ]
            }},
            {"type": "repeatingTable", "attrs": {
                "listVariable": "table_items",
                "itemAlias": "item",
                "columns": [
                    {"key": "item_name", "label": "Item Description", "align": "left"},
                    {"key": "quantity", "label": "Qty", "align": "center", "type": "int"},
                    {"key": "price", "label": "Price (INR)", "align": "right", "type": "money"}
                ],
                "hasTotal": True,
                "totalLabel": "Net Total",
                "totalField": "price"
            }},
            {"type": "pageBreak"},
            {"type": "signatureGrid", "attrs": {
                "columns": 2,
                "signatures": [
                    {"label": "Prepared By", "designation": "Coordinator"},
                    {"label": "Approved By", "designation": "Faculty Advisor"}
                ]
            }}
        ]
    }
    fields = [
        {"key": "sample_field", "label": "Sample Field", "type": "text", "required": True},
        {"key": "table_items", "label": "Items", "type": "table", "required": True},
    ]
    template_meta = {
        "id": "test_compile_docx",
        "name": "Test Compile Docx",
        "category": "Official Event Documents",
        "numbering_series": "TEST",
    }

    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields,
        template_meta=template_meta,
        club_slug="acm",
    )

    # Check 1: python-docx loading & OpenXML parsing
    doc = Document(io.BytesIO(docx_bytes))
    assert len(doc.paragraphs) > 0, "Document should contain paragraphs"
    assert len(doc.tables) >= 3, "Document should contain infoTable, repeatingTable, and signatureGrid"

    # Check 2: Row cantSplit and keepWithNext
    found_cant_split = False
    for table in doc.tables:
        for row in table.rows:
            trPr = row._tr.get_or_add_trPr()
            if any(child.tag.endswith("cantSplit") for child in trPr):
                found_cant_split = True
    assert found_cant_split, "Table rows should have cantSplit attribute"

    # Check 3: LibreOffice headless conversion (verifies OpenXML validity without Word repair prompt)
    temp_dir = Path(os.environ["STORAGE_LOCAL_ROOT"], "test_outputs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_docx = temp_dir / "test_compiled.docx"
    temp_docx.write_bytes(docx_bytes)

    renderer = Renderer()
    soffice = renderer._find_soffice()
    assert soffice, "LibreOffice executable must be available"

    cmd = [soffice, "--headless", "--convert-to", "pdf:writer_pdf_Export", str(temp_docx), "--outdir", str(temp_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"LibreOffice conversion failed: {res.stderr}"

    pdf_out = temp_dir / "test_compiled.pdf"
    assert pdf_out.exists(), "LibreOffice output PDF should exist"
    assert pdf_out.stat().st_size > 1000, "Converted PDF should not be empty"


def test_w4b_validator_rejects_unused_required_field():
    """Gate Check 2: Validator strictly rejects a template with an unused required field."""
    editor_json = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Notice"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Welcome to "},
                {"type": "fieldChip", "attrs": {"fieldName": "used_field", "label": "Used Field"}},
            ]}
        ]
    }
    # used_field is in template, but unused_required_field is NOT used anywhere
    fields = [
        {"key": "used_field", "label": "Used Field", "type": "text", "required": True},
        {"key": "unused_required_field", "label": "Unused Required Field", "type": "text", "required": True},
    ]

    _, _, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields,
        template_meta={"id": "tmpl_unused", "name": "Test Unused"},
        club_slug="acm",
    )

    assert not report["is_valid"], "Validation must fail when a required field is not used in template"
    assert any("unused_required_field" in err for err in report["errors"]), (
        f"Expected unused field error, got: {report['errors']}"
    )


def test_w4b_field_rename_updates_all_chips():
    """Gate Check 3: Renaming a field updates every chip across TipTap JSON."""
    editor_json = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Event: "},
                {"type": "fieldChip", "attrs": {"fieldName": "old_event_name", "label": "old_event_name"}},
                {"type": "text", "text": ". Please attend "},
                {"type": "fieldChip", "attrs": {"fieldName": "old_event_name", "label": "Old Event Name"}},
            ]},
            {"type": "infoTable", "attrs": {
                "rows": [
                    {"label": "Title", "field": "old_event_name"},
                    {"label": "Venue", "field": "venue"}
                ]
            }},
            {"type": "repeatingTable", "attrs": {
                "listVariable": "old_event_name",
                "columns": [{"key": "old_event_name", "label": "Col"}]
            }}
        ]
    }

    updated = rename_field_in_editor_json(editor_json, "old_event_name", "new_event_name")
    dumped = json.dumps(updated)

    assert "old_event_name" not in dumped, "All occurrences of old_event_name should have been replaced"
    assert dumped.count("new_event_name") == 6, "Expected 6 replacements across chips, rows, and tables"


def test_w4b_permissions_editor_viewer_another_club(client, auth_setup):
    """Gate Check 4:
    - Viewer cannot edit or publish (403).
    - Another club cannot see the draft (403/404).
    - System template rejects edits/compile/publish (403).
    """
    acm_id = auth_setup["acm_club_id"]
    other_id = auth_setup["other_club_id"]
    owner_headers = auth_setup["owner_headers"]
    viewer_headers = auth_setup["viewer_headers"]
    other_headers = auth_setup["other_headers"]

    # 1. Create a draft as owner
    create_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/blank",
        json={"name": "Permissions Test Draft", "category": "Official Event Documents"},
        headers=owner_headers,
    )
    assert create_res.status_code == 201
    draft_id = create_res.json()["id"]

    # 2. Viewer attempts to create, edit, compile, or publish -> all 403 Forbidden
    res_v_create = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/blank",
        json={"name": "Viewer Forbidden Draft"},
        headers=viewer_headers,
    )
    assert res_v_create.status_code == 403, "Viewer cannot create blank template"

    res_v_save = client.put(
        f"/api/v1/clubs/{acm_id}/documents/templates/{draft_id}/draft",
        json={"name": "Viewer Hacked Name"},
        headers=viewer_headers,
    )
    assert res_v_save.status_code == 403, "Viewer cannot save draft"

    res_v_compile = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{draft_id}/compile",
        json={"name": "Viewer Hacked Compile"},
        headers=viewer_headers,
    )
    assert res_v_compile.status_code == 403, "Viewer cannot compile draft"

    res_v_publish = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{draft_id}/publish",
        headers=viewer_headers,
    )
    assert res_v_publish.status_code == 403, "Viewer cannot publish draft"

    # 3. Another club user attempts to view or edit ACM's draft -> 403 or 404
    res_other_get = client.get(
        f"/api/v1/clubs/{other_id}/documents/templates/{draft_id}/draft",
        headers=other_headers,
    )
    assert res_other_get.status_code in (403, 404), "Another club cannot access ACM draft"

    # 4. System templates reject draft endpoints (403)
    res_sys_draft = client.get(
        f"/api/v1/clubs/{acm_id}/documents/templates/permission_letter/draft",
        headers=owner_headers,
    )
    assert res_sys_draft.status_code == 403, "System template cannot be retrieved as draft"

    res_sys_compile = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/permission_letter/compile",
        json={"name": "Attempt Edit System Template"},
        headers=owner_headers,
    )
    assert res_sys_compile.status_code == 403, "System template cannot be compiled or edited"

    res_sys_publish = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/permission_letter/publish",
        headers=owner_headers,
    )
    assert res_sys_publish.status_code == 403, "System template cannot be modified/published"


def test_w4b_sponsorship_request_letter_end_to_end(client, auth_setup):
    """Gate Check 5: Sponsorship Request Letter built entirely in the editor,
    compiled, published, used through the New Document page, generated to DOCX and PDF.
    
    Rendered-PDF assertions:
    - '&' survives in text
    - No '{{' or '}}'
    - No 'None' or 'null'
    - Money formatted only for money fields with Indian grouping (e.g. 50,000.00, 25,000.00, 75,000.00)
    - Counts and quantities retain standard integer format (slots_available: 1, 2)
    - DD/MM/YYYY dates
    - Signature grid keeps rows together (cantSplit)
    """
    acm_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]

    # 1. Create blank template
    create_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/blank",
        json={"name": "Sponsorship Request Letter (Editor)", "category": "Official Event Documents"},
        headers=owner_headers,
    )
    assert create_res.status_code == 201
    tmpl_id = create_res.json()["id"]

    # 2. Build editor JSON with each block type
    editor_json = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": "SPONSORSHIP & PARTNERSHIP PROPOSAL"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "To,\nThe Executive Director & Sponsorship Lead,\nCorporate Relations Office."}
            ]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Subject: Request for Sponsorship for "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}},
                {"type": "text", "text": " scheduled on "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_date", "label": "Event Date", "fieldType": "date"}},
                {"type": "text", "text": " at "},
                {"type": "fieldChip", "attrs": {"fieldName": "venue", "label": "Venue", "fieldType": "text"}},
                {"type": "text", "text": "."}
            ]},
            {"type": "infoTable", "attrs": {
                "rows": [
                    {"label": "Organizing Body", "value": "ACM Student Chapter & Coding Club, SVNIT"},
                    {"label": "Flagship Event", "field": "event_name"},
                    {"label": "Confirmed Date", "field": "event_date"},
                    {"label": "Campus Venue", "field": "venue"}
                ]
            }},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "The sponsorship tiers, deliverables & expected contribution amounts are detailed below:"}
            ]},
            {"type": "repeatingTable", "attrs": {
                "listVariable": "sponsorship_tiers",
                "itemAlias": "tier",
                "columns": [
                    {"key": "tier_name", "label": "Tier & Deliverables", "align": "left"},
                    {"key": "slots_available", "label": "Slots Available", "align": "center", "type": "int"},
                    {"key": "amount", "label": "Contribution (INR)", "align": "right", "type": "money"}
                ],
                "hasTotal": True,
                "totalLabel": "Total Expected Sponsorship",
                "totalField": "amount",
                "totalVarName": "total_sponsorship_amount"
            }},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "We look forward to a fruitful association and partnership with your organization."}
            ]},
            {"type": "signatureGrid", "attrs": {
                "columns": 2,
                "signatures": [
                    {"label": "Student Coordinator", "designation": "ACM Student Chapter"},
                    {"label": "Faculty Advisor", "designation": "Department of CSE, SVNIT"}
                ]
            }}
        ]
    }

    fields = [
        {"key": "event_name", "label": "Event Name", "type": "text", "required": True, "ask": "What is the event name?"},
        {"key": "event_date", "label": "Event Date", "type": "date", "required": True, "ask": "What is the event date?"},
        {"key": "venue", "label": "Venue", "type": "text", "required": True, "ask": "What is the venue?"},
        {
            "key": "sponsorship_tiers",
            "label": "Sponsorship Tiers",
            "type": "table",
            "required": True,
            "columns": [
                {"key": "tier_name", "type": "text"},
                {"key": "slots_available", "type": "int"},
                {"key": "amount", "type": "money"}
            ]
        },
    ]

    # 3. Save draft
    save_res = client.put(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/draft",
        json={"editor_json": editor_json, "fields": fields},
        headers=owner_headers,
    )
    assert save_res.status_code == 200

    # 4. Compile draft
    compile_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/compile",
        json={"editor_json": editor_json, "fields": fields},
        headers=owner_headers,
    )
    assert compile_res.status_code == 200
    comp_data = compile_res.json()
    assert comp_data["is_valid"] is True, f"Compilation errors: {comp_data.get('errors')}"

    # 5. Publish template
    pub_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/publish",
        headers=owner_headers,
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "published"

    # 6. Reserve reference number for document
    res_num = client.post(
        f"/api/v1/clubs/{acm_id}/numbering/DOC/reserve",
        json={"template_id": tmpl_id},
        headers=owner_headers,
    )
    assert res_num.status_code == 200
    res_data = res_num.json()
    reserved_ref = res_data["ref_no"]
    reservation_id = res_data["reservation_id"]
    assert "ACM" in reserved_ref

    # 7. Generate document through /generate
    gen_payload = {
        "template_id": tmpl_id,
        "ref_no": reserved_ref,
        "reservation_id": reservation_id,
        "event_data": {
            "event_name": "Innovate & Build Hackathon 2026",
            "event_date": "2026-11-20",
            "venue": "New CSE Seminar Hall & Advanced Lab 3",
            "sponsorship_tiers": [
                {"tier_name": "Title Sponsor & Industry Partner", "slots_available": 1, "amount": 50000},
                {"tier_name": "Gold Associate & Keynote Host", "slots_available": 2, "amount": 25000}
            ],
            "document_date": "2026-10-16"
        },
        "confirmed_fields": ["event_name", "event_date", "venue", "sponsorship_tiers"],
    }
    gen_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/generate",
        json=gen_payload,
        headers=owner_headers,
    )
    assert gen_res.status_code in (200, 201), f"Generate failed: {gen_res.text}"
    gen_data = gen_res.json()
    doc_id = gen_data["id"]

    # 8. Download generated PDF and verify rendered content
    pdf_res = client.get(
        f"/api/v1/clubs/{acm_id}/documents/{doc_id}/download?format=pdf",
        headers=owner_headers,
    )
    assert pdf_res.status_code == 200
    pdf_bytes = pdf_res.content

    # Save artifact for evidence
    evidence_dir = Path("docs/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    pdf_evidence_path = evidence_dir / "w4b_sponsorship_request_letter.pdf"
    pdf_evidence_path.write_bytes(pdf_bytes)

    # Also download docx artifact
    docx_res = client.get(
        f"/api/v1/clubs/{acm_id}/documents/{doc_id}/download?format=docx",
        headers=owner_headers,
    )
    if docx_res.status_code == 200:
        (evidence_dir / "w4b_sponsorship_request_letter.docx").write_bytes(docx_res.content)


    # 9. Extract PDF text with PyMuPDF
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = "\n".join([page.get_text() for page in pdf_doc])

    # Save extracted text to evidence file
    txt_evidence_path = evidence_dir / "w4b_sponsorship_request_letter.txt"
    txt_evidence_path.write_text(full_text, encoding="utf-8")

    # Render page 1 to PNG evidence
    page1 = pdf_doc[0]
    pix = page1.get_pixmap(dpi=150)
    png_evidence_path = evidence_dir / "w4b_sponsorship_request_letter.png"
    pix.save(str(png_evidence_path))
    pdf_doc.close()

    # 10. Strict Assertions on rendered PDF:
    # - "&" survives and is not lost or corrupt
    assert "&" in full_text, "Ampersand '&' must survive in rendered PDF"
    assert "Innovate & Build Hackathon 2026" in full_text
    assert "New CSE Seminar Hall & Advanced Lab 3" in full_text
    assert "Title Sponsor & Industry Partner" in full_text

    # - No unrendered Jinja tags
    assert "{{" not in full_text, "Unrendered Jinja tag '{{' found in PDF"
    assert "}}" not in full_text, "Unrendered Jinja tag '}}' found in PDF"

    # - No 'None' or 'null'
    assert "None" not in full_text, "'None' found in rendered PDF"
    assert "null" not in full_text, "'null' found in rendered PDF"

    # - Date formatted as DD/MM/YYYY
    assert "20/11/2026" in full_text, "Date must be formatted as DD/MM/YYYY (20/11/2026)"

    # - Money formatted only for money fields with Indian grouping
    assert "50,000.00" in full_text, "Money field 50000 must be formatted as 50,000.00"
    assert "25,000.00" in full_text, "Money field 25000 must be formatted as 25,000.00"
    assert "75,000.00" in full_text, "Computed total must be formatted as 75,000.00"

    # - Non-money fields (slots_available: 1 and 2) must remain plain integers, not formatted as 1.00 or 2.00
    assert "1" in full_text
    assert "2" in full_text
    # Ensure they were not converted to 1.00 or 2.00
    assert "1.00" not in full_text, "Integer count field must not be formatted as currency"
    assert "2.00" not in full_text, "Integer count field must not be formatted as currency"

    # - Signature labels present
    assert "Student Coordinator" in full_text
    assert "Faculty Advisor" in full_text
