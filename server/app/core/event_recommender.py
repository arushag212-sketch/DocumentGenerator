"""Event Document Recommender: natural language extraction + dynamic document recommendations.

Rules:
1. Rules first extraction; LLM fallback only if LLM is configured and key fields are missing.
2. Pre-event: Permission Letter always recommended. Approval Note recommended when budget/sanction applies.
3. Post-event: Prize Money Receipts if winners apply; Bill Summary and Bill Certificate if bills/expenses apply.
4. Meeting: Permission Letter and Minutes of Meeting (MoM).
5. Custom published club templates: matched dynamically via schema triggers and stage.
6. Grouped missing fields: aggregated across all selected templates, deduped shared fields, defer_ok marked.
"""

from __future__ import annotations

import re
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docgen.extractors.event_extractor import EventExtractor
from docgen.sources import build_club_config_from_db
from server.app.models import Club, Template, TemplateVersion


class TemplateRecommendationOut(BaseModel):
    template_id: str
    slug: str
    name: str
    category: str
    stage: str
    recommended: bool
    reason: str
    numbering_series: Optional[str] = None
    repeat_per: Optional[str] = None
    fields_count: int = 0


class GroupedMissingFieldOut(BaseModel):
    key: str
    label: str
    type: str = "text"
    ask: str
    required: bool = True
    importance: str = "optional"
    defer_ok: bool = False
    sensitive: bool = False
    columns: Optional[list[dict[str, Any]]] = None
    needed_by: list[str] = Field(default_factory=list)


class EventRecommendationResponse(BaseModel):
    event_text: str
    extracted_data: dict[str, Any]
    detected_stage: str
    has_budget: bool
    has_winners: bool
    has_bills: bool
    templates: list[TemplateRecommendationOut]
    other_templates: list[TemplateRecommendationOut] = Field(default_factory=list)
    grouped_missing_fields: list[GroupedMissingFieldOut]


BUDGET_REGEX = re.compile(
    r"\b(budget|advance|sanction|sanctioned|expenditure|fund|allocation|rs\.?|inr|\$|\d+\s*(?:lakh|thousand|k|cr|rupees))\b",
    re.IGNORECASE,
)
WINNERS_REGEX = re.compile(
    r"\b(winner|winners|prize|prizes|cash prize|1st place|2nd place|3rd place|podium|runners?-up)\b",
    re.IGNORECASE,
)
BILLS_REGEX = re.compile(
    r"\b(bill|bills|voucher|vouchers|receipts?|invoice|invoices|reimbursement|expenses?|audit)\b",
    re.IGNORECASE,
)
MEETING_REGEX = re.compile(
    r"\b(meeting|minutes|mom|agenda|deliberation|committee meet|executive meeting)\b",
    re.IGNORECASE,
)


class EventRecommender:
    @staticmethod
    def recommend(
        text: str,
        club_id: str,
        db: Session,
        explicit_data: Optional[dict[str, Any]] = None,
        selected_template_ids: Optional[list[str]] = None,
    ) -> EventRecommendationResponse:
        club = db.query(Club).filter(Club.id == club_id).first()
        club_slug = club.slug if club else "acm"
        club_config = build_club_config_from_db(db, club_slug)

        # 1. Extraction: Rules first, LLM fallback only if configured
        extractor = EventExtractor(config=club_config)
        event_record = extractor.extract_from_text(text)
        extracted = event_record.flat_dict()

        from datetime import date
        extracted.setdefault("document_date", date.today().strftime("%d/%m/%Y"))

        if explicit_data:
            for k, v in explicit_data.items():
                if v is not None and v != "":
                    extracted[k] = v

        # 2. Context detection
        has_budget = bool(
            (extracted.get("estimated_budget") and float(extracted.get("estimated_budget", 0)) > 0)
            or BUDGET_REGEX.search(text)
        )
        has_winners = bool(
            (extracted.get("winners") and len(extracted.get("winners", [])) > 0)
            or WINNERS_REGEX.search(text)
        )
        has_bills = bool(
            (extracted.get("bills") and len(extracted.get("bills", [])) > 0)
            or BILLS_REGEX.search(text)
        )
        is_meeting = bool(MEETING_REGEX.search(text))

        if is_meeting:
            detected_stage = "meeting"
        elif has_winners or has_bills:
            detected_stage = "post_event"
        else:
            detected_stage = "pre_event"

        # 3. Fetch published templates for this club
        tmpls = (
            db.query(Template)
            .filter(
                (Template.club_id == club_id) | (Template.is_system == True),
                Template.status == "published",
            )
            .all()
        )

        template_recs: list[TemplateRecommendationOut] = []
        other_template_recs: list[TemplateRecommendationOut] = []
        parsed_schemas: dict[str, dict[str, Any]] = {}

        BUNDLE_KEYWORDS = re.compile(
            r"\b(start to finish|full event|entire event|complete event|lifecycle|all documents|bundle|package|all stages)\b",
            re.IGNORECASE,
        )
        is_bundle_intent = bool(BUNDLE_KEYWORDS.search(text))

        # Detect specific simple intent
        wants_venue_simple = (
            bool(re.search(r"\b(book|booking|hall|room|seminar hall|venue|permission|lab|ground|auditorium)\b", text, re.IGNORECASE))
            and not (has_budget or has_winners or has_bills or is_meeting or is_bundle_intent)
        )
        wants_meeting_simple = (
            is_meeting
            and not (has_budget or has_winners or has_bills or is_bundle_intent or bool(re.search(r"\b(book|booking|seminar hall|auditorium)\b", text, re.IGNORECASE)))
        )
        wants_prize_simple = (
            bool(re.search(r"\b(prize|prize money|winner|winners)\b", text, re.IGNORECASE))
            and not (has_budget or wants_venue_simple or is_bundle_intent or has_bills)
        )
        wants_bills_simple = (
            has_bills
            and not (wants_venue_simple or has_winners or is_bundle_intent or has_budget or bool(re.search(r"\b(conduct|organize|book|booking|workshop|hackathon|seminar|permission)\b", text, re.IGNORECASE)))
        )
        wants_sanction_simple = (
            bool(re.search(r"\b(approval note|budget approval|sanction|financial sanction|advance approval)\b", text, re.IGNORECASE))
            and not (wants_venue_simple or has_winners or has_bills or is_meeting or is_bundle_intent)
        )

        for tmpl in tmpls:
            ver = (
                db.query(TemplateVersion)
                .filter(TemplateVersion.template_id == tmpl.id)
                .order_by(TemplateVersion.version_no.desc())
                .first()
            )
            schema_dict: dict[str, Any] = {}
            if ver and ver.schema_yaml:
                try:
                    loaded = yaml.safe_load(ver.schema_yaml)
                    if isinstance(loaded, dict):
                        schema_dict = loaded
                except Exception:
                    pass

            parsed_schemas[tmpl.id] = schema_dict

            t_stage = schema_dict.get("stage") or tmpl.stage or "pre_event"
            triggers = [t.lower() for t in (schema_dict.get("triggers") or [])]
            t_name = tmpl.name
            t_slug = tmpl.slug
            repeat_per = schema_dict.get("repeat_per")
            series_key = ((schema_dict.get("numbering") or {}).get("series") or t_slug) if schema_dict.get("numbering") else None
            fields_list = schema_dict.get("fields") or []

            recommended = False
            reason = ""

            if not tmpl.is_system:
                # Custom published club templates are eligible when their
                # declared stage matches, or when an explicit trigger appears
                # for a non-simple intent.
                matched_trigger = next((tr for tr in triggers if tr in text.lower()), None)
                stage_match = t_stage == detected_stage
                if stage_match:
                    recommended = True
                    reason = f"Matches detected event stage '{detected_stage}'."
                elif matched_trigger and not (wants_venue_simple or wants_meeting_simple or wants_prize_simple or wants_bills_simple or wants_sanction_simple):
                    recommended = True
                    reason = f"Matches '{matched_trigger}' trigger in template schema."
                else:
                    recommended = False
                    reason = f"Published club template for {tmpl.category or 'official communications'}."
            else:
                # System templates:
                if wants_venue_simple:
                    recommended = (t_slug == "permission_letter")
                    reason = "Official permission required to book and use the venue on campus." if recommended else "Not required for room/venue booking."
                elif wants_meeting_simple:
                    recommended = (t_slug == "mom")
                    reason = "Official minutes of meeting record for committee deliberations and resolutions." if recommended else "Not required for meeting minutes."
                elif wants_prize_simple:
                    recommended = (t_slug == "prize_money_receipt")
                    reason = "Individual acknowledgement receipts for prize money disbursement to winners." if recommended else "Not required for prize money receipt."
                elif wants_bills_simple:
                    recommended = (t_slug in ("bill_certificate", "bill_summary"))
                    reason = "Formal expenditure certification (Form BC-R) and summary for incurred expenses." if recommended else "Not required for bill settlement."
                elif wants_sanction_simple:
                    recommended = (t_slug == "approval_note")
                    reason = "Financial sanction and advance approval required for budget allocation and expenditures." if recommended else "Not required for financial sanction."
                else:
                    # Multi-phase / bundle / general event intent
                    if (t_slug == "permission_letter" or "permission" in triggers or (t_stage == "pre_event" and not any(k in triggers for k in ["approval", "sanction", "budget"]))) and not (has_bills and not is_bundle_intent):
                        recommended = True
                        reason = "Official permission from Head of Department and Faculty Advisor to conduct event on campus."
                    elif t_slug == "approval_note" or any(k in triggers for k in ["approval", "sanction", "budget", "finance"]):
                        if has_budget or is_bundle_intent:
                            recommended = True
                            reason = "Financial sanction and advance approval required for budget allocation and expenditures."
                        else:
                            recommended = False
                            reason = "Requires budget allocation or financial sanction to apply."
                    elif t_slug == "prize_money_receipt" or repeat_per == "winners" or any(k in triggers for k in ["prize", "winner"]):
                        if has_winners:
                            recommended = True
                            reason = "Individual acknowledgement receipts for prize money disbursement to winners."
                        else:
                            recommended = False
                            reason = "Applicable post-event when student winners and prize amounts are declared."
                    elif t_slug == "bill_summary" or any(k in triggers for k in ["bill_summary", "expenditure", "bills"]):
                        if has_bills or is_bundle_intent:
                            recommended = True
                            reason = "Consolidated itemized summary of event expenditures and audit vouchers."
                        else:
                            recommended = False
                            reason = "Applicable post-event when vouchers and expenses are settled."
                    elif t_slug == "bill_certificate" or repeat_per == "bills" or any(k in triggers for k in ["certificate", "bc-r"]):
                        if has_bills:
                            recommended = True
                            reason = "Formal expenditure certification (Form BC-R) for incurred expenses."
                        else:
                            recommended = False
                            reason = "Formal reimbursement certification for incurred expenses."
                    elif t_slug == "mom" or t_stage == "meeting" or any(k in triggers for k in ["meeting", "minutes"]):
                        if is_meeting:
                            recommended = True
                            reason = "Official minutes of meeting record for committee deliberations and resolutions."
                        else:
                            recommended = False
                            reason = "Applicable for internal committee meetings and formal resolutions."
                    else:
                        recommended = False
                        reason = f"System template for {tmpl.category or 'official communications'}."

            target_list = template_recs if recommended else other_template_recs
            target_list.append(
                TemplateRecommendationOut(
                    template_id=tmpl.id,
                    slug=t_slug,
                    name=t_name,
                    category=tmpl.category or "Official Event Documents",
                    stage=t_stage,
                    recommended=recommended,
                    reason=reason,
                    numbering_series=series_key,
                    repeat_per=repeat_per,
                    fields_count=len(fields_list),
                )
            )

        # 4. Grouped Missing-Info calculation
        # Which templates are active? User-selected list if provided, else all recommended templates
        if selected_template_ids is not None:
            # The web client uses stable slugs while the recommender schema map is
            # keyed by database ids. Resolve both forms so selecting a document
            # type also exposes that template's detail fields.
            requested = set(selected_template_ids)
            active_ids = {
                tmpl.id for tmpl in tmpls
                if tmpl.id in requested or tmpl.slug in requested
            }
        else:
            active_ids = {r.template_id for r in template_recs if r.recommended}

        grouped_fields_map: dict[str, GroupedMissingFieldOut] = {}

        for tmpl_id in active_ids:
            schema_dict = parsed_schemas.get(tmpl_id, {})
            t_obj = next((t for t in tmpls if t.id == tmpl_id), None)
            t_name = t_obj.name if t_obj else "Selected Template"

            for f in schema_dict.get("fields", []):
                f_key = f.get("key")
                if not f_key or f_key in ("ref_no", "document_date"):
                    continue

                # Check if already present in extracted data
                val = extracted.get(f_key)
                is_missing = False
                if val is None:
                    is_missing = True
                elif isinstance(val, str) and not val.strip():
                    is_missing = True
                elif isinstance(val, str) and "[AI-drafted" in val:
                    is_missing = True
                elif isinstance(val, (list, dict)) and len(val) == 0:
                    is_missing = True

                # If missing, add to grouped panel
                if is_missing:
                    ask_raw = f.get("ask") or f.get("label") or f"Please provide {f_key.replace('_', ' ')}"
                    ay_str = club.academic_year_default if club and club.academic_year_default else "2026-27"
                    from docgen.numbering import compute_short_year
                    short_y = compute_short_year(ay_str)
                    ask_text = (
                        ask_raw
                        .replace("{academic_year}", ay_str)
                        .replace("{short_year}", short_y)
                        .replace("{next}", "001")
                    )

                    if f_key not in grouped_fields_map:
                        grouped_fields_map[f_key] = GroupedMissingFieldOut(
                            key=f_key,
                            label=f.get("label") or f_key.replace("_", " ").title(),
                            type=f.get("type", "text"),
                            ask=ask_text,
                            required=bool(f.get("required", False)),
                            importance=f.get("importance", "essential" if f.get("required") else "optional"),
                            defer_ok=bool(f.get("defer_ok", False)),
                            sensitive=bool(f.get("mask", False) or f.get("sensitive", False)),
                            columns=f.get("columns"),
                            needed_by=[t_name],
                        )
                    else:
                        if t_name not in grouped_fields_map[f_key].needed_by:
                            grouped_fields_map[f_key].needed_by.append(t_name)
                        # If any template requires it strictly without defer_ok, update
                        if not f.get("defer_ok", False):
                            grouped_fields_map[f_key].defer_ok = False

        # Inferred year detection: if dates present but year omitted from user text
        has_explicit_year = bool(re.search(r"\b20\d\d\b", text))
        ay_club = club.academic_year_default if club and club.academic_year_default else "2026-27"
        inferred_year = ay_club.split("-")[0] if "-" in ay_club else ay_club
        if extracted.get("dates") and not has_explicit_year:
            notice = f"{inferred_year} (assumed from academic year {ay_club}, confirm)"
            extracted["dates_inferred_notice"] = notice
            extracted["dates_inferred"] = True
            if not explicit_data or not explicit_data.get("dates_confirmed"):
                active_names = [t.name for t in tmpls if t.id in active_ids]
                grouped_fields_map["dates_confirmation"] = GroupedMissingFieldOut(
                    key="dates_confirmation",
                    label="Dates Confirmation",
                    type="confirm",
                    ask=notice,
                    required=True,
                    defer_ok=False,
                    sensitive=False,
                    needed_by=active_names or ["All Selected Documents"],
                )

        missing_list = list(grouped_fields_map.values())

        return EventRecommendationResponse(
            event_text=text,
            extracted_data=extracted,
            detected_stage=detected_stage,
            has_budget=has_budget,
            has_winners=has_winners,
            has_bills=has_bills,
            templates=template_recs,
            other_templates=other_template_recs,
            grouped_missing_fields=missing_list,
        )
