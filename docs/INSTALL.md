# Install

musegauge 0.1 can be installed and run in four ways. All of them run the same wheel, so the code
and the numbers are the same everywhere. No way is the "main" one. (The spec also had a Docker
`full` image; it is not part of 0.1, see amendment A16 in `docs/DECISIONS.md`.)

| Path | You need | Admin rights | Internet | Tested on the build machine (2026-10-03) |
| --- | --- | --- | --- | --- |
| pip | Python 3.10 or newer | No (use a virtual environment) | First run | **Tested**: wheel installed into a clean `python -m venv`, `--version` and `doctor` ran |
| uvx | uv | No | First run | **Tested from the source folder only** (`uvx --from . musegauge`); the `git+https` form is not tested |
| Docker `slim` | Docker; for GPU the NVIDIA Container Toolkit | Usually yes | First run | **Not built here, not tested** (no Docker on the build machine) |
| Apptainer | Apptainer | Often no | To build the `.sif` and fetch weights | **Not tested** (no Apptainer on the build machine) |

GPU in a container: **not tested**.

## The cache folder (`MUSEGAUGE_HOME`)

musegauge keeps everything it builds and downloads in one folder, `MUSEGAUGE_HOME` (default
`~/.cache/musegauge`; `/cache` in the container image): the plugin environments (`envs/`), the
model weights (`weights/`), the per-run work folders (`work/`) and a hash cache (`refs/`). It must
be writable. The first run that uses all four plugins builds about **24 GB** of environments
there and downloads about 3.7 GB of weights (see "Disk space" below).

## 1. pip

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install git+https://github.com/aroy1990-dev/musegauge
musegauge doctor
musegauge setup --suite t2m-basic --fetch-weights   # optional: build and download ahead of time
musegauge run --generated ./my_audio --prompts prompts.csv --out ./out
```

The core depends on `uv`, so `pip install` brings it; musegauge uses it to build the plugin
environments. The `setup` step is optional: without it, the first `run` builds the environments
and downloads the weights. On the build machine the wheel from `uv build` was installed into a
clean `python3 -m venv` with pip 24.2, and `musegauge --version` and `musegauge doctor` ran
(exit 0).

## 2. uvx (no install)

```bash
uvx --from git+https://github.com/aroy1990-dev/musegauge musegauge run --generated ./my_audio --out ./out
uvx --from . musegauge --version                             # from a source checkout
```

Tested: `uvx --from . musegauge --version` printed `musegauge 0.1.0.dev0` (the version at the time) with uv 0.12.22, and
`uvx --from . musegauge list` worked. The `git+https` form is not tested.

## 3. Docker `slim`

**Not built here, not tested.** Commands and notes: `docker/README.md`. In short:

```bash
uv build
docker build -f docker/Dockerfile --target slim -t musegauge:slim .
docker run --rm --gpus all -v "$PWD/audio:/data/audio:ro" -v musegauge-cache:/cache \
  -v "$PWD/out:/out" musegauge:slim run --generated /data/audio --out /out
```

The image holds only the core, uv and system tools. **`/cache` holds the plugin environments and
the weights.** Mount a writable named volume or host folder there, from outside the image, so it
survives the container; the first run builds about 24 GB of environments into it. No weights are
ever put in an image. The published image name is Roy's decision (D7); docs use the placeholder
`ghcr.io/OWNER/musegauge:TAG`.

## 4. Apptainer

**Not tested** (no Apptainer on the build machine; U8 not checked). The commands of the spec,
with the placeholder image name:

```bash
apptainer build musegauge.sif docker://ghcr.io/OWNER/musegauge:TAG
apptainer run --nv --bind ./audio:/data/audio:ro --bind ./cache:/cache --bind ./out:/out \
  musegauge.sif run --generated /data/audio --out /out
```

The image file system is read only. **The bound folder `./cache` holds the plugin environments
and the weights**: it must be writable, it lives outside the image, and the first run builds
about 24 GB of environments into it. The image sets `MUSEGAUGE_HOME=/cache`, so binding a
writable folder to `/cache` should be enough. How to pass an extra environment variable, if
needed: see `apptainer run --help` (not checked here).

## 5. From source (for contributors)

```bash
git clone https://github.com/aroy1990-dev/musegauge.git && cd musegauge
uv sync --extra dev
uv run pytest            # the fast set; real plugins: docs/TESTING_REAL_PLUGINS.md
```

Tested: with uv 0.12.22, `uv sync --extra dev` set up `.venv` and `uv run pytest` ran the fast
set.

## Offline use (`--no-fetch`)

`--no-fetch` **blocks downloads from libraries that honour the proxy settings, and sets the
Hugging Face offline variables.** For every plugin process it sets `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, and `HTTP_PROXY`/`HTTPS_PROXY` to an address that does not answer
(`http://127.0.0.1:9`, with an empty `NO_PROXY`), so a download or network check by such a
library fails at once and torch.hub uses its cache. **It is best effort, not a guarantee:** a
library that opened network connections without honouring the proxy variables would not be
stopped. For a hard guarantee, cut the network outside the tool, for example a container started
with `--network none`.

Steps:

1. With network: `musegauge setup --all --fetch-weights` (or `--suite NAME`, `--metrics IDS`).
2. Then run with `--no-fetch`. If an environment that the run needs is not built yet,
   `run --no-fetch` stops before anything runs, with exit code 4 and a message that says which
   `musegauge setup` command to run first. It never builds an environment.

Tested on 2026-10-03 **only with the proxy method, not with a truly blocked network** (the build
machine does not allow `unshare -rn`, and has no Docker): all six metrics of `t2m-full` with
`--no-fetch` finished with exit 0, no file was added to any weight cache, and torch.hub reported
"Using cache found in ..." in the FAD and KAD logs. With an empty `MUSEGAUGE_HOME`,
`run --no-fetch` stopped with exit code 4 and the setup hint.

## Network use without `--no-fetch`

Every FAD and KAD run with a VGGish model contacts github.com, even with a full cache: torch.hub
asks GitHub whether the repository has a `main` branch each time it loads VGGish
(`docs/UPSTREAM_NOTES.md`). If GitHub answers with an HTTP error (for example a rate limit), the
run of that metric fails. When the plugin's output shows such an HTTP error from torch.hub,
musegauge reports the error type `NETWORK_ERROR` and suggests retrying, or running
`musegauge setup --fetch-weights` once and then using `--no-fetch`. musegauge does not retry by
itself.

## GPU driver

The plugin environments use the torch builds from PyPI. Each build needs an NVIDIA driver
that supports the CUDA version it was built for. Checked on the builder's machine (driver
560.35.03, which `nvidia-smi` reports as CUDA 12.6):

| torch build | Built for CUDA (`torch.version.cuda`) | Works with driver 560.35.03 | Used by |
| --- | --- | --- | --- |
| 2.7.0+cu126 | 12.6 | yes (checked) | `aesthetics_audiobox`, `clapscore_laion`, `fad_fadtk` |
| 2.5.1+cu124 | 12.4 | yes (checked) | `kad_kadtk` |

The newest torch on PyPI when this was written (2.14.1) did not use CUDA with this driver: it
printed "The NVIDIA driver on your system is too old (found version 12060)". Without a usable
GPU the plugins run on the CPU.

## Disk space

Measured on 2026-10-03 with all four plugins set up (`musegauge clean` shows the same sizes):

| What | Where | Size |
| --- | --- | --- |
| Plugin environments | `$MUSEGAUGE_HOME/envs/` (or `MUSEGAUGE_ENVS_DIR`) | about 24 GB (23 GiB) |
| ... of which fadtk's own copy of three CLAP checkpoints | `envs/fad_fadtk-*/lib/python3.11/site-packages/fadtk/.model-checkpoints/` | 4.9 GB |
| ... of which kadtk's own copy of the same three checkpoints | `envs/kad_kadtk-*/lib/python3.11/site-packages/kadtk/.model-checkpoints/` | 4.9 GB |
| Weights cache (Hugging Face, torch.hub) | `$MUSEGAUGE_HOME/weights/` | about 3.7 GB (3.5 GiB) |

fadtk and kadtk download `630k-audioset-best.pt`, `CLAP_weights_2023.pth` and
`music_audioset_epoch_15_esc_90.14.pt` into their own package folders the first time they run,
even for `vggish` (amendment A8). Each keeps its own copy. They are inside the environments, so
`musegauge clean --envs` removes them (and `musegauge setup --fetch-weights` downloads them again).
`musegauge clean --weights` removes the weights cache. uv keeps its own package cache in
`~/.cache/uv`; `uv cache clean` empties it.

## Reference sets are embedded again on every run

Since amendment A9, the reference folder is staged fresh for every run, so fadtk and kadtk
compute the reference embeddings again each time. For a large reference set this costs time on
every run. It prevents a wrong number: a reused reference folder once mixed CPU-made reference
statistics into a GPU run. The bundled `fma_pop` statistics are not affected.

## Shared machines: limit CPU threads

On a CPU run, fadtk and kadtk start several worker processes (`--workers`, default
`min(8, CPU count)`), and torch in each worker uses one thread per core. On a 256-core machine
this meant more than 2,000 busy threads and a load average around 700. On a shared machine, use
`--threads N`:

```bash
musegauge run --generated ./my_audio --threads 4 --out ./out
```

This sets `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `NUMEXPR_NUM_THREADS`
to N in each plugin. Without the flag nothing is set and the tools behave exactly as upstream.
CPU numbers depend slightly on the thread count (about 1e-6 here, see `docs/METRICS.md`), and
`results.json` records the setting, so compare runs made with the same setting. You can also run
musegauge under `nice -n 19` and `taskset -c 0-15` (16 cores), which is how the tests were run on
the build machine.


## sox without admin rights (optional)

No plugin in 0.1 runs sox: fadtk 1.1.0 and kadtk 1.1.0 convert audio with torchaudio (amendment
A6 in `docs/DECISIONS.md`). `musegauge doctor` reports a missing sox as WARN only. These steps are
kept for later plugins that may need it. musegauge finds sox through the environment variable
`SOX_PATH` (a path to the binary), or else on `PATH`. If you cannot use `apt-get` or `brew`, you
can install sox from conda-forge into a folder you own.

These steps were run on 2026-10-03 on Ubuntu 24.04 (x86_64) with conda 24.9.2. They gave
SoX v14.4.2 from conda-forge.

```bash
# 1. Install sox into a folder you own (here ~/tools/sox; pick any folder).
conda create -y -p ~/tools/sox --override-channels -c conda-forge sox

# 2. Check that it runs without activating the conda environment.
env -i ~/tools/sox/bin/sox --version

# 3. Tell musegauge where it is. Put this line in your shell start-up file to keep it.
export SOX_PATH=~/tools/sox/bin/sox

# 4. Check: the sox line should say OK and "via SOX_PATH" (WARN if sox is missing).
musegauge doctor
```

`--override-channels -c conda-forge` uses only the conda-forge channel. Any conda or mamba
installation works for step 1. musegauge does not need the conda environment to be activated.

Checked: with WAV and FLAC files at 16, 32 and 44.1 kHz, fadtk and kadtk worked without sox and
called sox only as `sox -h` (`docs/VERIFIED_FACTS.md`). Other formats (mp3, ogg) were not tested.

ffmpeg is optional (`doctor` reports it as WARN when missing). On the builder's machine it came
from the system (`/usr/bin/ffmpeg`, version 6.1.1), so no separate install was tested.

