"""OpenAI-compatible router client (Spec §Technical design; AC-2, AC-3).

Wraps the ``openai`` SDK pointed at ``OR_LLM_BASE_URL`` so any router (LiteLLM,
OpenRouter, self-hosted) works unchanged. A forced tool call yields structured
findings/verdicts.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI, OpenAIError

from .errors import OperationalError


def is_configured() -> bool:
    """True iff a router API key is present — else the AI stage is skipped (AC-3)."""
    return bool(os.environ.get("OR_LLM_API_KEY"))


def _max_tokens() -> int:
    """Output-token cap, configurable via `OR_LLM_MAX_TOKENS`. Small/cheap models (e.g. a cheap
    `OR_MODEL_DESCRIBE`) cap below the old hardcoded 8000 and would 400 — this lets them be set."""
    try:
        return int(os.environ.get("OR_LLM_MAX_TOKENS", "8000"))
    except ValueError:
        return 8000


def _extra_body(model: str = "") -> dict:
    """OpenRouter provider routing, from human-friendly env:

      OR_LLM_PROVIDER           comma-separated provider names in preference order, e.g. "StreamLake"
      OR_LLM_PROVIDER_FALLBACK  bool — allow other providers when a preferred one can't serve the model

    The pin is **model-aware**: an Anthropic/Claude model (the judge) is never pinned to a
    DeepSeek-family host (OpenRouter 404s on that), so it routes to its own provider. That is what
    makes a *hard* pin safe — set `OR_LLM_PROVIDER_FALLBACK=false` and every DeepSeek request sticks to
    one provider (cache locality: the codemap prefix hits the *same* provider's cache each time,
    instead of scattering across hosts under concurrency), while the Opus judge still reaches
    Anthropic. Unset OR_LLM_PROVIDER → no routing constraint."""
    order = [p.strip() for p in os.environ.get("OR_LLM_PROVIDER", "").split(",") if p.strip()]
    if not order:
        return {}
    m = model.lower()
    if "claude" in m or m.startswith("anthropic/"):
        return {}  # judge: leave unpinned so it routes to Anthropic even with fallback off
    fallback = os.environ.get("OR_LLM_PROVIDER_FALLBACK", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )
    return {"provider": {"order": order, "allow_fallbacks": fallback}}


def _array_key(tool: dict) -> str | None:
    """The name of the tool's array parameter (findings / verdicts / descriptions)."""
    props = tool.get("function", {}).get("parameters", {}).get("properties", {})
    return next((k for k, v in props.items() if v.get("type") == "array"), None)


def _close_partial(obj_text: str) -> dict | None:
    """Recover a truncated object (its closing `}` cut off) by keeping the complete top-level
    key/value pairs and dropping the incomplete trailing one, then closing the brace."""
    depth = 0
    last_comma = None
    in_str = esc = False
    for k, c in enumerate(obj_text):
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        elif c == "," and depth == 1:
            last_comma = k  # a top-level pair boundary — everything before it is complete
    if last_comma is None:
        return None
    try:
        return json.loads(obj_text[:last_comma] + "}")
    except json.JSONDecodeError:
        return None


def _salvage(raw: str, array_key: str) -> dict | None:
    """Best-effort recovery from truncated tool-call JSON: walk the result array and keep every
    complete `{...}` object, dropping only the incomplete trailing one. Returns {array_key: [...]}
    so a truncated response still yields all the findings the model did emit (AC-2)."""
    anchor = raw.find(f'"{array_key}"')
    start = raw.find("[", anchor) if anchor != -1 else -1
    if start == -1:
        return None
    objs: list = []
    i, n = start + 1, len(raw)
    while i < n:
        while i < n and raw[i] in " \t\r\n,":
            i += 1
        if i >= n or raw[i] != "{":
            break
        depth, j, in_str, esc, end = 0, i, False, False, None
        while j < n:
            c = raw[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
            j += 1
        if end is None:
            partial = _close_partial(raw[i:])  # last object's `}` was cut off — keep its whole pairs
            if partial is not None:
                objs.append(partial)
            break
        try:
            objs.append(json.loads(raw[i:end]))
        except json.JSONDecodeError:
            break
        i = end
    return {array_key: objs} if objs else None


def _log_cache(resp) -> None:
    """Surface provider-reported cached prompt tokens so cache reuse is visible in our own logs,
    not just the router's console. Shapes vary (OpenAI `prompt_tokens_details.cached_tokens`,
    DeepSeek `prompt_cache_hit_tokens`) — read defensively."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details is not None else None
    if cached is None:
        cached = getattr(usage, "prompt_cache_hit_tokens", None)
    if cached:
        print(f"· router: {cached} cached prompt token(s) reused", file=sys.stderr)


_REPAIR_SYSTEM = (
    "You repair malformed or truncated JSON. The user message is a broken tool-call argument "
    "string. Re-emit it as a single valid call to the given tool, keeping ONLY data that is "
    "actually present — never invent, complete, or guess missing values."
)


def _ai_repair(raw: str, tool: dict) -> dict | None:
    """Last-resort repair: hand the broken string to a cheap model whose forced tool schema
    guarantees valid structured output. Only used when deterministic salvage recovered nothing;
    off unless a repair model is configured (`OR_MODEL_REPAIR`, else describe/generate/`MODEL`)."""
    model = (
        os.environ.get("OR_MODEL_REPAIR")
        or os.environ.get("OR_MODEL_DESCRIBE")
        or os.environ.get("OR_MODEL_GENERATE")
        or os.environ.get("OR_MODEL")
    )
    if not model:
        return None
    try:
        return call_tool(model, _REPAIR_SYSTEM, raw, tool, repair=False)  # repair=False: no recursion
    except (OpenAIError, OperationalError):
        return None


def call_tool(model: str, system: str, user: str, tool: dict, repair: bool = True) -> dict | None:
    """One forced-tool-call round trip; returns the parsed tool arguments, or None
    if the model returned no tool call (AC-2)."""
    base_url = os.environ.get("OR_LLM_BASE_URL")
    if not base_url:
        raise OperationalError("OR_LLM_API_KEY is set but OR_LLM_BASE_URL is not")

    client = OpenAI(base_url=base_url, api_key=os.environ["OR_LLM_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        max_tokens=_max_tokens(),
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool["function"]["name"]}},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        extra_body=_extra_body(model),
    )
    _log_cache(resp)
    calls = resp.choices[0].message.tool_calls
    if not calls:
        return None
    raw = calls[0].function.arguments
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Truncated/malformed args (model hit max_tokens mid-JSON, finish_reason "length").
        # Salvage every complete object from the result array rather than lose the whole batch.
        key = _array_key(tool)
        salvaged = _salvage(raw, key) if key else None
        if salvaged:  # deterministic first: free, instant, can't hallucinate
            print(f"· router: recovered {len(salvaged[key])} item(s) from truncated output", file=sys.stderr)
            return salvaged
        if repair:  # nothing recoverable deterministically — ask a model to repair the string
            fixed = _ai_repair(raw, tool)
            if fixed is not None:
                print("· router: AI-repaired malformed tool output", file=sys.stderr)
                return fixed
        print("· router: tool-call args did not parse (truncated?) — skipping", file=sys.stderr)
        return None


def chat(model: str, messages: list, tools: list):
    """One tool-enabled turn (tool_choice=auto); returns the assistant message so the
    caller can run any tool calls and continue the loop (AC-11)."""
    base_url = os.environ.get("OR_LLM_BASE_URL")
    if not base_url:
        raise OperationalError("OR_LLM_API_KEY is set but OR_LLM_BASE_URL is not")

    client = OpenAI(base_url=base_url, api_key=os.environ["OR_LLM_API_KEY"])
    resp = client.chat.completions.create(
        model=model, max_tokens=_max_tokens(), messages=messages, tools=tools,
        tool_choice="auto", extra_body=_extra_body(model),
    )
    _log_cache(resp)
    return resp.choices[0].message
