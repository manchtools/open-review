"""Codemap: complete deterministic structural map + read/commit (AC-16, AC-16b, AC-17..AC-19)."""

import os
import subprocess

from open_review import ai, cli, codemap


def _git(tmp, *a):
    subprocess.run(["git", *a], cwd=tmp, check=True, capture_output=True)


def _init_repo(tmp):
    _git(tmp, "init", "-q")
    _git(tmp, "config", "user.email", "t@example.com")
    _git(tmp, "config", "user.name", "t")
    (tmp / "a.py").write_text("def foo():\n    pass\n")
    _git(tmp, "add", ".")
    _git(tmp, "commit", "-qm", "base")


def test_codemap_is_complete(tmp_path, monkeypatch):
    """AC-16b: every symbol ast-grep finds appears in the map (matches-zero guarded)."""
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n\nclass Baz:\n    def m(self):\n        pass\n")
    (tmp_path / "b.js").write_text("function bar() {}\n")
    monkeypatch.chdir(tmp_path)

    names = {n for lst in codemap._symbols(".").values() for n, _ in lst}
    assert names, "matches-zero guard: the extractor found no symbols"
    assert {"foo", "Baz", "m", "bar"} <= names

    doc = codemap.generate(".")
    for name in names:
        assert name in doc, f"codemap omitted symbol {name}"


def test_codemap_lists_every_source_file(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.go").write_text("package main\nfunc doIt() {}\n")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    assert "a.py" in doc
    assert "sub/b.go" in doc.replace(os.sep, "/")


def test_codemap_read_and_folded_into_prompt(tmp_path, monkeypatch):
    """AC-17: a committed codemap is fed to the reviewer as architectural context."""
    d = tmp_path / ".open-review"
    d.mkdir()
    (d / "codemap.md").write_text("# open-review codemap\n## a.py\n- foo (L1)\n")
    monkeypatch.chdir(tmp_path)

    m = codemap.read(".")
    assert m and "foo" in m
    _system, user = ai._prompt("diff", [], m, None)
    assert "Repository architecture" in user and "foo" in user


def test_codemap_commit_has_skip_ci(tmp_path, monkeypatch):
    """AC-18: an opt-in commit carries a CI-skip marker."""
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["codemap", "--commit"]) == 0
    msg = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "[skip ci]" in msg
    assert os.path.exists(os.path.join(tmp_path, ".open-review", "codemap.md"))


def test_codemap_fork_does_not_commit(tmp_path, monkeypatch):
    """AC-19: an untrusted/fork PR generates the map but never commits it."""
    _init_repo(tmp_path)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    monkeypatch.chdir(tmp_path)

    assert cli.main(["codemap", "--commit", "--untrusted"]) == 0
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert before == after
