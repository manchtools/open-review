"""Multi-model cascade: collapse, evaluate/judge adjudication, dropped-retention (AC-13, AC-14, AC-15)."""

from open_review import ai, cascade
from open_review.findings import Finding


def _f(msg, line, sev="warning"):
    return Finding(file="a.py", line=line, severity=sev, category="bug", message=msg, source="ai:g")


def test_cascade_collapses_without_stage_models(monkeypatch):
    """AC-14: with no evaluate/judge model set, findings pass through untouched."""
    for v in ("MODEL_EVALUATE", "MODEL_JUDGE"):
        monkeypatch.delenv(v, raising=False)
    findings = [_f("keep", 1)]
    out = cascade.apply(findings)
    assert out == findings and not out[0].dropped_by


def test_cascade_adjudicator_sees_the_code(tmp_path, monkeypatch):
    """Anti-false-positive: the judge receives the real code at each finding's location, and a
    finding pointing at a nonexistent location is flagged unverifiable."""
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n")
    monkeypatch.chdir(tmp_path)

    cat = cascade._catalog([_f("check bar", 4)], ".")
    assert ">>4: def bar():" in cat  # cited line shown and marked
    assert "def foo():" in cat  # surrounding context included so claims can be verified

    ghost = cascade._catalog([_f("points nowhere", 999)], ".")
    assert "unverifiable" in ghost  # location out of range → strong drop signal


def test_cascade_evaluate_drops_and_retains(fake_router, tmp_path, monkeypatch):
    """AC-13/AC-15: evaluate adjudicates the candidates; a dropped finding is kept + tagged."""
    base_url, ctl = fake_router
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("MODEL", "gen")
    monkeypatch.setenv("MODEL_EVALUATE", "eval")
    monkeypatch.delenv("MODEL_JUDGE", raising=False)
    monkeypatch.delenv("MODEL_GENERATE", raising=False)
    ctl.script(
        ("report", {"summary": "s", "findings": [
            {"file": "a.py", "line": 1, "severity": "warning", "category": "bug",
             "message": "keep me", "suggestion": ""},
            {"file": "a.py", "line": 2, "severity": "warning", "category": "bug",
             "message": "drop me", "suggestion": ""}]}),
        ("tool", "verdicts", {"verdicts": [
            {"id": 0, "keep": True, "severity": "warning", "reason": "real"},
            {"id": 1, "keep": False, "severity": "warning", "reason": "false positive"}]}),
    )

    out = ai.run("diff", [], None, None, ".")

    assert len(out) == 2  # both retained (AC-15)
    active = [f for f in out if not f.dropped_by]
    dropped = [f for f in out if f.dropped_by]
    assert len(active) == 1 and active[0].message == "keep me"
    assert len(dropped) == 1
    assert dropped[0].dropped_by == "evaluate" and "false positive" in dropped[0].drop_reason
