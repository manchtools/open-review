"""Static scan stage (Spec §Static stage; AC-6, AC-7).

Runs fully self-contained, **local** static tools — no network, no telemetry, no
third-party service:
  - ruff       — Python lint / bug rules
  - shellcheck — shell scripts
  - gitleaks   — secrets (any language)
  - ast-grep   — polyglot structural rules from a vendored, extensible ruleset
Each normalizes to ``Finding`` objects. A tool absent from PATH — or one whose output
can't be parsed — is skipped with a printed notice, never a silent omission (AC-7).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

from .findings import Finding

_RULES_DIR = os.path.join(os.path.dirname(__file__), "rules")
_SHELLCHECK_SEVERITY = {"error": "error", "warning": "warning", "info": "note", "style": "note"}
_ASTGREP_SEVERITY = {"error": "error", "warning": "warning", "info": "note", "hint": "note"}


def _rel(path: str, root: str) -> str:
    """Normalize a tool-reported path (absolute or already-relative) to repo-relative."""
    return os.path.relpath(path, root) if os.path.isabs(path) else path


def _ruff(files: list[str], repo: str) -> list[Finding]:
    if not shutil.which("ruff"):
        print("· open-review: ruff not found — skipping (install it, or use the full image)")
        return []
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return []
    proc = subprocess.run(
        ["ruff", "check", "--output-format", "json", "--", *py],
        cwd=repo, capture_output=True, text=True,
    )
    try:
        items = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        print(f"· open-review: ruff produced no parseable output — skipping ({proc.stderr.strip()[:150]})")
        return []
    root = os.path.realpath(repo)
    return [
        Finding(
            file=_rel(it["filename"], root),
            line=(it.get("location") or {}).get("row", 1),
            severity="warning",
            category="lint",
            message=f'{it["code"]}: {it["message"]}',
            source=f'ruff:{it["code"]}',
        )
        for it in items
    ]


def _shellcheck(files: list[str], repo: str) -> list[Finding]:
    if not shutil.which("shellcheck"):
        print("· open-review: shellcheck not found — skipping (install it, or use the full image)")
        return []
    sh = [f for f in files if f.endswith((".sh", ".bash"))]
    if not sh:
        return []
    proc = subprocess.run(
        ["shellcheck", "-f", "json", "--", *sh], cwd=repo, capture_output=True, text=True
    )
    try:
        items = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        print(f"· open-review: shellcheck produced no parseable output — skipping ({proc.stderr.strip()[:150]})")
        return []
    root = os.path.realpath(repo)
    return [
        Finding(
            file=_rel(it["file"], root),
            line=it.get("line", 1),
            severity=_SHELLCHECK_SEVERITY.get(it.get("level", "warning"), "warning"),
            category="lint",
            message=f'SC{it["code"]}: {it["message"]}',
            source=f'shellcheck:SC{it["code"]}',
        )
        for it in items
    ]


def _astgrep_rules(files: list[str], repo: str) -> list[Finding]:
    if not files:
        return []
    if not shutil.which("ast-grep"):
        print("· open-review: ast-grep not found — skipping structural rules")
        return []
    if not os.path.isdir(_RULES_DIR):
        return []
    root = os.path.realpath(repo)
    targets = [os.path.join(root, f) for f in files]
    out: list[Finding] = []
    for rule in sorted(glob.glob(os.path.join(_RULES_DIR, "*.yml"))):
        proc = subprocess.run(
            ["ast-grep", "scan", "--rule", rule, "--json", *targets],
            cwd=repo, capture_output=True, text=True,
        )
        try:
            items = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            continue
        for it in items:
            if not it.get("file"):
                continue  # guard: os.path.relpath('', root) raises ValueError
            out.append(
                Finding(
                    file=os.path.relpath(it["file"], root),
                    line=it.get("range", {}).get("start", {}).get("line", 0) + 1,
                    severity=_ASTGREP_SEVERITY.get(it.get("severity", "warning"), "warning"),
                    category="bug",
                    message=it.get("message", it.get("ruleId", "")),
                    source=f'ast-grep:{it.get("ruleId", "rule")}',
                )
            )
    return out


def _gitleaks(files: list[str], repo: str) -> list[Finding]:
    if not files:
        return []  # nothing changed to scan — match _ruff/_shellcheck (don't scan the whole repo)
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
        if not isinstance(leaks, list):  # gitleaks should emit an array; guard other shapes
            leaks = []
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
    findings = _ruff(files, repo) + _shellcheck(files, repo) + _astgrep_rules(files, repo) + _gitleaks(files, repo)
    print(f"· static: {len(findings)} finding(s) from {len(files)} changed file(s)", file=sys.stderr)
    return findings
