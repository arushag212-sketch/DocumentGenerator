"""Document renderer: fills DOCX templates with data and converts to PDF."""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from docgen.config import ClubConfig, load_config
from docgen.functions import get_function
from docgen.models import EventRecord
from docgen.schema import TemplateSchema, load_schema

BLANK_LINE: str = "____________________"


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


def safe_render_docx(tpl: DocxTemplate, context: dict[str, Any], timeout: float = 30.0) -> None:
    """Render a DocxTemplate with SandboxedEnvironment, StrictUndefined, 30s timeout, and 1000-row cap."""
    safe_cap_collections(context, max_items=1000)

    env = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)

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



class RenderResult:
    """Result of rendering a document."""

    def __init__(self, docx_path: Path, pdf_path: Optional[Path] = None,
                 template_id: str = "", version: int = 1, converter: str = ""):
        self.docx_path = docx_path
        self.pdf_path = pdf_path
        self.template_id = template_id
        self.version = version
        self.converter = converter

    def __repr__(self) -> str:
        return f"RenderResult(docx={self.docx_path}, pdf={self.pdf_path}, converter={self.converter})"


class Renderer:
    """Renders DOCX templates with event record data."""

    def __init__(self, templates_dir: str | Path = "templates",
                 config: ClubConfig | None = None,
                 outputs_dir: str | Path = "outputs",
                 template_source: Any | None = None):
        self.templates_dir = Path(templates_dir)
        self.config = config or load_config()
        self.outputs_dir = Path(outputs_dir)
        if template_source is not None:
            self.template_source = template_source
        else:
            from docgen.sources import FileSystemTemplateSource
            self.template_source = FileSystemTemplateSource(self.templates_dir)

    def render(self, template_id: str, event: EventRecord,
               extra_context: dict[str, Any] | None = None,
               output_dir: Path | None = None,
               version: int = 1,
               convert_pdf: bool = True) -> RenderResult:
        """Render a template with event data.

        Args:
            template_id: The template folder name or slug (e.g., 'permission_letter')
            event: The canonical event record
            extra_context: Additional template variables (e.g., winner data for repeat_per)
            output_dir: Override output directory
            version: Version number for the output filename
            convert_pdf: Whether to convert the rendered DOCX to PDF (raises if soffice missing)

        Returns:
            RenderResult with paths to generated files
        """
        schema = self.template_source.get_template_schema(template_id)
        docx_source = self.template_source.get_template_docx_stream(template_id)

        # Build context from event record
        context = self._build_context(event, schema, extra_context)

        # Render DOCX with SandboxedEnvironment and StrictUndefined (autoescape=True)
        if hasattr(docx_source, "seek"):
            docx_source.seek(0)
            doc = DocxTemplate(docx_source)
        else:
            doc = DocxTemplate(str(docx_source))
        safe_render_docx(doc, context, timeout=30.0)

        # Output path
        if output_dir is None:
            slug = self._slugify(event.event_name.value or "unnamed")
            output_dir = self.outputs_dir / slug
        output_dir.mkdir(parents=True, exist_ok=True)

        docx_filename = f"{template_id}_v{version}.docx"
        docx_path = output_dir / docx_filename
        doc.save(str(docx_path))

        # Convert to PDF if requested
        pdf_path = None
        converter_used = ""
        if convert_pdf:
            pdf_path, converter_used = self._convert_to_pdf(docx_path)

        return RenderResult(
            docx_path=docx_path,
            pdf_path=pdf_path,
            template_id=template_id,
            version=version,
            converter=converter_used,
        )

    def _build_context(self, event: EventRecord, schema: TemplateSchema,
                       extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build the template context from event data + config + computed values."""
        ctx = event.flat_dict()

        # Add config values
        ctx["club_name"] = self.config.club_name
        ctx["club_short"] = self.config.club_short
        ctx["institute_name"] = self.config.institute_name
        ctx["institute_short"] = self.config.institute_short
        ctx["chapter_code"] = self.config.chapter_code
        ctx["head_of_account"] = self.config.head_of_account
        ctx["academic_year"] = event.academic_year.value or self.config.academic_year
        ctx["affiliating_institute_text"] = self.config.affiliating_institute_text

        # Add defaults from config
        for key, value in self.config.defaults.items():
            if key not in ctx or ctx[key] is None:
                ctx[key] = value

        # Add personnel
        if self.config.student_head:
            ctx["student_head"] = self.config.student_head.model_dump()
        if self.config.student_secretary:
            ctx["student_secretary"] = self.config.student_secretary.model_dump()
        if self.config.chairperson:
            ctx["chairperson"] = self.config.chairperson.model_dump()
        if self.config.faculty_chairman:
            ctx["faculty_chairman"] = self.config.faculty_chairman.model_dump()
        if self.config.faculty_co_chairman:
            ctx["faculty_co_chairman"] = self.config.faculty_co_chairman.model_dump()

        # Ensure safe defaults for personnel structures so StrictUndefined never raises
        for role_name in ("student_head", "student_secretary", "chairperson"):
            if role_name not in ctx or not isinstance(ctx[role_name], dict):
                ctx[role_name] = {"name": "", "admission_no": "", "branch": "", "mobile": "", "email": "", "designation": "", "roles": {}}
            else:
                for attr in ("name", "admission_no", "branch", "mobile", "email", "designation"):
                    if attr not in ctx[role_name] or ctx[role_name][attr] is None:
                        ctx[role_name][attr] = ""

        for role_name in ("faculty_chairman", "faculty_co_chairman"):
            if role_name not in ctx or not isinstance(ctx[role_name], dict):
                ctx[role_name] = {"name": "", "mobile": "", "email": "", "department": "", "designation": "", "roles": {}}
            else:
                for attr in ("name", "mobile", "email", "department", "designation"):
                    if attr not in ctx[role_name] or ctx[role_name][attr] is None:
                        ctx[role_name][attr] = ""

        # Add venue info
        venue_name = ctx.get("venue", "")
        if venue_name:
            venue_config = self.config.get_venue(venue_name)
            if venue_config:
                ctx["venue_config"] = venue_config.model_dump()
                ctx["submitted_to"] = venue_config.default_addressee
                if venue_config.tech_assistant:
                    ctx["venue_tech_assistant"] = venue_config.tech_assistant.model_dump()
                if venue_config.faculty_in_charge:
                    ctx["venue_faculty_in_charge"] = venue_config.faculty_in_charge.model_dump()

        for v_role in ("venue_tech_assistant", "venue_faculty_in_charge"):
            if v_role not in ctx or not isinstance(ctx[v_role], dict):
                ctx[v_role] = {"name": "", "mobile": "", "phone": "", "designation": "", "roles": {"permission_letter": ""}}
            else:
                if "name" not in ctx[v_role] or ctx[v_role]["name"] is None:
                    ctx[v_role]["name"] = ""
                if "mobile" not in ctx[v_role] or ctx[v_role]["mobile"] is None:
                    ctx[v_role]["mobile"] = ""
                if "roles" not in ctx[v_role] or not isinstance(ctx[v_role]["roles"], dict):
                    ctx[v_role]["roles"] = {"permission_letter": ""}
                elif "permission_letter" not in ctx[v_role]["roles"] or ctx[v_role]["roles"]["permission_letter"] is None:
                    ctx[v_role]["roles"]["permission_letter"] = ""

        # Document-specific reference number handling (Permission Letter uses room_ref_no if set)
        if schema.id == "permission_letter" and ctx.get("room_ref_no"):
            ctx["ref_no"] = ctx["room_ref_no"]

        # Unpack approval note properties if available in event
        if isinstance(ctx.get("approval_note"), dict):
            if not ctx.get("approval_note_no"):
                ctx["approval_note_no"] = ctx["approval_note"].get("ref_no") or ctx["approval_note"].get("no")
            if not ctx.get("approval_note_date"):
                ctx["approval_note_date"] = ctx["approval_note"].get("date")

        # Unpack first bill if rendering bill_certificate and bill properties exist in event
        if schema.id == "bill_certificate" and ctx.get("bills") and isinstance(ctx["bills"], list) and len(ctx["bills"]) > 0:
            first_bill = ctx["bills"][0]
            if isinstance(first_bill, dict):
                if not ctx.get("supplier_name") and first_bill.get("supplier"):
                    ctx["supplier_name"] = first_bill["supplier"].get("name")
                    ctx["supplier_gst"] = first_bill["supplier"].get("gst_no")
                if not ctx.get("invoice_no"):
                    ctx["invoice_no"] = first_bill.get("invoice_no")
                if not ctx.get("invoice_date"):
                    ctx["invoice_date"] = first_bill.get("invoice_date")
                if not ctx.get("bill_items"):
                    ctx["bill_items"] = first_bill.get("items")
                if not ctx.get("bill_amount"):
                    # compute sum of items
                    items = first_bill.get("items", [])
                    tot = sum(
                        (Decimal(str(it.get("unit_cost", 0))) * Decimal(str(it.get("qty", 1))) if isinstance(it, dict) else Decimal(0))
                        for it in items
                    ) if items else Decimal("0")
                    ctx["bill_amount"] = tot
                if not ctx.get("payment_party") and first_bill.get("payment"):
                    pay = first_bill["payment"]
                    ctx["payment_party"] = pay.get("party")
                    ctx["payment_account_no"] = pay.get("account_no")
                    ctx["payment_holder"] = pay.get("holder")
                    ctx["payment_bank"] = pay.get("bank")
                    ctx["payment_branch"] = pay.get("branch")
                    ctx["payment_ifsc"] = pay.get("ifsc")
                if not ctx.get("tax_type"):
                    ctx["tax_type"] = first_bill.get("tax_type")
                if not ctx.get("tax_amount") and not ctx.get("tax_rate_or_amount"):
                    ctx["tax_amount"] = first_bill.get("tax_rate_or_amount") or first_bill.get("tax_amount")
                if not ctx.get("ref_no"):
                    ctx["ref_no"] = first_bill.get("invoice_no")

        # Unpack first winner if rendering prize_money_receipt and winners exist in event
        if schema.id == "prize_money_receipt" and ctx.get("winners") and isinstance(ctx["winners"], list) and len(ctx["winners"]) > 0:
            first_w = ctx["winners"][0]
            if isinstance(first_w, dict):
                if not ctx.get("winner_name"):
                    ctx["winner_name"] = first_w.get("name")
                if not ctx.get("winner_position"):
                    ctx["winner_position"] = first_w.get("position")
                if not ctx.get("winner_amount"):
                    ctx["winner_amount"] = first_w.get("amount")
                if not ctx.get("winner_roll_no"):
                    ctx["winner_roll_no"] = first_w.get("roll_no")
                if not ctx.get("winner_course_semester"):
                    ctx["winner_course_semester"] = first_w.get("course_semester")
                if not ctx.get("winner_mobile"):
                    ctx["winner_mobile"] = first_w.get("mobile")
                bank_info = first_w.get("bank")
                if isinstance(bank_info, dict):
                    if not ctx.get("winner_bank_name_as_per_bank"):
                        ctx["winner_bank_name_as_per_bank"] = bank_info.get("name_as_per_bank")
                    if not ctx.get("winner_bank_name"):
                        ctx["winner_bank_name"] = bank_info.get("bank_name")
                    if not ctx.get("winner_bank_branch"):
                        ctx["winner_bank_branch"] = bank_info.get("branch")
                    if not ctx.get("winner_account_no"):
                        ctx["winner_account_no"] = bank_info.get("account_no")
                    if not ctx.get("winner_ifsc"):
                        ctx["winner_ifsc"] = bank_info.get("ifsc")
                    if not ctx.get("winner_pan"):
                        ctx["winner_pan"] = bank_info.get("pan")

        # Unpack meeting block if rendering mom and meeting exists in event
        if schema.id == "mom":
            if isinstance(ctx.get("meeting"), dict):
                m = ctx["meeting"]
                if not ctx.get("meeting_title"):
                    ctx["meeting_title"] = m.get("title")
                if not ctx.get("meeting_date"):
                    ctx["meeting_date"] = m.get("date")
                if not ctx.get("meeting_start_time"):
                    ctx["meeting_start_time"] = m.get("start_time")
                if not ctx.get("meeting_end_time"):
                    ctx["meeting_end_time"] = m.get("end_time")
                if not ctx.get("chaired_by"):
                    ctx["chaired_by"] = m.get("chaired_by")
                if not ctx.get("attendees"):
                    ctx["attendees"] = m.get("attendees")
                if not ctx.get("absentees"):
                    ctx["absentees"] = m.get("absentees")
                if not ctx.get("agenda_items"):
                    ctx["agenda_items"] = m.get("agenda_items")
                if not ctx.get("action_items"):
                    ctx["action_items"] = m.get("action_items")
                if not ctx.get("venue"):
                    ctx["venue"] = m.get("venue")
                if m.get("ref_no"):
                    ctx["ref_no"] = m.get("ref_no")
                elif ctx.get("mom_ref_no"):
                    ctx["ref_no"] = ctx["mom_ref_no"]
                if not ctx.get("prepared_by"):
                    ctx["prepared_by"] = m.get("prepared_by")
                if not ctx.get("approved_by"):
                    ctx["approved_by"] = m.get("approved_by")
            elif ctx.get("mom_ref_no"):
                ctx["ref_no"] = ctx["mom_ref_no"]

            # Guarantee that MoM uses the MOM numbering series, never reusing the event's SIH or other series
            if "MOM" not in str(ctx.get("ref_no", "")):
                ay = ctx.get("academic_year", self.config.academic_year)
                cs = self.config.club_short
                ctx["ref_no"] = f"{cs}/{ay}/MOM/001"

        # Process computed fields
        for field in schema.fields:
            if field.computed:
                fn_name = field.computed.get("function", "")
                fn_args = field.computed.get("args", {})
                try:
                    fn = get_function(fn_name)
                    # Resolve args from context
                    resolved_args = {}
                    for arg_key, arg_val in fn_args.items():
                        if isinstance(arg_val, str) and arg_val.startswith("$"):
                            resolved_args[arg_key] = ctx.get(arg_val[1:])
                        else:
                            resolved_args[arg_key] = arg_val
                    ctx[field.key] = fn(**resolved_args)
                except Exception as e:
                    ctx[field.key] = f"[COMPUTE ERROR: {e}]"

            # Apply default_from config
            if field.default_from and (field.key not in ctx or ctx[field.key] is None):
                parts = field.default_from.split(".")
                val: Any = self.config
                for part in parts[1:]:  # skip 'config'
                    if isinstance(val, dict):
                        val = val.get(part)
                    else:
                        val = getattr(val, part, None) if hasattr(val, part) else None
                if field.key == "submitted_to":
                    venue_key = ctx.get("venue")
                    v_conf = None
                    if isinstance(val, dict):
                        if venue_key and venue_key in val:
                            v_conf = val[venue_key]
                        elif val:
                            for vk, vv in val.items():
                                if venue_key and (vk.lower() in str(venue_key).lower() or (getattr(vv, "short_name", "") and getattr(vv, "short_name", "").lower() in str(venue_key).lower())):
                                    v_conf = vv
                                    break
                            if not v_conf:
                                v_conf = next(iter(val.values()), None)
                    if v_conf:
                        val = getattr(v_conf, "default_addressee", None) or getattr(v_conf, "full_name", None)
                    elif isinstance(val, dict):
                        val = "The Head of Department"
                elif field.type == "text" and isinstance(val, (dict, list)):
                    val = None
                if val is not None:
                    ctx[field.key] = val

        # Add formatted helpers and dates to context as evaluated values, never raw functions
        from docgen.functions import (
            fn_format_date, fn_format_date_range, fn_format_inr,
            fn_amount_in_words_inr, fn_ordinal, fn_today, fn_line_total,
            fn_sum, fn_tax_amount, fn_total_with_tax,
        )
        # Merge extra context (e.g., custom form data, winner data for repeat_per)
        if extra_context:
            for ek, ev in extra_context.items():
                if ev is not None:
                    ctx[ek] = ev

        # Ensure safe defaults for nested winner and reimbursement data structures
        if "winners" in ctx and isinstance(ctx["winners"], list):
            clean_winners = []
            for w in ctx["winners"]:
                w_dict = w.model_dump() if hasattr(w, "model_dump") else dict(w)
                BLANK_LINE = "____________________"
                bank_dict = w_dict.get("bank")
                if not isinstance(bank_dict, dict) or not bank_dict:
                    bank_dict = {
                        "account_no": BLANK_LINE,
                        "name_as_per_bank": w_dict.get("name", "") or BLANK_LINE,
                        "bank_name": BLANK_LINE,
                        "branch": BLANK_LINE,
                        "ifsc": BLANK_LINE,
                        "pan": BLANK_LINE,
                    }
                else:
                    bank_dict = dict(bank_dict)
                    for bk in ("account_no", "name_as_per_bank", "bank_name", "branch", "ifsc", "pan"):
                        if bk not in bank_dict or bank_dict[bk] is None or str(bank_dict[bk]).strip() in ("", "None"):
                            bank_dict[bk] = w_dict.get("name", "") if bk == "name_as_per_bank" else BLANK_LINE
                w_dict["bank"] = bank_dict
                for wk in ("roll_no", "course_semester", "mobile"):
                    if wk not in w_dict or w_dict[wk] is None or str(w_dict[wk]).strip() in ("", "None"):
                        w_dict[wk] = BLANK_LINE
                clean_winners.append(w_dict)
            ctx["winners"] = clean_winners

        if "winner" in ctx and ctx["winner"]:
            BLANK_LINE = "____________________"
            w = ctx["winner"]
            w_dict = w.model_dump() if hasattr(w, "model_dump") else dict(w)
            bank_dict = w_dict.get("bank")
            if not isinstance(bank_dict, dict) or not bank_dict:
                bank_dict = {
                    "account_no": BLANK_LINE,
                    "name_as_per_bank": w_dict.get("name", "") or BLANK_LINE,
                    "bank_name": BLANK_LINE,
                    "branch": BLANK_LINE,
                    "ifsc": BLANK_LINE,
                    "pan": BLANK_LINE,
                }
            else:
                bank_dict = dict(bank_dict)
                for bk in ("account_no", "name_as_per_bank", "bank_name", "branch", "ifsc", "pan"):
                    if bk not in bank_dict or bank_dict[bk] is None or str(bank_dict[bk]).strip() in ("", "None"):
                        bank_dict[bk] = w_dict.get("name", "") if bk == "name_as_per_bank" else BLANK_LINE
            w_dict["bank"] = bank_dict
            for wk in ("roll_no", "course_semester", "mobile"):
                if wk not in w_dict or w_dict[wk] is None or str(w_dict[wk]).strip() in ("", "None"):
                    w_dict[wk] = BLANK_LINE
            ctx["winner"] = w_dict

        if "other_reimbursements" in ctx and isinstance(ctx["other_reimbursements"], list):
            clean_reimb = []
            for r in ctx["other_reimbursements"]:
                r_dict = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                for rk in ("name", "account_no", "ifsc", "amount"):
                    if rk not in r_dict or r_dict[rk] is None:
                        r_dict[rk] = ""
                clean_reimb.append(r_dict)
            ctx["other_reimbursements"] = clean_reimb

        if "budget_items" in ctx and isinstance(ctx["budget_items"], list):
            clean_budget = []
            for b in ctx["budget_items"]:
                b_dict = b.model_dump() if hasattr(b, "model_dump") else dict(b)
                for bk in ("item", "amount"):
                    if bk not in b_dict or b_dict[bk] is None:
                        b_dict[bk] = ""
                clean_budget.append(b_dict)
            ctx["budget_items"] = clean_budget

        # Compute bill totals and line totals if bill_items present
        if ctx.get("bill_items") and isinstance(ctx["bill_items"], list):
            enriched_items = []
            bill_subtotal = Decimal("0")
            for it in ctx["bill_items"]:
                if isinstance(it, dict):
                    qty = int(it.get("qty", 1))
                    unit_cost = Decimal(str(it.get("unit_cost", 0)))
                    line_tot = fn_line_total(qty, unit_cost)
                    bill_subtotal += line_tot
                    enriched_it = dict(it)
                    enriched_it["line_total"] = line_tot
                    enriched_items.append(enriched_it)
                else:
                    enriched_items.append(it)
            ctx["bill_items"] = enriched_items
            ctx["bill_total"] = bill_subtotal

            # Tax and total with tax
            raw_tax = ctx.get("tax_rate_or_amount") or ctx.get("tax_amount")
            if raw_tax is not None and not callable(raw_tax):
                try:
                    tax_dec = Decimal(str(raw_tax))
                except Exception:
                    tax_dec = Decimal("0")
            else:
                tax_dec = Decimal("0")
            ctx["tax_amount"] = tax_dec
            ctx["bill_total_with_tax"] = fn_total_with_tax(bill_subtotal, tax_dec)

        # Compute budget total if budget items present
        if ctx.get("budget_items"):
            ctx["budget_total"] = fn_sum(ctx["budget_items"], "amount")
            ctx["budget_total_inr"] = fn_format_inr(ctx["budget_total"])

        # Compute bill summary totals: winners (prize money) + other reimbursements
        prize_tot = Decimal("0")
        if ctx.get("winners"):
            prize_tot = fn_sum(ctx["winners"], "amount")
        other_tot = Decimal("0")
        if ctx.get("other_reimbursements"):
            other_tot = fn_sum(ctx["other_reimbursements"], "amount")
        
        ctx["prize_total"] = prize_tot
        ctx["prize_total_inr"] = fn_format_inr(prize_tot)
        ctx["other_total"] = other_tot
        ctx["other_total_inr"] = fn_format_inr(other_tot)
        
        grand_total = prize_tot + other_tot
        ctx["grand_total"] = grand_total
        ctx["grand_total_inr"] = fn_format_inr(grand_total)

        # Date formatting
        if ctx.get("date_start") and ctx.get("date_end"):
            ctx["date_range_str"] = fn_format_date_range(ctx["date_start"], ctx["date_end"])
            if not ctx.get("dates"):
                ctx["dates"] = ctx["date_range_str"]
        elif ctx.get("date_start"):
            ctx["date_range_str"] = fn_format_date(ctx["date_start"])
            if not ctx.get("dates"):
                ctx["dates"] = ctx["date_range_str"]
        elif ctx.get("dates"):
            ctx["date_range_str"] = fn_format_date(str(ctx["dates"]))

        from docgen.functions import fn_format_time
        if ctx.get("time_start"):
            ctx["time_start"] = fn_format_time(ctx["time_start"])
        if ctx.get("time_end"):
            ctx["time_end"] = fn_format_time(ctx["time_end"])

        # Permission Letter Schedule & Description Formatting per official institutional sample
        if schema.id == "permission_letter":
            t_start = ctx.get("time_start")
            t_end = ctx.get("time_end")
            d_range = ctx.get("date_range_str", "")
            if t_start and t_end and d_range:
                if " to " not in d_range:
                    ctx["date_range_str"] = f"{d_range}, {t_start} to {t_end}"

            # Brief Description includes the reusable clause from sample:
            # "We request permission to use {venue} on {date} from {start} to {end} for conducting the {event}."
            desc_val = str(ctx.get("description", "") or "").strip()
            if "We request permission to use" not in desc_val:
                venue_val = ctx.get("venue", "the venue")
                evt_val = ctx.get("event_name", "the event")
                date_val = fn_format_date(ctx.get("date_start") or ctx.get("dates") or ctx.get("document_date"))
                time_clause = f"from {t_start} to {t_end}" if (t_start and t_end) else ""
                clause = f"We request permission to use {venue_val} on {date_val} {time_clause} for conducting the {evt_val}.".replace("  ", " ")
                if desc_val:
                    ctx["description"] = f"{desc_val}\n\n{clause}"
                else:
                    ctx["description"] = clause

        # Formatted date for document header (always default to today, standardized to DD/MM/YYYY)
        raw_doc_date = ctx.get("document_date")
        if not raw_doc_date:
            ctx["document_date"] = fn_today()
        else:
            ctx["document_date"] = fn_format_date(raw_doc_date)


        # Standardize all schema date fields to DD/MM/YYYY
        for f in schema.fields:
            if f.type == "date" and ctx.get(f.key):
                ctx[f.key] = fn_format_date(ctx[f.key])

        # Requirement 5: Money formatting must use ONLY the schema field type `money`
        # plus computed fields declared `format: inr`
        money_keys = {
            f.key for f in schema.fields 
            if f.type == "money" or (getattr(f, "format", None) == "inr")
        }
        for f in schema.fields:
            if getattr(f, "columns", None):
                for col in f.columns:
                    if isinstance(col, dict) and (col.get("type") == "money" or col.get("key") in ("amount", "price", "unit_cost", "line_total")):
                        money_keys.add(col.get("key"))
        # In bill_certificate, bill_total, tax_amount, bill_total_with_tax are money fields
        if schema.id == "bill_certificate":
            money_keys.update({"bill_total", "tax_amount", "bill_total_with_tax", "bill_amount", "unit_cost", "line_total"})
        elif schema.id == "bill_summary":
            money_keys.update({"prize_total", "other_total", "grand_total", "amount"})
        money_keys.add("amount")

        # Convert Decimal values (format strictly as INR if field is in money_keys, otherwise keep plain numeric string)
        ctx = self._convert_decimals(ctx, money_keys)

        # Ensure optional/missing schema fields have default blank lines for hand-filling
        BLANK_LINE = "____________________"
        for f in schema.fields:
            is_essential = getattr(f, "importance", "optional") == "essential"
            val = ctx.get(f.key)
            if not is_essential:
                # If optional field is empty or literal "None", render clean blank line for hand-filling
                if val is None or str(val).strip() in ("", "None", "null"):
                    if f.type in ("table",):
                        ctx[f.key] = [] if val is None else val
                    elif f.key in ("description", "objectives"):
                        # Keep empty string if unfilled (Permission Letter's venue clause carries meaning)
                        ctx[f.key] = ""
                    else:
                        ctx[f.key] = BLANK_LINE
            else:
                if f.key not in ctx or ctx[f.key] is None:
                    ctx[f.key] = ""

        # GLOBAL GUARD (Extended per Requirement 2 & W3.1):
        # 1. Any context value that is callable, a function/method repr, or contains "<function", "<bound", "object at 0x", "[AI-drafted" must raise.
        # 2. Any required field that is None or resolves to empty must raise.
        # 3. Any computed field that resolves to empty must raise.
        self._validate_rendered_context(ctx, schema)

        return ctx

    def _validate_rendered_context(self, ctx: dict[str, Any], schema: TemplateSchema) -> None:
        """Extended global guard enforcing data integrity on template variables."""
        def check_val(key_name: str, val: Any):
            if callable(val):
                raise ValueError(
                    f"Global guard violation: Context variable '{key_name}' in template '{schema.id}' is a callable function object ({val}). "
                    f"Computed fields must be evaluated to data, not passed as functions."
                )
            s_val = str(val)
            for bad_token in ["<function", "<bound", "object at 0x", "[AI-drafted"]:
                if bad_token in s_val:
                    token_desc = "function repr" if bad_token in ("<function", "<bound", "object at 0x") else "illegal token"
                    raise ValueError(
                        f"Global guard violation: Context variable '{key_name}' in template '{schema.id}' contains {token_desc} '{bad_token}': {s_val}"
                    )

        # Recursively check all context values for callable or function representations
        def walk_ctx(d: Any, prefix: str = ""):
            if isinstance(d, dict):
                for k, v in d.items():
                    k_full = f"{prefix}.{k}" if prefix else k
                    check_val(k_full, v)
                    walk_ctx(v, k_full)
            elif isinstance(d, list):
                for idx, item in enumerate(d):
                    walk_ctx(item, f"{prefix}[{idx}]")

        walk_ctx(ctx)

        # Check essential required fields
        for f_schema in schema.fields:
            val = ctx.get(f_schema.key)
            is_essential = getattr(f_schema, "importance", "optional") == "essential"
            if f_schema.required is True and not f_schema.defer_ok and is_essential:
                if val is None or str(val).strip() in ("", "None", "null"):
                    raise ValueError(
                        f"Rendering validation failed for template '{schema.id}': "
                        f"Required essential field '{f_schema.key}' is missing or None. "
                        f"Official templates cannot render empty or 'None' values. "
                        f"(Field prompt: {f_schema.ask})"
                    )
            # Raise when a computed field resolves to empty
            if f_schema.computed:
                if val is None or str(val).strip() in ("", "None", "null"):
                    raise ValueError(
                        f"Rendering validation failed for template '{schema.id}': "
                        f"Computed field '{f_schema.key}' resolved to empty or None."
                    )
                if "[COMPUTE ERROR:" in str(val):
                    raise ValueError(
                        f"Rendering validation failed for template '{schema.id}': "
                        f"Computed field '{f_schema.key}' had evaluation error: {val}"
                    )

    def _convert_decimals(self, obj: Any, money_keys: set[str], current_key: str = "") -> Any:
        """Convert Decimal values. Money-typed fields get Indian grouping with two decimals; counts and quantities keep standard format."""
        if isinstance(obj, Decimal):
            from docgen.functions import fn_format_inr
            if current_key in money_keys:
                return fn_format_inr(obj)
            # Counts and quantities retain standard decimal/integer string format without currency grouping
            if obj % 1 == 0:
                return str(int(obj))
            return str(obj)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool) and current_key in money_keys:
            from docgen.functions import fn_format_inr
            return fn_format_inr(Decimal(str(obj)))
        elif isinstance(obj, dict):
            return {k: self._convert_decimals(v, money_keys, k) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals(item, money_keys, current_key) for item in obj]
        return obj

    def _convert_to_pdf(self, docx_path: Path) -> tuple[Path, str]:
        """Convert DOCX to PDF using LibreOffice headless as official converter.
        
        Word COM is an emergency fallback only. Returns (pdf_path, converter_name).
        """
        soffice = self._find_soffice()
        if soffice:
            try:
                result = subprocess.run(
                    [soffice, "--headless", "--convert-to", "pdf:writer_pdf_Export",
                     str(docx_path), "--outdir", str(docx_path.parent)],
                    capture_output=True, text=True, timeout=60,
                )
                pdf_path = docx_path.with_suffix(".pdf")
                if pdf_path.exists():
                    print(f"  [PDF Converter] Used official converter: LibreOffice ('{soffice}')")
                    return pdf_path, "LibreOffice"
            except Exception as e:
                print(f"  [PDF Converter] LibreOffice conversion warning: {e}")

        # Emergency Fallback: Word COM (docx2pdf)
        print("  [PDF Converter] WARNING: LibreOffice unavailable or failed. Trying emergency fallback: Microsoft Word COM...")
        try:
            import docx2pdf
            import pythoncom
            pythoncom.CoInitialize()
            try:
                pdf_path = docx_path.with_suffix(".pdf")
                docx2pdf.convert(str(docx_path), str(pdf_path))
                if pdf_path.exists():
                    print("  [PDF Converter] Used emergency fallback: Microsoft Word COM")
                    return pdf_path, "MS Word COM (Fallback)"
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            print(f"  [PDF Converter] Emergency fallback failed: {e}")

        # Raise visible error with explicit install instructions
        raise RuntimeError(
            f"\n{'='*70}\n"
            f"ERROR: LibreOffice executable ('soffice') not found for PDF conversion!\n"
            f"Target document: {docx_path}\n\n"
            f"Checked standard Windows locations:\n"
            f" - C:\\Program Files\\LibreOffice\\program\\soffice.exe\n"
            f" - C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe\n"
            f" - System PATH ('soffice')\n\n"
            f"Resolution Steps:\n"
            f" 1. Install LibreOffice from https://www.libreoffice.org/\n"
            f" 2. Add 'C:\\Program Files\\LibreOffice\\program' to your Windows PATH environment variable.\n"
            f"{'='*70}\n"
        )

    def _find_soffice(self) -> Optional[str]:
        """Find LibreOffice soffice executable."""
        # Check PATH
        soffice = shutil.which("soffice")
        if soffice:
            return soffice

        # Common Windows locations
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p

        return None

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a filesystem-safe slug."""
        import re
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "_", slug)
        return slug[:50]
