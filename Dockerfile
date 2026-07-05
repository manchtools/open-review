# syntax=docker/dockerfile:1
# open-review — default image (Spec §Packaging; AC-25, AC-26).

# --- builder: fetch the one non-pip binary (gitleaks). Discarded. -------------
FROM debian:bookworm-slim AS builder
ARG GITLEAKS_VERSION=8.21.2
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    | tar -xz -C /usr/local/bin gitleaks

# --- runtime: NO curl / wget / nc / ssh in this image (AC-26) ------------------
FROM python:3.12-slim

# git + ripgrep + shellcheck from apt (none pulls a network exfiltration CLI). No runtimes.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ripgrep shellcheck \
 && rm -rf /var/lib/apt/lists/*

# Bundled analysis tools — all local, no service (AC-25). ruff + ast-grep via pip.
RUN pip install --no-cache-dir \
      ast-grep-cli==0.44.1 \
      ruff

COPY --from=builder /usr/local/bin/gitleaks /usr/local/bin/gitleaks

COPY . /app
RUN pip install --no-cache-dir /app

ENTRYPOINT ["open-review"]
