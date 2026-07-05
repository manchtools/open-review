"""open-review CLI entrypoint (Spec §Technical design).

P0 implements `run` (diff → AI review → report) and `report` (render findings.json
inputs + gate). The `static`, `ai`, and `codemap` subcommands are wired in their
respective phases; their argument surface is defined now so `--help` reflects the
design.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import ai, codemap, config, diff, instructions, report, static
from .errors import OperationalError
from .findings import dump, load

_FAIL_ON = ("note", "warning", "error", "off")
_BOOL = argparse.BooleanOptionalAction

# Behaviour is environment-driven: every flag defaults from an `OPEN_REVIEW_*` variable, so an
# org/repo setting changes all reviewers without editing a CI job. Precedence: CLI flag → env → default.


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _envbool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() not in ("0", "false", "no", "off", "")


def _env_choice(name: str, choices: tuple[str, ...], default: str) -> str:
    v = os.environ.get(name)
    return v if v in choices else default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="open-review", description="AI code reviewer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="full pipeline: review the diff + report [AC-1..AC-5]")
    p_run.add_argument("--base", default=_env("OPEN_REVIEW_BASE"), help="base ref (default: CI env, then origin/main)")
    p_run.add_argument("--fail-on", choices=_FAIL_ON, default=_env_choice("OPEN_REVIEW_FAIL_ON", _FAIL_ON, "warning"))
    p_run.add_argument("--untrusted", action=_BOOL, default=_envbool("OPEN_REVIEW_UNTRUSTED"),
                       help="fork/untrusted PR: read repo config from the base branch")
    p_run.add_argument("--sarif", default=_env("OPEN_REVIEW_SARIF"), help="also write a SARIF 2.1.0 report to this path")
    p_run.add_argument("--gitlab-report", default=_env("OPEN_REVIEW_GITLAB_REPORT"), help="also write a GitLab Code Quality report")

    p_static = sub.add_parser("static", help="static scan only → findings.json [P1]")
    p_static.add_argument("--base", default=_env("OPEN_REVIEW_BASE"))
    p_static.add_argument("--out", default="findings.json")

    p_ai = sub.add_parser("ai", help="AI investigation [P2]")
    p_ai.add_argument("--base", default=_env("OPEN_REVIEW_BASE"))
    p_ai.add_argument("--static", help="static findings.json to fold in as signal")
    p_ai.add_argument("--out", default="ai.json")

    p_report = sub.add_parser("report", help="render findings + gate exit code [AC-4,5,20-23]")
    p_report.add_argument("paths", nargs="*", help="findings.json inputs")
    p_report.add_argument("--fail-on", choices=_FAIL_ON, default=_env_choice("OPEN_REVIEW_FAIL_ON", _FAIL_ON, "warning"))
    p_report.add_argument("--sarif", default=_env("OPEN_REVIEW_SARIF"), help="also write a SARIF 2.1.0 report to this path")
    p_report.add_argument("--gitlab-report", default=_env("OPEN_REVIEW_GITLAB_REPORT"), help="also write a GitLab Code Quality report")

    p_codemap = sub.add_parser("codemap", help="generate the committed codemap [P3]")
    p_codemap.add_argument("--commit", action=_BOOL, default=_envbool("OPEN_REVIEW_COMMIT"), help="commit the map [skip ci]")
    p_codemap.add_argument("--untrusted", action=_BOOL, default=_envbool("OPEN_REVIEW_UNTRUSTED"), help="fork PR: generate but never commit")
    p_codemap.add_argument("--describe", action=_BOOL, default=_envbool("OPEN_REVIEW_DESCRIBE"),
                           help="AI one-liners for undocumented symbols (iterate-cached)")
    p_codemap.add_argument("--light", action=_BOOL, default=_envbool("OPEN_REVIEW_LIGHT"),
                           help="compact structural-only map for small context windows")

    p_baseline = sub.add_parser("baseline", help="full-repo baseline sweep over tracked files [P6]")
    p_baseline.add_argument("--out", default=_env("OPEN_REVIEW_OUT", "findings.json"))
    p_baseline.add_argument("--fail-on", choices=_FAIL_ON, default=_env_choice("OPEN_REVIEW_FAIL_ON", _FAIL_ON, "warning"))
    p_baseline.add_argument("--sarif", default=_env("OPEN_REVIEW_SARIF"))
    p_baseline.add_argument("--gitlab-report", default=_env("OPEN_REVIEW_GITLAB_REPORT"))
    p_baseline.add_argument("--describe", action=_BOOL, default=_envbool("OPEN_REVIEW_DESCRIBE"), help="AI-describe undocumented symbols")
    p_baseline.add_argument("--light", action=_BOOL, default=_envbool("OPEN_REVIEW_LIGHT"), help="compact structural-only codemap")
    return parser


def _run(args: argparse.Namespace) -> int:
    base = diff.resolve_base(args.base)
    files = diff.changed_files(base)
    static_findings = static.run(files, ".")
    instr = instructions.load(base, untrusted=args.untrusted)
    ai_findings = ai.run(diff.unified_diff(base), static_findings, codemap.read("."), instr, ".")
    return report.report(
        static_findings + ai_findings, fail_on=args.fail_on,
        sarif=args.sarif, gitlab_report=args.gitlab_report,
    )


def _normalize_or_env() -> None:
    """Accept org-style `OR_`-prefixed variables directly: for each `OR_X` in the environment,
    populate `X` if it isn't already set. So CI can forward the org's `OR_*` variables verbatim
    (no per-variable `LLM_BASE_URL=${{ vars.OR_LLM_BASE_URL }}` mapping), and an explicit bare `X`
    still wins over the prefixed one."""
    for k, v in list(os.environ.items()):
        if k.startswith("OR_") and len(k) > 3:
            os.environ.setdefault(k[3:], v)


def main(argv: list[str] | None = None) -> int:
    _normalize_or_env()  # before build_parser: flag defaults read OPEN_REVIEW_* / OR_OPEN_REVIEW_*
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "static":
            base = diff.resolve_base(args.base)
            findings = static.run(diff.changed_files(base), ".")
            dump(findings, args.out)
            print(f"· open-review: {len(findings)} static finding(s) → {args.out}")
            return 0
        if args.command == "codemap":
            codemap.write(".", codemap.generate(".", describe=args.describe, light=args.light))
            print(f"· open-review: codemap written to {codemap.CODEMAP_PATH}")
            if args.untrusted:
                print("· open-review: fork/untrusted PR — codemap not committed")
            elif args.commit:
                codemap.commit(".")
                print("· open-review: codemap committed [skip ci]")
            return 0
        if args.command == "baseline":
            files = [
                f for f in codemap.source_files(".")
                if not config.is_excluded(f, config.excludes("."))
            ]
            cmap = codemap.generate(".", describe=args.describe, light=args.light)
            codemap.write(".", cmap)
            static_findings = static.run(files, ".")
            instr = instructions.load("HEAD", untrusted=False)
            ai_findings = ai.baseline(files, cmap, instr, ".")
            findings = static_findings + ai_findings
            dump(findings, args.out)
            print(f"· open-review: baseline → {len(findings)} finding(s) in {args.out}; "
                  f"codemap in {codemap.CODEMAP_PATH}")
            return report.report(
                findings, fail_on=args.fail_on, sarif=args.sarif, gitlab_report=args.gitlab_report
            )
        if args.command == "report":
            findings = [f for path in args.paths for f in load(path)]
            return report.report(
                findings, fail_on=args.fail_on, sarif=args.sarif, gitlab_report=args.gitlab_report
            )
        raise NotImplementedError(
            f"'{args.command}' is not yet implemented — see docs/specs/01-open-review.md."
        )
    except OperationalError as e:
        print(f"open-review: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # any crash is an operational failure (exit 2), not a finding (exit 1)
        print(f"open-review: unexpected error: {e.__class__.__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
