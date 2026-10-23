"""Long tables repeat their heading row on every page; badly shaped data is a 400, not a crash."""

from __future__ import annotations

from pathlib import Path

from docx.oxml.ns import qn
from docxtpl import DocxTemplate
from fastapi.testclient import TestClient
from pydantic import BaseModel

from docgen.renderer import Renderer
from server.app.main import app

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def _header_rows(doc: DocxTemplate) -> list[str]:
    out = []
    for tbl in doc.docx.element.body.iter(qn("w:tbl")):
        for row in tbl.findall(qn("w:tr")):
            tr_pr = row.find(qn("w:trPr"))
            if tr_pr is not None and tr_pr.find(qn("w:tblHeader")) is not None:
                out.append("".join(t.text or "" for t in row.iter(qn("w:t"))))
    return out


def test_growing_tables_get_a_repeating_heading():
    doc = DocxTemplate(str(TEMPLATES / "mom" / "template.docx"))
    Renderer.__new__(Renderer)._repeat_table_headers(doc)
    heads = _header_rows(doc)
    assert any("Discussion" in h for h in heads)  # agenda table
    assert any("Deadline" in h for h in heads)  # action items table
    assert not any("{%" in h for h in heads)  # never the loop row itself


def test_fixed_tables_are_left_alone():
    doc = DocxTemplate(str(TEMPLATES / "approval_note" / "template.docx"))
    Renderer.__new__(Renderer)._repeat_table_headers(doc)
    heads = _header_rows(doc)
    assert any("Items" in h for h in heads)  # budget table repeats
    assert not any("Title of the Event" in h for h in heads)  # key/value table does not


class _Row(BaseModel):
    amount: int


def test_bad_data_shape_is_400_not_500():
    from fastapi import FastAPI
    from pydantic import ValidationError

    from server.app.main import _invalid_data

    probe = FastAPI()
    probe.add_exception_handler(ValidationError, _invalid_data)
    assert app.exception_handlers.get(ValidationError) is _invalid_data  # registered on the real app

    @probe.get("/bad")
    def _bad_shape():
        _Row(amount="not a number")

    res = TestClient(probe, raise_server_exceptions=False).get("/bad")
    assert res.status_code == 400
    body = res.json()["detail"]
    assert body["code"] == "INVALID_DATA" and "amount" in body["message"]
