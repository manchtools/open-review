"""Static scan stage (Spec §Static stage; AC-6, AC-7).

Runs bundled semgrep (``--config`` = ``SEMGREP_CONFIG``, default ``auto``) and gitleaks
over the changed files and normalizes their output into ``Finding`` objects. A scanner
absent from PATH — or one whose output can't be parsed — is skipped with a printed
notice, never a silent omission (AC-7).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from .findings import Finding

_SEMGREP_SEVERITY = {"ERROR": "error", "WARNING": "warning", "INFO": "note"}


def _semgrep(files: list[str], repo: str) -> list[Finding]:
    if not shutil.which("semgrep"):
        print("· open-review: semgrep not found — skipping (install it, or use the full image)")
        return []
    if not files:
        return []
    cfg = os.environ.get("SEMGREP_CONFIG", "auto")
    proc = subprocess.run(
        ["semgrep", "--config", cfg, "--json", "--quiet", "--metrics", "off", *files],
        capture_output=True, text=True, cwd=repo,
    )
    try:
        results = json.loads(proc.stdout)["results"]
    except (json.JSONDecodeError, KeyError):
        print(f"· open-review: semgrep produced no parseable output — skipping ({proc.stderr.strip()[:150]})")
        return []
    return [
        Finding(
            file=r["path"],
            line=r["start"]["line"],
            severity=_SEMGREP_SEVERITY.get(r["extra"].get("severity", "WARNING"), "warning"),
            category="bug",
            message=r["extra"].get("message", r["check_id"]),
            source=f"semgrep:{r['check_id'].split('.')[-1]}",
        )
        for r in results
    ]


def _gitleaks(files: list[str], repo: str) -> list[Finding]:
    if not shutil.which("gitleaks"):
        print("· open-review: gitleaks not found — skipping (install it, or use the full image)")
        return []
    changed = set(files)
    fd, report = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        proc = subprocess.run(
            ["gitleaks", "detect", "--no-git", "--source", repo,
             "--report-format", "json", "--report-path", report, "--no-banner"],
            capture_output=True, text=True,
        )
        content = ""
        try:
            with open(report) as f:
                content = f.read().strip()
        except OSError:
            pass
        leaks = json.loads(content) if content else []
    except json.JSONDecodeError:
        print(f"· open-review: gitleaks produced no parseable output — skipping ({proc.stderr.strip()[:150]})")
        return []
    finally:
        try:
            os.unlink(report)
        except OSError:
            pass
    out: list[Finding] = []
    for lk in leaks:
        path = lk.get("File", "")
        if changed and path not in changed:
            continue
        out.append(
            Finding(
                file=path,
                line=lk.get("StartLine", 1),
                severity="error",
                category="security",
                message=f"secret: {lk.get('Description', 'detected')}",
                source="gitleaks",
            )
        )
    return out


def run(files: list[str], repo: str) -> list[Finding]:
    return _semgrep(files, repo) + _gitleaks(files, repo)
