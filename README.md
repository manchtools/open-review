# open-review

A containerized, CI-agnostic, router-agnostic AI code reviewer that runs on **your own
infra**. Add it once to any CI service; on each pull/merge request it runs a deterministic
static scan plus an LLM investigation that pulls in the *cross-file* context a diff-only
reviewer misses, then reports findings via the exit code and native CI annotations. Point it
at any OpenAI-compatible router (OpenRouter, LiteLLM, self-hosted) — no hosted index, no
service dependency of its own.

The thesis (validated against CodeRabbit/Greptile): the value is **context assembly before
the model**, not the model itself. Cross-file recall comes from a committed, deterministic
codemap plus on-demand retrieval over a vetted read-only toolbox — not a hosted graph.

Image: `ghcr.io/manchtools/open-review:latest` · License: AGPL-3.0-or-later.

## How it works

```
files → static scan (ruff · shellcheck · gitleaks · ast-grep)     [0 tokens]
      → AI review (generate → evaluate → judge cascade)
          │ codemap (.open-review/codemap.md) as committed cross-file context
          │ vetted read-only toolbox for on-demand retrieval (diff mode)
          └ the judge verifies every finding against the real code before keeping it
      → report: exit code (universal) + GitHub annotations / GitLab / SARIF
```

- **Static** — `ruff`, `shellcheck`, `gitleaks`, and `ast-grep` (vendored rules). All local,
  no network, no telemetry.
- **Codemap** — a deterministic structural map built with **universal-ctags** (40+ languages):
  every symbol with its signature and doc-comment, an import-resolved **call graph**, and
  module-level variables. Committed to `.open-review/codemap.md` so git is the index.
- **Cascade** — `generate` (cheap recall) → `evaluate` (cull) → `judge` (final). Each
  adjudicator is shown the **actual code** at every finding and drops what the code doesn't
  support — the primary false-positive guard. Dropped findings are kept + tagged, not deleted.

## Modes

| Command | Use | Scope |
|---|---|---|
| `open-review baseline` | first adoption / on demand | whole repo → a snapshot of existing issues |
| `open-review run` | every PR | just the diff, using the committed codemap + toolbox |
| `open-review codemap [--commit] [--describe] [--light]` | on `main` | (re)generate the codemap |
| `open-review static` / `report` | building blocks | static-only / render + gate |

Findings gate the exit code: `0` clean, `1` a finding at/above `--fail-on` (default `warning`),
`2` operational failure. Use `--fail-on off` for advisory mode.

## Quickstart (local)

```sh
# one-time: establish the codemap + a baseline of existing issues
docker run --rm --env-file .env -v "$PWD":/repo -w /repo \
  ghcr.io/manchtools/open-review:latest baseline --describe

# per-change: review the diff
docker run --rm --env-file .env -v "$PWD":/repo -w /repo \
  ghcr.io/manchtools/open-review:latest run --sarif out.sarif
```

Commit `.open-review/codemap.md` so PR reviews have cross-file context. **CI setup** (GitHub
Actions / GitLab, with a codemap job that handles branch-protected `main`) is in
[`docs/ci/`](docs/ci/).

## Configuration (environment)

| Variable | Meaning |
|---|---|
| `OR_LLM_BASE_URL` | OpenAI-compatible router endpoint |
| `OR_LLM_API_KEY` | router key (unset → static-only; not an error) |
| `OR_MODEL` / `OR_MODEL_GENERATE` | generate-stage model (cheap recall) |
| `OR_MODEL_EVALUATE` | evaluate-stage model (unset → stage skipped) |
| `OR_MODEL_JUDGE` | judge-stage model (unset → stage skipped) |
| `OR_MODEL_DESCRIBE` | cheap model for codemap `--describe` (falls back to generate) |
| `OR_MODEL_REPAIR` | cheap model to repair truncated tool output (falls back to describe/generate) |
| `OR_LLM_MAX_TOKENS` | output-token cap (default 8000; lower for small models) |
| `OR_LLM_PROVIDER` | comma-separated provider preference order, e.g. `StreamLake,DeepSeek` |
| `OR_LLM_PROVIDER_FALLBACK` | bool (default `true`) — allow other providers when a preferred one can't serve a model |
| `OR_CONCURRENCY` | parallel baseline batches after the cache is warmed (default 4) |
| `OR_BATCH_CHARS` | baseline batch size in chars (default 20000; lower to avoid truncation) |
| `OR_TOOL_TIMEOUT` | per external-tool timeout, seconds (default 300) |

Base ref auto-resolves from CI env (`GITHUB_BASE_REF`, `CI_MERGE_REQUEST_TARGET_BRANCH_NAME`),
falling back to `origin/main`; override with `--base`. For fork/untrusted PRs use `--untrusted`
(repo config + codemap are read from the base branch, never the PR head).

### Provider routing & caching

The big cacheable payload is the codemap prefix sent to the generate model. Routers like
OpenRouter load-balance a model across upstreams, and the prompt cache is **per-provider** — so
pin `OR_LLM_PROVIDER` to one that caches (keep `OR_LLM_PROVIDER_FALLBACK=true` so an Anthropic judge
still routes to Anthropic). The baseline warms the cache with the first batch, then fans the
rest out concurrently. Cache reuse is logged (`· router: N cached prompt token(s)`).

## Languages

Full support (symbols + signatures + doc-comments + resolved call graph): **Python, JavaScript,
TypeScript, Go, Rust, Java, C#, C++, PHP, Kotlin.** Symbols + signatures + doc-comments for
**40+ more** via ctags (C, Ruby, Bash, PowerShell, Batch, SQL, Lua, …). `--light` emits a
compact structural-only codemap for small context windows.

## Development

```sh
pip install -e '.[dev]'
pytest                 # test suite
ruff check src tests   # lint
```

Built spec-first: acceptance criteria live in [`docs/specs/01-open-review.md`](docs/specs/01-open-review.md),
and prose is anchored to code with docref. Third-party components and their licenses are listed
in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## License

[AGPL-3.0-or-later](LICENSE). If you run a modified version as a network service, §13 requires
you to offer your users the source of your modifications — so hosted forks give back.
