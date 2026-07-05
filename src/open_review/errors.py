"""Error types that map to process exit codes (Spec §Rejection paths)."""

from __future__ import annotations


class OperationalError(Exception):
    """open-review itself could not run — bad config, unresolved base ref, a
    required router URL missing. Maps to exit code 2, distinct from findings
    (which use exit 0/1)."""
