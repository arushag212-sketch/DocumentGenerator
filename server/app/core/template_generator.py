"""AI-powered plain text template generator with schema validation, security sanitization, and PII prevention."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docgen.llm import (
    AIBadResponseError,
    AIAuthenticationError,
    AIQuotaError,
    AIServiceError,
    AITimeoutError,
    LLMClient,
    get_llm_client,
)
from server.app.core.rate_limit import check_rate_limit
from server.app.core.storage import LocalDiskStorage, get_storage, require_local_storage
from server.app.core.tenancy import get_asset_for_club, validate_letterhead_asset_refs
from server.app.core.template_compiler import (
    TemplateCompiler,
    escape_jinja_delimiters,
    validate_identifier,
)
from server.app.models import (
    AIRequest,
    Asset,
    Club,
    Letterhead,
    NumberingSeries,
    Template,
    TemplateVersion,
)


ALLOWED_BLOCK_TYPES = {
    "heading",
    "paragraph",
    "infoTable",
    "repeatingTable",
    "signatureGrid",
    "pageBreak",
    "table",
    "tableRow",
    "tableCell",
    "tableHeader",
}

ALLOWED_FIELD_TYPES = {
    "text",
    "longtext",
    "int",
    "money",
    "date",
    "date_range",
    "time_range",
    "enum",
    "person_ref",
    "table",
}

OFFICIAL_WORDING_TRIGGERS = [
    "sanction",
    "approval",
    "certification",
    "certify",
    "undertaking",
    "undertake",
    "declaration",
    "declare",
    "recommended",
    "recommend",
    "approved",
    "approve",
]

# Regex patterns for redacting sensitive PII before prompt is constructed
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
PHONE_REGEX = re.compile(r"\b(?:\+91|91|0)?[6-9]\d{9}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
BANK_ACC_REGEX = re.compile(r"\b\d{9,18}\b")
IFSC_REGEX = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)


class TemplateFieldSpec(BaseModel):
    key: str
    type: str = "text"
    required: bool = True
    ask: str
    defer_ok: bool = False
    sensitive: bool = False
    columns: Optional[list[dict[str, Any]]] = None
    ai_suggested: bool = True


class TemplateBlockSpec(BaseModel):
    type: str
    attrs: Optional[dict[str, Any]] = None
    content: Optional[list[dict[str, Any]]] = None
    ai_suggested: bool = True


class TemplateDesignSpec(BaseModel):
    """Page-level look; keys match the editor's DesignSettings."""

    orientation: Optional[Literal["portrait", "landscape"]] = None
    pageBorder: Optional[Literal["none", "single", "double"]] = None
    borderColor: Optional[str] = None
    headingColor: Optional[str] = None
    textColor: Optional[str] = None
    fontFamily: Optional[str] = None
    headingFontFamily: Optional[str] = None
    margins: Optional[Literal["normal", "compact", "wide"]] = None
    layout: Optional[Literal["document", "certificate"]] = None


class TemplateSpec(BaseModel):
    name: str
    category: str = "Official Event Documents"
    stage: str = "custom"
    description: str
    fields: list[TemplateFieldSpec]
    blocks: list[TemplateBlockSpec]
    design: Optional[TemplateDesignSpec] = None


class _ModelFieldSpec(BaseModel):
    key: str
    type: str = "text"
    required: bool = True
    ask: str
    defer_ok: bool = False
    sensitive: bool = False
    columns_json: Optional[str] = Field(
        default=None, description='For type "table": the columns list serialized as a JSON string.'
    )


class _ModelBlockSpec(BaseModel):
    type: str
    block_json: str = Field(description="The complete block object (type, attrs, content) serialized as a JSON string.")


class _ModelTemplateSpec(BaseModel):
    name: str
    category: str = "Official Event Documents"
    stage: str = "custom"
    description: str
    fields: list[_ModelFieldSpec]
    blocks: list[_ModelBlockSpec]
    design: Optional[TemplateDesignSpec] = None


# Schema sent to the model. Block bodies and table columns travel as JSON strings because
# structured-output decoding returns `{}` for free-form objects (attrs, content items).
TEMPLATE_SPEC_MODEL_SCHEMA = _ModelTemplateSpec.model_json_schema()

MODEL_ENCODING_NOTE = """OUTPUT ENCODING (required by the response schema):
- Each blocks[] item is {"type": "<block type>", "block_json": "<the complete block object from the rules above, serialized as a JSON string>"}.
- A field of type "table" carries its columns as "columns_json": "<the columns list serialized as a JSON string>".
Everything else is plain JSON as shown in the example."""

_TABLE_ATTR_KEYS = ("title", "rows", "listVariable", "itemAlias", "columns", "hasTotal", "totalLabel", "totalField", "totalVarName", "signatures")


def _decode_model_spec(raw: Any) -> Any:
    """Expand `block_json` / `columns_json` strings from the model into TemplateSpec shape."""
    if not isinstance(raw, dict):
        return raw
    out = dict(raw)
    blocks = []
    for block in raw.get("blocks") or []:
        if isinstance(block, dict) and "block_json" in block:
            encoded = block["block_json"]
            try:
                decoded = json.loads(encoded) if isinstance(encoded, str) else encoded
            except (TypeError, ValueError):
                decoded = None
            if not isinstance(decoded, dict):
                continue
            decoded.setdefault("type", block.get("type"))
            # Table blocks keep their settings in attrs; accept them at the top level too.
            if decoded.get("type") in ("infoTable", "repeatingTable", "signatureGrid"):
                attrs = dict(decoded.get("attrs") or {})
                for k in _TABLE_ATTR_KEYS:
                    if k in decoded and k not in attrs:
                        attrs[k] = decoded.pop(k)
                decoded["attrs"] = attrs
            block = decoded
        blocks.append(block)
    out["blocks"] = blocks
    fields = []
    for field in raw.get("fields") or []:
        if isinstance(field, dict) and "columns_json" in field:
            field = dict(field)
            encoded = field.pop("columns_json")
            try:
                cols = json.loads(encoded) if isinstance(encoded, str) and encoded.strip() else None
            except (TypeError, ValueError):
                cols = None
            if isinstance(cols, list) and not field.get("columns"):
                field["columns"] = cols
        fields.append(field)
    out["fields"] = fields
    return out


def strip_pii_from_text(text: str) -> str:
    """Redact personal financial & contact data (PAN, phone, bank account, IFSC, email) from input."""
    s = PAN_REGEX.sub("[REDACTED_PAN]", text)
    s = PHONE_REGEX.sub("[REDACTED_PHONE]", s)
    s = EMAIL_REGEX.sub("[REDACTED_EMAIL]", s)
    s = IFSC_REGEX.sub("[REDACTED_IFSC]", s)
    s = BANK_ACC_REGEX.sub("[REDACTED_ACCOUNT]", s)
    return s


def sanitize_identifier(name: str) -> str:
    """Normalize user input or field label into a safe snake_case identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "field"


def normalize_text_for_match(t: str) -> str:
    """Normalize text by lowercasing and stripping punctuation and excess whitespace."""
    clean = re.sub(r"[^\w\s]", "", t.lower())
    return re.sub(r"\s+", " ", clean).strip()


def derive_unique_series_key(
    template_name: str,
    club_id: str,
    db: Session,
    exclude_template_id: Optional[str] = None,
) -> str:
    """Derive unique numbering series key for a template within a club.

    If collision occurs with an existing series in the club or another template in the club,
    append 2, 3, etc. Never let two templates share a counter.
    """
    words = re.findall(r"[A-Za-z]+", template_name)
    if len(words) >= 2:
        base = "".join(w[0] for w in words[:4]).upper()
    elif words:
        base = words[0][:4].upper()
    else:
        base = "DOC"

    base = base[:8]

    used_series: set[str] = set()

    # 1. From numbering_series table in this club
    existing_ns = db.query(NumberingSeries.key).filter(NumberingSeries.club_id == club_id).all()
    for row in existing_ns:
        used_series.add(str(row[0]).upper())

    # 2. From other templates in the club and system templates
    tmpls = db.query(Template).filter(
        (Template.club_id == club_id) | (Template.is_system == True)
    )
    if exclude_template_id:
        tmpls = tmpls.filter(Template.id != exclude_template_id)

    for t in tmpls.all():
        latest_ver = (
            db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == t.id)
            .order_by(TemplateVersion.version_no.desc())
            .first()
        )
        if latest_ver and latest_ver.schema_yaml:
            try:
                s = yaml.safe_load(latest_ver.schema_yaml)
                if isinstance(s, dict):
                    ser = s.get("numbering", {}).get("series")
                    if ser:
                        used_series.add(str(ser).upper())
            except Exception:
                pass

    if base not in used_series:
        return base

    suffix = 2
    while f"{base}{suffix}" in used_series:
        suffix += 1
    return f"{base}{suffix}"


ALLOWED_DESIGN_FONTS = {"Tinos", "Merriweather", "Roboto", "Open Sans", "Montserrat", "Playfair Display", "Roboto Mono"}
_HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _sanitize_design(design: Optional[TemplateDesignSpec]) -> Optional[dict[str, Any]]:
    """Keep only well-formed design values (hex colours, known fonts)."""
    if design is None:
        return None
    out: dict[str, Any] = {}
    for key, value in design.model_dump(exclude_none=True).items():
        if key.endswith("Color"):
            if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
                out[key] = "#" + value.strip().lstrip("#").upper()
        elif key in ("fontFamily", "headingFontFamily"):
            if value in ALLOWED_DESIGN_FONTS:
                out[key] = value
        else:
            out[key] = value
    return out or None


def sanitize_template_spec(spec: TemplateSpec, original_prompt: str) -> TemplateSpec:
    """Strictly sanitize, validate identifiers, escape Jinja delimiters, and enforce official wording rules."""
    # 1. Delimiter escaping on metadata
    spec.name = escape_jinja_delimiters(spec.name.strip())
    spec.description = escape_jinja_delimiters(spec.description.strip())
    spec.category = escape_jinja_delimiters(spec.category.strip())

    # 2. Validate fields
    seen_field_keys: set[str] = set()
    declared_fields_by_key: dict[str, TemplateFieldSpec] = {}

    for f in spec.fields:
        validate_identifier(f.key, "Field key")
        if f.key in seen_field_keys:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Duplicate field key '{f.key}' generated by AI.",
            )
        seen_field_keys.add(f.key)
        declared_fields_by_key[f.key] = f

        if f.type not in ALLOWED_FIELD_TYPES:
            f.type = "text"

        f.ask = escape_jinja_delimiters(f.ask)
        f.ai_suggested = True

        if f.columns:
            seen_cols = set()
            for col in f.columns:
                ckey = col.get("key")
                if ckey:
                    validate_identifier(ckey, f"Column key in field '{f.key}'")
                    if ckey in seen_cols:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Duplicate column key '{ckey}' generated by AI.",
                        )
                    seen_cols.add(ckey)
                if col.get("label"):
                    col["label"] = escape_jinja_delimiters(str(col["label"]))

    # Helper: Ensure referenced field is declared; auto-declare missing as "AI-suggested"
    def check_and_ensure_field(field_key: str, suggested_type: str = "text", ask_label: Optional[str] = None) -> None:
        if field_key not in declared_fields_by_key:
            validate_identifier(field_key, "Auto-declared field key")
            new_f = TemplateFieldSpec(
                key=field_key,
                type=suggested_type,
                required=True,
                ask=f"Enter {ask_label or field_key.replace('_', ' ').title()}",
                defer_ok=False,
                sensitive=False,
                ai_suggested=True,
            )
            spec.fields.append(new_f)
            declared_fields_by_key[field_key] = new_f

    # 3. Validate blocks and escape all user text
    for block in spec.blocks:
        b_type = block.type
        if b_type not in ALLOWED_BLOCK_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid block type '{b_type}'. Allowed types: {list(ALLOWED_BLOCK_TYPES)}",
            )
        block.ai_suggested = True
        attrs = block.attrs or {}
        attrs["ai_suggested"] = True
        block.attrs = attrs

        if b_type == "heading":
            _sanitize_inline_content(block.content or [])
        elif b_type == "paragraph":
            _sanitize_inline_content(block.content or [])
            # Validate every fieldChip references a declared field
            for node in (block.content or []):
                if node.get("type") == "fieldChip":
                    fn = node.get("attrs", {}).get("fieldName")
                    if fn:
                        check_and_ensure_field(fn, node.get("attrs", {}).get("fieldType", "text"), node.get("attrs", {}).get("label"))
        elif b_type == "infoTable":
            if attrs.get("title"):
                attrs["title"] = escape_jinja_delimiters(str(attrs["title"]))
            rows = attrs.get("rows") or []
            for r in rows:
                if r.get("label"):
                    r["label"] = escape_jinja_delimiters(str(r["label"]))
                f_name = r.get("field") or r.get("key")
                if f_name:
                    validate_identifier(f_name, "InfoTable field")
                    check_and_ensure_field(f_name, "text", r.get("label"))
        elif b_type == "repeatingTable":
            list_var = attrs.get("listVariable")
            if list_var:
                validate_identifier(list_var, "RepeatingTable listVariable")
                cols = attrs.get("columns") or []
                if list_var not in declared_fields_by_key:
                    check_and_ensure_field(list_var, "table")
                    declared_fields_by_key[list_var].columns = cols
                else:
                    if not declared_fields_by_key[list_var].columns:
                        declared_fields_by_key[list_var].columns = cols
            item_alias = attrs.get("itemAlias")
            if item_alias:
                validate_identifier(item_alias, "RepeatingTable itemAlias")
            tot_var = attrs.get("totalVarName")
            if tot_var:
                validate_identifier(tot_var, "RepeatingTable totalVarName")
            if attrs.get("totalLabel"):
                attrs["totalLabel"] = escape_jinja_delimiters(str(attrs["totalLabel"]))
            cols = attrs.get("columns") or []
            seen_table_cols = set()
            for c in cols:
                ckey = c.get("key")
                if ckey:
                    validate_identifier(ckey, "RepeatingTable column key")
                    if ckey in seen_table_cols:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Duplicate column key '{ckey}' in repeatingTable.",
                        )
                    seen_table_cols.add(ckey)
                if c.get("label"):
                    c["label"] = escape_jinja_delimiters(str(c["label"]))
        elif b_type == "signatureGrid":
            signs = attrs.get("signatures") or []
            for s in signs:
                if s.get("label"):
                    s["label"] = escape_jinja_delimiters(str(s["label"]))
                if s.get("designation"):
                    s["designation"] = escape_jinja_delimiters(str(s["designation"]))
                if s.get("role"):
                    s["role"] = escape_jinja_delimiters(str(s["role"]))

    # 4. Enforce Official Wording Rule:
    # Compare each paragraph in the AI output matching official triggers against user's own sentences.
    # Anything else becomes the "Add official wording here" placeholder.
    _enforce_official_wording(spec, original_prompt)

    return spec


def _sanitize_inline_content(content: list[dict[str, Any]]) -> None:
    for node in content:
        n_type = node.get("type")
        if n_type == "text" and "text" in node:
            node["text"] = escape_jinja_delimiters(node["text"])
        elif n_type == "fieldChip":
            attrs = node.get("attrs", {})
            fn = attrs.get("fieldName")
            if fn:
                validate_identifier(fn, "FieldChip fieldName")
            if attrs.get("label"):
                attrs["label"] = escape_jinja_delimiters(str(attrs["label"]))
        if "content" in node and isinstance(node["content"], list):
            _sanitize_inline_content(node["content"])


RECOGNITION_WORDS = ("secured", "participated", "participation", "awarded", "won", "achieved", "achievement",
                     "completed", "position", "place", "rank", "appreciation", "recognition", "volunteer")
# Standard certificate openers that state no fact of their own.
CERTIFICATE_LEAD_INS = {
    normalize_text_for_match(s)
    for s in ("This is to certify that", "This is to certify that Mr./Ms.", "This certificate is proudly presented to")
}
INSTITUTIONAL_TRIGGERS = [t for t in OFFICIAL_WORDING_TRIGGERS if t not in ("certify", "certification")]


def _is_recognition_statement(block: TemplateBlockSpec, text_lower: str) -> bool:
    """A certificate line ("This is to certify that <recipient> secured <position> in <event>").

    Its facts all come from declared fields (chips), and it uses only "certify" wording, never
    approval/sanction/undertaking/declaration language, so it does not invent an official decision.
    """
    if normalize_text_for_match(text_lower) in CERTIFICATE_LEAD_INS:
        return True
    has_chip = any(n.get("type") == "fieldChip" for n in (block.content or []))
    if not has_chip:
        return False
    if any(trig in text_lower for trig in INSTITUTIONAL_TRIGGERS):
        return False
    return any(word in text_lower for word in RECOGNITION_WORDS)


def _enforce_official_wording(spec: TemplateSpec, prompt: str) -> None:
    """Enforce that official wording (approvals, undertakings, certifications) is not invented.

    Only text the user wrote verbatim may stay; compare each paragraph in the AI output that
    matches an official trigger (sanction, approval, certification, undertaking, declaration,
    recommended, approved) against the user's own sentences (exact or near-exact match).
    Anything else becomes the "Add official wording here" placeholder.
    """
    user_raw_sentences = [s.strip() for s in re.split(r"[.!?\n;]+", prompt) if len(s.strip()) >= 5]
    user_norm_sentences = [normalize_text_for_match(s) for s in user_raw_sentences if normalize_text_for_match(s)]
    user_full_norm = normalize_text_for_match(prompt)

    prompt_lower = prompt.lower()
    spec_triggers_needed = any(trig in prompt_lower for trig in OFFICIAL_WORDING_TRIGGERS) or any(
        trig in spec.name.lower() or trig in spec.description.lower() for trig in OFFICIAL_WORDING_TRIGGERS
    )

    found_official_block = False

    for block in spec.blocks:
        if block.type == "paragraph":
            p_text = "".join(n.get("text", "") for n in (block.content or []) if n.get("type") == "text").strip()
            p_lower = p_text.lower()

            is_official = any(trig in p_lower for trig in OFFICIAL_WORDING_TRIGGERS)
            if is_official and _is_recognition_statement(block, p_lower):
                found_official_block = True
                continue
            if is_official:
                p_norm = normalize_text_for_match(p_text)
                exact_in_prompt = p_norm in user_full_norm
                near_match = False
                if not exact_in_prompt:
                    for u_sent in user_norm_sentences:
                        if len(u_sent) >= 10 and len(p_norm) >= 10:
                            ratio = SequenceMatcher(None, u_sent, p_norm).ratio()
                            if ratio >= 0.88:
                                near_match = True
                                break

                if exact_in_prompt or near_match:
                    found_official_block = True
                else:
                    block.content = [
                        {
                            "type": "text",
                            "text": "Add official wording here",
                        }
                    ]
                    block.attrs = block.attrs or {}
                    block.attrs["official_wording_required"] = True
                    block.attrs["ai_suggested"] = True
                    found_official_block = True

    if spec_triggers_needed and not found_official_block:
        placeholder_block = TemplateBlockSpec(
            type="paragraph",
            attrs={"textAlign": "left", "official_wording_required": True, "ai_suggested": True},
            content=[{"type": "text", "text": "Add official wording here"}],
            ai_suggested=True,
        )
        insert_idx = len(spec.blocks)
        for i, b in enumerate(spec.blocks):
            if b.type == "signatureGrid":
                insert_idx = i
                break
        spec.blocks.insert(insert_idx, placeholder_block)


def resolve_club_logo_by_text(club_id: str, text: str, db: Session) -> dict[str, Any]:
    """Resolve logo from text (e.g. 'use the ACM logo on the left') to an asset in the club's library."""
    text_lower = text.lower()
    club_assets = db.query(Asset).filter(Asset.club_id == club_id).all()
    system_assets = db.query(Asset).filter(Asset.is_system == True, Asset.club_id.is_(None)).all()
    all_assets = club_assets + system_assets

    logo_assets = [
        a for a in all_assets
        if a.kind in ("logo", "letterhead") or "logo" in a.filename.lower() or "acm" in a.filename.lower() or "img" in a.filename.lower()
    ]

    matched: list[Asset] = []
    if "acm" in text_lower:
        club_acm = [a for a in club_assets if "acm" in a.filename.lower()]
        if club_acm:
            matched = club_acm
        else:
            matched = [a for a in logo_assets if "acm" in a.filename.lower()]
            if not matched:
                matched = [a for a in logo_assets if "permission_page1_img2" in a.filename]

    if not matched:
        m = re.search(r"(\w+)\s+logo", text_lower)
        if m:
            keyword = m.group(1)
            matched = [a for a in logo_assets if keyword in a.filename.lower()]

    if len(matched) == 1:
        chosen = matched[0]
        return {
            "status": "resolved",
            "asset_id": chosen.id,
            "filename": chosen.filename,
            "url": f"/api/v1/assets/{chosen.id}/content" if chosen.club_id else f"/assets/{chosen.filename}",
        }
    elif len(matched) > 1:
        return {
            "status": "ambiguous",
            "candidates": [
                {
                    "asset_id": a.id,
                    "filename": a.filename,
                    "url": f"/api/v1/assets/{a.id}/content" if a.club_id else f"/assets/{a.filename}",
                }
                for a in matched
            ],
        }
    else:
        return {
            "status": "not_found",
            "message": "No matching logo found in club asset library. Please pick from your asset library.",
        }


SYSTEM_PROMPT_TEMPLATE = """You are the official SVNIT Surat Document Generator AI Template Architect.
Your task is to convert the user's natural language template request into a strictly structured TemplateSpec JSON adhering to the provided schema.

ALLOWED FIELD TYPES (fields[].type):
- "text": Single-line text string (e.g. event_name, venue, designation)
- "longtext": Multi-line descriptive text (e.g. description, objectives)
- "int": Integer counts (e.g. expected_participants, slots)
- "money": Monetary amount in INR (e.g. amount, budget_total)
- "date": Date in YYYY-MM-DD or DD/MM/YYYY (e.g. event_date)
- "date_range": Date range string (e.g. event_dates)
- "time_range": Time range string (e.g. event_timing)
- "enum": Selection from fixed choices
- "person_ref": Person reference with roles and designation
- "table": Tabular repeating collection (must define columns: [{key, label, align}])

FIELD SPECIFICATION (fields[]):
Every declared field must contain:
- "key": Unique identifier matching ^[a-z][a-z0-9_]{0,39}$ (lowercase, no reserved keywords, no dunder names).
- "type": One of the allowed types above.
- "required": Boolean (true for essential inputs, false if optional).
- "ask": Clear user prompt (e.g. "Enter confirmed event name").
- "defer_ok": Boolean (true if fillable at later stage, false if needed immediately).
- "sensitive": Boolean (true for personal PII like mobile, bank details, PAN).
- "ai_suggested": Boolean (always true for AI-generated fields).
- "columns": Required if type="table", list of {key, label, align}.

ALLOWED BLOCK TYPES (blocks[]):
1. "heading": {type: "heading", attrs: {level: 1|2|3, textAlign: "left"|"center"|"right"}, content: [{type: "text", text: "..."}]}
2. "paragraph": {type: "paragraph", attrs: {textAlign: "left"|"center"|"justify"}, content: [{type: "text", text: "..."}, {type: "fieldChip", attrs: {fieldName: "declared_field_key", label: "Field Label", fieldType: "text"}}]}
3. "infoTable": {type: "infoTable", attrs: {title: "Overview", rows: [{label: "Label", field: "declared_field_key"}]}}
4. "repeatingTable": {type: "repeatingTable", attrs: {listVariable: "declared_table_key", itemAlias: "item", columns: [{key: "col_key", label: "Column Title", align: "left"|"center"|"right"}], hasTotal: true|false, totalLabel: "Total Amount", totalField: "col_key", totalVarName: "total_var"}}
5. "signatureGrid": {type: "signatureGrid", attrs: {columns: 2|3|4, signatures: [{label: "Role", designation: "Club / Department"}]}}
6. "pageBreak": {type: "pageBreak"}

PAGE DESIGN (optional top-level "design" object):
{"orientation": "portrait"|"landscape", "pageBorder": "none"|"single"|"double", "borderColor": "#RRGGBB",
 "headingColor": "#RRGGBB", "textColor": "#RRGGBB", "fontFamily": FONT, "headingFontFamily": FONT, "margins": "normal"|"compact"|"wide",
 "layout": "document"|"certificate"}
FONT is one of: Tinos, Merriweather, Roboto, Open Sans, Montserrat, Playfair Display.
Honour colours and borders the user asks for (gold = #B8860B, silver = #8A8D91, navy = #1E3A8A, maroon = #7B1E2B).

CERTIFICATES, AWARDS AND APPRECIATION LETTERS:
- design: layout "certificate", orientation "landscape", pageBorder "double", borderColor from the request (default #B8860B), headingFontFamily "Playfair Display", margins "wide".
- Layout, all centred: small heading with the organising club/event; large level-1 title (e.g. "CERTIFICATE OF ACHIEVEMENT" or "CERTIFICATE OF PARTICIPATION");
  paragraph "This is to certify that"; level-2 heading containing ONLY the recipient_name fieldChip;
  a paragraph like "has secured <position chip> in <event_name chip> organised by <organiser chip> on <award_date chip>.";
  then a signatureGrid with exactly the number of signatories requested (e.g. three judges -> 3 signatures labelled "Judge").
- Names, positions, events and dates given in the request are DATA for the document: declare them as fields
  (recipient_name, position, event_name, award_date, ...) and reference them with fieldChips; never type them into text runs.

CRITICAL RULES:
- Put fieldChip references, infoTable row fields, and repeatingTable listVariables ONLY for fields explicitly declared in fields[].
- IDENTIFIERS: All keys, listVariables, itemAliases, column keys, and totalVarNames must match ^[a-z][a-z0-9_]{0,39}$. Never use reserved Python/Jinja keywords or dunder names.
- DELIMITERS: NEVER emit Jinja delimiters ({{, }}, {%, %}) in plain text runs. All variables must be fieldChip nodes or structured table references.
- OFFICIAL WORDING RULE: NEVER invent official sanction, approval, certification, or undertaking sentences. If requested and not supplied verbatim by the user, insert a paragraph with exact text "Add official wording here".

COMPLETE EXAMPLE SPEC:
{
  "name": "Equipment Requisition Form",
  "category": "Official Event Documents",
  "stage": "custom",
  "description": "Requisition note for borrowing laboratory and AV equipment",
  "fields": [
    {"key": "event_name", "type": "text", "required": true, "ask": "Enter event name", "defer_ok": false, "sensitive": false, "ai_suggested": true},
    {"key": "event_date", "type": "date", "required": true, "ask": "Enter requisition date", "defer_ok": false, "sensitive": false, "ai_suggested": true},
    {"key": "equipment_items", "type": "table", "required": true, "ask": "List equipment items", "defer_ok": false, "sensitive": false, "ai_suggested": true,
     "columns": [
       {"key": "item_name", "label": "Item Description", "align": "left"},
       {"key": "quantity", "label": "Quantity", "align": "center"}
     ]}
  ],
  "blocks": [
    {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": "LABORATORY EQUIPMENT REQUISITION"}]},
    {"type": "paragraph", "attrs": {"textAlign": "left"}, "content": [
      {"type": "text", "text": "This requisition is submitted for "},
      {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}},
      {"type": "text", "text": " scheduled on "},
      {"type": "fieldChip", "attrs": {"fieldName": "event_date", "label": "Event Date", "fieldType": "date"}},
      {"type": "text", "text": "."}
    ]},
    {"type": "infoTable", "attrs": {"title": "Session Overview", "rows": [
      {"label": "Activity Name", "field": "event_name"},
      {"label": "Required On", "field": "event_date"}
    ]}},
    {"type": "repeatingTable", "attrs": {
      "listVariable": "equipment_items",
      "itemAlias": "eq",
      "columns": [
        {"key": "item_name", "label": "Item Description", "align": "left"},
        {"key": "quantity", "label": "Quantity", "align": "center"}
      ],
      "hasTotal": false
    }},
    {"type": "signatureGrid", "attrs": {
      "columns": 2,
      "signatures": [
        {"label": "Student Secretary", "designation": "ACM Chapter"},
        {"label": "Faculty Convener", "designation": "SVNIT Surat"}
      ]
    }}
  ]
}
"""


def generate_draft_template(
    description: str,
    club_id: str,
    user_id: str,
    db: Session,
    llm_client: Optional[LLMClient] = None,
) -> tuple[Template, TemplateVersion, dict[str, Any]]:
    """Generate a club draft template from plain text with LLM and strict validation."""
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # 1. Rate limiting
    check_rate_limit(f"ai_user:{user_id}", max_requests=10, window_seconds=60, db=db)
    check_rate_limit(f"ai_club:{club_id}", max_requests=20, window_seconds=60, db=db)

    # 2. Check LLM client availability
    client = llm_client or get_llm_client()
    if not client.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI drafting is unavailable; build the template manually in the editor",
        )

    # 3. PII strip and Prompt Injection Sanitization
    cleaned_desc = strip_pii_from_text(description.strip())
    if not cleaned_desc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template description cannot be empty.",
        )

    # 4. Construct prompt and schema
    schema = TEMPLATE_SPEC_MODEL_SCHEMA
    full_prompt = (
        f"{SYSTEM_PROMPT_TEMPLATE}\n{MODEL_ENCODING_NOTE}\n\n"
        f"USER TEMPLATE REQUEST:\n{cleaned_desc}\n\n"
        f"Generate the TemplateSpec JSON:"
    )

    # 5. Call LLM with 1 retry on schema validation failure
    try:
        raw_json = client.generate_json(full_prompt, schema)
    except AIServiceError as ai_err:
        err_code = status.HTTP_503_SERVICE_UNAVAILABLE if isinstance(ai_err, AIAuthenticationError) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=err_code,
            detail=str(ai_err),
        )

    spec: Optional[TemplateSpec] = None

    try:
        spec = TemplateSpec.model_validate(_decode_model_spec(raw_json))
        if not spec.blocks:
            raise ValueError("blocks must contain at least one block with content")
    except Exception as first_err:
        retry_prompt = (
            f"{full_prompt}\n\n"
            f"NOTE: Your previous output failed schema validation with error: {str(first_err)}.\n"
            f"Ensure all required fields (name, category, description, fields, blocks) are present and conform to schema. Return corrected JSON:"
        )
        try:
            retry_json = client.generate_json(retry_prompt, schema)
        except AIServiceError as ai_err:
            err_code = status.HTTP_503_SERVICE_UNAVAILABLE if isinstance(ai_err, AIAuthenticationError) else status.HTTP_502_BAD_GATEWAY
            raise HTTPException(
                status_code=err_code,
                detail=str(ai_err),
            )

        try:
            spec = TemplateSpec.model_validate(_decode_model_spec(retry_json))
        except Exception as second_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"AI template generation failed schema validation: {str(second_err)}",
            )

    # 6. Strict sanitization, whitelist validation, official wording enforcement
    try:
        spec = sanitize_template_spec(spec, description)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Template spec failed validation: {str(ve)}",
        )

    # 7. Resolve logo by text if mentioned
    logo_res = resolve_club_logo_by_text(club_id, description, db)

    # 8. Log to ai_requests table with real token usage metadata when present
    prompt_hash = hashlib.sha256(cleaned_desc.encode("utf-8")).hexdigest()
    usage = getattr(client, "last_usage_metadata", None) or {}
    tokens_in = usage.get("tokens_in")
    if tokens_in is None:
        tokens_in = usage.get("promptTokenCount")
    tokens_out = usage.get("tokens_out")
    if tokens_out is None:
        tokens_out = usage.get("candidatesTokenCount")
    usage_estimated = bool(usage.get("usage_estimated", True if (tokens_in is None or tokens_out is None) else False))

    ai_log = AIRequest(
        club_id=club_id,
        user_id=user_id,
        purpose="template_draft",
        model=client.model_name,
        prompt_hash=prompt_hash,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        usage_estimated=usage_estimated,
    )
    db.add(ai_log)
    db.flush()

    # 9. Create draft Template & TemplateVersion in database
    club = db.query(Club).filter(Club.id == club_id).first()
    club_slug = club.slug if club else "custom"

    # Derive unique numbering series (never collision within club)
    series = derive_unique_series_key(spec.name, club_id, db)

    tmpl = Template(
        club_id=club_id,
        name=spec.name,
        slug=f"custom-{uuid.uuid4().hex[:8]}",
        category=spec.category,
        stage=spec.stage or "custom",
        description=spec.description,
        status="draft",
        is_system=False,
    )
    db.add(tmpl)
    db.flush()

    # Prepare editor_json with doc container
    editor_json = {
        "type": "doc",
        "content": [b.model_dump(exclude_none=True) for b in spec.blocks],
    }
    design_settings = _sanitize_design(spec.design)
    if design_settings:
        editor_json["design_settings"] = design_settings
    fields_list = [f.model_dump(exclude_none=True) for f in spec.fields]

    storage_templates_dir = local_storage.base_dir / "templates"
    storage_templates_dir.mkdir(parents=True, exist_ok=True)
    dest_docx = storage_templates_dir / f"{tmpl.id}_v1.docx"

    # Resolve letterhead if logo resolved
    letterhead_id = None
    letterhead_cfg = {}
    if logo_res.get("status") == "resolved" and logo_res.get("asset_id"):
        lh = db.query(Letterhead).filter(Letterhead.club_id == club_id).first()
        if lh:
            letterhead_id = lh.id
            letterhead_cfg = {
                "title_text": lh.title_text,
                "subtitle_text": lh.subtitle_text,
            }
            validate_letterhead_asset_refs(db, club_id, letterhead=lh)
            target_asset_id = lh.right_logo_asset_id or lh.left_logo_asset_id
            if target_asset_id:
                asset_rec = get_asset_for_club(db, target_asset_id, club_id)
                active_storage = get_storage()
                if asset_rec and isinstance(active_storage, LocalDiskStorage):
                    asset_path = active_storage.local_path(asset_rec.storage_key)
                    if asset_path.exists():
                        letterhead_cfg["club_logo_path"] = str(asset_path)

    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields_list,
        template_meta={
            "id": tmpl.id,
            "name": tmpl.name,
            "category": tmpl.category,
            "description": tmpl.description or "",
            "numbering_series": series,
        },
        club_slug=club_slug,
        letterhead_cfg=letterhead_cfg,
        design_settings=design_settings,
    )
    dest_docx.write_bytes(docx_bytes)

    ver = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=tmpl.id,
        version_no=1,
        editor_json=editor_json,
        schema_yaml=schema_yaml,
        docx_storage_key=str(dest_docx),
        validation_report=report,
        letterhead_id=letterhead_id,
        created_by=user_id,
        change_note="Initial AI-generated draft",
    )
    db.add(ver)
    db.flush()
    tmpl.current_version_id = ver.id
    # The request/session owns the transaction boundary.  Flushing here keeps
    # the generated rows available to the caller without committing a partial
    # draft if a later response/audit step fails.
    db.flush()
    db.refresh(tmpl)
    db.refresh(ver)

    return tmpl, ver, logo_res
