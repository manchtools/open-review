# Spec 02 — open-review v0.2.0

## Overview

v0.1 answers *"what's wrong with this change?"* v0.2 adds the **write-back** and **learning**
layer on top of it: committable fixes, a PR summary (with a change diagram), suggested tests,
confidence scores, path-scoped instructions, git-native memory, and incremental (delta-only)
review — plus explicit per-stage provider routing for cost/cache control.

Two invariants carry over and constrain every feature here:

- **The CI-agnostic core is untouched.** The exit code + `findings.json` seam remain the
  universal contract. Everything that writes back to a PR (comments, suggestions, summaries) is
  an **optional emitter**, token-gated, exactly like the SARIF/GitLab emitters today — absent a
  token it is skipped, never an error.
- **No hosted service, no chat.** Interactive bot replies are explicitly out of scope. All new
  persistent state (memory, incremental cursor) lives **in-repo; git is the index** — the same
  philosophy as the committed codemap.

## Acceptance criteria

Grouped by feature; `[P7x]` marks the delivery sub-phase. Each is verifiable by ≥1 automated test.

### GitHub review emitter + committable suggested fixes `[P7a]`
The model already produces a `suggestion` (replacement code) per finding; v0.2 surfaces it.
- **AC-1** Given `--emit-github-review` and a `GITHUB_TOKEN` on a pull request, when the report
  step runs, then each active finding is posted as an inline PR review comment at its `file:line`,
  and a finding with a non-empty `suggestion` includes a committable ```suggestion block.
- **AC-2** Given a finding with a `suggestion`, when SARIF is written, then the result carries a
  `fixes[].artifactChanges` region so the GitHub Security tab can offer "apply fix".
- **AC-3** Given no token (or not a PR), when the emitter runs, then it is skipped with a notice
  and the exit-code/stdout output is unchanged (optional-emitter invariant).
- **AC-4** Given a re-review of the same PR, when comments are posted, then a finding already
  commented at the same `file:line:message` is not duplicated (stable fingerprint dedupe).

### PR summary / walkthrough + change diagram `[P7b]`
- **AC-5** Given `--emit-summary`, when review runs, then a concise markdown summary of the PR
  (what changed, notable risks, affected areas) is generated from the diff by a cheap model and
  written to a file and/or posted as a single PR comment that is **updated** (not duplicated) on
  re-runs.
- **AC-6** Given the summary, when it is generated, then it includes a **mermaid** diagram of the
  change (control/data flow for the touched symbols). The deterministic fallback, when the model
  declines or the diagram fails to parse, is a mermaid graph built from the **codemap's call
  edges** for the changed symbols — so a diagram always renders.

### Confidence scores `[P7c]`
- **AC-7** Given the judge stage, when it adjudicates a finding it keeps, then it assigns a
  `confidence` (enum `low|medium|high`) stored on the `Finding`; confidence is rendered in stdout,
  annotations, and SARIF.
- **AC-8** Given `--min-confidence <level>`, when reporting, then findings below the level are
  moved to the discarded section (retained + tagged, like a cascade drop), not deleted.

### Path-based instructions `[P7c]`
- **AC-9** Given `.open-review/instructions/<glob>.md` files (or a `[paths]` table in
  `.open-review/config.toml`), when a changed file matches a path glob, then that path's
  instructions are appended to the reviewer's guidance **for that file's batch only**; a file
  matching no path uses just the repo-level `instructions.md`.

### Memory (learnings) `[P7e]`
- **AC-10** Given a committed `.open-review/memory.md`, when a review runs, then its entries are
  injected as durable guidance (do-not-flag rules, accepted patterns, house conventions) into the
  reviewer's system prompt, after `instructions.md`.
- **AC-11** Given a merged PR and the review that ran on it, when `open-review learn` executes,
  then for each finding that review raised it classifies **fixed** (the flagged lines changed in
  the merge) vs **dismissed** (merged unchanged), and emits **proposed** `memory.md` additions for
  dismissed findings that recur — written as a diff/branch a human or agent commits. Nothing is
  auto-committed to `memory.md`; the derivation only proposes.
- **AC-12** Given a fork/untrusted PR, when memory is loaded, then the **base-branch** `memory.md`
  is used (never the PR head's), same trust model as `instructions.md` (v0.1 AC-28).

### Incremental review `[P7d]`
- **AC-13** Given a PR whose earlier commits were already reviewed, when `run --incremental`
  executes, then only the delta since the last-reviewed SHA is sent to the model; findings on
  unchanged lines are **carried forward** from the prior review rather than regenerated, cutting
  tokens on push-after-push.
- **AC-14** Given an incremental run, when it completes, then the last-reviewed SHA is recorded
  (a git note or `.open-review/state.json`) so the next run knows the delta; a first run with no
  cursor falls back to a full diff review.

### Suggested unit tests `[P7e]`
- **AC-15** Given `--suggest-tests`, when review runs on changed code that lacks a corresponding
  test, then open-review discovers the repo's test framework/conventions (via the read-only
  toolbox reading sibling tests) and produces a unit test, emitted as a new-file suggestion (or a
  finding whose `suggestion` is the test). It is a proposal a human commits — never auto-added.

### Explicit per-stage provider routing `[P7c]`
Replaces the v0.1.1 model-aware "skip Anthropic" heuristic with explicit control.
- **AC-16** Given `MODEL_<STAGE>_PROVIDER` and `MODEL_<STAGE>_PROVIDER_FALLBACK` (STAGE ∈
  `GENERATE|EVALUATE|JUDGE|DESCRIBE|REPAIR`), when that stage calls the router, then it uses the
  stage's provider order + fallback; if unset it falls back to the global `LLM_PROVIDER`
  /`LLM_PROVIDER_FALLBACK`; a stage explicitly set empty/`none` is left **unpinned**. This lets
  DeepSeek stages hard-pin to one host (cache locality) while the judge (Anthropic) is unpinned —
  no name heuristic.

## Out of scope

- **Chat / interactive replies** to the bot in PR comments — not wanted; no one uses it.
- **Suppression markers** (`// open-review: ignore`) — `memory.md` + fixes cover the need; a
  separate ignore syntax is redundant.
- Auto-applying fixes/tests/memory — every write-back is a **proposal a human commits**.
- Any hosted index or persistent service.

## Technical design

- **Emitters** (`emitters.py` grows): `github_review` (PR review comments + suggestion blocks via
  the GitHub REST API using `GITHUB_TOKEN`), `summary` (markdown + mermaid). Both optional and
  token/PR-gated; the neutral `findings.json` + exit code stay the fallback.
- **Schema**: `Finding` gains `confidence: str = ""`. The report tool schema adds `confidence`
  (judge stage) and the tests/summary use dedicated tools.
- **Commands / flags**: `run`/`baseline` gain `--emit-github-review`, `--emit-summary`,
  `--suggest-tests`, `--incremental`, `--min-confidence`. New `open-review learn` for memory
  derivation.
- **Memory**: `instructions.load` gains a sibling `memory.load` reading `.open-review/memory.md`
  (base-branch for untrusted). `learn` reuses the diff machinery to compare a stored prior-review
  `findings.json` against the merge and classify fixed/dismissed.
- **Incremental**: a cursor (git note `open-review/reviewed` or `.open-review/state.json`) holds
  the last-reviewed SHA; `diff.resolve_base` gains an incremental mode.
- **Per-stage provider**: `router._extra_body(stage, model)` resolves `MODEL_<STAGE>_PROVIDER`
  before the global; the stage name threads through `call_tool(..., stage=...)`. Remove the
  `"claude" in model` heuristic.

## Security considerations

- **Write-back tokens.** `github_review` needs `pull-requests: write`; on **fork** PRs, never run
  it with elevated permissions (gate on non-fork, or use the base-repo trust model). Suggestions
  are committable by the PR author, not auto-merged.
- **Memory + path instructions are repo-owner content**, like `instructions.md`: for untrusted PRs
  read the **base-branch** version so a PR can't rewrite the reviewer that judges it (AC-12).
- **No new secret surfaces.** The read-only toolbox (used by suggested-tests discovery) keeps its
  scrubbed-env executor from v0.1.

## Test requirements

| Scenario | AC |
|---|---|
| github_review posts inline comment + suggestion block (fake GitHub API); dedupe on re-run | AC-1, AC-4 |
| SARIF carries a fix region for a finding with a suggestion | AC-2 |
| no token / not a PR → emitter skipped, core output unchanged | AC-3 |
| summary generated + updated (not duplicated); mermaid present, deterministic fallback renders | AC-5, AC-6 |
| judge assigns confidence; `--min-confidence` moves low ones to discarded | AC-7, AC-8 |
| path-glob instructions injected only for matching file's batch | AC-9 |
| memory.md injected into system prompt; base-branch for untrusted | AC-10, AC-12 |
| `learn` classifies fixed vs dismissed and proposes (never commits) memory entries | AC-11 |
| incremental sends only the delta; carries prior findings; records the cursor | AC-13, AC-14 |
| suggest-tests emits a framework-matched test as a proposal | AC-15 |
| per-stage `MODEL_JUDGE_PROVIDER` unpins the judge; DeepSeek stages pin | AC-16 |

## Rejection paths

| Condition | Behavior |
|---|---|
| `--emit-github-review` but no token / not a PR | skip with notice, exit unaffected |
| `--emit-summary` but router unconfigured | skip (static/AI still gate) |
| `memory.md` / path instructions absent | no memory / repo-level only — not an error |
| `learn` with no stored prior review | notice, no-op |
| incremental with no cursor | full review (graceful first-run) |
| per-stage provider set to empty/`none` | stage unpinned |

## Phased delivery

`P7a` github_review emitter + suggested fixes · `P7b` PR summary + change diagram · `P7c`
confidence + path-instructions + per-stage provider routing · `P7d` incremental review · `P7e`
memory (memory.md + `learn` derivation) + suggested unit tests.

Each sub-phase is spec → test → implement → verify → document, and each ships independently.
