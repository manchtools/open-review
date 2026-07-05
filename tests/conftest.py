"""Shared fixtures: a real git repo and a fake OpenAI-compatible router.

Per the spec's Test requirements, the router HTTP call is the only external boundary we
stub — everything else (git, scanners, ast-grep, parsing, the openai SDK path) is real.
"""

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


@pytest.fixture
def git_repo(tmp_path):
    """Temp git repo with a base commit and a change on HEAD. Returns (path, base_sha)."""

    def g(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    g("add", ".")
    g("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    (tmp_path / "a.py").write_text("def f():\n    return 2  # changed\n")
    g("add", ".")
    g("commit", "-qm", "change")
    return tmp_path, base


_DEFAULT_REPORT = {
    "summary": "s",
    "findings": [
        {"file": "a.py", "line": 1, "severity": "warning",
         "category": "bug", "message": "m", "suggestion": ""}
    ],
}


@pytest.fixture
def fake_router():
    """Fake OpenAI-compatible server serving a scripted queue of tool calls.

    Yields (base_url, control). ``control(payload)`` sets a single ``report`` tool call
    (the common case). ``control.script(*specs)`` queues a sequence, each spec either
    ``("report", payload)`` or ``("tool", name, args)``; once the queue drains to one, the
    last item repeats (so a single tool spec loops forever for max-steps tests).
    """
    queue = [{"name": "report", "arguments": _DEFAULT_REPORT}]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length", 0)))
            spec = queue.pop(0) if len(queue) > 1 else queue[0]
            body = json.dumps({
                "id": "chatcmpl-x", "object": "chat.completion", "created": 0, "model": "fake",
                "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {
                        "name": spec["name"], "arguments": json.dumps(spec["arguments"])}}]}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def control(payload):
        queue[:] = [{"name": "report", "arguments": payload}]

    def script(*specs):
        q = []
        for s in specs:
            if s[0] == "report":
                q.append({"name": "report", "arguments": s[1]})
            else:
                q.append({"name": s[1], "arguments": s[2]})
        queue[:] = q

    control.script = script
    yield f"http://127.0.0.1:{port}/v1", control
    srv.shutdown()


@pytest.fixture(autouse=True)
def offline_semgrep(tmp_path_factory, monkeypatch):
    """Default every test to an offline, no-match semgrep rule so nothing reaches the
    semgrep registry (network). Tests that want a real match override SEMGREP_CONFIG."""
    rule = tmp_path_factory.mktemp("sg") / "noop.yaml"
    rule.write_text(
        "rules:\n"
        "  - id: noop\n"
        "    languages: [python]\n"
        "    severity: INFO\n"
        "    message: noop\n"
        "    pattern: __open_review_never_match__\n"
    )
    monkeypatch.setenv("SEMGREP_CONFIG", str(rule))
