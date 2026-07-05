"""OpenAI-compatible router client (Spec §Technical design; AC-2, AC-3).

Wraps the ``openai`` SDK pointed at ``LLM_BASE_URL`` so any router (LiteLLM,
OpenRouter, self-hosted) works unchanged. A forced tool call yields structured
findings/verdicts.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

from .errors import OperationalError


def is_configured() -> bool:
    """True iff a router API key is present — else the AI stage is skipped (AC-3)."""
    return bool(os.environ.get("LLM_API_KEY"))


def _max_tokens() -> int:
    """Output-token cap, configurable via `LLM_MAX_TOKENS`. Small/cheap models (e.g. a cheap
    `MODEL_DESCRIBE`) cap below the old hardcoded 8000 and would 400 — this lets them be set."""
    try:
        return int(os.environ.get("LLM_MAX_TOKENS", "8000"))
    except ValueError:
        return 8000


def _extra_body() -> dict:
    """OpenRouter provider routing, from human-friendly env:

      LLM_PROVIDER           comma-separated provider names in preference order, e.g. "DeepSeek,Together"
      LLM_PROVIDER_FALLBACK  bool (default true) — allow other providers when a preferred one
                             can't serve the requested model

    Fallback defaults to **true** on purpose: one global preference list then works for a mixed
    model set — DeepSeek-hosted models (generate/describe) pin to DeepSeek so the stable codemap
    prefix hits its cache, while an Anthropic model like the Opus judge falls through to its own
    provider instead of 404-ing. Set it false only if every model can be served by the listed
    providers. Unset LLM_PROVIDER → no routing constraint."""
    order = [p.strip() for p in os.environ.get("LLM_PROVIDER", "").split(",") if p.strip()]
    if not order:
        return {}
    fallback = os.environ.get("LLM_PROVIDER_FALLBACK", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )
    return {"provider": {"order": order, "allow_fallbacks": fallback}}


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


def call_tool(model: str, system: str, user: str, tool: dict) -> dict | None:
    """One forced-tool-call round trip; returns the parsed tool arguments, or None
    if the model returned no tool call (AC-2)."""
    base_url = os.environ.get("LLM_BASE_URL")
    if not base_url:
        raise OperationalError("LLM_API_KEY is set but LLM_BASE_URL is not")

    client = OpenAI(base_url=base_url, api_key=os.environ["LLM_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        max_tokens=_max_tokens(),
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool["function"]["name"]}},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        extra_body=_extra_body(),
    )
    _log_cache(resp)
    calls = resp.choices[0].message.tool_calls
    if not calls:
        return None
    return json.loads(calls[0].function.arguments)


def chat(model: str, messages: list, tools: list):
    """One tool-enabled turn (tool_choice=auto); returns the assistant message so the
    caller can run any tool calls and continue the loop (AC-11)."""
    base_url = os.environ.get("LLM_BASE_URL")
    if not base_url:
        raise OperationalError("LLM_API_KEY is set but LLM_BASE_URL is not")

    client = OpenAI(base_url=base_url, api_key=os.environ["LLM_API_KEY"])
    resp = client.chat.completions.create(
        model=model, max_tokens=_max_tokens(), messages=messages, tools=tools,
        tool_choice="auto", extra_body=_extra_body(),
    )
    _log_cache(resp)
    return resp.choices[0].message
