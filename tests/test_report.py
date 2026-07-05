"""Report rendering + exit-code gate (AC-4, AC-5)."""

from open_review import report
from open_review.findings import Finding


def _f(sev, file="a.py", line=1):
    return Finding(file=file, line=line, severity=sev, category="bug", message="m", source="ai:x")


def test_prints_each_finding(capsys):
    report.report([_f("error"), _f("note", line=2)])
    out = capsys.readouterr().out
    assert "ERROR" in out and "a.py:1" in out and "[ai:x]" in out


def test_exit_zero_when_clean():
    assert report.report([]) == 0


def test_exit_one_on_warning_default():
    assert report.report([_f("warning")]) == 1


def test_note_below_default_warning_is_zero():
    assert report.report([_f("note")]) == 0


def test_fail_on_off_forces_zero():
    assert report.report([_f("error")], fail_on="off") == 0


def test_fail_on_error_ignores_warning_but_not_error():
    assert report.report([_f("warning")], fail_on="error") == 0
    assert report.report([_f("error")], fail_on="error") == 1


def test_dropped_findings_shown_separately_and_excluded_from_gate(capsys):
    """AC-15: dropped findings render in a discarded section and don't affect the gate."""
    dropped = _f("error")
    dropped.dropped_by = "judge"
    dropped.drop_reason = "false positive"
    code = report.report([_f("note", line=2), dropped])  # only a note is active
    out = capsys.readouterr().out
    assert "discarded" in out.lower() and "false positive" in out
    assert code == 0  # the dropped error is excluded from the gate
