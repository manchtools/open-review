"""Repo-level instructions: load (present/absent/base-for-untrusted) + injection (AC-27, AC-28)."""

import subprocess

from open_review import ai, instructions


def _repo_with_instructions(tmp_path, base_text, head_text):
    def g(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    d = tmp_path / ".open-review"
    d.mkdir()
    (d / "instructions.md").write_text(base_text)
    g("add", ".")
    g("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    (d / "instructions.md").write_text(head_text)
    g("add", ".")
    g("commit", "-qm", "head")
    return base


def test_absent_is_none(git_repo, monkeypatch):
    path, base = git_repo
    monkeypatch.chdir(path)
    assert instructions.load(base) is None


def test_load_working_tree(tmp_path, monkeypatch):
    base = _repo_with_instructions(tmp_path, "BASE rules", "HEAD rules")
    monkeypatch.chdir(tmp_path)
    assert instructions.load(base, untrusted=False).strip() == "HEAD rules"


def test_untrusted_uses_base_version(tmp_path, monkeypatch):
    base = _repo_with_instructions(tmp_path, "BASE rules", "HEAD rules")
    monkeypatch.chdir(tmp_path)
    assert instructions.load(base, untrusted=True).strip() == "BASE rules"


def test_untrusted_rejects_hostile_base(tmp_path, monkeypatch):
    """A base ref that isn't a plain ref can't be coerced into a git option / other revision."""
    monkeypatch.chdir(tmp_path)
    assert instructions.load("--upload-pack=evil", untrusted=True) is None
    assert instructions.load("bad ref with spaces", untrusted=True) is None
    assert instructions.load("", untrusted=True) is None


def test_system_injects_instructions():
    s = ai._system("be strict about money handling")
    assert "be strict about money handling" in s
    assert "repository_review_instructions" in s


def test_system_none_is_base_prompt():
    assert ai._system(None) == ai.SYSTEM
