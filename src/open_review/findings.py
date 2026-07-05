"""The neutral findings seam (Spec §Technical design).

Every pipeline stage emits ``Finding`` objects; the report edge translates them to
stdout / exit codes / GitHub / GitLab / SARIF. Nothing in this module imports a CI
or VCS SDK — that decoupling is the whole point of the seam, and what makes
open-review CI-agnostic.

This module is the one piece of real behavior in the scaffold: it is the shared
contract every other module depends on.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SEVERITIES = ("note", "warning", "error")  # == SARIF levels, ascending
LEVEL = {name: i for i, name in enumerate(SEVERITIES)}


@dataclass
class Finding:
    file: str
    line: int
    severity: str          # one of SEVERITIES
    category: str          # lint | bug | security | style | design
    message: str
    source: str            # "semgrep:<rule>", "gitleaks", "ai:<model>"
    suggestion: str = ""   # optional replacement code
    dropped_by: str = ""   # "" = active; else the cascade stage that dropped it (AC-15)
    drop_reason: str = ""

    def __post_init__(self) -> None:
        if self.severity not in LEVEL:
            raise ValueError(
                f"invalid severity {self.severity!r}; expected one of {SEVERITIES}"
            )


def dump(findings: list[Finding], path: str | Path) -> None:
    """Serialize findings to a JSON array (the inter-stage artifact)."""
    Path(path).write_text(json.dumps([asdict(f) for f in findings], indent=2))


def load(path: str | Path) -> list[Finding]:
    """Load findings from a JSON array produced by :func:`dump`."""
    return [Finding(**item) for item in json.loads(Path(path).read_text())]


def worst(findings: list[Finding]) -> int:
    """Highest severity level present, or -1 for an empty list (used by the gate)."""
    return max((LEVEL[f.severity] for f in findings), default=-1)
