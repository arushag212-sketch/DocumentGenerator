"""Document Importer for SVNIT ClubDocs.

Supports:
1. Pasting existing letter/notice text -> detects variable parts and converts to TipTap editor JSON + proposed fields.
2. Uploading existing DOCX -> parses via python-docx (paragraphs, tables, bold/italic/underline, alignments), detects variables, and returns editor JSON + proposed fields + list of unsupported elements.
"""

from __future__ import annotations

import io
import re
import uuid
from typing import Any
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from server.app.core.template_generator import (
    sanitize_identifier,
    strip_pii_from_text,
)


DATE_REGEX = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{4})\b",
    re.IGNORECASE,
)
MONEY_REGEX = re.compile(
    r"\b(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)\b|\b([\d,]+)\s*(?:/-\s*|INR|Rupees)\b",
    re.IGNORECASE,
)
BRACKET_REGEX = re.compile(r"[\[<\{]([A-Za-z0-9 _\-\.]{2,40})[\]>\}]")
LABEL_REGEX = re.compile(r"^(Date|Venue|Place|Time|Amount|Budget|Subject|Coordinator|Chairperson|President):\s*(.+)$", re.IGNORECASE)


def detect_variable_candidates(text: str) -> list[dict[str, Any]]:
    """Detect variable expressions in plain text (dates, amounts, bracketed placeholders)."""
    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    # 1. Bracketed placeholders: [Event Name], <Date>, {Venue}
    for m in BRACKET_REGEX.finditer(text):
        raw_val = m.group(1).strip()
        key = sanitize_identifier(raw_val.lower().replace(" ", "_"))
        if key and key not in seen_keys:
            seen_keys.add(key)
            candidates.append({
                "key": key,
                "label": raw_val.title(),
                "type": "date" if "date" in key else "money" if any(k in key for k in ("budget", "amount", "cost")) else "text",
                "sample_value": m.group(0),
                "pattern": m.group(0),
            })

    # 2. Money amounts
    for m in MONEY_REGEX.finditer(text):
        amt = m.group(1) or m.group(2)
        raw_str = m.group(0).strip()
        key = "sanctioned_amount" if "amount" not in seen_keys else f"amount_{len(candidates) + 1}"
        if key not in seen_keys:
            seen_keys.add(key)
            candidates.append({
                "key": key,
                "label": "Sanctioned Amount",
                "type": "money",
                "sample_value": raw_str,
                "pattern": raw_str,
            })

    # 3. Dates
    for m in DATE_REGEX.finditer(text):
        raw_str = m.group(0).strip()
        key = "event_date" if "event_date" not in seen_keys else f"date_{len(candidates) + 1}"
        if key not in seen_keys:
            seen_keys.add(key)
            candidates.append({
                "key": key,
                "label": "Event Date",
                "type": "date",
                "sample_value": raw_str,
                "pattern": raw_str,
            })

    return candidates


def convert_text_to_tiptap_with_fields(
    raw_text: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Converts pasted plain text into TipTap document blocks with embedded field chips."""
    cleaned = strip_pii_from_text(raw_text.strip())
    candidates = detect_variable_candidates(cleaned)

    # Sort candidates by length descending to prevent partial replacement
    sorted_candidates = sorted(candidates, key=lambda c: len(c["pattern"]), reverse=True)

    paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]
    content_blocks: list[dict[str, Any]] = []

    for idx, p_text in enumerate(paragraphs):
        # Heading heuristic
        is_heading = idx == 0 and len(p_text) < 100 and not p_text.endswith(".")
        if is_heading:
            content_blocks.append({
                "type": "heading",
                "attrs": {"level": 1, "textAlign": "center", "blockId": str(uuid.uuid4())[:8]},
                "content": [{"type": "text", "text": p_text}],
            })
            continue

        # Segment paragraph text around detected variables
        inline_items: list[dict[str, Any]] = []
        remaining = p_text

        while remaining:
            earliest_match = None
            earliest_cand = None
            earliest_idx = len(remaining)

            for cand in sorted_candidates:
                pos = remaining.find(cand["pattern"])
                if pos != -1 and pos < earliest_idx:
                    earliest_idx = pos
                    earliest_cand = cand
                    earliest_match = cand["pattern"]

            if earliest_cand and earliest_match:
                prefix = remaining[:earliest_idx]
                if prefix:
                    inline_items.append({"type": "text", "text": prefix})
                inline_items.append({
                    "type": "fieldChip",
                    "attrs": {
                        "fieldName": earliest_cand["key"],
                        "label": earliest_cand["label"],
                        "fieldType": earliest_cand["type"],
                    },
                })
                remaining = remaining[earliest_idx + len(earliest_match):]
            else:
                inline_items.append({"type": "text", "text": remaining})
                break

        content_blocks.append({
            "type": "paragraph",
            "attrs": {"blockId": str(uuid.uuid4())[:8]},
            "content": inline_items,
        })

    fields = [
        {
            "key": c["key"],
            "label": c["label"],
            "type": c["type"],
            "required": True,
            "ask": f"Please provide the {c['label']}",
            "ai_suggested": True,
        }
        for c in candidates
    ]

    return {"type": "doc", "content": content_blocks}, fields, []


def convert_docx_to_tiptap_with_fields(
    docx_bytes: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Converts a DOCX binary file into TipTap editor JSON, proposed fields, and unsupported features report."""
    if hasattr(docx_bytes, "read"):
        docx_bytes.seek(0)
        doc = Document(docx_bytes)
    else:
        doc = Document(io.BytesIO(docx_bytes))
    unsupported_elements: list[str] = []

    # Detect unsupported DOCX elements
    xml_str = doc._body._element.xml
    if "<w:drawing" in xml_str or "<wp:inline" in xml_str:
        unsupported_elements.append("Embedded inline Vector Shapes / SmartArt (simplified to image placeholders)")
    if "<m:oMath" in xml_str:
        unsupported_elements.append("Office Math Equations (converted to raw text representation)")
    if "<w:vmlFrame" in xml_str:
        unsupported_elements.append("Legacy Word VML Frames")

    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    candidates = detect_variable_candidates(full_text)
    sorted_candidates = sorted(candidates, key=lambda c: len(c["pattern"]), reverse=True)

    content_blocks: list[dict[str, Any]] = []

    # 1. Process Paragraphs
    for p in doc.paragraphs:
        p_text = p.text.strip()
        if not p_text:
            continue

        align_str = "left"
        if p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            align_str = "center"
        elif p.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            align_str = "right"
        elif p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
            align_str = "justify"

        # Check if heading style
        style_name = p.style.name.lower() if p.style else ""
        if "heading 1" in style_name or "title" in style_name:
            content_blocks.append({
                "type": "heading",
                "attrs": {"level": 1, "textAlign": align_str, "blockId": str(uuid.uuid4())[:8]},
                "content": [{"type": "text", "text": p_text}],
            })
            continue
        elif "heading 2" in style_name:
            content_blocks.append({
                "type": "heading",
                "attrs": {"level": 2, "textAlign": align_str, "blockId": str(uuid.uuid4())[:8]},
                "content": [{"type": "text", "text": p_text}],
            })
            continue

        # Inline runs
        inline_items: list[dict[str, Any]] = []
        for run in p.runs:
            r_text = run.text
            if not r_text:
                continue

            marks = []
            if run.bold:
                marks.append({"type": "bold"})
            if run.italic:
                marks.append({"type": "italic"})
            if run.underline:
                marks.append({"type": "underline"})

            # Check if run matches any variable candidate
            matched = False
            for cand in sorted_candidates:
                if cand["pattern"] == r_text.strip():
                    item: dict[str, Any] = {
                        "type": "fieldChip",
                        "attrs": {
                            "fieldName": cand["key"],
                            "label": cand["label"],
                            "fieldType": cand["type"],
                        },
                    }
                    inline_items.append(item)
                    matched = True
                    break

            if not matched:
                item = {"type": "text", "text": r_text}
                if marks:
                    item["marks"] = marks
                inline_items.append(item)

        if inline_items:
            content_blocks.append({
                "type": "paragraph",
                "attrs": {"textAlign": align_str, "blockId": str(uuid.uuid4())[:8]},
                "content": inline_items,
            })

    # 2. Process Tables
    for tbl in doc.tables:
        rows_data = []
        for r_idx, row in enumerate(tbl.rows):
            cells_data = []
            is_header_row = (r_idx == 0)
            cell_type = "tableHeader" if is_header_row else "tableCell"

            for cell in row.cells:
                cell_p_nodes = []
                for cp in cell.paragraphs:
                    cp_text = cp.text.strip()
                    if not cp_text:
                        continue
                    cell_p_nodes.append({
                        "type": "paragraph",
                        "content": [{"type": "text", "text": cp_text}],
                    })
                if not cell_p_nodes:
                    cell_p_nodes = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]

                cells_data.append({
                    "type": cell_type,
                    "content": cell_p_nodes,
                })

            rows_data.append({
                "type": "tableRow",
                "content": cells_data,
            })

        if rows_data:
            content_blocks.append({
                "type": "table",
                "attrs": {"blockType": "genericTable", "blockId": str(uuid.uuid4())[:8]},
                "content": rows_data,
            })

    fields = [
        {
            "key": c["key"],
            "label": c["label"],
            "type": c["type"],
            "required": True,
            "ask": f"Please provide {c['label']}",
            "ai_suggested": True,
        }
        for c in candidates
    ]

    return {"type": "doc", "content": content_blocks}, fields, unsupported_elements
