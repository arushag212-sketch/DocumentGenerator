"""Natural language extractor: combines deterministic rule/regex parsing with optional LLM fallback."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

import dateparser

from docgen.config import ClubConfig, load_config
from docgen.llm import LLMClient, get_llm_client
from docgen.models import EventRecord, FieldSource, tf


class EventExtractor:
    def __init__(self, config: Optional[ClubConfig] = None, llm: Optional[LLMClient] = None):
        self.config = config or load_config()
        self.llm = llm or get_llm_client()

    def extract_from_text(self, text: str) -> EventRecord:
        """Extract event information from freeform natural language text."""
        event = EventRecord()

        # 1. Rule-based extraction
        # Expected participants (e.g., "around 120 students", "150+ participants", "50 attendees")
        count_match = re.search(r'(?:around|approx(?:imately)?|about|\+)?\s*(\d+)\s*(?:students?|participants?|attendees?|delegates?|people)', text, re.IGNORECASE)
        if count_match:
            event.expected_participants = tf(int(count_match.group(1)), FieldSource.extracted_rule, confirmed=True)

        # Date ranges (e.g. "14–15 October", "14-15 Oct", "14 to 15 October")
        # Normalize en-dash / em-dash to hyphen
        norm_text = text.replace("–", "-").replace("—", "-")
        range_match = re.search(r'(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?', norm_text)
        current_year = int(self.config.academic_year.split("-")[0]) if self.config.academic_year else 2026

        if range_match:
            d_start, d_end, month_name, year_str = range_match.groups()
            year = int(year_str) if year_str else current_year
            try:
                dt_start = dateparser.parse(f"{d_start} {month_name} {year}")
                dt_end = dateparser.parse(f"{d_end} {month_name} {year}")
                if dt_start and dt_end:
                    event.date_start = tf(dt_start.strftime("%Y-%m-%d"), FieldSource.extracted_rule, confirmed=True)
                    event.date_end = tf(dt_end.strftime("%Y-%m-%d"), FieldSource.extracted_rule, confirmed=True)
                    event.dates = tf(f"{d_start}-{d_end} {month_name} {year}", FieldSource.extracted_rule, confirmed=True)
            except Exception:
                pass
        else:
            # Single date match (e.g. "14 October 2026" or "14 Oct")
            single_match = re.search(r'(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?', norm_text)
            if single_match:
                d_day, month_name, year_str = single_match.groups()
                year = int(year_str) if year_str else current_year
                parsed_dt = dateparser.parse(f"{d_day} {month_name} {year}")
                if parsed_dt:
                    iso_str = parsed_dt.strftime("%Y-%m-%d")
                    event.date_start = tf(iso_str, FieldSource.extracted_rule, confirmed=True)
                    event.date_end = tf(iso_str, FieldSource.extracted_rule, confirmed=True)
                    event.dates = tf(f"{d_day} {month_name} {year}", FieldSource.extracted_rule, confirmed=True)

        # Venue matching against venue registry
        for v_name, v_conf in self.config.venues.items():
            if v_name.lower() in text.lower() or (v_conf.short_name and v_conf.short_name.lower() in text.lower()):
                event.venue = tf(v_conf.full_name, FieldSource.extracted_rule, confirmed=True)
                break

        # Event type (e.g. Workshop, Hackathon, Webinar, Competition, Meet)
        event_types = ["workshop", "hackathon", "competition", "seminar", "webinar", "meet", "session", "conference"]
        for et in event_types:
            if re.search(r'\b' + et + r'\b', text, re.IGNORECASE):
                event.event_type = tf(et.capitalize(), FieldSource.extracted_rule, confirmed=True)
                event.category = tf(et.capitalize(), FieldSource.extracted_rule, confirmed=True)
                break

        # Event title / name heuristics
        title_match = re.search(r'(?:conducting|organizing|holding|hosting)\s+(?:a|an)?\s*(?:two-day|one-day|3-day|2-day)?\s*([A-Za-z0-9\s]+?(?:Workshop|Hackathon|Competition|Seminar|Webinar|Meet|Session))', text, re.IGNORECASE)
        if title_match:
            extracted_name = title_match.group(1).strip()
            event.event_name = tf(extracted_name, FieldSource.extracted_rule, confirmed=True)
            # Default short code
            words = [w for w in extracted_name.split() if w.lower() not in ("a", "an", "the", "for", "in", "on", "of")]
            code = "".join(w[0].upper() for w in words[:4])
            event.event_code = tf(code, FieldSource.extracted_rule, confirmed=False)

        # Default organizers
        event.organizers = tf(self.config.club_name, FieldSource.config, confirmed=True)
        event.academic_year = tf(self.config.academic_year, FieldSource.config, confirmed=True)

        # 2. LLM Fallback for unextracted fields or drafting narrative
        llm_schema = {
            "type": "object",
            "properties": {
                "event_name": {"type": "string"},
                "event_type": {"type": "string"},
                "venue": {"type": "string"},
                "expected_participants": {"type": "integer"},
                "target_audience": {"type": "string"},
            },
        }

        # Check if key info is missing
        if not event.event_name.is_present or not event.venue.is_present:
            llm_res = self.llm.generate_json(
                f"Extract event information from the following sentence:\n{text}",
                llm_schema
            )
            if llm_res:
                if not event.event_name.is_present and llm_res.get("event_name"):
                    event.event_name = tf(llm_res["event_name"], FieldSource.extracted_llm, confirmed=False)
                if not event.venue.is_present and llm_res.get("venue"):
                    event.venue = tf(llm_res["venue"], FieldSource.extracted_llm, confirmed=False)
                if not event.expected_participants.is_present and llm_res.get("expected_participants"):
                    event.expected_participants = tf(int(llm_res["expected_participants"]), FieldSource.extracted_llm, confirmed=False)
                if llm_res.get("target_audience"):
                    event.target_audience = tf(llm_res["target_audience"], FieldSource.extracted_llm, confirmed=False)

        # SEPARATE AI drafting for Description and Objectives (never shared)
        ev_name_val = event.event_name.value or "the event"
        venue_val = event.venue.value or "the venue"
        dates_val = event.dates.value or "the scheduled dates"
        part_val = event.expected_participants.value or "participants"

        if not event.description.is_present:
            desc_prompt = (
                f"Draft a brief 2-sentence description of the event '{ev_name_val}' "
                f"to be held at {venue_val} on {dates_val} for {part_val}."
            )
            raw_desc = self.llm.draft_text(desc_prompt, {"event_name": ev_name_val, "venue": venue_val})
            event.description = tf(
                f"[AI-drafted, review] {raw_desc}",
                FieldSource.extracted_llm,
                confirmed=False
            )

        if not event.objectives.is_present:
            obj_prompt = (
                f"Draft 2 specific, clear learning and organizational objectives for '{ev_name_val}'."
            )
            raw_obj = self.llm.draft_text(obj_prompt, {"event_name": ev_name_val, "venue": venue_val})
            event.objectives = tf(
                f"[AI-drafted, review] {raw_obj}",
                FieldSource.extracted_llm,
                confirmed=False
            )

        return event
