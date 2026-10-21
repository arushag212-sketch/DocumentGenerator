"""Unit tests for deterministic output, response caching, and Groq fallback."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from docgen.llm import (
    AIBadResponseError,
    AIAuthenticationError,
    AIQuotaError,
    AIServiceError,
    AITimeoutError,
    CachedLLMClient,
    DummyLLMClient,
    FallbackLLMClient,
    GeminiLLMClient,
    GroqLLMClient,
    StubLLMClient,
    compute_cache_key,
    get_llm_client,
    set_llm_client,
)
from server.app.core.database import SessionLocal
from server.app.models import AICache, Club


def _mock_gemini_success(text: str = '{"title": "Test Letter", "body": "Content"}'):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 120,
            "candidatesTokenCount": 60,
            "totalTokenCount": 180,
        },
    }
    return resp


def _mock_groq_success(text: str = '{"title": "Groq Output", "body": "Groq Content"}'):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "llama-3.3-70b-versatile",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 110,
            "completion_tokens": 45,
            "total_tokens": 155,
        },
    }
    return resp


# ---------------------------------------------------------------------------
# Part A: Deterministic Output Tests
# ---------------------------------------------------------------------------


def test_gemini_temperature_and_topp_in_generate_json(monkeypatch):
    """Assert GeminiLLMClient sends temperature 0 and topP 1 by default."""
    monkeypatch.setenv("AI_TEMPERATURE", "0")
    client = GeminiLLMClient(api_key="test-key", model="gemini-2.5-flash")

    schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}},
        "required": ["title"],
    }
    mock_resp = _mock_gemini_success('{"title": "Deterministic"}')

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = client.generate_json("Generate letter", schema)
        assert res == {"title": "Deterministic"}
        assert mock_post.call_count == 1
        _, kwargs = mock_post.call_args
        gen_config = kwargs["json"]["generationConfig"]
        assert gen_config["temperature"] == 0.0
        assert gen_config["topP"] == 1.0


def test_gemini_temperature_configurable(monkeypatch):
    """Assert AI_TEMPERATURE env var overrides default temperature."""
    monkeypatch.setenv("AI_TEMPERATURE", "0.7")
    client = GeminiLLMClient(api_key="test-key", model="gemini-2.5-flash")

    schema = {"type": "object", "properties": {"title": {"type": "string"}}}
    mock_resp = _mock_gemini_success('{"title": "Creative"}')

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client.generate_json("Generate letter", schema)
        gen_config = mock_post.call_args[1]["json"]["generationConfig"]
        assert gen_config["temperature"] == 0.7
        assert gen_config["topP"] == 1.0


def test_gemini_draft_text_deterministic(monkeypatch):
    """Assert draft_text sends temperature 0 and topP 1."""
    monkeypatch.setenv("AI_TEMPERATURE", "0")
    client = GeminiLLMClient(api_key="test-key", model="gemini-2.5-flash")

    mock_resp = _mock_gemini_success("Drafted narrative content")
    with patch("requests.post", return_value=mock_resp) as mock_post:
        text = client.draft_text("Draft an invitation", {"club": "ACM"})
        assert text == "Drafted narrative content"
        gen_config = mock_post.call_args[1]["json"]["generationConfig"]
        assert gen_config["temperature"] == 0.0
        assert gen_config["topP"] == 1.0


# ---------------------------------------------------------------------------
# Part C: Groq Client Tests
# ---------------------------------------------------------------------------


def test_groq_json_success():
    """Assert Groq client sends valid OpenAI chat completions format and returns parsed dict."""
    client = GroqLLMClient(api_key="gsk_test123", model="llama-3.3-70b-versatile")
    schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}},
        "required": ["title"],
    }
    mock_resp = _mock_groq_success('{"title": "Groq Title"}')

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = client.generate_json("Prompt for Groq", schema)
        assert res == {"title": "Groq Title"}
        assert mock_post.call_count == 1

        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.groq.com/openai/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer gsk_test123"
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        assert kwargs["json"]["temperature"] == 0.0
        assert client.last_usage_metadata["tokens_in"] == 110


def test_groq_invalid_json_raises_bad_response():
    """Assert Groq response with malformed JSON raises AIBadResponseError."""
    client = GroqLLMClient(api_key="gsk_test123")
    schema = {"type": "object"}
    mock_resp = _mock_groq_success("Not a JSON object")

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(AIBadResponseError):
            client.generate_json("Prompt", schema)


def test_groq_schema_validation_failure_raises_bad_response():
    """Assert Groq response that fails JSON schema validation raises AIBadResponseError."""
    client = GroqLLMClient(api_key="gsk_test123")
    schema = {
        "type": "object",
        "properties": {"count": {"type": "number"}},
        "required": ["count"],
    }
    # Response has string instead of number
    mock_resp = _mock_groq_success('{"count": "not-a-number"}')

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(AIBadResponseError):
            client.generate_json("Prompt", schema)


def test_groq_error_mappings():
    """Assert HTTP 401 -> AuthError, 429 -> QuotaError, Timeout -> TimeoutError."""
    client = GroqLLMClient(api_key="gsk_test123")
    schema = {"type": "object"}

    # 401
    resp_401 = MagicMock(status_code=401, text="Unauthorized")
    with patch("requests.post", return_value=resp_401):
        with pytest.raises(AIAuthenticationError):
            client.generate_json("Prompt", schema)

    # 429
    resp_429 = MagicMock(status_code=429, text="Rate limit reached")
    with patch("requests.post", return_value=resp_429):
        with pytest.raises(AIQuotaError):
            client.generate_json("Prompt", schema)

    # Timeout
    import requests
    with patch("requests.post", side_effect=requests.exceptions.Timeout("timed out")):
        with pytest.raises(AITimeoutError):
            client.generate_json("Prompt", schema)


# ---------------------------------------------------------------------------
# Part C: Fallback LLM Client Tests
# ---------------------------------------------------------------------------


def test_fallback_gemini_429_groq_answers():
    """Assert Gemini 429 quota error causes immediate retry on Groq, returning Groq's answer."""
    gemini = GeminiLLMClient(api_key="gemini-key", model="gemini-2.5-flash")
    groq = GroqLLMClient(api_key="groq-key", model="llama-3.3-70b-versatile")
    client = FallbackLLMClient(primary=gemini, secondary=groq)

    schema = {"type": "object", "properties": {"title": {"type": "string"}}}

    resp_gemini_429 = MagicMock(status_code=429, text="Gemini Quota Exceeded")
    resp_gemini_429.json.return_value = {"error": {"message": "Resource exhausted"}}
    resp_groq_200 = _mock_groq_success('{"title": "Answered by Groq"}')

    def mock_post(url, *args, **kwargs):
        if "generativelanguage" in url:
            return resp_gemini_429
        elif "api.groq.com" in url:
            return resp_groq_200
        raise ValueError(f"Unexpected url: {url}")

    with patch("requests.post", side_effect=mock_post):
        res = client.generate_json("Draft something", schema)
        assert res == {"title": "Answered by Groq"}
        assert client.model_name == "llama-3.3-70b-versatile"


def test_fallback_gemini_invalid_key_no_fallback():
    """Assert invalid Gemini API key (401/403) raises AIAuthenticationError without trying Groq."""
    gemini = GeminiLLMClient(api_key="bad-gemini-key", model="gemini-2.5-flash")
    groq = GroqLLMClient(api_key="groq-key", model="llama-3.3-70b-versatile")
    client = FallbackLLMClient(primary=gemini, secondary=groq)

    schema = {"type": "object"}
    resp_gemini_403 = MagicMock(status_code=403, text="API key not valid")
    mock_groq = MagicMock()

    with patch("requests.post", return_value=resp_gemini_403) as mock_post:
        with patch.object(groq, "generate_json", mock_groq):
            with pytest.raises(AIAuthenticationError):
                client.generate_json("Prompt", schema)
            mock_groq.assert_not_called()


def test_fallback_both_fail_raises_original_gemini_error():
    """Assert if both Gemini and Groq fail, the original Gemini quota error is raised."""
    gemini = GeminiLLMClient(api_key="gemini-key", model="gemini-2.5-flash")
    groq = GroqLLMClient(api_key="groq-key", model="llama-3.3-70b-versatile")
    client = FallbackLLMClient(primary=gemini, secondary=groq)

    schema = {"type": "object"}
    resp_gemini_429 = MagicMock(status_code=429, text="Gemini Quota Exceeded")
    resp_gemini_429.json.return_value = {"error": {"message": "Resource exhausted"}}
    resp_groq_500 = MagicMock(status_code=500, text="Groq Internal Server Error")

    def mock_post(url, *args, **kwargs):
        if "generativelanguage" in url:
            return resp_gemini_429
        elif "api.groq.com" in url:
            return resp_groq_500
        raise ValueError(f"Unexpected url: {url}")

    with patch("requests.post", side_effect=mock_post):
        with pytest.raises(AIQuotaError) as exc_info:
            client.generate_json("Prompt", schema)
        assert "Gemini API quota exceeded" in str(exc_info.value)


def test_only_groq_configuration_works(monkeypatch):
    """Assert when only GROQ_API_KEY is provided, get_llm_client returns an active Groq-backed client."""
    set_llm_client(None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_only_groq")
    monkeypatch.setenv("AI_CACHE_ENABLED", "false")

    client = get_llm_client()
    assert client.is_available() is True
    assert isinstance(client, GroqLLMClient)
    assert client.model_name == "llama-3.3-70b-versatile"


def test_fallback_draft_text():
    """Assert draft_text on FallbackLLMClient also falls back to Groq on 429."""
    gemini = GeminiLLMClient(api_key="gemini-key", model="gemini-2.5-flash")
    groq = GroqLLMClient(api_key="groq-key", model="llama-3.3-70b-versatile")
    client = FallbackLLMClient(primary=gemini, secondary=groq)

    resp_gemini_429 = MagicMock(status_code=429, text="Quota exceeded")
    resp_groq_200 = _mock_groq_success("Groq narrative text")

    def mock_post(url, *args, **kwargs):
        if "generativelanguage" in url:
            return resp_gemini_429
        return resp_groq_200

    with patch("requests.post", side_effect=mock_post):
        res = client.draft_text("Draft prompt", {"club": "ACM"})
        assert res == "Groq narrative text"
        assert client.model_name == "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Part B: Response Caching Tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_test_clubs_and_cleanup_cache():
    """Ensure test clubs exist for FK and clean up ai_cache entries before each test."""
    db = SessionLocal()
    try:
        db.query(AICache).delete()
        for cid, slug in [("club-alpha", "alpha"), ("club-1", "c1"), ("club-2", "c2"), ("test-club", "testc")]:
            if not db.query(Club).filter(Club.id == cid).first():
                db.add(Club(id=cid, name=f"Test {slug}", short_name=slug, slug=slug))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AICache).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_cache_same_request_twice_calls_provider_once():
    """Assert same request twice hits cache, calls provider only once, and increments hits."""
    stub = StubLLMClient(default_json={"result": "generated-value"})
    cached_client = CachedLLMClient(inner=stub, ttl_hours=168, enabled=True)

    schema = {"type": "object", "properties": {"result": {"type": "string"}}}
    prompt = "Unique prompt 1"

    # Call 1: Miss -> provider called
    r1 = cached_client.generate_json(prompt, schema, club_id="club-alpha")
    assert r1 == {"result": "generated-value"}
    assert stub.attempt_count == 1

    # Check DB
    db = SessionLocal()
    entry = db.query(AICache).first()
    assert entry is not None
    assert entry.hits == 0
    assert entry.club_id == "club-alpha"
    db.close()

    # Call 2: Hit -> provider NOT called
    r2 = cached_client.generate_json(prompt, schema, club_id="club-alpha")
    assert r2 == {"result": "generated-value"}
    assert stub.attempt_count == 1  # Still 1!

    # Check DB hits incremented
    db = SessionLocal()
    entry = db.query(AICache).first()
    assert entry.hits == 1
    db.close()


def test_cache_different_club_calls_provider_again():
    """Assert different club_id results in different cache keys and calls provider again."""
    stub = StubLLMClient(default_json={"result": "data"})
    cached_client = CachedLLMClient(inner=stub, ttl_hours=168, enabled=True)
    schema = {"type": "object"}
    prompt = "Shared template prompt"

    cached_client.generate_json(prompt, schema, club_id="club-1")
    assert stub.attempt_count == 1

    # Second club calls provider again
    cached_client.generate_json(prompt, schema, club_id="club-2")
    assert stub.attempt_count == 2

    db = SessionLocal()
    entries = db.query(AICache).all()
    assert len(entries) == 2
    club_ids = {e.club_id for e in entries}
    assert club_ids == {"club-1", "club-2"}
    db.close()


def test_cache_different_prompt_calls_provider_again():
    """Assert different prompt results in cache miss and calls provider again."""
    stub = StubLLMClient(default_json={"result": "data"})
    cached_client = CachedLLMClient(inner=stub, ttl_hours=168, enabled=True)
    schema = {"type": "object"}

    cached_client.generate_json("Prompt A", schema)
    assert stub.attempt_count == 1

    cached_client.generate_json("Prompt B", schema)
    assert stub.attempt_count == 2


def test_cache_expired_entry_lazily_deleted_and_refreshed():
    """Assert expired cache entry is ignored, deleted lazily, and re-fetched from provider."""
    stub = StubLLMClient(default_json={"result": "fresh-data"})
    cached_client = CachedLLMClient(inner=stub, ttl_hours=24, enabled=True)
    schema = {"type": "object"}
    prompt = "Expiring prompt"

    # Pre-populate expired entry (created 48 hours ago)
    db = SessionLocal()
    expired_key = compute_cache_key(
        kind="json",
        model=stub.model_name,
        temperature=stub.temperature,
        prompt=prompt,
        payload_or_context=schema,
        club_id="test-club",
    )
    old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
    expired_entry = AICache(
        key=expired_key,
        club_id="test-club",
        kind="json",
        model=stub.model_name,
        response='{"result": "stale-data"}',
        created_at=old_time,
        hits=5,
    )
    db.add(expired_entry)
    db.commit()
    db.close()

    # Calling client should detect expiration, delete stale entry, and call provider
    res = cached_client.generate_json(prompt, schema, club_id="test-club")
    assert res == {"result": "fresh-data"}
    assert stub.attempt_count == 1

    # Verify entry in DB is now refreshed
    db = SessionLocal()
    entry = db.query(AICache).filter(AICache.key == expired_key).first()
    assert entry is not None
    assert entry.response == '{"result": "fresh-data"}'
    assert entry.hits == 0
    assert (datetime.now(timezone.utc).replace(tzinfo=None) - entry.created_at).total_seconds() < 10
    db.close()


def test_cache_errors_are_never_cached():
    """Assert failures or exceptions from provider are never stored in the cache table."""
    stub = StubLLMClient(simulate_error=AIQuotaError("Quota limit hit"))
    cached_client = CachedLLMClient(inner=stub, ttl_hours=168, enabled=True)
    schema = {"type": "object"}

    with pytest.raises(AIQuotaError):
        cached_client.generate_json("Failing prompt", schema)

    db = SessionLocal()
    assert db.query(AICache).count() == 0
    db.close()

    # Now make it succeed
    stub.simulate_error = None
    stub.default_json = {"result": "recovered"}
    res = cached_client.generate_json("Failing prompt", schema)
    assert res == {"result": "recovered"}

    db = SessionLocal()
    assert db.query(AICache).count() == 1
    db.close()


def test_cache_draft_text_caching():
    """Assert draft_text is also cached properly."""
    stub = StubLLMClient()
    cached_client = CachedLLMClient(inner=stub, ttl_hours=168, enabled=True)

    t1 = cached_client.draft_text("Draft something", {"title": "Workshop"})
    assert t1 == "Stubbed drafted narrative text."
    assert len(stub.call_history) == 1

    t2 = cached_client.draft_text("Draft something", {"title": "Workshop"})
    assert t2 == "Stubbed drafted narrative text."
    assert len(stub.call_history) == 1  # Hit cache!
