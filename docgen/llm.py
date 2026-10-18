"""Pluggable LLM client interface, Gemini REST implementation, and testing stubs."""

from __future__ import annotations

import copy
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Typed AI Service Errors
# ---------------------------------------------------------------------------


class AIServiceError(Exception):
    """Base error for AI service failures."""

    def __init__(self, message: str, code: str = "AI_SERVICE_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class AIAuthenticationError(AIServiceError):
    """Invalid or missing API key."""

    def __init__(self, message: str = "AI service error: Invalid or missing Gemini API key."):
        super().__init__(message, code="INVALID_API_KEY")


class AIQuotaError(AIServiceError):
    """Rate limit or quota exceeded."""

    def __init__(self, message: str = "AI service error: Gemini API quota exceeded or rate limit reached."):
        super().__init__(message, code="QUOTA_EXCEEDED")


class AITimeoutError(AIServiceError):
    """Request timed out."""

    def __init__(self, message: str = "AI service error: Gemini API request timed out."):
        super().__init__(message, code="TIMEOUT")


class AIBadResponseError(AIServiceError):
    """Malformed JSON or unexpected response from AI service."""

    def __init__(self, message: str = "AI service error: Malformed response from Gemini."):
        super().__init__(message, code="BAD_RESPONSE")


# ---------------------------------------------------------------------------
# Schema Inliner for Gemini OpenAPI Subset
# ---------------------------------------------------------------------------


def simplify_schema_for_gemini(raw_schema: dict[str, Any]) -> dict[str, Any]:
    """Inlines all $defs and $ref into an inline OpenAPI schema accepted by Gemini generationConfig.response_schema."""
    defs = raw_schema.get("$defs", {})

    def inline_refs(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].split("/")[-1]
                if ref_name in defs:
                    resolved = copy.deepcopy(defs[ref_name])
                    return inline_refs(resolved)
            res = {}
            for k, v in node.items():
                if k in ("$defs", "$schema", "title"):
                    continue
                res[k] = inline_refs(v)
            return res
        elif isinstance(node, list):
            return [inline_refs(item) for item in node]
        return node

    return inline_refs(raw_schema)


# ---------------------------------------------------------------------------
# LLM Client Base & Implementations
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    last_usage_metadata: Optional[dict[str, Any]] = None

    @property
    def model_name(self) -> str:
        return "abstract-model"

    @abstractmethod
    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON adhering to the provided JSON schema."""
        pass

    @abstractmethod
    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        """Draft narrative text (e.g. descriptions, objectives)."""
        pass

    def is_available(self) -> bool:
        """Check if the client is configured and ready to handle requests."""
        return True


class DummyLLMClient(LLMClient):
    """Fallback client when no API key or remote service is configured."""

    @property
    def model_name(self) -> str:
        return "dummy-model"

    def is_available(self) -> bool:
        return False

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise AIAuthenticationError("AI service error: Gemini API key not configured. Build template manually in editor.")

    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        raise AIAuthenticationError("AI service error: Gemini API key not configured.")


class StubLLMClient(LLMClient):
    """Configurable stub client for deterministic testing without network calls."""

    def __init__(
        self,
        default_json: Optional[dict[str, Any]] = None,
        responses_by_keyword: Optional[dict[str, dict[str, Any]]] = None,
        fail_attempts: int = 0,
        simulate_error: Optional[Exception] = None,
        simulated_usage: Optional[dict[str, Any]] = None,
        model: str = "stub-model-w5",
    ):
        self.default_json = default_json or {}
        self.responses_by_keyword = responses_by_keyword or {}
        self.fail_attempts = fail_attempts
        self.simulate_error = simulate_error
        self.simulated_usage = simulated_usage
        self.last_usage_metadata = simulated_usage
        self.attempt_count = 0
        self._model = model
        self.call_history: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return True

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.attempt_count += 1
        self.call_history.append({"prompt": prompt, "schema": schema, "attempt": self.attempt_count})

        if self.simulate_error:
            raise self.simulate_error

        # Simulate failures for retry testing
        if self.attempt_count <= self.fail_attempts:
            # Return an invalid structure that fails Pydantic schema
            return {"invalid": "payload_missing_required_fields"}

        if self.simulated_usage:
            self.last_usage_metadata = self.simulated_usage
        else:
            self.last_usage_metadata = {"tokens_in": None, "tokens_out": None, "usage_estimated": True}

        # Check keyword matches
        for kw, resp in self.responses_by_keyword.items():
            if kw.lower() in prompt.lower():
                return resp

        return self.default_json

    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        self.call_history.append({"prompt": prompt, "context": context})
        if self.simulate_error:
            raise self.simulate_error
        return "Stubbed drafted narrative text."


class GeminiLLMClient(LLMClient):
    """Google Gemini API implementation using requests / REST API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite"
        self.last_usage_metadata = None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def endpoint_url(self) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    @property
    def _endpoint_url(self) -> str:
        return self.endpoint_url

    def build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or "",
        }

    def _build_headers(self) -> dict[str, str]:
        return self.build_headers()

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.is_available():
            raise AIAuthenticationError("AI service error: Gemini API key not configured. Build template manually in editor.")

        import logging
        import requests

        logger = logging.getLogger(__name__)

        # Pass API key strictly in header, NEVER in URL query string
        url = self.endpoint_url
        headers = self.build_headers()

        simplified_schema = simplify_schema_for_gemini(schema)
        schema_json_str = json.dumps(simplified_schema, indent=2)
        prompt_with_schema = prompt if (schema_json_str in prompt or "TemplateSpec" in prompt) else f"{prompt}\n\nTarget JSON Schema:\n{schema_json_str}"

        # Standard JSON schema via responseJsonSchema (response_schema and responseSchema MUST be omitted)
        payload = {
            "contents": [{"parts": [{"text": prompt_with_schema}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": simplified_schema,
                "temperature": 0.1,
            },
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.exceptions.Timeout:
            raise AITimeoutError("AI service error: Gemini API request timed out.")
        except requests.exceptions.RequestException as e:
            logger.error("Network failure contacting Gemini API: %s", str(e))
            raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        # Check for 400 schema error -> retry ONCE without any schema (prompt-only JSON mode)
        if resp.status_code == 400:
            raw_err_msg = ""
            err_reason = ""
            try:
                err_json = resp.json()
                raw_err_msg = err_json.get("error", {}).get("message", "")
                details = err_json.get("error", {}).get("details", [])
                if details and isinstance(details[0], dict):
                    err_reason = details[0].get("reason", "")
            except Exception:
                raw_err_msg = resp.text[:300]

            is_auth_error = (
                err_reason == "API_KEY_INVALID"
                or "API key not valid" in raw_err_msg
                or "API_KEY" in raw_err_msg
            )
            if is_auth_error:
                logger.error("Gemini API authentication failed (HTTP 400): %s", raw_err_msg)
                raise AIAuthenticationError("AI service error: Invalid or expired API key")

            # Schema or payload issue: log server-side only and retry ONCE in prompt-only JSON mode
            logger.warning("Gemini rejected schema with HTTP 400 (%s). Retrying ONCE in prompt-only JSON mode.", raw_err_msg)
            fallback_payload = {
                "contents": [{"parts": [{"text": prompt_with_schema}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }
            try:
                resp = requests.post(url, headers=headers, json=fallback_payload, timeout=30)
            except requests.exceptions.Timeout:
                raise AITimeoutError("AI service error: Gemini API request timed out.")
            except requests.exceptions.RequestException as e:
                logger.error("Network failure contacting Gemini API on retry: %s", str(e))
                raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        if resp.status_code == 429:
            logger.warning("Gemini model '%s' hit HTTP 429 quota. Trying fallback models...", self.model)
            fallback_models = [m for m in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite") if m != self.model]
            for fb_model in fallback_models:
                fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fb_model}:generateContent"
                try:
                    fb_resp = requests.post(fb_url, headers=headers, json=payload, timeout=30)
                    if fb_resp.status_code == 200:
                        logger.info("Successfully completed request using fallback model '%s'", fb_model)
                        resp = fb_resp
                        break
                except Exception as fb_err:
                    logger.warning("Fallback model '%s' request failed: %s", fb_model, fb_err)

        if resp.status_code in (401, 403):
            logger.error("Gemini API authentication error (HTTP %d): %s", resp.status_code, resp.text[:300])
            raise AIAuthenticationError("AI service error: Invalid or expired API key")
        elif resp.status_code == 429:
            logger.error("Gemini API rate limit or quota exceeded (HTTP 429): %s", resp.text[:300])
            raise AIQuotaError("AI service error: Gemini API quota exceeded or rate limit reached.")
        elif resp.status_code != 200:
            logger.error("Gemini API returned error (HTTP %d): %s", resp.status_code, resp.text[:300])
            raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Failed to decode Gemini response as JSON: %s (raw: %s)", str(e), resp.text[:300])
            raise AIBadResponseError("AI could not draft this template right now. You can build it manually in the editor.")

        # Capture real token usage metadata from API
        usage_meta = data.get("usageMetadata", {})
        if usage_meta and "promptTokenCount" in usage_meta:
            self.last_usage_metadata = {
                "tokens_in": usage_meta.get("promptTokenCount"),
                "tokens_out": usage_meta.get("candidatesTokenCount") or (usage_meta.get("totalTokenCount", 0) - usage_meta.get("promptTokenCount", 0)),
                "usage_estimated": False,
            }
        else:
            self.last_usage_metadata = {
                "tokens_in": None,
                "tokens_out": None,
                "usage_estimated": True,
            }

        candidates = data.get("candidates", [])
        if not candidates:
            logger.error("Gemini returned empty candidates list: %s", data)
            raise AIBadResponseError("AI could not draft this template right now. You can build it manually in the editor.")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason and finish_reason not in ("STOP", None):
            logger.error("Gemini generation incomplete (finish_reason: %s): %s", finish_reason, data)
            raise AIBadResponseError("AI could not draft this template right now. You can build it manually in the editor.")

        text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            logger.error("Gemini candidate part had empty text: %s", data)
            raise AIBadResponseError("AI could not draft this template right now. You can build it manually in the editor.")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON generated by model: %s (raw output: %s)", str(e), text[:300])
            raise AIBadResponseError("AI could not draft this template right now. You can build it manually in the editor.")

    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        if not self.is_available():
            raise AIAuthenticationError("AI service error: Gemini API key not configured.")

        import requests

        url = self.endpoint_url
        headers = self.build_headers()
        ctx_summary = "\n".join(f"{k}: {v}" for k, v in context.items() if v)
        full_prompt = f"Context:\n{ctx_summary}\n\nTask: {prompt}\nDraft professional text for official student chapter documentation."
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.exceptions.Timeout:
            raise AITimeoutError("AI service error: Request timed out after 30 seconds.")
        except requests.exceptions.RequestException as e:
            raise AIServiceError(f"AI service error: Network failure ({str(e)})")

        if resp.status_code == 429:
            fallback_models = [m for m in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite") if m != self.model]
            for fb_model in fallback_models:
                fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fb_model}:generateContent"
                try:
                    fb_resp = requests.post(fb_url, headers=headers, json=payload, timeout=30)
                    if fb_resp.status_code == 200:
                        resp = fb_resp
                        break
                except Exception:
                    pass

        if resp.status_code in (400, 401, 403):
            raise AIAuthenticationError(f"AI service error: Invalid or expired API key (HTTP {resp.status_code}).")
        elif resp.status_code == 429:
            raise AIQuotaError("AI service error: Gemini API quota exceeded or rate limit reached.")
        elif resp.status_code != 200:
            raise AIServiceError(f"AI service error: HTTP {resp.status_code}")

        try:
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIBadResponseError("AI service error: No text candidates returned.")
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip()
        except Exception as e:
            raise AIBadResponseError(f"AI service error: Failed to parse response: {str(e)}")


_current_llm_client: Optional[LLMClient] = None


def set_llm_client(client: Optional[LLMClient]) -> None:
    """Explicitly set or reset the active LLM client (used in testing)."""
    global _current_llm_client
    _current_llm_client = client


def get_llm_client() -> LLMClient:
    """Retrieve the configured LLM client."""
    global _current_llm_client
    if _current_llm_client is not None:
        return _current_llm_client
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key.strip():
        model = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite"
        return GeminiLLMClient(api_key=api_key.strip(), model=model)
    return DummyLLMClient()
