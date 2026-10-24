"""Template translation to Hindi / Gujarati: whole sentences go to the AI with chips as markers,
chips always survive, formatting and spacing are kept, and a missing AI is reported."""

from __future__ import annotations

import re

from server.app.core import text_improver
from server.app.core.text_improver import translate_template_content


def chip(name):
    return {"type": "fieldChip", "attrs": {"fieldName": name, "label": name.title(), "fieldType": "text"}}


def text(t, marks=None):
    node = {"type": "text", "text": t}
    if marks:
        node["marks"] = marks
    return node


class FakeAI:
    """Answers like a model would: 'HI:' + the sentence, with markers moved to the front (SOV order)."""

    def __init__(self, drop_markers=False):
        self.calls = []
        self.drop_markers = drop_markers

    def is_available(self):
        return True

    def generate_json(self, prompt, schema, club_id=None):
        import json

        items = json.loads(prompt.rsplit("\n", 1)[-1])
        self.calls.append(items)
        out = []
        for s in items:
            markers = re.findall(r"⟦\d+⟧", s)
            words = re.sub(r"⟦\d+⟧", "", s).strip()
            out.append(("" if self.drop_markers else " ".join(reversed(markers)) + " ") + "HI:" + words)
        return {"translations": out}


class NoAI:
    def is_available(self):
        return False


def _doc():
    return {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [text("Permission Letter")]},
            {"type": "paragraph", "content": [text("has secured "), chip("position"), text(" in "), chip("event_name"), text(".")]},
            {"type": "paragraph", "content": [text("Subject:", [{"type": "bold"}]), text(" Request for the hall")]},
            {"type": "paragraph", "content": [text("2026-27")]},
            {
                "type": "table",
                "content": [{"type": "tableRow", "content": [{"type": "tableCell", "content": [
                    {"type": "paragraph", "content": [text("Head of Department"), {"type": "hardBreak"}, text("SVNIT")]}
                ]}]}],
            },
        ],
    }


def _chips(node, out=None):
    out = [] if out is None else out
    if node.get("type") == "fieldChip":
        out.append(node["attrs"]["fieldName"])
    for c in node.get("content", []) or []:
        _chips(c, out)
    return out


def test_sentences_translated_whole_with_chips_kept(monkeypatch):
    ai = FakeAI()
    monkeypatch.setattr(text_improver, "get_llm_client", lambda: ai)
    report = {}
    doc, design = translate_template_content(_doc(), "hi", report=report)

    assert design["fontFamily"] == "Noto Sans Devanagari"
    assert sorted(_chips(doc)) == ["event_name", "position"]
    # One sentence per paragraph, chips as markers, sent in a single batched call
    assert len(ai.calls) == 1
    assert "has secured ⟦0⟧ in ⟦1⟧." in ai.calls[0]
    # Numbers-only text is left alone
    assert "2026-27" not in ai.calls[0]
    assert doc["content"][3]["content"][0]["text"] == "2026-27"
    # Chips moved to where the translation put them
    para = doc["content"][1]["content"]
    assert [n["attrs"]["fieldName"] for n in para if n.get("type") == "fieldChip"] == ["event_name", "position"]
    assert para[0]["type"] == "fieldChip" and para[-1]["text"] == " HI:has secured  in ."
    # Bold label and normal text translated separately; bold stays on the label
    mixed = doc["content"][2]["content"]
    assert mixed[0]["marks"] == [{"type": "bold"}] and mixed[0]["text"].startswith("HI:")
    assert "marks" not in mixed[1] and mixed[1]["text"].startswith(" ")  # leading space kept
    # Line break inside a table cell survives
    cell = doc["content"][4]["content"][0]["content"][0]["content"][0]["content"]
    assert any(n.get("type") == "hardBreak" for n in cell)
    assert report == {"total": 5, "translated": 5, "used_ai": True}


def test_dropped_marker_never_loses_a_chip(monkeypatch):
    monkeypatch.setattr(text_improver, "get_llm_client", lambda: FakeAI(drop_markers=True))
    doc, _ = translate_template_content(_doc(), "gu")
    assert sorted(_chips(doc)) == ["event_name", "position"]


def test_big_template_is_batched(monkeypatch):
    ai = FakeAI()
    monkeypatch.setattr(text_improver, "get_llm_client", lambda: ai)
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": [text(f"Line number {i}")]} for i in range(60)]}
    out, _ = translate_template_content(doc, "hi")
    assert len(ai.calls) == 3  # 25 + 25 + 10
    assert all(p["content"][0]["text"].startswith("HI:") for p in out["content"])


def test_without_ai_only_dictionary_and_it_says_so(monkeypatch):
    monkeypatch.setattr(text_improver, "get_llm_client", lambda: NoAI())
    report = {}
    doc, _ = translate_template_content(_doc(), "hi", report=report)
    assert doc["content"][0]["content"][0]["text"] == "अनुमति पत्र"
    assert sorted(_chips(doc)) == ["event_name", "position"]
    assert report["used_ai"] is False and report["translated"] == 0
