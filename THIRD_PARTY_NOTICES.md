# Third-party notices

`open-review` is licensed **AGPL-3.0-or-later**. It bundles and invokes the third-party
components below. This file satisfies the attribution and source-availability obligations of
their licenses.

## Linked libraries (imported into the open-review process)

The only non-stdlib library linked into the program is:

| Library | License | Source |
|---|---|---|
| openai (Python SDK) | Apache-2.0 | https://github.com/openai/openai-python |

Apache-2.0 is one-way compatible with (A)GPL-3.0, so this combination is permitted under AGPL.
No GPL-licensed library is imported into the process — doing so would create a *combined work*
and must be avoided (a GPL-2.0-only import would be incompatible with AGPL-3.0).

## Bundled executables (invoked as separate processes / aggregation)

These are invoked via `subprocess` (CLI + stdio) and are **separate works** — "mere
aggregation" under the GPL. Their licenses do not extend to open-review's code, and AGPL's
terms do not extend to them. They are shipped **unmodified** from their upstream/Debian
packages.

| Tool | License | Source (also the "corresponding source" for the GPL tools) |
|---|---|---|
| ruff | MIT | https://github.com/astral-sh/ruff |
| ast-grep (`ast-grep-cli`) | MIT | https://github.com/ast-grep/ast-grep |
| gitleaks | MIT | https://github.com/gitleaks/gitleaks |
| ripgrep | MIT OR Unlicense | https://github.com/BurntSushi/ripgrep |
| shellcheck | GPL-3.0-only | https://github.com/koalaman/shellcheck |
| universal-ctags | GPL-2.0-or-later | https://github.com/universal-ctags/ctags |
| git | GPL-2.0-only (with BSD-3-Clause, LGPL-2.1-or-later, MIT parts) | https://git-scm.com / https://github.com/git/git |

### Written offer for GPL source

The GPL-licensed executables above (git, shellcheck, universal-ctags) are redistributed
**unmodified** as installed from the Debian package repositories. Their complete corresponding
source is available from the upstream URLs above and from the Debian source packages
(`apt-get source <pkg>`, or https://snapshot.debian.org). No modifications are made by this
project.

## Development-only (not distributed in the image)

| Tool | License |
|---|---|
| pytest | MIT |
| hatchling (build backend) | MIT |

## Summary

- open-review's own code: **AGPL-3.0-or-later**.
- Everything linked in-process is permissive (Apache-2.0) and AGPL-compatible.
- Every GPL component is a separate executable (aggregation), shipped unmodified, with source
  available as noted above.
