"""Multi-model cascade (Spec §Cascade; AC-13, AC-14, AC-15).

generate (cheap, recall) → evaluate (cull obvious junk) → judge (adjudicate the few
survivors). Per-stage models come from ``MODEL_GENERATE`` / ``MODEL_EVALUATE`` /
``MODEL_JUDGE`` (``MODEL`` aliases generate); an unset stage is skipped so the cascade
collapses gracefully (AC-14). The evaluate/judge stages see ONLY the candidate findings,
never the full diff — that's what keeps the big models cheap (AC-13). A dropped finding is
retained and tagged with the stage and reason rather than removed (AC-15).
"""

from __future__ import annotations

import os
import sys

from openai import OpenAIError

from . import router
from .errors import OperationalError
from .findings import LEVEL, Finding

# docref: begin stages
STAGES = ("generate", "evaluate", "judge")
# docref: end stages

_ADJUDICATION_STAGES = ("evaluate", "judge")

# Every finding is shown WITH the code at its location (cited line marked `>>`). This is the
# core anti-false-positive guard: the model must verify each claim against the real code, not
# reason about the finding text alone (the failure mode where a plausible-sounding but wrong
# finding survives because nobody checked it against the source).
_VERIFY = (
    " The relevant code is shown under each finding, with the cited line marked `>>`. Verify "
    "every finding against that code and DROP it when the code contradicts it or does not "
    "contain what it cites — it references a docstring, name, call, or behavior that is not "
    "actually present; miscounts occurrences (e.g. claims something happens twice when the code "
    "shows once); or only assumes how a library/framework behaves without the shown code "
    "exhibiting the bug. If the code at the location is missing entirely, drop it. Keep only "
    "findings the shown code genuinely supports."
)
_SYSTEM = {
    "evaluate": (
        "You are triaging candidate code-review findings. Drop obvious false positives and "
        "low-value noise; keep anything plausibly real. Fix a clearly-wrong severity. Be "
        "lenient — a later judge makes the final call." + _VERIFY
    ),
    "judge": (
        "You are the final judge of candidate code-review findings. Keep only findings that "
        "are real, actionable, and worth a reviewer's attention; drop the rest with a brief "
        "reason. Correct any wrong severity." + _VERIFY
    ),
}

VERDICT_TOOL = {
    "type": "function",
    "function": {
        "name": "verdicts",
        "description": "Keep/drop and re-grade each candidate finding by id.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["verdicts"],
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "keep", "severity", "reason"],
                        "properties": {
                            "id": {"type": "integer"},
                            "keep": {"type": "boolean"},
                            "severity": {"type": "string", "enum": ["note", "warning", "error"]},
                            "reason": {"type": "string"},
                        },
                    },
                }
            },
        },
    },
}


def stage_models() -> dict[str, str | None]:
    """Resolve the per-stage model from env; None means the stage is skipped (AC-14)."""
    return {
        "generate": os.environ.get("MODEL_GENERATE") or os.environ.get("MODEL"),
        "evaluate": os.environ.get("MODEL_EVALUATE"),
        "judge": os.environ.get("MODEL_JUDGE"),
    }


def _code_context(f: Finding, repo: str, ctx: int = 12) -> str:
    """The source lines around a finding (cited line marked `>>`), so the judge can verify it
    against real code. Empty when the file or line doesn't exist — itself a strong drop signal."""
    try:
        with open(os.path.join(repo, f.file), encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    if not (1 <= f.line <= len(lines)):
        return ""
    lo, hi = max(0, f.line - 1 - ctx), min(len(lines), f.line + ctx)
    return "\n".join(f"{'>>' if n == f.line - 1 else '  '}{n + 1}: {lines[n]}" for n in range(lo, hi))


def _catalog(active: list[Finding], repo: str) -> str:
    blocks = []
    for i, f in enumerate(active):
        code = _code_context(f, repo)
        shown = f"\n```\n{code}\n```" if code else "  (no code at this location — unverifiable)"
        blocks.append(f"[{i}] {f.severity} {f.file}:{f.line}\n{f.message}{shown}")
    return "\n\n".join(blocks)


def adjudicate(stage: str, model: str, findings: list[Finding], repo: str = ".") -> list[Finding]:
    """Keep/drop/re-grade the active findings against the real code; dropped ones are retained
    + tagged (AC-15). The stage sees the candidate findings with their code context, never the
    full diff (AC-13)."""
    active = [f for f in findings if not f.dropped_by]
    if not active:
        return findings
    print(f"· cascade: {stage} ({model}) on {len(active)} finding(s)…", file=sys.stderr)
    user = "Candidate findings, each with the code at its location:\n\n" + _catalog(active, repo)
    try:
        data = router.call_tool(model, _SYSTEM[stage], user, VERDICT_TOOL)
    except OperationalError:
        raise
    except OpenAIError as e:
        print(f"· open-review: {stage} stage failed ({e.__class__.__name__}) — keeping findings as-is")
        return findings

    verdicts = {v["id"]: v for v in (data or {}).get("verdicts", []) if isinstance(v.get("id"), int)}
    for i, f in enumerate(active):
        v = verdicts.get(i)
        if not v:
            continue
        if not v.get("keep", True):
            f.dropped_by = stage
            f.drop_reason = v.get("reason", "")
        elif v.get("severity") in LEVEL:
            f.severity = v["severity"]
    return findings


def apply(findings: list[Finding], repo: str = ".") -> list[Finding]:
    """Run the evaluate then judge adjudication stages if their models are configured."""
    models = stage_models()
    for stage in _ADJUDICATION_STAGES:
        model = models.get(stage)
        if model and any(not f.dropped_by for f in findings):
            findings = adjudicate(stage, model, findings, repo)
    return findings
