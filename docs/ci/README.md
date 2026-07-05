# Running open-review in CI

open-review is a single container. A CI job runs it against the checked-out repo; it reports
findings via the **exit code** (universal) and native annotations where available (GitHub
workflow commands, GitLab Code Quality, SARIF).

## What you need

1. **The image.** Publish it once to a registry your CI can pull:
   - Tag this repo `vX.Y.Z` (or run the `publish` workflow manually) → it pushes
     `ghcr.io/<owner>/open-review:latest`. Any registry works; GHCR is the default.
   - Or build it in-repo: `docker build -t open-review .`
2. **Router config.** Set it **once at the org/group level** with an `OR_` prefix so every repo
   inherits it — secret `OR_LLM_API_KEY`, variables `OR_LLM_BASE_URL`, `OR_MODEL_GENERATE`,
   `OR_MODEL_EVALUATE`, `OR_MODEL_JUDGE`, `OR_MODEL_DESCRIBE`, `OR_LLM_PROVIDER`,
   `OR_LLM_PROVIDER_FALLBACK`. The templates read these; consuming repos need no per-repo setup.
3. **A committed codemap** (optional but recommended). `open-review run` reads
   `.open-review/codemap.md` for cross-file context. Generate it once and commit it — either
   run `open-review baseline` locally, or let the `codemap` job on `main` keep it fresh.
4. **The workflow.** Copy [github-actions.yml](./github-actions.yml) (or
   [gitlab-ci.yml](./gitlab-ci.yml)), replace `OWNER`, and commit it.

That's it — open a PR and the review runs.

## Two modes

| Command | When | Scope |
|---|---|---|
| `open-review baseline` | first adoption / manual | whole repo → a snapshot of existing issues |
| `open-review run` | every PR | just the diff, using the committed codemap + toolbox |
| `open-review codemap --commit` | on `main` | regenerate + commit the map (reuses cached AI descriptions) |

## Configuration (environment)

| Variable | Meaning |
|---|---|
| `LLM_BASE_URL` | OpenAI-compatible router base URL |
| `LLM_API_KEY` | router key (never logged; pass via secret) |
| `MODEL_GENERATE` | cheap recall model (also aliased by `MODEL`) |
| `MODEL_EVALUATE` | mid-stage culler (optional; skip to collapse the cascade) |
| `MODEL_JUDGE` | final judge — verifies each finding against the code (optional) |
| `MODEL_DESCRIBE` | cheap model for codemap `--describe` (falls back to `MODEL_GENERATE`) |
| `LLM_MAX_TOKENS` | output-token cap (default 8000; lower for small models) |
| `LLM_PROVIDER` | comma-separated provider preference order, e.g. `DeepSeek,Together` |
| `LLM_PROVIDER_FALLBACK` | bool, default `true` — allow other providers when a preferred one can't serve a model |
| `--fail-on {note,warning,error,off}` | gate threshold for the exit code (default `warning`) |

### Provider routing & caching

The big cacheable payload is the codemap prefix sent to the generate/baseline model. Pinning
`LLM_PROVIDER=DeepSeek` routes those to DeepSeek's own endpoint (which holds the prompt cache).
Keep `LLM_PROVIDER_FALLBACK=true` (the default) so the **Opus judge still works** — an Anthropic
model can't be served by DeepSeek, so it falls through to Anthropic automatically. One list,
mixed models, no per-stage config. Cache hits are logged (`· router: N cached prompt token(s)`).

Caching is primarily a **within-run** win (a baseline's batches / an investigation loop's steps
share the identical prefix). Run-to-run hits only happen for unchanged code, same provider,
within the provider's cache TTL.

## Trust

For fork/untrusted PRs, run with `run --untrusted`: repo instructions and the codemap are read
from the **base branch**, never the PR head, so a PR can't rewrite the reviewer that judges it.
Keep `LLM_API_KEY` out of fork-triggered jobs (use `pull_request_target` carefully or gate on
label) — the container also scrubs secrets from its own read-only toolbox subprocesses.
