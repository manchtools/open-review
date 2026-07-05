"""Environment-driven config: OPEN_REVIEW_* sets flag defaults; CLI overrides env (AC-CFG1)."""

from open_review import cli


def test_env_sets_flag_defaults(monkeypatch):
    monkeypatch.setenv("OPEN_REVIEW_FAIL_ON", "error")
    monkeypatch.setenv("OPEN_REVIEW_DESCRIBE", "true")
    monkeypatch.setenv("OPEN_REVIEW_LIGHT", "1")
    monkeypatch.setenv("OPEN_REVIEW_SARIF", "/tmp/x.sarif")

    args = cli.build_parser().parse_args(["baseline"])
    assert args.fail_on == "error"        # env drives the default
    assert args.describe is True          # env bool
    assert args.light is True
    assert args.sarif == "/tmp/x.sarif"   # env value


def test_cli_flag_overrides_env(monkeypatch):
    monkeypatch.setenv("OPEN_REVIEW_FAIL_ON", "error")
    monkeypatch.setenv("OPEN_REVIEW_DESCRIBE", "true")

    args = cli.build_parser().parse_args(["baseline", "--fail-on", "warning", "--no-describe"])
    assert args.fail_on == "warning"      # explicit flag beats env
    assert args.describe is False


def test_invalid_env_choice_falls_back(monkeypatch):
    monkeypatch.setenv("OPEN_REVIEW_FAIL_ON", "banana")  # not a valid level
    args = cli.build_parser().parse_args(["report"])
    assert args.fail_on == "warning"      # invalid env value → safe default, no crash


def test_or_prefix_env_is_normalized(monkeypatch):
    """AC-CFG3: OR_-prefixed org vars are accepted directly (OR_X populates X)."""
    import os
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_GENERATE", raising=False)
    monkeypatch.setenv("OR_LLM_BASE_URL", "https://router")
    monkeypatch.setenv("OR_MODEL_GENERATE", "deepseek/x")
    cli._normalize_or_env()
    assert os.environ["LLM_BASE_URL"] == "https://router"
    assert os.environ["MODEL_GENERATE"] == "deepseek/x"


def test_bare_env_wins_over_or_prefix(monkeypatch):
    import os
    monkeypatch.setenv("LLM_BASE_URL", "bare")
    monkeypatch.setenv("OR_LLM_BASE_URL", "prefixed")
    cli._normalize_or_env()
    assert os.environ["LLM_BASE_URL"] == "bare"  # explicit bare wins (setdefault)


def test_unset_env_uses_builtin_default(monkeypatch):
    for v in ("OPEN_REVIEW_FAIL_ON", "OPEN_REVIEW_DESCRIBE", "OPEN_REVIEW_SARIF"):
        monkeypatch.delenv(v, raising=False)
    args = cli.build_parser().parse_args(["baseline"])
    assert args.fail_on == "warning" and args.describe is False and args.sarif is None
