# open-review codemap

_Deterministic multi-language structural map — every source file, symbol (signature + its own description), import, navigable call edge, and module-level variable. Symbols via universal-ctags; call edges via ast-grep. Generated; do not hand-edit._

## src/open_review/__init__.py
- module vars: __version__ (L1)

## src/open_review/ai.py
- imports: .errors, .findings, cascade, json, openai, os, router, sys, toolbox
- module vars: SYSTEM (L23), REPORT_TOOL (L31), TOOLBOX_TOOLS (L81)
- module-level calls: _tool (L65)
### _tool (L65)
`def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict`
_(ai)_ Builds a JSON Schema tool definition dict for the AI model.
- called by: <module>
### _system (L98)
`def _system(instructions: str | None) -> str`
Base reviewer prompt, augmented with repo-provided guidance when present (AC-27).
- called by: _prompt (L111), baseline (L245)
### _prompt (L111)
`def _prompt( diff: str, static_findings: list[Finding], codemap: str | None, instructions: str | None ) -> tuple[str, str]`
_(ai)_ Constructs the system prompt and user message containing the diff, static findings, codemap, and custom instructions.
- calls: _system (L98)
- called by: run (L170)
### _to_findings (L124)
`def _to_findings(items: list[dict], model: str) -> list[Finding]`
_(ai)_ Converts raw AI response items into Finding instances, tagging each with the model name.
- calls: Finding (src/open_review/findings.py:23)
- called by: baseline (L245), run (L170)
### _max_steps (L144)
`def _max_steps() -> int`
_(ai)_ Returns the maximum number of assistant–tool call steps from the OPEN_REVIEW_MAX_STEPS env var.
- called by: run (L170)
### _parse_args (L151)
`def _parse_args(raw: str | None) -> dict`
_(ai)_ Parses the AI's raw text arguments (or JSON) into a dict, handling markdown fences.
- called by: run (L170)
### _assistant_message (L158)
`def _assistant_message(msg) -> dict`
_(ai)_ Wraps a message in the assistant role for the conversation history.
- called by: run (L170)
### run (L170)
`def run( diff: str, static_findings: list[Finding], codemap: str | None, instructions: str | None, repo: str, ) -> list[Finding]`
_(ai)_ Orchestrates the AI review loop: sends diff+findings+codemap+instructions to the model and collects Findings.
- calls: _assistant_message (L158), _max_steps (L144), _parse_args (L151), _prompt (L111), _to_findings (L124), apply (src/open_review/cascade.py:147), chat (src/open_review/router.py:56), is_configured (src/open_review/router.py:18), run_action (src/open_review/toolbox.py:188)
- called by: _run (src/open_review/cli.py:67)
### _read_batches (L223)
`def _read_batches(files: list[str], repo: str, budget: int = 20000)`
Group files into batches under a char budget — fewer, bounded calls.
- called by: baseline (L245)
### baseline (L245)
`def baseline( files: list[str], codemap: str | None, instructions: str | None, repo: str ) -> list[Finding]`
Full-repo baseline sweep (Spec §Baseline; AC-29, AC-31).
- calls: _read_batches (L223), _system (L98), _to_findings (L124), apply (src/open_review/cascade.py:147), call_tool (src/open_review/router.py:32), is_configured (src/open_review/router.py:18)
- called by: main (src/open_review/cli.py:79)

## src/open_review/cascade.py
- imports: .errors, .findings, openai, os, router, sys
- module vars: STAGES (L23), _ADJUDICATION_STAGES (L26), _VERIFY (L32), _SYSTEM (L41), VERDICT_TOOL (L54)
### stage_models (L85)
`def stage_models() -> dict[str, str | None]`
Resolve the per-stage model from env; None means the stage is skipped (AC-14).
- called by: apply (L147)
### _code_context (L94)
`def _code_context(f: Finding, repo: str, ctx: int = 12) -> str`
The source lines around a finding (cited line marked `>>`), so the judge can verify it
- called by: _catalog (L108)
### _catalog (L108)
`def _catalog(active: list[Finding], repo: str) -> str`
_(ai)_ Formats a numbered catalog of active findings with severity, location, message, and optional code context.
- calls: _code_context (L94)
- called by: adjudicate (L117)
### adjudicate (L117)
`def adjudicate(stage: str, model: str, findings: list[Finding], repo: str = ".") -> list[Finding]`
Keep/drop/re-grade the active findings against the real code; dropped ones are retained
- calls: _catalog (L108), call_tool (src/open_review/router.py:32)
- called by: apply (L147)
### apply (L147)
`def apply(findings: list[Finding], repo: str = ".") -> list[Finding]`
Run the evaluate then judge adjudication stages if their models are configured.
- calls: adjudicate (L117), stage_models (L85)
- called by: baseline (src/open_review/ai.py:245), run (src/open_review/ai.py:170)

## src/open_review/cli.py
- imports: .errors, .findings, ai, argparse, codemap, config, diff, instructions, report, static, sys
- module vars: _FAIL_ON (L18)
- module-level calls: main (L79)
### build_parser (L21)
`def build_parser() -> argparse.ArgumentParser`
_(ai)_ Builds the CLI argument parser with all open‑review options.
- called by: main (L79)
### _run (L67)
`def _run(args: argparse.Namespace) -> int`
_(ai)_ Executes the main review workflow from parsed CLI arguments.
- calls: changed_files (src/open_review/diff.py:34), load (src/open_review/instructions.py:17), read (src/open_review/codemap.py:723), report (src/open_review/report.py:19), resolve_base (src/open_review/diff.py:11), run (src/open_review/ai.py:170), run (src/open_review/static.py:176), unified_diff (src/open_review/diff.py:29)
- called by: main (L79)
### main (L79)
`def main(argv: list[str] | None = None) -> int`
_(ai)_ Entry point: parses argv and dispatches to _run.
- calls: _run (L67), _source_files (src/open_review/codemap.py:112), baseline (src/open_review/ai.py:245), build_parser (L21), changed_files (src/open_review/diff.py:34), commit (src/open_review/codemap.py:733), dump (src/open_review/findings.py:41), generate (src/open_review/codemap.py:635), load (src/open_review/findings.py:46), load (src/open_review/instructions.py:17), report (src/open_review/report.py:19), resolve_base (src/open_review/diff.py:11), run (src/open_review/static.py:176), write (src/open_review/codemap.py:716)
- called by: <module>

## src/open_review/codemap.py
- imports: ast, collections, json, openai, os, re, router, shutil, subprocess, sys
- module vars: CODEMAP_PATH (L29), _AI_PREFIX (L32), _DESCRIBE_SYSTEM (L34), _DESCRIBE_TOOL (L39), _LANGS (L64), _CTAGS_ONLY_EXT (L75), _SKIP_KINDS (L84), _VAR_KINDS (L86), _CALLABLE_KINDS (L87), _TYPE_KINDS (L90), _SLASH (L95), _DOC_MARKERS (L96), _CALL_PATTERNS (L109), _JS_FROM (L371)
### _source_files (L112)
`def _source_files(repo: str) -> list[str]`
_(ai)_ Lists all source files in a repo recognized by pygments.
- called by: _call_graph (L475), _ctags (L148), _repo_langs (L120), generate (L635), main (src/open_review/cli.py:79)
### _repo_langs (L120)
`def _repo_langs(repo: str) -> set[str]`
ast-grep language ids present (for call/import extraction) — excludes ctags-only langs.
- calls: _source_files (L112)
- called by: _calls (L431), _imports (L406)
### _astgrep (L125)
`def _astgrep(pattern: str, lang: str, repo: str) -> list[dict]`
Raw ast-grep JSON matches (empty list on any failure — fail-soft, never crash the map).
- called by: _calls (L431), _imports (L406)
### _meta (L137)
`def _meta(it: dict, var: str) -> str | None`
_(ai)_ Safely retrieves a string value from a dict, returning None if missing or non‑string.
- called by: _calls (L431)
### _relf (L141)
`def _relf(it: dict, root: str) -> str | None`
Relative path of an ast-grep match, or None if it carries no file (guards the empty-path
- called by: _calls (L431), _imports (L406)
### _ctags (L148)
`def _ctags(repo: str) -> list[dict]`
All ctags tags over the tracked source files — the multi-language symbol layer (name,
- calls: _source_files (L112)
- called by: _call_graph (L475), _module_vars (L235), _symbols (L192), generate (L635)
### _symbols_from (L173)
`def _symbols_from(tags: list[dict]) -> dict[str, list[tuple[str, int]]]`
_(ai)_ Converts ctags tag entries into a dict mapping filenames to (symbol, line) pairs.
- called by: _call_graph (L475), _symbols (L192), generate (L635)
### _symbols (L192)
`def _symbols(repo: str) -> dict[str, list[tuple[str, int]]]`
{relpath: [(symbol, line), ...]} for every source file — the complete symbol set,
- calls: _ctags (L148), _symbols_from (L173)
### _franges_from (L198)
`def _franges_from(tags: list[dict]) -> dict[str, list[tuple[str, int, int]]]`
{relpath: [(func, start, end), ...]} — to attribute each call to its enclosing function.
- called by: _call_graph (L475)
### _module_vars_from (L211)
`def _module_vars_from(tags: list[dict], repo: str) -> dict[str, list[tuple[str, int]]]`
{relpath: [(name, line), ...]} for module/package-level variables and constants. ctags
- called by: _module_vars (L235), generate (L635)
### _module_vars (L235)
`def _module_vars(repo: str) -> dict[str, list[tuple[str, int]]]`
_(ai)_ Collects top‑level module variables/functions/classes from Python files using stdlib ast.
- calls: _ctags (L148), _module_vars_from (L211)
### _declaration (L239)
`def _declaration(src_lines: list[str], start_1based: int) -> str`
The declaration text as written (any language): the def line(s), joined across a
- called by: _details (L303)
### _comment_above (L273)
`def _comment_above(src_lines: list[str], start_1based: int, ext: str) -> str`
First meaningful line of the doc-comment block directly above a declaration (`//`,
- called by: _details (L303)
### _details (L303)
`def _details( repo: str, syms: dict[str, list[tuple[str, int]]], ctag_sigs: dict[tuple[str, str], str] | None = None, ) -> dict[tuple[str, str], tuple[str, str]]`
{(relpath, name): (signature, doc_first_line)} across languages, fully static:
- calls: _comment_above (L273), _declaration (L239)
- called by: generate (L635)
### _py_import_names (L341)
`def _py_import_names(text: str) -> list[tuple[str, str]]`
Parse a Python import statement into (local_name, module) pairs. `import a.b` binds
- called by: _imports (L406)
### _js_import_names (L374)
`def _js_import_names(text: str) -> list[tuple[str, str]]`
Parse a JS/TS `import ... from 'mod'` into (local_name, module) pairs: default,
- called by: _imports (L406)
### _imports (L406)
`def _imports(repo: str) -> dict[str, dict[str, str]]`
{relpath: {local_name: module}} — Python and JS/TS precise; other languages best-effort
- calls: _astgrep (L125), _js_import_names (L374), _py_import_names (L341), _relf (L141), _repo_langs (L120)
- called by: _call_graph (L475), generate (L635)
### _calls (L431)
`def _calls(repo: str) -> dict[str, list[tuple[str, int]]]`
{relpath: [(callee_text, line), ...]} — every call expression, callee as written. Runs
- calls: _astgrep (L125), _meta (L137), _relf (L141), _repo_langs (L120)
- called by: _call_graph (L475)
### _basename (L455)
`def _basename(rel: str) -> str`
_(ai)_ Returns the base filename (without directory) from a relative path.
- called by: _resolve_module (L459)
### _resolve_module (L459)
`def _resolve_module(mod: str, from_file: str, files: list[str]) -> str | None`
Map an import module string to a repo file by basename (last dotted component),
- calls: _basename (L455)
- called by: resolve (L504)
### _call_graph (L475)
`def _call_graph(repo: str, tags: list[dict] | None = None) -> dict[tuple[str, str], dict[str, set]]`
Resolve every call edge to a repo symbol via the import table (see AC-16c ladder) and
- calls: _calls (L431), _ctags (L148), _franges_from (L198), _imports (L406), _source_files (L112), _symbols_from (L173), enclosing (L496), resolve (L504)
- called by: generate (L635)
### enclosing (L496)
`def enclosing(f: str, line: int) -> str`
_(ai)_ Returns the enclosing definition name for a given file and line number using ctags.
- called by: _call_graph (L475)
### resolve (L504)
`def resolve(f: str, callee: str) -> tuple[str, str] | None`
_(ai)_ Resolves a callee name to a (file, symbol) pair using ctags and import analysis.
- calls: _resolve_module (L459)
- called by: _call_graph (L475)
### _prior_ai (L536)
`def _prior_ai(text: str) -> dict[tuple[str, str], tuple[str, str]]`
Parse AI descriptions out of a previously committed codemap → {(file, name): (sig, desc)}.
- called by: generate (L635)
### _describe (L553)
`def _describe( repo: str, syms: dict[str, list[tuple[str, int]]], details: dict[tuple[str, str], tuple[str, str]], prior: dict[tuple[str, str], tuple[str, str]], ranges: dict[tuple[str, str], tuple[int, int]], budget: int = 15000, ) -> dict[tuple[str, str], str]`
Opt-in AI one-liners for symbols with **no author doc** (AC-16g). Reuses a prior
- calls: body (L591), call_tool (src/open_review/router.py:32), is_configured (src/open_review/router.py:18)
- called by: generate (L635)
### body (L591)
`def body(f: str, name: str) -> str`
_(ai)_ Returns the source body for a given symbol name in a file, cached and truncated to 3000 chars.
- called by: _describe (L553)
### generate (L635)
`def generate(repo: str, describe: bool = False) -> str`
Complete deterministic, multi-language structural map: every source file, symbol (with
- calls: _call_graph (L475), _ctags (L148), _describe (L553), _details (L303), _imports (L406), _module_vars_from (L211), _prior_ai (L536), _source_files (L112), _symbols_from (L173), edges (L663), read (L723), ref (L655)
- called by: main (src/open_review/cli.py:79)
### ref (L655)
`def ref(target: tuple[str, str], cur: str) -> str`
A navigable reference: `name (L12)` same-file, `name (path/to.py:12)` cross-file.
- called by: edges (L663), generate (L635)
### edges (L663)
`def edges(node: dict, cur: str) -> str`
_(ai)_ Formats a call‑graph edge list string starting from a given node.
- calls: ref (L655)
- called by: generate (L635)
### write (L716)
`def write(repo: str, content: str) -> None`
_(ai)_ Writes the generated codemap content to .open_review/codemap.txt in the repo.
- called by: main (src/open_review/cli.py:79)
### read (L723)
`def read(repo: str) -> str | None`
Return the committed codemap contents, or None if absent/empty (AC-17).
- called by: _run (src/open_review/cli.py:67), generate (L635)
### commit (L733)
`def commit(repo: str, message: str = "docs: update open-review codemap [skip ci]") -> None`
Commit the codemap with a CI-skip marker to avoid recursive runs (AC-18).
- called by: main (src/open_review/cli.py:79)

## src/open_review/diff.py
- imports: .errors, os, subprocess
### resolve_base (L11)
`def resolve_base(explicit: str | None) -> str`
--base, else the CI target branch (as a remote-tracking ref), else origin/main.
- called by: _run (src/open_review/cli.py:67), main (src/open_review/cli.py:79)
### _git (L22)
`def _git(*args: str) -> str`
_(ai)_ Runs a git command in the current directory and returns its stdout.
- calls: OperationalError (src/open_review/errors.py:6)
- called by: changed_files (L34), unified_diff (L29)
### unified_diff (L29)
`def unified_diff(base: str) -> str`
Changes introduced on HEAD since its merge-base with `base` (PR-style diff).
- calls: _git (L22)
- called by: _run (src/open_review/cli.py:67)
### changed_files (L34)
`def changed_files(base: str) -> list[str]`
_(ai)_ Returns a list of files changed relative to a given base ref.
- calls: _git (L22)
- called by: _run (src/open_review/cli.py:67), main (src/open_review/cli.py:79)

## src/open_review/emitters.py
- imports: .findings, hashlib
- module vars: _GH_LEVEL (L14), _SARIF_LEVEL (L15), _GITLAB_SEVERITY (L16)
### github_annotations (L19)
`def github_annotations(findings: list[Finding]) -> None`
Emit GitHub Actions workflow-command annotations (AC-20).
- called by: report (src/open_review/report.py:19)
### sarif (L26)
`def sarif(findings: list[Finding]) -> dict`
A SARIF 2.1.0 document (AC-22).
- called by: report (src/open_review/report.py:19)
### gitlab (L51)
`def gitlab(findings: list[Finding]) -> list[dict]`
A GitLab Code Quality report (AC-21).
- called by: report (src/open_review/report.py:19)

## src/open_review/errors.py
### OperationalError (L6)
`class OperationalError(Exception)`
open-review itself could not run — bad config, unresolved base ref, a
- called by: _git (src/open_review/diff.py:22), call_tool (src/open_review/router.py:32), chat (src/open_review/router.py:56)

## src/open_review/findings.py
- imports: dataclasses, json, pathlib
- module vars: SEVERITIES (L18), LEVEL (L19)
### Finding (L23)
`class Finding`
_(ai)_ Data class representing a review finding with file, line, severity, and message.
- called by: _astgrep_rules (src/open_review/static.py:94), _f (tests/test_cascade.py:7), _f (tests/test_emitters.py:10), _f (tests/test_findings.py:13), _f (tests/test_report.py:7), _gitleaks (src/open_review/static.py:130), _ruff (src/open_review/static.py:35), _shellcheck (src/open_review/static.py:65), _to_findings (src/open_review/ai.py:124), load (L46), test_static_findings_folded_into_prompt (tests/test_ai.py:38)
### __post_init__ (L34)
`def __post_init__(self) -> None`
_(ai)_ Post‑init hook that validates and normalizes Finding fields (e.g. strips prefixes from file paths).
### dump (L41)
`def dump(findings: list[Finding], path: str | Path) -> None`
Serialize findings to a JSON array (the inter-stage artifact).
- called by: main (src/open_review/cli.py:79), test_roundtrip (tests/test_findings.py:19)
### load (L46)
`def load(path: str | Path) -> list[Finding]`
Load findings from a JSON array produced by :func:`dump`.
- calls: Finding (L23)
- called by: main (src/open_review/cli.py:79), test_roundtrip (tests/test_findings.py:19)
### worst (L51)
`def worst(findings: list[Finding]) -> int`
Highest severity level present, or -1 for an empty list (used by the gate).
- called by: report (src/open_review/report.py:19), test_worst_of_empty_is_negative (tests/test_findings.py:30), test_worst_picks_highest_severity (tests/test_findings.py:34)

## src/open_review/instructions.py
- imports: os, subprocess
- module vars: INSTRUCTIONS_PATH (L14)
### load (L17)
`def load(base: str, untrusted: bool = False) -> str | None`
Return the repo instructions, or None if absent/empty.
- called by: _run (src/open_review/cli.py:67), main (src/open_review/cli.py:79)

## src/open_review/report.py
- imports: .findings, emitters, json, os, pathlib
### report (L19)
`def report( findings: list[Finding], fail_on: str = "warning", sarif: str | None = None, gitlab_report: str | None = None, ) -> int`
Print findings, emit CI outputs, and return the process exit code.
- calls: github_annotations (src/open_review/emitters.py:19), gitlab (src/open_review/emitters.py:51), sarif (src/open_review/emitters.py:26), worst (src/open_review/findings.py:51)
- called by: _run (src/open_review/cli.py:67), main (src/open_review/cli.py:79)

## src/open_review/router.py
- imports: .errors, json, openai, os
### is_configured (L18)
`def is_configured() -> bool`
True iff a router API key is present — else the AI stage is skipped (AC-3).
- called by: _describe (src/open_review/codemap.py:553), baseline (src/open_review/ai.py:245), run (src/open_review/ai.py:170)
### _max_tokens (L23)
`def _max_tokens() -> int`
Output-token cap, configurable via `LLM_MAX_TOKENS`. Small/cheap models (e.g. a cheap
- called by: call_tool (L32), chat (L56)
### call_tool (L32)
`def call_tool(model: str, system: str, user: str, tool: dict) -> dict | None`
One forced-tool-call round trip; returns the parsed tool arguments, or None
- calls: OperationalError (src/open_review/errors.py:6), _max_tokens (L23)
- called by: _describe (src/open_review/codemap.py:553), adjudicate (src/open_review/cascade.py:117), baseline (src/open_review/ai.py:245)
### chat (L56)
`def chat(model: str, messages: list, tools: list)`
One tool-enabled turn (tool_choice=auto); returns the assistant message so the
- calls: OperationalError (src/open_review/errors.py:6), _max_tokens (L23)
- called by: run (src/open_review/ai.py:170)

## src/open_review/static.py
- imports: .findings, glob, json, os, shutil, subprocess, sys, tempfile
- module vars: _RULES_DIR (L25), _SHELLCHECK_SEVERITY (L26), _ASTGREP_SEVERITY (L27)
### _rel (L30)
`def _rel(path: str, root: str) -> str`
Normalize a tool-reported path (absolute or already-relative) to repo-relative.
- called by: _ruff (L35), _shellcheck (L65)
### _ruff (L35)
`def _ruff(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs Ruff linter on the given files and returns Findings.
- calls: Finding (src/open_review/findings.py:23), _rel (L30)
- called by: run (L176)
### _shellcheck (L65)
`def _shellcheck(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs ShellCheck on the given shell files and returns Findings.
- calls: Finding (src/open_review/findings.py:23), _rel (L30)
- called by: run (L176)
### _astgrep_rules (L94)
`def _astgrep_rules(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs ast‑grep rules on the given files and returns Findings.
- calls: Finding (src/open_review/findings.py:23)
- called by: run (L176)
### _gitleaks (L130)
`def _gitleaks(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs Gitleaks on the given files and returns Findings for detected secrets.
- calls: Finding (src/open_review/findings.py:23)
- called by: run (L176)
### run (L176)
`def run(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs all static analysis tools (ruff, shellcheck, ast‑grep, gitleaks) on the given files.
- calls: _astgrep_rules (L94), _gitleaks (L130), _ruff (L35), _shellcheck (L65)
- called by: _run (src/open_review/cli.py:67), main (src/open_review/cli.py:79)

## src/open_review/toolbox.py
- imports: json, os, re, shutil, subprocess
- module vars: ALLOWLIST (L24), _IDENT (L34), _MAX_OUTPUT (L35), _LANGS (L38), _DEF_PATTERNS (L45)
### _scrubbed_env (L56)
`def _scrubbed_env() -> dict[str, str]`
``env -i``-style: only what tools need to run, never a secret (AC-10).
- called by: _run (L61)
### _run (L61)
`def _run(cmd: list[str], cwd: str = ".") -> subprocess.CompletedProcess`
_(ai)_ Runs a subprocess command with the given working directory and returns the CompletedProcess.
- calls: _scrubbed_env (L56)
- called by: _astgrep (L91), _blame (L156), _grep (L132)
### _ident (L65)
`def _ident(symbol: object) -> str`
_(ai)_ Returns the full dotted name of a symbol (e.g. module.Class.method).
- called by: run_action (L188)
### _safe_path (L71)
`def _safe_path(repo: str, path: str) -> str`
_(ai)_ Resolves a user‑supplied path safely within the repo root, rejecting traversal attempts.
- called by: _blame (L156), _list_tests_for (L175), _read_range (L162)
### _repo_langs (L79)
`def _repo_langs(repo: str) -> set[str]`
_(ai)_ Detects the set of programming languages present in the repo (toolbox version).
- called by: _find_callers (L141), _show_definition (L148)
### _astgrep (L91)
`def _astgrep(pattern: str, lang: str, repo: str) -> list[str]`
_(ai)_ Runs ast‑grep with a given pattern and language, returning matching line strings.
- calls: _run (L61)
- called by: _find_callers (L141), _show_definition (L148)
### _py_grep (L107)
`def _py_grep(pattern: str, repo: str) -> str`
Read-only, no-subprocess fallback when the ripgrep binary isn't present.
- called by: _grep (L132)
### _grep (L132)
`def _grep(pattern: str, repo: str) -> str`
_(ai)_ Runs grep (rg) with the given pattern in the repo and returns matches.
- calls: _py_grep (L107), _run (L61)
- called by: run_action (L188)
### _find_callers (L141)
`def _find_callers(symbol: str, repo: str) -> str`
_(ai)_ Finds callers of a symbol using ctags and grep.
- calls: _astgrep (L91), _repo_langs (L79)
- called by: run_action (L188)
### _show_definition (L148)
`def _show_definition(symbol: str, repo: str) -> str`
_(ai)_ Shows the definition (source lines) of a symbol using ctags.
- calls: _astgrep (L91), _repo_langs (L79)
- called by: run_action (L188)
### _blame (L156)
`def _blame(path: str, line: int, repo: str) -> str`
_(ai)_ Returns git blame info for a specific line in a file.
- calls: _run (L61), _safe_path (L71)
- called by: run_action (L188)
### _read_range (L162)
`def _read_range(path: str, start: int, end: int, repo: str) -> str`
_(ai)_ Reads a range of lines from a file safely within the repo.
- calls: _safe_path (L71)
- called by: run_action (L188)
### _list_tests_for (L175)
`def _list_tests_for(path: str, repo: str) -> str`
_(ai)_ List test files for a given path in a repository.
- calls: _safe_path (L71)
- called by: run_action (L188)
### run_action (L188)
`def run_action(name: str, args: dict, repo: str = ".") -> str`
Validate against ALLOWLIST + confinement, execute read-only, return a string (AC-9).
- calls: _blame (L156), _find_callers (L141), _grep (L132), _ident (L65), _list_tests_for (L175), _read_range (L162), _show_definition (L148)
- called by: run (src/open_review/ai.py:170)

## tests/conftest.py
- imports: http.server, json, pytest, subprocess, threading
- module vars: _DEFAULT_REPORT (L37)
### git_repo (L16)
`def git_repo(tmp_path)`
Temp git repo with a base commit and a change on HEAD. Returns (path, base_sha).
- calls: g (L19)
### g (L19)
`def g(*args)`
_(ai)_ Helper fixture returning a URL path by joining args.
- called by: git_repo (L16)
### fake_router (L47)
`def fake_router()`
Fake OpenAI-compatible server serving a scripted queue of tool calls.
### Handler (L57)
`class Handler(BaseHTTPRequestHandler)`
_(ai)_ Fake HTTP request handler for test server stubs.
### log_message (L58)
`def log_message(self, *a)`
_(ai)_ Silence log messages in the test handler.
### do_POST (L61)
`def do_POST(self)`
_(ai)_ Handle POST requests for test HTTP routing.
### control (L82)
`def control(payload)`
_(ai)_ Dispatch a control payload to the fake router.
### script (L85)
`def script(*specs)`
_(ai)_ Register route specs with the fake router.

## tests/test_ai.py
- imports: open_review, open_review.findings
### _env (L7)
`def _env(monkeypatch, base_url, model="fake-model")`
_(ai)_ Create environment for AI tests with a given base URL and model.
- called by: <module> (tests/test_baseline.py), test_ai_run_parses_findings_from_tool_call (L15), test_loop_caps_at_max_steps (L63), test_loop_investigates_then_reports (L47)
### test_ai_run_parses_findings_from_tool_call (L15)
`def test_ai_run_parses_findings_from_tool_call(fake_router, monkeypatch)`
_(ai)_ Verify AI run parses findings from a tool-call response.
- calls: _env (L7)
### test_ai_run_skips_without_key (L31)
`def test_ai_run_skips_without_key(monkeypatch, capsys)`
_(ai)_ Ensure AI run exits gracefully when no API key is set.
### test_static_findings_folded_into_prompt (L38)
`def test_static_findings_folded_into_prompt()`
AC-8: static findings are handed to the model as 'already found' signal.
- calls: Finding (src/open_review/findings.py:23)
### test_loop_investigates_then_reports (L47)
`def test_loop_investigates_then_reports(fake_router, tmp_path, monkeypatch)`
AC-11/AC-9: the agent may call toolbox actions before reporting findings.
- calls: _env (L7)
### test_loop_caps_at_max_steps (L63)
`def test_loop_caps_at_max_steps(fake_router, tmp_path, monkeypatch)`
AC-11: a model that never calls report is bounded by MAX_STEPS.
- calls: _env (L7)

## tests/test_cascade.py
- imports: open_review, open_review.findings
### _f (L7)
`def _f(msg, line, sev="warning")`
_(ai)_ Build a finding dict for cascade tests.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_cascade_adjudicator_sees_the_code (L20), test_cascade_collapses_without_stage_models (L11)
### test_cascade_collapses_without_stage_models (L11)
`def test_cascade_collapses_without_stage_models(monkeypatch)`
AC-14: with no evaluate/judge model set, findings pass through untouched.
- calls: _f (L7)
### test_cascade_adjudicator_sees_the_code (L20)
`def test_cascade_adjudicator_sees_the_code(tmp_path, monkeypatch)`
Anti-false-positive: the judge receives the real code at each finding's location, and a
- calls: _f (L7)
### test_cascade_evaluate_drops_and_retains (L34)
`def test_cascade_evaluate_drops_and_retains(fake_router, tmp_path, monkeypatch)`
AC-13/AC-15: evaluate adjudicates the candidates; a dropped finding is kept + tagged.

## tests/test_cli_run.py
- imports: open_review, subprocess
### test_run_end_to_end_gates_on_warning (L8)
`def test_run_end_to_end_gates_on_warning(git_repo, fake_router, monkeypatch, capsys)`
_(ai)_ End-to-end test that run gates on a warning-level finding.
### test_run_config_error_missing_base_url_exits_2 (L22)
`def test_run_config_error_missing_base_url_exits_2(git_repo, monkeypatch)`
_(ai)_ Test that missing base_url in config exits with code 2.
### test_run_reports_static_findings (L32)
`def test_run_reports_static_findings(tmp_path, monkeypatch, capsys)`
`run` wires the static stage: a secret in the changed file surfaces even with AI off.
- calls: g (L34)
### g (L34)
`def g(*a)`
_(ai)_ Helper fixture building URL paths in CLI run tests.
- called by: test_run_reports_static_findings (L32)

## tests/test_codemap.py
- imports: open_review, os, re, subprocess
### _git (L10)
`def _git(tmp, *a)`
_(ai)_ Run a git command inside a temporary repo.
- called by: _init_repo (L14), test_codemap_ai_descriptions_opt_in_and_iterate (L150), test_codemap_c_call_graph (L177), test_codemap_declaration_keeps_cpp_scope_operator (L209), test_codemap_doc_comment_preserves_content_chars (L220), test_codemap_enrichment_is_multilanguage (L121), test_codemap_is_complete (L23), test_codemap_is_human_navigable (L104), test_codemap_js_import_resolution (L194), test_codemap_lists_every_source_file (L247), test_codemap_marks_ambiguous_not_guessed (L71), test_codemap_module_vars_not_locals (L88), test_codemap_powershell_and_batch (L231), test_codemap_resolves_call_graph (L50)
### _init_repo (L14)
`def _init_repo(tmp)`
_(ai)_ Initialize a temporary git repository for testing.
- calls: _git (L10)
- called by: test_codemap_commit_has_skip_ci (L273), test_codemap_fork_does_not_commit (L286)
### test_codemap_is_complete (L23)
`def test_codemap_is_complete(tmp_path, monkeypatch)`
AC-16b: every symbol ast-grep finds appears in the map (matches-zero guarded).
- calls: _git (L10)
### test_codemap_resolves_call_graph (L50)
`def test_codemap_resolves_call_graph(tmp_path, monkeypatch)`
AC-16c: cross-module call edges resolve via imports, deterministically, both ways.
- calls: _git (L10)
### test_codemap_marks_ambiguous_not_guessed (L71)
`def test_codemap_marks_ambiguous_not_guessed(tmp_path, monkeypatch)`
AC-16c: a bare name shared by two files, neither local nor imported, is marked, not guessed.
- calls: _git (L10)
### test_codemap_module_vars_not_locals (L88)
`def test_codemap_module_vars_not_locals(tmp_path, monkeypatch)`
AC-16d: module-level variables are listed; assignments inside functions are not.
- calls: _git (L10)
### test_codemap_is_human_navigable (L104)
`def test_codemap_is_human_navigable(tmp_path, monkeypatch)`
AC-16e: signatures, the author's own docstring, and located edges — a human can read it.
- calls: _git (L10)
### test_codemap_enrichment_is_multilanguage (L121)
`def test_codemap_enrichment_is_multilanguage(tmp_path, monkeypatch)`
AC-16e: signatures, doc-comments, and module vars work for every language, not just Python.
- calls: _git (L10)
### test_codemap_ai_descriptions_opt_in_and_iterate (L150)
`def test_codemap_ai_descriptions_opt_in_and_iterate(fake_router, tmp_path, monkeypatch)`
AC-16g: --describe adds AI one-liners for *undocumented* symbols; iterate reuses an
- calls: _git (L10)
### test_codemap_c_call_graph (L177)
`def test_codemap_c_call_graph(tmp_path, monkeypatch)`
AC-16c: C call edges resolve despite C's declarator ambiguity (call-context patterns).
- calls: _git (L10)
### test_codemap_js_import_resolution (L194)
`def test_codemap_js_import_resolution(tmp_path, monkeypatch)`
AC-16c: a TS/JS call resolves cross-file via `import { x } from './mod'`.
- calls: _git (L10)
### test_codemap_declaration_keeps_cpp_scope_operator (L209)
`def test_codemap_declaration_keeps_cpp_scope_operator(tmp_path, monkeypatch)`
Regression (baseline-found): the `::` scope operator must not truncate the signature.
- calls: _git (L10)
### test_codemap_doc_comment_preserves_content_chars (L220)
`def test_codemap_doc_comment_preserves_content_chars(tmp_path, monkeypatch)`
Regression (baseline-found): only the comment prefix is stripped, never content chars.
- calls: _git (L10)
### test_codemap_powershell_and_batch (L231)
`def test_codemap_powershell_and_batch(tmp_path, monkeypatch)`
AC-16f: PowerShell + Batch are ctags-only languages (no ast-grep) — symbols still mapped.
- calls: _git (L10)
### test_codemap_lists_every_source_file (L247)
`def test_codemap_lists_every_source_file(tmp_path, monkeypatch)`
_(ai)_ Verify codemap lists every source file in the repo.
- calls: _git (L10)
### test_codemap_read_and_folded_into_prompt (L260)
`def test_codemap_read_and_folded_into_prompt(tmp_path, monkeypatch)`
AC-17: a committed codemap is fed to the reviewer as architectural context.
### test_codemap_commit_has_skip_ci (L273)
`def test_codemap_commit_has_skip_ci(tmp_path, monkeypatch)`
AC-18: an opt-in commit carries a CI-skip marker.
- calls: _init_repo (L14)
### test_codemap_fork_does_not_commit (L286)
`def test_codemap_fork_does_not_commit(tmp_path, monkeypatch)`
AC-19: an untrusted/fork PR generates the map but never commits it.
- calls: _init_repo (L14)

## tests/test_diff.py
- imports: open_review
### test_unified_diff_contains_the_change (L6)
`def test_unified_diff_contains_the_change(git_repo, monkeypatch)`
_(ai)_ Check that unified diff output includes the expected change.
### test_changed_files_lists_the_file (L13)
`def test_changed_files_lists_the_file(git_repo, monkeypatch)`
_(ai)_ Confirm changed-files listing contains the modified file.
### test_resolve_base_explicit_wins (L19)
`def test_resolve_base_explicit_wins(monkeypatch)`
_(ai)_ Test that an explicit base ref overrides other sources.
### test_resolve_base_from_github_env (L24)
`def test_resolve_base_from_github_env(monkeypatch)`
_(ai)_ Test resolve_base picks up GITHUB_BASE_REF from environment.
### test_resolve_base_from_gitlab_env (L30)
`def test_resolve_base_from_gitlab_env(monkeypatch)`
_(ai)_ Test resolve_base picks up GitLab CI merge-base variables.
### test_resolve_base_fallback (L36)
`def test_resolve_base_fallback(monkeypatch)`
_(ai)_ Test resolve_base fallback when no CI env is present.

## tests/test_emitters.py
- imports: json, open_review, open_review.findings
### _f (L10)
`def _f(sev, file="a.py", line=1)`
_(ai)_ Build a finding for emitter tests.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_github_annotation_format (L30), test_gitlab_code_quality_shape (L22), test_report_emits_github_annotations_in_actions (L45), test_report_plain_stdout_without_ci (L51), test_report_writes_sarif_and_gitlab (L37), test_sarif_2_1_0_shape (L14)
### test_sarif_2_1_0_shape (L14)
`def test_sarif_2_1_0_shape()`
_(ai)_ Validate the JSON structure of a SARIF 2.1.0 report.
- calls: _f (L10)
### test_gitlab_code_quality_shape (L22)
`def test_gitlab_code_quality_shape()`
_(ai)_ Validate the JSON structure of a GitLab Code Quality report.
- calls: _f (L10)
### test_github_annotation_format (L30)
`def test_github_annotation_format(capsys)`
_(ai)_ Check GitHub Actions annotation output format.
- calls: _f (L10)
### test_report_writes_sarif_and_gitlab (L37)
`def test_report_writes_sarif_and_gitlab(tmp_path)`
_(ai)_ Verify report writes both SARIF and GitLab artifacts to disk.
- calls: _f (L10)
### test_report_emits_github_annotations_in_actions (L45)
`def test_report_emits_github_annotations_in_actions(monkeypatch, capsys)`
_(ai)_ Ensure GitHub annotations are emitted when GITHUB_ACTIONS is set.
- calls: _f (L10)
### test_report_plain_stdout_without_ci (L51)
`def test_report_plain_stdout_without_ci(monkeypatch, capsys)`
_(ai)_ Ensure plain-text output is used when no CI environment is detected.
- calls: _f (L10)

## tests/test_findings.py
- imports: open_review.findings, pytest
### _f (L13)
`def _f(**kw) -> Finding`
_(ai)_ Create a Finding instance with given keyword arguments.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_invalid_severity_rejected (L38), test_roundtrip (L19), test_worst_picks_highest_severity (L34)
### test_roundtrip (L19)
`def test_roundtrip(tmp_path)`
_(ai)_ Test full serialize/deserialize roundtrip of findings.
- calls: _f (L13), dump (src/open_review/findings.py:41), load (src/open_review/findings.py:46)
### test_level_ordering (L26)
`def test_level_ordering()`
_(ai)_ Verify severity levels are ordered correctly.
### test_worst_of_empty_is_negative (L30)
`def test_worst_of_empty_is_negative()`
_(ai)_ Check that worst severity of an empty collection is negative.
- calls: worst (src/open_review/findings.py:51)
### test_worst_picks_highest_severity (L34)
`def test_worst_picks_highest_severity()`
_(ai)_ Confirm worst() picks the highest severity from a list.
- calls: _f (L13), worst (src/open_review/findings.py:51)
### test_invalid_severity_rejected (L38)
`def test_invalid_severity_rejected()`
_(ai)_ Ensure constructing a Finding with invalid severity raises.
- calls: _f (L13)

## tests/test_instructions.py
- imports: open_review, subprocess
### _repo_with_instructions (L8)
`def _repo_with_instructions(tmp_path, base_text, head_text)`
_(ai)_ Create a temporary repo with open-review instruction files.
- calls: g (L9)
- called by: test_load_working_tree (L35), test_untrusted_uses_base_version (L41)
### g (L9)
`def g(*a)`
_(ai)_ Helper fixture building URL paths for instruction tests.
- called by: _repo_with_instructions (L8)
### test_absent_is_none (L29)
`def test_absent_is_none(git_repo, monkeypatch)`
_(ai)_ Test that instructions return None when no file is present.
### test_load_working_tree (L35)
`def test_load_working_tree(tmp_path, monkeypatch)`
_(ai)_ Test loading open-review instructions from working tree.
- calls: _repo_with_instructions (L8)
### test_untrusted_uses_base_version (L41)
`def test_untrusted_uses_base_version(tmp_path, monkeypatch)`
_(ai)_ Test that untrusted mode falls back to the base (hardcoded) instructions version.
- calls: _repo_with_instructions (L8)
### test_untrusted_rejects_hostile_base (L47)
`def test_untrusted_rejects_hostile_base(tmp_path, monkeypatch)`
A base ref that isn't a plain ref can't be coerced into a git option / other revision.
### test_system_injects_instructions (L55)
`def test_system_injects_instructions()`
_(ai)_ Test that a system prompt injects custom instructions into the agent.
### test_system_none_is_base_prompt (L61)
`def test_system_none_is_base_prompt()`
_(ai)_ Test that a None system prompt falls back to the base (hardcoded) prompt.

## tests/test_report.py
- imports: open_review, open_review.findings
### _f (L7)
`def _f(sev, file="a.py", line=1)`
_(ai)_ Helper creating a Finding-like tuple with severity, file, and line.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_dropped_findings_shown_separately_and_excluded_from_gate (L38), test_exit_one_on_warning_default (L21), test_fail_on_error_ignores_warning_but_not_error (L33), test_fail_on_off_forces_zero (L29), test_note_below_default_warning_is_zero (L25), test_prints_each_finding (L11)
### test_prints_each_finding (L11)
`def test_prints_each_finding(capsys)`
_(ai)_ Test that the report function prints each finding to stdout.
- calls: _f (L7)
### test_exit_zero_when_clean (L17)
`def test_exit_zero_when_clean()`
_(ai)_ Test exit code is 0 when there are no findings.
### test_exit_one_on_warning_default (L21)
`def test_exit_one_on_warning_default()`
_(ai)_ Test default exit code is 1 when warnings are present.
- calls: _f (L7)
### test_note_below_default_warning_is_zero (L25)
`def test_note_below_default_warning_is_zero()`
_(ai)_ Test findings below the default warning threshold produce exit code 0.
- calls: _f (L7)
### test_fail_on_off_forces_zero (L29)
`def test_fail_on_off_forces_zero()`
_(ai)_ Test that --fail-on=off forces exit code 0 regardless of findings.
- calls: _f (L7)
### test_fail_on_error_ignores_warning_but_not_error (L33)
`def test_fail_on_error_ignores_warning_but_not_error()`
_(ai)_ Test that --fail-on=error only triggers on error-level findings, ignoring warnings.
- calls: _f (L7)
### test_dropped_findings_shown_separately_and_excluded_from_gate (L38)
`def test_dropped_findings_shown_separately_and_excluded_from_gate(capsys)`
AC-15: dropped findings render in a discarded section and don't affect the gate.
- calls: _f (L7)

## tests/test_static.py
- imports: open_review, shutil
### test_ruff_findings_normalized (L11)
`def test_ruff_findings_normalized(tmp_path, monkeypatch)`
_(ai)_ Test that ruff findings are normalized into the expected Finding format.
### test_shellcheck_findings_normalized (L19)
`def test_shellcheck_findings_normalized(tmp_path, monkeypatch)`
_(ai)_ Test that shellcheck findings are normalized into the expected Finding format.
### test_astgrep_vendored_rule_flags_pattern (L27)
`def test_astgrep_vendored_rule_flags_pattern(tmp_path, monkeypatch)`
_(ai)_ Test that ast-grep with a vendored rule flags a pattern match.
### test_gitleaks_detects_secret (L35)
`def test_gitleaks_detects_secret(tmp_path, monkeypatch)`
_(ai)_ Test that gitleaks detects hardcoded secrets in a repo.
### test_missing_tools_skip_with_notice (L43)
`def test_missing_tools_skip_with_notice(monkeypatch, capsys)`
_(ai)_ Test that missing external tools are skipped gracefully with a notice.

## tests/test_toolbox.py
- imports: open_review, subprocess
### test_allowlist_rejects_unknown_action (L9)
`def test_allowlist_rejects_unknown_action()`
_(ai)_ Test that the allowlist rejects tool calls for unknown actions.
### test_scrubbed_env_excludes_secrets (L14)
`def test_scrubbed_env_excludes_secrets(monkeypatch)`
_(ai)_ Test that scrubbed environment variables exclude secret keys.
### test_executor_spawns_without_secrets (L23)
`def test_executor_spawns_without_secrets(tmp_path, monkeypatch)`
_(ai)_ Test that the executor process spawns without secret environment variables.
### spy (L30)
`def spy(cmd, **kw)`
_(ai)_ Spy/helper that captures subprocess command invocations.
### test_find_callers_cross_language (L40)
`def test_find_callers_cross_language(tmp_path, monkeypatch)`
_(ai)_ Test that find-callers works across different languages in a temp repo.
### test_find_callers_rejects_bad_symbol (L48)
`def test_find_callers_rejects_bad_symbol(tmp_path, monkeypatch)`
_(ai)_ Test that find-callers rejects malformed or unknown symbol names.
### test_read_range_confined_to_repo (L54)
`def test_read_range_confined_to_repo(tmp_path, monkeypatch)`
_(ai)_ Test that read-range operations are confined within the repository root.
