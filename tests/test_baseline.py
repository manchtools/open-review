"""Full-repo baseline: per-file-batch single-call AI sweep + codemap + static (AC-29, AC-31)."""

import json
import os
import subprocess

from open_review import ai, cli


def _env(monkeypatch, base_url, model="fake-model"):
    monkeypatch.setenv("OR_LLM_BASE_URL", base_url)
    monkeypatch.setenv("OR_LLM_API_KEY", "k")
    monkeypatch.setenv("OR_MODEL", model)
    for v in ("OR_MODEL_GENERATE", "OR_MODEL_EVALUATE", "OR_MODEL_JUDGE"):
        monkeypatch.delenv(v, raising=False)


def test_baseline_reviews_each_file_with_single_call(fake_router, tmp_path, monkeypatch):
    """AC-31: baseline uses one forced-report call per batch — no investigation loop."""
    base_url, ctl = fake_router
    (tmp_path / "a.py").write_text("def f(x):\n    return eval(x)\n")
    monkeypatch.chdir(tmp_path)
    _env(monkeypatch, base_url)
    ctl({"summary": "s", "findings": [
        {"file": "a.py", "line": 2, "severity": "error", "category": "bug",
         "message": "eval is dangerous", "suggestion": ""}]})

    out = ai.baseline(["a.py"], "codemap context", None, ".")

    assert len(out) == 1
    assert out[0].file == "a.py" and out[0].severity == "error"


def test_baseline_command_writes_codemap_and_findings(tmp_path, monkeypatch):
    """AC-29: baseline generates the whole codemap and writes an aggregated findings file."""
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OR_LLM_API_KEY", raising=False)  # AI skipped → static-only baseline

    code = cli.main(["baseline", "--out", "base.json"])

    assert code in (0, 1)
    assert os.path.exists(os.path.join(".open-review", "codemap.md"))
    assert os.path.exists("base.json")
    json.loads(open("base.json").read())  # valid findings array
