# Spec 01 — open-review

## Overview

`open-review` is a containerized, CI-agnostic, router-agnostic AI code reviewer.
You add it once to any CI service; on each pull/merge request it runs a
deterministic static scan plus an LLM investigation that pulls in the *cross-file*
context a diff-only reviewer misses, then reports findings via the exit code and
(where available) native CI annotations. It points at any OpenAI-compatible model
router (LiteLLM, OpenRouter, self-hosted) and never requires a hosted index or
external service of its own — the persistent codebase context lives in-repo as a
committed, human-readable codemap (git is the index).

The design thesis (validated against Greptile): the value is **context assembly
before the model**, not the model itself. We achieve cross-file recall through
on-demand agentic retrieval over a **vetted read-only toolbox**, not a hosted
graph.

## Acceptance criteria

Each criterion is verifiable by at least one automated test. Grouped by component;
`[Pn]` marks the delivery phase (see Phased delivery).

### Core loop `[P0]`
- **AC-1** Given a git repo with a diff against a base ref, when `open-review run`
  executes, then it produces a list of `Finding` objects conforming to the schema
  in §Technical design.
- **AC-2** Given `LLM_BASE_URL`, `LLM_API_KEY`, `MODEL` are set, when the AI stage
  runs, then it calls the OpenAI-compatible `/chat/completions` endpoint at
  `LLM_BASE_URL` with a forced tool call and parses the returned findings.
- **AC-3** Given no `LLM_API_KEY` is set, when `run` executes, then the AI stage is
  skipped with a printed notice (a degraded mode, not an operational error / not
  exit 2); the static stage still runs and its findings are reported and gated
  normally.
- **AC-4** Given findings, when the report step runs, then every active finding is
  printed to stdout as `SEVERITY file:line [source] message`, and dropped findings
  are printed in a separate "discarded" section (AC-15).
- **AC-5** Given findings and the gate (default `--fail-on warning`), when the report
  step runs, then the exit code is `0` when no active finding is at/above the
  threshold and `1` when at least one is — so a clean review is green and any real
  finding is visibly not-green. `--fail-on off` forces `0` (pure advisory);
  `--fail-on error` gates only on errors. Per-finding severity stays visible in
  stdout and annotations; operational failure exits `2` (distinct from findings).

### Static stage `[P1]`
- **AC-6** Given changed files, when the static stage runs, then bundled `semgrep`
  (`--config` per `SEMGREP_CONFIG`, default `auto`) and `gitleaks` are executed and
  their output is normalized into `Finding` objects with `source` set to the tool.
- **AC-7** Given a bundled scanner is absent from PATH, when the static stage runs,
  then it prints a skip notice for that scanner and continues (no crash, no silent
  omission).
- **AC-8** Given the AI stage runs after the static stage, when it builds its
  prompt, then the static findings are included as "already found — do not repeat"
  signal.

### AI investigation — vetted toolbox `[P2]`
- **AC-9** Given the agent requests a toolbox action, when the executor runs it,
  then only commands on the allowlist (`grep`, `find_callers`, `show_definition`,
  `blame`, `read_range`, `list_tests_for`) are executed; any other requested action
  is rejected with an error result returned to the model.
- **AC-10** Given a toolbox action, when the executor process is spawned, then it
  runs with a scrubbed environment (`env -i` + explicit allowlist) that does **not**
  contain `LLM_API_KEY` or any `*_TOKEN`/CI-secret variable.
- **AC-11** Given the agent loop, when it has run `MAX_STEPS` toolbox calls (default
  20) or exceeded the token/time budget, then the loop terminates and proceeds to
  report with whatever findings exist.
- **AC-12** Given a repo in any supported language, when the toolbox resolves
  `find_callers`/`show_definition`, then it uses `ast-grep` (grammars-as-data) and
  returns results without requiring that language's runtime to be installed.

### Cascade `[P4]`
- **AC-13** Given `MODEL_GENERATE`, `MODEL_EVALUATE`, `MODEL_JUDGE` are all set,
  when the AI stage runs, then findings pass through all three stages in order and
  the evaluate/judge stages receive only the candidate findings (not the full diff).
- **AC-14** Given only `MODEL` (the single-model form, aliasing `MODEL_GENERATE`) is
  set, when the AI stage runs, then only the generate stage runs (cascade collapses)
  and the result is unaffected by the unset stages.
- **AC-15** Given an evaluate/judge stage drops a finding, when the pipeline
  completes, then the finding is **retained** in the output, tagged with the stage
  that dropped it and the reason, and rendered in a separate "discarded" section;
  dropped findings are excluded from the exit-code gate. (First-iteration debugging
  aid — the `Finding` schema gains a `dropped_by` field at P4; may be tuned if the
  discard volume proves noisy.)

### Codemap `[P3]`
- **AC-16** Given `--emit-codemap` on the default branch, when `run` executes, then a
  **complete** structural map is generated at `.open-review/codemap.md`: every source
  file and every top-level symbol (functions, classes, methods) plus their
  import/dependency edges. Completeness is **deterministic** — extracted by
  ast-grep/tree-sitter over the whole repo, never an LLM summary (which would omit);
  LLM prose descriptions are layered on top, best-effort. **Hard criterion: the
  structural layer omits nothing, under any circumstances.** First-generation on large
  repos may be slow and the file large — accepted.
- **AC-16b** Given a generated codemap, when the completeness check runs, then a
  self-discovering test enumerates every symbol in the repo via ast-grep and asserts
  each appears in the map (with a matches-zero guard); a single missing symbol fails.
- **AC-17** Given a committed `.open-review/codemap.md` exists, when a PR review
  runs, then its contents are included as architectural context in the generate
  prompt.
- **AC-18** Given codemap commit is opt-in and enabled, when `run` commits the map,
  then the commit message contains a CI-skip marker (e.g. `[skip ci]`) to prevent
  recursive CI runs.
- **AC-19** Given a fork PR, when codemap emission is enabled, then the map is read
  but not committed (no push attempted against the fork branch).

### Repo instructions `[P0]`
- **AC-27** Given a committed `.open-review/instructions.md`, when a review runs, then
  its contents are injected as repo-level guidance into the reviewer's **system**
  prompt (before the diff); an absent or empty file is a no-op (not an error).
- **AC-28** Given a fork/untrusted PR, when instructions are loaded, then the
  **base-branch** version is used (`git show <base>:.open-review/instructions.md`),
  never the PR head's — so a PR cannot rewrite the reviewer that judges it.

### Report / CI-agnostic emitters `[P5]`
- **AC-20** Given `GITHUB_ACTIONS=true` and findings, when report runs, then each
  finding is also emitted as a GitHub workflow command
  (`::warning|error|notice file=…,line=…::…`).
- **AC-21** Given `GITLAB_CI=true` and `--gitlab-report PATH`, when report runs,
  then a valid GitLab Code Quality JSON report is written to PATH.
- **AC-22** Given `--sarif PATH`, when report runs, then a valid SARIF 2.1.0 file is
  written to PATH containing one result per finding.
- **AC-23** Given no recognized CI env, when report runs, then stdout + exit code
  still convey all findings (universal fallback).

### Base-ref resolution `[P5]`
- **AC-24** Given no `--base` flag, when `run` executes, then the base ref is
  resolved from CI env (`GITHUB_BASE_REF`, `CI_MERGE_REQUEST_TARGET_BRANCH_NAME`),
  falling back to `origin/main`.

### Packaging `[P5]`
- **AC-25** Given the published container, when built, then the default image
  bundles semgrep + gitleaks + ast-grep + ripgrep + ruff and contains **no** bundled
  language runtime (node/ruby/go toolchains).
- **AC-26** Given the built runtime image, when inspected, then it contains no
  network/exfiltration CLI tools (`curl`, `wget`, `nc`, `ssh`): build-time downloads
  run in a discarded builder stage (multi-stage build). Defense-in-depth — shrinks the
  blast radius, especially if the free-form-shell opt-in is ever enabled.

## Out of scope

- Inline committable PR review comments (`suggestion` blocks are carried in the
  `Finding` schema for later, but posting them as inline review comments is not v1).
- A persistent/hosted codebase index or embedding graph (git-committed codemap
  replaces it).
- In-container type-level analysis / building / running tests (delegated to the
  repo's own CI; consumed via the `findings.json` seam if present).
- Free-form LLM-generated shell execution (documented opt-in for trusted/self-hosted
  runners only; not part of the default trust model).
- Per-path / per-directory review instructions (repo instructions are repo-wide in v1).
- Multi-tenant hosting, horizontal scaling, org-wide dashboards.

## Technical design

**Language & packaging.** Python 3.12 CLI (single console entrypoint `open-review`),
shipped as one container image. Rationale: bundling semgrep forces a Python runtime
into the image regardless of orchestrator language, so a Python orchestrator rides
that runtime for free — a Go binary would add a second runtime on top. (We shell out
to semgrep; its language doesn't otherwise bind ours. If semgrep ever moved to a
sidecar, a static Go/Rust core would win on size — out of scope here.)

**Components (internal stages, one binary):**

```
diff → static scan → AI investigate (generate→evaluate→judge) → report
                          │ uses vetted read-only toolbox (on-demand retrieval)
codemap: generate-on-main / read-on-PR (committed .open-review/codemap.md)
```

**The seam — `Finding`** (neutral, CI/VCS-agnostic):

```json
{"file": "str", "line": "int",
 "severity": "note|warning|error",       // == SARIF levels
 "category": "lint|bug|security|style|design",
 "message": "str", "source": "str",      // "semgrep:<rule>", "gitleaks", "ai:<model>"
 "suggestion": "str"}                     // optional replacement code
```

`findings.json` is the artifact passed between the static and AI stages when they
run as separate CI jobs; in-process it is a list. Emitters at the report edge
translate it to stdout/exit-code/GitHub/GitLab/SARIF — the core never imports a CI
SDK.

**Vetted toolbox** (read-only, allowlisted, implemented on ast-grep/ripgrep/git):
`grep`, `find_callers`, `show_definition`, `blame`, `read_range`, `list_tests_for`.
The LLM selects and parameterizes these; it never emits shell.

**Router.** OpenAI-compatible via the `openai` SDK + `base_url`. Per-stage models
via `MODEL_GENERATE` / `MODEL_EVALUATE` / `MODEL_JUDGE` (unset → stage skipped;
`MODEL` is an alias for `MODEL_GENERATE`). Stages may point at different backends
through one router (e.g. local Ollama for generate, frontier for judge).

**Dependencies (justified):**
- `openai` — OpenAI-compatible router calls (LiteLLM/OpenRouter/self-hosted).
- `semgrep` — bundled polyglot bug rules (`--config auto` infers per language). The
  single heavy dependency (~300MB); bundling is accepted per stakeholder decision.
- `gitleaks`, `ast-grep`, `ripgrep`, `ruff` — small static binaries (secrets,
  structural retrieval, search, python baseline). No language runtimes bundled.
- git CLI — diff extraction and codemap commit.

**Image size target.** ≤ 500MB is the aspiration; with semgrep bundled the accepted
ceiling is ~600MB. No language runtimes bundled (AC-25).

## Code-bound invariants (docref)

These structural contracts are bound to the code that defines them via docref, so
this spec cannot silently drift from `src/open_review/`. Behavioral acceptance
criteria are anchored to their implementations per phase, as each stage is built.

<!-- docref: begin src=src/open_review/findings.py#Finding:35812d6b -->
The `Finding` seam carries `file`, `line`, `severity` (one of `note`, `warning`, `error`
— the SARIF levels), `category`, `message`, `source`, an optional `suggestion`, and
`dropped_by`/`drop_reason` (empty when active; set when the cascade discards it).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/toolbox.py#@allowlist:208c5240 -->
The vetted read-only toolbox allows exactly six actions — `grep`, `find_callers`,
`show_definition`, `blame`, `read_range`, `list_tests_for` — and nothing else; the
model never emits raw shell (AC-9).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/cascade.py#@stages:f30be727 -->
The AI cascade runs three stages in order — `generate` → `evaluate` → `judge` —
each with its own configurable model (AC-13, AC-14).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/codemap.py#@codemap-path:cf5c1440 -->
The committed codemap lives at `.open-review/codemap.md` (AC-16).
<!-- docref: end -->

### Behavioral invariants (P0)

<!-- docref: begin src=src/open_review/diff.py#resolve_base:92e7330e -->
The base ref resolves in order: explicit `--base`, then the CI target branch as a
remote-tracking ref (`origin/$GITHUB_BASE_REF`, then
`origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME`), then `origin/main` (AC-24).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/ai.py#run:f0433dc7 -->
When no `LLM_API_KEY` is set the AI stage prints a notice and returns no findings (a
degraded mode, not an error, AC-3); otherwise it runs a bounded investigation loop — the
model may call vetted toolbox actions to gather cross-file context, then calls `report`,
capped at `MAX_STEPS` — and the resulting findings pass through the evaluate/judge cascade
(AC-2, AC-11, AC-13).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/report.py#report:dd07551b -->
The exit gate considers only active findings — `0` when none is at/above `--fail-on`
(default `warning`), `1` otherwise, `off` always `0`; dropped findings render in a separate
discarded section and don't affect the gate. GitHub annotations, SARIF, and GitLab reports
are dispatched additively (AC-5, AC-15, AC-20..AC-23).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/instructions.py#load:cdce8539 -->
Repo instructions load from `.open-review/instructions.md`: the working tree for
trusted PRs, and the base-branch version (`git show`) for untrusted/fork PRs; absent or
empty yields none (AC-27, AC-28).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/ai.py#_system:dcb1be6c -->
Repo instructions, when present, are injected into the reviewer's system prompt
(delimited, augmenting — not overriding — the core prompt); absent leaves the base
prompt unchanged (AC-27).
<!-- docref: end -->

### Behavioral invariants (P1)

<!-- docref: begin src=src/open_review/static.py#_semgrep:d1dbdb18 -->
semgrep findings are normalized to `Finding`s (severity mapped from ERROR/WARNING/INFO,
`source` = `semgrep:<rule>`); a semgrep missing from PATH or producing unparseable output
is skipped with a printed notice, never a silent omission (AC-6, AC-7).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/static.py#_gitleaks:2bd2f330 -->
gitleaks secrets are normalized to error/security `Finding`s, filtered to the changed
files; a gitleaks missing from PATH or producing unparseable output is skipped with a
printed notice (AC-6, AC-7).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/ai.py#_prompt:b82daab5 -->
Static findings are folded into the review prompt as "already found — do not repeat"
signal, alongside the codemap and diff (AC-8).
<!-- docref: end -->

### Behavioral invariants (P2)

<!-- docref: begin src=src/open_review/toolbox.py#run_action:90a15df0 -->
Every toolbox action is checked against the allowlist and its arguments validated (symbols
must be identifiers, paths confined to the repo root); a rejected request returns an
`error: ...` string to the model rather than raising (AC-9).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/toolbox.py#_scrubbed_env:9e66957d -->
Toolbox subprocesses are spawned with an `env -i`-style environment — only PATH/HOME/LANG,
never `LLM_API_KEY` or any CI secret (AC-10).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/toolbox.py#_find_callers:a9bb13da -->
Cross-language retrieval (`find_callers`) is resolved via ast-grep over every language
present in the repo, with no language runtime required (AC-12).
<!-- docref: end -->

### Behavioral invariants (P3)

<!-- docref: begin src=src/open_review/codemap.py#_symbols:5c8610c1 -->
The codemap's structural layer is extracted deterministically via ast-grep — every source
file's functions, classes, and methods captured by name; the map contains everything the
extractor finds, omitting nothing (AC-16, AC-16b).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/codemap.py#read:e76aae9c -->
A committed `.open-review/codemap.md` is read back and fed to the reviewer as architectural
context; absent or empty yields none (AC-17).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/codemap.py#commit:0871037b -->
Committing the codemap uses a `[skip ci]` message marker so the commit does not trigger a
recursive CI run (AC-18).
<!-- docref: end -->

### Behavioral invariants (P4)

<!-- docref: begin src=src/open_review/cascade.py#adjudicate:5504d83c -->
An adjudication stage (evaluate/judge) sees only the candidate findings, never the diff
(AC-13); it keeps/drops/re-grades each, and a dropped finding is retained and tagged with
the stage + reason rather than removed (AC-15).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/cascade.py#apply:8d9a51d9 -->
The cascade runs evaluate then judge only when their models are configured; with none set
it collapses to a no-op (AC-14).
<!-- docref: end -->

### Behavioral invariants (P5)

<!-- docref: begin src=src/open_review/emitters.py#github_annotations:549ab61e -->
GitHub Actions workflow-command annotations are emitted per finding
(`::error|warning|notice file=…,line=…::…`) when running under `GITHUB_ACTIONS` (AC-20).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/emitters.py#sarif:b8ae072d -->
The SARIF emitter produces a 2.1.0 document with one result per finding (AC-22).
<!-- docref: end -->

<!-- docref: begin src=src/open_review/emitters.py#gitlab:03964b5d -->
The GitLab emitter produces a Code Quality report with mapped severities and a stable
per-finding fingerprint (AC-21).
<!-- docref: end -->

## Security considerations

- **Secret scoping (AC-10).** Coarse: `review` job holds `LLM_API_KEY` and **no**
  write token; a separate `commit-map` job holds the write token and runs no LLM/
  exec. Fine: the orchestrator holds the key and the only egress (to the router);
  it spawns every toolbox executor with `env -i` so no secret is inherited.
- **Fork PRs.** Untrusted diff content → read-only, no privileged token, codemap
  read-not-written (AC-19).
- **Toolbox allowlist (AC-9).** Default trust model runs no LLM-authored code — only
  our read-only, non-networking tools with validated arguments. Free-form shell is a
  documented opt-in requiring a self-hosted/trusted runner and adds a `--network
  none` executor.
- **Minimal runtime image (AC-26).** No `curl`/`wget`/`nc`/`ssh` in the final image;
  fetches happen in a builder stage. Honest boundary: Python's stdlib can still open
  sockets, so this is not a hard network jail for arbitrary Python — but the executor
  runs only fixed binaries (never model-authored Python), and the free-form-shell
  opt-in additionally uses a `--network none` executor.
- **Input validation.** All model-supplied toolbox arguments (paths, symbols,
  patterns) are validated: paths resolved and confined to the repo root (reject
  `..`/symlink escape); patterns length-bounded.
- **No secrets in output.** Findings and logs never include env values; gitleaks
  finding messages report the *description*, not the secret value.
- **Repo instructions trust (AC-28).** `.open-review/instructions.md` is repo-owner
  config injected as system-level guidance; for untrusted/fork PRs it is read from the
  **base branch**, not the PR head, so a PR cannot whitewash its own review. Changes to
  it appear in the diff and are reviewable. It augments — it cannot override — core
  review and safety behavior.

## Test requirements

Real subprocesses for scanners/toolbox (no mocking the tools); the router call is
the only external boundary stubbed (a fake OpenAI-compatible server returning canned
tool calls). Mapping:

| Scenario | Covers |
|---|---|
| diff→findings happy path against a fixture repo | AC-1, AC-2 |
| no `LLM_API_KEY` → static-only, degraded (not exit 2) | AC-3 |
| report formatting + `--fail-on` thresholds (note/warning/error) | AC-4, AC-5 |
| semgrep+gitleaks normalization + missing-tool skip | AC-6, AC-7 |
| static findings appear in AI prompt | AC-8 |
| toolbox allowlist rejects non-allowlisted action | AC-9 |
| executor env has no `LLM_API_KEY`/`*_TOKEN` | AC-10 |
| loop stops at `MAX_STEPS` | AC-11 |
| `find_callers` across ≥2 languages without runtimes | AC-12 |
| 3-stage cascade order + payload isolation; collapse when unset; dropped findings retained + tagged | AC-13, AC-14, AC-15 |
| codemap generate/read/commit-skip-marker/fork-no-push | AC-16–AC-19 |
| codemap completeness: every repo symbol present (self-discovering) | AC-16b |
| repo instructions: present/absent/base-for-untrusted + injected into system | AC-27, AC-28 |
| GitHub/GitLab/SARIF/plain emitters keyed by env | AC-20–AC-23 |
| base-ref resolution per CI env + fallback | AC-24 |
| built image bundles scanners, no language runtime | AC-25 |
| runtime image has no curl/wget/nc/ssh (multi-stage) | AC-26 |

## Rejection paths

| Failure mode | Behavior | Exit / result | Logged context |
|---|---|---|---|
| No `LLM_API_KEY` | Skip AI stage, static-only | notice, exit per findings | "AI stage skipped: no router configured" |
| No `LLM_BASE_URL` but key set | Fail fast with config error | exit 2 | missing var name |
| Router call fails (network/5xx/timeout) | Retry per SDK, then skip AI stage with warning | warning, static findings still reported | request-id, status |
| Router returns no tool call | Treat as zero AI findings | continue | model, stage |
| Scanner not on PATH | Skip that scanner | notice, continue | scanner name |
| Scanner nonzero exit with parseable output | Use output; if unparseable, skip with warning | continue | scanner, stderr head |
| Toolbox action not on allowlist (AC-9) | Reject, return error result to model | continue | requested action |
| Toolbox path escapes repo root | Reject argument | continue | offending path |
| `MAX_STEPS`/budget exceeded | Stop loop, report partial | continue | steps, tokens |
| Base ref unresolvable | Fail fast | exit 2 | tried refs |
| Codemap commit on fork PR | Read-only, no push | continue | "fork PR: codemap read-only" |
| Instructions file absent/empty | No-op (no guidance injected) | continue | — |
| Instructions base version missing (untrusted) | Treat as absent | continue | base ref |
| Findings at/above `--fail-on` | Nonzero exit (gate) | exit 1 | worst severity, count |

## Phased delivery

Everything above is in scope; build order: **P0** core loop → **P1** static stage →
**P2** vetted toolbox + secret-scoped executor (the heart) → **P3** codemap → **P4**
cascade → **P5** CI emitters + base-ref + packaging. P0–P2 alone target
CodeRabbit-parity; P3–P5 are recall, cost, and adoption refinements.
