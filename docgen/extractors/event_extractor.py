"""Natural language extractor: combines deterministic rule/regex parsing with optional LLM fallback."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

import dateparser

from docgen.config import ClubConfig, load_config
from docgen.llm import LLMClient, get_llm_client
from docgen.models import EventRecord, FieldSource, tf


MONTH_NAMES = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december"
}


class EventExtractor:
    def __init__(self, config: Optional[ClubConfig] = None, llm: Optional[LLMClient] = None):
        self.config = config or load_config()
        self.llm = llm or get_llm_client()

    def extract_from_text(self, text: str) -> EventRecord:
        """Extract event information from freeform natural language text."""
        event = EventRecord()

        # 1. Rule-based extraction
        # Expected participants (e.g., "around 120 students", "150+ participants", "around 60 first years")
        count_match = re.search(
            r'(?:around|approx(?:imately)?|about|\+)?\s*(\d+)\s*(students?|participants?|attendees?|delegates?|people|first years?|second years?|third years?|final years?|freshers?|members?)',
            text,
            re.IGNORECASE,
        )
        if count_match:
            event.expected_participants = tf(int(count_match.group(1)), FieldSource.extracted_rule, confirmed=False)
            group_word = count_match.group(2) if len(count_match.groups()) > 1 and count_match.group(2) else "students"
            event.target_audience = tf(f"SVNIT {group_word.capitalize()}", FieldSource.extracted_rule, confirmed=False)

        norm_text = text.replace("–", "-").replace("—", "-")

        # Time ranges (explicit AM/PM or shorthand e.g. "from 09:00 AM to 06:00 PM", "10am to 4pm", "10 to 4", "10 to 4 pm")
        time_range_re = re.compile(
            r'\b(?:(?:from|between)\s+)?'
            r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*'
            r'(?:to|-|till|until)\s*'
            r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b',
            re.IGNORECASE,
        )

        for m in time_range_re.finditer(norm_text):
            m_start, m_end = m.start(), m.end()
            t1_raw, t2_raw = m.groups()

            # Disqualify if it's actually a date range like "14-15 October" or "October 14-15"
            has_explicit_time_signal = any(x in (t1_raw + t2_raw).lower() for x in ("am", "pm", ":"))
            if not has_explicit_time_signal:
                after_match = norm_text[m_end:].lstrip()
                word_after = re.match(r'^[a-zA-Z]+', after_match)
                if word_after and word_after.group(0).lower() in MONTH_NAMES:
                    continue

                before_match = norm_text[:m_start].rstrip()
                word_before = re.search(r'([a-zA-Z]+)$', before_match)
                if word_before and word_before.group(1).lower() in MONTH_NAMES:
                    continue

            # Parse hours & minutes
            m1 = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', t1_raw.strip(), re.I)
            m2 = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', t2_raw.strip(), re.I)
            if not m1 or not m2:
                continue
            h1, min1, ap1 = int(m1.group(1)), int(m1.group(2) or 0), (m1.group(3) or "").upper()
            h2, min2, ap2 = int(m2.group(1)), int(m2.group(2) or 0), (m2.group(3) or "").upper()

            if h1 > 23 or h2 > 23 or min1 > 59 or min2 > 59:
                continue

            # Disallow plain numbers without minutes/ampm where numbers are days > 12
            if not ap1 and not ap2 and not m1.group(2) and not m2.group(2) and (h1 > 12 or h2 > 12):
                continue

            if ap1 and ap2:
                pass
            elif ap2 and not ap1:
                if ap2 == "PM":
                    ap1 = "AM" if (h1 < 12 and h1 > h2) else "PM"
                else:
                    ap1 = "AM"
            elif ap1 and not ap2:
                if ap1 == "AM":
                    ap2 = "PM" if h2 < h1 else "AM"
                else:
                    ap2 = "PM"
            else:
                if h1 >= 12 or h2 >= 12:
                    ap1 = "AM" if h1 < 12 else "PM"
                    ap2 = "AM" if h2 < 12 else "PM"
                    h1 = h1 % 12 or 12
                    h2 = h2 % 12 or 12
                elif h1 in range(7, 13) and h2 in range(1, 8):
                    ap1, ap2 = "AM", "PM"
                elif h1 in range(1, 7) and h2 in range(1, 10) and h1 < h2:
                    ap1, ap2 = "PM", "PM"
                elif h1 in range(8, 13) and h2 in range(8, 13) and h1 < h2:
                    ap1, ap2 = "AM", "AM"
                else:
                    ap1, ap2 = "AM", "PM"

            t_start_str = f"{h1:02d}:{min1:02d} {ap1}"
            t_end_str = f"{h2:02d}:{min2:02d} {ap2}"
            event.time_start = tf(t_start_str, FieldSource.extracted_rule, confirmed=False)
            event.time_end = tf(t_end_str, FieldSource.extracted_rule, confirmed=False)
            break

        # Single time match fallback (e.g. "at 10:00 AM", "from 10:00 AM")
        if not event.time_start.is_present:
            single_time_m = re.search(r'\b(?:at|from)\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))\b', norm_text)
            if single_time_m:
                raw_st = single_time_m.group(1).strip()
                m_st = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)$', raw_st, re.I)
                if m_st:
                    h, m, ap = int(m_st.group(1)), int(m_st.group(2) or 0), m_st.group(3).upper()
                    event.time_start = tf(f"{h:02d}:{m:02d} {ap}", FieldSource.extracted_rule, confirmed=False)

        current_year = int(self.config.academic_year.split("-")[0]) if self.config.academic_year else 2026

        # Numeric date matching (e.g. "15/10/2026", "15-10-2026", "15.10.2026")
        num_date_match = re.search(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b', norm_text)

        # Range Day-First: e.g. "14-15 October", "14th to 15th Oct", "14 to 15 October 2026"
        range_df_match = re.search(
            r'\b(?:(?:on\s+)?(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*[,.]?\s+)?)?'
            r'(\d{1,2})(?:st|nd|rd|th)?\s*(?:-|to)\s*(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)(?:\s*,?\s*(\d{4}))?\b',
            norm_text,
            re.IGNORECASE,
        )

        # Range Month-First: e.g. "October 14-15", "Oct 14 to 15"
        range_mf_match = re.search(
            r'\b(?:(?:on\s+)?(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*[,.]?\s+)?)?'
            r'([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*(?:-|to)\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b',
            norm_text,
            re.IGNORECASE,
        )

        if num_date_match:
            d_day, d_month, d_year = num_date_match.groups()
            iso_str = f"{d_year}-{int(d_month):02d}-{int(d_day):02d}"
            formatted_date = f"{int(d_day):02d}/{int(d_month):02d}/{d_year}"
            event.date_start = tf(iso_str, FieldSource.extracted_rule, confirmed=False)
            event.date_end = tf(iso_str, FieldSource.extracted_rule, confirmed=False)
            event.dates = tf(formatted_date, FieldSource.extracted_rule, confirmed=False)
        elif range_df_match and range_df_match.group(3).lower() in MONTH_NAMES:
            d_start, d_end, month_name, year_str = range_df_match.groups()
            year = int(year_str) if year_str else current_year
            try:
                dt_start = dateparser.parse(f"{d_start} {month_name} {year}")
                dt_end = dateparser.parse(f"{d_end} {month_name} {year}")
                if dt_start and dt_end:
                    event.date_start = tf(dt_start.strftime("%Y-%m-%d"), FieldSource.extracted_rule, confirmed=False)
                    event.date_end = tf(dt_end.strftime("%Y-%m-%d"), FieldSource.extracted_rule, confirmed=False)
                    event.dates = tf(f"{d_start}-{d_end} {month_name.capitalize()} {year}", FieldSource.extracted_rule, confirmed=False)
            except Exception:
                pass
        elif range_mf_match and range_mf_match.group(1).lower() in MONTH_NAMES:
            month_name, d_start, d_end, year_str = range_mf_match.groups()
            year = int(year_str) if year_str else current_year
            try:
                dt_start = dateparser.parse(f"{d_start} {month_name} {year}")
                dt_end = dateparser.parse(f"{d_end} {month_name} {year}")
                if dt_start and dt_end:
                    event.date_start = tf(dt_start.strftime("%Y-%m-%d"), FieldSource.extracted_rule, confirmed=False)
                    event.date_end = tf(dt_end.strftime("%Y-%m-%d"), FieldSource.extracted_rule, confirmed=False)
                    event.dates = tf(f"{d_start}-{d_end} {month_name.capitalize()} {year}", FieldSource.extracted_rule, confirmed=False)
            except Exception:
                pass
        else:
            # Single date Day-First: e.g. "sat 7th nov", "7th November 2026", "14 October"
            single_df_match = re.search(
                r'\b(?:(?:on\s+)?(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*[,.]?\s+)?)?'
                r'(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)(?:\s*,?\s*(\d{4}))?\b',
                norm_text,
                re.IGNORECASE,
            )
            # Single date Month-First: e.g. "Nov 7th", "November 7, 2026"
            single_mf_match = re.search(
                r'\b(?:(?:on\s+)?(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*[,.]?\s+)?)?'
                r'([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b',
                norm_text,
                re.IGNORECASE,
            )

            if single_df_match and single_df_match.group(2).lower() in MONTH_NAMES:
                d_day, month_name, year_str = single_df_match.groups()
                year = int(year_str) if year_str else current_year
                parsed_dt = dateparser.parse(f"{d_day} {month_name} {year}")
                if parsed_dt:
                    iso_str = parsed_dt.strftime("%Y-%m-%d")
                    event.date_start = tf(iso_str, FieldSource.extracted_rule, confirmed=False)
                    event.date_end = tf(iso_str, FieldSource.extracted_rule, confirmed=False)
                    event.dates = tf(f"{d_day} {month_name.capitalize()} {year}", FieldSource.extracted_rule, confirmed=False)
            elif single_mf_match and single_mf_match.group(1).lower() in MONTH_NAMES:
                month_name, d_day, year_str = single_mf_match.groups()
                year = int(year_str) if year_str else current_year
                parsed_dt = dateparser.parse(f"{d_day} {month_name} {year}")
                if parsed_dt:
                    iso_str = parsed_dt.strftime("%Y-%m-%d")
                    event.date_start = tf(iso_str, FieldSource.extracted_rule, confirmed=False)
                    event.date_end = tf(iso_str, FieldSource.extracted_rule, confirmed=False)
                    event.dates = tf(f"{d_day} {month_name.capitalize()} {year}", FieldSource.extracted_rule, confirmed=False)

        # Venue matching against venue registry
        # Venue matching against venue registry
        for v_name, v_conf in self.config.venues.items():
            if v_name.lower() in text.lower():
                event.venue = tf(v_name, FieldSource.extracted_rule, confirmed=False)
                break
            elif v_conf.short_name and v_conf.short_name.lower() in text.lower():
                event.venue = tf(v_conf.short_name, FieldSource.extracted_rule, confirmed=False)
                break
            elif v_conf.full_name and v_conf.full_name.lower() in text.lower():
                event.venue = tf(v_conf.full_name, FieldSource.extracted_rule, confirmed=False)
                break

        # Event type (e.g. Workshop, Hackathon, Webinar, Competition, Meet)
        event_types = ["workshop", "hackathon", "competition", "seminar", "webinar", "meet", "session", "conference"]
        for et in event_types:
            if re.search(r'\b' + et + r'\b', text, re.IGNORECASE):
                event.event_type = tf(et.capitalize(), FieldSource.extracted_rule, confirmed=False)
                event.category = tf(et.capitalize(), FieldSource.extracted_rule, confirmed=False)
                break

        # Event title / name heuristics
        title_match = re.search(
            r'(?:conducting|organizing|holding|hosting)\s+(?:a|an)?\s*(?:two-day|one-day|\d+-day)?\s*'
            r'([A-Za-z0-9\s]+?)(?=\s+(?:on|at|from|for|in|during)\b|[.,;]|$)',
            text,
            re.IGNORECASE,
        )
        if not title_match:
            title_match = re.search(
                r'(?:conducting|organizing|holding|hosting)\s+(?:a|an)?\s*(?:two-day|one-day|3-day|2-day)?\s*'
                r'([A-Za-z0-9\s]+?(?:Workshop|Hackathon|Competition|Seminar|Webinar|Meet|Session|Bootcamp))',
                text,
                re.IGNORECASE,
            )
        if not title_match:
            title_match = re.search(
                r'(?:permission|approval|note|request)\s+(?:for|regarding|about)\s+(?:(?:our|the|a|an)\s+)?'
                r'([A-Za-z0-9\s]+?(?:Workshop|Hackathon|Competition|Seminar|Webinar|Meet|Session|Bootcamp|Conclave|Fest|Conference))',
                text,
                re.IGNORECASE,
            )
        if not title_match:
            title_match = re.search(
                r'\bfor\s+(?:(?:our|the|a|an)\s+)?([A-Za-z0-9\s]+?(?:Workshop|Hackathon|Competition|Seminar|Webinar|Meet|Session|Bootcamp|Conclave|Fest|Conference))\b',
                text,
                re.IGNORECASE,
            )
        if not title_match:
            if not re.match(r'^\s*(?:i need|we need|please|request|can you)\b', text, re.IGNORECASE):
                title_match = re.match(
                    r'^\s*([A-Za-z0-9\s_-]+?)(?=\s+(?:on|at|from|during)\b|[.,;]|$)',
                    text,
                    re.IGNORECASE,
                )
        if title_match:
            extracted_name = title_match.group(1).strip()
            if extracted_name.islower():
                extracted_name = extracted_name.title()
            event.event_name = tf(extracted_name, FieldSource.extracted_rule, confirmed=False)
            # Default short code
            if "smart india hackathon" in extracted_name.lower():
                code = "SIH"
            else:
                words = [w for w in extracted_name.split() if w.lower() not in ("a", "an", "the", "for", "in", "on", "of")]
                code = "".join(w[0].upper() for w in words[:4])
            event.event_code = tf(code, FieldSource.extracted_rule, confirmed=False)
        # Budget matching (e.g. "budget sanction of Rs 25000", "budget of 15000", "sanction of 25,000 INR")
        from decimal import Decimal
        from docgen.models import BudgetItem, Winner
        budget_match = re.search(
            r'(?:budget|sanction|sanctioned(?:\s+of)?|fund|allocation)\s*(?:of|is|:)?\s*(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)',
            text,
            re.IGNORECASE,
        )
        if budget_match:
            try:
                b_amt = Decimal(budget_match.group(1).replace(",", ""))
                if b_amt > 0:
                    event.budget_items = [BudgetItem(item="Proposed Budget", amount=b_amt)]
            except Exception:
                pass

        # Winners matching (e.g. "1st prize Rs 5000 to Rahul Sharma (U22CS001)", "1st: Rahul Sharma (5000)")
        winner_pattern = re.compile(
            r'\b(1st|2nd|3rd|first|second|third|runner[\s-]?up)\s*(?:prize|place)?\s*(?:of|is|:)?\s*(?:Rs\.?|INR)?\s*([\d,]+)?\s*(?:to|for|-)?\s*([A-Za-z\s]+?)\s*\(([A-Za-z0-9]+)\)',
            re.IGNORECASE,
        )
        extracted_winners = []
        for wm in winner_pattern.finditer(text):
            pos, amt_s, w_name, w_roll = wm.groups()
            amt_val = Decimal(amt_s.replace(",", "")) if amt_s else Decimal("1000")
            extracted_winners.append(
                Winner(
                    position=pos.lower(),
                    amount=amt_val,
                    name=w_name.strip(),
                    roll_no=w_roll.strip(),
                )
            )
        if extracted_winners:
            event.winners = extracted_winners

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
                "date_start": {"type": "string", "description": "ISO format YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "ISO format YYYY-MM-DD"},
                "time_start": {"type": "string", "description": "e.g. 10:00 AM or 10:00"},
                "time_end": {"type": "string", "description": "e.g. 04:00 PM or 16:00"},
            },
        }

        # Check if key info is missing (LLM fallback only if available/configured)
        if not event.event_name.is_present or not event.venue.is_present or not event.date_start.is_present:
            try:
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
                    if not event.date_start.is_present and llm_res.get("date_start"):
                        event.date_start = tf(llm_res["date_start"], FieldSource.extracted_llm, confirmed=False)
                        event.date_end = tf(llm_res.get("date_end", llm_res["date_start"]), FieldSource.extracted_llm, confirmed=False)
                        if not event.dates.is_present:
                            event.dates = tf(llm_res["date_start"], FieldSource.extracted_llm, confirmed=False)
                    if not event.time_start.is_present and llm_res.get("time_start"):
                        from server.app.core.input_validation import format_time_display
                        event.time_start = tf(format_time_display(llm_res["time_start"]), FieldSource.extracted_llm, confirmed=False)
                    if not event.time_end.is_present and llm_res.get("time_end"):
                        from server.app.core.input_validation import format_time_display
                        event.time_end = tf(format_time_display(llm_res["time_end"]), FieldSource.extracted_llm, confirmed=False)
            except Exception:
                pass

        # SEPARATE AI drafting for Description and Objectives (never shared, clean text without tags)
        ev_name_val = event.event_name.value or "the event"
        venue_val = event.venue.value or "the venue"
        dates_val = event.dates.value or "the scheduled dates"
        part_val = event.expected_participants.value or "participants"

        if not event.description.is_present:
            desc_prompt = (
                f"Draft a brief 2-sentence description of the event '{ev_name_val}' "
                f"to be held at {venue_val} on {dates_val} for {part_val}."
            )
            try:
                raw_desc = self.llm.draft_text(desc_prompt, {"event_name": ev_name_val, "venue": venue_val})
            except Exception:
                raw_desc = f"{ev_name_val} scheduled at {venue_val} on {dates_val}."
            event.description = tf(
                f"[AI-drafted, review] {raw_desc.strip()}",
                FieldSource.extracted_llm,
                confirmed=False
            )

        if not event.objectives.is_present:
            obj_prompt = (
                f"Draft 2 specific, clear learning and organizational objectives for '{ev_name_val}'."
            )
            try:
                raw_obj = self.llm.draft_text(obj_prompt, {"event_name": ev_name_val, "venue": venue_val})
            except Exception:
                raw_obj = f"1. Successfully organize {ev_name_val}.\n2. Facilitate learning and participation for {part_val}."
            event.objectives = tf(
                f"[AI-drafted, review] {raw_obj.strip()}",
                FieldSource.extracted_llm,
                confirmed=False
            )

        return event
