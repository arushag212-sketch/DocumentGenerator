"""Streamlit Web UI for ACM SVNIT Document Generator."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from docgen.config import load_config
from docgen.db import Database
from docgen.extractors.event_extractor import EventExtractor
from docgen.extractors.mom_extractor import MoMExtractor
from docgen.missing_fields import detect_missing_fields
from docgen.models import EventRecord, FieldSource, tf
from docgen.recommender import recommend_documents
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas

st.set_page_config(
    page_title="ACM SVNIT Document Generator",
    page_icon="📄",
    layout="wide",
)

config = load_config()
db = Database()
schemas = load_all_schemas()
renderer = Renderer(config=config)
extractor = EventExtractor(config=config)
mom_extractor = MoMExtractor(config=config)

st.title("📄 ACM SVNIT Smart Document Generator")
st.markdown("Automated, branded document generation for official student chapter workflows.")

tab_input, tab_docs, tab_templates, tab_history = st.tabs([
    "✍️ Event Input & Extraction",
    "📑 Generate Documents",
    "📋 Templates & Validation",
    "🕒 Version History"
])

if "event" not in st.session_state:
    st.session_state.event = EventRecord()

with tab_input:
    input_mode = st.radio("Input Mode", ["Natural Language Sentence", "Structured Form", "Meeting Notes (MoM)"], horizontal=True)

    if input_mode == "Natural Language Sentence":
        sample_sentence = "We are conducting a two-day Web Development Workshop on 14–15 October in Seminar Hall for around 120 students."
        text_input = st.text_area("Describe your event", value=sample_sentence, height=100)
        if st.button("Extract Event Details", type="primary"):
            event = extractor.extract_from_text(text_input)
            st.session_state.event = event
            db.save_event(event)
            st.success("Extracted event details successfully!")

    elif input_mode == "Meeting Notes (MoM)":
        sample_notes = """Executive Committee Meeting
Chaired by: Ansh Gupta
Attendees: Sunny Bodiwala, Ansh Gupta, Meet Patel
Agenda:
1. Web Dev Workshop Planning: Finalized dates 14-15 October and venue as Seminar Hall 402.
2. Hackathon Sponsorship: Approached 3 tech sponsors for INR 25,000 prize pool.
Action items:
Action: Submit permission letter to HoD CSE by Monday (Owner: Sunny)
Action: Finalize poster design and print banner (Owner: Meet)
"""
        notes_input = st.text_area("Paste Meeting Notes or Transcript", value=sample_notes, height=180)
        if st.button("Extract Meeting Minutes", type="primary"):
            event = mom_extractor.extract_from_notes(notes_input)
            st.session_state.event = event
            db.save_event(event)
            st.success("Extracted meeting minutes successfully!")

    else:
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Event Name", value=st.session_state.event.event_name.value or "")
            venue = st.text_input("Venue", value=st.session_state.event.venue.value or "Seminar Hall 402, CSE Department")
            dates = st.text_input("Dates / Range", value=st.session_state.event.dates.value or "14-15 October 2026")
        with col2:
            participants = st.number_input("Expected Participants", value=int(st.session_state.event.expected_participants.value or 120))
            category = st.selectbox("Category", ["Workshop", "Hackathon", "Seminar", "Competition", "Executive Meet"])
            mode = st.selectbox("Mode", ["Offline", "Online", "Hybrid"])

        if st.button("Save Event Details", type="primary"):
            event = st.session_state.event
            event.event_name = tf(name, FieldSource.user, confirmed=True)
            event.venue = tf(venue, FieldSource.user, confirmed=True)
            event.dates = tf(dates, FieldSource.user, confirmed=True)
            event.expected_participants = tf(participants, FieldSource.user, confirmed=True)
            event.category = tf(category, FieldSource.user, confirmed=True)
            event.mode = tf(mode, FieldSource.user, confirmed=True)
            db.save_event(event)
            st.success("Event details saved!")

    st.subheader("Current Canonical Event Record")
    st.json(st.session_state.event.flat_dict())

with tab_docs:
    st.subheader("Recommended Documents")
    event = st.session_state.event
    recs = recommend_documents(event, schemas)

    selected_doc_ids = []
    for r in recs:
        col_c, col_r = st.columns([1, 4])
        with col_c:
            checked = st.checkbox(r.template_name, value=True, key=f"rec_{r.template_id}")
            if checked:
                selected_doc_ids.append(r.template_id)
        with col_r:
            st.caption(f"**Why recommended**: {r.reason}")

    if selected_doc_ids:
        selected_schemas = [schemas[tid] for tid in selected_doc_ids]
        report = detect_missing_fields(event, selected_schemas)

        if report.missing:
            st.warning("⚠️ Missing Information Checklist")
            for m in report.missing:
                tag = "REQUIRED" if m.required and not m.defer_ok else "Optional / Fill Later"
                st.markdown(f"- **[{tag}] {m.key}**: {m.ask} *(Needed by: {', '.join(m.documents)})*")

        st.divider()
        if st.button("🚀 Generate Selected Documents", type="primary"):
            from docgen.numbering import suggest_reference_number

            # Generate suggested reference numbers if not set
            for tid in selected_doc_ids:
                s_obj = schemas[tid]
                if s_obj.numbering and not event.ref_no.is_present:
                    suggested = suggest_reference_number(
                        s_obj,
                        config=config,
                        db=db,
                        event_code=event.event_code.value or "SIH",
                    )
                    if suggested:
                        event.ref_no = suggested
                        # Confirm upon user clicking generate
                        event.ref_no.confirmed = True

            generated_files = []
            for tid in selected_doc_ids:
                res = renderer.render(tid, event)
                db.save_version(
                    event_id=event.id,
                    template_id=tid,
                    version=1,
                    docx_path=str(res.docx_path),
                    pdf_path=str(res.pdf_path) if res.pdf_path else None,
                    snapshot=event.flat_dict(),
                )
                generated_files.append(res)

            st.success(f"Generated {len(generated_files)} document(s) successfully!")
            for g in generated_files:
                col_d, col_b = st.columns([3, 1])
                with col_d:
                    st.write(f"📄 **{g.template_id}** -> `{g.docx_path}`")
                with col_b:
                    if g.docx_path.exists():
                        with open(g.docx_path, "rb") as f:
                            st.download_button(
                                label="Download DOCX",
                                data=f,
                                file_name=g.docx_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_{g.template_id}"
                            )

with tab_templates:
    st.subheader("Registered Templates & Validator Status")
    for tid, s in schemas.items():
        with st.expander(f"📁 {s.name} (`{s.id}`)"):
            st.markdown(f"**Description**: {s.description}")
            st.markdown(f"**Stage**: `{s.stage}` | **Letterhead**: `{s.letterhead}`")
            st.markdown(f"**Triggers**: {', '.join(s.triggers)}")
            st.markdown(f"**Total Fields Defined**: {len(s.fields)}")

with tab_history:
    st.subheader("Document Version History")
    events_list = db.list_events()
    if events_list:
        selected_event_id = st.selectbox("Select Event", [e["id"] for e in events_list], format_func=lambda eid: next((e["event_name"] for e in events_list if e["id"] == eid), eid))
        versions = db.get_versions(selected_event_id)
        if versions:
            for v in versions:
                st.markdown(f"- **{v['template_id']}** (Version {v['version']}) — Generated at `{v['created_at']}` | DOCX: `{v['docx_path']}`")
        else:
            st.info("No rendered document versions found for this event yet.")
    else:
        st.info("No events saved in the database yet.")
