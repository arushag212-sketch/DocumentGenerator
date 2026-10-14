"""Command Line Interface (CLI) for docgen."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docgen.config import load_config
from docgen.db import Database
from docgen.extractors.event_extractor import EventExtractor
from docgen.extractors.mom_extractor import MoMExtractor
from docgen.missing_fields import detect_missing_fields
from docgen.models import EventRecord, FieldSource, tf
from docgen.recommender import recommend_documents
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas
from docgen.validator import validate_all_templates


def main():
    parser = argparse.ArgumentParser(description="Smart Document Generator for ACM SVNIT Surat")
    subparsers = parser.add_subparsers(dest="command")

    # Command: validate-templates
    val_parser = subparsers.add_parser("validate-templates", help="Validate all DOCX templates against their schemas")

    # Command: parse
    parse_parser = subparsers.add_parser("parse", help="Parse natural language event description")
    parse_parser.add_argument("text", help="Event description text")

    # Command: recommend
    rec_parser = subparsers.add_parser("recommend", help="Recommend documents for an event description")
    rec_parser.add_argument("text", help="Event description text")

    # Command: render
    render_parser = subparsers.add_parser("render", help="Render a document template")
    render_parser.add_argument("--template", "-t", required=True, help="Template ID (e.g. permission_letter)")
    render_parser.add_argument("--text", help="Natural language description")
    render_parser.add_argument("--event-name", help="Event name override")
    render_parser.add_argument("--venue", help="Venue override")
    render_parser.add_argument("--date", help="Date range override")
    render_parser.add_argument("--output-dir", "-o", default="outputs", help="Output directory")

    args = parser.parse_args()

    if args.command == "validate-templates":
        results = validate_all_templates()
        has_errors = False
        for res in results:
            print(res.summary())
            print()
            if not res.is_valid:
                has_errors = True
        sys.exit(1 if has_errors else 0)

    elif args.command == "parse":
        extractor = EventExtractor()
        event = extractor.extract_from_text(args.text)
        print("=== Extracted Canonical Event Record ===")
        for k, v in event.flat_dict().items():
            if v:
                print(f"  {k}: {v}")

    elif args.command == "recommend":
        extractor = EventExtractor()
        event = extractor.extract_from_text(args.text)
        schemas = load_all_schemas()
        recs = recommend_documents(event, schemas)
        print("=== Recommended Documents ===")
        for r in recs:
            print(f"- [{r.template_id}] {r.template_name} (Stage: {r.stage})")
            print(f"  Reason: {r.reason}")

        report = detect_missing_fields(event, [schemas[r.template_id] for r in recs])
        print("\n" + report.summary())

    elif args.command == "render":
        config = load_config()
        schemas = load_all_schemas()
        if args.template not in schemas:
            print(f"Error: Unknown template '{args.template}'. Available: {list(schemas.keys())}")
            sys.exit(1)

        event = EventRecord()
        if args.text:
            extractor = EventExtractor(config=config)
            event = extractor.extract_from_text(args.text)

        if args.event_name:
            event.event_name = tf(args.event_name, FieldSource.user, confirmed=True)
        if args.venue:
            event.venue = tf(args.venue, FieldSource.user, confirmed=True)
        if args.date:
            event.dates = tf(args.date, FieldSource.user, confirmed=True)
            event.date_start = tf(args.date, FieldSource.user, confirmed=True)
            event.date_end = tf(args.date, FieldSource.user, confirmed=True)

        # Suggest reference number from counter as unconfirmed suggestion
        from docgen.numbering import suggest_reference_number
        if not event.ref_no.is_present:
            suggested_ref = suggest_reference_number(
                schemas[args.template],
                config=config,
                event_code=event.event_code.value or "SIH",
            )
            if suggested_ref:
                # Mark confirmed=True only after user confirmation; in CLI simulation we set value and print warning
                event.ref_no = suggested_ref
                print(f"[NOTE] Reference number suggested from counter: {event.ref_no.value} (confirmed={event.ref_no.confirmed})")
                # User confirms it for render execution:
                event.ref_no.confirmed = True

        renderer = Renderer(config=config, outputs_dir=args.output_dir)
        res = renderer.render(args.template, event)
        print(f"Document generated successfully:")
        print(f"  DOCX: {res.docx_path}")
        if res.pdf_path:
            print(f"  PDF:  {res.pdf_path}")
        else:
            print(f"  PDF:  (Skipped, LibreOffice not available)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
