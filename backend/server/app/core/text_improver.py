"""Text Improver, Detail Suggester, and Indic Translator for SVNIT ClubDocs.

Capabilities:
1. "Improve my text": Proofread, formal tone, shorten, or expand description/objectives with before/after and AI-suggested label.
2. "Suggest details": Proposes optional fields (e.g. expected_attendees, prerequisites) - NEVER official numbers, amounts, names, or IDs.
3. "Translate / adapt": English <-> Hindi/Gujarati for template text while keeping field chips completely intact and setting Indic fonts.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Literal
from pydantic import BaseModel

from docgen.llm import LLMClient, get_llm_client
from server.app.core.template_generator import strip_pii_from_text

strip_pii_for_llm = strip_pii_from_text



# Guardrails: Never allow suggestion of official numbers, amounts, roll numbers, or bank IDs
FORBIDDEN_SUGGESTION_TERMS = {
    "amount",
    "budget",
    "cost",
    "price",
    "fee",
    "money",
    "bank",
    "account",
    "ifsc",
    "pan",
    "gst",
    "roll",
    "mobile",
    "phone",
    "ref",
    "number",
    "approval_no",
    "sanction_no",
}


HEURISTIC_FORMAL_REPLACEMENTS = [
    (r"\bpls\b", "please"),
    (r"\bwanna\b", "wish to"),
    (r"\bgonna\b", "intend to"),
    (r"\basap\b", "at your earliest convenience"),
    (r"\bin order to\b", "to"),
    (r"\bdue to the fact that\b", "as"),
    (r"\bat this point in time\b", "presently"),
    (r"\bwe want to conduct\b", "we respectfully request permission to organize"),
    (r"\bgive us permission\b", "kindly grant the necessary administrative permission"),
    (r"\bkindly approve\b", "kindly accord sanction for"),
    (r"\bneed money\b", "request budgetary allocation"),
]


OFFLINE_HINDI_DICTIONARY = {
    "Annual Tech Symposium Approval Note": "वार्षिक तकनीकी संगोष्ठी अनुमोदन टिप्पणी",
    "Permission Letter": "अनुमति पत्र",
    "Submitted To": "सेवा में",
    "Respected Sir / Madam": "आदरणीय महोदय / महोदया",
    "We request your kind permission": "हम विनम्रतापूर्वक आपकी अनुमति का अनुरोध करते हैं",
    "Event Title": "कार्यक्रम का शीर्षक",
    "Date & Venue": "दिनांक एवं स्थान",
    "Lead Coordinator": "मुख्य समन्वयक",
    "Estimated Budget": "अनुमानित बजट",
    "Student Coordinator": "छात्र समन्वयक",
    "Faculty Advisor": "संकाय सलाहकार",
    "Head of Department": "विभागाध्यक्ष",
    "Total": "कुल",
    "Description": "विवरण",
}

OFFLINE_GUJARATI_DICTIONARY = {
    "Annual Tech Symposium Approval Note": "વાર્ષિક ટેક સિમ્પોઝિયમ મંજૂરી નોંધ",
    "Permission Letter": "પરવાનગી પત્ર",
    "Submitted To": "પ્રતિ",
    "Respected Sir / Madam": "આદરણીય સાહેબ / મેડમ",
    "We request your kind permission": "અમે નમ્રતાપૂર્વક તમારી પરવાનગીની વિનંતી કરીએ છીએ",
    "Event Title": "કાર્યક્રમનું શીર્ષક",
    "Date & Venue": "તારીખ અને સ્થળ",
    "Lead Coordinator": "મુખ્ય સંયોજક",
    "Estimated Budget": "અંદાજિત બજેટ",
    "Student Coordinator": "વિદ્યાર્થી સંયોજક",
    "Faculty Advisor": "ફેકલ્ટી સલાહકાર",
    "Head of Department": "વિભાગના વડા",
    "Total": "કુલ",
    "Description": "વિગત",
}


def heuristic_improve(text: str, mode: str) -> str:
    """Offline rule-based transformation when LLM is offline or unconfigured."""
    res = text.strip()
    if mode == "formal":
        for pat, repl in HEURISTIC_FORMAL_REPLACEMENTS:
            res = re.sub(pat, repl, res, flags=re.IGNORECASE)
        # Capitalize first letter of sentences
        sentences = [s.strip() for s in res.split(".") if s.strip()]
        res = ". ".join([s[0].upper() + s[1:] if len(s) > 1 else s for s in sentences])
        if res and not res.endswith("."):
            res += "."
    elif mode == "proofread":
        # Fix multiple spaces
        res = re.sub(r" {2,}", " ", res)
        # Fix lowercase 'i'
        res = re.sub(r"\bi\b", "I", res)
        # Ensure punctuation after sentences
        if res and not res.endswith((".", "!", "?")):
            res += "."
    elif mode == "shorten":
        # Remove wordy fluff
        for pat, repl in [
            (r"\bwith reference to the subject cited above,\s*", ""),
            (r"\bfor the purpose of\b", "for"),
            (r"\bin the event that\b", "if"),
            (r"\bit is important to note that\b", "notably,"),
        ]:
            res = re.sub(pat, repl, res, flags=re.IGNORECASE)
    elif mode == "longer":
        res += " This initiative is designed to foster technical collaboration, enhance hands-on learning, and support SVNIT's academic vision."

    return res


def improve_text(
    text: str,
    mode: Literal["formal", "proofread", "shorter", "longer"] = "formal",
) -> dict[str, Any]:
    """Improve plain text for descriptions, objectives, or notices with before/after diff."""
    cleaned = strip_pii_from_text(text.strip())
    client = get_llm_client()

    improved = cleaned
    explanation = f"Enhanced text into a {mode} tone suitable for official institute correspondence."

    if client and getattr(client, "api_key", None):
        try:
            instruction = (
                f"You are an expert editorial assistant for SVNIT Student Clubs. "
                f"Rewrite the following text according to mode: '{mode}'. "
                f"- 'formal': Professional, official institute tone. "
                f"- 'proofread': Fix spelling and grammar errors only. "
                f"- 'shorten': Concise and direct without losing key facts. "
                f"- 'longer': Elaborate constructively on the objective and educational value. "
                f"Never invent official numbers, amounts, roll numbers, or names. "
                f"Return ONLY the rewritten text without markdown fences or explanations."
            )
            raw = client.generate_text(prompt=cleaned, system_instruction=instruction)
            if raw and raw.strip():
                improved = raw.strip()
        except Exception:
            improved = heuristic_improve(cleaned, mode)
    else:
        improved = heuristic_improve(cleaned, mode)

    return {
        "original": cleaned,
        "improved": improved,
        "mode": mode,
        "ai_suggested": True,
        "explanation": explanation,
        "diff": {
            "before": cleaned,
            "after": improved,
        },
    }


def suggest_optional_details(
    event_type: str = "Workshop",
    club_name: str = "",
    existing_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Proposes contextual optional fields — strictly excluding official numbers, amounts, or names."""
    existing_set = set(existing_fields or [])
    suggestions: list[dict[str, Any]] = []

    catalog = [
        {
            "key": "target_audience",
            "label": "Target Audience",
            "type": "text",
            "ask": "Which departments or student years are eligible to attend?",
            "sample": "B.Tech 2nd & 3rd Year students",
        },
        {
            "key": "expected_attendees",
            "label": "Expected Attendee Count",
            "type": "int",
            "ask": "Approximately how many participants are expected?",
            "sample": "80",
        },
        {
            "key": "prerequisites",
            "label": "Student Prerequisites",
            "type": "text",
            "ask": "Are any prior software tools or skills required?",
            "sample": "Basic familiarity with Python and Git",
        },
        {
            "key": "event_time",
            "label": "Event Timings",
            "type": "time_range",
            "ask": "What are the start and end times for the session?",
            "sample": "02:00 PM - 05:00 PM",
        },
        {
            "key": "mode_of_conduct",
            "label": "Mode of Conduction",
            "type": "enum",
            "ask": "Is this offline in-person or hybrid?",
            "values": ["Offline (In-Person)", "Hybrid", "Online"],
            "sample": "Offline (In-Person)",
        },
    ]

    for item in catalog:
        # Enforce guardrail: verify key is never in forbidden list
        if any(term in item["key"] for term in FORBIDDEN_SUGGESTION_TERMS):
            continue
        if item["key"] not in existing_set:
            suggestions.append({**item, "ai_suggested": True, "required": False})

    return suggestions[:4]


LANGUAGE_NAMES = {"hi": "Hindi", "gu": "Gujarati", "en": "English"}

# A field chip, line break or other inline node inside a sentence, held as a numbered marker
_TOKEN_RE = re.compile(r"⟦(\d+)⟧")
_HAS_LETTERS = re.compile(r"[A-Za-zऀ-ॿ઀-૿]")
# Sentences per AI request: keeps each call well inside the client timeout
TRANSLATE_BATCH_SIZE = 25

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
    "required": ["translations"],
}


def _translation_prompt(texts: list[str], lang_name: str) -> str:
    import json

    return (
        f"Translate each string in the JSON list below into formal, official {lang_name} as used in Indian "
        "institute letters and notices. Rules:\n"
        "- Return {\"translations\": [...]} with exactly one translation per input string, in the same order.\n"
        "- Markers like ⟦0⟧, ⟦1⟧ stand for names, dates and other filled-in values. Keep every marker exactly "
        "once, unchanged; move it to wherever it belongs in natural " + lang_name + " word order.\n"
        "- Keep numbers, reference codes, e-mail addresses, URLs and acronyms (SVNIT, ACM, IEEE, HoD) as they are.\n"
        "- Keep the spacing and punctuation style; do not add quotes, notes or explanations.\n\n"
        + json.dumps(texts, ensure_ascii=False)
    )


def _split_spaces(text: str) -> tuple[str, str, str]:
    core = text.strip()
    if not core:
        return text, "", ""
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return lead, core, trail


def _dictionary_translate(text: str, dict_map: dict[str, str]) -> str:
    lead, core, trail = _split_spaces(text)
    if core in dict_map:
        return lead + dict_map[core] + trail
    for en_key, trans_val in dict_map.items():
        core = core.replace(en_key, trans_val)
    return lead + core + trail


class _Unit:
    """One sentence-sized piece to translate: a paragraph, heading or cell line, or a single run."""

    def __init__(self, parent: dict[str, Any], indexes: list[int], source: str, tokens: list[dict[str, Any]], marks: Any):
        self.parent = parent
        self.indexes = indexes  # positions in parent["content"] this unit replaces
        self.source = source
        self.tokens = tokens  # inline nodes the ⟦n⟧ markers stand for
        self.marks = marks


def _collect_units(doc: dict[str, Any]) -> list[_Unit]:
    units: list[_Unit] = []

    def visit(node: dict[str, Any]):
        if not isinstance(node, dict) or node.get("type") == "fieldChip":
            return
        content = node.get("content")
        if not isinstance(content, list):
            return
        if not any(isinstance(c, dict) and c.get("type") == "text" for c in content):
            for child in content:
                visit(child)
            return

        text_marks = [c.get("marks") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        same_style = all(m == text_marks[0] for m in text_marks)
        if same_style:
            # Whole sentence at once, so the translation reads naturally around the chips
            parts: list[str] = []
            tokens: list[dict[str, Any]] = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append(c.get("text", ""))
                else:
                    parts.append(f"⟦{len(tokens)}⟧")
                    tokens.append(c)
            source = "".join(parts)
            if _HAS_LETTERS.search(_TOKEN_RE.sub("", source)):
                units.append(_Unit(node, list(range(len(content))), source, tokens, text_marks[0]))
        else:
            # Mixed bold/italic runs: translate each run on its own so its formatting stays put
            for i, c in enumerate(content):
                if isinstance(c, dict) and c.get("type") == "text" and _HAS_LETTERS.search(c.get("text", "")):
                    units.append(_Unit(node, [i], c.get("text", ""), [], c.get("marks")))

    visit(doc)
    return units


def _rebuild(unit: _Unit, translated: str) -> list[dict[str, Any]]:
    """Turn a translated string back into text nodes and the original chips; no chip is ever lost."""
    nodes: list[dict[str, Any]] = []
    used: set[int] = set()
    pos = 0

    def add_text(t: str):
        if not t:
            return
        node: dict[str, Any] = {"type": "text", "text": t, "ai_suggested": True}
        if unit.marks:
            node["marks"] = copy.deepcopy(unit.marks)
        nodes.append(node)

    for m in _TOKEN_RE.finditer(translated):
        add_text(translated[pos:m.start()])
        idx = int(m.group(1))
        if idx < len(unit.tokens) and idx not in used:
            nodes.append(unit.tokens[idx])
            used.add(idx)
        pos = m.end()
    add_text(translated[pos:])
    # A marker the model dropped: keep the chip, at the end of the sentence
    for idx, token in enumerate(unit.tokens):
        if idx not in used:
            nodes.append(token)
    return nodes


def translate_template_content(
    editor_json: dict[str, Any],
    target_lang: Literal["hi", "gu", "en"],
    report: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Translate the template's wording sentence by sentence, keeping every field chip intact.

    Uses the AI in a few batched requests; without AI only the common headings in the offline
    dictionary change. ``report`` (if given) is filled with how much was translated and how.
    """
    from concurrent.futures import ThreadPoolExecutor

    migrated = copy.deepcopy(editor_json)
    lang_name = LANGUAGE_NAMES.get(target_lang, "Hindi")
    dict_map = {"hi": OFFLINE_HINDI_DICTIONARY, "gu": OFFLINE_GUJARATI_DICTIONARY}.get(target_lang, {})
    units = _collect_units(migrated)
    results: list[str | None] = [None] * len(units)

    client = get_llm_client()
    use_ai = bool(units) and client.is_available()
    if use_ai:
        batches = [list(range(i, min(i + TRANSLATE_BATCH_SIZE, len(units)))) for i in range(0, len(units), TRANSLATE_BATCH_SIZE)]

        def run(batch: list[int]) -> None:
            cores = [_split_spaces(units[i].source)[1] for i in batch]
            try:
                raw = client.generate_json(_translation_prompt(cores, lang_name), TRANSLATION_SCHEMA)
            except Exception:
                return
            out = raw.get("translations") if isinstance(raw, dict) else None
            if not isinstance(out, list) or len(out) != len(batch):
                return
            for i, text in zip(batch, out):
                if isinstance(text, str) and text.strip():
                    lead, _, trail = _split_spaces(units[i].source)
                    results[i] = lead + text.strip() + trail

        with ThreadPoolExecutor(max_workers=min(4, len(batches))) as pool:
            list(pool.map(run, batches))

    translated = 0
    # Replace from the end of each parent so earlier positions stay valid
    for i in sorted(range(len(units)), key=lambda k: (id(units[k].parent), -units[k].indexes[0])):
        unit = units[i]
        if results[i] is not None:
            text = results[i]
            translated += 1
        else:
            text = _dictionary_translate(unit.source, dict_map) if dict_map else unit.source
        new_nodes = _rebuild(unit, text)
        content = unit.parent["content"]
        content[unit.indexes[0]: unit.indexes[-1] + 1] = new_nodes

    if report is not None:
        report.update({"total": len(units), "translated": translated, "used_ai": use_ai})

    # Update design font for Indic script support
    if target_lang == "hi":
        design_update = {
            "fontFamily": "Noto Sans Devanagari",
            "headingFontFamily": "Noto Sans Devanagari",
        }
    elif target_lang == "gu":
        design_update = {
            "fontFamily": "Noto Sans Gujarati",
            "headingFontFamily": "Noto Sans Gujarati",
        }
    else:
        design_update = {
            "fontFamily": "Tinos",
            "headingFontFamily": "Tinos",
        }

    return migrated, design_update
