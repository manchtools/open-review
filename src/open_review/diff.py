"""Diff extraction + base-ref resolution (Spec §Technical design; AC-1, AC-24)."""

from __future__ import annotations

import os
import subprocess

from .errors import OperationalError


def resolve_base(explicit: str | None) -> str:
    """--base, else the CI target branch (as a remote-tracking ref), else origin/main."""
    if explicit:
        return explicit
    for var in ("GITHUB_BASE_REF", "CI_MERGE_REQUEST_TARGET_BRANCH_NAME"):
        val = os.environ.get(var)
        if val:
            return f"origin/{val}"
    return "origin/main"


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise OperationalError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def unified_diff(base: str) -> str:
    """Changes introduced on HEAD since its merge-base with `base` (PR-style diff)."""
    return _git("diff", f"{base}...HEAD")


def changed_files(base: str) -> list[str]:
    return [line for line in _git("diff", "--name-only", f"{base}...HEAD").splitlines() if line]
