"""Static stage — real semgrep + gitleaks subprocesses, normalized to Findings (AC-6, AC-7)."""

import shutil

from open_review import static

EVAL_RULE = """rules:
  - id: no-eval
    languages: [python]
    severity: ERROR
    message: avoid eval
    pattern: eval(...)
"""


def test_semgrep_findings_normalized(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("def f(x):\n    return eval(x)\n")
    (tmp_path / "rule.yaml").write_text(EVAL_RULE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEMGREP_CONFIG", "rule.yaml")  # override the offline noop default

    out = [f for f in static.run(["a.py"], ".") if f.source.startswith("semgrep")]

    assert out, "expected a semgrep finding"
    assert out[0].source == "semgrep:no-eval"
    assert out[0].severity == "error" and out[0].file == "a.py" and "eval" in out[0].message


def test_gitleaks_detects_secret(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text('token = "AKIAZ7Q2K9WL3MNP4XYD"\n')  # AWS access key id shape
    monkeypatch.chdir(tmp_path)

    out = [f for f in static.run(["a.py"], ".") if f.source == "gitleaks"]

    assert out, "expected a gitleaks finding"
    assert out[0].severity == "error" and out[0].category == "security" and out[0].file == "a.py"


def test_missing_tools_skip_with_notice(monkeypatch, capsys):
    monkeypatch.setattr(shutil, "which", lambda name: None)

    assert static.run(["a.py"], ".") == []

    printed = capsys.readouterr().out.lower()
    assert "semgrep" in printed and "gitleaks" in printed and "skip" in printed
