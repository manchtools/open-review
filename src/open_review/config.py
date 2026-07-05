"""Optional baseline exclude patterns (Spec §Baseline; AC-30).

The baseline candidate set is the **git-tracked** source files — so `.gitignore` already
governs what's included, and everything committed is a candidate (commit `node_modules` and
that's on you). This optional `.open-review/config.toml` (`exclude = [glob, ...]`) filters
out *additional* tracked paths (e.g. committed-but-generated code). stdlib only.
"""

from __future__ import annotations

import fnmatch
import os
import tomllib

CONFIG_PATH = os.path.join(".open-review", "config.toml")


def excludes(repo: str) -> list[str]:
    path = os.path.join(repo, CONFIG_PATH)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    return [p for p in data.get("exclude", []) if isinstance(p, str)]


def is_excluded(relpath: str, user_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(relpath, pat) for pat in user_patterns)
