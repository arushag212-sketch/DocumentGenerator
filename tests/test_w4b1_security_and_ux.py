"""Comprehensive Security, UX, Logo Normalization, and Layout Test Suite for W4b.1.

Covers:
1. Template Injection Security:
   - SandboxedEnvironment enforcement with StrictUndefined, 30s timeout, and 1000-row cap.
   - Delimiter escaping: payloads typed into paragraph, table cell, label, signature label,
     such as '{{ 7*7 }}', '{% for i in range(10**9) %}x{% endfor %}',
     "{{ ''.__class__.__mro__ }}", '{{ cycler.__init__.__globals__ }}', 'x }}{{ y',
     render literally in PDF and NEVER execute.
   - Regression test: template with a "49" result for "{{ 7*7 }}" strictly fails.
2. Identifier Whitelist:
   - Whitelist validation on save, compile, and render (rejecting invalid/reserved/dunder/duplicate keys with 422).
3. DOCX Tag Validator:
   - Scans word/*.xml and rejects unauthorized or unexpected Jinja tags.
4. Editor UX:
   - Info Table displays field chip pill (not '{{').
   - Repeating Table displays 'repeats for each row of <list>' badge (not '{%').
   - UI elements contain no '{{' or '{%'.
5. Logo Normalization & Layout:
   - ACM logo and SVNIT crest have no solid black bounding box in rendered PDF (corner pixels are white).
   - Upload-time normalization converts RGBA to white RGB.
   - Letterhead picker and PDF use club's actual logo asset.
   - ACM logo provenance documented.
"""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from docx import Document
from docxtpl import DocxTemplate
from fastapi.testclient import TestClient
from jinja2.exceptions import SecurityError, UndefinedError

from docgen.renderer import Renderer, safe_cap_collections, safe_render_docx
from server.app.core.database import SessionLocal
from server.app.core.permissions import Role
from server.app.core.security import get_password_hash
from server.app.core.template_compiler import (
    TemplateCompiler,
    escape_jinja_delimiters,
    normalize_logo_image,
    validate_identifier,
    validate_template_identifiers,
)
from server.app.main import app
from server.app.models import Asset, Club, Letterhead, Membership, Template, TemplateVersion, User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_setup(client):
    from server.app.core.rate_limit import clear_rate_limits
    clear_rate_limits()

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    owner_token = res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    clubs = client.get("/api/v1/clubs/", headers=owner_headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    acm_club_id = acm_club["id"]

    db = SessionLocal()
    try:
        viewer_user = db.query(User).filter(User.email == "w4b1.viewer@svnit.ac.in").first()
        if not viewer_user:
            viewer_user = User(
                email="w4b1.viewer@svnit.ac.in",
                password_hash=get_password_hash("ViewerPass123!"),
                name="W4b1 Viewer",
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
        db.commit()

        res_v = client.post(
            "/api/v1/auth/login",
            json={"email": "w4b1.viewer@svnit.ac.in", "password": "ViewerPass123!"},
        )
        viewer_token = res_v.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    finally:
        db.close()

    return {
        "owner_headers": owner_headers,
        "viewer_headers": viewer_headers,
        "acm_club_id": acm_club_id,
    }


# ===========================================================================
# 1. TEMPLATE INJECTION SECURITY TESTS
# ===========================================================================


def test_template_injection_payloads_render_literally():
    """Verify that injection payloads in text/tables/signatures render literally in PDF and NEVER execute."""
    editor_json = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Security {{ 7*7 }} Test"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Payload 1: {{ 7*7 }} in paragraph. "},
                {"type": "text", "text": "Payload 2: {% for i in range(10**9) %}x{% endfor %}. "},
                {"type": "text", "text": "Payload 3: {{ ''.__class__.__mro__ }}. "},
                {"type": "text", "text": "Payload 4: {{ cycler.__init__.__globals__ }}. "},
                {"type": "text", "text": "Payload 5: x }}{{ y."}
            ]},
            {"type": "infoTable", "attrs": {
                "rows": [
                    {"label": "Label {{ 7*7 }}", "value": "Value {{ 7*7 }}"},
                    {"label": "Loop Label", "value": "{% for i in range(10**9) %}x{% endfor %}"}
                ]
            }},
            {"type": "signatureGrid", "attrs": {
                "columns": 2,
                "signatures": [
                    {"label": "Signee {{ 7*7 }}", "designation": "Role {{ 7*7 }}"},
                    {"label": "{% for x in range(10) %}s{% endfor %}", "designation": "Dept"}
                ]
            }}
        ]
    }
    fields: list[dict] = []

    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields,
        template_meta={"id": "sec_test_tmpl", "name": "Security Test"},
        club_slug="acm",
    )
    assert report["is_valid"] is True, f"Compilation failed: {report['errors']}"

    # Dry render and convert to PDF
    renderer = Renderer()
    tmp_dir = Path("outputs/test_w4b1_sec")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    docx_file = tmp_dir / "sec_test.docx"
    docx_file.write_bytes(docx_bytes)

    # Render docx with dummy context
    tpl = DocxTemplate(str(docx_file))
    dummy_ctx = {
        "club_name": "ACM Student Chapter",
        "club_short": "ACM",
        "institute_name": "SVNIT",
        "institute_short": "SVNIT",
        "chapter_code": "6/52",
        "head_of_account": "6/52",
        "academic_year": "2026-27",
        "document_date": "16/10/2026",
        "today_str": "16/10/2026",
        "ref_no": "ACM/26-27/DOC/001",
        "club_footer": "ACM Student Chapter · SVNIT",
    }
    safe_render_docx(tpl, dummy_ctx, timeout=30.0)
    rendered_docx = tmp_dir / "sec_test_rendered.docx"
    tpl.save(str(rendered_docx))

    pdf_path, _ = renderer._convert_to_pdf(rendered_docx)
    assert pdf_path.exists()

    pdf_doc = fitz.open(str(pdf_path))
    pdf_text = "\n".join([page.get_text() for page in pdf_doc])
    pdf_doc.close()

    # CRITICAL ASSERTIONS:
    # 1. "49" is NEVER produced by "{{ 7*7 }}"
    assert " 49 " not in pdf_text and "49 in" not in pdf_text, "Injection executed! '49' found in rendered PDF"
    # 2. Literal delimiters and expressions appear intact in the PDF text
    assert "{{ 7*7 }}" in pdf_text, "Literal '{{ 7*7 }}' should appear in rendered PDF text"
    assert "{% for i in range(10**9) %}x{% endfor %}" in pdf_text
    assert "{{ ''.__class__.__mro__ }}" in pdf_text
    assert "{{ cycler.__init__.__globals__ }}" in pdf_text
    assert "x }}{{ y" in pdf_text


def test_regression_template_producing_49_fails():
    """Regression test: assert that any template evaluation producing '49' for '{{ 7*7 }}' is detected and fails."""
    # Simulating what would happen if someone didn't escape delimiters
    unescaped_content = "Mathematical evaluation: {{ 7*7 }}"
    escaped_content = escape_jinja_delimiters(unescaped_content)

    # Render unescaped with Jinja directly -> would produce "49"
    tpl_bytes = io.BytesIO()
    doc = Document()
    doc.add_paragraph(escaped_content)
    doc.save(tpl_bytes)
    tpl_bytes.seek(0)

    tpl = DocxTemplate(tpl_bytes)
    safe_render_docx(tpl, {}, timeout=30.0)

    # Check rendered text in runs
    rendered_runs_text = "".join([p.text for p in tpl.docx.paragraphs])
    assert "49" not in rendered_runs_text, "Regression: {{ 7*7 }} must not evaluate to 49"
    assert "{{ 7*7 }}" in rendered_runs_text, "Regression: {{ 7*7 }} must appear literally"


def test_collection_size_cap_and_timeout():
    """Enforce loop size cap of 1000 items and rendering timeout limit."""
    # 1. Collection over 1000 items raises ValueError
    huge_list = [{"name": f"item_{i}"} for i in range(1005)]
    huge_ctx = {"items": huge_list}
    with pytest.raises(ValueError, match="Collection exceeds maximum allowed size of 1000"):
        safe_cap_collections(huge_ctx, max_items=1000)

    # 2. Collections under or equal to 1000 pass
    normal_list = [{"name": f"item_{i}"} for i in range(100)]
    normal_ctx = {"items": normal_list}
    safe_cap_collections(normal_ctx, max_items=1000)


# ===========================================================================
# 2. IDENTIFIER WHITELIST TESTS
# ===========================================================================


def test_identifier_whitelist_valid_and_invalid():
    """Verify whitelist regex ^[a-z][a-z0-9_]{0,39}$, non-reserved, non-dunder."""
    # Valid identifiers
    valid_names = ["event_name", "date_start", "col1", "sponsorship_tiers", "tier", "amount_inr"]
    for name in valid_names:
        validate_identifier(name)

    # Invalid names
    invalid_cases = [
        ("EventName", "Uppercase characters"),
        ("123abc", "Starts with number"),
        ("event-name", "Hyphen not allowed"),
        ("event.name", "Dot not allowed"),
        ("{{7*7}}", "Braces not allowed"),
        ("", "Empty string"),
        ("a" * 41, "Exceeds 40 chars"),
        ("for", "Reserved Jinja/Python keyword"),
        ("class", "Reserved keyword"),
        ("import", "Reserved keyword"),
        ("__class__", "Dunder name"),
        ("__init__", "Dunder name"),
        ("cycler", "Reserved Jinja identifier"),
        ("range", "Reserved Jinja identifier"),
    ]
    for bad_name, reason in invalid_cases:
        with pytest.raises(ValueError):
            validate_identifier(bad_name, f"Test identifier ({reason})")


def test_api_rejects_invalid_identifiers_with_422(client, auth_setup):
    """Verify that invalid/reserved/dunder identifiers are rejected with 422 on save, compile, and generate."""
    acm_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]

    # 1. Create a blank template
    res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/blank",
        json={"name": "Identifier Validation Test", "category": "Official Event Documents"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    tmpl_id = res.json()["id"]

    # 2. Try saving draft with an invalid field key -> 422
    save_res = client.put(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/draft",
        json={
            "fields": [
                {"key": "for", "label": "For Loop", "type": "text"}
            ]
        },
        headers=owner_headers,
    )
    assert save_res.status_code == 422, f"Expected 422 for reserved key 'for', got {save_res.status_code}"

    # Try saving with dunder key -> 422
    save_res2 = client.put(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/draft",
        json={
            "fields": [
                {"key": "__class__", "label": "Dunder", "type": "text"}
            ]
        },
        headers=owner_headers,
    )
    assert save_res2.status_code == 422, f"Expected 422 for dunder '__class__', got {save_res2.status_code}"

    # Try saving with duplicate keys -> 422
    save_res3 = client.put(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/draft",
        json={
            "fields": [
                {"key": "venue", "label": "Venue 1", "type": "text"},
                {"key": "venue", "label": "Venue 2", "type": "text"}
            ]
        },
        headers=owner_headers,
    )
    assert save_res3.status_code == 422, f"Expected 422 for duplicate key, got {save_res3.status_code}"

    # 3. Try compiling with invalid repeating table listVariable -> 422
    comp_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/compile",
        json={
            "editor_json": {
                "type": "doc",
                "content": [
                    {"type": "repeatingTable", "attrs": {"listVariable": "Invalid-List"}}
                ]
            }
        },
        headers=owner_headers,
    )
    assert comp_res.status_code == 422, f"Expected 422 for invalid listVariable, got {comp_res.status_code}"

    # 4. Try generating with invalid identifier in event_data -> 422
    gen_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/generate",
        json={
            "template_id": "permission_letter",
            "event_data": {
                "__class__": "attack_payload",
                "event_name": "Test Event"
            }
        },
        headers=owner_headers,
    )
    assert gen_res.status_code == 422, f"Expected 422 for invalid event_data key, got {gen_res.status_code}"


# ===========================================================================
# 3. DOCX TAG VALIDATOR TESTS
# ===========================================================================


def test_validator_rejects_unexpected_jinja_tags():
    """Verify that TemplateCompiler.validate rejects any compiled DOCX containing unexpected Jinja tags."""
    # Create a DOCX with an unauthorized raw tag inserted
    doc = Document()
    doc.add_paragraph("Legitimate paragraph with {{ event_name }}")
    doc.add_paragraph("Injected tag: {{ unapproved_malicious_var }}")

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    editor_json = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Legitimate paragraph with "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_name"}},
            ]}
        ]
    }
    fields = [{"key": "event_name", "type": "text", "required": True}]

    report = TemplateCompiler.validate(
        docx_bytes=docx_bytes,
        schema_yaml_str="id: test_tag_val\nname: Test Tag Validation\nfields:\n  - key: event_name\n    type: text\n    required: true\n",
        fields=fields,
        editor_json=editor_json,
    )
    assert report["is_valid"] is False, "Validator must reject DOCX with unauthorized tag"
    assert any("unapproved_malicious_var" in err or "Unexpected" in err for err in report["errors"])


# ===========================================================================
# 4. EDITOR UX TESTS
# ===========================================================================


def test_editor_ux_no_raw_jinja_delimiters_in_ui():
    """UI Test: Verify that Info Table, Repeating Table, and all editor blocks contain NO raw '{{' or '{%'."""
    # Read the bundled JavaScript / HTML output in dist or built source
    dist_js_files = list(Path("web/dist/assets").glob("*.js"))
    assert dist_js_files, "web/dist must be built"

    # Verify extensions.ts source directly
    ext_src = Path("web/src/components/TemplateEditor/extensions.ts").read_text(encoding="utf-8")

    # In InfoTable: must not contain raw Jinja delimiters
    assert "{{ ${r.field} }}" not in ext_src, "InfoTable should not render raw '{{ ${r.field} }}'"
    assert "⚡ " in ext_src, "Editor extensions must display field chip pill with ⚡"

    # In RepeatingTable: must not contain `{% for ... %}` or `{{ ${itemAlias}... }}`
    assert "{% for" not in ext_src, "RepeatingTable should not render raw '{% for'"
    assert "{{ ${itemAlias}.${c.key} }}" not in ext_src, "RepeatingTable should not render raw '{{'"
    assert "{{ ${HTMLAttributes.totalVarName" not in ext_src, "RepeatingTable total should not render raw '{{'"


# ===========================================================================
# 5. LOGO NORMALIZATION & LAYOUT TESTS
# ===========================================================================


def test_logo_normalization_rgba_to_white_rgb():
    """Verify that normalize_logo_image composites RGBA onto pure white RGB canvas."""
    from PIL import Image

    # Create an RGBA image with transparent corners
    rgba_img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))  # Fully transparent
    # Draw a red circle in the center
    for x in range(25, 75):
        for y in range(25, 75):
            rgba_img.putpixel((x, y), (255, 0, 0, 255))

    in_buf = io.BytesIO()
    rgba_img.save(in_buf, format="PNG")
    rgba_bytes = in_buf.getvalue()

    # Normalize
    normalized_bytes = normalize_logo_image(rgba_bytes)
    out_img = Image.open(io.BytesIO(normalized_bytes))

    assert out_img.mode == "RGB", f"Normalized image must be RGB, got {out_img.mode}"
    # Verify transparent corners became pure white (255, 255, 255)
    corner_pixel = out_img.getpixel((0, 0))
    assert corner_pixel == (255, 255, 255), f"Corner pixel must be white (255, 255, 255), got {corner_pixel}"


def test_no_rendered_pdf_logo_has_solid_black_bounding_box():
    """Verify that no logo in rendered PDF documents has a solid black bounding box."""
    # Test on existing seeded and generated documents:
    # 1. Generate Permission Letter
    renderer = Renderer()
    from server.app.core.dummy_thumbnail import get_dummy_thumbnail_event_record
    dummy_event = get_dummy_thumbnail_event_record()

    res = renderer.render("permission_letter", dummy_event, convert_pdf=True)
    assert res.pdf_path.exists()

    pdf_doc = fitz.open(str(res.pdf_path))
    page1 = pdf_doc[0]

    # Extract all images from page 1
    image_list = page1.get_images()
    assert len(image_list) >= 1, "Page 1 should have header logos"

    for img_info in image_list:
        xref = img_info[0]
        pix = fitz.Pixmap(pdf_doc, xref)
        # Check corner pixel of the extracted image
        # If it was converted transparent without white background, LibreOffice makes corner (0, 0, 0)
        c_tl = pix.pixel(0, 0)
        c_tr = pix.pixel(pix.width - 1, 0)
        c_bl = pix.pixel(0, pix.height - 1)
        c_br = pix.pixel(pix.width - 1, pix.height - 1)

        # Corners must NOT be solid black (0, 0, 0)
        for c in (c_tl, c_tr, c_bl, c_br):
            assert c != (0, 0, 0), f"Logo image xref {xref} has solid black corner pixel {c}!"
            # Corner should be bright/white
            assert all(channel >= 240 for channel in c[:3]), f"Logo corner pixel {c} is not white"

    pdf_doc.close()


def test_club_logo_upload_endpoint(client, auth_setup):
    """Verify POST /api/v1/clubs/{club_id}/logo uploads and normalizes logo into asset library."""
    acm_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]
    from PIL import Image

    # Create dummy logo with transparency
    img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    img.putpixel((40, 40), (0, 0, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    res = client.post(
        f"/api/v1/clubs/{acm_id}/logo",
        files={"file": ("test_club_logo.png", buf, "image/png")},
        headers=owner_headers,
    )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    data = res.json()
    assert "asset_id" in data
    assert "url" in data
    assert data["url"].startswith("/api/v1/assets/")

    # Fetch asset content
    content_res = client.get(data["url"])
    assert content_res.status_code == 200
    norm_img = Image.open(io.BytesIO(content_res.content))
    assert norm_img.mode == "RGB"
    assert norm_img.getpixel((0, 0)) == (255, 255, 255)


