"""Dummy synthetic data and rendering pipeline for template thumbnails.

Renders template thumbnails directly from the template's docx using purely synthetic,
clearly fake dummy values (no real names, redaction boxes, or content from external documents).
Converts via LibreOffice, rasterizes page 1 with PyMuPDF, and caches at
storage/thumbnails/{template_version_id}.png.
"""

from __future__ import annotations

import logging
import queue
import shutil
import threading
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional, Any

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
from docgen.renderer import Renderer, _PDF_SLOTS
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


def get_static_thumbnail_path(slug: str) -> Optional[Path]:
    """Return pre-rendered static thumbnail path if it exists."""
    candidates = [
        Path("static_thumbnails") / f"{slug}.webp",
        Path(__file__).resolve().parents[3] / "static_thumbnails" / f"{slug}.webp",
        Path("/app/static_thumbnails") / f"{slug}.webp",
        Path("backend/static_thumbnails") / f"{slug}.webp",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def get_static_preview_pages(slug: str) -> list[Path]:
    """Return pre-rendered full preview pages if they exist."""
    candidates_dirs = [
        Path("static_thumbnails"),
        Path(__file__).resolve().parents[3] / "static_thumbnails",
        Path("/app/static_thumbnails"),
        Path("backend/static_thumbnails"),
    ]
    for d in candidates_dirs:
        if d.is_dir():
            pages = sorted(
                d.glob(f"{slug}_p*.webp"),
                key=lambda p: int(p.stem.rsplit("_p", 1)[1]) if "_p" in p.stem else 0,
            )
            if pages:
                return pages
    return []


def is_placeholder_file(path: Path) -> bool:
    """Return True if path is a placeholder image or has an active .placeholder marker."""
    name = path.name.lower()
    if "placeholder" in name or name.startswith("neutral"):
        return True
    if path.with_suffix(".placeholder").exists():
        return True
    return False


def _render_clean_placeholder(
    tmpl: Optional[Template],
    ver: Optional[TemplateVersion],
    club_slug: str,
    target_path: Path,
    db: Optional[Session] = None,
) -> Path:
    """Build a clean neutral card placeholder with template name, category, simple page outline, and 'Preview loading…'."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (420, 594), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)

    # Document border
    draw.rectangle([(20, 20), (400, 574)], outline=(226, 232, 240), fill=(255, 255, 255), width=1)

    # Brand color accent stripe
    brand_color = (79, 129, 189)
    if tmpl and tmpl.club_id is not None and club_slug and db:
        try:
            db_config = build_club_config_from_db(db, club_slug)
            brand_color = _parse_hex_color(getattr(db_config, "brand_color", None))
        except Exception:
            pass
    draw.rectangle([(20, 20), (400, 26)], fill=brand_color)

    font_title = _get_preview_font(13, bold=True)
    font_category = _get_preview_font(9, bold=True)
    font_body = _get_preview_font(10)

    # Category badge
    cat_text = (tmpl.category if tmpl and tmpl.category else "OFFICIAL DOCUMENT").upper()
    draw.text((45, 45), cat_text, fill=(100, 116, 139), font=font_category)

    # Template title
    title_text = ((tmpl.name or tmpl.slug.replace("_", " ").title()) if tmpl else "Document Preview").strip()
    lines = textwrap.wrap(title_text, width=28)
    y = 66
    for line in lines[:3]:
        draw.text((45, y), line, fill=(30, 41, 59), font=font_title)
        y += 18

    # Divider line
    y = max(y + 8, 115)
    draw.line([(45, y), (375, y)], fill=(226, 232, 240), width=1)

    # Clean wireframe lines (no raw placeholders)
    wire_y = y + 18
    wire_lines = [(315, 10), (275, 10), (300, 10), (240, 10)]
    for w, h in wire_lines:
        if wire_y + h < 240:
            draw.rounded_rectangle([(45, wire_y), (45 + w, wire_y + h)], radius=3, fill=(241, 245, 249))
            wire_y += h + 10

    # Table wireframe
    draw.rounded_rectangle([(45, 245), (375, 335)], radius=4, outline=(226, 232, 240), fill=(248, 250, 252), width=1)
    draw.line([(45, 275), (375, 275)], fill=(226, 232, 240), width=1)
    draw.line([(180, 245), (180, 335)], fill=(226, 232, 240), width=1)
    draw.line([(45, 305), (375, 305)], fill=(226, 232, 240), width=1)

    # Lower wireframe lines
    draw.rounded_rectangle([(45, 355), (350, 365)], radius=3, fill=(241, 245, 249))
    draw.rounded_rectangle([(45, 375), (290, 385)], radius=3, fill=(241, 245, 249))

    # "Preview loading…" pill badge
    draw.rounded_rectangle([(120, 415), (300, 455)], radius=8, fill=(241, 245, 249), outline=(203, 213, 225), width=1)
    draw.text((150, 428), "Preview loading…", fill=(100, 116, 139), font=font_body)

    # Signature line wireframes at bottom
    draw.line([(45, 520), (150, 520)], fill=(203, 213, 225), width=2)
    draw.line([(270, 520), (375, 520)], fill=(203, 213, 225), width=2)

    try:
        img.save(str(target_path), format="WEBP", quality=88, method=6)
    except Exception:
        try:
            img.save(str(target_path), format="JPEG", quality=90)
        except Exception:
            img.save(str(target_path), format="PNG")

    try:
        target_path.with_suffix(".placeholder").touch()
    except Exception:
        pass
    return target_path


def get_clean_placeholder(
    tmpl: Optional[Template] = None,
    ver: Optional[TemplateVersion] = None,
    club_slug: str = "",
    target_path: Optional[Path] = None,
    db: Optional[Session] = None,
) -> Path:
    """Generate a clean document placeholder image with template title and category."""
    local_storage = require_local_storage()
    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    if target_path is None:
        stem = f"placeholder_{tmpl.id}" if tmpl else "neutral_placeholder"
        target_path = thumbnails_dir / f"{stem}.webp"
    return _render_clean_placeholder(tmpl, ver, club_slug, target_path, db=db)


def get_neutral_placeholder(target_path: Optional[Path] = None) -> Path:
    """Generate or retrieve a neutral document placeholder image."""
    placeholder_dir = require_local_storage().base_dir / "thumbnails"
    placeholder_dir.mkdir(parents=True, exist_ok=True)
    placeholder_file = placeholder_dir / "neutral_placeholder.png"

    if not placeholder_file.exists():
        _render_clean_placeholder(None, None, "", placeholder_file)

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
    if getattr(settings, "LOW_MEMORY_MODE", False) and tmpl.club_id is None:
        static_pages = get_static_preview_pages(tmpl.slug)
        if static_pages:
            return static_pages
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


@dataclass
class ThumbnailJob:
    template_id: str
    version_id: str
    club_slug: str
    club_id: Optional[str]
    stem: str


_thumbnail_queue: queue.Queue[ThumbnailJob] = queue.Queue(maxsize=50)
_pending_stems: set[str] = set()
_queue_lock = threading.Lock()
_worker_thread: Optional[threading.Thread] = None
_worker_pause_event = threading.Event()
_worker_pause_event.set()


def is_thumbnail_pending(stem: str) -> bool:
    """Return True if a thumbnail rendering job is currently queued or running."""
    with _queue_lock:
        return stem in _pending_stems


def get_queue_size() -> int:
    """Return the number of jobs currently waiting in the thumbnail queue."""
    return _thumbnail_queue.qsize()


def pause_worker() -> None:
    """Pause the background thumbnail worker (useful for testing queue state)."""
    _worker_pause_event.clear()


def resume_worker() -> None:
    """Resume the background thumbnail worker."""
    global _worker_thread
    _worker_pause_event.set()
    with _queue_lock:
        if not _thumbnail_queue.empty() and (_worker_thread is None or not _worker_thread.is_alive()):
            _worker_thread = threading.Thread(
                target=_thumbnail_worker_loop, daemon=True, name="ThumbnailWorker"
            )
            _worker_thread.start()


def wait_for_thumbnail_jobs(timeout: float = 10.0) -> None:
    """Wait for all pending thumbnail jobs in the queue to be completed."""
    _thumbnail_queue.join()


def reset_worker_state() -> None:
    """Clear the queue and pending stems, and stop any active worker (for test isolation)."""
    global _worker_thread
    with _queue_lock:
        _worker_pause_event.set()
        while not _thumbnail_queue.empty():
            try:
                _thumbnail_queue.get_nowait()
                _thumbnail_queue.task_done()
            except Exception:
                pass
        _pending_stems.clear()
        if _worker_thread is not None and _worker_thread.is_alive():
            _thumbnail_queue.put(None)
    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=2.0)
    _worker_thread = None
    _worker_pause_event.set()


def enqueue_thumbnail_job(
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    club_id: Optional[str],
    stem: str,
) -> bool:
    """Enqueue a thumbnail rendering job if not already queued or pending."""
    global _worker_thread
    with _queue_lock:
        if stem in _pending_stems:
            return False
        if _thumbnail_queue.full():
            logger.warning("Thumbnail queue full (50); dropping render for %s", stem)
            return False
        _pending_stems.add(stem)
        _thumbnail_queue.put(
            ThumbnailJob(
                template_id=tmpl.id,
                version_id=ver.id,
                club_slug=club_slug,
                club_id=club_id,
                stem=stem,
            )
        )
        if _worker_pause_event.is_set():
            if _worker_thread is None or not _worker_thread.is_alive():
                _worker_thread = threading.Thread(
                    target=_thumbnail_worker_loop, daemon=True, name="ThumbnailWorker"
                )
                _worker_thread.start()
        return True


def _thumbnail_worker_loop():
    while True:
        _worker_pause_event.wait()
        try:
            job = _thumbnail_queue.get()
        except Exception:
            break
        if job is None:
            _thumbnail_queue.task_done()
            break
        try:
            _process_thumbnail_job(job)
        except Exception as e:
            logger.warning("Thumbnail worker job failed for %s: %s", job.stem, e)
        finally:
            with _queue_lock:
                _pending_stems.discard(job.stem)
            _thumbnail_queue.task_done()


def _process_thumbnail_job(job: ThumbnailJob):
    from server.app.core.database import SessionLocal

    # Don't start jobs while a PDF download is converting: wait on _PDF_SLOTS semaphore
    _PDF_SLOTS.acquire()
    _PDF_SLOTS.release()

    db = SessionLocal()
    try:
        from server.app.models import Template, TemplateVersion

        tmpl = db.query(Template).filter(Template.id == job.template_id).first()
        ver = db.query(TemplateVersion).filter(TemplateVersion.id == job.version_id).first()
        if not tmpl or not ver:
            return
        local_storage = require_local_storage()
        docx_path = _template_docx(tmpl, ver, local_storage)
        if not docx_path or not docx_path.exists():
            return
        thumbnails_dir = local_storage.base_dir / "thumbnails"
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumbnails_dir / f"{job.stem}.webp"

        _render_thumbnail(
            db=db,
            tmpl=tmpl,
            ver=ver,
            club_slug=job.club_slug,
            docx_path=docx_path,
            thumb_path=thumb_path,
            local_storage=local_storage,
            render_pages=False,
        )

        if thumb_path.exists() and not is_placeholder_file(thumb_path):
            if hasattr(local_storage, "push"):
                local_storage.push(f"thumbnails/{thumb_path.name}")
    finally:
        db.close()


def _render_lightweight_thumbnail(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    docx_path: Path,
    thumb_path: Path,
) -> Path:
    """Build a clean neutral document card placeholder without LibreOffice."""
    return _render_clean_placeholder(tmpl, ver, club_slug, thumb_path, db=db)


def render_template_thumbnail(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    club_id: Optional[str] = None,
) -> Path:
    """Render a thumbnail from the template's DOCX with dummy sample data.
    
    In LOW_MEMORY_MODE:
    - Built-in templates: returns pre-rendered static WebP file if present, else clean placeholder.
    - Club templates: enqueues background worker job on cache miss and returns clean placeholder.
    In normal mode:
    - Renders synchronously with LibreOffice and PyMuPDF.
    """
    local_storage = require_local_storage()
    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    stem = thumbnail_stem(tmpl, ver, club_id)
    thumb_path = local_storage.local_path(f"thumbnails/{stem}.webp")
    thumb_path_png = local_storage.local_path(f"thumbnails/{stem}.png")

    if thumb_path.exists() and not is_placeholder_file(thumb_path):
        return thumb_path
    if thumb_path_png.exists() and not is_placeholder_file(thumb_path_png):
        return thumb_path_png

    docx_path = _template_docx(tmpl, ver, local_storage)

    if getattr(settings, "LOW_MEMORY_MODE", False):
        if tmpl.club_id is None:
            # Built-in template: return pre-rendered file if present
            static_thumb = get_static_thumbnail_path(tmpl.slug)
            if static_thumb and static_thumb.exists():
                return static_thumb
            return _render_clean_placeholder(tmpl, ver, club_slug, thumb_path, db=db)
        else:
            # Club template: enqueue background job and immediately return clean placeholder
            enqueue_thumbnail_job(tmpl, ver, club_slug, club_id, stem)
            return _render_clean_placeholder(tmpl, ver, club_slug, thumb_path, db=db)

    if not docx_path or not docx_path.exists():
        return get_neutral_placeholder()

    with _RENDER_SLOTS:
        if thumb_path.exists() and not is_placeholder_file(thumb_path):
            return thumb_path
        return _render_thumbnail(db, tmpl, ver, club_slug, docx_path, thumb_path, local_storage)


def _render_thumbnail(
    db: Session,
    tmpl: Template,
    ver: TemplateVersion,
    club_slug: str,
    docx_path: Path,
    thumb_path: Path,
    local_storage,
    render_pages: bool = True,
) -> Path:
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
                if render_pages:
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
                            del ppix
                if len(pdf_doc) > 0:
                    page = pdf_doc[0]
                    rect = page.rect
                    # Sharp on high-DPI screens: the gallery card is ~360 px wide, shown at up to 2.5x.
                    # In LOW_MEMORY_MODE, cap page image at 600 px on longest side for cards.
                    if getattr(settings, "LOW_MEMORY_MODE", False):
                        longest_side = max(rect.width, rect.height, 1.0)
                        scale = min(THUMBNAIL_WIDTH_PX / max(rect.width, 1.0), 600.0 / longest_side)
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
                        del pix
                    # Clean up placeholder marker if this thumb_path was previously marked as placeholder
                    placeholder_marker = thumb_path.with_suffix(".placeholder")
                    if placeholder_marker.exists():
                        try:
                            placeholder_marker.unlink()
                        except Exception:
                            pass
                    return thumb_path
            finally:
                pdf_doc.close()
    except Exception as e:
        logger.warning("Thumbnail generation failed for template %s (v%s): %s", tmpl.slug, ver.version_no, e)
    finally:
        shutil.rmtree(temp_out_dir, ignore_errors=True)

    # Not cached under this template's name, so the next view tries again
    return get_neutral_placeholder()
