"""Committed codemap (Spec §Codemap; AC-16, AC-16b, AC-17, AC-18, AC-19).

A **complete, deterministic** structural map of the repository — every source file and
every top-level symbol (functions, classes, methods), extracted via ast-grep
(grammars-as-data, no language runtime). The structural layer omits nothing; an LLM prose
layer may be added best-effort later. Committed to `.open-review/codemap.md` so git is the
persistent index; read back as architectural context on PR reviews. For fork/untrusted
PRs the map is read but never committed.
"""

from __future__ import annotations

import json
import os
import subprocess

# docref: begin codemap-path
CODEMAP_PATH = ".open-review/codemap.md"
# docref: end codemap-path

_LANGS = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
}

# Definition patterns that capture the symbol name as $NAME, per language.
_SYMBOL_PATTERNS = {
    "python": ["def $NAME($$$): $$$", "class $NAME: $$$", "class $NAME($$$): $$$"],
    "javascript": ["function $NAME($$$) { $$$ }", "class $NAME { $$$ }", "const $NAME = $$$"],
    "typescript": ["function $NAME($$$) { $$$ }", "class $NAME { $$$ }", "const $NAME = $$$"],
    "tsx": ["function $NAME($$$) { $$$ }", "class $NAME { $$$ }", "const $NAME = $$$"],
    "go": ["func $NAME($$$) $$$ { $$$ }", "func ($$$) $NAME($$$) $$$ { $$$ }", "type $NAME $$$"],
    "rust": ["fn $NAME($$$) $$$ { $$$ }", "struct $NAME $$$", "enum $NAME $$$"],
    "java": ["class $NAME { $$$ }", "$$$ $NAME($$$) { $$$ }"],
    "ruby": ["def $NAME\n  $$$\nend", "class $NAME\n  $$$\nend"],
}


def _source_files(repo: str) -> list[str]:
    root = os.path.realpath(repo)
    files = []
    for r, _dirs, names in os.walk(repo):
        if ".git" in r.split(os.sep):
            continue
        for n in names:
            if os.path.splitext(n)[1] in _LANGS:
                files.append(os.path.relpath(os.path.join(r, n), root))
    return sorted(files)


def _repo_langs(repo: str) -> set[str]:
    return {_LANGS[os.path.splitext(f)[1]] for f in _source_files(repo)}


def _astgrep_capture(pattern: str, lang: str, repo: str) -> list[tuple[str, str, int]]:
    proc = subprocess.run(
        ["ast-grep", "run", "-p", pattern, "-l", lang, "--json", repo],
        cwd=repo, capture_output=True, text=True,
    )
    try:
        items = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    root = os.path.realpath(repo)
    out = []
    for it in items:
        name = it.get("metaVariables", {}).get("single", {}).get("NAME", {}).get("text")
        if not name:
            continue
        rel = os.path.relpath(it.get("file", ""), root)
        line = it.get("range", {}).get("start", {}).get("line", 0) + 1
        out.append((rel, name, line))
    return out


def _symbols(repo: str) -> dict[str, list[tuple[str, int]]]:
    """{relpath: [(symbol, line), ...]} for every source file — the complete symbol set."""
    by_file: dict[str, list[tuple[str, int]]] = {}
    for lang in _repo_langs(repo):
        for pattern in _SYMBOL_PATTERNS.get(lang, []):
            for rel, name, line in _astgrep_capture(pattern, lang, repo):
                by_file.setdefault(rel, []).append((name, line))
    return by_file


def generate(repo: str) -> str:
    """Complete deterministic structural map: every source file and symbol (AC-16)."""
    files = _source_files(repo)
    syms = _symbols(repo)
    lines = [
        "# open-review codemap",
        "",
        "_Deterministic structural map — every source file and symbol. Generated; do not"
        " hand-edit._",
        "",
    ]
    for f in files:
        lines.append(f"## {f}")
        seen = set()
        for name, line in sorted(syms.get(f, []), key=lambda s: (s[1], s[0])):
            if (name, line) in seen:
                continue
            seen.add((name, line))
            lines.append(f"- {name} (L{line})")
        lines.append("")
    return "\n".join(lines)


def write(repo: str, content: str) -> None:
    path = os.path.join(repo, CODEMAP_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read(repo: str) -> str | None:
    """Return the committed codemap contents, or None if absent/empty (AC-17)."""
    path = os.path.join(repo, CODEMAP_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return content if content.strip() else None


def commit(repo: str, message: str = "docs: update open-review codemap [skip ci]") -> None:
    """Commit the codemap with a CI-skip marker to avoid recursive runs (AC-18)."""
    subprocess.run(["git", "add", CODEMAP_PATH], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)
