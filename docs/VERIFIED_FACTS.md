# Verified facts

Facts checked by the builder on this machine, with the command and the date.
Dates are local time (+08:00). Facts F1 to F17 from the spec are re-checked by
`scripts/verify_facts.py` where the spec asks for it.

## This machine

Checked 2026-10-03.

| Item | Result | Command |
| --- | --- | --- |
| OS | Ubuntu 24.04.1 LTS, Linux 6.8.0-48-generic, x86_64. Running as root inside a container, no sudo. | `uname -a`, `cat /etc/os-release` |
| Pythons | Only 3.12: `~/miniconda3/bin/python3.12` (3.12.7) and `/usr/bin/python3.12` (3.12.3). No 3.9, 3.10, 3.11 or 3.13. This differs from F16 (the research sandbox). uv downloaded CPython 3.11.17 into `~/.local/share/uv/python/` during the U1 check. | `command -v python3.X`, `uv python list --only-installed` |
| uv | Not installed system-wide. Installed with pip into the project `.venv`: uv 0.12.22. `uv.find_uv_bin()` returned `.venv/bin/uv`. | `pip install uv`, `uv --version` |
| sox | **Not found.** fadtk needs it (F10). Not needed before M5. | `command -v sox` |
| ffmpeg | `/usr/bin/ffmpeg` | `command -v ffmpeg` |
| Docker, Apptainer, Singularity, Podman | **Not found.** | `command -v docker apptainer singularity podman` |
| unzip | Not found. Use `python -m zipfile -l` to list a wheel. | `command -v unzip` |
| GPU | 6 × NVIDIA L40S (46 GB), driver 560.35.03, CUDA 12.6. At check time every GPU showed 99 % utilisation and 8 to 15 GB in use by other processes. | `nvidia-smi --query-gpu=index,name,driver_version,memory.used,memory.total,utilization.gpu --format=csv` |
| Network | pypi.org, huggingface.co and github.com answer HTTP 200. | `curl -w "%{http_code}"` |
| Disk | 167 GB free on `/` (95 % used). `/tmp` and `~/.cache` are on the same file system. | `df -h` |

## U10: uv version and flags

Checked 2026-10-03 with uv 0.12.22. Every flag below appears in the `--help` output of this version.

| Planned use | Flag or variable | Found in |
| --- | --- | --- |
| Make a plugin environment | `uv venv --python <spec> <dir>` (`-p, --python`) | `uv venv --help` |
| Install a lock into it | `uv pip install --python <dir>/bin/python -r <lock>` (`-p, --python`, `-r, --requirements`) | `uv pip install --help` |
| Hash checking on install | `--require-hashes` exists. `--no-verify-hashes` exists, so hashes in the file are verified by default. | `uv pip install --help` |
| Make a lock | `uv pip compile --python-version <v> --python-platform <p> --generate-hashes -o <file>` | `uv pip compile --help` |
| Platform values | Include `linux`, `x86_64-unknown-linux-gnu`, `x86_64-manylinux_2_17` ... `x86_64-manylinux_2_40`, `aarch64-apple-darwin` | `uv pip compile --help` |
| No Python downloads | `--no-python-downloads`, which the help text maps to `UV_PYTHON_DOWNLOADS=never`. The value `manual` is also accepted: a bad value gives `expected one of 'auto', 'true', 'manual', 'never', or 'false'`. | `uv venv --help`, `UV_PYTHON_DOWNLOADS=bogus uv python find 3.12` |
| Where managed Pythons go | `UV_PYTHON_INSTALL_DIR` is honoured: `uv python dir` printed the folder it was set to. | `UV_PYTHON_INSTALL_DIR=<dir> uv python dir` |
| Offline install | `uv pip install --offline` | `uv pip install --help` |
| Build | `uv build` with `--wheel`, `--sdist`, `-o, --out-dir` | `uv build --help` |
| Contributor setup | `uv sync --extra dev` worked: it installed the project in editable mode plus pytest, jsonschema and ruff into `.venv`. `uv run` exists. | `uv sync --extra dev`, `uv run --help` |
| No-install run | `uvx --from <path>` and `uv tool run` exist | `uvx --help`, `uv tool run --help` |

Two more uv behaviours, checked 2026-10-03:

- `uv pip install -r FILE` with an empty file, or a file with only a comment, prints `warning: Requirements file ... does not contain any dependencies` and exits 0. This also works with `--offline`. So a plugin with no dependencies can use an empty lock.
- `UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 DIR` used `~/miniconda3` (3.12.7) with no network access needed.

## Build backend

Checked 2026-10-03: `uv pip install --python .venv/bin/python hatchling --dry-run` exit 0, would install `hatchling==1.32.4` and 5 dependencies.

## pytest marker selection

Checked 2026-10-03 with pytest 9.1.1: with `addopts = "-m 'not slow'"` in the config, `pytest` deselects slow tests, and `pytest -m slow` on the command line replaces the default and runs only them.

## U1: does each plugin lock, install and import?

Checked 2026-10-03 with uv 0.12.22 on CPython 3.11.17. This first check used only the upstream pin in `requirements.in` (no torch pairing), to see what a plain resolve gives. It is not the final lock; M3 to M5 make the real locks.

Command per package (full log: kept by the builder, not committed):

```text
uv pip compile X.in --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --generate-hashes -o X.lock
uv venv --python 3.11 env_X
uv pip install --python env_X/bin/python -r X.lock
env_X/bin/python -c "import <module>"
```

| `requirements.in` | Lock | Install | Import | Resolved versions |
| --- | --- | --- | --- | --- |
| `fadtk==1.1.0` | OK | OK | OK | torch 2.14.1, torchvision 0.29.1, torchaudio 2.11.0, numpy 1.26.4, transformers 4.57.6, laion-clap 1.1.7 |
| `kadtk==1.1.0` | OK | OK | **FAIL**: `OSError: libcudart.so.13: cannot open shared object file` while importing torchaudio | torch 2.5.1, torchaudio **2.11.0** (mismatch, see U3), torchvision 0.20.1, tensorflow 2.21.0, keras 3.15.1, kapre 0.3.6, numba 0.58.1, numpy 1.26.4, transformers 4.46.3 |
| `laion-clap==1.1.7` and `huggingface_hub` | OK | **FAIL**: `Failed to build tokenizers==0.10.3` (source build) | not reached | huggingface-hub 2.1.1, transformers **4.12.2**, numpy 1.26.4, numba 0.68.0, llvmlite 0.50.0 |
| `audiobox-aesthetics==0.0.4` | OK | OK | OK | torch 2.14.1, torchaudio 2.11.0, numpy 2.4.6 |

Follow-up checks, same day:

- **kadtk with a matched pair.** `uv pip install --python env_kad/bin/python torchaudio==2.5.1` (to match torch 2.5.1), then `import kadtk`: OK. torch `2.5.1+cu124`, torchaudio `2.5.1+cu124`, `torch.cuda.is_available()` True.
- **Does `import kadtk` pull in TensorFlow at import time?** Yes. After `import kadtk`, `"tensorflow" in sys.modules` is `True` (tensorflow 2.21.0). For fadtk and audiobox_aesthetics it is `False`.
- **Why laion-clap failed.** The unconstrained `huggingface_hub` resolved to 2.1.1. The resolver then went back to transformers 4.12.2, which needs `tokenizers==0.10.3`. That version has no wheel for Python 3.11 and its source build failed. The M4 lock needs a constraint that avoids this. Not fixed here.
- **torch 2.14.1 on this GPU.** Importing fadtk with torch 2.14.1 printed `UserWarning: CUDA initialization: The NVIDIA driver on your system is too old (found version 12060)`. The PyPI wheel of torch 2.14.1 loads CUDA 13 libraries; this driver supports CUDA 12.6.

## U2: does fadtk 1.1.0 run on the target GPU with the torch 2.7 line?

Partly checked 2026-10-03. In a scratch environment made with
`uv pip install --python env_fad27/bin/python fadtk==1.1.0 torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0`:
`import fadtk` OK, torch `2.7.0+cu126`, `torch.version.cuda` 12.6, `torch.cuda.is_available()` True,
6 devices, `NVIDIA L40S`, driver 560.35.03.

Answered in M5 (2026-10-03): fadtk 1.1.0 runs on the GPU with the torch 2.7 line. The golden
cases of `tests/golden/fad_fadtk.json` ran with torch 2.7.0+cu126 on an NVIDIA L40S, driver
560.35.03 (see `docs/PROGRESS.md`, M5). fadtk does not need sox (next entry).

## U3: does `torchaudio.load` work in the Audiobox environment?

Checked 2026-10-03.

torch pin declared by each torchaudio version on PyPI (`https://pypi.org/pypi/torchaudio/<v>/json`, field `requires_dist`):

| torchaudio | torch requirement |
| --- | --- |
| 2.5.1 | `torch==2.5.1` |
| 2.6.0 | `torch==2.6.0` |
| 2.7.0 | `torch==2.7.0` |
| 2.7.1 | `torch==2.7.1` |
| 2.8.0 | `torch==2.8.0` |
| 2.9.0 | `torch==2.9.0` |
| 2.10.0 | `torch==2.10.0` |
| 2.11.0 | **none listed** |

torchaudio 2.11.0 does not declare a torch requirement, so a resolver can pair it with any torch. This explains the mismatch the spec mentions, and the kadtk import failure in U1.

torchvision for comparison (same method): 0.20.1 needs `torch==2.5.1`, 0.21.0 needs `torch==2.6.0`, 0.22.0 needs `torch==2.7.0`, 0.22.1 needs `torch==2.7.1`.

`torchaudio.load` results (`python -c "import torchaudio; print(torchaudio.load('x.wav')[1])"`, x.wav is 1 s of silence, 16 kHz, written with soundfile):

- Plain resolve (torch 2.14.1, torchaudio 2.11.0): **fails** with `ImportError: TorchCodec is required for load_with_torchcodec. Please install torchcodec to use this function.`
- Matched pair `audiobox-aesthetics==0.0.4 torch==2.7.0 torchaudio==2.7.0`: works, prints sample rate 16000, shape (1, 16000). `torch.cuda.is_available()` True.

The final lock for M3 is not made yet.

## U4: licences of weight files

Read 2026-10-03. These are what the pages state. Manifests keep `status: unknown` and `commercial_ok: unknown` until Roy decides (rule 5), except where the spec itself says otherwise (CLAP weights, section 9.4).

| Weights | Where read | What the page states |
| --- | --- | --- |
| VGGish (torch port) | `curl https://api.github.com/repos/harritaylor/torchvggish/license`; README | Repository licence Apache-2.0 (file `LICENSE`). Release `v0.1` holds `vggish-10086976.pth`, `vggish_pca_params-4d878af3.npz`, `vggish_pca_params-970ea276.pth`. README: "The weights are ported directly from the tensorflow model" (tensorflow/models, research/audioset). Whether the repository licence covers the weight files: not stated. |
| LAION-CLAP | `curl https://huggingface.co/api/models/lukewys/laion_clap` | `cardData.license: cc0-1.0`. Files include `music_audioset_epoch_15_esc_90.14.pt` and `630k-audioset-best.pt`. Not gated. |
| Audiobox Aesthetics | `curl https://huggingface.co/api/models/facebook/audiobox-aesthetics` | `cardData.license: cc-by-4.0`. Files: `checkpoint.pt`, `model.safetensors`, `config.json`. Not gated. |
| EnCodec 24 kHz | `curl https://huggingface.co/api/models/facebook/encodec_24khz` | No licence field in the card metadata. Which EnCodec source fadtk's `encodec-emb` loads: not checked yet (M5). |
| MS-CLAP | `curl https://huggingface.co/api/models/microsoft/msclap` | `cardData.license: ms-pl`. Not used by any 0.1 metric. |
| fma_pop statistics (bundled in fadtk) | not checked | unknown |
| PANNs (zenodo, kadtk) | not checked | unknown |

## U5: can soundfile read mp3 here?

Checked 2026-10-03 in the core `.venv`: soundfile 0.14.0, libsndfile 1.2.2. `sf.available_formats()` includes `'MP3': 'MPEG-1/2 Audio'`. A 2 s mp3 made with `ffmpeg -f lavfi -i sine=frequency=440:duration=2 -ar 44100 t.mp3` gave `sf.info`: 44100 Hz, 1 channel, 88200 frames, 2.0 s, and `sf.read` returned shape (88200,). **Yes, mp3 works on this machine with this soundfile version.**

## Correction of F10: fadtk 1.1.0 and kadtk 1.1.0 do not need sox (2026-10-03)

The spec's F10 ("fadtk needs the SoX program") came from reading the source. It does not hold for
these versions:

- **Source.** `fadtk/fad.py` line 24 and `kadtk/emb_loader.py` line 19 hard-code
  `TORCHAUDIO_RESAMPLING = True`, so audio is loaded and resampled with torchaudio. The sox and
  ffmpeg paths are reached only when that constant is False. With no sox anywhere,
  `ENV/bin/fadtk vggish ref_small gen_small out.csv -w 4` exited 0 (FAD 6.404002057871558) and
  `kadtk vggish ...` exited 0 (KAD 6.871640682220459).
- **Runs with a logging fake sox (the A6 check, section "A6 rechecked" below).** With WAV and FLAC
  files at 16, 32 and 44.1 kHz, sox was only ever called as `sox -h` (to list its formats, answer
  ignored), never on an audio file, and fadtk and kadtk converted every file and worked without
  sox.
- **Not tested:** other formats such as mp3 and ogg.

Reported to Roy; amendment A6.

## U6: how many clips does FAD-inf need?

Checked 2026-10-03. fadtk gives **no error** with a tiny set. `score_inf` uses `min_n=500`
embedding *frames* and 25 steps; with 12 clips of 10 s (about 120 VGGish frames) it samples with
replacement and returns a value:

```text
$ fadtk vggish ref_small gen_small inf.csv --inf -w 4   (run 1)
FAD-inf Information: FADInfResults(score=6.464296598454074, slope=14.989206948055976, r2=0.005534650601726643, ...)
$ fadtk vggish ref_small gen_small inf.csv --inf -w 4   (run 2)
FAD-inf Information: FADInfResults(score=6.624542887338677, slope=-38.654331053814595, r2=0.09006413593421192, ...)
```

No minimum clip count is documented or enforced. The low r² and the change between runs show the
number is not reliable on such small sets; the harness does not invent a threshold.

## U7: Docker base image tags and the uv Docker pattern

- `docker manifest inspect`: **not checked here**, Docker is not installed. Instead, on 2026-10-03
  the registries' HTTP APIs were asked (used in `docker/Dockerfile`):
  - `curl -s https://hub.docker.com/v2/repositories/library/python/tags/3.12-slim-bookworm`:
    name `3.12-slim-bookworm`, last_updated 2026-10-02T05:09:13Z, digest `sha256:54c85f3c47607a77...`,
    architectures include amd64 and arm64.
  - `ghcr.io/v2/astral-sh/uv/manifests/0.12.22` (with an anonymous pull token): HTTP 200, an OCI
    image index with amd64 and arm64.
- uv Docker guide, read 2026-10-03 (`curl -sL https://docs.astral.sh/uv/guides/integration/docker/`). It shows these ways to get uv into an image: `COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /uvx /bin/` (it recommends a fixed version tag or an image digest over `latest`), and `ADD https://astral.sh/uv/0.12.22/install.sh /uv-installer.sh`. Image tags follow `ghcr.io/astral-sh/uv:{major}.{minor}.{patch}`. To use in M7.

## U8: Apptainer commands

**Not checked here.** Apptainer and Singularity are not installed (checked again 2026-10-03).
`docs/INSTALL.md` marks the Apptainer path "not tested".

## U9: is the name `musegauge` free on GitHub?

Checked 2026-10-03:

- `curl -s "https://api.github.com/search/repositories?q=musegauge+in:name"` gave `total_count 0`.
- `curl -s "https://api.github.com/search/users?q=musegauge"` gave `total_count 0`.
- `https://github.com/musegauge` gave HTTP 404.
- `https://pypi.org/pypi/musegauge/json` gave HTTP 404 (still free on PyPI).

No public repository, user or organisation named `musegauge` was found. Roy still decides the name (D1).

## Numbers used for lower bounds in pyproject.toml

None. No lower bound was added.

## GPU and torch checks per plugin environment

Before each GPU check, `nvidia-smi --query-gpu=index,name,memory.used,memory.free,utilization.gpu --format=csv`
was run and the GPU with the most free memory was used alone (`CUDA_VISIBLE_DEVICES`). The GPUs
were shared with other jobs at 99 % utilisation.

| Environment | Date | GPU used | Driver | torch | `torch.version.cuda` | `torch.cuda.is_available()` | Small GPU op (512×512 matmul) | torchaudio load of a 32 kHz WAV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `aesthetics_audiobox-76e395f1` | 2026-10-03 | 5, NVIDIA L40S (39,402 MiB free) | 560.35.03 | 2.7.0+cu126 | 12.6 | True | OK, finite result | OK: 32000 Hz, shape (1, 320000), backends `['ffmpeg', 'soundfile']` |
| `clapscore_laion-a3ecbe8b` | 2026-10-03 | 0, NVIDIA L40S (most free at the time) | 560.35.03 | 2.7.0+cu126 | 12.6 | True | OK, finite result | not used by this plugin (librosa loads audio) |
| `fad_fadtk-f7a67ac7` | 2026-10-03 | 2, NVIDIA L40S (34,999 MiB free) | 560.35.03 | 2.7.0+cu126 | 12.6 | True | OK, finite result | fadtk loads audio itself (torchaudio, soundfile backend) |
| `kad_kadtk-391cfe89` | 2026-10-03 | 2, NVIDIA L40S (34,999 MiB free) | 560.35.03 | 2.5.1+cu124 | 12.4 | True | OK, finite result | kadtk loads audio itself (torchaudio) |

U3 is answered for the audiobox lock: torch 2.7.0 and torchaudio 2.7.0 are pinned as a pair
(`torchaudio 2.7.0` requires `torch==2.7.0` on PyPI) and `torchaudio.load` works.

## A6 rechecked: sox with several sample rates and FLAC (2026-10-03)

A fake `sox` was put first on `PATH` and in `SOX_PATH`; it logs every call and exits 1. fadtk and
kadtk ran (`nice -n 19 taskset -c 0-15`, CPU) on six files: the mixed_rates fixture at 16000,
32000 and 44100 Hz, each as 16-bit WAV and as FLAC, against `ref_small`:

```text
$ ... ENV/bin/fadtk vggish ref_fad gen_fad fad.csv -w 2
exit code: 0; score: 8.440816605083569
converted files (16 kHz): rate_16000_flac.wav rate_16000.wav rate_32000_flac.wav rate_32000.wav rate_44100_flac.wav rate_44100.wav
$ ... ENV/bin/kadtk vggish ref_kad gen_kad --csv kad.csv --device cpu -w 2
exit code: 0; score: 8.853960037231445
converted files (16 kHz): rate_16000_flac.wav rate_16000.wav rate_32000_flac.wav rate_32000.wav rate_44100_flac.wav rate_44100.wav
--- every call the fake sox received:
10:48:45 sox called with: -h
(10 calls in total, all `-h`)
```

sox is never called on an audio file. When a `sox` exists, both tools call `sox -h` at start
(`find_sox_formats`, to list formats) and ignore the answer; when it does not exist, nothing is
called. torchaudio converts every file. A6 (sox not required, `doctor` WARN) stands.

## CPU results depend on the thread count (2026-10-03)

| Check | Result |
| --- | --- |
| `torch.get_num_threads()` in the fad environment | 128 with all 256 cores; 16 under `taskset -c 0-15` |
| Harness with `--threads 4` against golden runs with default threads (128) | `fad.vggish@1` `fad`: 6.404003361929213 vs 6.404002057871558, difference 1.3e-6; `aesthetics.audiobox@1`: 3 of 48 values outside 1e-6, largest difference 2.86e-6 |
| Harness under `taskset -c 0-15` (16 threads) against golden runs with 128 threads | `fad.vggish@1`: difference 3.6e-15; `aesthetics.audiobox@1`: 2 of 48 values outside 1e-6, largest difference 4.77e-6 |

So CPU golden numbers are recorded and compared at the same core count (they store
`cpu_cores`), and the `--threads 4` check is kept as a documented expected difference.

## `unshare -rn` is not allowed in this container (2026-10-03)

```text
$ unshare -rn sh -c 'id -u'
unshare: unshare failed: Operation not permitted
```

An offline test therefore cannot cut the network with a user namespace here (see M7).

## M7 checks (2026-10-03)

- **pip path:** `python3 -m venv` (pip 24.2), `pip install dist/musegauge-0.1.0.dev0-py3-none-any.whl`,
  then `musegauge --version` printed `musegauge 0.1.0.dev0` and `musegauge doctor` exited 0 (sox WARN).
  `uv.find_uv_bin()` returned the uv inside that venv.
- **uvx path:** `uvx --from . musegauge --version` printed `musegauge 0.1.0.dev0` (uv 0.12.22).
- **GitHub Actions used in the workflows:** `actions/checkout@v4`, `actions/setup-python@v5` and
  `actions/cache@v4` exist (`curl https://api.github.com/repos/<repo>/git/ref/tags/<tag>`: HTTP 200).
  The workflows themselves have not run (no GitHub remote).
- **torch.hub behind an unreachable proxy** (both torch 2.7.0+cu126 and 2.5.1+cu124 have the
  `URLError` cache fallback in `torch/hub.py`):

  ```text
  $ env -i ... TORCH_HOME=<weights>/torch HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY= ENV/bin/python ...
  Using cache found in ~/.cache/musegauge/weights/torch/hub/harritaylor_torchvggish_master
  direct request to github.com: URLError - [Errno 111] Connection refused
  torch 2.7.0+cu126 | torch.hub.load(vggish) OK: VGGish
  (same result in the kad environment with torch 2.5.1+cu124)
  ```

- **`--no-fetch` end to end:** `musegauge run --generated gen_small --prompts prompts.csv
  --reference ref_small --suite t2m-full --no-fetch` (GPU 1, `nice -n 19 taskset -c 16-31`): all six
  metrics `ok`, exit 0; files in the weight caches before / after: 82 / 82; no `NETWORK_FETCH`;
  "Using cache found in" 17 times in each of the FAD and KAD logs. `unshare -rn` is not permitted
  here, so this is the proxy test, not a removed network.

