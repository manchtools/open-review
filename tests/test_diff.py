"""Diff extraction + base-ref resolution (AC-1, AC-24)."""

from open_review import diff


def test_unified_diff_contains_the_change(git_repo, monkeypatch):
    path, base = git_repo
    monkeypatch.chdir(path)
    d = diff.unified_diff(base)
    assert "a.py" in d and "changed" in d


def test_changed_files_lists_the_file(git_repo, monkeypatch):
    path, base = git_repo
    monkeypatch.chdir(path)
    assert diff.changed_files(base) == ["a.py"]


def test_resolve_base_explicit_wins(monkeypatch):
    monkeypatch.setenv("GITHUB_BASE_REF", "develop")
    assert diff.resolve_base("feature-x") == "feature-x"


def test_resolve_base_from_github_env(monkeypatch):
    monkeypatch.delenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", raising=False)
    monkeypatch.setenv("GITHUB_BASE_REF", "develop")
    assert diff.resolve_base(None) == "origin/develop"


def test_resolve_base_from_gitlab_env(monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.setenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "trunk")
    assert diff.resolve_base(None) == "origin/trunk"


def test_resolve_base_fallback(monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", raising=False)
    assert diff.resolve_base(None) == "origin/main"
