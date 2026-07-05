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

from openai import OpenAIError

from . import router
from .errors import OperationalError
from .findings import LEVEL, Finding

# docref: begin stages
STAGES = ("generate", "evaluate", "judge")
# docref: end stages

_ADJUDICATION_STAGES = ("evaluate", "judge")

_SYSTEM = {
    "evaluate": (
        "You are triaging candidate code-review findings. Drop obvious false positives and "
        "low-value noise; keep anything plausibly real. Fix a clearly-wrong severity. Be "
        "lenient — a later judge makes the final call."
    ),
    "judge": (
        "You are the final judge of candidate code-review findings. Keep only findings that "
        "are real, actionable, and worth a reviewer's attention; drop the rest with a brief "
        "reason. Correct any wrong severity."
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


def _catalog(active: list[Finding]) -> str:
    return "\n".join(f"{i}: [{f.severity}] {f.file}:{f.line} {f.message}" for i, f in enumerate(active))


def adjudicate(stage: str, model: str, findings: list[Finding]) -> list[Finding]:
    """Keep/drop/re-grade the active findings; dropped ones are retained + tagged (AC-15).

    The stage sees only the candidate findings, never the diff (AC-13)."""
    active = [f for f in findings if not f.dropped_by]
    if not active:
        return findings
    user = "Candidate findings (id: [severity] file:line message):\n" + _catalog(active)
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


def apply(findings: list[Finding]) -> list[Finding]:
    """Run the evaluate then judge adjudication stages if their models are configured."""
    models = stage_models()
    for stage in _ADJUDICATION_STAGES:
        model = models.get(stage)
        if model and any(not f.dropped_by for f in findings):
            findings = adjudicate(stage, model, findings)
    return findings
