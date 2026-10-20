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


def translate_template_content(
    editor_json: dict[str, Any],
    target_lang: Literal["hi", "gu", "en"],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recursively translates text runs in TipTap document while leaving field chips 100% intact."""
    migrated = copy.deepcopy(editor_json)
    client = get_llm_client()

    dict_map = OFFLINE_HINDI_DICTIONARY if target_lang == "hi" else OFFLINE_GUJARATI_DICTIONARY

    def translate_phrase(text: str) -> str:
        trimmed = text.strip()
        if not trimmed:
            return text

        # Check offline dictionary first
        if trimmed in dict_map:
            return dict_map[trimmed]

        if client and getattr(client, "api_key", None):
            try:
                lang_name = "Hindi" if target_lang == "hi" else "Gujarati"
                inst = (
                    f"Translate the following administrative document snippet into formal {lang_name}. "
                    f"Preserve all formatting and tone. Do not add explanations."
                )
                raw = client.generate_text(prompt=trimmed, system_instruction=inst)
                if raw and raw.strip():
                    return raw.strip()
            except Exception:
                pass

        # Offline translation: replace known word phrases
        res = trimmed
        for en_key, trans_val in dict_map.items():
            res = res.replace(en_key, trans_val)
        return res

    def walk_node(node: dict[str, Any]):
        n_type = node.get("type")
        # IMPORTANT: fieldChip nodes must remain 100% intact!
        if n_type == "fieldChip":
            return
        elif n_type == "text" and "text" in node:
            original_text = node["text"]
            # Translate text runs
            node["text"] = translate_phrase(original_text)
            node["ai_suggested"] = True
        elif "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                walk_node(child)

    walk_node(migrated)

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
