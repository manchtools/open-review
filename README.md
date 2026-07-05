# open-review

A containerized, CI-agnostic, router-agnostic AI code reviewer. Add it once to any
CI service; on each pull/merge request it runs a deterministic static scan plus an
LLM investigation that pulls in the cross-file context a diff-only reviewer misses,
then reports findings via the exit code and native CI annotations. Points at any
OpenAI-compatible model router (LiteLLM, OpenRouter, self-hosted).

> **Status: scaffold.** The design is specified in
> [`docs/specs/01-open-review.md`](docs/specs/01-open-review.md). Behavior is not yet
> implemented — the project follows a spec → test → implement flow, so pipeline
> commands currently raise `NotImplementedError`.

## How it works

```
diff → static scan (semgrep + gitleaks) → AI investigate (generate → evaluate → judge)
        │ vetted read-only toolbox for on-demand cross-file retrieval
        └ committed codemap (.open-review/codemap.md) as persistent context
→ report (stdout + exit code; GitHub / GitLab / SARIF)
```

The value is context assembly *before* the model: cross-file recall comes from
on-demand agentic retrieval over a vetted read-only toolbox, not a hosted index.

## Configuration (environment)

| Var | Meaning |
|---|---|
| `LLM_BASE_URL` | OpenAI-compatible router endpoint |
| `LLM_API_KEY` | router key (unset → static-only, not an error) |
| `MODEL` / `MODEL_GENERATE` | generate-stage model |
| `MODEL_EVALUATE` | evaluate-stage model (unset → stage skipped) |
| `MODEL_JUDGE` | judge-stage model (unset → stage skipped) |
| `SEMGREP_CONFIG` | semgrep ruleset (default `auto`) |

Base ref is auto-resolved from CI env (`GITHUB_BASE_REF`,
`CI_MERGE_REQUEST_TARGET_BRANCH_NAME`), falling back to `origin/main`; override with
`--base`.

## Quickstart

See [`.github/workflows/review.yml`](.github/workflows/review.yml) for a full
static → review → report example. Any CI works — the exit code is the universal
signal; native annotations are emitted where the CI supports them.

## Development

```sh
pip install -e '.[dev]'
pytest
```

## Delivery phases

`P0` core loop · `P1` static · `P2` vetted toolbox + secret-scoped executor · `P3`
codemap · `P4` cascade · `P5` CI emitters + packaging. Acceptance criteria per phase
are in the spec.

## License

[AGPL-3.0-or-later](LICENSE). If you run a modified version as a network service,
the AGPL's §13 requires you to offer your users the source of your modifications —
so hosted forks give back to the project.
