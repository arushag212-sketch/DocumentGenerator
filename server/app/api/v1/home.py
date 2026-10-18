"""Home Convenience API for Phase W7.

Provides:
- POST /clubs/{club_id}/home/understand: converts user's plain words into what was understood,
  recommended documents with one-line plain reasons and suggested reference numbers,
  and a single grouped list of missing details framed as plain questions.
- POST /clubs/{club_id}/home/generate: validates input widgets, verifies reference number acceptance,
  and executes atomic batch generation via BatchGenerator.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docgen.numbering import compute_short_year
from server.app.core.batch_generator import BatchGenerator
from server.app.core.database import get_db
from server.app.core.event_recommender import EventRecommender
from server.app.core.input_validation import (
    format_time_canonical_24h,
    format_time_display,
    validate_input_fields,
)
from server.app.core.permissions import ClubContext, Role, require_club_access
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Club, NumberingSeries, Person, RoleHeld, Template, TemplateVersion


router = APIRouter(prefix="/clubs/{club_id}/home", tags=["home"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HomeUnderstandRequest(BaseModel):
    text: str = Field(..., min_length=2)
    explicit_data: Optional[dict[str, Any]] = None
    selected_template_ids: Optional[list[str]] = None


class HomeUnderstoodData(BaseModel):
    event_name: Optional[str] = None
    dates: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    venue: Optional[str] = None
    participants: Optional[int] = None
    description: Optional[str] = None
    objectives: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class HomeRecommendedDoc(BaseModel):
    template_id: str
    name: str
    slug: str
    reason: str
    recommended: bool
    suggested_ref_no: str  # e.g. "ACM/26-27/ROOM/001 will be used"


class HomeMissingQuestion(BaseModel):
    key: str
    question: str
    label: str
    type: str  # time | time_range | date | date_range | int | money | enum | venue | person_ref | text | longtext
    required: bool = True
    defer_ok: bool = False
    needed_by: list[str] = Field(default_factory=list)
    values: Optional[list[str]] = None
    current_value: Optional[Any] = None


class HomeUnderstandResponse(BaseModel):
    understood: HomeUnderstoodData
    recommended_documents: list[HomeRecommendedDoc]
    missing_questions: list[HomeMissingQuestion]


class HomeGenerateRequest(BaseModel):
    selected_template_ids: list[str] = Field(..., min_length=1)
    event_data: dict[str, Any] = Field(default_factory=dict)
    ref_numbers_accepted: bool = Field(..., description="Must be true to confirm reference numbers")
    event_title: Optional[str] = None


class HomeGeneratedDoc(BaseModel):
    id: str
    template_slug: str
    title: str
    ref_no: str
    pdf_url: str
    docx_url: str
    preview_url: str
    version_no: int


class HomeGenerateResponse(BaseModel):
    batch_id: str
    event_id: str
    event_title: str
    documents_count: int
    zip_url: str
    documents: list[HomeGeneratedDoc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_jargon(text: str) -> str:
    """Filter out internal engineering jargon from user-facing text."""
    replacements = [
        ("reservation", "booking"),
        ("series", "numbering"),
        ("canonical", "standard"),
        ("schema", "template"),
        ("job", "task"),
        ("event record", "event details"),
        ("event_record", "event details"),
    ]
    cleaned = text
    for old, new in replacements:
        cleaned = re.sub(re.escape(old), new, cleaned, flags=re.IGNORECASE)
    return cleaned


def _get_suggested_ref_no(club: Club, series_key: str, db: Session) -> str:
    """Calculate the next reference number string without incrementing."""
    ay = club.academic_year_default or "2026-27"
    short_ay = compute_short_year(ay)
    code = club.short_name or club.slug.upper()

    ns_repo = ScopedRepository(db, NumberingSeries, club_id=club.id)
    ns = ns_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == ay,
    )

    if ns:
        next_seq = ns.last_seq + 1
        fmt = ns.format
        ref_no = (
            fmt.replace("{academic_year}", short_ay)
            .replace("{short_year}", short_ay)
            .replace("{year}", ay)
            .replace("{series}", series_key)
            .replace("{seq:03d}", f"{next_seq:03d}")
            .replace("{seq}", str(next_seq))
        )
    else:
        ref_no = f"{code}/{short_ay}/{series_key}/001"

    return f"{ref_no} will be used"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/understand", response_model=HomeUnderstandResponse)
def understand_user_need(
    payload: HomeUnderstandRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Convenience endpoint: Plain words -> what was understood + recommendations + missing questions."""
    rec = EventRecommender.recommend(
        text=payload.text,
        club_id=ctx.club.id,
        db=db,
        explicit_data=payload.explicit_data,
        selected_template_ids=payload.selected_template_ids,
    )

    extracted = rec.extracted_data

    # Canonicalize time formats for input widgets
    raw_time_start = extracted.get("time_start")
    raw_time_end = extracted.get("time_end")
    time_start_picker = format_time_canonical_24h(raw_time_start) if raw_time_start else None
    time_end_picker = format_time_canonical_24h(raw_time_end) if raw_time_end else None

    understood = HomeUnderstoodData(
        event_name=extracted.get("event_name"),
        dates=extracted.get("dates") or extracted.get("date_range_str"),
        date_start=extracted.get("date_start"),
        date_end=extracted.get("date_end"),
        time_start=time_start_picker,
        time_end=time_end_picker,
        venue=extracted.get("venue"),
        participants=extracted.get("participants") or extracted.get("expected_participants"),
        description=extracted.get("description"),
        objectives=extracted.get("objectives"),
        raw=extracted,
    )

    recommended_docs: list[HomeRecommendedDoc] = []
    # Combine active recommended and other templates
    all_recs = rec.templates + rec.other_templates
    for t in all_recs:
        series_key = t.numbering_series or ("ROOM" if t.slug == "permission_letter" else "EVT")
        suggested_ref = _get_suggested_ref_no(ctx.club, series_key, db)
        reason_text = _clean_jargon(t.reason)
        if t.slug == "permission_letter" and extracted.get("venue"):
            reason_text = f"Official permission required to book and use {extracted.get('venue')} on campus."
        recommended_docs.append(
            HomeRecommendedDoc(
                template_id=t.template_id,
                name=t.name,
                slug=t.slug,
                reason=reason_text,
                recommended=t.recommended,
                suggested_ref_no=suggested_ref,
            )
        )

    # Transform missing fields into plain questions
    missing_questions: list[HomeMissingQuestion] = []
    for mf in rec.grouped_missing_fields:
        q_text = _clean_jargon(mf.ask)
        q_label = _clean_jargon(mf.label)

        # Infer widget type
        w_type = mf.type
        if mf.key in ("time_start", "time_end", "meeting_start_time", "meeting_end_time"):
            w_type = "time"
        elif mf.key in ("date_start", "date_end", "meeting_date", "invoice_date"):
            w_type = "date"
        elif mf.key in ("participants", "expected_participants"):
            w_type = "int"
        elif mf.key in ("amount", "prize_amount", "budget_total"):
            w_type = "money"
        elif mf.key == "venue":
            w_type = "venue"

        # Check prefilled value
        curr_val = extracted.get(mf.key)
        if w_type == "time" and curr_val:
            curr_val = format_time_canonical_24h(curr_val)

        missing_questions.append(
            HomeMissingQuestion(
                key=mf.key,
                question=q_text,
                label=q_label,
                type=w_type,
                required=mf.required,
                defer_ok=mf.defer_ok,
                needed_by=[_clean_jargon(n) for n in mf.needed_by],
                values=getattr(mf, "values", None),
                current_value=curr_val,
            )
        )

    # Check for roles with multiple active signatories
    if ctx.club.academic_year_default:
        active_role_holders = (
            db.query(RoleHeld)
            .filter(
                RoleHeld.club_id == ctx.club.id,
                RoleHeld.academic_year == ctx.club.academic_year_default,
                RoleHeld.valid_to.is_(None),
            )
            .all()
        )
        from collections import defaultdict
        holders_by_role = defaultdict(list)
        for rh in active_role_holders:
            holders_by_role[rh.role_key].append(rh)

        person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
        for r_key, r_holders in holders_by_role.items():
            if len(r_holders) > 1:
                people = [person_repo.get(h.person_id) for h in r_holders]
                names = [p.full_name for p in people if p]
                display_role = r_key.replace("_", " ").title()
                missing_questions.append(
                    HomeMissingQuestion(
                        key=f"signatory_{r_key}",
                        question=f"Who should sign as {display_role}?",
                        label=f"Signatory: {display_role}",
                        type="enum",
                        values=names,
                        required=True,
                        defer_ok=False,
                        needed_by=["Official Documents"],
                        current_value=extracted.get(f"signatory_{r_key}"),
                    )
                )

    return HomeUnderstandResponse(
        understood=understood,
        recommended_documents=recommended_docs,
        missing_questions=missing_questions,
    )


@router.post("/generate", response_model=HomeGenerateResponse)
def generate_user_need(
    payload: HomeGenerateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Convenience endpoint: Validate widgets, verify ref numbers acceptance, and batch generate."""
    # 1. Permission check: Editor role minimum required
    if not ctx.is_editor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access is required to generate documents.",
        )

    # 2. Reference numbers must be explicitly accepted
    if not payload.ref_numbers_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REF_NUMBERS_NOT_ACCEPTED",
                "message": "Please accept the suggested reference numbers before generating.",
            },
        )

    # Sanitize list fields (judges, budget_items) if scalar string or number sent from form
    if "judges" in payload.event_data:
        from docgen.models import coerce_to_list_of_strings
        payload.event_data["judges"] = coerce_to_list_of_strings(payload.event_data["judges"])

    if "budget_items" in payload.event_data:
        from docgen.models import coerce_to_budget_items
        b_list = coerce_to_budget_items(payload.event_data["budget_items"])
        payload.event_data["budget_items"] = [b.model_dump() for b in b_list]
    elif any(payload.event_data.get(k) for k in ("estimated_budget", "budget", "budget_amount", "sanctioned_budget")):
        from docgen.models import coerce_to_budget_items
        b_val = payload.event_data.get("estimated_budget") or payload.event_data.get("budget") or payload.event_data.get("budget_amount") or payload.event_data.get("sanctioned_budget")
        b_list = coerce_to_budget_items(b_val)
        payload.event_data["budget_items"] = [b.model_dump() for b in b_list]

    # 3. Input widget validation (dates, times, integers, amounts)
    validate_input_fields(payload.event_data)

    has_picker_dates = bool(
        payload.event_data.get("date_start")
        and payload.event_data.get("date_end")
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(payload.event_data.get("date_start")))
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(payload.event_data.get("date_end")))
    )
    if has_picker_dates:
        payload.event_data["dates_confirmed"] = True
        if not payload.event_data.get("dates"):
            from docgen.functions import fn_format_date_range
            payload.event_data["dates"] = fn_format_date_range(payload.event_data["date_start"], payload.event_data["date_end"])
    elif payload.event_data.get("dates"):
        dates_val = str(payload.event_data.get("dates") or "").strip()
        is_confirmed = bool(payload.event_data.get("dates_confirmed"))
        has_full_year = bool(re.search(r"\b20\d\d\b", dates_val))
        if not is_confirmed or not has_full_year or "assumed" in dates_val.lower():
            if not is_confirmed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "DATES_NOT_CONFIRMED",
                        "message": "Event dates must be confirmed before generation.",
                    },
                )
        if not payload.event_data.get("date_start") or not payload.event_data.get("date_end"):
            from docgen.extractors.event_extractor import EventExtractor
            try:
                ext = EventExtractor()
                parsed_rec = ext.extract_from_text(dates_val)
                if parsed_rec.date_start and not payload.event_data.get("date_start"):
                    payload.event_data["date_start"] = parsed_rec.date_start.value
                if parsed_rec.date_end and not payload.event_data.get("date_end"):
                    payload.event_data["date_end"] = parsed_rec.date_end.value
            except Exception:
                pass

    # 4. Check for multiple active signatories conflict in generate
    if ctx.club.academic_year_default:
        active_role_holders = (
            db.query(RoleHeld)
            .filter(
                RoleHeld.club_id == ctx.club.id,
                RoleHeld.academic_year == ctx.club.academic_year_default,
                RoleHeld.valid_to.is_(None),
            )
            .all()
        )
        from collections import defaultdict
        holders_by_role = defaultdict(list)
        for rh in active_role_holders:
            holders_by_role[rh.role_key].append(rh)

        person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
        for r_key, r_holders in holders_by_role.items():
            if len(r_holders) > 1:
                people = [person_repo.get(h.person_id) for h in r_holders]
                names = [p.full_name for p in people if p]
                display_role = r_key.replace("_", " ").title()
                chosen_name = payload.event_data.get(f"signatory_{r_key}")
                if not chosen_name or chosen_name not in names:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "SIGNATORY_SELECTION_REQUIRED",
                            "message": f"Multiple active signatories exist for {display_role}. Please choose who signs ({', '.join(names)}).",
                            "key": f"signatory_{r_key}",
                            "options": names,
                        },
                    )
                chosen_p = next(p for p in people if p and p.full_name == chosen_name)
                chosen_rh = next(h for h in r_holders if h.person_id == chosen_p.id)
                payload.event_data[r_key] = {
                    "name": chosen_p.full_name,
                    "admission_no": chosen_p.roll_no or "",
                    "branch": chosen_p.branch or "",
                    "mobile": chosen_p.mobile or "",
                    "email": chosen_p.email or "",
                    "designation": chosen_rh.designation_label,
                }

    # 5. Delegate to BatchGenerator
    batch_result = BatchGenerator.generate_batch(
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        selected_template_ids=payload.selected_template_ids,
        event_data=payload.event_data,
        event_title=payload.event_title,
        db=db,
    )

    # 5. Format documents list for simplified Home result page
    docs_out: list[HomeGeneratedDoc] = []
    for doc_info in batch_result.get("documents", []):
        doc_id = doc_info.get("id") or doc_info.get("document_id")
        ver_no = doc_info.get("version_no", 1)
        docs_out.append(
            HomeGeneratedDoc(
                id=doc_id,
                template_slug=doc_info.get("template_slug", "document"),
                title=doc_info.get("title", "Generated Document"),
                ref_no=doc_info.get("ref_no", ""),
                pdf_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/pdf",
                docx_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/docx",
                preview_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/preview",
                version_no=ver_no,
            )
        )

    return HomeGenerateResponse(
        batch_id=batch_result.get("batch_id"),
        event_id=batch_result.get("event_id"),
        event_title=batch_result.get("event_title"),
        documents_count=len(docs_out),
        zip_url=batch_result.get("zip_url"),
        documents=docs_out,
    )
