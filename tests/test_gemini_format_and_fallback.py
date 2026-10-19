"""Unit tests for Gemini request format and fallback behavior (no network calls)."""

from unittest.mock import MagicMock, patch
import pytest

from docgen.llm import (
    GeminiLLMClient,
    AIAuthenticationError,
    AIServiceError,
)


def _mock_success_response(text: str = '{"template_id": "test", "title": "Test Template"}'):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": text}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 50,
            "totalTokenCount": 150,
        },
    }
    return mock_resp


def test_gemini_request_format_standard():
    """Assert request body contains responseJsonSchema and no response_schema/responseSchema."""
    client = GeminiLLMClient(api_key="test-api-key", model="gemini-2.5-flash")

    dummy_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "field": {"type": "number"},
        },
        "required": ["title"],
    }

    mock_resp = _mock_success_response()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = client.generate_json(
            prompt="Draft a permission letter",
            schema=dummy_schema,
        )

        assert mock_post.call_count == 1
        args, kwargs = mock_post.call_args

        # URL and header checks
        assert "x-goog-api-key" in kwargs["headers"]
        assert kwargs["headers"]["x-goog-api-key"] == "test-api-key"
        assert "key=" not in args[0]  # Key must not be in query parameters

        # Generation config checks
        gen_config = kwargs["json"]["generationConfig"]
        assert gen_config.get("responseMimeType") == "application/json"
        assert "responseJsonSchema" in gen_config
        assert "response_schema" not in gen_config
        assert "responseSchema" not in gen_config
        assert gen_config["responseJsonSchema"]["type"] == "object"

        assert result == {"template_id": "test", "title": "Test Template"}


def test_gemini_fallback_on_400_schema_error():
    """Assert a 400 schema error triggers exactly one prompt-only retry without schema."""
    client = GeminiLLMClient(api_key="test-api-key", model="gemini-2.5-flash")

    dummy_schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}},
    }

    mock_err_400 = MagicMock()
    mock_err_400.status_code = 400
    mock_err_400.json.return_value = {
        "error": {
            "code": 400,
            "message": 'Unknown name "additionalProperties" at generation_config.response_schema...',
            "status": "INVALID_ARGUMENT",
            "details": [],
        }
    }

    mock_success = _mock_success_response('{"title": "Recovered Without Schema"}')

    with patch("requests.post", side_effect=[mock_err_400, mock_success]) as mock_post:
        result = client.generate_json(
            prompt="Draft a permission letter",
            schema=dummy_schema,
        )

        assert mock_post.call_count == 2

        # 1st call had responseJsonSchema
        first_call_config = mock_post.call_args_list[0][1]["json"]["generationConfig"]
        assert "responseJsonSchema" in first_call_config
        assert first_call_config.get("responseMimeType") == "application/json"

        # 2nd call had NO responseJsonSchema and NO response_schema
        retry_call_config = mock_post.call_args_list[1][1]["json"]["generationConfig"]
        assert "responseJsonSchema" not in retry_call_config
        assert "response_schema" not in retry_call_config
        assert "responseSchema" not in retry_call_config
        assert retry_call_config.get("responseMimeType") == "application/json"

        assert result == {"title": "Recovered Without Schema"}


def test_gemini_fallback_does_not_loop_on_persistent_400():
    """Assert exactly one retry occurs and no infinite loop on persistent error."""
    client = GeminiLLMClient(api_key="test-api-key", model="gemini-2.5-flash")

    mock_err_400 = MagicMock()
    mock_err_400.status_code = 400
    mock_err_400.text = "Bad Request"
    mock_err_400.json.return_value = {
        "error": {
            "code": 400,
            "message": "Persistent schema or syntax error",
        }
    }

    with patch("requests.post", side_effect=[mock_err_400, mock_err_400]) as mock_post:
        with pytest.raises(AIServiceError) as exc_info:
            client.generate_json(
                prompt="Draft a permission letter",
                schema={"type": "object"},
            )

        assert mock_post.call_count == 2
        # Verify user message does not leak raw Google errors
        assert exc_info.value.message == "AI could not draft this template right now. You can build it manually in the editor."


def test_gemini_400_invalid_api_key_raises_auth_error_without_retry():
    """Assert an invalid API key error on 400 raises AIAuthenticationError without retrying."""
    client = GeminiLLMClient(api_key="invalid-key", model="gemini-2.5-flash")

    mock_auth_400 = MagicMock()
    mock_auth_400.status_code = 400
    mock_auth_400.json.return_value = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
            "details": [{"reason": "API_KEY_INVALID"}],
        }
    }

    with patch("requests.post", return_value=mock_auth_400) as mock_post:
        with pytest.raises(AIAuthenticationError):
            client.generate_json(
                prompt="Draft something",
                schema={"type": "object"},
            )

        assert mock_post.call_count == 1


def test_gemini_429_quota_retries_with_fallback_model():
    """Assert a 429 quota error on primary model falls back to alternative model."""
    client = GeminiLLMClient(api_key="test-key", model="gemini-3.8-flash")

    mock_err_429 = MagicMock()
    mock_err_429.status_code = 429
    mock_err_429.text = "Quota exceeded"
    mock_err_429.json.return_value = {
        "error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota)."}
    }

    mock_success = _mock_success_response('{"title": "Fallback Model Response"}')

    with patch("requests.post", side_effect=[mock_err_429, mock_success]) as mock_post:
        result = client.generate_json(
            prompt="Draft template",
            schema={"type": "object"},
        )

        assert mock_post.call_count == 2
        # Second call fell back to next flash candidate
        second_call_url = mock_post.call_args_list[1][0][0]
        assert "flash" in second_call_url and "gemini-3.8-flash" not in second_call_url
        assert result == {"title": "Fallback Model Response"}


def test_gemini_404_triggers_fallback_to_next_model():
    """Assert a 404 on current model invalidates cache and retries with next model."""
    from docgen.llm import clear_model_cache
    clear_model_cache()

    client = GeminiLLMClient(api_key="test-key", model="gemini-deprecated-model")

    mock_err_404 = MagicMock()
    mock_err_404.status_code = 404
    mock_err_404.json.return_value = {"error": {"message": "Model not found or no longer available"}}

    mock_success = _mock_success_response('{"title": "Recovered On Next Model"}')

    # Mock discovery endpoint to return candidate list
    mock_models_resp = MagicMock()
    mock_models_resp.status_code = 200
    mock_models_resp.json.return_value = {
        "models": [
            {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]},
        ]
    }

    with patch("requests.get", return_value=mock_models_resp):
        with patch("requests.post", side_effect=[mock_err_404, mock_success]) as mock_post:
            result = client.generate_json(
                prompt="Draft template",
                schema={"type": "object"},
            )

            assert mock_post.call_count == 2
            # First call was to deprecated model
            assert "gemini-deprecated-model" in mock_post.call_args_list[0][0][0]
            # Second call was to next candidate model
            assert "gemini-3.6-flash" in mock_post.call_args_list[1][0][0]
            assert result == {"title": "Recovered On Next Model"}


def test_gemini_429_backoff_and_exhaustion():
    """Assert 429 retries with 1s backoff and raises AIQuotaError when exhausted."""
    from docgen.llm import AIQuotaError, clear_model_cache
    clear_model_cache()

    client = GeminiLLMClient(api_key="test-key", model="gemini-3.8-flash")

    mock_err_429 = MagicMock()
    mock_err_429.status_code = 429
    mock_err_429.text = "Quota exhausted"
    mock_err_429.json.return_value = {"error": {"message": "Quota exceeded"}}

    with patch("time.sleep") as mock_sleep:
        with patch("requests.post", return_value=mock_err_429) as mock_post:
            with pytest.raises(AIQuotaError) as exc_info:
                client.generate_json(
                    prompt="Draft template",
                    schema={"type": "object"},
                )

            assert mock_post.call_count >= 2
            assert mock_sleep.call_count >= 1
            mock_sleep.assert_called_with(1)
            assert "quota exceeded or rate limit reached" in exc_info.value.message.lower()


def test_gemini_model_discovery_1hr_cache():
    """Assert discovered models are cached in-memory and not re-fetched within 1 hour."""
    from docgen.llm import clear_model_cache, discover_gemini_models
    clear_model_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
        ]
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # First discovery call
        m1 = discover_gemini_models(api_key="test-key")
        assert mock_get.call_count == 1
        assert "gemini-3.6-flash" in m1

        # Second call within 1 hour should hit cache
        m2 = discover_gemini_models(api_key="test-key")
        assert mock_get.call_count == 1
        assert m1 == m2

        # Forced refresh should make a new network call
        m3 = discover_gemini_models(api_key="test-key", force_refresh=True)
        assert mock_get.call_count == 2
        assert m3 == m1

