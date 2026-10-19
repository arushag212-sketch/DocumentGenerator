"""Pluggable LLM client interface, Gemini REST implementation, and testing stubs."""

from __future__ import annotations

import copy
import json
import os
import re
import time
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

    def __init__(self, message: str = "Gemini API key is invalid or expired. Check your .env."):
        super().__init__(message, code="INVALID_API_KEY")


class AIQuotaError(AIServiceError):
    """Rate limit or quota exceeded."""

    def __init__(self, message: str = "Gemini API quota exceeded or rate limit reached. Tip: Set GEMINI_API_KEY in your environment or .env to activate live Gemini AI drafting. Alternatively, click 'New Blank Template' above to compose manually in the WYSIWYG editor."):
        super().__init__(message, code="QUOTA_EXCEEDED")


class AITimeoutError(AIServiceError):
    """Request timed out."""

    def __init__(self, message: str = "AI service timed out after 30s. Try a shorter prompt."):
        super().__init__(message, code="TIMEOUT")


class AIBadResponseError(AIServiceError):
    """Malformed JSON or unexpected response from AI service."""

    def __init__(self, message: str = "AI service returned invalid data. You can build this manually in the editor."):
        super().__init__(message, code="BAD_RESPONSE")


# ---------------------------------------------------------------------------
# Dynamic Model Discovery & Cache
# ---------------------------------------------------------------------------

_CACHED_MODELS: list[str] = []
_CACHE_TIMESTAMP: float = 0.0
MODEL_CACHE_TTL: float = 3600.0  # 1 hour


def clear_model_cache() -> None:
    """Clear in-memory model discovery cache (used in testing)."""
    global _CACHED_MODELS, _CACHE_TIMESTAMP
    _CACHED_MODELS = []
    _CACHE_TIMESTAMP = 0.0


def discover_gemini_models(api_key: Optional[str] = None, force_refresh: bool = False) -> list[str]:
    """
    Query https://generativelanguage.googleapis.com/v1beta/models using x-goog-api-key header.
    Filter to models supporting generateContent and containing 'flash'.
    Order:
      1. Newest non-preview flash models
      2. Other flash models / gemini-flash-latest
    Cached in-memory for 1 hour.
    """
    global _CACHED_MODELS, _CACHE_TIMESTAMP
    now = time.time()
    if not force_refresh and _CACHED_MODELS and (now - _CACHE_TIMESTAMP < MODEL_CACHE_TTL):
        return list(_CACHED_MODELS)

    key = api_key or os.environ.get("GEMINI_API_KEY")
    fallback_candidates = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
    ]

    if not key or not key.strip():
        _CACHED_MODELS = fallback_candidates
        _CACHE_TIMESTAMP = now
        return list(_CACHED_MODELS)

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"Content-Type": "application/json", "x-goog-api-key": key.strip()}

    import requests

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            raw_models = data.get("models", [])
            valid_models = []
            for m in raw_models:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "flash" in name.lower():
                    # Exclude specialized modalities and deprecated models
                    if any(sub in name.lower() for sub in ["-image", "-tts", "gemini-2.5-flash", "gemini-2.5-pro"]):
                        continue
                    valid_models.append(name)

            if valid_models:
                def _version_key(name: str):
                    is_preview = 1 if any(p in name.lower() for p in ["preview", "exp", "experimental"]) else 0
                    is_healthy = 1 if any(h in name.lower() for h in ["3.5-flash", "3.6-flash", "3.7-flash", "flash-lite-latest"]) else 0
                    match = re.search(r"(\d+(?:\.\d+)*)", name)
                    if match:
                        parts = tuple(int(x) for x in match.group(1).split("."))
                    else:
                        parts = (0,)
                    return (is_healthy, -is_preview, parts)

                valid_models.sort(key=_version_key, reverse=True)

                _CACHED_MODELS = valid_models
                _CACHE_TIMESTAMP = now
                return list(_CACHED_MODELS)
    except Exception:
        pass

    _CACHED_MODELS = fallback_candidates
    _CACHE_TIMESTAMP = now
    return list(_CACHED_MODELS)


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
                if k in ("$defs", "$schema", "title", "additionalProperties"):
                    continue
                res[k] = inline_refs(v)
            if res.get("type") == "object" and not res.get("properties"):
                res["properties"] = {}
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
        if model:
            self.model = model
        else:
            candidates = discover_gemini_models(self.api_key)
            env_model = os.environ.get("GEMINI_MODEL")
            if env_model and env_model in candidates:
                self.model = env_model
            elif candidates:
                self.model = candidates[0]
            else:
                self.model = "gemini-flash-latest"
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

        simplified_schema = simplify_schema_for_gemini(schema)
        schema_json_str = json.dumps(simplified_schema, indent=2)
        prompt_with_schema = prompt if (schema_json_str in prompt or "TemplateSpec" in prompt) else f"{prompt}\n\nTarget JSON Schema:\n{schema_json_str}"

        payload = {
            "contents": [{"parts": [{"text": prompt_with_schema}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": simplified_schema,
                "temperature": 0.1,
            },
        }

        candidates = discover_gemini_models(self.api_key)
        if self.model not in candidates:
            candidates = [self.model] + candidates
        else:
            candidates = [self.model] + [m for m in candidates if m != self.model]

        current_model = self.model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
        headers = self.build_headers()

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.exceptions.Timeout:
            raise AITimeoutError("AI service timed out after 30s. Try a shorter prompt.")
        except requests.exceptions.RequestException as e:
            logger.error("Network failure contacting Gemini API: %s", str(e))
            raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        # On 404 ("model not found" or "no longer available"): invalidate cache, re-fetch list, switch to next candidate flash model, retry ONCE
        if resp.status_code == 404:
            logger.warning("Gemini model '%s' returned 404. Invalidating cache and switching to next model.", current_model)
            refreshed_candidates = discover_gemini_models(self.api_key, force_refresh=True)
            next_models = [m for m in refreshed_candidates if m != current_model]
            if next_models:
                self.model = next_models[0]
                current_model = self.model
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                except requests.exceptions.Timeout:
                    raise AITimeoutError("AI service timed out after 30s. Try a shorter prompt.")
                except requests.exceptions.RequestException as e:
                    logger.error("Network failure contacting Gemini API on 404 fallback: %s", str(e))
                    raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        active_payload = payload
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
                raise AIAuthenticationError("Gemini API key is invalid or expired. Check your .env.")

            logger.warning("Gemini rejected schema with HTTP 400 (%s). Retrying ONCE in prompt-only JSON mode.", raw_err_msg)
            active_payload = {
                "contents": [{"parts": [{"text": prompt_with_schema}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }
            try:
                resp = requests.post(url, headers=headers, json=active_payload, timeout=30)
            except requests.exceptions.Timeout:
                raise AITimeoutError("AI service timed out after 30s. Try a shorter prompt.")
            except requests.exceptions.RequestException as e:
                logger.error("Network failure contacting Gemini API on retry: %s", str(e))
                raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        # On 429 or 503 ("quota exceeded" or "high demand"): try candidate flash models in order
        if resp.status_code in (429, 503):
            logger.warning("Gemini model '%s' hit HTTP %d. Trying fallback models with 1s backoff...", current_model, resp.status_code)
            alt_candidates = [m for m in candidates if m != current_model][:4]
            for fb_model in alt_candidates:
                time.sleep(1)
                fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fb_model}:generateContent"
                try:
                    fb_resp = requests.post(fb_url, headers=headers, json=active_payload, timeout=30)
                    if fb_resp.status_code == 200:
                        logger.info("Successfully completed request using fallback model '%s'", fb_model)
                        self.model = fb_model
                        resp = fb_resp
                        break
                    elif fb_resp.status_code not in (429, 503, 404):
                        resp = fb_resp
                        break
                except Exception as fb_err:
                    logger.warning("Fallback model '%s' request failed: %s", fb_model, fb_err)

        if resp.status_code in (401, 403):
            logger.error("Gemini API authentication error (HTTP %d): %s", resp.status_code, resp.text[:300])
            raise AIAuthenticationError("Gemini API key is invalid or expired. Check your .env.")
        elif resp.status_code == 429:
            logger.error("Gemini API rate limit or quota exceeded (HTTP 429): %s", resp.text[:300])
            raise AIQuotaError("Gemini API quota exceeded or rate limit reached. Tip: Set GEMINI_API_KEY in your environment or .env to activate live Gemini AI drafting. Alternatively, click 'New Blank Template' above to compose manually in the WYSIWYG editor.")
        elif resp.status_code != 200:
            logger.error("Gemini API returned error (HTTP %d): %s", resp.status_code, resp.text[:300])
            raise AIServiceError("AI could not draft this template right now. You can build it manually in the editor.")

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Failed to decode Gemini response as JSON: %s (raw: %s)", str(e), resp.text[:300])
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

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

        candidates_list = data.get("candidates", [])
        if not candidates_list:
            logger.error("Gemini returned empty candidates list: %s", data)
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        candidate = candidates_list[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason and finish_reason not in ("STOP", None):
            logger.error("Gemini generation incomplete (finish_reason: %s): %s", finish_reason, data)
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            logger.error("Gemini candidate part had empty text: %s", data)
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON generated by model: %s (raw output: %s)", str(e), text[:300])
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

    def draft_text(self, prompt: str, context: dict[str, Any]) -> str:
        if not self.is_available():
            raise AIAuthenticationError("AI service error: Gemini API key not configured.")

        import requests

        candidates = discover_gemini_models(self.api_key)
        if self.model not in candidates:
            candidates = [self.model] + candidates
        else:
            candidates = [self.model] + [m for m in candidates if m != self.model]

        current_model = self.model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
        headers = self.build_headers()
        ctx_summary = "\n".join(f"{k}: {v}" for k, v in context.items() if v)
        full_prompt = f"Context:\n{ctx_summary}\n\nTask: {prompt}\nDraft professional text for official student chapter documentation."
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
        except requests.exceptions.Timeout:
            raise AITimeoutError("AI service timed out after 12s. Try a shorter prompt.")
        except requests.exceptions.RequestException as e:
            raise AIServiceError(f"AI service error: Network failure ({str(e)})")

        if resp.status_code == 404:
            refreshed_candidates = discover_gemini_models(self.api_key, force_refresh=True)
            next_models = [m for m in refreshed_candidates if m != current_model]
            if next_models:
                self.model = next_models[0]
                current_model = self.model
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=12)
                except requests.exceptions.Timeout:
                    raise AITimeoutError("AI service timed out after 12s. Try a shorter prompt.")
                except requests.exceptions.RequestException as e:
                    raise AIServiceError(f"AI service error: Network failure ({str(e)})")

        if resp.status_code == 429:
            raise AIQuotaError("Gemini API quota exceeded or rate limit reached.")

        if resp.status_code in (400, 401, 403):
            raise AIAuthenticationError(f"Gemini API key is invalid or expired. Check your .env.")
        elif resp.status_code == 429:
            raise AIQuotaError("Gemini API quota exceeded or rate limit reached. Tip: Set GEMINI_API_KEY in your environment or .env to activate live Gemini AI drafting. Alternatively, click 'New Blank Template' above to compose manually in the WYSIWYG editor.")
        elif resp.status_code != 200:
            raise AIServiceError(f"AI service error: HTTP {resp.status_code}")

        try:
            data = resp.json()
            candidates_list = data.get("candidates", [])
            if not candidates_list:
                raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")
            text = candidates_list[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip()
        except Exception as e:
            raise AIBadResponseError(f"AI service returned invalid data. You can build this manually in the editor.")


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
        model = os.environ.get("GEMINI_MODEL")
        return GeminiLLMClient(api_key=api_key.strip(), model=model)
    return DummyLLMClient()

