"""CI-agnostic emitters: SARIF, GitLab code-quality, GitHub annotations, plain fallback
(AC-20, AC-21, AC-22, AC-23)."""

import json

from open_review import emitters, report
from open_review.findings import Finding


def _f(sev, file="a.py", line=1):
    return Finding(file=file, line=line, severity=sev, category="bug", message="m", source="ai:x")


def test_sarif_2_1_0_shape():
    doc = emitters.sarif([_f("error", "a.py", 3)])
    assert doc["version"] == "2.1.0"
    r = doc["runs"][0]["results"][0]
    assert r["level"] == "error"
    assert r["locations"][0]["physicalLocation"]["region"]["startLine"] == 3


def test_gitlab_code_quality_shape():
    rep = emitters.gitlab([_f("warning", "a.py", 2)])
    assert rep[0]["severity"] == "minor"
    assert rep[0]["location"]["path"] == "a.py"
    assert rep[0]["location"]["lines"]["begin"] == 2
    assert rep[0]["fingerprint"]


def test_github_annotation_format(capsys):
    emitters.github_annotations([_f("error", "a.py", 1), _f("note", "b.py", 5)])
    out = capsys.readouterr().out
    assert "::error file=a.py,line=1::" in out
    assert "::notice file=b.py,line=5::" in out


def test_github_annotation_escapes_special_chars(capsys):
    """Regression (baseline-found): %, CR, LF in a message must be escaped or the annotation breaks."""
    f = Finding(file="a.py", line=1, severity="warning", category="bug",
                message="hit 100% at line\ntwo", source="ai:x")
    emitters.github_annotations([f])
    out = capsys.readouterr().out
    assert "100%25 at line%0Atwo" in out  # % → %25, newline → %0A
    assert "100% at line\ntwo" not in out  # raw form must not leak through


def test_report_writes_sarif_and_gitlab(tmp_path):
    s = tmp_path / "out.sarif"
    g = tmp_path / "gl.json"
    report.report([_f("warning", "a.py", 1)], sarif=str(s), gitlab_report=str(g))
    assert json.loads(s.read_text())["version"] == "2.1.0"
    assert json.loads(g.read_text())[0]["severity"] == "minor"


def test_report_emits_github_annotations_in_actions(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    report.report([_f("error", "a.py", 1)])
    assert "::error file=a.py,line=1::" in capsys.readouterr().out


def test_report_plain_stdout_without_ci(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    report.report([_f("error", "a.py", 1)])
    out = capsys.readouterr().out
    assert "::error" not in out and "a.py:1" in out  # AC-23: universal fallback
