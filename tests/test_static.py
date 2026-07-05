"""Static stage — local, self-contained tools normalized to Findings (AC-6, AC-7).

No network, no telemetry, no service: ruff (Python), shellcheck (shell), gitleaks
(secrets), ast-grep with vendored rules (polyglot structural)."""

import shutil

from open_review import static


def test_ruff_findings_normalized(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("import os\nx = 1\n")  # F401 unused import
    monkeypatch.chdir(tmp_path)
    out = [f for f in static.run(["a.py"], ".") if f.source.startswith("ruff")]
    assert out, "expected a ruff finding"
    assert out[0].file == "a.py" and "F401" in out[0].source


def test_shellcheck_findings_normalized(tmp_path, monkeypatch):
    (tmp_path / "s.sh").write_text("#!/bin/sh\nif [ $x = 1 ]; then echo hi; fi\n")
    monkeypatch.chdir(tmp_path)
    out = [f for f in static.run(["s.sh"], ".") if f.source.startswith("shellcheck")]
    assert out, "expected a shellcheck finding"
    assert out[0].file == "s.sh"


def test_astgrep_vendored_rule_flags_pattern(tmp_path, monkeypatch):
    (tmp_path / "b.py").write_text("def f(x):\n    return eval(x)\n")
    monkeypatch.chdir(tmp_path)
    out = [f for f in static.run(["b.py"], ".") if f.source.startswith("ast-grep")]
    assert out, "expected an ast-grep rule finding"
    assert out[0].file == "b.py" and out[0].line == 2 and "eval" in out[0].source


def test_gitleaks_detects_secret(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text('token = "AKIAZ7Q2K9WL3MNP4XYD"\n')
    monkeypatch.chdir(tmp_path)
    out = [f for f in static.run(["a.py"], ".") if f.source == "gitleaks"]
    assert out, "expected a gitleaks finding"
    assert out[0].severity == "error" and out[0].category == "security" and out[0].file == "a.py"


def test_missing_tools_skip_with_notice(monkeypatch, capsys):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert static.run(["a.py"], ".") == []
    printed = capsys.readouterr().out.lower()
    for tool in ("ruff", "shellcheck", "gitleaks", "ast-grep"):
        assert tool in printed
    assert "skip" in printed
