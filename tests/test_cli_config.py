"""Environment-driven config: OR_* sets flag defaults; CLI overrides env (AC-CFG1)."""

from open_review import cli


def test_env_sets_flag_defaults(monkeypatch):
    monkeypatch.setenv("OR_FAIL_ON", "error")
    monkeypatch.setenv("OR_DESCRIBE", "true")
    monkeypatch.setenv("OR_LIGHT", "1")
    monkeypatch.setenv("OR_SARIF", "/tmp/x.sarif")

    args = cli.build_parser().parse_args(["baseline"])
    assert args.fail_on == "error"        # env drives the default
    assert args.describe is True          # env bool
    assert args.light is True
    assert args.sarif == "/tmp/x.sarif"   # env value


def test_cli_flag_overrides_env(monkeypatch):
    monkeypatch.setenv("OR_FAIL_ON", "error")
    monkeypatch.setenv("OR_DESCRIBE", "true")

    args = cli.build_parser().parse_args(["baseline", "--fail-on", "warning", "--no-describe"])
    assert args.fail_on == "warning"      # explicit flag beats env
    assert args.describe is False


def test_invalid_env_choice_falls_back(monkeypatch):
    monkeypatch.setenv("OR_FAIL_ON", "banana")  # not a valid level
    args = cli.build_parser().parse_args(["report"])
    assert args.fail_on == "warning"      # invalid env value → safe default, no crash


def test_unset_env_uses_builtin_default(monkeypatch):
    for v in ("OR_FAIL_ON", "OR_DESCRIBE", "OR_SARIF"):
        monkeypatch.delenv(v, raising=False)
    args = cli.build_parser().parse_args(["baseline"])
    assert args.fail_on == "warning" and args.describe is False and args.sarif is None
