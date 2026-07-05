"""AI stage — single-model generate against a fake router (AC-2, AC-3)."""

from open_review import ai
from open_review.findings import Finding


def _env(monkeypatch, base_url, model="fake-model"):
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("MODEL", model)
    for v in ("MODEL_GENERATE", "MODEL_EVALUATE", "MODEL_JUDGE"):
        monkeypatch.delenv(v, raising=False)


def test_ai_run_parses_findings_from_tool_call(fake_router, monkeypatch):
    base_url, set_findings = fake_router
    set_findings({"summary": "s", "findings": [
        {"file": "a.py", "line": 3, "severity": "error",
         "category": "security", "message": "bad", "suggestion": "fix"}]})
    _env(monkeypatch, base_url)

    out = ai.run("some diff", [], None, None, ".")

    assert len(out) == 1
    f = out[0]
    assert isinstance(f, Finding)
    assert (f.file, f.line, f.severity, f.category) == ("a.py", 3, "error", "security")
    assert f.source == "ai:fake-model"


def test_ai_run_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    out = ai.run("some diff", [], None, None, ".")
    assert out == []
    assert "skip" in capsys.readouterr().out.lower()


def test_static_findings_folded_into_prompt():
    """AC-8: static findings are handed to the model as 'already found' signal."""
    sf = [Finding(file="a.py", line=2, severity="warning", category="bug",
                  message="unused variable x", source="semgrep:unused")]
    _system, user = ai._prompt("some diff", sf, None, None)
    assert "Static analysis already found" in user
    assert "unused variable x" in user


def test_loop_investigates_then_reports(fake_router, tmp_path, monkeypatch):
    """AC-11/AC-9: the agent may call toolbox actions before reporting findings."""
    base_url, ctl = fake_router
    (tmp_path / "a.py").write_text("def foo():\n    return 1\nfoo()\n")
    monkeypatch.chdir(tmp_path)
    _env(monkeypatch, base_url)
    ctl.script(
        ("tool", "find_callers", {"symbol": "foo"}),
        ("report", {"summary": "s", "findings": [
            {"file": "a.py", "line": 3, "severity": "warning",
             "category": "bug", "message": "m", "suggestion": ""}]}),
    )
    out = ai.run("diff", [], None, None, ".")
    assert len(out) == 1 and out[0].line == 3


def test_loop_caps_at_max_steps(fake_router, tmp_path, monkeypatch):
    """AC-11: a model that never calls report is bounded by MAX_STEPS."""
    base_url, ctl = fake_router
    (tmp_path / "a.py").write_text("foo()\n")
    monkeypatch.chdir(tmp_path)
    _env(monkeypatch, base_url)
    monkeypatch.setenv("OPEN_REVIEW_MAX_STEPS", "3")
    ctl.script(("tool", "find_callers", {"symbol": "foo"}))  # never reports → repeats
    out = ai.run("diff", [], None, None, ".")
    assert out == []
