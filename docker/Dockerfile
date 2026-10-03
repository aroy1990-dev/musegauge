# syntax=docker/dockerfile:1
# musegauge container image, target `slim` (spec section 8.3). There is no `full` target in 0.1
# (amendment A16, Roy's decision at GATE 3; see docs/IDEAS.md).
#
# NOT BUILT on the builder's machine: Docker is not installed there (docs/INSTALL.md).
#
# Build from the repository root after `uv build`, so dist/ holds exactly one musegauge wheel:
#   docker build -f docker/Dockerfile --target slim -t musegauge:slim .
# The plugin lock files are for linux-x86_64, so build for linux/amd64.

# Base: Debian bookworm with Python 3.12. The tag was checked on Docker Hub (HTTP API) on
# 2026-10-03, not with `docker manifest inspect`. Pin it by digest for a release.
FROM python:3.12-slim-bookworm AS slim

# System packages from section 8.3. No 0.1 plugin runs sox (amendment A6); it is kept for
# `musegauge doctor` and later plugins. ffmpeg also gives torchaudio its FFmpeg backend.
RUN apt-get update \
 && apt-get install -y --no-install-recommends sox ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# uv, the way the uv Docker guide shows (read 2026-10-03): copy the binaries from the uv image
# at a fixed version (the guide recommends a fixed version or a digest over `latest`).
COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /uvx /bin/

# musegauge from the wheel in the build context, never from PyPI, so CI tests the exact wheel.
COPY dist/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# /cache holds the plugin environments (about 24 GB once all are built) and the weights. Mount a
# writable volume or folder there from outside the image. It is world-writable so the image also
# works with `docker run --user`.
RUN mkdir -p /cache && chmod 777 /cache
ENV MUSEGAUGE_HOME=/cache
ENTRYPOINT ["musegauge"]
CMD ["--help"]
