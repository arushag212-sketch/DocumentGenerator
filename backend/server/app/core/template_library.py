"""Shared template library: templates defined as data in ``templates/library/*.json``.

Each spec is compiled by the same pipeline as user-made templates and installed as a
read-only, published system template that every club can use directly or fork and edit in
the Studio. Adding a document type means adding a JSON file, not code.

Spec shorthand (expanded to editor JSON here):
  {"type": "heading", "level": 1, "align": "center", "text": "EVENT PROPOSAL"}
  {"type": "paragraph", "text": "{{club_name}} proposes to conduct {{event_name}} ..."}
  {"type": "infoTable", "rows": [{"label": "Venue", "field": "venue"}]}
  {"type": "repeatingTable", ...attrs}, {"type": "signatureGrid", "signatures": [...]}
  any block may carry "showIf": "<field_key>" to appear only when that field has a value.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.template_compiler import TemplateCompiler

LIBRARY_DIR = Path(__file__).resolve().parents[3] / "templates" / "library"
_CHIP = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


def load_specs(directory: Path = LIBRARY_DIR) -> list[dict[str, Any]]:
    specs = []
    for path in sorted(directory.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec.setdefault("slug", path.stem)
        specs.append(spec)
    return specs


def _inline(text: str, fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Text with {{field}} markers -> TipTap text runs and field chips."""
    content: list[dict[str, Any]] = []
    pos = 0
    for m in _CHIP.finditer(text):
        if m.start() > pos:
            content.append({"type": "text", "text": text[pos:m.start()]})
        key = m.group(1)
        f = fields.get(key, {})
        content.append({
            "type": "fieldChip",
            "attrs": {
                "fieldName": key,
                "label": f.get("label") or key.replace("_", " ").title(),
                "fieldType": f.get("type", "text"),
            },
        })
        pos = m.end()
    if pos < len(text):
        content.append({"type": "text", "text": text[pos:]})
    return content


def spec_to_editor_json(spec: dict[str, Any]) -> dict[str, Any]:
    fields = {f["key"]: f for f in spec.get("fields", [])}
    blocks: list[dict[str, Any]] = []
    for b in spec.get("blocks", []):
        b_type = b["type"]
        attrs: dict[str, Any] = {}
        if b.get("align"):
            attrs["textAlign"] = b["align"]
        if b.get("showIf"):
            attrs["showIf"] = b["showIf"]
        if b_type == "heading":
            attrs["level"] = b.get("level", 2)
            blocks.append({"type": "heading", "attrs": attrs, "content": _inline(b.get("text", ""), fields)})
        elif b_type == "paragraph":
            blocks.append({"type": "paragraph", "attrs": attrs, "content": _inline(b.get("text", ""), fields)})
        else:
            extra = {k: v for k, v in b.items() if k not in ("type", "align", "showIf")}
            blocks.append({"type": b_type, "attrs": {**attrs, **extra}})
    doc: dict[str, Any] = {"type": "doc", "content": blocks}
    if spec.get("design"):
        doc["design_settings"] = spec["design"]
    return doc


def install_library(db: Session, storage: Any, specs: list[dict[str, Any]] | None = None) -> int:
    """Compile every library spec and upsert it as a published system template."""
    from server.app.models import Template, TemplateVersion

    installed = 0
    for spec in specs if specs is not None else load_specs():
        slug = spec["slug"]
        editor_json = spec_to_editor_json(spec)
        docx_bytes, schema_yaml, report = TemplateCompiler.compile(
            editor_json=editor_json,
            fields=spec.get("fields", []),
            template_meta={
                "id": slug,
                "name": spec["name"],
                "category": spec.get("category", "Club Documents"),
                "description": spec.get("description", ""),
                "stage": spec.get("stage", "custom"),
                "numbering_series": spec.get("numbering_series", "DOC"),
                "triggers": spec.get("triggers"),
                "recommend": spec.get("recommend"),
            },
            club_slug="club",
            letterhead_cfg={"banner_placeholder": True},
            design_settings=spec.get("design"),
        )
        if not report.get("is_valid"):
            raise ValueError(f"Library template '{slug}' failed validation: {report.get('errors')}")

        key = storage.save(f"templates/{slug}_v1.docx", docx_bytes)
        docx_path = str(storage.local_path(key)) if hasattr(storage, "local_path") else key

        tmpl = db.query(Template).filter(Template.slug == slug, Template.club_id.is_(None)).first()
        if tmpl is None:
            tmpl = Template(
                club_id=None,
                slug=slug,
                name=spec["name"],
                description=spec.get("description", ""),
                category=spec.get("category", "Club Documents"),
                stage=spec.get("stage", "custom"),
                is_system=True,
                status="published",
            )
            db.add(tmpl)
            db.flush()
        tmpl.name = spec["name"]
        tmpl.description = spec.get("description", "")
        tmpl.category = spec.get("category", "Club Documents")
        tmpl.stage = spec.get("stage", "custom")
        tmpl.status = "published"

        ver = db.query(TemplateVersion).filter(
            TemplateVersion.template_id == tmpl.id, TemplateVersion.version_no == 1
        ).first()
        if ver is None:
            ver = TemplateVersion(
                id=str(uuid.uuid4()),
                template_id=tmpl.id,
                version_no=1,
                created_by=None,
                change_note="Template library",
            )
            db.add(ver)
        ver.editor_json = editor_json
        ver.schema_yaml = schema_yaml
        ver.docx_storage_key = docx_path
        ver.validation_report = report
        db.flush()
        tmpl.current_version_id = ver.id
        installed += 1
    db.flush()
    return installed
