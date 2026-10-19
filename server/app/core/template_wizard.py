"""Template Wizard for SVNIT ClubDocs.

Guides beginners through creating customized, high-quality document templates:
1. "What document do you want?" -> AI (or offline fallback) proposes up to 3 clarifying question chips.
2. User selects answer chips (Purpose, Audience, Tone).
3. AI builds a complete designed template (fields, tables, signatures, theme) ready for the editor.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docgen.llm import LLMClient, get_llm_client
from server.app.core.template_compiler import TemplateCompiler
from server.app.core.template_generator import (
    OFFICIAL_WORDING_TRIGGERS,
    strip_pii_from_text,
)


def sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "field"

from server.app.core.rate_limit import check_rate_limit
from server.app.core.storage import get_storage, require_local_storage
from server.app.models import (
    AIRequest,
    Asset,
    Club,
    Template,
    TemplateVersion,
)


class WizardQuestion(BaseModel):
    id: str
    question: str
    category: str  # purpose, audience, tone
    options: list[str]


class WizardQuestionsResponse(BaseModel):
    prompt: str
    questions: list[WizardQuestion]
    suggested_title: str


class WizardGenerateRequest(BaseModel):
    prompt: str
    answers: dict[str, str] = Field(default_factory=dict)
    numbering_series: Optional[str] = "DOC"


def get_default_wizard_questions(prompt: str) -> list[WizardQuestion]:
    """Offline rule-based clarifying questions tailored to SVNIT student club workflows."""
    lower = prompt.lower()
    
    # 1. Purpose options
    if any(k in lower for k in ("sponsor", "financial", "budget", "money", "fund", "bill", "expense")):
        purpose_opts = [
            "Financial Sanction & Advance Approval",
            "Sponsorship Proposal to Corporate",
            "Reimbursement & Bill Settlement",
            "Prize Money Distribution",
        ]
    elif any(k in lower for k in ("permission", "room", "venue", "lab", "hall", "ground", "audi")):
        purpose_opts = [
            "Campus Venue / Lab Booking Permission",
            "After-Hours / Weekend Event Permission",
            "Sound System & AV Facilities Request",
            "Hostel Late Entry for Participants",
        ]
    elif any(k in lower for k in ("cert", "attend", "particip", "winner")):
        purpose_opts = [
            "Merit / Winner Certificate Layout",
            "Participation Certificate",
            "Volunteer Appreciation Record",
            "Executive Committee Member Certificate",
        ]
    else:
        purpose_opts = [
            "Formal Institute Approval Request",
            "Club Member Circular / Announcement",
            "Comprehensive Event Report & Summary",
            "Official Minutes of Meeting (MoM)",
        ]

    # 2. Audience options
    audience_opts = [
        "Faculty Advisor & Head of Department (DoCSE)",
        "Dean of Student Welfare (DSW) & Director",
        "Registered Club Members & Students",
        "External Industry Sponsors & Judges",
    ]

    # 3. Tone and Layout options
    tone_opts = [
        "Official Institute Protocol (Times New Roman, Navy)",
        "SVNIT Institutional Brand (Blue & Gold)",
        "Structured Tabular Format (Data-Centric)",
        "Modern Clean Document (Spacious Sans)",
    ]

    return [
        WizardQuestion(
            id="q_purpose",
            question="What is the primary purpose of this document?",
            category="purpose",
            options=purpose_opts,
        ),
        WizardQuestion(
            id="q_audience",
            question="Who will receive or review this document?",
            category="audience",
            options=audience_opts,
        ),
        WizardQuestion(
            id="q_tone",
            question="What visual tone and layout is preferred?",
            category="tone",
            options=tone_opts,
        ),
    ]


def get_wizard_questions(prompt: str, club_name: str = "ACM SVNIT") -> WizardQuestionsResponse:
    """Generate up to 3 clarifying questions with answer chips."""
    cleaned_prompt = strip_pii_from_text(prompt.strip())
    client = get_llm_client()

    # Rule-based title derivation
    title_words = [w.capitalize() for w in re.sub(r"[^\w\s]", "", cleaned_prompt).split() if len(w) > 2][:5]
    suggested_title = " ".join(title_words) if title_words else "Official Club Document"
    if not any(k in suggested_title.lower() for k in ("letter", "note", "report", "notice", "proposal", "certificate")):
        suggested_title += " Proposal"

    # Default questions
    questions = get_default_wizard_questions(cleaned_prompt)

    if client and getattr(client, "api_key", None):
        try:
            system_instruction = (
                "You are an assistant for SVNIT Student Clubs document generator. "
                "Given a document description, propose at most 3 clarifying questions with exactly 4 concise answer chips each. "
                "Categories must be: purpose, audience, tone. "
                "Respond in valid JSON format only: "
                '{"suggested_title": "string", "questions": [{"id": "q_purpose", "question": "string", "category": "purpose", "options": ["opt1", "opt2", "opt3", "opt4"]}]}'
            )
            raw = client.generate_text(
                prompt=f"Document request: {cleaned_prompt}\nClub: {club_name}",
                system_instruction=system_instruction,
            )
            clean_json = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(clean_json)
            if "questions" in data and isinstance(data["questions"], list) and len(data["questions"]) > 0:
                parsed_questions = []
                for q in data["questions"][:3]:
                    parsed_questions.append(
                        WizardQuestion(
                            id=q.get("id", f"q_{len(parsed_questions)}"),
                            question=q.get("question", ""),
                            category=q.get("category", "purpose"),
                            options=q.get("options", [])[:4],
                        )
                    )
                if parsed_questions:
                    return WizardQuestionsResponse(
                        prompt=cleaned_prompt,
                        questions=parsed_questions,
                        suggested_title=data.get("suggested_title", suggested_title),
                    )
        except Exception:
            pass  # Fall back to default rule-based questions

    return WizardQuestionsResponse(
        prompt=cleaned_prompt,
        questions=questions,
        suggested_title=suggested_title,
    )


def build_wizard_template_spec(
    prompt: str,
    answers: dict[str, str],
    club_name: str = "ACM SVNIT",
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    """Constructs TipTap editor JSON, fields, design settings, and title from user inputs."""
    cleaned_prompt = strip_pii_from_text(prompt)
    purpose = answers.get("q_purpose") or answers.get("purpose") or ""
    audience = answers.get("q_audience") or answers.get("audience") or ""
    tone = answers.get("q_tone") or answers.get("tone") or ""

    # Derive Title
    if purpose:
        title = purpose
    else:
        title_words = [w.capitalize() for w in re.sub(r"[^\w\s]", "", cleaned_prompt).split() if len(w) > 2][:5]
        title = " ".join(title_words) if title_words else "Official Club Document"

    # Select Theme based on tone
    theme_id = "official_navy"
    orientation = "portrait"
    font_family = "Tinos"
    heading_color = "#1e3a8a"
    table_header_bg = "#1e3a8a"

    if "gold" in tone.lower() or "svnit" in tone.lower():
        theme_id = "svnit_gold"
        font_family = "Open Sans"
        heading_color = "#003366"
        table_header_bg = "#003366"
    elif "modern" in tone.lower() or "sans" in tone.lower():
        theme_id = "modern_green"
        font_family = "Roboto"
        heading_color = "#065f46"
        table_header_bg = "#065f46"
    elif "tabular" in tone.lower() or "minimal" in tone.lower():
        theme_id = "minimal_grey"
        font_family = "Montserrat"
        heading_color = "#334155"
        table_header_bg = "#334155"

    design_settings = {
        "theme": theme_id,
        "fontFamily": font_family,
        "headingFontFamily": font_family,
        "fontSize": "base",
        "lineHeight": "normal",
        "headingColor": heading_color,
        "textColor": "#0f172a",
        "tableHeaderBg": table_header_bg,
        "tableHeaderTextColor": "#ffffff",
        "borderColor": "#cbd5e1",
        "dividerColor": heading_color,
        "pageBg": "#ffffff",
        "orientation": orientation,
        "margins": "normal",
        "pageBorder": "single" if "certificate" in title.lower() else "none",
        "watermark": "",
        "watermarkOpacity": 0.15,
    }

    # Build Fields
    fields: list[dict[str, Any]] = [
        {"key": "event_name", "label": "Event Name", "type": "text", "required": True, "ask": "What is the official title of the event?", "ai_suggested": True},
        {"key": "event_date", "label": "Event Date", "type": "date", "required": True, "ask": "On what date is the event taking place?", "ai_suggested": True},
        {"key": "venue", "label": "Venue / Location", "type": "text", "required": True, "ask": "Where will the activity be conducted?", "ai_suggested": True},
        {"key": "coordinator_name", "label": "Lead Student Coordinator", "type": "text", "required": True, "ask": "Who is the lead student organizer?", "ai_suggested": True},
    ]

    has_budget = any(k in (prompt + " " + purpose).lower() for k in ("budget", "cost", "sanction", "money", "expense", "fund", "prize"))
    if has_budget:
        fields.append({"key": "estimated_budget", "label": "Estimated Budget (INR)", "type": "money", "required": True, "ask": "What is the total estimated financial outlay?", "ai_suggested": True})

    # Build TipTap Content Blocks
    blocks: list[dict[str, Any]] = [
        {
            "type": "heading",
            "attrs": {"level": 1, "textAlign": "center", "blockId": str(uuid.uuid4())[:8]},
            "content": [{"type": "text", "text": title}],
        },
        {
            "type": "paragraph",
            "attrs": {"blockId": str(uuid.uuid4())[:8]},
            "content": [
                {"type": "text", "text": "Submitted To: "},
                {"type": "text", "text": audience or "The Head of Department, DoCSE, SVNIT Surat"},
            ],
        },
        {
            "type": "paragraph",
            "attrs": {"blockId": str(uuid.uuid4())[:8]},
            "content": [
                {"type": "text", "text": "Respected Sir / Madam,\n\nWe, the office bearers of "},
                {"type": "text", "text": club_name},
                {"type": "text", "text": ", respectfully submit this proposal for organizing "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}},
                {"type": "text", "text": " on "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_date", "label": "Event Date", "fieldType": "date"}},
                {"type": "text", "text": " at "},
                {"type": "fieldChip", "attrs": {"fieldName": "venue", "label": "Venue", "fieldType": "text"}},
                {"type": "text", "text": ". The objective of this session is to enrich student skills and promote technical excellence across the department."},
            ],
        },
    ]

    # Add Info / Summary Table
    table_rows = [
        [
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Event Title"}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}}]}]},
        ],
        [
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Date & Venue"}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "fieldChip", "attrs": {"fieldName": "event_date", "label": "Event Date", "fieldType": "date"}}, {"type": "text", "text": " at "}, {"type": "fieldChip", "attrs": {"fieldName": "venue", "label": "Venue", "fieldType": "text"}}]}]},
        ],
        [
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Lead Coordinator"}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "fieldChip", "attrs": {"fieldName": "coordinator_name", "label": "Coordinator", "fieldType": "text"}}]}]},
        ],
    ]
    if has_budget:
        table_rows.append([
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Estimated Outlay"}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "fieldChip", "attrs": {"fieldName": "estimated_budget", "label": "Budget", "fieldType": "money"}}]}]},
        ])

    blocks.append({
        "type": "table",
        "attrs": {"blockType": "infoTable", "blockId": str(uuid.uuid4())[:8]},
        "content": [{"type": "tableRow", "content": r} for r in table_rows],
    })

    # Official Wording Guard Placeholder
    blocks.append({
        "type": "paragraph",
        "attrs": {"blockId": str(uuid.uuid4())[:8]},
        "content": [
            {"type": "text", "text": "We request your kind permission and necessary administrative approval for smooth conduction of the event.\n\n[Add official wording here]"}
        ],
    })

    # Signatures
    blocks.append({
        "type": "signatureGrid",
        "attrs": {
            "columns": 3,
            "blockId": str(uuid.uuid4())[:8],
            "signatures": [
                {"label": "Student Coordinator", "designation": club_name},
                {"label": "Faculty Advisor", "designation": "DoCSE, SVNIT"},
                {"label": "Head of Department", "designation": "DoCSE, SVNIT"},
            ],
        },
    })

    editor_json = {"type": "doc", "content": blocks}
    return editor_json, fields, design_settings, title


def create_wizard_template(
    prompt: str,
    answers: dict[str, str],
    club_id: str,
    user_id: str,
    db: Session,
    numbering_series: str = "DOC",
) -> tuple[Template, TemplateVersion]:
    """Creates a new database Template and TemplateVersion directly from the wizard inputs."""
    club = db.query(Club).filter(Club.id == club_id).first()
    club_name = club.name if club else "ACM SVNIT"

    editor_json, fields, design_settings, title = build_wizard_template_spec(prompt, answers, club_name)

    # Compile initial DOCX
    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields,
        template_meta={"name": title, "category": "Official Event Documents", "numbering_series": numbering_series},
        club_slug=club.short_name.lower() if club and club.short_name else "acm",
        design_settings=design_settings,
    )

    # Save to storage
    storage = get_storage()
    slug = f"custom-{uuid.uuid4().hex[:8]}"
    dest_docx = storage.save(f"templates/{slug}_v1.docx", docx_bytes)

    tmpl = Template(
        id=str(uuid.uuid4()),
        club_id=club_id,
        slug=slug,
        name=title,
        description=f"Generated via Template Wizard from prompt: {prompt[:120]}",
        category="Official Event Documents",
        stage="pre_event",
        is_system=False,
        status="draft",
    )
    db.add(tmpl)
    db.flush()

    # Embed design_settings inside editor_json for persistence
    if isinstance(editor_json, dict):
        editor_json["design_settings"] = design_settings
        if "attrs" not in editor_json:
            editor_json["attrs"] = {}
        editor_json["attrs"]["design_settings"] = design_settings

    ver = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=tmpl.id,
        version_no=1,
        editor_json=editor_json,
        schema_yaml=schema_yaml,
        docx_storage_key=str(dest_docx),
        validation_report=report,
        created_by=user_id,
        change_note="Created via Template Wizard",
    )
    db.add(ver)
    db.flush()

    tmpl.current_version_id = ver.id
    db.commit()
    db.refresh(tmpl)
    db.refresh(ver)

    return tmpl, ver
