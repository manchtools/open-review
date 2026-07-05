"""Router config: output-token cap and provider-routing pass-through (caching locality)."""

from open_review import router


def test_max_tokens_default_and_override(monkeypatch):
    monkeypatch.delenv("OR_LLM_MAX_TOKENS", raising=False)
    assert router._max_tokens() == 8000
    monkeypatch.setenv("OR_LLM_MAX_TOKENS", "4096")
    assert router._max_tokens() == 4096
    monkeypatch.setenv("OR_LLM_MAX_TOKENS", "not-a-number")
    assert router._max_tokens() == 8000  # bad value falls back, never crashes


def test_salvage_recovers_findings_from_truncated_array():
    """A truncated report keeps every complete finding plus the completed pairs of the cut-off one."""
    raw = ('{"summary":"s","findings":['
           '{"file":"a.py","line":1,"message":"one"},'
           '{"file":"b.py","line":2,"message":"two"},'
           '{"file":"c.py","line":3,"message":"trunc')  # third object cut mid-string
    out = router._salvage(raw, "findings")
    got = out["findings"]
    assert {"file": "a.py", "line": 1, "message": "one"} in got
    assert {"file": "b.py", "line": 2, "message": "two"} in got
    assert any(f.get("file") == "c.py" and f.get("line") == 3 and "message" not in f for f in got)


def test_salvage_single_object_missing_closing_brace():
    """One big object whose `}` is truncated still yields its complete key/value pairs."""
    raw = '{"findings":[{"file":"x.py","line":9,"severity":"error","message":"long trunc'
    out = router._salvage(raw, "findings")
    f = out["findings"][0]
    assert f["file"] == "x.py" and f["line"] == 9 and f["severity"] == "error"
    assert "message" not in f  # the cut-off pair is dropped, the rest kept


def test_salvage_complete_array_missing_outer_brace():
    raw = '{"findings":[{"file":"a.py","line":1,"message":"m"}]'  # only the outer } is missing
    assert router._salvage(raw, "findings")["findings"] == [{"file": "a.py", "line": 1, "message": "m"}]


def test_ai_repair_noop_without_model(monkeypatch):
    """The AI-repair fallback is off (returns None) unless a repair-capable model is configured."""
    for v in ("OR_MODEL_REPAIR", "OR_MODEL_DESCRIBE", "OR_MODEL_GENERATE", "OR_MODEL"):
        monkeypatch.delenv(v, raising=False)
    tool = {"function": {"parameters": {"properties": {"findings": {"type": "array"}}}}}
    assert router._ai_repair('{"findings":[{"broken', tool) is None


def test_extra_body_provider_passthrough(monkeypatch):
    monkeypatch.delenv("OR_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OR_LLM_PROVIDER_FALLBACK", raising=False)
    assert router._extra_body() == {}  # unset → no routing constraint

    # comma-separated list → ordered preference; fallback defaults true (keeps Opus working)
    monkeypatch.setenv("OR_LLM_PROVIDER", "DeepSeek, Together")
    assert router._extra_body() == {
        "provider": {"order": ["DeepSeek", "Together"], "allow_fallbacks": True}
    }

    # OR_LLM_PROVIDER_FALLBACK bool is human-friendly
    monkeypatch.setenv("OR_LLM_PROVIDER_FALLBACK", "false")
    assert router._extra_body("deepseek/deepseek-v4-pro")["provider"]["allow_fallbacks"] is False
    monkeypatch.setenv("OR_LLM_PROVIDER_FALLBACK", "yes")
    assert router._extra_body("deepseek/deepseek-v4-pro")["provider"]["allow_fallbacks"] is True


def test_extra_body_skips_anthropic_models(monkeypatch):
    """Model-aware: an Anthropic/Claude model (the judge) is never pinned to a DeepSeek host,
    so a hard pin (fallback=false) is safe — the judge still reaches Anthropic."""
    monkeypatch.setenv("OR_LLM_PROVIDER", "StreamLake")
    monkeypatch.setenv("OR_LLM_PROVIDER_FALLBACK", "false")
    assert router._extra_body("deepseek/deepseek-v4-pro")["provider"]["order"] == ["StreamLake"]
    assert router._extra_body("anthropic/claude-opus-4.8") == {}
    assert router._extra_body("some/claude-model") == {}
