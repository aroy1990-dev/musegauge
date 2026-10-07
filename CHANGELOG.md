# Changelog

## Unreleased

Docker image fixes, found when the M7 checklist was first run on a real Docker machine
(2026-10-06/07; `docs/PROGRESS.md` M7). No metric numbers can move (the locks pin the
environments; the doctor string is not asserted anywhere):

- `docker/Dockerfile` sets `ENV UV_PYTHON_INSTALL_DIR=/cache/uv-python`. Before, the plugin
  environments on a `/cache` volume did not survive the container (`/cache/envs/*/bin/python`
  pointed into the removed container), so a later container found dead environments. Re-verified
  with a fresh volume and a second, `--network none` container.
- The wheel's pip-installed `uv`/`uvx` scripts are removed from `/usr/local/bin` after the
  install, so the Dockerfile-pinned uv (0.12.22) is the effective one; before, the wheel's
  uv 0.12.23 shadowed it through PATH. The image shrank from 788 MB to 740 MB.
- `doctor`'s missing-nvidia-smi WARN now says "no NVIDIA driver *visible*" — in a container
  that usually means the toolkit did not inject nvidia-smi, not that the host has no driver.

## 0.1.1 (2026-10-04)

Docs fixes, project links.

## 0.1.0 (2026-10-03, not published)

First version. No PyPI or TestPyPI upload and no image pushed (D7 is open). The code is under the
Apache License 2.0 (`LICENSE`, decision D2).

Metrics, all at version `@1`:

- `fad.vggish@1`, `fad.clap-laion-music@1`, `fad.encodec-emb@1`: plugin `fad_fadtk`, fadtk 1.1.0, torch 2.7.0
- `kad.vggish@1`, `kad.clap-laion-music@1`: plugin `kad_kadtk`, kadtk 1.1.0, torch 2.5.1
- `clapscore.laion-music@1`: plugin `clapscore_laion`, laion-clap 1.1.7, torch 2.7.0 (harness-defined metric)
- `aesthetics.audiobox@1`: plugin `aesthetics_audiobox`, audiobox-aesthetics 0.0.4, torch 2.7.0

Suites: `t2m-basic@1` (default), `t2m-full@1`.

Commands: `run`, `list`, `info`, `doctor`, `setup`, `clean`, `report`, `validate`.

Install: pip and uvx (tested), Docker `slim` image and Apptainer (written, not built or tested).

Changes from the build spec are listed in `docs/DECISIONS.md` (C1 to C4, A1 to A22). The metric
ids were not bumped during development, because nothing had been released; from this version on,
every change that can move a metric's numbers bumps its `@N` with a line here.
