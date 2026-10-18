"""Dummy synthetic data and rendering pipeline for template thumbnails.

Renders template thumbnails directly from the template's docx using purely synthetic,
clearly fake dummy values (no real names, redaction boxes, or content from external documents).
Converts via LibreOffice, rasterizes page 1 with PyMuPDF, and caches at
storage/thumbnails/{template_version_id}.png.
"""

from __future__ import annotations

import shutil
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw
import pymupdf
from sqlalchemy.orm import Session

from docgen.config import load_config
from docgen.models import (
    ActionItem,
    AgendaItem,
    ApprovalNote,
    BankDetails,
    BillItem,
    BillRecord,
    BudgetItem,
    EventRecord,
    FieldSource,
    MeetingBlock,
    OtherReimbursement,
    PaymentDetails,
    SupplierDetails,
    Winner,
    tf,
)
from docgen.renderer import Renderer
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.models import Template, TemplateVersion


def get_dummy_thumbnail_event_record() -> EventRecord:
    """Return an EventRecord populated with purely synthetic, obviously fake dummy data."""
    event = EventRecord()

    event.event_name = tf("Demo Technical Workshop 2026", FieldSource.user, confirmed=True)
    event.event_code = tf("DEMO", FieldSource.user, confirmed=True)
    event.category = tf("Workshop", FieldSource.user, confirmed=True)
    event.event_type = tf("Workshop", FieldSource.user, confirmed=True)

    event.description = tf(
        "Demonstrative technical workshop organized for institutional document preview.",
        FieldSource.user,
        confirmed=True,
    )
    event.objectives = tf(
        "To illustrate template layout, dynamic styling, and typography across official formats.",
        FieldSource.user,
        confirmed=True,
    )
    event.target_audience = tf("Registered Institute Students", FieldSource.user, confirmed=True)
    event.expected_participants = tf(100, FieldSource.user, confirmed=True)

    event.dates = tf("15/10/2026", FieldSource.user, confirmed=True)
    event.date_start = tf("15/10/2026", FieldSource.user, confirmed=True)
    event.date_end = tf("15/10/2026", FieldSource.user, confirmed=True)
    event.venue = tf("Central Seminar Hall 1", FieldSource.user, confirmed=True)
    event.mode = tf("Offline", FieldSource.user, confirmed=True)
    event.time_start = tf("09:00 AM", FieldSource.user, confirmed=True)
    event.time_end = tf("05:00 PM", FieldSource.user, confirmed=True)

    event.ref_no = tf("DEMO/2026-27/001", FieldSource.user, confirmed=True)
    event.room_ref_no = tf("DEMO/26-27/ROOM/001", FieldSource.computed, confirmed=False)
    event.document_date = tf("10/10/2026", FieldSource.user, confirmed=True)
    event.submitted_to = tf("Head of Department", FieldSource.config, confirmed=True)

    event.judges = tf(["Demo Guest Evaluator"], FieldSource.user, confirmed=True)

    event.budget_items = [
        BudgetItem(item="Event Banner & Signage", amount=Decimal("1200")),
        BudgetItem(item="Stationery & Handouts", amount=Decimal("800")),
    ]

    event.approval_note = ApprovalNote(
        no="DEMO/2026-27/001",
        date="10/10/2026",
    )

    event.winners = [
        Winner(
            position="1st",
            name="TEST WINNER ONE",
            roll_no="U24CS000",
            course_semester="B.Tech Computer Science 3rd Semester",
            mobile="0000000000",
            amount=Decimal("3000"),
            bank=BankDetails(
                name_as_per_bank="TEST WINNER ONE",
                bank_name="TEST STATE BANK",
                branch="TEST CAMPUS BRANCH",
                account_no="000000000000",
                ifsc="TEST0000001",
                pan="ABCDE0000F",
            ),
        ),
        Winner(
            position="2nd",
            name="TEST WINNER TWO",
            roll_no="U24CS000",
            course_semester="B.Tech Computer Science 3rd Semester",
            mobile="0000000000",
            amount=Decimal("2000"),
            bank=BankDetails(
                name_as_per_bank="TEST WINNER TWO",
                bank_name="TEST NATIONAL BANK",
                branch="TEST CITY BRANCH",
                account_no="000000000000",
                ifsc="TEST0000002",
                pan="FGHIJ0000K",
            ),
        ),
    ]

    event.bills = [
        BillRecord(
            supplier=SupplierDetails(name="TEST VENDOR PVT LTD", gst_no="24AAAAA0000A1Z0"),
            invoice_no="INV/TEST/001",
            invoice_date="15/10/2026",
            items=[
                BillItem(name="Event Banner & Signage", qty=1, unit_cost=Decimal("1200")),
            ],
            tax_type="GST 18%",
            tax_rate_or_amount=Decimal("216"),
            payment=PaymentDetails(
                party="TEST VENDOR PVT LTD",
                account_no="00000000000000",
                holder="TEST VENDOR PVT LTD",
                bank="TEST COMMERCIAL BANK",
                branch="TEST BRANCH",
                ifsc="TEST0000123",
            ),
        )
    ]

    event.other_reimbursements = [
        OtherReimbursement(
            name="TEST REIMBURSE PERSON",
            account_no="000000000000",
            ifsc="TEST0000123",
            amount=Decimal("400"),
        )
    ]

    event.meeting = MeetingBlock(
        title="Technical Workshop Core Planning Meeting",
        ref_no="DEMO/2026-27/MOM/001",
        date="08/10/2026",
        start_time="03:00 PM",
        end_time="04:30 PM",
        venue="Central Seminar Hall 1",
        mode="Offline",
        chaired_by="Demo Faculty Chairman",
        attendees=["Demo Faculty Chairman", "Demo Student Head", "Demo Student Secretary"],
        absentees=["None"],
        agenda_items=[
            AgendaItem(
                topic="Schedule & Venue Booking",
                discussion="Reviewed capacity and technical equipment in Central Seminar Hall 1.",
                decision="Approved reservation and schedule.",
            ),
            AgendaItem(
                topic="Budget Approval",
                discussion="Examined expenditure estimates for banners and stationery.",
                decision="Sanctioned budget of Rs. 2,000/-.",
            ),
        ],
        action_items=[
            ActionItem(task="Submit room reservation letter", owner="Demo Student Secretary", deadline="09/10/2026"),
            ActionItem(task="Order banners and materials", owner="Demo Student Head", deadline="11/10/2026"),
        ],
        prepared_by="Demo Student Head",
        approved_by="Demo Faculty Chairman",
    )

    return event


def get_neutral_placeholder(target_path: Optional[Path] = None) -> Path:
    """Generate or retrieve a neutral document placeholder image."""
    placeholder_dir = Path("storage/thumbnails")
    placeholder_dir.mkdir(parents=True, exist_ok=True)
    placeholder_file = placeholder_dir / "neutral_placeholder.png"

    if not placeholder_file.exists():
        img = Image.new("RGBA", (360, 480), color=(248, 250, 252, 255))
        draw = ImageDraw.Draw(img)
        # Outer document border
        draw.rectangle([(20, 20), (340, 460)], outline=(203, 213, 225, 255), width=2, fill=(255, 255, 255, 255))
        # Header block
        draw.rectangle([(60, 60), (300, 85)], fill=(226, 232, 240, 255))
        # Content lines
        draw.rectangle([(60, 110), (280, 122)], fill=(241, 245, 249, 255))
        draw.rectangle([(60, 135), (300, 147)], fill=(241, 245, 249, 255))
        draw.rectangle([(60, 160), (250, 172)], fill=(241, 245, 249, 255))
        draw.rectangle([(60, 185), (290, 197)], fill=(241, 245, 249, 255))
        # Table wireframe
        draw.rectangle([(60, 230), (300, 310)], outline=(226, 232, 240, 255), width=1, fill=(248, 250, 252, 255))
        draw.line([(60, 255), (300, 255)], fill=(226, 232, 240, 255), width=1)
        draw.line([(180, 230), (180, 310)], fill=(226, 232, 240, 255), width=1)
        # Signature lines
        draw.line([(60, 400), (150, 400)], fill=(203, 213, 225, 255), width=2)
        draw.line([(210, 400), (300, 400)], fill=(203, 213, 225, 255), width=2)
        img.save(str(placeholder_file), "PNG")

    if target_path and target_path != placeholder_file:
        shutil.copy2(placeholder_file, target_path)
        return target_path
    return placeholder_file


def render_template_thumbnail(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
) -> Path:
    """Render a thumbnail from the template's DOCX with dummy sample data.
    
    Pipeline: render DOCX -> convert to PDF via LibreOffice -> rasterize page 1 via PyMuPDF ->
    save to storage/thumbnails/{ver.id}.png.
    """
    thumbnails_dir = Path("storage/thumbnails")
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumbnails_dir / f"{ver.id}.webp"
    thumb_path_png = thumbnails_dir / f"{ver.id}.png"

    if thumb_path.exists():
        return thumb_path
    if thumb_path_png.exists():
        return thumb_path_png

    # Determine DOCX source
    docx_path = None
    if ver.docx_storage_key and Path(ver.docx_storage_key).exists():
        docx_path = Path(ver.docx_storage_key)
    elif (Path("templates") / tmpl.slug / "template.docx").exists():
        docx_path = Path("templates") / tmpl.slug / "template.docx"

    if not docx_path or not docx_path.exists():
        return get_neutral_placeholder(thumb_path)

    temp_out_dir = Path("storage/temp_thumbnails") / str(uuid.uuid4())
    temp_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        db_source = DatabaseTemplateSource({tmpl.slug: (ver.schema_yaml, docx_path)})
        try:
            db_config = build_club_config_from_db(db, club_slug)
        except Exception:
            db_config = load_config()

        renderer = Renderer(
            config=db_config,
            template_source=db_source,
            outputs_dir=temp_out_dir,
        )
        dummy_event = get_dummy_thumbnail_event_record()
        dummy_extra: dict[str, Any] = {}
        if ver.schema_yaml:
            try:
                import yaml
                from docgen.schema import TemplateSchema
                from server.app.core.template_compiler import _build_editor_dummy_context
                s_dict = yaml.safe_load(ver.schema_yaml)
                s_obj = TemplateSchema(**s_dict)
                dummy_extra = _build_editor_dummy_context(s_obj, s_dict.get("fields", []), ver.editor_json or {})
            except Exception:
                pass

        render_res = renderer.render(
            template_id=tmpl.slug,
            event=dummy_event,
            extra_context=dummy_extra,
            output_dir=temp_out_dir,
            version=ver.version_no,
            convert_pdf=True,
        )

        if render_res.pdf_path and render_res.pdf_path.exists():
            pdf_doc = pymupdf.open(str(render_res.pdf_path))
            if len(pdf_doc) > 0:
                page = pdf_doc[0]
                rect = page.rect
                scale = 240.0 / max(rect.width, 1.0)
                mat = pymupdf.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                try:
                    img.save(str(thumb_path), format="WEBP", quality=80)
                except Exception:
                    img.save(str(thumb_path), format="JPEG", quality=80)
                pdf_doc.close()
                return thumb_path
            pdf_doc.close()
    except Exception as e:
        print(f"[WARN] Thumbnail generation failed for template {tmpl.slug} (v{ver.version_no}): {e}")
    finally:
        shutil.rmtree(temp_out_dir, ignore_errors=True)

    return get_neutral_placeholder(thumb_path)
