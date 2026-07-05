"""Vetted read-only investigation toolbox (Spec §Security; AC-9, AC-10, AC-12).

The model selects and parameterizes these allowlisted, non-networking commands; it never
emits raw shell. Subprocess actions (grep, find_callers, show_definition, blame) run in a
scrubbed environment (``env -i``-style: only PATH/HOME/LANG, no ``LLM_API_KEY`` or CI
secret — AC-10). All model-supplied paths are confined to the repo root and symbols must
be valid identifiers. Cross-language retrieval uses ast-grep, so no language runtime is
required (AC-12). Every action returns a string; an invalid request returns an
``error: ...`` string handed back to the model rather than raising (AC-9).

Free-form shell is a documented opt-in for trusted/self-hosted runners only and is NOT
part of this default trust model.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

# docref: begin allowlist
ALLOWLIST = (
    "grep",
    "find_callers",
    "show_definition",
    "blame",
    "read_range",
    "list_tests_for",
)
# docref: end allowlist

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_OUTPUT = 8000

# ast-grep language per file extension (grammars ship with ast-grep — no runtime needed).
_LANGS = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
    ".php": "php", ".c": "c", ".cc": "cpp", ".cpp": "cpp", ".cs": "csharp",
}

# show_definition patterns per language; SYMBOL is replaced with the validated symbol.
_DEF_PATTERNS = {
    "python": ["def SYMBOL($$$): $$$", "class SYMBOL: $$$", "class SYMBOL($$$): $$$"],
    "javascript": ["function SYMBOL($$$) { $$$ }", "const SYMBOL = $$$"],
    "typescript": ["function SYMBOL($$$) { $$$ }", "const SYMBOL = $$$"],
    "tsx": ["function SYMBOL($$$) { $$$ }", "const SYMBOL = $$$"],
    "go": ["func SYMBOL($$$) $$$ { $$$ }"],
    "rust": ["fn SYMBOL($$$) $$$ { $$$ }"],
    "java": ["$$$ SYMBOL($$$) { $$$ }"],
}


def _scrubbed_env() -> dict[str, str]:
    """``env -i``-style: only what tools need to run, never a secret (AC-10)."""
    return {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL") if k in os.environ}


def _run(cmd: list[str], cwd: str = ".") -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=_scrubbed_env(), capture_output=True, text=True)


def _ident(symbol: object) -> str:
    if not isinstance(symbol, str) or not _IDENT.match(symbol):
        raise ValueError(f"invalid symbol {symbol!r}; must be a plain identifier")
    return symbol


def _safe_path(repo: str, path: str) -> str:
    root = os.path.realpath(repo)
    full = os.path.realpath(os.path.join(root, path))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError(f"path escapes the repo root: {path}")
    return full


def _repo_langs(repo: str) -> set[str]:
    langs = set()
    for root, _dirs, files in os.walk(repo):
        if ".git" in root.split(os.sep):
            continue
        for f in files:
            lang = _LANGS.get(os.path.splitext(f)[1])
            if lang:
                langs.add(lang)
    return langs


def _astgrep(pattern: str, lang: str, repo: str) -> list[str]:
    proc = _run(["ast-grep", "run", "-p", pattern, "-l", lang, "--json", repo], cwd=repo)
    try:
        items = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    root = os.path.realpath(repo)
    out = []
    for it in items:
        rel = os.path.relpath(it.get("file", ""), root)
        line = it.get("range", {}).get("start", {}).get("line", 0) + 1
        text = (it.get("text", "").strip().splitlines() or [""])[0][:160]
        out.append(f"{rel}:{line}: {text}")
    return out


def _py_grep(pattern: str, repo: str) -> str:
    """Read-only, no-subprocess fallback when the ripgrep binary isn't present."""
    try:
        rx = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"invalid regex: {e}")
    out: list[str] = []
    root = os.path.realpath(repo)
    for r, _dirs, files in os.walk(repo):
        if ".git" in r.split(os.sep):
            continue
        for f in files:
            p = os.path.join(r, f)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            out.append(f"{os.path.relpath(p, root)}:{i}:{line.rstrip()}")
                            if len(out) >= 100:
                                return "\n".join(out)
            except OSError:
                continue
    return "\n".join(out)[:_MAX_OUTPUT] if out else "(no matches)"


def _grep(pattern: str, repo: str) -> str:
    if not isinstance(pattern, str) or not pattern or len(pattern) > 500:
        raise ValueError("pattern must be a non-empty string under 500 chars")
    if shutil.which("rg"):
        proc = _run(["rg", "--line-number", "--no-heading", "--max-count", "100", "--", pattern, repo], cwd=repo)
        return (proc.stdout or "(no matches)")[:_MAX_OUTPUT]
    return _py_grep(pattern, repo)


def _find_callers(symbol: str, repo: str) -> str:
    results: list[str] = []
    for lang in _repo_langs(repo):
        results += _astgrep(f"{symbol}($$$)", lang, repo)
    return "\n".join(results)[:_MAX_OUTPUT] if results else "(no callers found)"


def _show_definition(symbol: str, repo: str) -> str:
    results: list[str] = []
    for lang in _repo_langs(repo):
        for tmpl in _DEF_PATTERNS.get(lang, []):
            results += _astgrep(tmpl.replace("SYMBOL", symbol), lang, repo)
    return "\n".join(results)[:_MAX_OUTPUT] if results else "(no definition found)"


def _blame(path: str, line: int, repo: str) -> str:
    rel = os.path.relpath(_safe_path(repo, path), os.path.realpath(repo))
    proc = _run(["git", "blame", "-L", f"{line},{line}", "--", rel], cwd=repo)
    return (proc.stdout or proc.stderr or "(no blame)").strip()[:_MAX_OUTPUT]


def _read_range(path: str, start: int, end: int, repo: str) -> str:
    full = _safe_path(repo, path)
    if start < 1 or end < start or end - start > 400:
        raise ValueError("invalid range (1-based, end >= start, max 400 lines)")
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e}")
    chunk = lines[start - 1:end]
    return "".join(f"{start + i}: {ln}" for i, ln in enumerate(chunk))[:_MAX_OUTPUT] or "(empty)"


def _list_tests_for(path: str, repo: str) -> str:
    _safe_path(repo, path)  # validate confinement
    stem = os.path.splitext(os.path.basename(path))[0]
    hits = []
    for root, _dirs, files in os.walk(repo):
        if ".git" in root.split(os.sep):
            continue
        for f in files:
            if "test" in f.lower() and stem in f:
                hits.append(os.path.relpath(os.path.join(root, f), os.path.realpath(repo)))
    return "\n".join(sorted(hits)) or "(no matching test files)"


def run_action(name: str, args: dict, repo: str = ".") -> str:
    """Validate against ALLOWLIST + confinement, execute read-only, return a string (AC-9)."""
    if name not in ALLOWLIST:
        return f"error: '{name}' is not an allowed action; allowed: {', '.join(ALLOWLIST)}"
    try:
        if name == "grep":
            return _grep(args["pattern"], repo)
        if name == "find_callers":
            return _find_callers(_ident(args["symbol"]), repo)
        if name == "show_definition":
            return _show_definition(_ident(args["symbol"]), repo)
        if name == "blame":
            return _blame(args["file"], int(args["line"]), repo)
        if name == "read_range":
            return _read_range(args["file"], int(args["start"]), int(args["end"]), repo)
        if name == "list_tests_for":
            return _list_tests_for(args["file"], repo)
    except (KeyError, ValueError, TypeError) as e:
        return f"error: {e}"
    return f"error: '{name}' not implemented"
