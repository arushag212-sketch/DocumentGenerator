"""Natural language extractor for Minutes of Meeting (MoM) transcripts/notes."""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

import dateparser

from docgen.config import ClubConfig, load_config
from docgen.llm import LLMClient, get_llm_client
from docgen.models import ActionItem, AgendaItem, EventRecord, FieldSource, MeetingBlock, tf


class MoMExtractor:
    def __init__(self, config: Optional[ClubConfig] = None, llm: Optional[LLMClient] = None):
        self.config = config or load_config()
        self.llm = llm or get_llm_client()

    def extract_from_notes(self, text: str) -> EventRecord:
        """Parse raw meeting notes into an EventRecord with a MeetingBlock."""
        event = EventRecord()
        event.record_type = tf("meeting", FieldSource.user, confirmed=True)

        meeting = MeetingBlock()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Try deterministic pattern extraction
        attendees = []
        agenda_items = []
        action_items = []

        for line in lines:
            # Attendees line
            if re.match(r'^(?:attendees?|present):', line, re.IGNORECASE):
                names_part = re.sub(r'^(?:attendees?|present):', '', line, flags=re.IGNORECASE)
                attendees.extend([n.strip() for n in re.split(r'[,;]', names_part) if n.strip()])
            # Chaired by
            elif re.match(r'^(?:chaired by|chair):', line, re.IGNORECASE):
                meeting.chaired_by = re.sub(r'^(?:chaired by|chair):', '', line, flags=re.IGNORECASE).strip()
            # Action item
            elif re.search(r'\baction(?:\s+item)?:\s*(.*)', line, re.IGNORECASE):
                m = re.search(r'\baction(?:\s+item)?:\s*(.*)', line, re.IGNORECASE)
                task_text = m.group(1).strip()
                action_items.append(ActionItem(task=task_text))
            # Agenda / discussion
            elif re.match(r'^(?:agenda|topic|\d+\.):', line, re.IGNORECASE):
                topic_text = re.sub(r'^(?:agenda|topic|\d+\.):', '', line, flags=re.IGNORECASE).strip()
                agenda_items.append(AgendaItem(topic=topic_text, discussion=line))

        # Title
        if lines:
            meeting.title = lines[0]
            event.event_name = tf(lines[0], FieldSource.extracted_rule, confirmed=False)

        meeting.attendees = attendees
        meeting.agenda_items = agenda_items
        meeting.action_items = action_items
        meeting.venue = self.config.venues.get("Seminar Hall", None).full_name if self.config.venues else "Seminar Hall"
        meeting.mode = "Offline"
        meeting.date = date.today()
        meeting.start_time = None
        meeting.end_time = None
        meeting.prepared_by = self.config.student_head.name if self.config.student_head else "Student Representative"
        meeting.approved_by = self.config.faculty_chairman.name if self.config.faculty_chairman else "Faculty In-Charge"

        # LLM enhancement if attendees or agenda items weren't found deterministically
        if not attendees or not agenda_items:
            schema = {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "chaired_by": {"type": "string"},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                    "agenda_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "discussion": {"type": "string"},
                                "decision": {"type": "string"}
                            }
                        }
                    },
                    "action_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string"},
                                "owner": {"type": "string"},
                                "deadline": {"type": "string"}
                            }
                        }
                    }
                }
            }
            res = self.llm.generate_json(
                f"Extract structured meeting minutes strictly from these notes:\n{text}",
                schema
            )
            if res:
                if res.get("title") and not meeting.title:
                    meeting.title = res["title"]
                    event.event_name = tf(res["title"], FieldSource.extracted_llm, confirmed=False)
                if res.get("chaired_by"):
                    meeting.chaired_by = res["chaired_by"]
                if res.get("attendees") and not meeting.attendees:
                    meeting.attendees = res["attendees"]
                if res.get("agenda_items") and not meeting.agenda_items:
                    meeting.agenda_items = [AgendaItem(**item) for item in res["agenda_items"]]
                if res.get("action_items") and not meeting.action_items:
                    meeting.action_items = [ActionItem(**item) for item in res["action_items"]]

        event.meeting = meeting
        return event
