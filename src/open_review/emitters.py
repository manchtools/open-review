"""CI-specific output emitters (Spec §Report; AC-20, AC-21, AC-22).

The neutral findings list is translated to each CI target here; report.py calls these at
the edge so the core stays CI-agnostic. stdout + exit code (report.py) is the universal
fallback (AC-23); every emitter here is additive.
"""

from __future__ import annotations

import hashlib

from .findings import Finding

_GH_LEVEL = {"error": "error", "warning": "warning", "note": "notice"}
_SARIF_LEVEL = {"error": "error", "warning": "warning", "note": "note"}
_GITLAB_SEVERITY = {"error": "major", "warning": "minor", "note": "info"}


def github_annotations(findings: list[Finding]) -> None:
    """Emit GitHub Actions workflow-command annotations (AC-20)."""
    for f in findings:
        msg = f"[{f.source}] {f.message}".replace("\n", " ")
        print(f"::{_GH_LEVEL[f.severity]} file={f.file},line={f.line}::{msg}")


def sarif(findings: list[Finding]) -> dict:
    """A SARIF 2.1.0 document (AC-22)."""
    results = [
        {
            "ruleId": f.source,
            "level": _SARIF_LEVEL[f.severity],
            "message": {"text": f.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file},
                        "region": {"startLine": max(1, f.line)},
                    }
                }
            ],
        }
        for f in findings
    ]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "open-review"}}, "results": results}],
    }


def gitlab(findings: list[Finding]) -> list[dict]:
    """A GitLab Code Quality report (AC-21)."""
    out = []
    for f in findings:
        fingerprint = hashlib.sha256(
            f"{f.file}:{f.line}:{f.source}:{f.message}".encode()
        ).hexdigest()
        out.append(
            {
                "description": f"[{f.source}] {f.message}",
                "severity": _GITLAB_SEVERITY[f.severity],
                "fingerprint": fingerprint,
                "location": {"path": f.file, "lines": {"begin": max(1, f.line)}},
            }
        )
    return out
