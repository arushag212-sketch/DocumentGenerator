"""Pluggable LLM client interface, Gemini REST implementation, Groq fallback, response cache, and testing stubs."""

from __future__ import annotations

import copy
import hashlib
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


_CACHED_GROQ_MODELS: list[str] = []
_GROQ_CACHE_TIMESTAMP: float = 0.0


def clear_groq_model_cache() -> None:
    global _CACHED_GROQ_MODELS, _GROQ_CACHE_TIMESTAMP
    _CACHED_GROQ_MODELS = []
    _GROQ_CACHE_TIMESTAMP = 0.0


def discover_groq_models(api_key: Optional[str] = None, force_refresh: bool = False) -> list[str]:
    """
    Query https://api.groq.com/openai/v1/models using Bearer token.
    Filter to available chat/completion models.
    Cached in-memory for 1 hour.
    """
    global _CACHED_GROQ_MODELS, _GROQ_CACHE_TIMESTAMP
    now = time.time()
    if not force_refresh and _CACHED_GROQ_MODELS and (now - _GROQ_CACHE_TIMESTAMP < MODEL_CACHE_TTL):
        return list(_CACHED_GROQ_MODELS)

    fallback_candidates = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ]

    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key or not key.strip():
        _CACHED_GROQ_MODELS = fallback_candidates
        _GROQ_CACHE_TIMESTAMP = now
        return list(_CACHED_GROQ_MODELS)

    import requests

    try:
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {key.strip()}"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            valid_models = []
            for item in data:
                m_id = item.get("id", "")
                if any(x in m_id.lower() for x in ["whisper", "prompt-guard", "safeguard", "orpheus"]):
                    continue
                valid_models.append(m_id)
            if valid_models:
                pref_order = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
                ordered = [p for p in pref_order if p in valid_models] + [v for v in valid_models if v not in pref_order]
                _CACHED_GROQ_MODELS = ordered
                _GROQ_CACHE_TIMESTAMP = now
                return list(_CACHED_GROQ_MODELS)
    except Exception:
        pass

    _CACHED_GROQ_MODELS = fallback_candidates
    _GROQ_CACHE_TIMESTAMP = now
    return list(_CACHED_GROQ_MODELS)


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
            # Free-form objects (e.g. `dict[str, Any]` payloads) must stay open. An explicit
            # empty `properties` would constrain the model to return `{}` for them.
            if res.get("type") == "object" and "properties" in res and not res["properties"]:
                del res["properties"]
            return res
        elif isinstance(node, list):
            return [inline_refs(item) for item in node]
        return node

    return inline_refs(raw_schema)


# ---------------------------------------------------------------------------
# Cache Key Computation & Database Session Helper
# ---------------------------------------------------------------------------


def compute_cache_key(
    kind: str,
    model: str,
    temperature: float,
    prompt: str,
    payload_or_context: Any,
    club_id: Optional[str] = None,
) -> str:
    """
    Compute sha256 of: kind + model name + temperature + prompt + JSON schema/context (sorted) + club_id.
    Ensures different clubs or prompts never collide.
    """
    if isinstance(payload_or_context, (dict, list)):
        payload_str = json.dumps(payload_or_context, sort_keys=True)
    else:
        payload_str = str(payload_or_context or "")

    raw = (
        f"kind:{kind}\n"
        f"model:{model}\n"
        f"temp:{temperature:.4f}\n"
        f"club_id:{club_id or ''}\n"
        f"prompt:{prompt}\n"
        f"payload:{payload_str}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_cache_db():
    """Acquire a database session for cache operations, or None if unavailable."""
    try:
        from server.app.core.database import SessionLocal
        return SessionLocal()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LLM Client Base & Implementations
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    last_usage_metadata: Optional[dict[str, Any]] = None

    @property
    def model_name(self) -> str:
        return "abstract-model"

    @property
    def temperature(self) -> float:
        return 0.0

    @abstractmethod
    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
        """Generate structured JSON adhering to the provided JSON schema."""
        pass

    @abstractmethod
    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
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

    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
        raise AIAuthenticationError("AI service error: Gemini API key not configured. Build template manually in editor.")

    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
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
        temperature: float = 0.0,
    ):
        self.default_json = default_json or {}
        self.responses_by_keyword = responses_by_keyword or {}
        self.fail_attempts = fail_attempts
        self.simulate_error = simulate_error
        self.simulated_usage = simulated_usage
        self.last_usage_metadata = simulated_usage
        self.attempt_count = 0
        self._model = model
        self._temperature = temperature
        self.call_history: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def temperature(self) -> float:
        return self._temperature

    def is_available(self) -> bool:
        return True

    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
        self.attempt_count += 1
        self.call_history.append({"prompt": prompt, "schema": schema, "club_id": club_id, "attempt": self.attempt_count})

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

    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
        self.call_history.append({"prompt": prompt, "context": context, "club_id": club_id})
        if self.simulate_error:
            raise self.simulate_error
        return "Stubbed drafted narrative text."


class GeminiLLMClient(LLMClient):
    """Google Gemini API implementation using requests / REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
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

        if temperature is not None:
            self._temperature = float(temperature)
        else:
            try:
                self._temperature = float(os.environ.get("AI_TEMPERATURE", "0"))
            except (ValueError, TypeError):
                self._temperature = 0.0

        self.last_usage_metadata = None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def temperature(self) -> float:
        return self._temperature

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

    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
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
                "temperature": self._temperature,
                "topP": 1.0,
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
                    "temperature": self._temperature,
                    "topP": 1.0,
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

    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
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
            "generationConfig": {
                "temperature": self._temperature,
                "topP": 1.0,
            },
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

        if resp.status_code in (401, 403):
            raise AIAuthenticationError("Gemini API key is invalid or expired. Check your .env.")
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
        except Exception:
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")


class GroqLLMClient(LLMClient):
    """Groq API implementation using OpenAI-compatible REST API (https://api.groq.com/openai/v1/chat/completions)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        if temperature is not None:
            self._temperature = float(temperature)
        else:
            try:
                self._temperature = float(os.environ.get("AI_TEMPERATURE", "0"))
            except (ValueError, TypeError):
                self._temperature = 0.0
        self.last_usage_metadata = None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def endpoint_url(self) -> str:
        return "https://api.groq.com/openai/v1/chat/completions"

    def build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
        }

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
        if not self.is_available():
            raise AIAuthenticationError("AI service error: Groq API key not configured.")

        import logging
        import requests

        logger = logging.getLogger(__name__)

        system_instruction = (
            "You are a helpful structured JSON assistant. Output valid JSON strictly conforming to the following JSON schema:\n"
            f"{json.dumps(schema, indent=2)}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self._temperature,
        }

        headers = self.build_headers()

        current_model = self.model
        try:
            resp = requests.post(self.endpoint_url, headers=headers, json=payload, timeout=30)
        except requests.exceptions.Timeout:
            raise AITimeoutError("AI service timed out after 30s. Try a shorter prompt.")
        except requests.exceptions.RequestException as e:
            logger.error("Network failure contacting Groq API: %s", str(e))
            raise AIServiceError(f"AI service network failure contacting Groq: {str(e)}")

        if resp.status_code == 404:
            logger.warning("Groq model '%s' returned 404. Invalidating cache and switching to next model.", current_model)
            refreshed = discover_groq_models(self.api_key, force_refresh=True)
            next_models = [m for m in refreshed if m != current_model]
            if next_models:
                self.model = next_models[0]
                current_model = self.model
                payload["model"] = current_model
                try:
                    resp = requests.post(self.endpoint_url, headers=headers, json=payload, timeout=30)
                except requests.exceptions.Timeout:
                    raise AITimeoutError("AI service timed out after 30s. Try a shorter prompt.")
                except requests.exceptions.RequestException as e:
                    logger.error("Network failure contacting Groq API on 404 fallback: %s", str(e))
                    raise AIServiceError(f"AI service network failure contacting Groq: {str(e)}")

        if resp.status_code in (401, 403):
            logger.error("Groq API authentication error (HTTP %d): %s", resp.status_code, resp.text[:300])
            raise AIAuthenticationError("Groq API key is invalid or expired. Check your .env.")
        elif resp.status_code == 429:
            logger.error("Groq API rate limit or quota exceeded (HTTP 429): %s", resp.text[:300])
            raise AIQuotaError("Groq API quota exceeded or rate limit reached.")
        elif resp.status_code != 200:
            logger.error("Groq API returned error (HTTP %d): %s", resp.status_code, resp.text[:300])
            raise AIServiceError(f"Groq API returned error (HTTP {resp.status_code}): {resp.text[:300]}")

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Failed to decode Groq response as JSON: %s (raw: %s)", str(e), resp.text[:300])
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        usage_meta = data.get("usage", {})
        if usage_meta and "prompt_tokens" in usage_meta:
            self.last_usage_metadata = {
                "tokens_in": usage_meta.get("prompt_tokens"),
                "tokens_out": usage_meta.get("completion_tokens"),
                "usage_estimated": False,
            }
        else:
            self.last_usage_metadata = {
                "tokens_in": None,
                "tokens_out": None,
                "usage_estimated": True,
            }

        choices = data.get("choices", [])
        if not choices:
            logger.error("Groq returned empty choices list: %s", data)
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        message = choices[0].get("message", {})
        text = message.get("content", "")
        if not text:
            logger.error("Groq choice message had empty content: %s", data)
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        try:
            parsed_data = json.loads(text)
            if not isinstance(parsed_data, dict):
                raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON generated by Groq: %s (raw: %s)", str(e), text[:300])
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        if schema:
            try:
                import jsonschema
                jsonschema.validate(instance=parsed_data, schema=schema)
            except Exception as val_err:
                logger.error("Groq JSON response failed schema validation: %s", str(val_err))
                raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")

        return parsed_data

    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
        if not self.is_available():
            raise AIAuthenticationError("AI service error: Groq API key not configured.")

        import logging
        import requests

        logger = logging.getLogger(__name__)

        ctx_summary = "\n".join(f"{k}: {v}" for k, v in context.items() if v)
        full_prompt = f"Context:\n{ctx_summary}\n\nTask: {prompt}\nDraft professional text for official student chapter documentation."

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional documentation drafting assistant for official student chapter documentation.",
                },
                {"role": "user", "content": full_prompt},
            ],
            "temperature": self._temperature,
        }

        headers = self.build_headers()

        current_model = self.model
        try:
            resp = requests.post(self.endpoint_url, headers=headers, json=payload, timeout=12)
        except requests.exceptions.Timeout:
            raise AITimeoutError("AI service timed out after 12s. Try a shorter prompt.")
        except requests.exceptions.RequestException as e:
            logger.error("Network failure contacting Groq API in draft_text: %s", str(e))
            raise AIServiceError(f"AI service error: Network failure ({str(e)})")

        if resp.status_code == 404:
            refreshed = discover_groq_models(self.api_key, force_refresh=True)
            next_models = [m for m in refreshed if m != current_model]
            if next_models:
                self.model = next_models[0]
                current_model = self.model
                payload["model"] = current_model
                try:
                    resp = requests.post(self.endpoint_url, headers=headers, json=payload, timeout=12)
                except requests.exceptions.Timeout:
                    raise AITimeoutError("AI service timed out after 12s. Try a shorter prompt.")
                except requests.exceptions.RequestException as e:
                    raise AIServiceError(f"AI service error: Network failure ({str(e)})")

        if resp.status_code in (401, 403):
            raise AIAuthenticationError("Groq API key is invalid or expired. Check your .env.")
        elif resp.status_code == 429:
            raise AIQuotaError("Groq API quota exceeded or rate limit reached.")
        elif resp.status_code != 200:
            raise AIServiceError(f"AI service error: HTTP {resp.status_code}")

        try:
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")
            text = choices[0].get("message", {}).get("content", "")
            if not text:
                raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")
            return text.strip()
        except (AIBadResponseError, AIAuthenticationError, AIQuotaError, AIServiceError, AITimeoutError):
            raise
        except Exception:
            raise AIBadResponseError("AI service returned invalid data. You can build this manually in the editor.")


class FallbackLLMClient(LLMClient):
    """Attempts requests on Gemini first; on quota/rate-limit (429), timeout, or 5xx/network errors, retries once on Groq."""

    def __init__(self, primary: LLMClient, secondary: LLMClient):
        self.primary = primary
        self.secondary = secondary
        self._last_active_model: Optional[str] = None
        self.last_usage_metadata = None

    @property
    def model_name(self) -> str:
        return self._last_active_model or self.primary.model_name

    @property
    def temperature(self) -> float:
        return getattr(self.primary, "temperature", 0.0)

    def candidate_model_names(self) -> list[str]:
        return [self.primary.model_name, self.secondary.model_name]

    def is_available(self) -> bool:
        return self.primary.is_available() or self.secondary.is_available()

    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)

        try:
            try:
                res = self.primary.generate_json(prompt, schema, club_id=club_id)
            except TypeError:
                res = self.primary.generate_json(prompt, schema)
            self._last_active_model = self.primary.model_name
            self.last_usage_metadata = self.primary.last_usage_metadata
            logger.info("AI request answered by primary provider (%s)", self.primary.model_name)
            return res
        except (AIAuthenticationError, AIBadResponseError):
            # Don't fall back on invalid-key errors from Gemini (raise them so the owner sees the config problem),
            # and don't fall back on invalid-data errors.
            raise
        except (AIQuotaError, AITimeoutError, AIServiceError) as gemini_err:
            logger.warning(
                "Primary provider (%s) failed with %s (%s). Retrying request once on fallback provider (%s)...",
                self.primary.model_name,
                type(gemini_err).__name__,
                str(gemini_err),
                self.secondary.model_name,
            )
            try:
                try:
                    res = self.secondary.generate_json(prompt, schema, club_id=club_id)
                except TypeError:
                    res = self.secondary.generate_json(prompt, schema)
                self._last_active_model = self.secondary.model_name
                self.last_usage_metadata = self.secondary.last_usage_metadata
                logger.info("AI request answered by fallback provider (%s)", self.secondary.model_name)
                return res
            except Exception as secondary_err:
                logger.error(
                    "Fallback provider (%s) failed with %s. Raising original primary error: %s",
                    self.secondary.model_name,
                    str(secondary_err),
                    str(gemini_err),
                )
                raise gemini_err

    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
        import logging
        logger = logging.getLogger(__name__)

        try:
            try:
                res = self.primary.draft_text(prompt, context, club_id=club_id)
            except TypeError:
                res = self.primary.draft_text(prompt, context)
            self._last_active_model = self.primary.model_name
            self.last_usage_metadata = self.primary.last_usage_metadata
            logger.info("AI request answered by primary provider (%s)", self.primary.model_name)
            return res
        except (AIAuthenticationError, AIBadResponseError):
            raise
        except (AIQuotaError, AITimeoutError, AIServiceError) as gemini_err:
            logger.warning(
                "Primary provider (%s) failed with %s (%s). Retrying draft request once on fallback provider (%s)...",
                self.primary.model_name,
                type(gemini_err).__name__,
                str(gemini_err),
                self.secondary.model_name,
            )
            try:
                try:
                    res = self.secondary.draft_text(prompt, context, club_id=club_id)
                except TypeError:
                    res = self.secondary.draft_text(prompt, context)
                self._last_active_model = self.secondary.model_name
                self.last_usage_metadata = self.secondary.last_usage_metadata
                logger.info("AI request answered by fallback provider (%s)", self.secondary.model_name)
                return res
            except Exception as secondary_err:
                logger.error(
                    "Fallback provider (%s) failed with %s. Raising original primary error: %s",
                    self.secondary.model_name,
                    str(secondary_err),
                    str(gemini_err),
                )
                raise gemini_err


class CachedLLMClient(LLMClient):
    """Transparent caching wrapper for LLM clients using SQLAlchemy AICache."""

    def __init__(
        self,
        inner: LLMClient,
        ttl_hours: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        self.inner = inner
        if ttl_hours is not None:
            self.ttl_hours = ttl_hours
        else:
            try:
                self.ttl_hours = int(os.environ.get("AI_CACHE_TTL_HOURS", "168"))
            except (ValueError, TypeError):
                self.ttl_hours = 168

        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.environ.get("AI_CACHE_ENABLED", "true").strip().lower() in ("true", "1", "yes", "on")

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    @property
    def temperature(self) -> float:
        return getattr(self.inner, "temperature", 0.0)

    @property
    def last_usage_metadata(self) -> Optional[dict[str, Any]]:
        return self.inner.last_usage_metadata

    def is_available(self) -> bool:
        return self.inner.is_available()

    def candidate_model_names(self) -> list[str]:
        if hasattr(self.inner, "candidate_model_names"):
            return self.inner.candidate_model_names()
        return [self.inner.model_name]

    def _lookup(
        self,
        kind: str,
        prompt: str,
        payload_or_context: Any,
        club_id: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """Look up response from cache. Returns (cached_str, model_name) or (None, None)."""
        if not self.enabled:
            return None, None

        db = _get_cache_db()
        if db is None:
            return None, None

        try:
            from server.app.models import AICache
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            candidate_models = self.candidate_model_names()

            for cand_model in candidate_models:
                key = compute_cache_key(
                    kind=kind,
                    model=cand_model,
                    temperature=self.temperature,
                    prompt=prompt,
                    payload_or_context=payload_or_context,
                    club_id=club_id,
                )
                entry = db.query(AICache).filter(AICache.key == key).first()
                if entry:
                    # Check expiry
                    age_seconds = (now - entry.created_at).total_seconds()
                    if age_seconds > (self.ttl_hours * 3600):
                        # Expired: delete lazily
                        db.delete(entry)
                        db.commit()
                        continue

                    # Cache hit! Bump hits and return
                    entry.hits += 1
                    db.commit()
                    if hasattr(self.inner, "_last_active_model"):
                        self.inner._last_active_model = entry.model
                    return entry.response, entry.model

            return None, None
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("AI cache lookup failed: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return None, None
        finally:
            try:
                db.close()
            except Exception:
                pass

    def _store(
        self,
        kind: str,
        model: str,
        prompt: str,
        payload_or_context: Any,
        club_id: Optional[str],
        response_str: str,
    ) -> None:
        """Store valid successful response in cache."""
        if not self.enabled:
            return

        db = _get_cache_db()
        if db is None:
            return

        try:
            from server.app.models import AICache
            from datetime import datetime, timezone

            key = compute_cache_key(
                kind=kind,
                model=model,
                temperature=self.temperature,
                prompt=prompt,
                payload_or_context=payload_or_context,
                club_id=club_id,
            )
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            existing = db.query(AICache).filter(AICache.key == key).first()
            if existing:
                existing.response = response_str
                existing.created_at = now
            else:
                entry = AICache(
                    key=key,
                    club_id=club_id,
                    kind=kind,
                    model=model,
                    response=response_str,
                    created_at=now,
                    hits=0,
                )
                db.add(entry)
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("AI cache store failed: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass

    def generate_json(self, prompt: str, schema: dict[str, Any], club_id: Optional[str] = None) -> dict[str, Any]:
        cached_str, _ = self._lookup(kind="json", prompt=prompt, payload_or_context=schema, club_id=club_id)
        if cached_str is not None:
            try:
                return json.loads(cached_str)
            except Exception:
                pass

        try:
            res = self.inner.generate_json(prompt, schema, club_id=club_id)
        except TypeError:
            res = self.inner.generate_json(prompt, schema)

        if isinstance(res, dict) and res:
            self._store(
                kind="json",
                model=self.inner.model_name,
                prompt=prompt,
                payload_or_context=schema,
                club_id=club_id,
                response_str=json.dumps(res, sort_keys=True),
            )
        return res

    def draft_text(self, prompt: str, context: dict[str, Any], club_id: Optional[str] = None) -> str:
        cached_str, _ = self._lookup(kind="text", prompt=prompt, payload_or_context=context, club_id=club_id)
        if cached_str is not None:
            return cached_str

        try:
            res = self.inner.draft_text(prompt, context, club_id=club_id)
        except TypeError:
            res = self.inner.draft_text(prompt, context)

        if isinstance(res, str) and res.strip():
            self._store(
                kind="text",
                model=self.inner.model_name,
                prompt=prompt,
                payload_or_context=context,
                club_id=club_id,
                response_str=res,
            )
        return res


_current_llm_client: Optional[LLMClient] = None


def set_llm_client(client: Optional[LLMClient]) -> None:
    """Explicitly set or reset the active LLM client (used in testing)."""
    global _current_llm_client
    _current_llm_client = client


def get_llm_client() -> LLMClient:
    """Retrieve the configured LLM client.

    Uses FallbackLLMClient when both GEMINI_API_KEY and GROQ_API_KEY are set,
    only Gemini when just Gemini is set, only Groq when just Groq is set,
    and DummyLLMClient when neither is set.
    Wraps with CachedLLMClient when AI_CACHE_ENABLED is true.
    """
    global _current_llm_client
    if _current_llm_client is not None:
        return _current_llm_client

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    gemini_client: Optional[GeminiLLMClient] = None
    if gemini_key:
        gemini_model = os.environ.get("GEMINI_MODEL")
        gemini_client = GeminiLLMClient(api_key=gemini_key, model=gemini_model)

    groq_client: Optional[GroqLLMClient] = None
    if groq_key:
        groq_model = os.environ.get("GROQ_MODEL")
        groq_client = GroqLLMClient(api_key=groq_key, model=groq_model)

    base: LLMClient
    if gemini_client and groq_client:
        base = FallbackLLMClient(primary=gemini_client, secondary=groq_client)
    elif gemini_client:
        base = gemini_client
    elif groq_client:
        base = groq_client
    else:
        return DummyLLMClient()

    cache_enabled = os.environ.get("AI_CACHE_ENABLED", "true").strip().lower() in ("true", "1", "yes", "on")
    if cache_enabled:
        return CachedLLMClient(inner=base)
    return base
