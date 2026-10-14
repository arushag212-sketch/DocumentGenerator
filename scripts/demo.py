"""Demonstration script executing the exact user prompt end-to-end."""

from pathlib import Path
from docgen.config import load_config
from docgen.db import Database
from docgen.extractors.event_extractor import EventExtractor
from docgen.missing_fields import detect_missing_fields
from docgen.models import FieldSource, tf
from docgen.recommender import recommend_documents
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas

def main():
    print("=" * 70)
    print(" ACM SVNIT SMART DOCUMENT GENERATOR: END-TO-END DEMO")
    print("=" * 70)

    # 1. Natural language input prompt from the project specification
    sample_text = (
        "We are conducting a two-day Web Development Workshop on 14–15 October "
        "in Seminar Hall for around 120 students."
    )
    print(f"\n[1] INPUT PROMPT:")
    print(f"    \"{sample_text}\"")

    # 2. Extract Event Details
    print(f"\n[2] RUNNING EXTRACTOR (Rules + Dateparser + Fallbacks)...")
    config = load_config()
    extractor = EventExtractor(config=config)
    event = extractor.extract_from_text(sample_text)

    print("    Extracted Fields:")
    flat = event.flat_dict()
    for field in ["event_name", "category", "dates", "venue", "expected_participants", "mode"]:
        val = flat.get(field)
        print(f"      - {field}: {val}")

    # 3. Document Recommendations
    print(f"\n[3] EVALUATING DOCUMENT RECOMMENDATIONS...")
    schemas = load_all_schemas()
    recs = recommend_documents(event, schemas)
    for r in recs:
        print(f"    * [{r.template_id}] {r.template_name}")
        print(f"      Reason: {r.reason}")

    # 4. Missing Field Detection
    print(f"\n[4] RUNNING MISSING-FIELD DETECTOR...")
    rec_schemas = [schemas[r.template_id] for r in recs]
    report = detect_missing_fields(event, rec_schemas)
    for mf in report.missing[:5]:
        req_tag = "REQUIRED" if mf.required and not mf.defer_ok else "Optional"
        print(f"    * [{req_tag}] {mf.key}: {mf.ask}")

    # 5. Populate remaining execution details & render
    print(f"\n[5] NUMBERING & USER CONFIRMATION...")
    from docgen.numbering import suggest_reference_number

    suggested_ref = suggest_reference_number(
        schemas["permission_letter"],
        config=config,
        event_code=event.event_code.value or "WDW",
    )
    print(f"    * Counter Suggestion: {suggested_ref.value} (confirmed={suggested_ref.confirmed})")
    # Rule 1: User explicitly confirms reference number
    suggested_ref.confirmed = True
    event.ref_no = suggested_ref
    print(f"    * User confirmed Reference Number: {event.ref_no.value}")

    # User answers missing required fields (time_start, time_end)
    print(f"    * User provides required times: 09:00 AM to 05:00 PM")
    event.time_start = tf("09:00 AM", FieldSource.user, confirmed=True)
    event.time_end = tf("05:00 PM", FieldSource.user, confirmed=True)

    renderer = Renderer(config=config, outputs_dir="outputs")
    res = renderer.render("permission_letter", event, convert_pdf=True)

    print(f"    [OK] Document rendered successfully:")
    print(f"         DOCX: {res.docx_path}")
    if res.pdf_path:
        print(f"         PDF:  {res.pdf_path}")
    else:
        print(f"         PDF:  (Skipped, LibreOffice not available on PATH)")

    # 6. Save in database
    db = Database()
    event_id = db.save_event(event)
    db.save_version(
        event_id=event_id,
        template_id="permission_letter",
        version=1,
        docx_path=str(res.docx_path),
        pdf_path=str(res.pdf_path) if res.pdf_path else None,
        snapshot=event.flat_dict(),
    )
    print(f"\n[6] SAVED TO DATABASE (Event ID: {event_id})")
    print("=" * 70)
    print(" DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
