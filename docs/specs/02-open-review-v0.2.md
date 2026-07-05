# Spec 02 — open-review v0.2.0

## Overview

v0.1 answers *"what's wrong with this change?"* v0.2 adds the **write-back** and **learning**
layer: committable fixes, a PR summary (with a change diagram), suggested tests, confidence
scores, path-scoped instructions, git-native memory, and automatic incremental review.

Three invariants constrain every feature here:

- **Configuration is environment-driven, not flag-driven.** A variable set once at the org/repo
  level must change the behaviour of *every* reviewer without editing a single CI job. So every
  behaviour is read from the environment; CLI flags remain only as per-invocation overrides.
  Where a capability implies intent, the mere presence of its credential/value **auto-enables** it
  (a `GITHUB_TOKEN` on a PR ⇒ post the review; `OR_SARIF=path` ⇒ write SARIF). The CI
  templates pass **all `OR_*` org variables through generically** (stripping the prefix), so a new
  `OR_OR_SUMMARY=true` reaches the container as `OR_SUMMARY=true` with no job edit.
- **The CI-agnostic core is untouched.** The exit code + `findings.json` seam remain the universal
  contract. Everything that writes back to a PR is an optional, capability-gated emitter — absent
  its credential it is skipped, never an error.
- **No hosted service, no chat.** Interactive bot replies are out of scope. All persistent state
  (memory, the incremental cursor) lives **in-repo; git is the index** — like the committed codemap.

## Acceptance criteria

Grouped by feature; `[P7x]` marks the delivery sub-phase. Each is verifiable by ≥1 automated test.

### Environment-driven configuration `[P7c]`
- **AC-CFG1** Given a behaviour setting, when open-review resolves it, then the precedence is
  **explicit CLI flag → environment variable → built-in default**. Every current flag has an env
  equivalent: `OR_FAIL_ON`, `OR_SARIF`, `OR_GITLAB_REPORT`,
  `OR_DESCRIBE`, `OR_LIGHT`, `OR_UNTRUSTED`, `OR_COMMIT` — and
  the v0.2 additions below. Setting the env var alone (no flag) changes behaviour.
- **AC-CFG2** Given a credential/value that implies a feature, when a run starts, then the feature
  **auto-enables**: a `GITHUB_TOKEN` on a pull request enables the GitHub review emitter;
  `OR_SARIF=<path>` enables SARIF; etc. A feature can be force-disabled with its explicit
  env flag (e.g. `OR_GITHUB_REVIEW=off`).
- **AC-CFG3** Given the CI templates, when they run, then they export every `OR_*` repo/org
  variable into the container with the `OR_` prefix stripped, so org-level settings drive all
  reviewers without editing any job.

### GitHub review emitter + committable suggested fixes `[P7a]`
The model already produces a `suggestion` (replacement code) per finding; v0.2 surfaces it.
- **AC-1** Given a `GITHUB_TOKEN` on a pull request, when the report step runs, then all findings
  are **aggregated into a single PR review comment** (one comment, not one-per-line — to avoid an
  email storm), grouped by file with each finding's `file:line`, severity, message, and a
  committable ```suggestion block where a `suggestion` exists.
- **AC-2** Given a finding with a `suggestion`, when SARIF is written, then the result carries a
  `fixes[].artifactChanges` region so the GitHub Security tab can offer "apply fix".
- **AC-3** Given no token (or not a PR), when the run happens, then the review emitter is skipped
  with a notice and the exit-code/stdout output is unchanged.
- **AC-4** Given a re-review of the same PR, when the aggregated comment is posted, then the prior
  open-review comment is **updated in place** (stable marker), not duplicated.

### PR summary / walkthrough + change diagram `[P7b]`
- **AC-5** Given `OR_SUMMARY` (or a token on a PR), when review runs, then a concise
  markdown summary of the PR (what changed, notable risks, affected areas) is generated from the
  diff by a cheap model, written to a file, and — when a token is present — posted as a single PR
  comment updated in place on re-runs.
- **AC-6** Given the summary, when the model includes a **mermaid** diagram of the change, then it
  is rendered in the summary; when the model does not produce one, **no diagram is shown** (no
  deterministic fallback — a diagram appears only when it comes from the summary).

### Confidence scores `[P7c]`
- **AC-7** Given the judge stage, when it keeps a finding, then it assigns a `confidence`
  (`low|medium|high`) stored on the `Finding` and rendered in stdout, annotations, and SARIF.
- **AC-8** Given `OR_MIN_CONFIDENCE` (or `--min-confidence`), when reporting, then findings
  below the level are moved to the discarded section (retained + tagged), not deleted.

### Path-based instructions `[P7c]`
- **AC-9** Given `.open-review/instructions/<glob>.md` files (or a `[paths]` table in
  `.open-review/config.toml`), when a changed file matches a path glob, then that path's
  instructions are appended to the reviewer's guidance **for that file's batch only**; a file
  matching none uses just the repo-level `instructions.md`.

### Memory (learnings) — automatic `[P7e]`
- **AC-10** Given a committed `.open-review/memory.md`, when a review runs, then its entries are
  injected as durable guidance (do-not-flag rules, accepted patterns) into the system prompt,
  after `instructions.md`. For fork/untrusted PRs the **base-branch** `memory.md` is used (v0.1
  trust model).
- **AC-11** Given a merged PR and the review that ran on it, when the run completes, then
  open-review **automatically** classifies each raised finding as *fixed* (flagged lines changed)
  vs *dismissed* (merged unchanged) and **appends** a concise entry for recurring dismissals
  directly to `.open-review/memory.md` (committed on the codemap-refresh path). No branch → PR
  workflow — memory just accretes; a human edits the file directly if they disagree.

### Incremental review — automatic `[P7d]`
- **AC-13** Given a PR whose earlier commits were already reviewed, when a run happens, then it
  **automatically** reviews only the delta since the last-reviewed SHA (findings on unchanged lines
  are carried forward), with no flag or user interaction; the last-reviewed SHA is stored (git note
  or `.open-review/state.json`). A first run with no cursor falls back to a full diff review.

### Suggested unit tests `[P7e]`
- **AC-15** Given `OR_SUGGEST_TESTS`, when review runs on changed code lacking a test, then
  open-review discovers the repo's test conventions (via the read-only toolbox reading sibling
  tests) and produces a unit test, carried in the finding's `suggestion`. It is a proposal a human
  commits — never auto-added.

### Provider / model routing — env only `[P7c]`
- **AC-16** Given provider/model routing, when a stage calls the router, then **all** provider and
  model selection is environment-driven and org/repo-settable — there is **no project-specific
  (in-repo) model or provider config**. Per-stage overrides `MODEL_<STAGE>_PROVIDER` /
  `MODEL_<STAGE>_PROVIDER_FALLBACK` (STAGE ∈ `GENERATE|EVALUATE|JUDGE|DESCRIBE|REPAIR`) fall back to
  the global `LLM_PROVIDER`/`LLM_PROVIDER_FALLBACK`; a stage set empty/`none` is unpinned. This
  replaces the v0.1.1 model-name heuristic with explicit env config.

## Out of scope

- **Chat / interactive replies** — not wanted.
- **Suppression markers** (`// open-review: ignore`) — memory + fixes cover the need.
- **Per-finding inline PR comments** — one aggregated comment instead (email-storm avoidance).
- Auto-applying fixes/tests — proposals a human commits. (Memory is the one thing that *does* auto-accrete.)
- Any hosted index or persistent service.

## Technical design

- **Config layer**: a small resolver (`config.setting(name, cli, default)`) reads env then flag;
  argparse defaults are seeded from `OR_*`. Capability gates (`token → review`) resolve at
  runtime. Applied to current flags **now** (v0.1.x) and to v0.2 additions.
- **CI templates**: a pre-step exports `${{ toJSON(vars) }}` entries matching `OR_*` into `$GITHUB_ENV`
  with the prefix stripped; the run step passes the container `--env-file` / inherits them.
- **Emitters** (`emitters.py`): `github_review` (one aggregated PR comment + suggestion blocks via
  the GitHub REST API), `summary` (markdown + optional model-provided mermaid). Optional, gated.
- **Schema**: `Finding` gains `confidence: str = ""`.
- **Commands**: no new user-facing flags for describe/tests/incremental — env-driven. Memory
  derivation runs on the codemap-refresh path (auto-append). `--min-confidence` kept as an override.
- **Memory / incremental**: `memory.load` (base-branch for untrusted); a stored prior-review
  `findings.json` + the last-reviewed SHA drive dismissal classification and delta selection.
- **Per-stage provider**: `router._extra_body(stage, model)` resolves `MODEL_<STAGE>_PROVIDER` before
  the global; the stage threads through `call_tool(..., stage=...)`. The v0.1.1 name heuristic is removed.

## Security considerations

- **Write-back tokens.** The `github_review` emitter needs `pull-requests: write`; on **fork** PRs it
  must not run with elevated permissions. Suggestions are committable by the PR author, not merged.
- **Memory + path instructions are repo-owner content** (like `instructions.md`): untrusted PRs read
  the **base-branch** version so a PR cannot rewrite the reviewer that judges it.
- **Generic `OR_*` pass-through** must forward **variables**, not secrets, by default; the key and
  token are passed explicitly. Never `toJSON(secrets)` into the container.

## Test requirements

| Scenario | AC |
|---|---|
| setting resolves flag → env → default; env alone changes behaviour | AC-CFG1 |
| token-on-PR auto-enables review; `OR_GITHUB_REVIEW=off` disables | AC-CFG2 |
| CI pass-through maps `OR_X` → `X` | AC-CFG3 |
| all findings in ONE PR comment, grouped, with suggestion blocks; updated (not duplicated) on re-run | AC-1, AC-4 |
| SARIF carries a fix region for a finding with a suggestion | AC-2 |
| no token / not a PR → emitter skipped, core output unchanged | AC-3 |
| summary generated + updated; mermaid shown only when the model provides one | AC-5, AC-6 |
| judge assigns confidence; min-confidence moves low ones to discarded | AC-7, AC-8 |
| path-glob instructions injected only for the matching file's batch | AC-9 |
| memory.md injected (base-branch for untrusted); dismissed findings auto-appended | AC-10, AC-11 |
| incremental auto-detects cursor, sends only the delta, carries prior findings | AC-13 |
| suggest-tests emits a framework-matched test proposal | AC-15 |
| per-stage `MODEL_JUDGE_PROVIDER` unpins the judge; DeepSeek stages pin; no in-repo model config | AC-16 |

## Rejection paths

| Condition | Behavior |
|---|---|
| review capability but no token / not a PR | skip with notice, exit unaffected |
| summary but router unconfigured | skip (static/AI still gate) |
| `memory.md` / path instructions absent | none / repo-level only — not an error |
| no incremental cursor | full review (graceful first-run) |
| per-stage provider empty/`none` | stage unpinned |

## Phased delivery

`P7a` github_review emitter (one aggregated comment) + suggested fixes · `P7b` PR summary +
model-provided diagram · `P7c` env-driven config layer + confidence + path-instructions + per-stage
provider · `P7d` automatic incremental review · `P7e` automatic memory + suggested tests.

Each sub-phase is spec → test → implement → verify, and each ships independently. The env-driven
config layer (P7c) is also back-ported to the current v0.1 flags immediately.
