"""Schema loader: reads and validates schema.yaml for each template."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class FieldSchema(BaseModel):
    key: str
    type: str = "text"  # text, longtext, int, money, date, date_range, time_range, enum, person_ref, table
    required: bool | str = False  # True, False, or conditional expression string
    ask: Optional[str] = None
    defer_ok: bool = False
    source_allowed: list[str] = Field(default_factory=lambda: ["user", "config", "extracted_rule", "extracted_llm", "computed", "default"])
    default_from: Optional[str] = None
    computed: Optional[dict[str, Any]] = None  # {function: "fn_name", args: [...]}
    validate: Optional[str] = None  # regex or range
    mask: bool = False
    values: Optional[list[str]] = None  # for enum type
    format: Optional[str] = None  # e.g. "inr" for computed fields
    columns: Optional[list[Any]] = None  # for table type column definitions
    importance: str = "optional"  # essential | optional


class SectionSchema(BaseModel):
    id: str
    show_if: Optional[str] = None


class NumberingSchema(BaseModel):
    series: Optional[str] = None
    format: str  # e.g. "ACM/{short_year}/{series}/{seq:03d}"
    confirm: bool = True


class TemplateSchema(BaseModel):
    id: str
    name: str
    description: str = ""
    stage: str = "pre_event"  # pre_event, post_event, meeting
    triggers: list[str] = Field(default_factory=list)
    # When this template is useful (see server/app/core/recommend_rules.py)
    recommend: Optional[dict[str, Any]] = None
    letterhead: str = "acm"
    numbering: Optional[NumberingSchema] = None
    depends_on: list[str] = Field(default_factory=list)
    repeat_per: Optional[str] = None  # e.g. "winners" -> one doc per winner
    fields: list[FieldSchema] = Field(default_factory=list)
    sections: list[SectionSchema] = Field(default_factory=list)

    def required_field_keys(self) -> list[str]:
        """Return keys of fields where required is True (not conditional)."""
        return [f.key for f in self.fields if f.required is True]

    def essential_field_keys(self) -> list[str]:
        """Return keys of fields designated as essential."""
        return [f.key for f in self.fields if getattr(f, "importance", "optional") == "essential"]

    def optional_field_keys(self) -> list[str]:
        """Return keys of fields designated as optional."""
        return [f.key for f in self.fields if getattr(f, "importance", "optional") != "essential"]

    def all_field_keys(self) -> list[str]:
        return [f.key for f in self.fields]

    def get_field(self, key: str) -> Optional[FieldSchema]:
        for f in self.fields:
            if f.key == key:
                return f
        return None


def load_schema(template_dir: str | Path) -> TemplateSchema:
    """Load schema.yaml from a template directory or template name."""
    template_path = Path(template_dir)
    schema_path = template_path / "schema.yaml"
    if not schema_path.exists():
        fallback_path = Path("templates") / template_path / "schema.yaml"
        if fallback_path.exists():
            schema_path = fallback_path
        else:
            raise FileNotFoundError(f"No schema.yaml found in {template_path} or {fallback_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return TemplateSchema(**data)


def load_all_schemas(templates_dir: str | Path = "templates") -> dict[str, TemplateSchema]:
    """Load all schemas from the templates directory."""
    templates_dir = Path(templates_dir)
    schemas: dict[str, TemplateSchema] = {}
    for subdir in sorted(templates_dir.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("_"):
            schema_path = subdir / "schema.yaml"
            if schema_path.exists():
                schema = load_schema(subdir)
                schemas[schema.id] = schema
    return schemas
