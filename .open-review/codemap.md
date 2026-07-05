# open-review codemap

_Deterministic multi-language structural map — every source file, symbol (signature + its own description), import, navigable call edge, and module-level variable. Symbols via universal-ctags; call edges via ast-grep. Generated; do not hand-edit._

## src/open_review/__init__.py
- module vars: __version__ (L1)

## src/open_review/ai.py
- imports: .errors, .findings, cascade, concurrent.futures, json, openai, os, router, sys, toolbox
- module vars: SYSTEM (L24), REPORT_TOOL (L32), TOOLBOX_TOOLS (L82)
- module-level calls: _tool (L66)
### _tool (L66)
`def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict`
_(ai)_ Builds a function-calling tool descriptor dict for the LLM API, given name, description, JSON schema properties, and required fields.
- called by: <module>
### _system (L99)
`def _system(instructions: str | None) -> str`
Base reviewer prompt, augmented with repo-provided guidance when present (AC-27).
- called by: _prompt (L112), baseline (L265)
### _prompt (L112)
`def _prompt( diff: str, static_findings: list[Finding], codemap: str | None, instructions: str | None ) -> tuple[str, str]`
_(ai)_ Assembles the system and user prompt strings for the AI review, optionally including codemap context and static-finding dedup instructions.
- calls: _system (L99)
- called by: run (L171)
### _to_findings (L125)
`def _to_findings(items: list[dict], model: str) -> list[Finding]`
_(ai)_ Validates and converts raw JSON AI output items into typed Finding objects, dropping malformed entries with a stderr warning.
- calls: Finding (src/open_review/findings.py:23)
- called by: _review_batch (L249), run (L171)
### _max_steps (L145)
`def _max_steps() -> int`
_(ai)_ Returns the maximum number of AI chat-turn steps allowed, reading from the OPEN_REVIEW_MAX_STEPS env var with a default of 20.
- called by: run (L171)
### _parse_args (L152)
`def _parse_args(raw: str | None) -> dict`
_(ai)_ Parses a JSON string into a dict, returning empty dict on None or parse failure.
- called by: run (L171)
### _assistant_message (L159)
`def _assistant_message(msg) -> dict`
_(ai)_ Converts an LLM assistant message with tool calls into the chat-history dict format the router expects.
- called by: run (L171)
### run (L171)
`def run( diff: str, static_findings: list[Finding], codemap: str | None, instructions: str | None, repo: str, ) -> list[Finding]`
_(ai)_ Orchestrates the multi-step AI review: builds prompt, iterates tool calls until a report is produced, then runs cascade deduplication against the repo.
- calls: _assistant_message (L159), _max_steps (L145), _parse_args (L152), _prompt (L112), _to_findings (L125), apply (src/open_review/cascade.py:147), chat (src/open_review/router.py:221), is_configured (src/open_review/router.py:19), run_action (src/open_review/toolbox.py:191)
- called by: _run (src/open_review/cli.py:72)
### _read_batches (L227)
`def _read_batches(files: list[str], repo: str, budget: int = 20000)`
Group files into batches under a char budget — fewer, bounded calls.
- called by: baseline (L265)
### _review_batch (L249)
`def _review_batch(batch: list[tuple[str, str]], idx: int, total: int, model: str, prefix: str) -> list[Finding]`
One forced-`report` call for a file batch. A failed or truncated call skips (returns [])
- calls: _to_findings (L125), call_tool (src/open_review/router.py:178)
- called by: baseline (L265)
### baseline (L265)
`def baseline( files: list[str], codemap: str | None, instructions: str | None, repo: str ) -> list[Finding]`
Full-repo baseline sweep (Spec §Baseline; AC-29, AC-31).
- calls: _read_batches (L227), _review_batch (L249), _system (L99), apply (src/open_review/cascade.py:147), is_configured (src/open_review/router.py:19)
- called by: main (src/open_review/cli.py:84)

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
_(ai)_ Formats a list of active findings into a human-readable catalog string with surrounding code context for each finding.
- calls: _code_context (L94)
- called by: adjudicate (L117)
### adjudicate (L117)
`def adjudicate(stage: str, model: str, findings: list[Finding], repo: str = ".") -> list[Finding]`
Keep/drop/re-grade the active findings against the real code; dropped ones are retained
- calls: _catalog (L108), call_tool (src/open_review/router.py:178)
- called by: apply (L147)
### apply (L147)
`def apply(findings: list[Finding], repo: str = ".") -> list[Finding]`
Run the evaluate then judge adjudication stages if their models are configured.
- calls: adjudicate (L117), stage_models (L85)
- called by: baseline (src/open_review/ai.py:265), run (src/open_review/ai.py:171)

## src/open_review/cli.py
- imports: .errors, .findings, ai, argparse, codemap, config, diff, instructions, report, static, sys
- module vars: _FAIL_ON (L18)
- module-level calls: main (L84)
### build_parser (L21)
`def build_parser() -> argparse.ArgumentParser`
_(ai)_ Creates and returns the ArgumentParser with all subcommands (run, static, ai, report, codemap, baseline) and their options.
- called by: main (L84)
### _run (L72)
`def _run(args: argparse.Namespace) -> int`
_(ai)_ Implements the `run` subcommand: resolves base, gathers diff and static findings, runs AI review with codemap and instructions, then reports results.
- calls: changed_files (src/open_review/diff.py:34), load (src/open_review/instructions.py:17), read (src/open_review/codemap.py:756), report (src/open_review/report.py:19), resolve_base (src/open_review/diff.py:11), run (src/open_review/ai.py:171), run (src/open_review/static.py:180), unified_diff (src/open_review/diff.py:29)
- called by: main (L84)
### main (L84)
`def main(argv: list[str] | None = None) -> int`
_(ai)_ CLI entry point that dispatches to the appropriate subcommand handler (run, static, codemap, baseline, report) and translates errors to exit codes.
- calls: _run (L72), baseline (src/open_review/ai.py:265), build_parser (L21), changed_files (src/open_review/diff.py:34), commit (src/open_review/codemap.py:766), dump (src/open_review/findings.py:41), excludes (src/open_review/config.py:18), generate (src/open_review/codemap.py:649), is_excluded (src/open_review/config.py:30), load (src/open_review/findings.py:46), load (src/open_review/instructions.py:17), report (src/open_review/report.py:19), resolve_base (src/open_review/diff.py:11), run (src/open_review/static.py:180), write (src/open_review/codemap.py:749)
- called by: <module>

## src/open_review/codemap.py
- imports: ast, collections, json, openai, os, re, router, shutil, subprocess, sys
- module vars: CODEMAP_PATH (L29), _CMD_TIMEOUT (L33), _AI_PREFIX (L35), _DESCRIBE_SYSTEM (L37), _DESCRIBE_TOOL (L42), _LANGS (L67), _CTAGS_ONLY_EXT (L78), _SKIP_KINDS (L87), _VAR_KINDS (L89), _CALLABLE_KINDS (L90), _TYPE_KINDS (L93), _SLASH (L98), _DOC_MARKERS (L99), _CALL_PATTERNS (L112), source_files (L124), _JS_FROM (L385)
### _source_files (L115)
`def _source_files(repo: str) -> list[str]`
_(ai)_ Lists all tracked source files in the repo by matching git-ls-files output against known programming-language extensions.
- called by: _call_graph (L489), _ctags (L158), _repo_langs (L127), generate (L649)
### _repo_langs (L127)
`def _repo_langs(repo: str) -> set[str]`
ast-grep language ids present (for call/import extraction) — excludes ctags-only langs.
- calls: _source_files (L115)
- called by: _calls (L445), _imports (L420)
### _astgrep (L132)
`def _astgrep(pattern: str, lang: str, repo: str) -> list[dict]`
Raw ast-grep JSON matches (empty list on any failure — fail-soft, never crash the map).
- called by: _calls (L445), _imports (L420)
### _meta (L147)
`def _meta(it: dict, var: str) -> str | None`
_(ai)_ Extracts a text value for a given variable key from a ctags entry's metaVariables dict, or returns None.
- called by: _calls (L445)
### _relf (L151)
`def _relf(it: dict, root: str) -> str | None`
Relative path of an ast-grep match, or None if it carries no file (guards the empty-path
- called by: _calls (L445), _imports (L420)
### _ctags (L158)
`def _ctags(repo: str) -> list[dict]`
All ctags tags over the tracked source files — the multi-language symbol layer (name,
- calls: _source_files (L115)
- called by: _call_graph (L489), _module_vars (L249), _symbols (L206), generate (L649)
### _symbols_from (L187)
`def _symbols_from(tags: list[dict]) -> dict[str, list[tuple[str, int]]]`
_(ai)_ Filters ctags tag entries to keep only callables and types, deduplicates by path/name/line, and groups them by file.
- called by: _call_graph (L489), _symbols (L206), generate (L649)
### _symbols (L206)
`def _symbols(repo: str) -> dict[str, list[tuple[str, int]]]`
{relpath: [(symbol, line), ...]} for every source file — the complete symbol set,
- calls: _ctags (L158), _symbols_from (L187)
### _franges_from (L212)
`def _franges_from(tags: list[dict]) -> dict[str, list[tuple[str, int, int]]]`
{relpath: [(func, start, end), ...]} — to attribute each call to its enclosing function.
- called by: _call_graph (L489)
### _module_vars_from (L225)
`def _module_vars_from(tags: list[dict], repo: str) -> dict[str, list[tuple[str, int]]]`
{relpath: [(name, line), ...]} for module/package-level variables and constants. ctags
- called by: _module_vars (L249), generate (L649)
### _module_vars (L249)
`def _module_vars(repo: str) -> dict[str, list[tuple[str, int]]]`
_(ai)_ Runs ctags and returns per-file module-level variable definitions (constants, module-scope names).
- calls: _ctags (L158), _module_vars_from (L225)
### _declaration (L253)
`def _declaration(src_lines: list[str], start_1based: int) -> str`
The declaration text as written (any language): the def line(s), joined across a
- called by: _details (L317)
### _comment_above (L287)
`def _comment_above(src_lines: list[str], start_1based: int, ext: str) -> str`
First meaningful line of the doc-comment block directly above a declaration (`//`,
- called by: _details (L317)
### _details (L317)
`def _details( repo: str, syms: dict[str, list[tuple[str, int]]], ctag_sigs: dict[tuple[str, str], str] | None = None, ) -> dict[tuple[str, str], tuple[str, str]]`
{(relpath, name): (signature, doc_first_line)} across languages, fully static:
- calls: _comment_above (L287), _declaration (L253)
- called by: generate (L649)
### _py_import_names (L355)
`def _py_import_names(text: str) -> list[tuple[str, str]]`
Parse a Python import statement into (local_name, module) pairs. `import a.b` binds
- called by: _imports (L420)
### _js_import_names (L388)
`def _js_import_names(text: str) -> list[tuple[str, str]]`
Parse a JS/TS `import ... from 'mod'` into (local_name, module) pairs: default,
- called by: _imports (L420)
### _imports (L420)
`def _imports(repo: str) -> dict[str, dict[str, str]]`
{relpath: {local_name: module}} — Python and JS/TS precise; other languages best-effort
- calls: _astgrep (L132), _js_import_names (L388), _py_import_names (L355), _relf (L151), _repo_langs (L127)
- called by: _call_graph (L489), generate (L649)
### _calls (L445)
`def _calls(repo: str) -> dict[str, list[tuple[str, int]]]`
{relpath: [(callee_text, line), ...]} — every call expression, callee as written. Runs
- calls: _astgrep (L132), _meta (L147), _relf (L151), _repo_langs (L127)
- called by: _call_graph (L489)
### _basename (L469)
`def _basename(rel: str) -> str`
_(ai)_ Returns the file stem (basename without extension) of a relative path.
- called by: _resolve_module (L473), short (L679)
### _resolve_module (L473)
`def _resolve_module(mod: str, from_file: str, files: list[str]) -> str | None`
Map an import module string to a repo file by basename (last dotted component),
- calls: _basename (L469)
- called by: resolve (L518)
### _call_graph (L489)
`def _call_graph(repo: str, tags: list[dict] | None = None) -> dict[tuple[str, str], dict[str, set]]`
Resolve every call edge to a repo symbol via the import table (see AC-16c ladder) and
- calls: _calls (L445), _ctags (L158), _franges_from (L212), _imports (L420), _source_files (L115), _symbols_from (L187), enclosing (L510), resolve (L518)
- called by: generate (L649)
### enclosing (L510)
`def enclosing(f: str, line: int) -> str`
_(ai)_ Finds the nearest enclosing symbol (function/class) that contains the given line in a file, or returns '<module>'.
- called by: _call_graph (L489)
### resolve (L518)
`def resolve(f: str, callee: str) -> tuple[str, str] | None`
_(ai)_ Resolves a callee name to a (file, symbol) pair by checking locals, imports, and repo-wide uniqueness, or returns None if ambiguous or external.
- calls: _resolve_module (L473)
- called by: _call_graph (L489)
### _prior_ai (L550)
`def _prior_ai(text: str) -> dict[tuple[str, str], tuple[str, str]]`
Parse AI descriptions out of a previously committed codemap → {(file, name): (sig, desc)}.
- called by: generate (L649)
### _describe (L567)
`def _describe( repo: str, syms: dict[str, list[tuple[str, int]]], details: dict[tuple[str, str], tuple[str, str]], prior: dict[tuple[str, str], tuple[str, str]], ranges: dict[tuple[str, str], tuple[int, int]], budget: int = 15000, ) -> dict[tuple[str, str], str]`
Opt-in AI one-liners for symbols with **no author doc** (AC-16g). Reuses a prior
- calls: body (L605), call_tool (src/open_review/router.py:178), is_configured (src/open_review/router.py:19)
- called by: generate (L649)
### body (L605)
`def body(f: str, name: str) -> str`
_(ai)_ Retrieves the source code lines for a given file and function name from a cached dictionary, returning up to 3000 characters.
- called by: _describe (L567)
### generate (L649)
`def generate(repo: str, describe: bool = False, light: bool = False) -> str`
Complete deterministic, multi-language structural map: every source file, symbol (with
- calls: _call_graph (L489), _ctags (L158), _describe (L567), _details (L317), _imports (L420), _module_vars_from (L225), _prior_ai (L550), _source_files (L115), _symbols_from (L187), edges (L684), read (L756), ref (L671), short (L679)
- called by: main (src/open_review/cli.py:84)
### ref (L671)
`def ref(target: tuple[str, str], cur: str) -> str`
A navigable reference: `name (L12)` same-file, `name (path/to.py:12)` cross-file.
- called by: generate (L649)
### short (L679)
`def short(target: tuple[str, str], cur: str) -> str`
A compact reference (light mode): `name` same-file, `basename.name` cross-file.
- calls: _basename (L469)
- called by: generate (L649)
### edges (L684)
`def edges(node: dict, cur: str) -> str`
_(ai)_ Formats a node's outgoing call edges and ambiguous references as a comma-separated string for the code map.
- called by: generate (L649)
### write (L749)
`def write(repo: str, content: str) -> None`
_(ai)_ Writes the given content string to the .open-review/codemap file inside the repo directory.
- called by: main (src/open_review/cli.py:84)
### read (L756)
`def read(repo: str) -> str | None`
Return the committed codemap contents, or None if absent/empty (AC-17).
- called by: _run (src/open_review/cli.py:72), generate (L649)
### commit (L766)
`def commit(repo: str, message: str = "docs: update open-review codemap [skip ci]") -> None`
Commit the codemap with a CI-skip marker to avoid recursive runs (AC-18).
- called by: main (src/open_review/cli.py:84)

## src/open_review/config.py
- imports: fnmatch, os, tomllib
- module vars: CONFIG_PATH (L15)
### excludes (L18)
`def excludes(repo: str) -> list[str]`
_(ai)_ Loads the TOML config from .open-review.toml and returns the list of exclude patterns, or an empty list if the file is missing or invalid.
- called by: main (src/open_review/cli.py:84)
### is_excluded (L30)
`def is_excluded(relpath: str, user_patterns: list[str]) -> bool`
_(ai)_ Returns True if the relative file path matches any of the user-supplied glob patterns.
- called by: main (src/open_review/cli.py:84)

## src/open_review/diff.py
- imports: .errors, os, subprocess
### resolve_base (L11)
`def resolve_base(explicit: str | None) -> str`
--base, else the CI target branch (as a remote-tracking ref), else origin/main.
- called by: _run (src/open_review/cli.py:72), main (src/open_review/cli.py:84)
### _git (L22)
`def _git(*args: str) -> str`
_(ai)_ Runs a git command with the given arguments and returns stdout, raising OperationalError on failure.
- calls: OperationalError (src/open_review/errors.py:6)
- called by: changed_files (L34), unified_diff (L29)
### unified_diff (L29)
`def unified_diff(base: str) -> str`
Changes introduced on HEAD since its merge-base with `base` (PR-style diff).
- calls: _git (L22)
- called by: _run (src/open_review/cli.py:72)
### changed_files (L34)
`def changed_files(base: str) -> list[str]`
_(ai)_ Returns a list of file paths changed between the given base branch and HEAD.
- calls: _git (L22)
- called by: _run (src/open_review/cli.py:72), main (src/open_review/cli.py:84)

## src/open_review/emitters.py
- imports: .findings, hashlib
- module vars: _GH_LEVEL (L14), _SARIF_LEVEL (L15), _GITLAB_SEVERITY (L16)
### _gh_escape (L19)
`def _gh_escape(s: str, prop: bool = False) -> str`
Escape a value for a GitHub Actions workflow command. Message data escapes `%`, CR and
- called by: github_annotations (L29)
### github_annotations (L29)
`def github_annotations(findings: list[Finding]) -> None`
Emit GitHub Actions workflow-command annotations (AC-20).
- calls: _gh_escape (L19)
- called by: report (src/open_review/report.py:19)
### sarif (L36)
`def sarif(findings: list[Finding]) -> dict`
A SARIF 2.1.0 document (AC-22).
- called by: report (src/open_review/report.py:19)
### gitlab (L61)
`def gitlab(findings: list[Finding]) -> list[dict]`
A GitLab Code Quality report (AC-21).
- called by: report (src/open_review/report.py:19)

## src/open_review/errors.py
### OperationalError (L6)
`class OperationalError(Exception)`
open-review itself could not run — bad config, unresolved base ref, a
- called by: _git (src/open_review/diff.py:22), call_tool (src/open_review/router.py:178), chat (src/open_review/router.py:221)

## src/open_review/findings.py
- imports: dataclasses, json, pathlib
- module vars: SEVERITIES (L18), LEVEL (L19)
### Finding (L23)
`class Finding`
_(ai)_ A dataclass representing a single code finding with file, line, severity, category, message, source, optional suggestion, and drop tracking fields.
- called by: _astgrep_rules (src/open_review/static.py:94), _f (tests/test_cascade.py:7), _f (tests/test_emitters.py:10), _f (tests/test_findings.py:13), _f (tests/test_report.py:7), _gitleaks (src/open_review/static.py:130), _ruff (src/open_review/static.py:35), _shellcheck (src/open_review/static.py:65), _to_findings (src/open_review/ai.py:125), load (L46), test_github_annotation_escapes_special_chars (tests/test_emitters.py:37), test_static_findings_folded_into_prompt (tests/test_ai.py:38)
### __post_init__ (L34)
`def __post_init__(self) -> None`
_(ai)_ Validates that the severity field is one of the allowed SEVERITIES after initialization.
### dump (L41)
`def dump(findings: list[Finding], path: str | Path) -> None`
Serialize findings to a JSON array (the inter-stage artifact).
- called by: main (src/open_review/cli.py:84), test_roundtrip (tests/test_findings.py:19)
### load (L46)
`def load(path: str | Path) -> list[Finding]`
Load findings from a JSON array produced by :func:`dump`.
- calls: Finding (L23)
- called by: main (src/open_review/cli.py:84), test_roundtrip (tests/test_findings.py:19)
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
- called by: _run (src/open_review/cli.py:72), main (src/open_review/cli.py:84)

## src/open_review/report.py
- imports: .findings, emitters, json, os, pathlib
### report (L19)
`def report( findings: list[Finding], fail_on: str = "warning", sarif: str | None = None, gitlab_report: str | None = None, ) -> int`
Print findings, emit CI outputs, and return the process exit code.
- calls: github_annotations (src/open_review/emitters.py:29), gitlab (src/open_review/emitters.py:61), sarif (src/open_review/emitters.py:36), worst (src/open_review/findings.py:51)
- called by: _run (src/open_review/cli.py:72), main (src/open_review/cli.py:84)

## src/open_review/router.py
- imports: .errors, json, openai, os, sys
- module vars: _REPAIR_SYSTEM (L153)
### is_configured (L19)
`def is_configured() -> bool`
True iff a router API key is present — else the AI stage is skipped (AC-3).
- called by: _describe (src/open_review/codemap.py:567), baseline (src/open_review/ai.py:265), run (src/open_review/ai.py:171)
### _max_tokens (L24)
`def _max_tokens() -> int`
Output-token cap, configurable via `LLM_MAX_TOKENS`. Small/cheap models (e.g. a cheap
- called by: call_tool (L178), chat (L221)
### _extra_body (L33)
`def _extra_body() -> dict`
OpenRouter provider routing, from human-friendly env:
- called by: call_tool (L178), chat (L221)
### _array_key (L54)
`def _array_key(tool: dict) -> str | None`
The name of the tool's array parameter (findings / verdicts / descriptions).
- called by: call_tool (L178)
### _close_partial (L60)
`def _close_partial(obj_text: str) -> dict | None`
Recover a truncated object (its closing `}` cut off) by keeping the complete top-level
- called by: _salvage (L90)
### _salvage (L90)
`def _salvage(raw: str, array_key: str) -> dict | None`
Best-effort recovery from truncated tool-call JSON: walk the result array and keep every
- calls: _close_partial (L60)
- called by: call_tool (L178)
### _log_cache (L138)
`def _log_cache(resp) -> None`
Surface provider-reported cached prompt tokens so cache reuse is visible in our own logs,
- called by: call_tool (L178), chat (L221)
### _ai_repair (L160)
`def _ai_repair(raw: str, tool: dict) -> dict | None`
Last-resort repair: hand the broken string to a cheap model whose forced tool schema
- calls: call_tool (L178)
- called by: call_tool (L178)
### call_tool (L178)
`def call_tool(model: str, system: str, user: str, tool: dict, repair: bool = True) -> dict | None`
One forced-tool-call round trip; returns the parsed tool arguments, or None
- calls: OperationalError (src/open_review/errors.py:6), _ai_repair (L160), _array_key (L54), _extra_body (L33), _log_cache (L138), _max_tokens (L24), _salvage (L90)
- called by: _ai_repair (L160), _describe (src/open_review/codemap.py:567), _review_batch (src/open_review/ai.py:249), adjudicate (src/open_review/cascade.py:117)
### chat (L221)
`def chat(model: str, messages: list, tools: list)`
One tool-enabled turn (tool_choice=auto); returns the assistant message so the
- calls: OperationalError (src/open_review/errors.py:6), _extra_body (L33), _log_cache (L138), _max_tokens (L24)
- called by: run (src/open_review/ai.py:171)

## src/open_review/static.py
- imports: .findings, glob, json, os, shutil, subprocess, sys, tempfile
- module vars: _RULES_DIR (L25), _SHELLCHECK_SEVERITY (L26), _ASTGREP_SEVERITY (L27)
### _rel (L30)
`def _rel(path: str, root: str) -> str`
Normalize a tool-reported path (absolute or already-relative) to repo-relative.
- called by: _ruff (L35), _shellcheck (L65)
### _ruff (L35)
`def _ruff(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs ruff check on Python files in the given list and returns a list of lint findings.
- calls: Finding (src/open_review/findings.py:23), _rel (L30)
- called by: run (L180)
### _shellcheck (L65)
`def _shellcheck(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs shellcheck on .sh/.bash files in the given list and returns a list of lint findings.
- calls: Finding (src/open_review/findings.py:23), _rel (L30)
- called by: run (L180)
### _astgrep_rules (L94)
`def _astgrep_rules(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs ast-grep scan using custom YAML rules on the given files and returns bug findings.
- calls: Finding (src/open_review/findings.py:23)
- called by: run (L180)
### _gitleaks (L130)
`def _gitleaks(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs gitleaks on the whole repo and returns security findings only for the given changed files.
- calls: Finding (src/open_review/findings.py:23)
- called by: run (L180)
### run (L180)
`def run(files: list[str], repo: str) -> list[Finding]`
_(ai)_ Runs all static analysis tools (ruff, shellcheck, ast-grep, gitleaks) on the changed files and returns combined findings.
- calls: _astgrep_rules (L94), _gitleaks (L130), _ruff (L35), _shellcheck (L65)
- called by: _run (src/open_review/cli.py:72), main (src/open_review/cli.py:84)

## src/open_review/toolbox.py
- imports: json, os, re, shutil, subprocess
- module vars: ALLOWLIST (L24), _IDENT (L34), _MAX_OUTPUT (L35), _LANGS (L38), _DEF_PATTERNS (L45)
### _scrubbed_env (L56)
`def _scrubbed_env() -> dict[str, str]`
``env -i``-style: only what tools need to run, never a secret (AC-10).
- called by: _run (L61)
### _run (L61)
`def _run(cmd: list[str], cwd: str = ".") -> subprocess.CompletedProcess`
_(ai)_ Runs a command with a scrubbed environment and returns the CompletedProcess result.
- calls: _scrubbed_env (L56)
- called by: _astgrep (L91), _blame (L159), _grep (L135)
### _ident (L65)
`def _ident(symbol: object) -> str`
_(ai)_ Validates that the argument is a string matching the identifier pattern or raises ValueError.
- called by: run_action (L191)
### _safe_path (L71)
`def _safe_path(repo: str, path: str) -> str`
_(ai)_ Resolves a path relative to the repo root and raises ValueError if it escapes the repo.
- called by: _blame (L159), _list_tests_for (L178), _read_range (L165)
### _repo_langs (L79)
`def _repo_langs(repo: str) -> set[str]`
_(ai)_ Walks the repo tree (skipping .git) and returns the set of programming language names found by file extension.
- called by: _find_callers (L144), _show_definition (L151)
### _astgrep (L91)
`def _astgrep(pattern: str, lang: str, repo: str) -> list[str]`
_(ai)_ Runs ast-grep to find AST matches for a pattern in a given language and returns formatted location: text lines.
- calls: _run (L61)
- called by: _find_callers (L144), _show_definition (L151)
### _py_grep (L110)
`def _py_grep(pattern: str, repo: str) -> str`
Read-only, no-subprocess fallback when the ripgrep binary isn't present.
- called by: _grep (L135)
### _grep (L135)
`def _grep(pattern: str, repo: str) -> str`
_(ai)_ Searches for a regex pattern in the repo using ripgrep (or a fallback Python grep) and returns up to 100 matches.
- calls: _py_grep (L110), _run (L61)
- called by: run_action (L191)
### _find_callers (L144)
`def _find_callers(symbol: str, repo: str) -> str`
_(ai)_ Finds all callers of a symbol across all detected languages in the repo using ast-grep.
- calls: _astgrep (L91), _repo_langs (L79)
- called by: run_action (L191)
### _show_definition (L151)
`def _show_definition(symbol: str, repo: str) -> str`
_(ai)_ Finds definitions of a symbol across all detected languages using language-specific AST patterns.
- calls: _astgrep (L91), _repo_langs (L79)
- called by: run_action (L191)
### _blame (L159)
`def _blame(path: str, line: int, repo: str) -> str`
_(ai)_ Runs git blame on a single line of a file and returns the blame line.
- calls: _run (L61), _safe_path (L71)
- called by: run_action (L191)
### _read_range (L165)
`def _read_range(path: str, start: int, end: int, repo: str) -> str`
_(ai)_ Reads and returns up to 400 lines from a file with line numbers, validating the path stays within the repo.
- calls: _safe_path (L71)
- called by: run_action (L191)
### _list_tests_for (L178)
`def _list_tests_for(path: str, repo: str) -> str`
_(ai)_ Lists test files whose name contains both 'test' and the stem of the given file path, walking the repo.
- calls: _safe_path (L71)
- called by: run_action (L191)
### run_action (L191)
`def run_action(name: str, args: dict, repo: str = ".") -> str`
Validate against ALLOWLIST + confinement, execute read-only, return a string (AC-9).
- calls: _blame (L159), _find_callers (L144), _grep (L135), _ident (L65), _list_tests_for (L178), _read_range (L165), _show_definition (L151)
- called by: run (src/open_review/ai.py:171)

## tests/conftest.py
- imports: http.server, json, pytest, subprocess, threading
- module vars: _DEFAULT_REPORT (L37)
### git_repo (L16)
`def git_repo(tmp_path)`
Temp git repo with a base commit and a change on HEAD. Returns (path, base_sha).
- calls: g (L19)
### g (L19)
`def g(*args)`
_(ai)_ Runs a git command with args in the temporary test fixture directory.
- called by: git_repo (L16)
### fake_router (L47)
`def fake_router()`
Fake OpenAI-compatible server serving a scripted queue of tool calls.
### Handler (L57)
`class Handler(BaseHTTPRequestHandler)`
_(ai)_ A minimal HTTP request handler that responds to POST with a fake OpenAI-like tool-call response from a queue of specs.
### log_message (L58)
`def log_message(self, *a)`
_(ai)_ Suppresses default HTTP request logging to keep test output clean.
### do_POST (L61)
`def do_POST(self)`
_(ai)_ HTTP POST handler that pops a canned tool-call spec from a queue and returns it as a fake OpenAI chat-completion response.
### control (L82)
`def control(payload)`
_(ai)_ Replaces the shared queue with a single "report" tool-call carrying the given payload dict.
### script (L85)
`def script(*specs)`
_(ai)_ Replaces the shared queue with an ordered list of tool-call specs parsed from positional arguments.

## tests/test_ai.py
- imports: open_review, open_review.findings
### _env (L7)
`def _env(monkeypatch, base_url, model="fake-model")`
_(ai)_ Sets required env vars (base URL, API key, model) and removes per-stage model overrides for test isolation.
- called by: test_ai_run_parses_findings_from_tool_call (L15), test_loop_caps_at_max_steps (L63), test_loop_investigates_then_reports (L47)
### test_ai_run_parses_findings_from_tool_call (L15)
`def test_ai_run_parses_findings_from_tool_call(fake_router, monkeypatch)`
_(ai)_ Verifies that ai.run() returns a parsed Finding from a tool-call response with correct fields and source.
- calls: _env (L7)
### test_ai_run_skips_without_key (L31)
`def test_ai_run_skips_without_key(monkeypatch, capsys)`
_(ai)_ Ensures ai.run() returns empty list and prints a skip message when LLM_API_KEY is absent.
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

## tests/test_baseline.py
- imports: json, open_review, os, subprocess
### _env (L10)
`def _env(monkeypatch, base_url, model="fake-model")`
_(ai)_ Same as _env for test_baseline.py: sets base URL, API key, model, and clears per-stage model overrides.
- called by: test_baseline_reviews_each_file_with_single_call (L18)
### test_baseline_reviews_each_file_with_single_call (L18)
`def test_baseline_reviews_each_file_with_single_call(fake_router, tmp_path, monkeypatch)`
AC-31: baseline uses one forced-report call per batch — no investigation loop.
- calls: _env (L10)
### test_baseline_command_writes_codemap_and_findings (L34)
`def test_baseline_command_writes_codemap_and_findings(tmp_path, monkeypatch)`
AC-29: baseline generates the whole codemap and writes an aggregated findings file.

## tests/test_cascade.py
- imports: open_review, open_review.findings
### _f (L7)
`def _f(msg, line, sev="warning")`
_(ai)_ Constructs a Finding with fixed file "a.py", given message, line, and optional severity.
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
_(ai)_ End-to-end test that a pipeline run finds the default warning and exits with code 1.
### test_run_config_error_missing_base_url_exits_2 (L22)
`def test_run_config_error_missing_base_url_exits_2(git_repo, monkeypatch)`
_(ai)_ Verifies that missing LLM_BASE_URL causes the CLI to exit with code 2.
### test_run_reports_static_findings (L32)
`def test_run_reports_static_findings(tmp_path, monkeypatch, capsys)`
`run` wires the static stage: a secret in the changed file surfaces even with AI off.
- calls: g (L34)
### g (L34)
`def g(*a)`
_(ai)_ Runs a git command inside tmp_path with check and captured output.
- called by: test_run_reports_static_findings (L32)

## tests/test_codemap.py
- imports: open_review, os, re, subprocess
### _git (L10)
`def _git(tmp, *a)`
_(ai)_ Runs a git command in the given tmp directory with check and captured output.
- called by: _init_repo (L14), test_codemap_ai_descriptions_opt_in_and_iterate (L150), test_codemap_c_call_graph (L177), test_codemap_declaration_keeps_cpp_scope_operator (L209), test_codemap_doc_comment_preserves_content_chars (L220), test_codemap_enrichment_is_multilanguage (L121), test_codemap_is_complete (L23), test_codemap_is_human_navigable (L104), test_codemap_js_import_resolution (L194), test_codemap_light_mode_compact_but_complete (L247), test_codemap_lists_every_source_file (L269), test_codemap_marks_ambiguous_not_guessed (L71), test_codemap_module_vars_not_locals (L88), test_codemap_powershell_and_batch (L231), test_codemap_resolves_call_graph (L50)
### _init_repo (L14)
`def _init_repo(tmp)`
_(ai)_ Initializes a Git repo with one commit containing a small Python file.
- calls: _git (L10)
- called by: test_codemap_commit_has_skip_ci (L295), test_codemap_fork_does_not_commit (L308)
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
### test_codemap_light_mode_compact_but_complete (L247)
`def test_codemap_light_mode_compact_but_complete(tmp_path, monkeypatch)`
AC-16h: light mode drops prose but keeps every symbol, signature, and call edge.
- calls: _git (L10)
### test_codemap_lists_every_source_file (L269)
`def test_codemap_lists_every_source_file(tmp_path, monkeypatch)`
_(ai)_ Checks that codemap.generate() includes every source file (including subdirectories) in its output.
- calls: _git (L10)
### test_codemap_read_and_folded_into_prompt (L282)
`def test_codemap_read_and_folded_into_prompt(tmp_path, monkeypatch)`
AC-17: a committed codemap is fed to the reviewer as architectural context.
### test_codemap_commit_has_skip_ci (L295)
`def test_codemap_commit_has_skip_ci(tmp_path, monkeypatch)`
AC-18: an opt-in commit carries a CI-skip marker.
- calls: _init_repo (L14)
### test_codemap_fork_does_not_commit (L308)
`def test_codemap_fork_does_not_commit(tmp_path, monkeypatch)`
AC-19: an untrusted/fork PR generates the map but never commits it.
- calls: _init_repo (L14)

## tests/test_config.py
- imports: open_review
### test_no_config_excludes_nothing (L6)
`def test_no_config_excludes_nothing(tmp_path, monkeypatch)`
_(ai)_ Verifies that with no config file, nothing is excluded and node_modules is not excluded by the tool.
### test_user_exclude_patterns (L14)
`def test_user_exclude_patterns(tmp_path, monkeypatch)`
_(ai)_ Checks that exclude patterns from .open-review/config.toml are respected by is_excluded().

## tests/test_diff.py
- imports: open_review
### test_unified_diff_contains_the_change (L6)
`def test_unified_diff_contains_the_change(git_repo, monkeypatch)`
_(ai)_ Verifies that the unified diff includes the changed file and the word "changed".
### test_changed_files_lists_the_file (L13)
`def test_changed_files_lists_the_file(git_repo, monkeypatch)`
_(ai)_ Checks that changed_files() returns a list containing the modified file name.
### test_resolve_base_explicit_wins (L19)
`def test_resolve_base_explicit_wins(monkeypatch)`
_(ai)_ Ensures resolve_base returns the explicit argument even when GITHUB_BASE_REF is set.
### test_resolve_base_from_github_env (L24)
`def test_resolve_base_from_github_env(monkeypatch)`
_(ai)_ Verifies that resolve_base uses origin/GITHUB_BASE_REF when the env var is present.
### test_resolve_base_from_gitlab_env (L30)
`def test_resolve_base_from_gitlab_env(monkeypatch)`
_(ai)_ Verifies that resolve_base uses origin/CI_MERGE_REQUEST_TARGET_BRANCH_NAME when set.
### test_resolve_base_fallback (L36)
`def test_resolve_base_fallback(monkeypatch)`
_(ai)_ Checks that resolve_base falls back to origin/main when no CI env var is set.

## tests/test_emitters.py
- imports: json, open_review, open_review.findings
### _f (L10)
`def _f(sev, file="a.py", line=1)`
_(ai)_ Helper that creates a Finding with given severity and optional file/line overrides.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_github_annotation_format (L30), test_gitlab_code_quality_shape (L22), test_report_emits_github_annotations_in_actions (L55), test_report_plain_stdout_without_ci (L61), test_report_writes_sarif_and_gitlab (L47), test_sarif_2_1_0_shape (L14)
### test_sarif_2_1_0_shape (L14)
`def test_sarif_2_1_0_shape()`
_(ai)_ Validates that the SARIF output has version 2.1.0 and the correct error level and line number.
- calls: _f (L10)
### test_gitlab_code_quality_shape (L22)
`def test_gitlab_code_quality_shape()`
_(ai)_ Validates that GitLab code quality output uses "minor" for warnings and includes path, line, and fingerprint.
- calls: _f (L10)
### test_github_annotation_format (L30)
`def test_github_annotation_format(capsys)`
_(ai)_ Checks that GitHub annotation output uses ::error and ::notice prefixes with correct file and line.
- calls: _f (L10)
### test_github_annotation_escapes_special_chars (L37)
`def test_github_annotation_escapes_special_chars(capsys)`
Regression (baseline-found): %, CR, LF in a message must be escaped or the annotation breaks.
- calls: Finding (src/open_review/findings.py:23)
### test_report_writes_sarif_and_gitlab (L47)
`def test_report_writes_sarif_and_gitlab(tmp_path)`
_(ai)_ Verifies that report() writes valid SARIF and GitLab JSON files to disk.
- calls: _f (L10)
### test_report_emits_github_annotations_in_actions (L55)
`def test_report_emits_github_annotations_in_actions(monkeypatch, capsys)`
_(ai)_ Ensures that GITHUB_ACTIONS=true triggers GitHub annotation output on stderr/stdout.
- calls: _f (L10)
### test_report_plain_stdout_without_ci (L61)
`def test_report_plain_stdout_without_ci(monkeypatch, capsys)`
_(ai)_ Ensures that without CI env, findings are printed in plain text without GitHub annotations.
- calls: _f (L10)

## tests/test_findings.py
- imports: open_review.findings, pytest
### _f (L13)
`def _f(**kw) -> Finding`
_(ai)_ Helper factory that builds a Finding with defaults overridden by keyword arguments.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_invalid_severity_rejected (L38), test_roundtrip (L19), test_worst_picks_highest_severity (L34)
### test_roundtrip (L19)
`def test_roundtrip(tmp_path)`
_(ai)_ Verifies that a list of findings round-trips correctly through dump() and load().
- calls: _f (L13), dump (src/open_review/findings.py:41), load (src/open_review/findings.py:46)
### test_level_ordering (L26)
`def test_level_ordering()`
_(ai)_ Asserts that the severity level ordering is note < warning < error.
### test_worst_of_empty_is_negative (L30)
`def test_worst_of_empty_is_negative()`
_(ai)_ Verifies that worst([]) returns -1 for an empty findings list.
- calls: worst (src/open_review/findings.py:51)
### test_worst_picks_highest_severity (L34)
`def test_worst_picks_highest_severity()`
_(ai)_ Checks that worst() returns the level value of the highest severity finding present.
- calls: _f (L13), worst (src/open_review/findings.py:51)
### test_invalid_severity_rejected (L38)
`def test_invalid_severity_rejected()`
_(ai)_ Verifies that constructing a Finding with an invalid severity raises ValueError.
- calls: _f (L13)

## tests/test_instructions.py
- imports: open_review, subprocess
### _repo_with_instructions (L8)
`def _repo_with_instructions(tmp_path, base_text, head_text)`
_(ai)_ Creates a repo with two commits, setting instructions.md in both, and returns the base commit hash.
- calls: g (L9)
- called by: test_load_working_tree (L35), test_untrusted_uses_base_version (L41)
### g (L9)
`def g(*a)`
_(ai)_ Runs a git command inside tmp_path with check and suppressed output.
- called by: _repo_with_instructions (L8)
### test_absent_is_none (L29)
`def test_absent_is_none(git_repo, monkeypatch)`
_(ai)_ Verifies that instructions.load() returns None when no instructions.md exists.
### test_load_working_tree (L35)
`def test_load_working_tree(tmp_path, monkeypatch)`
_(ai)_ Verifies that instructions.load() returns the working-tree version when untrusted=False.
- calls: _repo_with_instructions (L8)
### test_untrusted_uses_base_version (L41)
`def test_untrusted_uses_base_version(tmp_path, monkeypatch)`
_(ai)_ Verifies that instructions.load(..., untrusted=True) returns the base-commit version.
- calls: _repo_with_instructions (L8)
### test_untrusted_rejects_hostile_base (L47)
`def test_untrusted_rejects_hostile_base(tmp_path, monkeypatch)`
A base ref that isn't a plain ref can't be coerced into a git option / other revision.
### test_system_injects_instructions (L55)
`def test_system_injects_instructions()`
_(ai)_ Checks that _system() injects custom instructions into the prompt string.
### test_system_none_is_base_prompt (L61)
`def test_system_none_is_base_prompt()`
_(ai)_ Verifies that _system(None) returns the default SYSTEM prompt unchanged.

## tests/test_report.py
- imports: open_review, open_review.findings
### _f (L7)
`def _f(sev, file="a.py", line=1)`
_(ai)_ Helper that builds a Finding with given severity and optional file/line.
- calls: Finding (src/open_review/findings.py:23)
- called by: test_dropped_findings_shown_separately_and_excluded_from_gate (L38), test_exit_one_on_warning_default (L21), test_fail_on_error_ignores_warning_but_not_error (L33), test_fail_on_off_forces_zero (L29), test_note_below_default_warning_is_zero (L25), test_prints_each_finding (L11)
### test_prints_each_finding (L11)
`def test_prints_each_finding(capsys)`
_(ai)_ Verifies that report() prints each finding with severity, file:line, and source tag.
- calls: _f (L7)
### test_exit_zero_when_clean (L17)
`def test_exit_zero_when_clean()`
_(ai)_ Checks that report([]) returns exit code 0 when there are no findings.
### test_exit_one_on_warning_default (L21)
`def test_exit_one_on_warning_default()`
_(ai)_ Verifies that report() returns exit code 1 for a warning under the default threshold.
- calls: _f (L7)
### test_note_below_default_warning_is_zero (L25)
`def test_note_below_default_warning_is_zero()`
_(ai)_ Checks that a note-level finding does not trigger a non-zero exit code by default.
- calls: _f (L7)
### test_fail_on_off_forces_zero (L29)
`def test_fail_on_off_forces_zero()`
_(ai)_ Verifies that fail_on="off" forces exit code 0 regardless of finding severity.
- calls: _f (L7)
### test_fail_on_error_ignores_warning_but_not_error (L33)
`def test_fail_on_error_ignores_warning_but_not_error()`
_(ai)_ Verifies that fail_on="error" ignores warnings and only fails on errors.
- calls: _f (L7)
### test_dropped_findings_shown_separately_and_excluded_from_gate (L38)
`def test_dropped_findings_shown_separately_and_excluded_from_gate(capsys)`
AC-15: dropped findings render in a discarded section and don't affect the gate.
- calls: _f (L7)

## tests/test_router.py
- imports: open_review
### test_max_tokens_default_and_override (L6)
`def test_max_tokens_default_and_override(monkeypatch)`
_(ai)_ Verifies _max_tokens returns 8000 by default and respects a valid override, falling back on garbage.
### test_salvage_recovers_findings_from_truncated_array (L15)
`def test_salvage_recovers_findings_from_truncated_array()`
A truncated report keeps every complete finding plus the completed pairs of the cut-off one.
### test_salvage_single_object_missing_closing_brace (L28)
`def test_salvage_single_object_missing_closing_brace()`
One big object whose `}` is truncated still yields its complete key/value pairs.
### test_salvage_complete_array_missing_outer_brace (L37)
`def test_salvage_complete_array_missing_outer_brace()`
_(ai)_ Verifies _salvage can recover a JSON array missing only the closing brace.
### test_ai_repair_noop_without_model (L42)
`def test_ai_repair_noop_without_model(monkeypatch)`
The AI-repair fallback is off (returns None) unless a repair-capable model is configured.
### test_extra_body_provider_passthrough (L50)
`def test_extra_body_provider_passthrough(monkeypatch)`
_(ai)_ Tests that _extra_body() builds correct provider routing from LLM_PROVIDER and LLM_PROVIDER_FALLBACK env vars.

## tests/test_static.py
- imports: open_review, shutil
### test_ruff_findings_normalized (L11)
`def test_ruff_findings_normalized(tmp_path, monkeypatch)`
_(ai)_ Runs ruff on a small file with an unused import and verifies the finding is normalized to the expected format.
### test_shellcheck_findings_normalized (L19)
`def test_shellcheck_findings_normalized(tmp_path, monkeypatch)`
_(ai)_ Runs shellcheck on a shell script and confirms the finding is captured.
### test_astgrep_vendored_rule_flags_pattern (L27)
`def test_astgrep_vendored_rule_flags_pattern(tmp_path, monkeypatch)`
_(ai)_ Runs ast-grep with a vendored rule on a file containing eval() and checks the finding matches the expected line and source.
### test_gitleaks_detects_secret (L35)
`def test_gitleaks_detects_secret(tmp_path, monkeypatch)`
_(ai)_ Writes a fake AWS secret key to a file, runs gitleaks, and asserts the finding has severity error, category security.
### test_gitleaks_short_circuits_on_empty_files (L43)
`def test_gitleaks_short_circuits_on_empty_files(tmp_path, monkeypatch)`
Regression (baseline-found): empty changed-file set → no scan (like ruff/shellcheck),
### test_missing_tools_skip_with_notice (L51)
`def test_missing_tools_skip_with_notice(monkeypatch, capsys)`
_(ai)_ Monkeypatches shutil.which to return None for all tools and verifies run() returns empty and prints skip notices for each missing tool.

## tests/test_toolbox.py
- imports: open_review, subprocess
### test_allowlist_rejects_unknown_action (L9)
`def test_allowlist_rejects_unknown_action()`
_(ai)_ Ensures running the disallowed 'rm_rf' action returns an error message.
### test_scrubbed_env_excludes_secrets (L14)
`def test_scrubbed_env_excludes_secrets(monkeypatch)`
_(ai)_ Verifies that _scrubbed_env() strips secret-like env vars (LLM_API_KEY, GITHUB_TOKEN) but keeps PATH.
### test_executor_spawns_without_secrets (L23)
`def test_executor_spawns_without_secrets(tmp_path, monkeypatch)`
_(ai)_ Checks that run_action spawning subprocesses passes a scrubbed environment without LLM_API_KEY.
### spy (L30)
`def spy(cmd, **kw)`
_(ai)_ A test spy that captures the env kwarg from subprocess.run for later assertion.
### test_find_callers_cross_language (L40)
`def test_find_callers_cross_language(tmp_path, monkeypatch)`
_(ai)_ Verifies find_callers finds callers of 'foo' across both Python and JavaScript files.
### test_find_callers_rejects_bad_symbol (L48)
`def test_find_callers_rejects_bad_symbol(tmp_path, monkeypatch)`
_(ai)_ Verifies find_callers rejects a symbol containing a shell injection attempt.
### test_read_range_confined_to_repo (L54)
`def test_read_range_confined_to_repo(tmp_path, monkeypatch)`
_(ai)_ Checks that read_range reads lines inside the repo but returns an error for paths escaping via ../
