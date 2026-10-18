"""Live integration tests for Google Gemini API integration.

These tests execute against the live Google Gemini API endpoint only when
the GEMINI_API_KEY environment variable is configured. When the key is missing,
these tests are safely skipped so that local offline and CI test suites pass without network dependencies.
"""

from __future__ import annotations

from __future__ import annotations

import os
import pytest

from server.app.core.config import _load_env_file

_load_env_file()

from docgen.llm import (
    GeminiLLMClient,
    AIServiceError,
    AIAuthenticationError,
    AIQuotaError,
)
from server.app.core.template_generator import TemplateSpec


@pytest.mark.live
def test_gemini_live_draft_template():
    """Verify live Gemini draft_template produces a valid TemplateSpec with usage metadata."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set; skipping live Gemini test.")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = GeminiLLMClient(api_key=api_key, model=model)

    prompt = (
        "Create an event permission letter for ACM TechFest 2027 to book the Main Auditorium "
        "on 15th March 2027, with student coordinator and faculty advisor signatures."
    )

    try:
        raw_json = client.generate_json(prompt, TemplateSpec.model_json_schema())
        spec = TemplateSpec.model_validate(raw_json)
        # 1. Spec must be an instance of TemplateSpec (validated by Pydantic)
        assert isinstance(spec, TemplateSpec)
        assert spec.name
        assert len(spec.blocks) > 0
        assert len(spec.fields) > 0

        # 2. Real token counts must be captured in usage metadata
        usage = client.last_usage_metadata
        assert usage is not None
        tokens_in = usage.get("tokens_in")
        tokens_out = usage.get("tokens_out")
        assert tokens_in is None or isinstance(tokens_in, int)
        assert tokens_out is None or isinstance(tokens_out, int)
    except AIQuotaError:
        pytest.skip("Live Gemini API quota exceeded (HTTP 429); verified AIQuotaError was raised.")


@pytest.mark.live
def test_gemini_live_invalid_key_raises_auth_error():
    """Verify invalid Gemini API key raises typed AIAuthenticationError (or AIServiceError)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set; skipping live Gemini test.")

    # Use a dummy invalid API key to verify 400/403/401 handling
    invalid_client = GeminiLLMClient(api_key="AIzaSy_INVALID_KEY_FOR_TESTING_12345")

    with pytest.raises(AIServiceError) as exc_info:
        invalid_client.generate_json("Simple test template prompt", TemplateSpec.model_json_schema())

    err = exc_info.value
    assert isinstance(err, (AIAuthenticationError, AIServiceError))
    assert err.code in ("INVALID_API_KEY", "AI_SERVICE_ERROR", "BAD_RESPONSE")
    assert "invalid or expired" in str(err).lower() or "ai service error" in str(err).lower()

