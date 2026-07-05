"""End-to-end `run`: diff -> router -> findings -> report + gate (AC-1, AC-5); exit 2 on config error."""

import subprocess

from open_review import cli


def test_run_end_to_end_gates_on_warning(git_repo, fake_router, monkeypatch, capsys):
    path, base = git_repo
    base_url, _ = fake_router
    monkeypatch.chdir(path)
    monkeypatch.setenv("OR_LLM_BASE_URL", base_url)
    monkeypatch.setenv("OR_LLM_API_KEY", "k")
    monkeypatch.setenv("OR_MODEL", "fake-model")

    code = cli.main(["run", "--base", base])

    assert "a.py:1" in capsys.readouterr().out
    assert code == 1  # default fake finding is a warning, default --fail-on warning


def test_run_config_error_missing_base_url_exits_2(git_repo, monkeypatch):
    path, base = git_repo
    monkeypatch.chdir(path)
    monkeypatch.setenv("OR_LLM_API_KEY", "k")          # key set...
    monkeypatch.delenv("OR_LLM_BASE_URL", raising=False)  # ...but no router URL
    monkeypatch.setenv("OR_MODEL", "m")

    assert cli.main(["run", "--base", base]) == 2


def test_run_reports_static_findings(tmp_path, monkeypatch, capsys):
    """`run` wires the static stage: a secret in the changed file surfaces even with AI off."""
    def g(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    g("add", ".")
    g("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    (tmp_path / "a.py").write_text('token = "AKIAZ7Q2K9WL3MNP4XYD"\n')
    g("add", ".")
    g("commit", "-qm", "secret")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OR_LLM_API_KEY", raising=False)  # AI skipped → isolates the static path

    code = cli.main(["run", "--base", base])

    out = capsys.readouterr().out
    assert "gitleaks" in out and "a.py:1" in out
    assert code == 1  # a secret is error-severity; default gate is warning
