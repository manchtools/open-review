"""Router config: output-token cap and provider-routing pass-through (caching locality)."""

from open_review import router


def test_max_tokens_default_and_override(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert router._max_tokens() == 8000
    monkeypatch.setenv("LLM_MAX_TOKENS", "4096")
    assert router._max_tokens() == 4096
    monkeypatch.setenv("LLM_MAX_TOKENS", "not-a-number")
    assert router._max_tokens() == 8000  # bad value falls back, never crashes


def test_extra_body_provider_passthrough(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER_FALLBACK", raising=False)
    assert router._extra_body() == {}  # unset → no routing constraint

    # comma-separated list → ordered preference; fallback defaults true (keeps Opus working)
    monkeypatch.setenv("LLM_PROVIDER", "DeepSeek, Together")
    assert router._extra_body() == {
        "provider": {"order": ["DeepSeek", "Together"], "allow_fallbacks": True}
    }

    # LLM_PROVIDER_FALLBACK bool is human-friendly
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK", "false")
    assert router._extra_body()["provider"]["allow_fallbacks"] is False
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK", "yes")
    assert router._extra_body()["provider"]["allow_fallbacks"] is True
