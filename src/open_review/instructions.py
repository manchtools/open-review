"""Repo-level instructions (Spec §Repo instructions; AC-27, AC-28).

A repo may commit `.open-review/instructions.md` with house rules and domain context
that steer every review. It is injected as system-level guidance (see `ai._system`).
For untrusted/fork PRs the base-branch version is used, so a PR cannot rewrite the
reviewer that judges it. Absent or empty → no guidance (not an error).
"""

from __future__ import annotations

import os
import subprocess

INSTRUCTIONS_PATH = ".open-review/instructions.md"


def load(base: str, untrusted: bool = False) -> str | None:
    """Return the repo instructions, or None if absent/empty.

    Trusted (default): read the working tree. Untrusted (fork PR): read the
    base-branch version via `git show`, so PR-head edits cannot influence the review
    of that same PR.
    """
    if untrusted:
        proc = subprocess.run(
            ["git", "show", f"{base}:{INSTRUCTIONS_PATH}"], capture_output=True, text=True
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return proc.stdout

    if not os.path.exists(INSTRUCTIONS_PATH):
        return None
    with open(INSTRUCTIONS_PATH, encoding="utf-8") as f:
        content = f.read()
    return content if content.strip() else None
