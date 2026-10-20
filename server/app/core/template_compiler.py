"""Template Compiler for SVNIT ClubDocs Template Editor.

Converts TipTap JSON and field schemas into:
1. Valid python-docx templates with single-run Jinja tags, cantSplit rows, keepWithNext paragraphs,
   and official SVNIT typography and borders.
2. Standard schema.yaml definitions.
3. Strict validation: sandboxed Jinja, unused required field detection, dry render with dummy data,
   and OpenXML integrity checks.
"""

from __future__ import annotations

import concurrent.futures
import io
import keyword
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import yaml
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor
from docxtpl import DocxTemplate
from jinja2 import DebugUndefined, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from docgen.functions import (
    fn_amount_in_words_inr,
    fn_format_date,
    fn_format_date_range,
    fn_format_inr,
    fn_line_total,
    fn_ordinal,
    fn_sum,
    fn_today,
)
from docgen.schema import FieldSchema, TemplateSchema
from docgen.validator import extract_docx_tags
from server.app.core.config import settings


# ---------------------------------------------------------------------------
# Identifier Whitelist & Jinja Tag Sanitizer
# ---------------------------------------------------------------------------

_SANDBOX = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)

IDENTIFIER_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

RESERVED_IDENTIFIERS = set(keyword.kwlist) | {
    "loop", "block", "endblock", "for", "endfor", "if", "endif", "elif",
    "else", "macro", "endmacro", "call", "endcall", "filter", "endfilter",
    "set", "endset", "include", "import", "from", "extends", "autoescape",
    "endautoescape", "raw", "endraw", "cycler", "joiner", "namespace",
    "lipsum", "range", "dict", "super", "self", "var",
    "eval", "exec", "open", "compile", "getattr", "setattr", "delattr",
    "hasattr", "globals", "locals", "vars", "dir",
}

DELIM_PATTERN = re.compile(r"(\{\{|\}\}|\{%|%\}|\{#|#\})")


def sanitize_text(text: str) -> str:
    """Sanitize editor text: disallow script injections and dangerous characters."""
    if not text:
        return ""
    clean = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', text, flags=re.IGNORECASE | re.DOTALL)
    clean = clean.replace('\0', '')
    return clean


def escape_jinja_delimiters(text: str) -> str:
    """Escape Jinja2 delimiters so {{, }}, {%, %}, {#, #} appear literally in output."""
    if not text:
        return ""
    return DELIM_PATTERN.sub(lambda m: f'{{{{ "{m.group(1)}" }}}}', text)


def normalize_logo_image(image_bytes: bytes) -> bytes:
    """Normalize uploaded club logo: resize to max 1000px, composite RGBA onto pure white RGB canvas, optimize."""
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    if img.width > 1000 or img.height > 1000:
        img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        alpha_composite = Image.alpha_composite(background, img)
        rgb_img = alpha_composite.convert("RGB")
    else:
        rgb_img = img.convert("RGB")
    out = io.BytesIO()
    rgb_img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def validate_identifier(name: str, identifier_type: str = "Identifier") -> None:
    """Whitelist identifiers: ^[a-z][a-z0-9_]{0,39}$, non-reserved, non-dunder."""
    if not isinstance(name, str) or not IDENTIFIER_REGEX.match(name):
        raise ValueError(
            f"{identifier_type} '{name}' is invalid. Must match ^[a-z][a-z0-9_]{{0,39}}$ (start with lowercase letter, lowercase alphanumeric or underscore, max 40 chars)."
        )
    if name in RESERVED_IDENTIFIERS or name.startswith("__") or name.endswith("__"):
        raise ValueError(
            f"{identifier_type} '{name}' is a reserved Python/Jinja keyword or dunder name and cannot be used."
        )


def migrate_template_content(content: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy TipTap atom nodes (infoTable, repeatingTable, signatureGrid) into native editable TipTap table nodes."""
    if not isinstance(content, dict):
        return content

    blocks = content.get("content", [])
    if not isinstance(blocks, list):
        return content

    new_blocks = []
    for b in blocks:
        if not isinstance(b, dict):
            new_blocks.append(b)
            continue

        b_type = b.get("type")
        attrs = b.get("attrs", {})

        if b_type == "infoTable":
            rows = b.get("rows") or attrs.get("rows") or []
            table_rows = []
            for r in rows:
                label = str(r.get("label", "Label"))
                field_name = r.get("field") or r.get("key")
                val_text = r.get("value")

                val_content = []
                if field_name:
                    val_content = [{
                        "type": "fieldChip",
                        "attrs": {"fieldName": field_name, "label": field_name, "fieldType": "text"}
                    }]
                elif val_text:
                    val_content = [{"type": "text", "text": str(val_text)}]
                else:
                    val_content = []

                table_rows.append({
                    "type": "tableRow",
                    "content": [
                        {
                            "type": "tableCell",
                            "content": [{"type": "paragraph", "content": [{"type": "text", "text": label}]}]
                        },
                        {
                            "type": "tableCell",
                            "content": [{"type": "paragraph", "content": val_content}] if val_content else [{"type": "paragraph"}]
                        }
                    ]
                })

            new_blocks.append({
                "type": "table",
                "attrs": {
                    "blockType": "infoTable",
                    "class": "cd-info-table",
                },
                "content": table_rows
            })

        elif b_type == "repeatingTable":
            cols = attrs.get("columns", [])
            list_var = attrs.get("listVariable", "budget_items")
            item_alias = attrs.get("itemAlias", "item")
            has_total = attrs.get("hasTotal", False)
            total_label = attrs.get("totalLabel", "Total")
            total_var_name = attrs.get("totalVarName") or f"total_{list_var}_amount"

            header_cells = [
                {
                    "type": "tableHeader",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(c.get("label", c.get("key", "Column")))}]}]
                }
                for c in cols
            ]
            table_rows = [{"type": "tableRow", "content": header_cells}]

            data_cells = [
                {
                    "type": "tableCell",
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "fieldChip",
                            "attrs": {
                                "fieldName": f"{list_var}.{c.get('key', '')}" if c.get("key") else "",
                                "label": c.get("label", c.get("key", "")),
                                "fieldType": "text"
                            }
                        }]
                    }]
                }
                for c in cols
            ]
            table_rows.append({"type": "tableRow", "content": data_cells})

            if has_total and cols:
                total_cells = [
                    {
                        "type": "tableCell",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": total_label}]}]
                    }
                ]
                for _ in range(max(len(cols) - 2, 0)):
                    total_cells.append({"type": "tableCell", "content": [{"type": "paragraph"}]})
                if len(cols) > 1:
                    total_cells.append({
                        "type": "tableCell",
                        "content": [{
                            "type": "paragraph",
                            "content": [{
                                "type": "fieldChip",
                                "attrs": {
                                    "fieldName": total_var_name,
                                    "label": total_var_name,
                                    "fieldType": "money"
                                }
                            }]
                        }]
                    })
                table_rows.append({"type": "tableRow", "content": total_cells})

            new_blocks.append({
                "type": "table",
                "attrs": {
                    "blockType": "repeatingTable",
                    "class": "cd-repeating-table",
                    "listVariable": list_var,
                    "itemAlias": item_alias,
                    "hasTotal": has_total,
                    "totalLabel": total_label,
                    "totalVarName": total_var_name,
                },
                "content": table_rows
            })

        elif b_type == "signatureGrid":
            signatures = attrs.get("signatures", [])
            cells = []
            for s in signatures:
                label = str(s.get("label", "Signee"))
                desig = str(s.get("designation", ""))
                cell_content = [{"type": "paragraph", "content": [{"type": "text", "text": label}]}]
                if desig:
                    cell_content.append({"type": "paragraph", "content": [{"type": "text", "text": desig}]})
                cells.append({
                    "type": "tableCell",
                    "content": cell_content
                })

            new_blocks.append({
                "type": "table",
                "attrs": {
                    "blockType": "signatureGrid",
                    "class": "cd-signature-grid",
                    "columns": len(signatures) or 2
                },
                "content": [{"type": "tableRow", "content": cells}] if cells else []
            })

        else:
            new_blocks.append(b)

    # One output block per input block: carry block-level conditions across the migration.
    for old_block, new_block in zip(blocks, new_blocks):
        show_if = isinstance(old_block, dict) and (old_block.get("attrs") or {}).get("showIf")
        if show_if and isinstance(new_block, dict) and new_block is not old_block:
            new_block.setdefault("attrs", {})["showIf"] = show_if

    migrated = dict(content)
    migrated["content"] = new_blocks
    return migrated


def validate_template_identifiers(editor_json: dict[str, Any] | None, fields: list[dict[str, Any]] | None) -> None:
    """Validate all identifiers in schema fields and editor JSON blocks for strict compliance and uniqueness."""
    seen_field_keys: set[str] = set()
    if fields:
        for f in fields:
            key = f.get("key")
            if key:
                validate_identifier(key, "Field key")
                if key in seen_field_keys:
                    raise ValueError(f"Duplicate field key '{key}' found in fields list. Field keys must be unique.")
                seen_field_keys.add(key)
            if f.get("columns"):
                seen_col_keys: set[str] = set()
                for c in f["columns"]:
                    ckey = c.get("key")
                    if ckey:
                        validate_identifier(ckey, f"Column key in field '{key}'")
                        if ckey in seen_col_keys:
                            raise ValueError(f"Duplicate column key '{ckey}' in table field '{key}'. Column keys must be unique.")
                        seen_col_keys.add(ckey)

    if editor_json and isinstance(editor_json, dict):
        migrated_json = migrate_template_content(editor_json)
        blocks = migrated_json.get("content", [])
        for b in blocks:
            b_type = b.get("type")
            attrs = b.get("attrs") or {}
            cls_name = attrs.get("class") or ""
            if b_type == "table":
                block_type = attrs.get("blockType") or ""
                if block_type == "repeatingTable" or "cd-repeating-table" in cls_name:
                    list_var = attrs.get("listVariable")
                    if list_var:
                        validate_identifier(list_var, "List variable")
                    item_alias = attrs.get("itemAlias")
                    if item_alias:
                        validate_identifier(item_alias, "Item alias")
                    tot_var = attrs.get("totalVarName")
                    if tot_var:
                        validate_identifier(tot_var, "Total variable name")
            elif b_type == "repeatingTable":
                list_var = attrs.get("listVariable")
                if list_var:
                    validate_identifier(list_var, "List variable")
                item_alias = attrs.get("itemAlias")
                if item_alias:
                    validate_identifier(item_alias, "Item alias")
                tot_var = attrs.get("totalVarName")
                if tot_var:
                    validate_identifier(tot_var, "Total variable name")
            if b.get("content"):
                _validate_chips_recursive(b.get("content") or [])


def _validate_chips_recursive(nodes: list[dict[str, Any]] | None) -> None:
    if not nodes:
        return
    for node in nodes:
        if node.get("type") == "fieldChip":
            fn = node.get("attrs", {}).get("fieldName")
            if fn:
                for part in fn.split("."):
                    if part:
                        validate_identifier(part, "Field chip identifier part")
        if node.get("content"):
            _validate_chips_recursive(node.get("content"))

        if "content" in node and isinstance(node["content"], list):
            _validate_chips_recursive(node["content"])


def _block_condition(block: dict[str, Any]) -> Optional[str]:
    """Field key a block is conditional on ("show only if this field has a value"), if any."""
    attrs = block.get("attrs") or {}
    key = attrs.get("showIf") or block.get("showIf")
    if not isinstance(key, str) or not key.strip():
        return None
    key = key.strip()
    validate_identifier(key, "Condition field")
    return key


BLANK_FILL_LINE = "____________________"


def condition_open_tag(key: str) -> str:
    """Opening tag of a conditional section: shown only when ``key`` has a real value.

    Optional fields left empty render as a blank fill-in line, which must not count as a value.
    """
    return f'{{%p if {key} is defined and {key} and {key} != "{BLANK_FILL_LINE}" %}}'


def validate_jinja_expression(expr: str) -> bool:
    """Ensure a Jinja expression parses cleanly inside the sandboxed environment."""
    try:
        _SANDBOX.parse(f"{{{{ {expr} }}}}")
        return True
    except Exception:
        return False


def safe_cap_collections(obj: Any, max_items: int = 1000) -> None:
    """Enforce loop size cap of 1000 items on any collection."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            safe_cap_collections(v, max_items)
    elif isinstance(obj, (list, tuple)):
        if len(obj) > max_items:
            raise ValueError(f"Collection exceeds maximum allowed size of {max_items} rows (found {len(obj)} items)")
        for item in obj:
            safe_cap_collections(item, max_items)


def safe_render_docx(tpl: DocxTemplate, context: dict[str, Any], timeout: float = 30.0, strict: bool = True) -> None:
    """Render a DocxTemplate with SandboxedEnvironment, 30s timeout, and 1000-row cap."""
    safe_cap_collections(context, max_items=1000)

    undefined_cls = StrictUndefined if strict else DebugUndefined
    env = SandboxedEnvironment(autoescape=True, undefined=undefined_cls)

    def safe_range(*args):
        r = range(*args)
        if len(r) > 1000:
            raise ValueError("Loop range exceeds maximum allowed size of 1000")
        return r
    env.globals["range"] = safe_range

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(tpl.render, context, jinja_env=env)
        try:
            future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Template rendering exceeded time limit of {timeout}s")


def find_unreviewed_ai_items(
    editor_json: dict[str, Any] | None,
    fields: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Scan editor JSON blocks and fields for any unreviewed AI-suggested content."""
    unreviewed: list[dict[str, Any]] = []

    # 1. Check fields
    if fields:
        for f in fields:
            if f.get("ai_suggested") is True:
                unreviewed.append({
                    "type": "field",
                    "key": f.get("key"),
                    "label": f.get("label") or f.get("ask") or f.get("key"),
                    "description": f"Field '{f.get('key')}' is AI-suggested and has not been reviewed.",
                })

    # 2. Check blocks and inline chips in editor_json
    if editor_json and isinstance(editor_json, dict):
        blocks = editor_json.get("content", [])
        for idx, block in enumerate(blocks):
            attrs = block.get("attrs", {})
            b_type = block.get("type", "block")
            if attrs.get("ai_suggested") is True or block.get("ai_suggested") is True:
                unreviewed.append({
                    "type": "block",
                    "block_type": b_type,
                    "index": idx,
                    "label": attrs.get("label") or b_type,
                    "description": f"{b_type.capitalize()} block at position {idx + 1} is AI-suggested.",
                })
            # Check inline field chips
            for child in block.get("content", []):
                c_attrs = child.get("attrs", {})
                if child.get("type") == "fieldChip" and (c_attrs.get("ai_suggested") is True or child.get("ai_suggested") is True):
                    chip_key = c_attrs.get("fieldName")
                    if chip_key and not any(u.get("key") == chip_key for u in unreviewed):
                        unreviewed.append({
                            "type": "field",
                            "key": chip_key,
                            "label": c_attrs.get("label") or chip_key,
                            "description": f"Field chip '{chip_key}' is AI-suggested.",
                        })

    return unreviewed


def clear_ai_suggested_flags(
    editor_json: dict[str, Any] | None,
    fields: list[dict[str, Any]] | None,
    review_all: bool = False,
    field_keys: list[str] | None = None,
    block_indices: list[int] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Clear ai_suggested flag from specific or all fields and blocks."""
    import copy
    new_fields = copy.deepcopy(fields) if fields else []
    new_editor = copy.deepcopy(editor_json) if editor_json else {"type": "doc", "content": []}

    f_keys_set = set(field_keys or [])
    b_idx_set = set(block_indices or [])

    # Clear from fields
    for f in new_fields:
        if review_all or f.get("key") in f_keys_set:
            f.pop("ai_suggested", None)

    # Clear from editor blocks
    for idx, block in enumerate(new_editor.get("content", [])):
        if review_all or idx in b_idx_set:
            if "attrs" in block and isinstance(block["attrs"], dict):
                block["attrs"].pop("ai_suggested", None)
            block.pop("ai_suggested", None)
        # Also check inline chips
        for child in block.get("content", []):
            if child.get("type") == "fieldChip":
                c_key = child.get("attrs", {}).get("fieldName")
                if review_all or (c_key and c_key in f_keys_set):
                    if "attrs" in child and isinstance(child["attrs"], dict):
                        child["attrs"].pop("ai_suggested", None)
                    child.pop("ai_suggested", None)

    return new_editor, new_fields




# ---------------------------------------------------------------------------
# XML / Word Styling Helpers
# ---------------------------------------------------------------------------

def set_cell_border(cell, **kwargs):
    """Set cell border properties cleanly."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}></w:tcBorders>')
    for edge, val in kwargs.items():
        element = parse_xml(
            f'<w:{edge} {nsdecls("w")} w:val="{val.get("val", "single")}" '
            f'w:sz="{val.get("sz", "4")}" w:space="0" '
            f'w:color="{val.get("color", "D1D5DB")}"/>'
        )
        tcBorders.append(element)
    tcPr.append(tcBorders)


def set_cell_shading(cell, color_hex: str):
    """Set cell background shading."""
    color_hex = color_hex.lstrip("#")
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set internal cell margins (padding) in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="{top}" w:type="dxa"/>'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'  <w:left w:w="{left}" w:type="dxa"/>'
        f'  <w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def set_row_cant_split(row):
    """Prevent table row from splitting across page breaks."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))


def set_table_header(row):
    """Mark row as repeating table header."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))


def set_paragraph_keep_with_next(p):
    """Prevent paragraph from being orphaned across page breaks."""
    p.paragraph_format.keep_with_next = True


# ---------------------------------------------------------------------------
# TipTap JSON -> python-docx Document Builder
# ---------------------------------------------------------------------------

def load_themes_catalog() -> dict[str, dict[str, Any]]:
    themes_file = Path(__file__).resolve().parent / "themes.json"
    if themes_file.exists():
        try:
            import json
            data = json.loads(themes_file.read_text(encoding="utf-8"))
            return {t["id"]: t for t in data if isinstance(t, dict) and "id" in t}
        except Exception:
            pass
    return {}

THEMES_CATALOG = load_themes_catalog()

def hex_to_rgb(hex_str: str | None) -> RGBColor | None:
    if not hex_str or not isinstance(hex_str, str):
        return None
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        try:
            return RGBColor(int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))
        except Exception:
            return None
    return None

def set_run_font(run, font_name: str | None):
    if not font_name:
        font_name = "Times New Roman"
    run.font.name = font_name
    try:
        rPr = run._r.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = parse_xml(
                f'<w:rFonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                f'w:ascii="{font_name}" w:hAnsi="{font_name}" w:cs="{font_name}"/>'
            )
            rPr.append(rFonts)
        else:
            rFonts.set(qn('w:ascii'), font_name)
            rFonts.set(qn('w:hAnsi'), font_name)
            rFonts.set(qn('w:cs'), font_name)
    except Exception:
        pass


class TipTapDocxCompiler:
    """Converts TipTap document JSON into a styled python-docx Document."""

    def __init__(self, editor_json: dict[str, Any], fields: list[dict[str, Any]],
                 club_slug: str = "acm", letterhead_cfg: dict[str, Any] | None = None,
                 design_settings: dict[str, Any] | None = None):
        self.editor_json = migrate_template_content(editor_json or {"type": "doc", "content": []})
        self.fields = fields or []
        self.fields_by_key = {f.get("key"): f for f in self.fields if f.get("key")}
        self.club_slug = club_slug
        self.letterhead_cfg = letterhead_cfg or {}

        # Merge with theme presets if theme specified
        self.design_settings = dict(design_settings or {})
        if not self.design_settings and isinstance(editor_json, dict):
            self.design_settings = editor_json.get("design_settings") or editor_json.get("attrs", {}).get("design_settings") or {}

        theme_id = self.design_settings.get("theme")
        if theme_id and theme_id in THEMES_CATALOG:
            theme_def = THEMES_CATALOG[theme_id]
            for k, v in theme_def.items():
                if k not in self.design_settings or not self.design_settings[k]:
                    self.design_settings[k] = v

        self.body_font = self.design_settings.get("fontFamily") or self.design_settings.get("body_font") or "Times New Roman"
        self.heading_font = self.design_settings.get("headingFontFamily") or self.design_settings.get("heading_font") or self.body_font
        self.heading_color_rgb = hex_to_rgb(self.design_settings.get("headingColor") or self.design_settings.get("heading_color"))
        self.text_color_rgb = hex_to_rgb(self.design_settings.get("textColor") or self.design_settings.get("text_color"))
        # Certificates and awards use display typography and spread content down the page.
        self.is_certificate = self.design_settings.get("layout") == "certificate"
        self.body_size = 13 if self.is_certificate else 11

        th_bg = self.design_settings.get("tableHeaderBg") or self.design_settings.get("table_header_bg") or ""
        self.table_header_bg_hex = th_bg.strip().lstrip("#").upper()
        self.table_header_text_rgb = hex_to_rgb(self.design_settings.get("tableHeaderTextColor") or self.design_settings.get("table_header_text"))

        self.doc = Document()
        self._configure_page()

    def _configure_page(self):
        """Set page dimensions, orientation, margins, borders, watermark, and styling."""
        orientation = self.design_settings.get("orientation", "portrait")
        margins_preset = self.design_settings.get("margins", "normal")
        margin_in = 0.5 if margins_preset == "compact" else 1.25 if margins_preset == "wide" else 0.8

        for section in self.doc.sections:
            if orientation == "landscape":
                section.orientation = WD_ORIENT.LANDSCAPE
                section.page_width = Inches(11.69)
                section.page_height = Inches(8.27)
            else:
                section.orientation = WD_ORIENT.PORTRAIT
                section.page_width = Inches(8.27)
                section.page_height = Inches(11.69)

            section.top_margin = Inches(margin_in)
            section.bottom_margin = Inches(margin_in)
            section.left_margin = Inches(margin_in)
            section.right_margin = Inches(margin_in)

            # Page border
            page_border = self.design_settings.get("pageBorder") or self.design_settings.get("border_style") or "none"
            if page_border in ("single", "double"):
                val = "double" if page_border == "double" else "single"
                sz = "12" if page_border == "double" else "8"
                b_color = (self.design_settings.get("borderColor") or self.design_settings.get("border_color") or "94A3B8").strip().lstrip("#").upper()
                borders_xml = parse_xml(
                    f'<w:pgBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:offsetFrom="page">'
                    f'<w:top w:val="{val}" w:sz="{sz}" w:space="24" w:color="{b_color}"/>'
                    f'<w:left w:val="{val}" w:sz="{sz}" w:space="24" w:color="{b_color}"/>'
                    f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="24" w:color="{b_color}"/>'
                    f'<w:right w:val="{val}" w:sz="{sz}" w:space="24" w:color="{b_color}"/>'
                    f'</w:pgBorders>'
                )
                section._sectPr.append(borders_xml)

            # Watermark text in header
            watermark_text = self.design_settings.get("watermark") or ""
            if watermark_text.strip():
                p_wm = section.header.add_paragraph()
                p_wm.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_wm.paragraph_format.space_before = Pt(4)
                p_wm.paragraph_format.space_after = Pt(4)
                run_wm = p_wm.add_run(f"[{watermark_text.strip().upper()}]")
                run_wm.font.size = Pt(26)
                run_wm.font.bold = True
                run_wm.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

        # Page background color
        page_bg = self.design_settings.get("pageBg") or self.design_settings.get("page_bg")
        if page_bg and page_bg.lower() not in ("#ffffff", "#fff", "white"):
            clean_hex = page_bg.strip().lstrip("#").upper()
            if len(clean_hex) == 6:
                bg_xml = parse_xml(
                    f'<w:background xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:color="{clean_hex}"/>'
                )
                self.doc.element.insert(0, bg_xml)

        # Set normal style font
        style = self.doc.styles['Normal']
        font = style.font
        font.name = self.body_font
        font.size = Pt(self.body_size)
        font.color.rgb = self.text_color_rgb or RGBColor(0x1F, 0x29, 0x37)

    def build(self) -> Document:
        """Construct the complete DOCX document."""
        # 1. Letterhead / Header and club footer
        self._build_header()
        self._build_footer()

        # 2. Iterate through TipTap content blocks
        content = self.editor_json.get("content", [])
        for block in content:
            condition = _block_condition(block)
            if condition:
                self._add_control_paragraph(condition_open_tag(condition))
            self._add_block(block)
            if condition:
                self._add_control_paragraph("{%p endif %}")

        return self.doc

    def _add_control_paragraph(self, tag: str) -> None:
        """A paragraph holding only a docxtpl control tag; docxtpl removes it when rendering."""
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.add_run(tag)

    def _add_block(self, block: dict[str, Any]) -> None:
        b_type = block.get("type", "")
        if b_type == "heading":
            self._add_heading(block)
        elif b_type == "paragraph":
            self._add_paragraph(block)
        elif b_type in ("bulletList", "orderedList"):
            self._add_list(block, ordered=(b_type == "orderedList"))
        elif b_type == "table":
            self._add_native_table(block)
        elif b_type == "infoTable":
            self._add_info_table(block)
        elif b_type == "repeatingTable":
            self._add_repeating_table(block)
        elif b_type == "signatureGrid":
            self._add_signature_grid(block)
        elif b_type == "imageBlock":
            self._add_image_block(block)
        elif b_type in ("pageBreak", "horizontalRule"):
            self._add_page_break()
        else:
            # Fallback: attempt paragraph extraction
            if "content" in block:
                self._add_paragraph(block)

    def _build_footer(self):
        """Footer on every page: the rendering club's footer line and "Page X of Y"."""
        footer = self.doc.sections[0].footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        def _run(text: str):
            r = p.add_run(text)
            r.font.size = Pt(7.5)
            r.font.name = self.body_font
            r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
            return r

        w_ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

        def _field(code: str):
            # begin / instruction / separate+result / end each in a formatted run, so the
            # page number takes the footer's size instead of the document default.
            for xml in (
                f'<w:fldChar {w_ns} w:fldCharType="begin"/>',
                f'<w:instrText {w_ns} xml:space="preserve"> {code} </w:instrText>',
                f'<w:fldChar {w_ns} w:fldCharType="separate"/>',
            ):
                _run("")._r.append(parse_xml(xml))
            _run("1")
            _run("")._r.append(parse_xml(f'<w:fldChar {w_ns} w:fldCharType="end"/>'))

        _run("{{ club_footer }}    ·    Page ")
        _field("PAGE")
        _run(" of ")
        _field("NUMPAGES")

    def _build_header(self):
        """Build document header: SVNIT logo on right (locked), club logo on left, centered titles."""
        section = self.doc.sections[0]
        header = section.header
        header.is_linked_to_previous = False

        if self.letterhead_cfg.get("banner_placeholder"):
            # Shared library templates: a placeholder banner the renderer swaps for the
            # rendering club's own banner (docgen.letterhead_banner).
            from docgen.letterhead_banner import PLACEHOLDER_NAME

            placeholder = Path("assets") / PLACEHOLDER_NAME
            if placeholder.exists():
                usable = section.page_width - section.left_margin - section.right_margin
                hp = header.paragraphs[0]
                hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                hp.add_run().add_picture(str(placeholder), width=min(usable, Inches(7.0)))
                return

        table = header.add_table(rows=1, cols=3, width=Inches(6.67))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        table.columns[0].width = Inches(0.85)
        table.columns[1].width = Inches(4.97)
        table.columns[2].width = Inches(0.85)

        # Left logo (club logo from assets)
        left_cell = table.cell(0, 0)
        left_cell.width = Inches(0.85)
        lp = left_cell.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # The club's own logo only; no logo rather than another club's.
        club_logo_path = Path(self.letterhead_cfg.get("club_logo_path") or "")
        if self.letterhead_cfg.get("club_logo_path") and club_logo_path.exists():
            l_run = lp.add_run()
            l_run.add_picture(str(club_logo_path), width=Inches(0.75))

        # Center titles
        center_cell = table.cell(0, 1)
        center_cell.width = Inches(4.97)
        cp = center_cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER

        title1 = self.letterhead_cfg.get("title_text", "SARDAR VALLABHBHAI NATIONAL INSTITUTE OF TECHNOLOGY, SURAT")
        # Without a configured letterhead, print the rendering club's own name.
        subtitle = self.letterhead_cfg.get("subtitle_text") or "{{ club_name | upper }}"

        r1 = cp.add_run(title1)
        r1.bold = True
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

        if subtitle:
            cp.add_run().add_break()
            r2 = cp.add_run(subtitle)
            r2.bold = True
            r2.font.name = "Times New Roman"
            r2.font.size = Pt(8.5)
            r2.font.color.rgb = RGBColor(0x1E, 0x5B, 0x94)

        # Right logo (SVNIT Emblem - permanently locked)
        right_cell = table.cell(0, 2)
        right_cell.width = Inches(0.85)
        rp = right_cell.paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        svnit_crest = Path("assets/svnit_crest.png")
        if not svnit_crest.exists():
            svnit_crest = Path("assets/permission_page1_img1.png")
        if svnit_crest.exists():
            r_run = rp.add_run()
            r_run.add_picture(str(svnit_crest), width=Inches(0.75))

        # Remove header table borders
        for row in table.rows:
            for cell in row.cells:
                set_cell_border(cell,
                                top={"val": "none", "sz": "0"},
                                bottom={"val": "none", "sz": "0"},
                                start={"val": "none", "sz": "0"},
                                end={"val": "none", "sz": "0"})

        # Thin divider below header
        p_div = self.doc.add_paragraph()
        p_div.paragraph_format.space_before = Pt(4)
        p_div.paragraph_format.space_after = Pt(8)
        run_div = p_div.add_run("—" * 52)
        run_div.font.size = Pt(8)
        run_div.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)
        p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _add_heading(self, block: dict[str, Any]):
        """Render heading block (H1, H2, H3) with institute typography."""
        attrs = block.get("attrs", {})
        level = attrs.get("level", 1)
        align_str = attrs.get("textAlign", "left")

        p = self.doc.add_paragraph()
        set_paragraph_keep_with_next(p)
        self._apply_alignment(p, align_str)

        if level == 1:
            p.paragraph_format.space_before = Pt(22 if self.is_certificate else 12)
            p.paragraph_format.space_after = Pt(14 if self.is_certificate else 4)
            font_size = 30 if self.is_certificate else 14
            color = self.heading_color_rgb or RGBColor(0x1E, 0x5B, 0x94)  # SVNIT Blue
        elif level == 2:
            p.paragraph_format.space_before = Pt(12 if self.is_certificate else 8)
            p.paragraph_format.space_after = Pt(12 if self.is_certificate else 3)
            font_size = 24 if self.is_certificate else 12
            color = self.heading_color_rgb or RGBColor(0x11, 0x18, 0x27)
        else:
            p.paragraph_format.space_before = Pt(10 if self.is_certificate else 6)
            p.paragraph_format.space_after = Pt(2)
            font_size = 13 if self.is_certificate else 11
            color = self.heading_color_rgb or RGBColor(0x37, 0x41, 0x51)

        self._render_inline_content(p, block.get("content", []), default_size=font_size,
                                   default_bold=True, default_color=color, font_name=self.heading_font)

    def _add_paragraph(self, block: dict[str, Any]):
        """Render paragraph block with inline text, marks, and field chips."""
        attrs = block.get("attrs", {})
        align_str = attrs.get("textAlign", "left")

        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(10 if self.is_certificate else 4)
        p.paragraph_format.line_spacing = 1.4 if self.is_certificate else 1.15
        self._apply_alignment(p, align_str)

        self._render_inline_content(p, block.get("content", []), default_size=self.body_size)

    def _add_image_block(self, block: dict[str, Any]):
        """Render image block or figure into DOCX."""
        attrs = block.get("attrs", {})
        src = attrs.get("src") or ""
        caption = attrs.get("caption")
        width_str = attrs.get("width") or "240px"
        alignment = attrs.get("alignment") or "center"

        width_in = Inches(2.5)
        if "px" in str(width_str):
            try:
                px = float(str(width_str).replace("px", "").strip())
                width_in = Inches(min(max(px / 96.0, 0.5), 6.5))
            except Exception:
                pass
        elif "%" in str(width_str):
            width_in = Inches(6.5)

        p = self.doc.add_paragraph()
        if alignment == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif alignment == "right":
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        image_data = None
        if src.startswith("data:image/") and ";base64," in src:
            try:
                import base64
                b64_part = src.split(";base64,")[1]
                image_data = base64.b64decode(b64_part)
            except Exception:
                pass
        elif attrs.get("assetId"):
            try:
                from server.app.core.storage import get_storage, LocalDiskStorage
                from server.app.models.club import ClubAsset
                from server.app.db.session import SessionLocal
                with SessionLocal() as db:
                    asset = db.query(ClubAsset).filter(ClubAsset.id == attrs["assetId"]).first()
                    if asset:
                        active_storage = get_storage()
                        if isinstance(active_storage, LocalDiskStorage):
                            p_asset = active_storage.local_path(asset.storage_key)
                            if p_asset.exists():
                                image_data = p_asset.read_bytes()
            except Exception:
                pass

        if image_data:
            try:
                img_stream = io.BytesIO(image_data)
                p.add_run().add_picture(img_stream, width=width_in)
            except Exception:
                pass

        if caption:
            p_cap = self.doc.add_paragraph()
            p_cap.alignment = p.alignment
            run_cap = p_cap.add_run(caption)
            run_cap.italic = True
            run_cap.font.size = Pt(9)
            run_cap.font.color.rgb = RGBColor(100, 116, 139)

    def _add_list(self, block: dict[str, Any], ordered: bool = False):
        """Render bullet or numbered list items."""
        items = block.get("content", [])
        style_name = 'List Number' if ordered else 'List Bullet'
        for it in items:
            p = self.doc.add_paragraph(style=style_name)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)
            for inner in it.get("content", []):
                self._render_inline_content(p, inner.get("content", []))

    def _add_info_table(self, block: dict[str, Any]):
        """Render 2-column label : value Info Table like official SVNIT forms."""
        attrs = block.get("attrs", {})
        rows_data = block.get("rows") or attrs.get("rows") or []
        if not rows_data:
            # Check if block has table structure
            return

        table = self.doc.add_table(rows=len(rows_data), cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        for i, r in enumerate(rows_data):
            row = table.rows[i]
            set_row_cant_split(row)

            label_text = escape_jinja_delimiters(sanitize_text(str(r.get("label", ""))))
            field_name = r.get("field") or r.get("key") or ""
            val_text = r.get("value")

            # Left Cell: Label
            c0 = row.cells[0]
            c0.width = Inches(2.2)
            set_cell_shading(c0, "F8FAFC")
            set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
            set_cell_border(c0,
                            top={"val": "single", "sz": "4", "color": "D1D5DB"},
                            bottom={"val": "single", "sz": "4", "color": "D1D5DB"},
                            start={"val": "single", "sz": "4", "color": "D1D5DB"},
                            end={"val": "single", "sz": "4", "color": "D1D5DB"})
            p0 = c0.paragraphs[0]
            p0.paragraph_format.space_before = Pt(0)
            p0.paragraph_format.space_after = Pt(0)
            set_paragraph_keep_with_next(p0)
            run0 = p0.add_run(label_text)
            run0.bold = True
            run0.font.name = "Times New Roman"
            run0.font.size = Pt(10)

            # Right Cell: Value or Field Chip
            c1 = row.cells[1]
            c1.width = Inches(4.47)
            set_cell_margins(c1, top=80, bottom=80, left=120, right=120)
            set_cell_border(c1,
                            top={"val": "single", "sz": "4", "color": "D1D5DB"},
                            bottom={"val": "single", "sz": "4", "color": "D1D5DB"},
                            start={"val": "single", "sz": "4", "color": "D1D5DB"},
                            end={"val": "single", "sz": "4", "color": "D1D5DB"})
            p1 = c1.paragraphs[0]
            p1.paragraph_format.space_before = Pt(0)
            p1.paragraph_format.space_after = Pt(0)

            # Insert tag in a single run
            if field_name:
                validate_identifier(field_name, "Info table field")
                run1 = p1.add_run(f"{{{{ {field_name} }}}}")
            elif val_text:
                run1 = p1.add_run(escape_jinja_delimiters(sanitize_text(str(val_text))))
            else:
                run1 = p1.add_run("")
            run1.font.name = "Times New Roman"
            run1.font.size = Pt(10)

        # Spacing after table
        p_sp = self.doc.add_paragraph()
        p_sp.paragraph_format.space_before = Pt(4)
        p_sp.paragraph_format.space_after = Pt(4)

    def _add_repeating_table(self, block: dict[str, Any]):
        """Render Repeating Table: Header, {%tr for %}, Data row, {%tr endfor %}, and Total row."""
        attrs = block.get("attrs", {})
        list_var = attrs.get("listVariable") or "items"
        validate_identifier(list_var, "List variable")
        item_alias = attrs.get("itemAlias") or "item"
        validate_identifier(item_alias, "Item alias")
        cols = attrs.get("columns") or []
        has_total = attrs.get("hasTotal", False)
        total_label = attrs.get("totalLabel", "Total")
        total_field = attrs.get("totalField", "amount")
        total_var_name = attrs.get("totalVarName") or f"total_{list_var}_amount"
        if has_total:
            validate_identifier(total_var_name, "Total variable name")

        num_cols = max(len(cols), 1)
        table = self.doc.add_table(rows=0, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        col_width = Inches(6.67 / num_cols)

        # 1. Header row
        h_row = table.add_row()
        set_row_cant_split(h_row)
        set_table_header(h_row)
        for j, col in enumerate(cols):
            cell = h_row.cells[j]
            cell.width = col_width
            set_cell_shading(cell, "EBF1F5")
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            set_cell_border(cell,
                            top={"val": "single", "sz": "6", "color": "1E5B94"},
                            bottom={"val": "single", "sz": "6", "color": "1E5B94"},
                            start={"val": "single", "sz": "4", "color": "D1D5DB"},
                            end={"val": "single", "sz": "4", "color": "D1D5DB"})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            align = col.get("align", "left")
            self._apply_alignment(p, align)
            col_label = escape_jinja_delimiters(sanitize_text(col.get("label", col.get("key", ""))))
            r = p.add_run(col_label)
            r.bold = True
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(0x1E, 0x5B, 0x94)

        # 2. Loop Start Row ({%tr for ... %})
        r_start = table.add_row()
        r_start.cells[0].paragraphs[0].text = f"{{%tr for {item_alias} in {list_var} %}}"

        # 3. Data row
        d_row = table.add_row()
        set_row_cant_split(d_row)
        for j, col in enumerate(cols):
            cell = d_row.cells[j]
            cell.width = col_width
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
            set_cell_border(cell,
                            top={"val": "single", "sz": "4", "color": "E5E7EB"},
                            bottom={"val": "single", "sz": "4", "color": "E5E7EB"},
                            start={"val": "single", "sz": "4", "color": "E5E7EB"},
                            end={"val": "single", "sz": "4", "color": "E5E7EB"})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            align = col.get("align", "left")
            self._apply_alignment(p, align)

            ckey = col.get("key", "")
            if ckey:
                validate_identifier(ckey, "Column key")
            # Place tag in a single run
            run = p.add_run(f"{{{{ {item_alias}.{ckey} }}}}")
            run.font.name = "Times New Roman"
            run.font.size = Pt(10)

        # 4. Loop End Row ({%tr endfor %})
        r_end = table.add_row()
        r_end.cells[0].paragraphs[0].text = "{%tr endfor %}"

        # 5. Computed Total row (if requested)
        if has_total:
            t_row = table.add_row()
            set_row_cant_split(t_row)
            for j in range(num_cols):
                cell = t_row.cells[j]
                cell.width = col_width
                set_cell_shading(cell, "F8FAFC")
                set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
                set_cell_border(cell,
                                top={"val": "single", "sz": "6", "color": "1E5B94"},
                                bottom={"val": "double", "sz": "8", "color": "1E5B94"},
                                start={"val": "single", "sz": "4", "color": "D1D5DB"},
                                end={"val": "single", "sz": "4", "color": "D1D5DB"})
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)

                if j == 0:
                    r = p.add_run(escape_jinja_delimiters(sanitize_text(total_label)))
                    r.bold = True
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(10)
                elif j == num_cols - 1:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    r = p.add_run(f"{{{{ {total_var_name} }}}}")
                    r.bold = True
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(10)

        p_sp = self.doc.add_paragraph()
        p_sp.paragraph_format.space_before = Pt(4)
        p_sp.paragraph_format.space_after = Pt(4)

    def _add_signature_grid(self, block: dict[str, Any]):
        """Render N x M Signature Grid with cantSplit and keepWithNext."""
        attrs = block.get("attrs", {})
        cols_count = max(int(attrs.get("columns", 3)), 1)
        signatures = attrs.get("signatures", [])
        if not signatures:
            # Default 3 signees
            signatures = [
                {"label": "Student Coordinator", "designation": ""},
                {"label": "Faculty Advisor", "designation": ""},
                {"label": "Head of Department", "designation": ""},
            ]

        # Break signatures into rows of cols_count
        chunked = [signatures[i:i + cols_count] for i in range(0, len(signatures), cols_count)]

        # Preceding spacing
        p_lead = self.doc.add_paragraph()
        p_lead.paragraph_format.space_before = Pt(30 if self.is_certificate else 14)
        p_lead.paragraph_format.space_after = Pt(4)
        set_paragraph_keep_with_next(p_lead)

        table = self.doc.add_table(rows=len(chunked) * 2, cols=cols_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        cell_width = Inches(6.67 / cols_count)

        for row_idx, row_signs in enumerate(chunked):
            # Row 1: Signature space (empty height for physical signature)
            space_row = table.rows[row_idx * 2]
            set_row_cant_split(space_row)
            for col_idx in range(cols_count):
                cell = space_row.cells[col_idx]
                cell.width = cell_width
                set_cell_border(cell,
                                top={"val": "none", "sz": "0"},
                                bottom={"val": "single", "sz": "4", "color": "9CA3AF"}, # Signature line
                                start={"val": "none", "sz": "0"},
                                end={"val": "none", "sz": "0"})
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(36) # Vertical space above signature labels per Requirement 4
                p.paragraph_format.space_after = Pt(2)
                set_paragraph_keep_with_next(p)

            # Row 2: Designation and Role details
            info_row = table.rows[row_idx * 2 + 1]
            set_row_cant_split(info_row)
            for col_idx in range(cols_count):
                cell = info_row.cells[col_idx]
                cell.width = cell_width
                set_cell_border(cell,
                                top={"val": "none", "sz": "0"},
                                bottom={"val": "none", "sz": "0"},
                                start={"val": "none", "sz": "0"},
                                end={"val": "none", "sz": "0"})
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(3)
                p.paragraph_format.space_after = Pt(10)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_paragraph_keep_with_next(p)

                if col_idx < len(row_signs):
                    sign = row_signs[col_idx]
                    s_label = escape_jinja_delimiters(sanitize_text(sign.get("label", "")))
                    s_desig = escape_jinja_delimiters(sanitize_text(sign.get("designation", "")))
                    r1 = p.add_run(s_label)
                    r1.bold = True
                    r1.font.name = "Times New Roman"
                    r1.font.size = Pt(9.5)
                    if s_desig:
                        p.add_run().add_break()
                        r2 = p.add_run(s_desig)
                        r2.font.name = "Times New Roman"
                        r2.font.size = Pt(8.5)
                        r2.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    def _add_native_table(self, block: dict[str, Any]):
        """Render native TipTap table (infoTable, repeatingTable, signatureGrid, or generic)."""
        attrs = block.get("attrs", {})
        block_type = attrs.get("blockType") or attrs.get("data-block-type") or ""
        css_class = attrs.get("class", "")

        if block_type == "infoTable" or "cd-info-table" in css_class:
            self._render_native_info_table(block)
        elif block_type == "repeatingTable" or "cd-repeating-table" in css_class:
            self._render_native_repeating_table(block)
        elif block_type == "signatureGrid" or "cd-signature-grid" in css_class:
            self._render_native_signature_grid(block)
        else:
            self._render_generic_table(block)

    def _render_native_info_table(self, block: dict[str, Any]):
        rows = block.get("content", [])
        if not rows:
            return

        table = self.doc.add_table(rows=len(rows), cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        for i, row_node in enumerate(rows):
            word_row = table.rows[i]
            set_row_cant_split(word_row)

            cells = row_node.get("content", [])
            # Left cell: Label
            c0 = word_row.cells[0]
            c0.width = Inches(2.2)
            set_cell_shading(c0, "F8FAFC")
            set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
            set_cell_border(c0,
                            top={"val": "single", "sz": "4", "color": "D1D5DB"},
                            bottom={"val": "single", "sz": "4", "color": "D1D5DB"},
                            start={"val": "single", "sz": "4", "color": "D1D5DB"},
                            end={"val": "single", "sz": "4", "color": "D1D5DB"})
            p0 = c0.paragraphs[0]
            p0.paragraph_format.space_before = Pt(0)
            p0.paragraph_format.space_after = Pt(0)
            set_paragraph_keep_with_next(p0)

            if len(cells) > 0:
                self._render_cell_paragraphs(c0, cells[0], is_bold=True)

            # Right cell: Value / Field
            c1 = word_row.cells[1]
            c1.width = Inches(4.47)
            set_cell_margins(c1, top=80, bottom=80, left=120, right=120)
            set_cell_border(c1,
                            top={"val": "single", "sz": "4", "color": "D1D5DB"},
                            bottom={"val": "single", "sz": "4", "color": "D1D5DB"},
                            start={"val": "single", "sz": "4", "color": "D1D5DB"},
                            end={"val": "single", "sz": "4", "color": "D1D5DB"})
            p1 = c1.paragraphs[0]
            p1.paragraph_format.space_before = Pt(0)
            p1.paragraph_format.space_after = Pt(0)

            if len(cells) > 1:
                self._render_cell_paragraphs(c1, cells[1], is_bold=False)

        p_sp = self.doc.add_paragraph()
        p_sp.paragraph_format.space_before = Pt(4)
        p_sp.paragraph_format.space_after = Pt(4)

    def _render_native_repeating_table(self, block: dict[str, Any]):
        attrs = block.get("attrs", {})
        list_var = attrs.get("listVariable") or "budget_items"
        validate_identifier(list_var, "List variable")
        item_alias = attrs.get("itemAlias") or "item"
        validate_identifier(item_alias, "Item alias")
        has_total = attrs.get("hasTotal", False)
        total_label = attrs.get("totalLabel", "Total")
        total_var_name = attrs.get("totalVarName") or f"total_{list_var}_amount"
        if has_total:
            validate_identifier(total_var_name, "Total variable name")

        rows = block.get("content", [])
        if not rows:
            return

        header_row_node = rows[0]
        header_cells = header_row_node.get("content", [])
        num_cols = max(len(header_cells), 1)
        col_width = Inches(6.67 / num_cols)

        table = self.doc.add_table(rows=0, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        # 1. Header row
        h_row = table.add_row()
        set_row_cant_split(h_row)
        set_table_header(h_row)
        for j in range(num_cols):
            cell = h_row.cells[j]
            cell.width = col_width
            set_cell_shading(cell, "EBF1F5")
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            set_cell_border(cell,
                            top={"val": "single", "sz": "6", "color": "1E5B94"},
                            bottom={"val": "single", "sz": "6", "color": "1E5B94"},
                            start={"val": "single", "sz": "4", "color": "D1D5DB"},
                            end={"val": "single", "sz": "4", "color": "D1D5DB"})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            if j < len(header_cells):
                self._render_cell_paragraphs(cell, header_cells[j], is_bold=True, font_color=RGBColor(0x1E, 0x5B, 0x94))

        # 2. Loop start row
        r_start = table.add_row()
        r_start.cells[0].paragraphs[0].text = f"{{%tr for {item_alias} in {list_var} %}}"

        # 3. Template data row
        template_row_node = rows[1] if len(rows) > 1 else None
        template_cells = template_row_node.get("content", []) if template_row_node else []

        d_row = table.add_row()
        set_row_cant_split(d_row)
        for j in range(num_cols):
            cell = d_row.cells[j]
            cell.width = col_width
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
            set_cell_border(cell,
                            top={"val": "single", "sz": "4", "color": "E5E7EB"},
                            bottom={"val": "single", "sz": "4", "color": "E5E7EB"},
                            start={"val": "single", "sz": "4", "color": "E5E7EB"},
                            end={"val": "single", "sz": "4", "color": "E5E7EB"})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)

            if j < len(template_cells):
                self._render_cell_paragraphs(cell, template_cells[j], item_alias=item_alias, list_var=list_var)

        # 4. Loop end row
        r_end = table.add_row()
        r_end.cells[0].paragraphs[0].text = "{%tr endfor %}"

        # 5. Total row
        if has_total or len(rows) > 2:
            t_row = table.add_row()
            set_row_cant_split(t_row)
            for j in range(num_cols):
                cell = t_row.cells[j]
                cell.width = col_width
                set_cell_shading(cell, "F8FAFC")
                set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
                set_cell_border(cell,
                                top={"val": "single", "sz": "6", "color": "1E5B94"},
                                bottom={"val": "double", "sz": "8", "color": "1E5B94"},
                                start={"val": "single", "sz": "4", "color": "D1D5DB"},
                                end={"val": "single", "sz": "4", "color": "D1D5DB"})
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)

                if j == 0:
                    r = p.add_run(escape_jinja_delimiters(sanitize_text(total_label)))
                    r.bold = True
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(10)
                elif j == num_cols - 1:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    r = p.add_run(f"{{{{ {total_var_name} }}}}")
                    r.bold = True
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(10)

        p_sp = self.doc.add_paragraph()
        p_sp.paragraph_format.space_before = Pt(4)
        p_sp.paragraph_format.space_after = Pt(4)

    def _render_native_signature_grid(self, block: dict[str, Any]):
        rows = block.get("content", [])
        if not rows:
            return
        row_node = rows[0]
        cells = row_node.get("content", [])
        cols_count = max(len(cells), 1)
        cell_width = Inches(6.67 / cols_count)

        p_lead = self.doc.add_paragraph()
        p_lead.paragraph_format.space_before = Pt(30 if self.is_certificate else 14)
        p_lead.paragraph_format.space_after = Pt(4)
        set_paragraph_keep_with_next(p_lead)

        table = self.doc.add_table(rows=2, cols=cols_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        # Row 0: Signature line space
        space_row = table.rows[0]
        set_row_cant_split(space_row)
        for col_idx in range(cols_count):
            cell = space_row.cells[col_idx]
            cell.width = cell_width
            set_cell_border(cell,
                            top={"val": "none", "sz": "0"},
                            bottom={"val": "single", "sz": "4", "color": "9CA3AF"},
                            start={"val": "none", "sz": "0"},
                            end={"val": "none", "sz": "0"})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(36)
            p.paragraph_format.space_after = Pt(2)
            set_paragraph_keep_with_next(p)

        # Row 1: Signee details
        info_row = table.rows[1]
        set_row_cant_split(info_row)
        for col_idx in range(cols_count):
            cell = info_row.cells[col_idx]
            cell.width = cell_width
            set_cell_border(cell,
                            top={"val": "none", "sz": "0"},
                            bottom={"val": "none", "sz": "0"},
                            start={"val": "none", "sz": "0"},
                            end={"val": "none", "sz": "0"})
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(10)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_paragraph_keep_with_next(p)

            if col_idx < len(cells):
                self._render_cell_paragraphs(cell, cells[col_idx], is_bold=True)
                # Name and designation lines sit centred under the signature line.
                for cell_p in cell.paragraphs:
                    cell_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _render_generic_table(self, block: dict[str, Any]):
        rows = block.get("content", [])
        if not rows:
            return

        first_row_cells = rows[0].get("content", [])
        cols_count = max(len(first_row_cells), 1)
        col_width = Inches(6.67 / cols_count)

        table = self.doc.add_table(rows=len(rows), cols=cols_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        for i, row_node in enumerate(rows):
            word_row = table.rows[i]
            set_row_cant_split(word_row)
            cells = row_node.get("content", [])
            is_header = any(c.get("type") == "tableHeader" for c in cells)
            if is_header and i == 0:
                set_table_header(word_row)

            for j in range(cols_count):
                cell = word_row.cells[j]
                cell.width = col_width
                if is_header:
                    set_cell_shading(cell, "F1F5F9")
                set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
                set_cell_border(cell,
                                top={"val": "single", "sz": "4", "color": "D1D5DB"},
                                bottom={"val": "single", "sz": "4", "color": "D1D5DB"},
                                start={"val": "single", "sz": "4", "color": "D1D5DB"},
                                end={"val": "single", "sz": "4", "color": "D1D5DB"})
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)

                if j < len(cells):
                    self._render_cell_paragraphs(cell, cells[j], is_bold=is_header)

        p_sp = self.doc.add_paragraph()
        p_sp.paragraph_format.space_before = Pt(4)
        p_sp.paragraph_format.space_after = Pt(4)

    def _render_cell_paragraphs(self, docx_cell, cell_node: dict[str, Any], is_bold: bool = False,
                                font_color: Optional[RGBColor] = None, item_alias: Optional[str] = None,
                                list_var: Optional[str] = None):
        """Render all paragraphs and inline runs/chips inside a TipTap table cell."""
        p_nodes = [n for n in cell_node.get("content", []) if n.get("type") == "paragraph"]
        if not p_nodes:
            p_nodes = [cell_node]

        for p_idx, p_node in enumerate(p_nodes):
            if p_idx == 0:
                p = docx_cell.paragraphs[0]
            else:
                p = docx_cell.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)

            for child in p_node.get("content", []):
                c_type = child.get("type")
                if c_type == "text":
                    text = child.get("text", "")
                    clean_text = escape_jinja_delimiters(sanitize_text(text))
                    run = p.add_run(clean_text)
                    run.bold = is_bold or any(m.get("type") == "bold" for m in child.get("marks", []))
                    run.italic = any(m.get("type") == "italic" for m in child.get("marks", []))
                    set_run_font(run, self.body_font)
                    run.font.size = Pt(10)
                    if font_color:
                        run.font.color.rgb = font_color
                elif c_type == "fieldChip":
                    fn = child.get("attrs", {}).get("fieldName", "")
                    if fn:
                        for part in fn.split("."):
                            if part:
                                validate_identifier(part, "Field chip identifier part")
                        if item_alias and list_var and (fn.startswith(f"{list_var}.") or fn.startswith(f"{item_alias}.")):
                            field_key = fn.split(".", 1)[1]
                            tag_text = f"{{{{ {item_alias}.{field_key} }}}}"
                        elif item_alias and "." not in fn:
                            tag_text = f"{{{{ {item_alias}.{fn} }}}}"
                        else:
                            tag_text = f"{{{{ {fn} }}}}"
                        run = p.add_run(tag_text)
                        set_run_font(run, self.body_font)
                        run.font.size = Pt(10)

    def _add_page_break(self):
        """Insert clean page break."""
        p = self.doc.add_paragraph()
        run = p.add_run()
        run.add_break(WD_BREAK.PAGE)

    def _render_inline_content(self, paragraph, content_list: list[dict[str, Any]],
                               default_size: int = 11, default_bold: bool = False,
                               default_color: RGBColor | None = None,
                               font_name: str | None = None):
        """Render inline elements: text runs with marks and field chips in single runs."""
        effective_font = font_name or self.body_font
        for item in content_list:
            i_type = item.get("type", "")
            if i_type == "text":
                text = escape_jinja_delimiters(sanitize_text(item.get("text", "")))
                marks = {m.get("type") for m in item.get("marks", [])}
                run = paragraph.add_run(text)
                run.bold = default_bold or ("bold" in marks)
                run.italic = "italic" in marks
                run.underline = "underline" in marks
                set_run_font(run, effective_font)
                run.font.size = Pt(default_size)
                if default_color:
                    run.font.color.rgb = default_color
                elif self.text_color_rgb:
                    run.font.color.rgb = self.text_color_rgb
            elif i_type == "fieldChip":
                # Crucial: render Jinja variable tag in a single run
                attrs = item.get("attrs", {})
                f_name = attrs.get("fieldName") or ""
                if f_name:
                    for part in f_name.split("."):
                        if part:
                            validate_identifier(part, "Field chip name part")
                    run = paragraph.add_run(f"{{{{ {f_name} }}}}")
                    run.bold = default_bold
                    set_run_font(run, effective_font)
                    run.font.size = Pt(default_size)
                    if default_color:
                        run.font.color.rgb = default_color
                    elif self.text_color_rgb:
                        run.font.color.rgb = self.text_color_rgb
            elif i_type == "hardBreak":
                paragraph.add_run().add_break()

    def _apply_alignment(self, paragraph, align_str: Optional[str]):
        if not align_str or not isinstance(align_str, str):
            return
        align_map = {
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        paragraph.alignment = align_map.get(align_str.lower(), WD_ALIGN_PARAGRAPH.LEFT)


# ---------------------------------------------------------------------------
# Schema Builder & Compiler Orchestrator
# ---------------------------------------------------------------------------

class TemplateCompiler:
    """Orchestrates compilation, schema.yaml generation, and strict validation."""

    @staticmethod
    def compile(
        editor_json: dict[str, Any],
        fields: list[dict[str, Any]],
        template_meta: dict[str, Any],
        club_slug: str = "acm",
        letterhead_cfg: dict[str, Any] | None = None,
        design_settings: dict[str, Any] | None = None,
    ) -> tuple[bytes, str, dict[str, Any]]:
        """Compile TipTap JSON + fields into DOCX bytes, schema.yaml string, and validation report.
        
        Returns:
            (docx_bytes, schema_yaml_str, validation_report_dict)
        """
        # 0. Validate identifiers in fields and editor_json
        validate_template_identifiers(editor_json, fields)

        # 1. Check for repeating tables with computed totals and register computed fields in schema
        enriched_fields = list(fields)
        content_blocks = editor_json.get("content", [])
        for block in content_blocks:
            if block.get("type") == "repeatingTable":
                attrs = block.get("attrs", {})
                if attrs.get("hasTotal"):
                    list_var = attrs.get("listVariable", "items")
                    tot_var = attrs.get("totalVarName") or f"total_{list_var}_amount"
                    # Check if already in fields
                    if not any(f.get("key") == tot_var for f in enriched_fields):
                        enriched_fields.append({
                            "key": tot_var,
                            "type": "money",
                            "required": False,
                            "ask": attrs.get("totalLabel", "Total Amount"),
                            "computed": {
                                "function": "sum",
                                "args": {
                                    "items": f"${list_var}",
                                    "field": attrs.get("totalField", "amount"),
                                }
                            },
                            "format": "inr",
                        })

        # 2. Build python-docx Document
        eff_design_settings = dict(design_settings or {})
        if not eff_design_settings and isinstance(editor_json, dict):
            eff_design_settings = editor_json.get("design_settings") or editor_json.get("attrs", {}).get("design_settings") or {}

        compiler = TipTapDocxCompiler(
            editor_json=editor_json,
            fields=enriched_fields,
            club_slug=club_slug,
            letterhead_cfg=letterhead_cfg,
            design_settings=eff_design_settings,
        )
        doc = compiler.build()

        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        # 3. Build schema.yaml
        template_id = template_meta.get("id") or template_meta.get("slug") or f"tmpl_{uuid.uuid4().hex[:8]}"
        template_name = template_meta.get("name", "Custom Club Template")
        category = template_meta.get("category", "General")
        description = template_meta.get("description", "")

        schema_dict = {
            "id": template_id,
            "name": template_name,
            "category": category,
            "description": description,
            "stage": template_meta.get("stage", "custom"),
            "triggers": template_meta.get("triggers") or [w.lower() for w in template_name.split() if len(w) > 3],
            "letterhead": (letterhead_cfg or {}).get("slug") or "club",
            "numbering": {
                "series": template_meta.get("numbering_series") or "DOC",
                # {club_code} is filled with the generating club's code, so shared templates
                # never carry another club's prefix.
                "format": f"{{club_code}}/{{short_year}}/{template_meta.get('numbering_series') or 'DOC'}/{{seq:03d}}",
                "confirm": True,
            },
            "depends_on": [],
            "repeat_per": None,
            "fields": [],
        }
        if isinstance(template_meta.get("recommend"), dict):
            schema_dict["recommend"] = template_meta["recommend"]

        for f in enriched_fields:
            f_entry: dict[str, Any] = {
                "key": f.get("key"),
                "type": f.get("type", "text"),
                "required": bool(f.get("required", False)),
            }
            if f.get("ask"):
                f_entry["ask"] = f["ask"]
            if f.get("defer_ok"):
                f_entry["defer_ok"] = True
            if f.get("sensitive"):
                f_entry["mask"] = True
            if f.get("ai_suggested"):
                f_entry["ai_suggested"] = True
            if f.get("values"):
                f_entry["values"] = f["values"]
            if f.get("computed"):
                f_entry["computed"] = f["computed"]
            if f.get("format"):
                f_entry["format"] = f["format"]
            if f.get("columns"):
                f_entry["columns"] = f["columns"]
            elif f.get("type") == "table":
                for b in editor_json.get("content", []):
                    if b.get("type") == "repeatingTable" and b.get("attrs", {}).get("listVariable") == f.get("key"):
                        f_entry["columns"] = b.get("attrs", {}).get("columns", [])
                        break
            schema_dict["fields"].append(f_entry)

        schema_yaml_str = yaml.dump(schema_dict, sort_keys=False)

        # 4. Strict Validation
        validation_report = TemplateCompiler.validate(
            docx_bytes=docx_bytes,
            schema_yaml_str=schema_yaml_str,
            fields=enriched_fields,
            editor_json=editor_json,
        )

        return docx_bytes, schema_yaml_str, validation_report

    @staticmethod
    def validate(
        docx_bytes: bytes,
        schema_yaml_str: str,
        fields: list[dict[str, Any]],
        editor_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate compiled artifacts: tags, unused required fields, OpenXML check, dry render."""
        report: dict[str, Any] = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        # Check 1: OpenXML / python-docx integrity check
        try:
            doc_test = Document(io.BytesIO(docx_bytes))
            para_count = len(doc_test.paragraphs)
            table_count = len(doc_test.tables)
            report["stats"] = {"paragraphs": para_count, "tables": table_count}
        except Exception as e:
            report["is_valid"] = False
            report["errors"].append(f"OpenXML verification failed: {e}")
            return report

        # Check 2: Load Schema model
        try:
            schema_data = yaml.safe_load(schema_yaml_str)
            schema = TemplateSchema(**schema_data)
        except Exception as e:
            report["is_valid"] = False
            report["errors"].append(f"schema.yaml failed validation: {e}")
            return report

        # Check 3: Extract docx tags using temporary file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            tmp_docx.write(docx_bytes)
            tmp_docx_path = Path(tmp_docx.name)

        try:
            docx_tags = extract_docx_tags(tmp_docx_path)
            report["stats"]["docx_tags"] = sorted(list(docx_tags))

            # Compile approved/expected tags set
            expected_vars = set(schema.all_field_keys()) | {f.get("key") for f in fields if f.get("key")}
            expected_vars.update({
                "club_name", "club_short", "institute_name", "institute_short",
                "chapter_code", "head_of_account", "academic_year", "affiliating_institute_text",
                "student_head", "student_secretary", "chairperson", "faculty_chairman",
                "faculty_co_chairman", "venue_config", "submitted_to", "venue_tech_assistant",
                "venue_faculty_in_charge", "document_date", "today_str", "date_range_str",
                "ref_no", "sr_no", "description",
                "department", "department_short", "approval_chain", "club_footer",
            })

            approved_escapes = {
                '{{ "{{" }}', '{{ "}}" }}', '{{ "{%" }}', '{{ "%}" }}', '{{ "{#" }}', '{{ "#}" }}',
                "{{ '{{' }}", "{{ '}}' }}", "{{ '{%' }}", "{{ '%}' }}", "{{ '{#' }}", "{{ '#}' }}",
                '{{ "{{"}}', '{{ "}}"}}', '{{ "{%"}}', '{{ "%}"}}', '{{ "{#"}}', '{{ "#}"}}',
            }

            allowed_loops = set()
            allowed_loop_end = "{%tr endfor %}"
            for b in editor_json.get("content", []):
                if b.get("type") == "repeatingTable":
                    l_var = b.get("attrs", {}).get("listVariable", "items")
                    i_alias = b.get("attrs", {}).get("itemAlias", "item")
                    allowed_loops.add(f"{{%tr for {i_alias} in {l_var} %}}")
                    for col in b.get("attrs", {}).get("columns", []):
                        ck = col.get("key")
                        if ck:
                            expected_vars.add(f"{i_alias}.{ck}")
                    tot_v = b.get("attrs", {}).get("totalVarName")
                    if tot_v:
                        expected_vars.add(tot_v)

            # Read all word/*.xml files from docx zip and verify every tag
            TAG_REGEX = re.compile(r"(\{\{(?:[^\"\x27}]|\"[^\"]*\"|\x27[^\x27]*\x27)*?\}\}|\{%(?:[^\"\x27%]|%[^}]|\"[^\"]*\"|\x27[^\x27]*\x27)*?%\}|\{#.*?#\})")
            found_raw_tags = []
            with zipfile.ZipFile(str(tmp_docx_path)) as zf:
                for zname in zf.namelist():
                    if zname.startswith("word/") and zname.endswith(".xml"):
                        xml_content = zf.read(zname).decode("utf-8", errors="ignore")
                        for m in TAG_REGEX.finditer(xml_content):
                            raw_t = m.group(1).strip()
                            found_raw_tags.append(raw_t)

            allowed_conditions = {"{%p endif %}"}
            for b in editor_json.get("content", []):
                cond = _block_condition(b)
                if cond:
                    allowed_conditions.add(condition_open_tag(cond))

            for raw_t in found_raw_tags:
                norm_t = re.sub(r"\s+", " ", raw_t)
                if norm_t in approved_escapes:
                    continue
                if norm_t == allowed_loop_end or norm_t in allowed_loops or norm_t in allowed_conditions:
                    continue
                if norm_t.startswith("{{") and norm_t.endswith("}}"):
                    inner = norm_t[2:-2].strip()
                    if not validate_jinja_expression(inner):
                        report["is_valid"] = False
                        report["errors"].append(f"Invalid Jinja expression inside tag: {raw_t}")
                        continue
                    if inner in expected_vars:
                        continue
                    # Known variable with display filters, e.g. {{ club_name | upper }}
                    base_var = inner.split("|", 1)[0].strip()
                    if "|" in inner and base_var in expected_vars and re.fullmatch(r"[\w\s|]+", inner):
                        continue
                    parts = inner.split(".")
                    if len(parts) == 2 and parts[0] in [b.get("attrs", {}).get("itemAlias", "item") for b in editor_json.get("content", []) if b.get("type") == "repeatingTable"]:
                        continue
                    report["is_valid"] = False
                    report["errors"].append(
                        f"Unexpected or unauthorized Jinja tag in template DOCX: {raw_t}"
                    )
                else:
                    report["is_valid"] = False
                    report["errors"].append(
                        f"Unexpected or unauthorized Jinja tag in template DOCX: {raw_t}"
                    )

            # Check 4: UNUSED REQUIRED FIELDS CHECK (Strict Gate Requirement)
            for f in fields:
                if f.get("required") is True:
                    f_key = f.get("key")
                    is_used = f_key in docx_tags
                    if not is_used:
                        if _is_field_referenced_in_editor(editor_json, f_key):
                            is_used = True
                    if not is_used:
                        report["is_valid"] = False
                        report["errors"].append(
                            f"Required field '{f_key}' is defined in schema but not used anywhere in the template."
                        )

            # Check 5: Dry render with dummy data using sandboxed environment & 30s timeout
            dummy_ctx = _build_editor_dummy_context(schema, fields, editor_json)
            try:
                tpl = DocxTemplate(str(tmp_docx_path))
                safe_render_docx(tpl, dummy_ctx, timeout=30.0)
                report["stats"]["dry_render"] = "succeeded"
            except Exception as e:
                report["is_valid"] = False
                report["errors"].append(f"Dry render failed with Jinja error: {e}")

        finally:
            if tmp_docx_path.exists():
                tmp_docx_path.unlink()

        return report


def _is_field_referenced_in_editor(editor_json: dict[str, Any], field_key: str) -> bool:
    """Check if field is referenced in any TipTap block (fieldChip, infoTable, repeatingTable)."""
    blocks = editor_json.get("content", [])
    for b in blocks:
        b_type = b.get("type", "")
        attrs = b.get("attrs", {})
        if b_type == "repeatingTable":
            if attrs.get("listVariable") == field_key:
                return True
            for c in (attrs.get("columns") or []):
                if c.get("key") == field_key:
                    return True
        elif b_type == "infoTable":
            for r in (b.get("rows") or attrs.get("rows") or []):
                if r.get("field") == field_key or r.get("key") == field_key:
                    return True
        elif "content" in b:
            if _find_chip_recursive(b.get("content", []), field_key):
                return True
    return False


def _find_chip_recursive(nodes: list[dict[str, Any]], field_key: str) -> bool:
    for node in nodes:
        if node.get("type") == "fieldChip" and node.get("attrs", {}).get("fieldName") == field_key:
            return True
        if "content" in node and _find_chip_recursive(node["content"], field_key):
            return True
    return False


def rename_field_in_editor_json(editor_json: dict[str, Any], old_key: str, new_key: str) -> dict[str, Any]:
    """Recursively rename fieldName/field/key from old_key to new_key in editor JSON."""
    import copy
    updated = copy.deepcopy(editor_json)

    def _walk(node: Any):
        if isinstance(node, dict):
            n_type = node.get("type")
            attrs = node.get("attrs", {})
            if n_type == "fieldChip" and attrs.get("fieldName") == old_key:
                attrs["fieldName"] = new_key
                if attrs.get("label") == old_key:
                    attrs["label"] = new_key
            elif n_type == "infoTable":
                rows = node.get("rows") or attrs.get("rows") or []
                for r in rows:
                    if r.get("field") == old_key:
                        r["field"] = new_key
                    if r.get("key") == old_key:
                        r["key"] = new_key
            elif n_type == "repeatingTable":
                if attrs.get("listVariable") == old_key:
                    attrs["listVariable"] = new_key
                for col in (attrs.get("columns") or []):
                    if col.get("key") == old_key:
                        col["key"] = new_key
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for it in node:
                _walk(it)

    _walk(updated)
    return updated


def _build_editor_dummy_context(schema: TemplateSchema, fields: list[dict[str, Any]],
                               editor_json: dict[str, Any]) -> dict[str, Any]:
    """Generate comprehensive synthetic dummy context to safely dry-render compiled templates."""
    # Neutral sample values for the validation dry-render only.
    ctx: dict[str, Any] = {
        "club_name": "Sample Club",
        "club_short": "CLUB",
        "institute_name": "SVNIT",
        "institute_short": "SVNIT",
        "chapter_code": "0/00",
        "head_of_account": "0/00",
        "academic_year": "2026-27",
        "document_date": "15/10/2026",
        "today_str": "15/10/2026",
        "ref_no": "CLUB/26-27/DOC/001",
        "department": "Department",
        "department_short": "DEPT",
        "club_footer": "Sample Club · SVNIT",
        "approval_chain": [{"name": "", "designation": ""}] * 3,
    }

    # Generate dummy values for every defined field based on its type
    for f in fields:
        f_key = f.get("key")
        f_type = f.get("type", "text")
        if not f_key:
            continue

        label = f.get("label") or f_key.replace("_", " ").title()
        if f_type == "text":
            ctx[f_key] = f"[{label}]"
        elif f_type == "longtext":
            ctx[f_key] = f"[{label}: text entered when the document is created]"
        elif f_type == "int":
            ctx[f_key] = 100
        elif f_type == "money":
            ctx[f_key] = fn_format_inr(Decimal("50000"))
        elif f_type == "date":
            ctx[f_key] = "15/10/2026"
        elif f_type == "date_range":
            ctx[f_key] = "15/10/2026 - 16/10/2026"
        elif f_type == "time_range":
            ctx[f_key] = "10:00 AM to 05:00 PM"
        elif f_type == "enum":
            vals = f.get("values") or ["Default Option"]
            ctx[f_key] = vals[0]
        elif f_type == "person_ref":
            ctx[f_key] = "Demo Person (Student Coordinator)"
        elif f_type == "table":
            # Find repeating table in editor_json to identify column structure
            cols = []
            for b in editor_json.get("content", []):
                if b.get("type") == "repeatingTable" and b.get("attrs", {}).get("listVariable") == f_key:
                    cols = b.get("attrs", {}).get("columns", [])
                    break
            if not cols:
                cols = [{"key": "name"}, {"key": "amount"}]

            dummy_rows = []
            for idx in (1, 2, 3):
                row_dict = {}
                for col in cols:
                    ckey = col.get("key", "col")
                    if "amount" in ckey or "cost" in ckey or "price" in ckey:
                        row_dict[ckey] = fn_format_inr(Decimal(str(idx * 25000)))
                    else:
                        row_dict[ckey] = f"Sample {ckey.replace('_', ' ').title()} {idx}"
                dummy_rows.append(row_dict)
            ctx[f_key] = dummy_rows

    # Also compute any total fields
    for f in fields:
        if f.get("computed"):
            fn_name = f["computed"].get("function")
            args = f["computed"].get("args", {})
            if fn_name == "sum":
                items_key = args.get("items", "").lstrip("$")
                field_name = args.get("field", "amount")
                items = ctx.get(items_key, [])
                total_val = Decimal("0")
                for it in items:
                    raw_val = it.get(field_name, 0)
                    clean_val = str(raw_val).replace(",", "").replace("INR", "").replace("₹", "").strip()
                    try:
                        total_val += Decimal(clean_val)
                    except Exception:
                        pass
                if f.get("format") == "inr":
                    ctx[f["key"]] = fn_format_inr(total_val)
                else:
                    ctx[f["key"]] = str(total_val)

    # Scan editor_json for any repeating tables (both legacy and native table nodes)
    migrated_json = migrate_template_content(editor_json) if editor_json else {"type": "doc", "content": []}
    for b in migrated_json.get("content", []):
        attrs = b.get("attrs", {})
        is_repeat = (
            b.get("type") == "repeatingTable"
            or (b.get("type") == "table" and (attrs.get("blockType") == "repeatingTable" or "repeating" in str(attrs.get("class", ""))))
        )
        if is_repeat:
            list_var = attrs.get("listVariable") or "budget_items"
            if list_var not in ctx or not isinstance(ctx[list_var], list):
                cols = attrs.get("columns") or [
                    {"key": "description", "label": "Item Description"},
                    {"key": "amount", "label": "Amount (INR)"},
                ]
                dummy_rows = []
                for idx in (1, 2, 3):
                    row_dict = {}
                    for col in cols:
                        ckey = col.get("key", "col")
                        if "amount" in ckey or "cost" in ckey or "price" in ckey:
                            row_dict[ckey] = fn_format_inr(Decimal(str(idx * 25000)))
                        else:
                            row_dict[ckey] = f"Sample {ckey.replace('_', ' ').title()} {idx}"
                    dummy_rows.append(row_dict)
                ctx[list_var] = dummy_rows

            tot_var = attrs.get("totalVarName") or f"total_{list_var}_amount"
            if tot_var not in ctx:
                ctx[tot_var] = fn_format_inr(Decimal("150000"))

    # Ensure all fieldChips in editor_json have a default value in ctx
    def _extract_chips(node: Any):
        if not isinstance(node, dict):
            return
        if node.get("type") == "fieldChip":
            fn = node.get("attrs", {}).get("fieldName")
            if fn and (fn not in ctx or ctx[fn] is None):
                label = node.get("attrs", {}).get("label") or fn.replace("_", " ").title()
                ctx[fn] = f"Demo {label}"
        for child in node.get("content", []):
            _extract_chips(child)

    _extract_chips(migrated_json)
    if editor_json and isinstance(editor_json, dict):
        _extract_chips(editor_json)

    # Ensure all schema fields have a default value to satisfy StrictUndefined
    for f_schema in schema.fields:
        if f_schema.key not in ctx or ctx[f_schema.key] is None:
            ctx[f_schema.key] = ""

    return ctx

