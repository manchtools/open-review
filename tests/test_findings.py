"""Tests for the findings seam — the one implemented module in the scaffold.

Per the spec-driven flow, per-acceptance-criteria tests for the pipeline stages are
written *before* each stage is implemented. These cover the shared contract they all
depend on, and prove the test harness is wired.
"""

import pytest

from open_review.findings import LEVEL, Finding, dump, load, worst


def _f(**kw) -> Finding:
    base = dict(file="a.py", line=1, severity="warning", category="bug", message="m", source="t")
    base.update(kw)
    return Finding(**base)


def test_roundtrip(tmp_path):
    findings = [_f(), _f(severity="error", line=2, suggestion="x = 1")]
    path = tmp_path / "findings.json"
    dump(findings, path)
    assert load(path) == findings


def test_level_ordering():
    assert LEVEL["note"] < LEVEL["warning"] < LEVEL["error"]


def test_worst_of_empty_is_negative():
    assert worst([]) == -1


def test_worst_picks_highest_severity():
    assert worst([_f(severity="note"), _f(severity="error"), _f(severity="warning")]) == LEVEL["error"]


def test_invalid_severity_rejected():
    with pytest.raises(ValueError):
        _f(severity="critical")
