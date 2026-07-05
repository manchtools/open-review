"""Baseline excludes: git-tracked is the candidate set; optional config filters extra (AC-30)."""

from open_review import config


def test_no_config_excludes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pats = config.excludes(".")
    assert pats == []
    # git (not us) decides node_modules is out — if it's tracked, it's a candidate.
    assert not config.is_excluded("node_modules/x.js", pats)


def test_user_exclude_patterns(tmp_path, monkeypatch):
    d = tmp_path / ".open-review"
    d.mkdir()
    (d / "config.toml").write_text('exclude = ["generated/*.py"]\n')
    monkeypatch.chdir(tmp_path)
    pats = config.excludes(".")
    assert config.is_excluded("generated/api.py", pats)
    assert not config.is_excluded("src/api.py", pats)
