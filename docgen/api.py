"""FastAPI backend service for document generator."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from docgen.config import load_config
from docgen.db import Database
from docgen.extractors.event_extractor import EventExtractor
from docgen.missing_fields import detect_missing_fields
from docgen.models import EventRecord
from docgen.recommender import recommend_documents
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas

app = FastAPI(title="ACM Document Generator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()
config = load_config()
schemas = load_all_schemas()
renderer = Renderer(config=config)
extractor = EventExtractor(config=config)


class ParseRequest(BaseModel):
    text: str


class RenderRequest(BaseModel):
    template_id: str
    event_id: Optional[str] = None
    event_data: Optional[dict[str, Any]] = None


@app.get("/templates")
def list_templates():
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "stage": s.stage,
            "triggers": s.triggers,
            "letterhead": s.letterhead,
        }
        for s in schemas.values()
    ]


@app.post("/parse")
def parse_text(req: ParseRequest):
    event = extractor.extract_from_text(req.text)
    event_id = db.save_event(event)
    recs = recommend_documents(event, schemas)
    report = detect_missing_fields(event, [schemas[r.template_id] for r in recs])
    return {
        "event_id": event_id,
        "event": event.flat_dict(),
        "recommendations": [
            {
                "template_id": r.template_id,
                "name": r.template_name,
                "reason": r.reason,
                "stage": r.stage,
            }
            for r in recs
        ],
        "missing_fields": [
            {
                "key": m.key,
                "ask": m.ask,
                "documents": m.documents,
                "required": m.required,
                "defer_ok": m.defer_ok,
            }
            for m in report.missing
        ],
    }


@app.post("/render")
def render_template(req: RenderRequest):
    if req.template_id not in schemas:
        raise HTTPException(status_code=404, detail="Template not found")

    if req.event_id:
        event = db.get_event(req.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
    elif req.event_data:
        event = EventRecord.model_validate(req.event_data)
    else:
        raise HTTPException(status_code=400, detail="Either event_id or event_data required")

    res = renderer.render(req.template_id, event)
    version = 1
    db.save_version(
        event_id=event.id,
        template_id=req.template_id,
        version=version,
        docx_path=str(res.docx_path),
        pdf_path=str(res.pdf_path) if res.pdf_path else None,
        snapshot=event.flat_dict(),
    )

    return {
        "status": "success",
        "docx_path": str(res.docx_path),
        "pdf_path": str(res.pdf_path) if res.pdf_path else None,
    }
