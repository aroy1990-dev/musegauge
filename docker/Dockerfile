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
# The wheel depends on uv, and pip puts its console scripts in /usr/local/bin, which shadows
# the pinned /bin/uv through PATH (found when the 0.1.1 image was first built and run on
# 2026-10-06: the effective uv was 0.12.23 while the pin says 0.12.22). Remove the scripts
# so the pinned uv is the one that runs; its musl build executes fine on this glibc base
# (verified 2026-10-07: `/bin/uv --version` in the image printed 0.12.22, exit 0).
COPY dist/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl \
 && rm -f /usr/local/bin/uv /usr/local/bin/uvx \
 && rm -rf /tmp/wheels

# /cache holds the plugin environments (about 24 GB once all are built) and the weights. Mount a
# writable volume or folder there from outside the image. It is world-writable so the image also
# works with `docker run --user`.
RUN mkdir -p /cache && chmod 777 /cache
ENV MUSEGAUGE_HOME=/cache
# uv must keep its managed Pythons inside /cache. Without this, /cache/envs/*/bin/python is a
# symlink into /root/.local/share/uv/python of the container that built the environment, and
# every later container finds dead environments on the volume (found 2026-10-06,
# docs/PROGRESS.md M7). With this, the environments survive the container and later runs
# reuse them, as docker/README.md says.
ENV UV_PYTHON_INSTALL_DIR=/cache/uv-python
ENTRYPOINT ["musegauge"]
CMD ["--help"]
