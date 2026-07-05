"""Committed codemap (Spec §Codemap; AC-16, AC-16b..AC-16f, AC-17, AC-18, AC-19).

A **complete, deterministic**, multi-language structural map of the repository. Symbols
(every function, method, class, type) come from **universal-ctags** — one small offline
binary with bundled grammars for 40+ languages, no language runtime, no network, no
service. Call edges come from **ast-grep**; signatures are read from the declaration line;
one-line descriptions come from each symbol's own doc-comment (Python via the stdlib `ast`,
other languages via the doc-comment convention above the declaration). The structural layer
omits nothing. Committed to `.open-review/codemap.md` so git is the persistent index; read
back as architectural context on PR reviews. For fork/untrusted PRs it is read, never committed.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict

from openai import OpenAIError

from . import router

# docref: begin codemap-path
CODEMAP_PATH = ".open-review/codemap.md"
# docref: end codemap-path

# Per external-tool call, in seconds — bounds ast-grep/ctags on huge repos (configurable).
_CMD_TIMEOUT = int(os.environ.get("OPEN_REVIEW_TOOL_TIMEOUT", "300"))

_AI_PREFIX = "_(ai)_ "  # marks a line as an AI-generated description (vs the author's own doc)

_DESCRIBE_SYSTEM = (
    "You document code for a repository map. For each listed symbol, return one short, factual "
    "line describing what it does, inferred from its name and signature. No fluff; do not just "
    "restate the signature."
)
_DESCRIBE_TOOL = {
    "type": "function",
    "function": {
        "name": "describe_symbols",
        "description": "Return a one-line description for each symbol id.",
        "parameters": {
            "type": "object",
            "properties": {
                "descriptions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
                        "required": ["id", "text"],
                    },
                },
            },
            "required": ["descriptions"],
        },
    },
}

# Extension → ast-grep language id. Used to (a) select which git-tracked files are "source"
# and (b) drive ast-grep call extraction. ctags auto-detects languages itself, so this list
# only needs to cover the languages we want call graphs for — the top ~15 by usage.
_LANGS = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "tsx", ".go": "go", ".rs": "rust",
    ".java": "java", ".rb": "ruby", ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp",
    ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".cs": "csharp", ".kt": "kotlin",
    ".kts": "kotlin", ".swift": "swift", ".scala": "scala", ".sc": "scala", ".sh": "bash",
    ".bash": "bash", ".lua": "lua",
}

# Extensions universal-ctags parses but ast-grep does not — discovered and symbol-mapped
# (ctags gives signatures + docs), but no call graph. PowerShell and Windows Batch scripts.
_CTAGS_ONLY_EXT = {".ps1", ".psm1", ".psd1", ".bat", ".cmd"}

# ctags kind taxonomy. Symbols = everything ctags finds that is a declaration, minus locals/
# packaging noise and minus variables/constants (those are surfaced separately as module
# vars). A denylist keeps this complete across ctags' 40+ languages without enumerating every
# per-language kind name — honouring the "map EVERYTHING" hard criterion.
# "label" is NOT skipped: in Batch scripts a `:label` is the unit of code you `call` (its
# function), so dropping labels would leave Batch files symbol-less. Rare goto/loop labels
# elsewhere are minor noise.
_SKIP_KINDS = {"local", "parameter", "arg", "package", "import", "include", "using",
               "namespaceAlias", "section", "chapter", "part", "unknown"}
_VAR_KINDS = {"variable", "constant", "var", "const", "global"}
_CALLABLE_KINDS = {"function", "method", "func", "subroutine", "procedure",
                   "singletonMethod", "constructor", "prototype", "operator", "accessor",
                   "getter", "setter", "label"}  # Batch `:label` is the unit you `call`
_TYPE_KINDS = {"class", "struct", "interface", "trait", "enum", "namespace", "module",
               "typedef", "union", "record", "object", "protocol", "annotation"}

# Doc-comment markers per extension, for the "one-line description above the declaration"
# convention. Python is handled by `ast` (real docstrings), not by this table.
_SLASH = ("///", "//!", "/**", "/*", "*/", "*", "//")
_DOC_MARKERS = {ext: _SLASH for ext in (
    ".go", ".rs", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".c", ".h", ".cpp",
    ".cc", ".cxx", ".hpp", ".hh", ".cs", ".kt", ".kts", ".swift", ".scala", ".sc", ".php")}
_DOC_MARKERS.update({ext: ("#",) for ext in (".rb", ".sh", ".bash")})
_DOC_MARKERS.update({".lua": ("--",)})
_DOC_MARKERS.update({ext: ("#",) for ext in (".ps1", ".psm1", ".psd1")})  # PowerShell
_DOC_MARKERS.update({ext: ("::", "REM", "rem", "@REM", "@rem") for ext in (".bat", ".cmd")})  # Batch

# Call-expression pattern per ast-grep language; default is the bare call `$F($$$)`. C parses
# that as a declarator, so it needs explicit call-context patterns (partial: the declarator-
# init form `T v = f()` is still missed). Ruby/Bash paren-less calls are syntactically
# identical to identifiers and cannot be extracted by pattern — only their parenthesized calls
# are captured by the default.
_CALL_PATTERNS = {"c": ["$F($$$);", "return $F($$$)", "$F($$$)"]}


def _source_files(repo: str) -> list[str]:
    proc = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    exts = set(_LANGS) | _CTAGS_ONLY_EXT
    return sorted(f for f in proc.stdout.splitlines() if os.path.splitext(f)[1] in exts)


#: Public entry point for the tracked source-file set (used by the CLI baseline command).
source_files = _source_files


def _repo_langs(repo: str) -> set[str]:
    """ast-grep language ids present (for call/import extraction) — excludes ctags-only langs."""
    return {_LANGS[ext] for f in _source_files(repo) if (ext := os.path.splitext(f)[1]) in _LANGS}


def _astgrep(pattern: str, lang: str, repo: str) -> list[dict]:
    """Raw ast-grep JSON matches (empty list on any failure — fail-soft, never crash the map)."""
    try:
        proc = subprocess.run(
            ["ast-grep", "run", "-p", pattern, "-l", lang, "--json", repo],
            cwd=repo, capture_output=True, text=True, timeout=_CMD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return []
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []


def _meta(it: dict, var: str) -> str | None:
    return it.get("metaVariables", {}).get("single", {}).get(var, {}).get("text")


def _relf(it: dict, root: str) -> str | None:
    """Relative path of an ast-grep match, or None if it carries no file (guards the empty-path
    `os.path.relpath('', root)` ValueError)."""
    f = it.get("file")
    return os.path.relpath(f, root) if f else None


def _ctags(repo: str) -> list[dict]:
    """All ctags tags over the tracked source files — the multi-language symbol layer (name,
    kind, line, end, signature). universal-ctags parses 40+ languages from bundled grammars:
    no language runtime, no network, no service. Returns [] if ctags is absent (degraded)."""
    if not shutil.which("ctags"):
        print("· codemap: universal-ctags not on PATH — symbol layer skipped", file=sys.stderr)
        return []
    files = _source_files(repo)
    if not files:
        return []
    try:
        proc = subprocess.run(
            ["ctags", "--output-format=json", "--fields=+neKSl", "--sort=no", "-f", "-", "-L", "-"],
            input="\n".join(files) + "\n", cwd=repo, capture_output=True, text=True, timeout=_CMD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print("· codemap: ctags timed out — symbol layer skipped", file=sys.stderr)
        return []
    tags = []
    for line in proc.stdout.splitlines():
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        if t.get("_type") == "tag" and t.get("name") and t.get("path"):
            tags.append(t)
    return tags


def _symbols_from(tags: list[dict]) -> dict[str, list[tuple[str, int]]]:
    by_file: dict[str, list[tuple[str, int]]] = defaultdict(list)
    seen = set()
    for t in tags:
        kind = t.get("kind", "")
        if kind in _SKIP_KINDS or kind in _VAR_KINDS:
            continue
        # types/containers and callables are symbols; a signature marks a callable whose kind
        # is language-specific (Python methods are "member"). A signature-less data field is not.
        if not (kind in _CALLABLE_KINDS or kind in _TYPE_KINDS or t.get("signature")):
            continue
        key = (t["path"], t["name"], t.get("line", 0))
        if key in seen:
            continue
        seen.add(key)
        by_file[t["path"]].append((t["name"], t.get("line", 0)))
    return dict(by_file)


def _symbols(repo: str) -> dict[str, list[tuple[str, int]]]:
    """{relpath: [(symbol, line), ...]} for every source file — the complete symbol set,
    across all ctags-supported languages."""
    return _symbols_from(_ctags(repo))


def _franges_from(tags: list[dict]) -> dict[str, list[tuple[str, int, int]]]:
    """{relpath: [(func, start, end), ...]} — to attribute each call to its enclosing function.
    `end` is ctags' end-line where the grammar provides it, else the start line."""
    by_file: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for t in tags:
        kind = t.get("kind", "")
        if kind in _CALLABLE_KINDS or (t.get("signature") and kind not in _VAR_KINDS):
            start = t.get("line", 0)
            end = t.get("end", start)
            by_file[t["path"]].append((t["name"], start, end if isinstance(end, int) and end >= start else start))
    return by_file


def _module_vars_from(tags: list[dict], repo: str) -> dict[str, list[tuple[str, int]]]:
    """{relpath: [(name, line), ...]} for module/package-level variables and constants. ctags
    finds every var; the column-0 source check keeps only top-level ones (locals and class
    fields are indented) — a language-general filter that works where ctags' scope does not."""
    by_file: dict[str, list[tuple[str, int]]] = defaultdict(list)
    cache: dict[str, list[str]] = {}
    for t in tags:
        if t.get("kind", "") not in _VAR_KINDS:
            continue
        f, ln = t["path"], t.get("line", 0)
        if f not in cache:
            try:
                with open(os.path.join(repo, f), encoding="utf-8", errors="ignore") as fh:
                    cache[f] = fh.read().splitlines()
            except OSError:
                cache[f] = []
        lines = cache[f]
        if 1 <= ln <= len(lines) and lines[ln - 1][:1] not in (" ", "\t"):  # column 0 ⇒ top-level
            entry = (t["name"], ln)
            if entry not in by_file[f]:
                by_file[f].append(entry)
    return by_file


def _module_vars(repo: str) -> dict[str, list[tuple[str, int]]]:
    return _module_vars_from(_ctags(repo), repo)


def _declaration(src_lines: list[str], start_1based: int) -> str:
    """The declaration text as written (any language): the def line(s), joined across a
    multi-line parameter list, cut at the body opener (`{` or a trailing `:`). Language-general
    — it reads the source rather than guessing a per-language pattern."""
    i = start_1based - 1
    if not (0 <= i < len(src_lines)):
        return ""
    decl = src_lines[i].strip()
    depth = decl.count("(") - decl.count(")")
    j = i + 1
    while depth > 0 and j < len(src_lines) and j < i + 8:
        nxt = src_lines[j].strip()
        decl += " " + nxt
        depth += nxt.count("(") - nxt.count(")")
        j += 1
    depth, cut = 0, None
    for k, c in enumerate(decl):
        if c == "{":
            if depth <= 0:
                cut = k
                break
            depth += 1
        elif c in "([":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ":" and depth <= 0 and decl[k - 1:k] != ":" and decl[k + 1:k + 2] != ":":
            cut = k  # python/ruby body separator — but NOT a C++/Rust `::` scope operator
            break
    if cut is not None:
        decl = decl[:cut]
    return decl.strip().rstrip("{").strip()


def _comment_above(src_lines: list[str], start_1based: int, ext: str) -> str:
    """First meaningful line of the doc-comment block directly above a declaration (`//`,
    `///`, JSDoc `/** */`, `#`, `--` per language). Empty if there is none."""
    marks = _DOC_MARKERS.get(ext, ())
    if not marks:
        return ""
    i = start_1based - 2  # line directly above the declaration (0-based)
    got: list[str] = []
    while i >= 0:
        s = src_lines[i].strip()
        if not s:
            break
        if any(s.startswith(m) for m in marks) or s.endswith("*/"):
            got.append(s)
            i -= 1
        else:
            break
    for s in reversed(got):  # top of the block downward
        text = s[:-2] if s.endswith("*/") else s  # drop a trailing block-comment close
        text = text.lstrip()
        for m in ("///", "//!", "/**", "/*", "//", "#", "--", "*"):  # strip ONE leading marker
            if text.startswith(m):
                text = text[len(m):]
                break
        text = text.strip()  # only whitespace — never content characters like * ! /
        if text and not text.startswith("@"):
            return text
    return ""


def _details(
    repo: str,
    syms: dict[str, list[tuple[str, int]]],
    ctag_sigs: dict[tuple[str, str], str] | None = None,
) -> dict[tuple[str, str], tuple[str, str]]:
    """{(relpath, name): (signature, doc_first_line)} across languages, fully static:
    signature from the declaration line (falling back to ctags' parameter signature when a
    symbol shares its line with a neighbour); doc from the Python docstring (`ast`, parse-only)
    or, for other languages, the doc-comment above the declaration."""
    ctag_sigs = ctag_sigs or {}
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for f, symlist in syms.items():
        try:
            with open(os.path.join(repo, f), encoding="utf-8", errors="ignore") as fh:
                src = fh.read()
        except OSError:
            continue
        src_lines = src.splitlines()
        ext = os.path.splitext(f)[1]
        pydocs: dict[str, str] = {}
        if ext == ".py":
            try:
                for node in ast.walk(ast.parse(src)):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        d = (ast.get_docstring(node) or "").strip()
                        if d:
                            pydocs[node.name] = d.splitlines()[0].strip()
            except (SyntaxError, ValueError):
                pass
        for name, line in symlist:
            sig = _declaration(src_lines, line)
            if name not in sig:  # line belongs to a neighbour (same-line decl) or is unreadable
                sig = f"{name}{ctag_sigs.get((f, name), '')}"
            doc = pydocs.get(name, "") if ext == ".py" else _comment_above(src_lines, line, ext)
            out[(f, name)] = (sig, doc)
    return out


def _py_import_names(text: str) -> list[tuple[str, str]]:
    """Parse a Python import statement into (local_name, module) pairs. `import a.b` binds
    the head `a`; `from x import y as z` binds `z`→`x`. Deterministic, no execution."""
    text = " ".join(text.split())
    out: list[tuple[str, str]] = []
    if text.startswith("from ") and " import " in text:
        mod, _, names = text[5:].partition(" import ")
        mod = mod.strip()
        dots_only = mod and set(mod) <= {"."}  # `from . import ai` ⇒ ai is itself a sibling module
        for part in names.replace("(", "").replace(")", "").split(","):
            part = part.strip()
            if not part or part == "*":
                continue
            orig = part.split(" as ")[0].strip()
            local = part.split(" as ")[-1].strip()
            if local.isidentifier():
                out.append((local, orig if dots_only else mod))
    elif text.startswith("import "):
        for part in text[7:].split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                mod, _, alias = part.partition(" as ")
                out.append((alias.strip(), mod.strip()))
            else:
                out.append((part.split(".")[0].strip(), part.strip()))
    return out


_JS_FROM = re.compile(r"""import\s+(.+?)\s+from\s+['"]([^'"]+)['"]""")


def _js_import_names(text: str) -> list[tuple[str, str]]:
    """Parse a JS/TS `import ... from 'mod'` into (local_name, module) pairs: default,
    `{ named, aliased as x }`, and `* as ns` forms. Module keeps its path (`./util`)."""
    text = " ".join(text.split())
    m = _JS_FROM.search(text)
    if not m:
        return []
    clause, mod = m.group(1).strip(), m.group(2)
    out: list[tuple[str, str]] = []
    if clause.startswith("*"):  # * as ns
        parts = clause.split(" as ")
        if len(parts) == 2 and parts[1].strip().isidentifier():
            out.append((parts[1].strip(), mod))
        return out
    named = ""
    if "{" in clause:
        default_part = clause[: clause.index("{")].strip().rstrip(",").strip()
        if "}" in clause:
            named = clause[clause.index("{") + 1 : clause.index("}")]
    else:
        default_part = clause
    if default_part:
        name = default_part.split(",")[0].strip()
        if name.isidentifier():
            out.append((name, mod))
    for item in named.split(","):
        local = item.strip().split(" as ")[-1].strip()
        if local.isidentifier():
            out.append((local, mod))
    return out


def _imports(repo: str) -> dict[str, dict[str, str]]:
    """{relpath: {local_name: module}} — Python and JS/TS precise; other languages best-effort
    empty (the resolver still handles same-file and repo-unique names for them)."""
    root = os.path.realpath(repo)
    by_file: dict[str, dict[str, str]] = defaultdict(dict)
    langs = _repo_langs(repo)
    if "python" in langs:
        for pattern in ("from $M import $$$", "import $M"):
            for it in _astgrep(pattern, "python", repo):
                rel = _relf(it, root)
                if rel is None:
                    continue
                for local, mod in _py_import_names(it.get("text", "")):
                    by_file[rel][local] = mod
    for lang in ("javascript", "typescript", "tsx"):
        if lang in langs:
            for it in _astgrep("import $$$ from $M", lang, repo):
                rel = _relf(it, root)
                if rel is None:
                    continue
                for local, mod in _js_import_names(it.get("text", "")):
                    by_file[rel][local] = mod
    return by_file


def _calls(repo: str) -> dict[str, list[tuple[str, int]]]:
    """{relpath: [(callee_text, line), ...]} — every call expression, callee as written. Runs
    for each ast-grep-supported language present; languages it can't parse simply yield none."""
    root = os.path.realpath(repo)
    by_file: dict[str, list[tuple[str, int]]] = defaultdict(list)
    seen: set[tuple[str, str, int]] = set()
    for lang in _repo_langs(repo):
        for pattern in _CALL_PATTERNS.get(lang, ["$F($$$)"]):
            for it in _astgrep(pattern, lang, repo):
                callee = _meta(it, "F")
                if not callee:
                    continue
                rel = _relf(it, root)
                if rel is None:
                    continue
                line = it.get("range", {}).get("start", {}).get("line", 0) + 1
                key = (rel, callee, line)
                if key in seen:  # a call can match several patterns (C) — count it once
                    continue
                seen.add(key)
                by_file[rel].append((callee, line))
    return by_file


def _basename(rel: str) -> str:
    return os.path.splitext(os.path.basename(rel))[0]


def _resolve_module(mod: str, from_file: str, files: list[str]) -> str | None:
    """Map an import module string to a repo file by basename (last dotted component),
    preferring the importer's own directory when several files share the name. Returns None
    for external modules (stdlib/third-party) or genuine cross-directory ambiguity."""
    comp = mod.lstrip(".").split(".")[-1]
    if not comp:
        return None
    cands = [f for f in files if _basename(f) == comp]
    if len(cands) == 1:
        return cands[0]
    if not cands:
        return None
    samedir = [f for f in cands if os.path.dirname(f) == os.path.dirname(from_file)]
    return samedir[0] if len(samedir) == 1 else None


def _call_graph(repo: str, tags: list[dict] | None = None) -> dict[tuple[str, str], dict[str, set]]:
    """Resolve every call edge to a repo symbol via the import table (see AC-16c ladder) and
    attribute it to its enclosing function. Returns {(file, sym): {calls, called_by, ambiguous}}.
    Deterministic, no language server. Ambiguous shared bare names are flagged, never guessed.
    """
    tags = _ctags(repo) if tags is None else tags
    files = _source_files(repo)
    symbols = _symbols_from(tags)
    local_names = {f: {n for n, _ in lst} for f, lst in symbols.items()}
    name_files: dict[str, set[str]] = defaultdict(set)
    for f, lst in symbols.items():
        for n, _ in lst:
            name_files[n].add(f)
    imports = _imports(repo)
    franges = _franges_from(tags)
    calls = _calls(repo)

    graph: dict[tuple[str, str], dict[str, set]] = defaultdict(
        lambda: {"calls": set(), "called_by": set(), "ambiguous": set()}
    )

    def enclosing(f: str, line: int) -> str:
        best = None  # (name, start) — nearest preceding definition that could contain the call
        for name, s, e in franges.get(f, []):
            if s <= line and (line <= e or e <= s):
                if best is None or s > best[1]:
                    best = (name, s)
        return best[0] if best else "<module>"

    def resolve(f: str, callee: str) -> tuple[str, str] | None:
        if "." in callee:  # qualified: head.….last — resolve head through imports
            head, last = callee.split(".")[0], callee.split(".")[-1]
            mod = imports.get(f, {}).get(head)
            if mod:
                mf = _resolve_module(mod, f, files)
                if mf and last in local_names.get(mf, ()):
                    return (mf, last)
            return None
        if callee in local_names.get(f, ()):  # same-file local
            return (f, callee)
        if callee in imports.get(f, {}):  # `from x import callee`
            mf = _resolve_module(imports[f][callee], f, files)
            if mf:
                return (mf, callee)
        hits = name_files.get(callee, set())
        if len(hits) == 1:  # repo-unique symbol
            return (next(iter(hits)), callee)
        return None  # >1 ⇒ ambiguous (handled by caller); 0 ⇒ external

    for f, clist in calls.items():
        for callee, line in clist:
            node = (f, enclosing(f, line))
            target = resolve(f, callee)
            if target and target != node:
                graph[node]["calls"].add(target)
                graph[target]["called_by"].add(node)
            elif target is None and "." not in callee and len(name_files.get(callee, ())) > 1:
                graph[node]["ambiguous"].add(callee)
    return graph


def _prior_ai(text: str) -> dict[tuple[str, str], tuple[str, str]]:
    """Parse AI descriptions out of a previously committed codemap → {(file, name): (sig, desc)}.
    Lets iterate reuse a description when the symbol's signature is unchanged — no re-spend."""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    cur_file = cur_name = cur_sig = None
    for line in text.splitlines():
        if line.startswith("## "):
            cur_file, cur_name, cur_sig = line[3:].strip(), None, None
        elif line.startswith("### "):
            cur_name, cur_sig = line[4:].rsplit(" (L", 1)[0].strip(), None
        elif cur_name and len(line) > 1 and line[0] == "`" and line[-1] == "`":
            cur_sig = line.strip("`")
        elif line.startswith(_AI_PREFIX) and cur_file and cur_name:
            out[(cur_file, cur_name)] = (cur_sig, line[len(_AI_PREFIX):].strip())
    return out


def _describe(
    repo: str,
    syms: dict[str, list[tuple[str, int]]],
    details: dict[tuple[str, str], tuple[str, str]],
    prior: dict[tuple[str, str], tuple[str, str]],
    ranges: dict[tuple[str, str], tuple[int, int]],
    budget: int = 15000,
) -> dict[tuple[str, str], str]:
    """Opt-in AI one-liners for symbols with **no author doc** (AC-16g). Reuses a prior
    description whenever the symbol's signature is unchanged, so iterate only spends tokens on
    new/changed symbols. The whole symbol **body** (from its ctags line range) is sent so the
    description reflects what the code does, not just its name. Runs on a cheap, configurable
    model (`MODEL_DESCRIBE`, else `MODEL_GENERATE`/`MODEL`), batched under a char budget;
    no-ops if the router is unset."""
    result: dict[tuple[str, str], str] = {}
    needers: list[tuple[str, str, str]] = []
    for f, symlist in syms.items():
        for name, _line in symlist:
            sig, doc = details.get((f, name), ("", ""))
            if doc:
                continue  # the author already documented it
            was = prior.get((f, name))
            if was and was[0] == sig and was[1]:
                result[(f, name)] = was[1]  # unchanged → reuse, no model call
            else:
                needers.append((f, name, sig))
    if not needers or not router.is_configured():
        return result
    model = (
        os.environ.get("MODEL_DESCRIBE")
        or os.environ.get("MODEL_GENERATE")
        or os.environ.get("MODEL")
    )
    if not model:
        return result

    src_cache: dict[str, list[str]] = {}

    def body(f: str, name: str) -> str:
        if f not in src_cache:
            try:
                with open(os.path.join(repo, f), encoding="utf-8", errors="ignore") as fh:
                    src_cache[f] = fh.read().splitlines()
            except OSError:
                src_cache[f] = []
        lines = src_cache[f]
        start, end = ranges.get((f, name), (0, 0))
        if 1 <= start <= len(lines):
            return "\n".join(lines[start - 1 : max(end, start)])[:3000]
        return ""

    batches: list[list[tuple[str, str, str, str]]] = []
    cur: list[tuple[str, str, str, str]] = []
    size = 0
    for f, name, sig in needers:
        b = body(f, name)
        if cur and size + len(b) + len(sig) > budget:
            batches.append(cur)
            cur, size = [], 0
        cur.append((f, name, sig, b))
        size += len(b) + len(sig)
    if cur:
        batches.append(cur)

    for batch in batches:
        parts = [
            f"{i}. {f} — {sig or name}\n```\n{b}\n```"
            for i, (f, name, sig, b) in enumerate(batch)
        ]
        user = "Describe what each symbol does in one short factual line, by id:\n\n" + "\n\n".join(parts)
        try:
            data = router.call_tool(model, _DESCRIBE_SYSTEM, user, _DESCRIBE_TOOL)
        except OpenAIError:
            continue
        for d in (data or {}).get("descriptions", []):
            i, text = d.get("id"), (d.get("text") or "").strip()
            if isinstance(i, int) and 0 <= i < len(batch) and text:
                f, name, _sig, _b = batch[i]
                result[(f, name)] = text
    return result


def generate(repo: str, describe: bool = False, light: bool = False) -> str:
    """Complete deterministic, multi-language structural map: every source file, symbol (with
    signature + its own one-line description), import, navigable call edge, and module-level
    variable (AC-16, AC-16c..AC-16f). With describe=True, undocumented symbols get an opt-in,
    iterate-cached AI description (AC-16g). With light=True, emit a **compact** structural-only
    variant — one line per symbol, no docstrings/descriptions/navigable refs — that keeps
    everything the reviewer needs at a fraction of the tokens, for small context windows (AC-16h)."""
    tags = _ctags(repo)
    files = _source_files(repo)
    syms = _symbols_from(tags)
    imports = _imports(repo)
    mvars = _module_vars_from(tags, repo)
    graph = _call_graph(repo, tags)
    ctag_sigs = {(t["path"], t["name"]): t.get("signature", "") for t in tags if t.get("signature")}
    details = _details(repo, syms, ctag_sigs)
    if describe and not light:  # light drops prose entirely, so it never spends describe tokens
        ranges = {(t["path"], t["name"]): (t.get("line", 0), t.get("end", t.get("line", 0))) for t in tags}
        ai_desc = _describe(repo, syms, details, _prior_ai(read(repo) or ""), ranges)
    else:
        ai_desc = {}
    sym_line = {(f, n): ln for f, lst in syms.items() for n, ln in lst}

    def ref(target: tuple[str, str], cur: str) -> str:
        """A navigable reference: `name (L12)` same-file, `name (path/to.py:12)` cross-file."""
        tf, tn = target
        ln = sym_line.get(target)
        if tf == cur:
            return f"{tn} (L{ln})" if ln else tn
        return f"{tn} ({tf}:{ln})" if ln else f"{tn} ({tf})"

    def short(target: tuple[str, str], cur: str) -> str:
        """A compact reference (light mode): `name` same-file, `basename.name` cross-file."""
        tf, tn = target
        return tn if tf == cur else f"{_basename(tf)}.{tn}"

    def edges(node: dict, cur: str) -> str:
        r = short if light else ref
        outs = sorted(r(t, cur) for t in node["calls"])
        outs += sorted(f"{a}?" for a in node["ambiguous"])
        return ", ".join(outs)

    kind = " (light)" if light else ""
    blurb = (
        "Compact structural map for LLM context — symbols, signatures, imports, call edges,"
        " module vars. No prose."
        if light
        else "Deterministic multi-language structural map — every source file, symbol (signature +"
        " its own description), import, navigable call edge, and module-level variable."
        " Symbols via universal-ctags; call edges via ast-grep."
    )
    lines = [f"# open-review codemap{kind}", "", f"_{blurb} Generated; do not hand-edit._", ""]
    for f in files:
        lines.append(f"## {f}")
        imps = sorted(set(imports.get(f, {}).values()))
        if imps:
            lines.append(f"- imports: {', '.join(imps)}")
        mv = mvars.get(f, [])
        if mv:
            mvsorted = sorted(mv, key=lambda x: x[1])
            if light:
                lines.append("- vars: " + ", ".join(n for n, _ in mvsorted))
            else:
                lines.append("- module vars: " + ", ".join(f"{n} (L{ln})" for n, ln in mvsorted))
        modnode = graph.get((f, "<module>"))
        if modnode and (modnode["calls"] or modnode["ambiguous"]):
            lines.append(f"- module-level calls: {edges(modnode, f)}")
        seen = set()
        for name, line in sorted(syms.get(f, []), key=lambda s: (s[1], s[0])):
            if (name, line) in seen:
                continue
            seen.add((name, line))
            sig, doc = details.get((f, name), ("", ""))
            node = graph.get((f, name))
            if light:
                parts = [f"{sig or name} L{line}"]  # sig already carries the name
                if node and (node["calls"] or node["ambiguous"]):
                    parts.append(f"→ {edges(node, f)}")
                if node and node["called_by"]:
                    parts.append(f"← {', '.join(sorted(short(c, f) for c in node['called_by']))}")
                lines.append(" ".join(parts))
                continue
            lines.append(f"### {name} (L{line})")
            if sig:
                lines.append(f"`{sig}`")
            if doc:
                lines.append(doc)
            elif (f, name) in ai_desc:
                lines.append(f"{_AI_PREFIX}{ai_desc[(f, name)]}")
            if not node:
                continue
            if node["calls"] or node["ambiguous"]:
                lines.append(f"- calls: {edges(node, f)}")
            if node["called_by"]:
                lines.append(
                    f"- called by: {', '.join(sorted(ref(c, f) for c in node['called_by']))}"
                )
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
