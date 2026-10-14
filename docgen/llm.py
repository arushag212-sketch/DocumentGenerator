"""Pluggable LLM client interface and fallback/Gemini implementations."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional


class LLMClient(ABC):
    @abstractmethod
    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON adhering to the provided JSON schema."""
        pass

    @abstractmethod
    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        """Draft narrative text (e.g. descriptions, objectives)."""
        pass


class DummyLLMClient(LLMClient):
    """Fallback client when no API key or remote service is configured."""

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return {}

    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        event_name = context.get("event_name", "the event")
        venue = context.get("venue", "the designated venue")
        prompt_lower = prompt.lower()
        if "objective" in prompt_lower:
            return f"1. Provide students hands-on technical training in {event_name}.\n2. Foster peer collaboration and practical problem solving at {venue}."
        else:
            return f"{event_name} is a student chapter activity organized at {venue} to equip participants with core skills and industry-standard practices."


class GeminiLLMClient(LLMClient):
    """Google Gemini API implementation using google-genai or requests."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return {}
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            return {}

    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        if not self.api_key:
            return DummyLLMClient().draft_text(prompt, context)
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            ctx_summary = "\n".join(f"{k}: {v}" for k, v in context.items() if v)
            full_prompt = f"Context:\n{ctx_summary}\n\nTask: {prompt}\nDraft professional text for official student chapter documentation."
            response = client.models.generate_content(
                model=self.model,
                contents=full_prompt,
            )
            return response.text.strip()
        except Exception:
            return DummyLLMClient().draft_text(prompt, context)


def get_llm_client() -> LLMClient:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return GeminiLLMClient(api_key=api_key)
    return DummyLLMClient()
