"""Vetted read-only toolbox: allowlist, scrubbed-env executor, cross-language retrieval,
path confinement (AC-9, AC-10, AC-12)."""

import subprocess

from open_review import toolbox


def test_allowlist_rejects_unknown_action():
    r = toolbox.run_action("rm_rf", {"path": "/"}, ".")
    assert r.lower().startswith("error") and "not an allowed action" in r.lower()


def test_scrubbed_env_excludes_secrets(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp-secret")
    env = toolbox._scrubbed_env()
    assert "LLM_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "PATH" in env  # tools still resolvable


def test_executor_spawns_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-secret")
    (tmp_path / "a.py").write_text("def foo():\n    return 1\nfoo()\n")
    monkeypatch.chdir(tmp_path)
    captured = {}
    real = subprocess.run

    def spy(cmd, **kw):
        captured["env"] = kw.get("env")
        return real(cmd, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    toolbox.run_action("find_callers", {"symbol": "foo"}, ".")  # spawns ast-grep
    assert captured.get("env") is not None
    assert "LLM_API_KEY" not in captured["env"]


def test_find_callers_cross_language(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("def foo():\n    return 1\nfoo()\n")
    (tmp_path / "b.js").write_text("function foo() {}\nfoo();\n")
    monkeypatch.chdir(tmp_path)
    out = toolbox.run_action("find_callers", {"symbol": "foo"}, ".")
    assert "a.py" in out and "b.js" in out


def test_find_callers_rejects_bad_symbol(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = toolbox.run_action("find_callers", {"symbol": "foo(); rm -rf /"}, ".")
    assert out.lower().startswith("error")


def test_read_range_confined_to_repo(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    monkeypatch.chdir(tmp_path)
    ok = toolbox.run_action("read_range", {"file": "a.py", "start": 1, "end": 2}, ".")
    assert "line1" in ok and "line2" in ok
    escaped = toolbox.run_action("read_range", {"file": "../../../etc/passwd", "start": 1, "end": 1}, ".")
    assert escaped.lower().startswith("error")
