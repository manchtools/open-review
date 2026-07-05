"""OpenAI-compatible router client (Spec §Technical design; AC-2, AC-3).

Wraps the ``openai`` SDK pointed at ``LLM_BASE_URL`` so any router (LiteLLM,
OpenRouter, self-hosted) works unchanged. A forced tool call yields structured
findings/verdicts.
"""

from __future__ import annotations

import json
import os

from openai import OpenAI

from .errors import OperationalError


def is_configured() -> bool:
    """True iff a router API key is present — else the AI stage is skipped (AC-3)."""
    return bool(os.environ.get("LLM_API_KEY"))


def call_tool(model: str, system: str, user: str, tool: dict) -> dict | None:
    """One forced-tool-call round trip; returns the parsed tool arguments, or None
    if the model returned no tool call (AC-2)."""
    base_url = os.environ.get("LLM_BASE_URL")
    if not base_url:
        raise OperationalError("LLM_API_KEY is set but LLM_BASE_URL is not")

    client = OpenAI(base_url=base_url, api_key=os.environ["LLM_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool["function"]["name"]}},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
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
        model=model, max_tokens=8000, messages=messages, tools=tools, tool_choice="auto"
    )
    return resp.choices[0].message
