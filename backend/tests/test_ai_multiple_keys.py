"""Several AI keys: every key is used in order (all Gemini, then all Groq), each falling back to the next."""

from __future__ import annotations

import pytest

from docgen import llm
from docgen.llm import (
    AIAuthenticationError,
    AIQuotaError,
    FallbackLLMClient,
    GeminiLLMClient,
    GroqLLMClient,
    LLMClient,
    api_keys,
)


@pytest.fixture
def clean_keys(monkeypatch):
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
        for i in range(2, 10):
            monkeypatch.delenv(f"{name}_{i}", raising=False)
    monkeypatch.setenv("AI_CACHE_ENABLED", "false")
    monkeypatch.setattr(llm, "_current_llm_client", None)
    return monkeypatch


def _chain(client):
    out = []
    while isinstance(client, FallbackLLMClient):
        out.append(client.primary)
        client = client.secondary
    out.append(client)
    return out


def test_api_keys_reads_lists_and_numbered_extras(clean_keys):
    clean_keys.setenv("GEMINI_API_KEY", "g1, g2\ng3")
    clean_keys.setenv("GEMINI_API_KEY_2", "g4")
    clean_keys.setenv("GEMINI_API_KEY_3", "g2")  # repeat dropped
    clean_keys.setenv("GROQ_API_KEY", '"q1"')
    assert api_keys("GEMINI_API_KEY") == ["g1", "g2", "g3", "g4"]
    assert api_keys("GROQ_API_KEY") == ["q1"]


def test_every_key_is_chained_gemini_first(clean_keys):
    clean_keys.setenv("GEMINI_API_KEY", "g1,g2")
    clean_keys.setenv("GROQ_API_KEY", "q1")
    clean_keys.setenv("GROQ_API_KEY_2", "q2")
    chain = _chain(llm.get_llm_client())
    assert [type(c) for c in chain] == [GeminiLLMClient, GeminiLLMClient, GroqLLMClient, GroqLLMClient]
    assert [c.api_key for c in chain] == ["g1", "g2", "q1", "q2"]


def test_single_keys_keep_old_behaviour(clean_keys):
    clean_keys.setenv("GEMINI_API_KEY", "g1")
    clean_keys.setenv("GROQ_API_KEY", "q1")
    client = llm.get_llm_client()
    assert isinstance(client, FallbackLLMClient) and client.fallback_on_auth_error is False
    clean_keys.setattr(llm, "_current_llm_client", None)
    clean_keys.delenv("GROQ_API_KEY")
    assert isinstance(llm.get_llm_client(), GeminiLLMClient)


class Fake(LLMClient):
    def __init__(self, name, error=None):
        self.name, self.error, self.calls = name, error, 0

    @property
    def model_name(self):
        return self.name

    def generate_json(self, prompt, schema, club_id=None):
        self.calls += 1
        if self.error:
            raise self.error
        return {"by": self.name}

    def draft_text(self, prompt, context, club_id=None):
        return self.generate_json(prompt, {})["by"]


def _build(*clients, auth=True):
    base = clients[-1]
    for c in reversed(clients[:-1]):
        base = FallbackLLMClient(c, base, fallback_on_auth_error=auth)
    return base


def test_rate_limited_keys_move_to_the_next():
    a, b, c = Fake("k1", AIQuotaError()), Fake("k2", AIQuotaError()), Fake("k3")
    client = _build(a, b, c)
    assert client.generate_json("p", {}) == {"by": "k3"}
    assert client.draft_text("p", {}) == "k3"
    assert (a.calls, b.calls, c.calls) == (2, 2, 2)


def test_bad_key_is_skipped_in_a_multi_key_chain_but_reported_if_all_fail():
    bad, good = Fake("k1", AIAuthenticationError()), Fake("k2")
    assert _build(bad, good).generate_json("p", {}) == {"by": "k2"}
    # Every key fails: the first key's error is what the owner sees
    with pytest.raises(AIAuthenticationError):
        _build(Fake("k1", AIAuthenticationError()), Fake("k2", AIQuotaError())).generate_json("p", {})
    # Without the option (one key per provider) a bad key is raised at once
    other = Fake("k2")
    with pytest.raises(AIAuthenticationError):
        _build(Fake("k1", AIAuthenticationError()), other, auth=False).generate_json("p", {})
    assert other.calls == 0
