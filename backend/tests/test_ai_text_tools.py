""""Improve my text" and the template wizard questions really call the AI (and fall back cleanly)."""

from __future__ import annotations

from server.app.core import template_wizard, text_improver
from server.app.core.template_wizard import get_wizard_questions
from server.app.core.text_improver import improve_text


class FakeAI:
    def __init__(self, answer=None, fail=False):
        self.answer = answer
        self.fail = fail
        self.prompts = []

    def is_available(self):
        return True

    def generate_json(self, prompt, schema, club_id=None):
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("model down")
        return self.answer


class NoAI:
    def is_available(self):
        return False


def test_improve_text_uses_ai_answer(monkeypatch):
    ai = FakeAI({"improved": "We respectfully request permission to organise the workshop."})
    monkeypatch.setattr(text_improver, "get_llm_client", lambda: ai)
    res = improve_text("we want to conduct workshop pls", mode="formal")
    assert res["improved"] == "We respectfully request permission to organise the workshop."
    assert "we want to conduct workshop pls" in ai.prompts[0]


def test_improve_text_falls_back_when_ai_fails_or_missing(monkeypatch):
    for client in (FakeAI(fail=True), FakeAI({"improved": "  "}), NoAI()):
        monkeypatch.setattr(text_improver, "get_llm_client", lambda c=client: c)
        res = improve_text("pls approve", mode="formal")
        assert res["improved"].startswith("Please approve")


def test_wizard_questions_use_ai(monkeypatch):
    ai = FakeAI({
        "suggested_title": "Hackathon Sponsorship Request",
        "questions": [
            {"id": "q_purpose", "question": "What is it for?", "category": "purpose", "options": ["A", "B", "C", "D", "E"]},
            {"id": "q_audience", "question": "Who reads it?", "category": "audience", "options": ["HoD", "Dean"]},
            {"id": "q_bad", "question": "", "category": "tone", "options": ["x", "y"]},
            {"id": "q_tone", "question": "Tone?", "category": "weird", "options": ["Formal"]},
        ],
    })
    monkeypatch.setattr(template_wizard, "get_llm_client", lambda: ai)
    res = get_wizard_questions("sponsorship letter for our hackathon", club_name="ACM")
    assert res.suggested_title == "Hackathon Sponsorship Request"
    # Empty question and one with a single option are dropped; options capped at 4
    assert [q.id for q in res.questions] == ["q_purpose", "q_audience"]
    assert res.questions[0].options == ["A", "B", "C", "D"]


def test_wizard_questions_fall_back(monkeypatch):
    for client in (FakeAI(fail=True), FakeAI({"suggested_title": "", "questions": []}), NoAI()):
        monkeypatch.setattr(template_wizard, "get_llm_client", lambda c=client: c)
        res = get_wizard_questions("permission letter for seminar hall")
        assert len(res.questions) == 3 and res.suggested_title
