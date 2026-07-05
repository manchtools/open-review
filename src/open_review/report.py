"""Report edge — stdout + exit-code gate + CI emitters (Spec §Report; AC-4, AC-5, AC-15,
AC-20..AC-23).

stdout + exit code is the universal signal that works on every CI (AC-23); GitHub
annotations, SARIF, and GitLab code-quality (emitters.py) are additive. Dropped findings
render in a separate "discarded" section and are excluded from the gate (AC-15).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import emitters
from .findings import LEVEL, Finding, worst


def report(
    findings: list[Finding],
    fail_on: str = "warning",
    sarif: str | None = None,
    gitlab_report: str | None = None,
) -> int:
    """Print findings, emit CI outputs, and return the process exit code."""
    active = [f for f in findings if not f.dropped_by]
    dropped = [f for f in findings if f.dropped_by]

    for f in sorted(active, key=lambda x: -LEVEL[x.severity]):
        print(f"{f.severity.upper():7} {f.file}:{f.line}  [{f.source}] {f.message}")
    if not active:
        print("· open-review: no findings")

    if dropped:
        print(f"\n--- discarded by cascade ({len(dropped)}) ---")
        for f in dropped:
            reason = f" ({f.drop_reason})" if f.drop_reason else ""
            print(f"  drop[{f.dropped_by}] {f.file}:{f.line}  {f.message}{reason}")

    if os.environ.get("GITHUB_ACTIONS") == "true":
        emitters.github_annotations(active)
    if sarif:
        Path(sarif).write_text(json.dumps(emitters.sarif(active), indent=2))
    if gitlab_report:
        Path(gitlab_report).write_text(json.dumps(emitters.gitlab(active), indent=2))

    if fail_on == "off":
        return 0
    return 1 if worst(active) >= LEVEL[fail_on] else 0
