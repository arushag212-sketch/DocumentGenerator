"""Dummy synthetic data and rendering pipeline for template thumbnails.

Renders template thumbnails directly from the template's docx using purely synthetic,
clearly fake dummy values (no real names, redaction boxes, or content from external documents).
Converts via LibreOffice, rasterizes page 1 with PyMuPDF, and caches at
storage/thumbnails/{template_version_id}.png.
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Optional

import re
import textwrap
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont
from server.app.core.config import settings
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
from server.app.core.storage import require_local_storage


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
    placeholder_dir = require_local_storage().base_dir / "thumbnails"
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


logger = logging.getLogger(__name__)

# Preview image width in pixels
THUMBNAIL_WIDTH_PX = 900.0
# Full-page sample preview (the gallery's "Preview" viewer) width in pixels
PAGE_PREVIEW_WIDTH_PX = 1400.0
MAX_PREVIEW_PAGES = 12


def preview_page_paths(thumb_path: Path) -> list[Path]:
    """Cached full-size sample pages saved next to a template's card preview."""
    stem = thumb_path.stem
    pages = sorted(thumb_path.parent.glob(f"{stem}_p*.webp"), key=lambda p: int(p.stem.rsplit("_p", 1)[1]))
    return pages


def render_template_preview_pages(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    club_id: Optional[str] = None,
) -> list[Path]:
    """Every page of the template filled with sample data, as the viewing club would print it."""
    local_storage = require_local_storage()
    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumbnails_dir / f"{thumbnail_stem(tmpl, ver, club_id)}.webp"
    pages = preview_page_paths(thumb_path)
    if pages:
        return pages
    with _PREVIEW_SLOTS:
        pages = preview_page_paths(thumb_path)
        if pages:
            return pages
        docx_path = _template_docx(tmpl, ver, local_storage)
        if docx_path is None:
            return []
        _render_thumbnail(db, tmpl, ver, club_slug, docx_path, thumb_path, local_storage)
    return preview_page_paths(thumb_path)


def _template_docx(tmpl: Template, ver: TemplateVersion, local_storage) -> Optional[Path]:
    if ver.docx_storage_key:
        candidate = local_storage.local_path(ver.docx_storage_key)
        if candidate.exists():
            return candidate
    fallback = Path("templates") / tmpl.slug / "template.docx"
    return fallback if fallback.exists() else None

# Each conversion runs its own LibreOffice profile; cap the gallery's card renders so opening it
# doesn't start a dozen at once, and give the Preview viewer separate slots so it never waits
# behind that queue.
class _ConfigurableSemaphore:
    """Bounded semaphore that uses 1 slot in LOW_MEMORY_MODE, 2 slots normally."""

    def __init__(self, normal_val: int = 2, low_val: int = 1):
        self._normal = threading.BoundedSemaphore(normal_val)
        self._low = threading.BoundedSemaphore(low_val)

    def _curr(self) -> threading.BoundedSemaphore:
        return self._low if getattr(settings, "LOW_MEMORY_MODE", False) else self._normal

    def acquire(self, *args, **kwargs):
        return self._curr().acquire(*args, **kwargs)

    def release(self, *args, **kwargs):
        return self._curr().release(*args, **kwargs)

    def __enter__(self):
        return self._curr().__enter__()

    def __exit__(self, *args):
        return self._curr().__exit__(*args)

    @property
    def _value(self):
        return self._curr()._value

    @property
    def _initial_value(self):
        return self._curr()._initial_value


_RENDER_SLOTS = _ConfigurableSemaphore(2, 1)
_PREVIEW_SLOTS = _ConfigurableSemaphore(2, 1)


def thumbnail_stem(tmpl: Template, ver: TemplateVersion, club_id: Optional[str]) -> str:
    """Built-in templates are shared, so each club gets its own preview (its own letterhead and
    name); a club's own template has a single preview."""
    if getattr(settings, "LOW_MEMORY_MODE", False):
        return str(ver.id)
    return f"{ver.id}_{club_id}" if tmpl.club_id is None and club_id else str(ver.id)


def _parse_hex_color(hex_str: Optional[str], default: tuple[int, int, int] = (79, 129, 189)) -> tuple[int, int, int]:
    if not hex_str:
        return default
    s = str(hex_str).strip().lstrip("#")
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            pass
    elif len(s) == 3:
        try:
            return (int(s[0] * 2, 16), int(s[1] * 2, 16), int(s[2] * 2, 16))
        except ValueError:
            pass
    return default


def _get_preview_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend([
            settings.ASSETS_DIR / "fonts" / "Tinos-Bold.ttf",
            settings.ASSETS_DIR / "fonts" / "OpenSans-Bold.ttf",
            settings.ASSETS_DIR / "fonts" / "Roboto-Bold.ttf",
        ])
    candidates.extend([
        settings.ASSETS_DIR / "fonts" / "OpenSans-Regular.ttf",
        settings.ASSETS_DIR / "fonts" / "Roboto-Regular.ttf",
        settings.ASSETS_DIR / "fonts" / "Tinos-Regular.ttf",
    ])
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _render_lightweight_thumbnail(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    docx_path: Path,
    thumb_path: Path,
) -> Path:
    """Build a lightweight preview image with Pillow from the template DOCX without LibreOffice."""
    try:
        doc = docx.Document(str(docx_path))
    except Exception as exc:
        logger.warning("Failed to open DOCX for lightweight preview of %s (v%s): %s", tmpl.slug, ver.version_no, exc)
        return get_neutral_placeholder()

    try:
        # White A4-proportioned page: 420 x 594 px
        img = Image.new("RGB", (420, 594), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Subtle border around document page
        draw.rectangle([(0, 0), (419, 593)], outline=(226, 232, 240), width=1)

        font_title = _get_preview_font(13, bold=True)
        font_body = _get_preview_font(9)

        y = 28
        left_x = 28
        right_x = 392
        max_y = 555

        # Club custom templates use the club's letterhead title in club's brand colour.
        # Built-in templates (tmpl.club_id is None) use a shared preview without club letterhead.
        if tmpl.club_id is not None:
            brand_color = (79, 129, 189)
            letterhead_title = None
            if club_slug:
                try:
                    db_config = build_club_config_from_db(db, club_slug)
                    letterhead_title = (getattr(db_config, "letterhead_title", None) or "").strip()
                    brand_color = _parse_hex_color(getattr(db_config, "brand_color", None))
                except Exception:
                    pass
            title_text = letterhead_title or (tmpl.name or tmpl.slug.replace("_", " ").title()).strip()
            draw.text((left_x, y), title_text, fill=brand_color, font=font_title)
            y += 18
            draw.line([(left_x, y), (right_x, y)], fill=brand_color, width=1)
            y += 12
        else:
            title_text = (tmpl.name or tmpl.slug.replace("_", " ").title()).strip()
            draw.text((left_x, y), title_text, fill=(30, 41, 59), font=font_title)
            y += 18
            draw.line([(left_x, y), (right_x, y)], fill=(203, 213, 225), width=1)
            y += 12

        def _clean_text(val: str) -> str:
            t = re.sub(r"\{%.*?%\}", "", val)
            t = re.sub(r"\{\{\s*(\w+?)(?:\.\w+)?\s*\}\}", r"[\1]", t)
            t = re.sub(r"\{\{.*?\}\}", "...", t)
            t = re.sub(r"[\t\r\n]+", "  ", t)
            t = re.sub(r" +", " ", t)
            return t.strip()

        for child in doc.element.body:
            if y >= max_y:
                break
            if child.tag.endswith("p"):
                p = Paragraph(child, doc)
                text = _clean_text(p.text)
                if not text:
                    continue
                lines = textwrap.wrap(text, width=54)
                for line in lines:
                    if y >= max_y:
                        break
                    draw.text((left_x, y), line, fill=(51, 65, 85), font=font_body)
                    y += 13
                y += 4
            elif child.tag.endswith("tbl"):
                tbl = Table(child, doc)
                for row in tbl.rows:
                    if y >= max_y:
                        break
                    cells = []
                    for c in row.cells:
                        ct = _clean_text(c.text)
                        if ct and (not cells or ct != cells[-1]):
                            cells.append(ct)
                    if cells:
                        row_text = "  |  ".join(cells)
                        lines = textwrap.wrap(row_text, width=52)
                        for line in lines:
                            if y >= max_y:
                                break
                            draw.text((left_x + 6, y), line, fill=(71, 85, 105), font=font_body)
                            y += 13
                        y += 2

        try:
            img.save(str(thumb_path), format="WEBP", quality=88, method=6)
        except Exception:
            try:
                img.save(str(thumb_path), format="JPEG", quality=90)
            except Exception:
                img.save(str(thumb_path), format="PNG")
        return thumb_path
    except Exception as exc:
        logger.warning("Lightweight thumbnail rendering failed for %s (v%s): %s", tmpl.slug, ver.version_no, exc)
        return get_neutral_placeholder()


def render_template_thumbnail(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    club_id: Optional[str] = None,
) -> Path:
    """Render a thumbnail from the template's DOCX with dummy sample data.
    
    Pipeline: render DOCX -> convert to PDF via LibreOffice -> rasterize page 1 via PyMuPDF ->
    save to storage/thumbnails/{ver.id}.png.
    """
    local_storage = require_local_storage()
    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    stem = thumbnail_stem(tmpl, ver, club_id)
    thumb_path = thumbnails_dir / f"{stem}.webp"
    thumb_path_png = thumbnails_dir / f"{stem}.png"

    if thumb_path.exists():
        return thumb_path
    if thumb_path_png.exists():
        return thumb_path_png

    # Determine DOCX source
    docx_path = None
    if ver.docx_storage_key:
        candidate = local_storage.local_path(ver.docx_storage_key)
        if candidate.exists():
            docx_path = candidate
    if docx_path is None and (Path("templates") / tmpl.slug / "template.docx").exists():
        docx_path = Path("templates") / tmpl.slug / "template.docx"

    if not docx_path or not docx_path.exists():
        return get_neutral_placeholder()

    if getattr(settings, "LOW_MEMORY_MODE", False):
        with _RENDER_SLOTS:
            if thumb_path.exists():
                return thumb_path
            return _render_lightweight_thumbnail(db, tmpl, ver, club_slug, docx_path, thumb_path)

    with _RENDER_SLOTS:
        if thumb_path.exists():  # rendered by another request while this one waited
            return thumb_path
        return _render_thumbnail(db, tmpl, ver, club_slug, docx_path, thumb_path, local_storage)


def _render_thumbnail(db, tmpl, ver, club_slug, docx_path, thumb_path, local_storage) -> Path:
    temp_out_dir = local_storage.base_dir / "temp_thumbnails" / str(uuid.uuid4())
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
        # Editor-built templates get per-field sample values; legacy forms (bills, minutes) render
        # from the full sample event record, whose tables have the columns those forms use.
        if ver.schema_yaml and ver.editor_json:
            try:
                import yaml
                from docgen.schema import TemplateSchema
                from server.app.core.template_compiler import _build_editor_dummy_context
                s_dict = yaml.safe_load(ver.schema_yaml)
                s_obj = TemplateSchema(**s_dict)
                dummy_extra = _build_editor_dummy_context(s_obj, s_dict.get("fields", []), ver.editor_json or {})
                # The viewing club's own name, department and footer come from its config, not sample values
                for key in ("club_name", "club_short", "club_code", "chapter_code", "institute_name", "institute_short",
                            "department", "department_short", "club_footer", "approval_chain", "head_of_account"):
                    dummy_extra.pop(key, None)
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
            try:
                # Full-size pages for the Preview viewer, from the same render
                for idx, pg in enumerate(pdf_doc):
                    if idx >= MAX_PREVIEW_PAGES:
                        break
                    if getattr(settings, "LOW_MEMORY_MODE", False):
                        longest_side = max(pg.rect.width, pg.rect.height, 1.0)
                        page_scale = min(PAGE_PREVIEW_WIDTH_PX / max(pg.rect.width, 1.0), 1200.0 / longest_side)
                    else:
                        page_scale = PAGE_PREVIEW_WIDTH_PX / max(pg.rect.width, 1.0)
                    mat = pymupdf.Matrix(page_scale, page_scale)
                    ppix = pg.get_pixmap(matrix=mat)
                    try:
                        Image.frombytes("RGB", [ppix.width, ppix.height], ppix.samples).save(
                            str(thumb_path.parent / f"{thumb_path.stem}_p{idx + 1}.webp"), format="WEBP", quality=88, method=6
                        )
                    finally:
                        ppix = None
                if len(pdf_doc) > 0:
                    page = pdf_doc[0]
                    rect = page.rect
                    # Sharp on high-DPI screens: the gallery card is ~360 px wide, shown at up to 2.5x
                    if getattr(settings, "LOW_MEMORY_MODE", False):
                        longest_side = max(rect.width, rect.height, 1.0)
                        scale = min(THUMBNAIL_WIDTH_PX / max(rect.width, 1.0), 1200.0 / longest_side)
                    else:
                        scale = THUMBNAIL_WIDTH_PX / max(rect.width, 1.0)
                    mat = pymupdf.Matrix(scale, scale)
                    pix = page.get_pixmap(matrix=mat)
                    try:
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        try:
                            img.save(str(thumb_path), format="WEBP", quality=88, method=6)
                        except Exception:
                            img.save(str(thumb_path), format="JPEG", quality=90)
                    finally:
                        pix = None
                    return thumb_path
            finally:
                pdf_doc.close()
    except Exception as e:
        logger.warning("Thumbnail generation failed for template %s (v%s): %s", tmpl.slug, ver.version_no, e)
    finally:
        shutil.rmtree(temp_out_dir, ignore_errors=True)

    # Not cached under this template's name, so the next view tries again
    return get_neutral_placeholder()
