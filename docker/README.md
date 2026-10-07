# Docker image

One target in `docker/Dockerfile`: **`slim`** (spec section 8.3). It holds the musegauge core, uv
and the system tools (sox, ffmpeg, ca-certificates, curl). There is no `full` image in 0.1
(amendment A16; the reason is in `docs/IDEAS.md`). No model weights are ever put in an image.

**Status: built and tested 2026-10-06/07** on a separate Linux x86_64 machine with Docker 27.3.1 (the
builder's machine has no Docker): build, `doctor`, the `ci.yml` fake-plugin run with
`--network none`, `setup --all --fetch-weights` into a named volume, an offline
`--network none --no-fetch` run of `t2m-full`, and GPU use with `--gpus all` all passed; log
excerpts in `docs/PROGRESS.md` M7. Testing found one bug — the environments on a `/cache`
volume did not survive the container — and one pin violation — the wheel's uv 0.12.23
shadowed the pinned 0.12.22 — both **fixed on main on 2026-10-07** and re-verified with a
rebuilt image and a fresh volume (`docs/PROGRESS.md` M7, "Fixes after the M7 checklist").
The `v0.1.1` tag carries both; there, pass `-e UV_PYTHON_INSTALL_DIR=/cache/uv-python` and
build the environments once with it. The base image tag and the uv image tag were checked
through the registries' HTTP APIs on 2026-10-03 (`docs/VERIFIED_FACTS.md`, U7).

## The cache folder `/cache`

`/cache` (`MUSEGAUGE_HOME`) holds everything musegauge builds and downloads: the plugin
environments and the model weights. It must be **writable** and **mounted from outside the
image** (a named volume or a host folder), so it survives the container. The first run builds the
environments there: about **24 GB** for all four plugins, plus about 3.7 GB of weights. Later runs
reuse them.

Measured on 2026-10-06 (`docs/PROGRESS.md` M7): the *environments* did not survive the
container — `/cache/envs/*/bin/python` was a symlink into the removed container, because uv
keeps its managed Pythons in `/root/.local/share/uv/python` unless told otherwise. **Fixed on
main on 2026-10-07**: the Dockerfile sets `ENV UV_PYTHON_INSTALL_DIR=/cache/uv-python`, so
the managed Pythons live on the volume and later containers reuse the environments
(re-verified with a fresh volume and a second, offline container). On the `v0.1.1` tag, pass
`-e UV_PYTHON_INSTALL_DIR=/cache/uv-python` (and build the environments once with it)
instead; the weights are unaffected.

## Build

```bash
uv build                                   # makes dist/musegauge-*.whl
docker build -f docker/Dockerfile --target slim -t musegauge:slim .
```

The plugin lock files are for linux-x86_64, so build and run on linux/amd64.

## Run

```bash
docker run --rm -v musegauge-cache:/cache musegauge:slim doctor
docker run --rm --gpus all \
  -v "$PWD/audio:/data/audio:ro" \
  -v "$PWD/prompts.csv:/data/prompts.csv:ro" \
  -v musegauge-cache:/cache \
  -v "$PWD/out:/out" \
  musegauge:slim run --generated /data/audio --prompts /data/prompts.csv --out /out
```

The input folders can be mounted read only: musegauge stages audio into its own folders.
`--gpus all` needs the NVIDIA Container Toolkit on the host. GPU use inside a container was
tested on 2026-10-06 with `--gpus all`: `torch.cuda.is_available()` was True in all four plugin
environments (`docs/PROGRESS.md` M7).

## Offline use

Fill the cache once with network, then run with no network at all. `--network none` cuts the
network outside the tool, which is the hard guarantee; `--no-fetch` on its own is best effort
(`docs/INSTALL.md`).

```bash
docker run --rm -v musegauge-cache:/cache musegauge:slim setup --suite t2m-basic --fetch-weights
docker run --rm --network none -v musegauge-cache:/cache -v "$PWD/audio:/data/audio:ro" -v "$PWD/out:/out" \
  musegauge:slim run --generated /data/audio --out /out --no-fetch
```

The image name on a public registry is Roy's decision (D7); docs use `ghcr.io/OWNER/musegauge:TAG`.
