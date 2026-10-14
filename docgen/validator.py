"""Template validator: ensures DOCX tags match schema and renders succeed."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from docgen.schema import TemplateSchema, load_schema


class ValidationResult:
    def __init__(self, template_id: str):
        self.template_id = template_id
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def __repr__(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        return f"ValidationResult({self.template_id}: {status}, errors={len(self.errors)}, warnings={len(self.warnings)})"

    def summary(self) -> str:
        lines = [f"Template: {self.template_id}"]
        lines.append(f"  Status: {'VALID [OK]' if self.is_valid else 'INVALID [FAIL]'}")
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        return "\n".join(lines)


def extract_docx_tags(docx_path: str | Path) -> set[str]:
    """Extract all Jinja2 template tags from a DOCX file."""
    import zipfile
    tags = set()
    
    with zipfile.ZipFile(str(docx_path)) as zf:
        for name in zf.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                xml_content = zf.read(name).decode("utf-8", errors="ignore")
                
                # Match {{ variable }} patterns
                var_pattern = re.compile(r'\{\{[\s]*([a-zA-Z_][a-zA-Z0-9_.]*)[\s]*\}\}')
                for match in var_pattern.finditer(xml_content):
                    tag = match.group(1).strip()
                    if tag not in ('if', 'else', 'endif', 'for', 'endfor', 'set', 'block', 'endblock'):
                        tags.add(tag.split('.')[0])
                
                # Match {% for x in items %} patterns
                for_pattern = re.compile(r'\{%[\s]*for\s+\w+\s+in\s+(\w+)')
                for match in for_pattern.finditer(xml_content):
                    tags.add(match.group(1))
                
                # Match {%tr for x in items %} patterns
                tr_pattern = re.compile(r'\{%tr[\s]*for\s+\w+\s+in\s+(\w+)')
                for match in tr_pattern.finditer(xml_content):
                    tags.add(match.group(1))

                # Match {% if variable %} patterns
                if_pattern = re.compile(r'\{%[\s]*if\s+(\w+)')
                for match in if_pattern.finditer(xml_content):
                    tags.add(match.group(1))

    return tags


def validate_template(template_dir: str | Path) -> ValidationResult:
    """Validate a template directory (schema.yaml + template.docx)."""
    template_dir = Path(template_dir)
    schema_path = template_dir / "schema.yaml"
    docx_path = template_dir / "template.docx"

    # Load schema
    try:
        schema = load_schema(template_dir)
    except Exception as e:
        result = ValidationResult(template_dir.name)
        result.add_error(f"Failed to load schema.yaml: {e}")
        return result

    result = ValidationResult(schema.id)

    # Check DOCX exists
    if not docx_path.exists():
        result.add_error("template.docx not found")
        return result

    # Extract tags from DOCX
    try:
        docx_tags = extract_docx_tags(docx_path)
    except Exception as e:
        result.add_error(f"Failed to read template.docx: {e}")
        return result

    schema_keys = set(schema.all_field_keys())

    # Context variables that are always available (from renderer)
    builtin_vars = {
        "club_name", "club_short", "institute_name", "institute_short",
        "chapter_code", "head_of_account", "academic_year",
        "affiliating_institute_text", "student_head", "student_secretary",
        "chairperson", "faculty_chairman", "faculty_co_chairman",
        "venue_config", "submitted_to", "venue_tech_assistant",
        "venue_faculty_in_charge", "document_date", "today_str",
        "date_range_str", "budget_total", "budget_total_inr",
        "format_date", "format_date_range", "format_inr",
        "amount_in_words_inr", "ordinal", "line_total", "sum_field",
        "tax_amount", "total_with_tax", "Decimal",
        # Common loop variables
        "item", "winner", "bill", "attendee", "agenda", "action",
        "approval_chain", "budget_items", "winners", "bills",
        "other_reimbursements", "agenda_items", "action_items",
        "attendees", "absentees", "loop",
        # Other context
        "ref_no", "sr_no", "meeting", "approval_note",
        "purchase_order", "advance", "laboratory_office",
        # Repeat context
        "winner_name", "winner_position", "winner_amount",
        "winner_amount_words", "winner_roll_no", "winner_course_semester",
        "winner_mobile", "winner_bank_name_as_per_bank", "winner_bank_name",
        "winner_bank_branch", "winner_account_no", "winner_ifsc", "winner_pan",
    }

    # Check: every required schema field should be in the DOCX
    for key in schema.required_field_keys():
        if key not in docx_tags and key not in builtin_vars:
            # Not necessarily an error if it's a computed field
            field = schema.get_field(key)
            if field and not field.computed:
                result.add_warning(f"Required field '{key}' not found in template.docx")

    # Dry render with dummy data
    try:
        doc = DocxTemplate(str(docx_path))
        dummy_context = _build_dummy_context(schema)
        doc.render(dummy_context)
        result.add_warning("Dry render succeeded") if False else None
    except Exception as e:
        result.add_error(f"Dry render failed: {e}")

    return result


def _build_dummy_context(schema: TemplateSchema) -> dict[str, Any]:
    """Build a dummy context for dry rendering."""
    from decimal import Decimal
    from docgen.functions import (
        fn_format_date, fn_format_date_range, fn_format_inr,
        fn_amount_in_words_inr, fn_ordinal, fn_today, fn_line_total,
        fn_sum, fn_tax_amount, fn_total_with_tax,
    )

    ctx: dict[str, Any] = {
        "club_name": "ACM Student Chapter, SVNIT",
        "club_short": "ACM",
        "institute_name": "SVNIT",
        "institute_short": "SVNIT",
        "chapter_code": "6/52",
        "head_of_account": "6/52",
        "academic_year": "2026-27",
        "affiliating_institute_text": "SVNIT, Surat",
        "document_date": "12 October 2026",
        "today_str": "12 October 2026",
        "date_range_str": "14-15 October 2026",
        "ref_no": "ACM/26-27/TEST/001",
        "submitted_to": "Head of Department (CSE Dept.)",
        "budget_total": "1100",
        "budget_total_inr": "1,100.00",
        "purchase_order": "NiL",
        "advance": "NiL",
        "laboratory_office": "Student Council",
        "format_date": fn_format_date,
        "format_date_range": fn_format_date_range,
        "format_inr": fn_format_inr,
        "amount_in_words_inr": fn_amount_in_words_inr,
        "ordinal": fn_ordinal,
        "line_total": fn_line_total,
        "sum_field": fn_sum,
        "tax_amount": fn_tax_amount,
        "total_with_tax": fn_total_with_tax,
        "Decimal": Decimal,
        "sr_no": 1,
    }

    # Add dummy values for schema fields
    for field in schema.fields:
        if field.key not in ctx:
            if field.type == "int":
                ctx[field.key] = 100
            elif field.type == "money":
                ctx[field.key] = "1000.00"
            elif field.type == "date":
                ctx[field.key] = "2026-10-14"
            elif field.type == "date_range":
                ctx[field.key] = "14-15 October 2026"
            elif field.type == "table":
                ctx[field.key] = [{"item": "Test", "amount": "500", "name": "Test Person",
                                   "qty": 1, "unit_cost": "500", "topic": "Test Topic",
                                   "discussion": "Test", "decision": "Agreed",
                                   "task": "Test Task", "owner": "Test", "deadline": "2026-12-01",
                                   "account_no": "XXXX", "ifsc": "XXXX", "position": "1st"}]
            elif field.type == "enum":
                ctx[field.key] = field.values[0] if field.values else "Test"
            else:
                ctx[field.key] = f"Test {field.key}"

    # Add dummy personnel
    person_dummy = {"name": "Test Person", "admission_no": "U22CS001", "branch": "CSE",
                    "mobile": "XXXX", "email": "test@test.com",
                    "roles": {"permission_letter": "Test Role"}}
    ctx["student_head"] = person_dummy
    ctx["student_secretary"] = person_dummy
    ctx["chairperson"] = person_dummy
    ctx["faculty_chairman"] = person_dummy
    ctx["faculty_co_chairman"] = person_dummy
    ctx["venue_tech_assistant"] = person_dummy
    ctx["venue_faculty_in_charge"] = person_dummy
    ctx["venue_config"] = {"full_name": "Test Venue", "default_addressee": "Test"}

    # Dummy lists
    ctx["budget_items"] = [{"item": "Test Item", "amount": "500"}]
    ctx["winners"] = [{"position": "1st", "name": "Test", "roll_no": "U22CS001",
                       "course_semester": "B.Tech CSE 5th", "mobile": "XXXX",
                       "amount": "500", "bank": {"name_as_per_bank": "Test",
                       "bank_name": "SBI", "branch": "Surat", "account_no": "XXXX",
                       "ifsc": "XXXX", "pan": "XXXX"}}]
    ctx["bills"] = [{"supplier": {"name": "Test Supplier", "gst_no": "XXXX"},
                     "invoice_no": "INV001", "invoice_date": "2026-10-01",
                     "items": [{"name": "Banner", "qty": 1, "unit_cost": "800"}],
                     "payment": {"party": "Test", "account_no": "XXXX"}}]
    ctx["other_reimbursements"] = [{"name": "Test", "account_no": "XXXX",
                                    "ifsc": "XXXX", "amount": "500"}]
    ctx["attendees"] = ["Person A", "Person B"]
    ctx["absentees"] = ["Person C"]
    ctx["agenda_items"] = [{"topic": "Test", "discussion": "Discussed", "decision": "Agreed"}]
    ctx["action_items"] = [{"task": "Test Task", "owner": "Test", "deadline": "2026-12-01"}]
    ctx["approval_chain"] = ["Chairman F&SW", "Associate Dean SW", "Dean SW"]
    ctx["approval_note"] = {"no": "ACM/2026-27/SIH/001", "date": "2026-09-01"}

    # Winner-specific fields for repeat_per
    ctx["winner_name"] = "Test Winner"
    ctx["winner_position"] = "1st"
    ctx["winner_amount"] = "5000"
    ctx["winner_amount_words"] = "Rupees Five Thousand Only"
    ctx["winner_roll_no"] = "U22CS001"
    ctx["winner_course_semester"] = "B.Tech CSE 5th Semester"
    ctx["winner_mobile"] = "XXXX-XXX-XXXX"
    ctx["winner_bank_name_as_per_bank"] = "Test Person"
    ctx["winner_bank_name"] = "State Bank of India"
    ctx["winner_bank_branch"] = "Surat Main"
    ctx["winner_account_no"] = "XXXXXXXXXXXX"
    ctx["winner_ifsc"] = "SBIN0001234"
    ctx["winner_pan"] = "ABCDE1234F"

    # MoM fields
    ctx["meeting_title"] = "Test Meeting"
    ctx["meeting_date"] = "14 October 2026"
    ctx["meeting_start_time"] = "10:00 AM"
    ctx["meeting_end_time"] = "12:00 PM"
    ctx["chaired_by"] = "Test Chair"
    ctx["prepared_by"] = "Test Preparer"
    ctx["approved_by"] = "Test Approver"
    ctx["next_meeting_date"] = "21 October 2026"

    # Bill certificate specific
    ctx["approval_note_no"] = "ACM/2026-27/SIH/001"
    ctx["approval_note_date"] = "01 September 2026"
    ctx["bill_amount"] = "800.00"
    ctx["supplier_name"] = "Test Supplier"
    ctx["supplier_gst"] = "XXXXXXXXX"
    ctx["invoice_no"] = "INV-001"
    ctx["invoice_date"] = "01 October 2026"
    ctx["bill_items"] = [{"name": "Banner", "qty": 1, "unit_cost": "800", "line_total": "800"}]
    ctx["tax_type"] = "GST"
    ctx["tax_amount"] = "0"
    ctx["certifier_name"] = "Test Certifier"
    ctx["payment_party"] = "Test Party"
    ctx["payment_account_no"] = "XXXXXXXXXXXX"
    ctx["payment_holder"] = "Test Holder"
    ctx["payment_bank"] = "SBI"
    ctx["payment_branch"] = "Surat"
    ctx["payment_ifsc"] = "SBIN0001234"
    ctx["bill_total"] = "800.00"
    ctx["bill_total_with_tax"] = "800.00"
    ctx["bill_total_words"] = "Rupees Eight Hundred Only"

    return ctx


def validate_all_templates(templates_dir: str | Path = "templates") -> list[ValidationResult]:
    """Validate all templates in the templates directory."""
    templates_dir = Path(templates_dir)
    results = []
    for subdir in sorted(templates_dir.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("_"):
            schema_path = subdir / "schema.yaml"
            if schema_path.exists():
                results.append(validate_template(subdir))
    return results
