# Progress

Acceptance output per milestone (spec section 12). Output is pasted as it was printed.

## M0. Bootstrap and verify facts

Date: 2026-10-03. Status: **passed**.

Unchecked facts U1 to U10 are answered in `docs/VERIFIED_FACTS.md`. Not checked here: U2 (fadtk
run, needs sox), U6 (needs fadtk run, needs sox), U7 `docker manifest inspect` (no Docker), U8 (no
Apptainer).

```text
$ python scripts/verify_facts.py
PASS  fadtk==1.1.0  requires_python expected '<=3.13,>=3.10'  found '<=3.13,>=3.10'
PASS  fadtk==1.1.0  requires_dist expected 'torchvision>=0.22.0'  found 'torchvision>=0.22.0'
PASS  torchvision==0.22.0  requires_dist expected 'torch==2.7.0'  found 'torch==2.7.0'
PASS  kadtk==1.1.0  requires_python expected '<3.12,>=3.9'  found '<3.12,>=3.9'
PASS  kadtk==1.1.0  requires_dist expected 'torch<2.6,>=2.1'  found 'torch<2.6,>=2.1'
PASS  audiobox-aesthetics==0.0.4  requires_python expected '>=3.9'  found '>=3.9'
PASS  audiobox-aesthetics==0.0.4  requires_dist expected 'torch>=2.2.0'  found 'torch>=2.2.0'
PASS  laion-clap==1.1.7  requires_dist expected 'numpy<2.0.0,>=1.23.5'  found 'numpy<2.0.0,>=1.23.5'
8 of 8 checks passed
exit code: 0

$ uv --version
uv 0.12.22 (x86_64-unknown-linux-gnu)

$ uv run pytest
============================= test session starts ==============================
platform linux -- Python 3.12.7, pytest-9.1.1, pluggy-1.6.0
rootdir: ~/musegauge
configfile: pyproject.toml
testpaths: tests
collected 4 items

tests/unit/test_verify_facts.py ...                                      [ 75%]
tests/unit/test_version.py .                                             [100%]

============================== 4 passed in 0.02s ===============================
exit code: 0

$ uv run ruff check
All checks passed!
exit code: 0
```

The uv flags planned for use are listed with their `--help` source in `docs/VERIFIED_FACTS.md`
(section U10).


## M1. Core skeleton with fake plugins

Date: 2026-10-03. Status: **passed, waiting at GATE 1**.

### Fast test set

```text
$ uv run pytest
============================= test session starts ==============================
platform linux -- Python 3.12.7, pytest-9.1.1, pluggy-1.6.0
rootdir: ~/musegauge
configfile: pyproject.toml
testpaths: tests
collected 187 items / 1 deselected / 186 selected

tests/integration/test_e2e_fakes.py ...........                          [  5%]
tests/unit/test_cli.py ........                                          [ 10%]
tests/unit/test_clips.py ......................                          [ 22%]
tests/unit/test_config.py .......                                        [ 25%]
tests/unit/test_envs.py ........                                         [ 30%]
tests/unit/test_errors.py ..                                             [ 31%]
tests/unit/test_registry.py ...............................              [ 47%]
tests/unit/test_results.py ..............                                [ 55%]
tests/unit/test_runner.py ..........                                     [ 60%]
tests/unit/test_runtime.py .............                                 [ 67%]
tests/unit/test_schemas.py ..............................                [ 83%]
tests/unit/test_staging.py ...........                                   [ 89%]
tests/unit/test_stats.py ............                                    [ 96%]
tests/unit/test_verify_facts.py ...                                      [ 97%]
tests/unit/test_version.py .                                             [ 98%]
tests/unit/test_warnings.py ...                                          [100%]

====================== 186 passed, 1 deselected in 12.00s ======================
exit code: 0

$ uv run ruff check
All checks passed!
exit code: 0
```

### End-to-end run with fake_clip and fake_set

Run with the built wheel installed into a clean virtual environment (not the editable
development install), on fixtures from `tests/make_fixtures.py`.

```text
$ uv build
Successfully built dist/musegauge-0.1.0.dev0.tar.gz
Successfully built dist/musegauge-0.1.0.dev0-py3-none-any.whl
$ uv venv --python 3.12 wheelenv && uv pip install --python wheelenv/bin/python dist/musegauge-0.1.0.dev0-py3-none-any.whl
installed: musegauge 0.1.0.dev0 at .../gate1/wheelenv/lib/python3.12/site-packages/musegauge/__init__.py

$ MUSEGAUGE_HOME=./home MUSEGAUGE_PLUGIN_PATH=<repo>/tests/fake_plugins musegauge run --generated fixtures/gen_small --prompts fixtures/prompts.csv --reference fixtures/ref_small --metrics fake.clip@1,fake.set@1 --out out
musegauge: 12 clip(s) readable, 0 skipped
musegauge: reference: 12 of 12 audio files readable
musegauge: run 20261002T164917Z-478d0c, output .../gate1/out
musegauge: plugin fake_clip: preparing environment
musegauge: metric fake.clip@1: running
musegauge: metric fake.clip@1: ok
musegauge: plugin fake_set: preparing environment
musegauge: metric fake.set@1: running
musegauge: metric fake.set@1: ok
musegauge: wrote .../gate1/out/results.json
exit code: 0

$ python -c "jsonschema.validate(results.json, results.schema.json); musegauge.schemas.check(...)"
jsonschema (Draft 2020-12): valid
musegauge built-in validator: valid
exit code: 0

$ find out -type f | sort
out/logs/fake_clip.log
out/logs/fake_set.log
out/per_clip/fake.clip@1.csv
out/requests/fake.clip@1.request.json
out/requests/fake.set@1.request.json
out/responses/fake.clip@1.response.json
out/responses/fake.set@1.response.json
out/results.json

$ ls home/work  (work folder cleaned after the run)
total 8
drwxr-xr-x 2 root root 4096 Oct  3 00:49 .
drwxr-xr-x 5 root root 4096 Oct  3 00:49 ..
```

The sample `results.json` from that run:

```json
{
  "schema": 1,
  "suite": null,
  "tool": {
    "name": "musegauge",
    "version": "0.1.0.dev0",
    "git_commit": null,
    "uv_version": "0.12.22",
    "python": "3.12.7",
    "platform": "linux-x86_64"
  },
  "run": {
    "run_id": "20261002T164917Z-478d0c",
    "started_utc": "2026-10-02T16:49:17Z",
    "finished_utc": "2026-10-02T16:49:17Z",
    "command": "musegauge run --generated fixtures/gen_small --prompts fixtures/prompts.csv --reference fixtures/ref_small --metrics fake.clip@1,fake.set@1 --out out",
    "seed": 0,
    "device_requested": "auto",
    "reproducible": true
  },
  "generated": {
    "n_clips": 12,
    "n_skipped": 0,
    "skipped": [],
    "n_with_prompt": 12,
    "total_duration_s": 120.0,
    "sample_rates_hz": {
      "32000": 12
    },
    "duration_s": {
      "min": 10.0,
      "median": 10.0,
      "max": 10.0
    },
    "manifest_sha256": "274ac46242361e3280d328714e3539e2664d726873af9c372a00dbff61f7a4b8",
    "extra": {}
  },
  "reference": {
    "kind": "dir",
    "name": null,
    "ref_hash": "e38692a8aea06972572f25e5eaffd79cea62a9dd44601347cf07f098a5825ded",
    "n_clips": 12,
    "total_duration_s": 120.0
  },
  "metrics": [
    {
      "metric_id": "fake.clip@1",
      "plugin_id": "fake_clip",
      "kind": "clip",
      "status": "ok",
      "primary": "amplitude",
      "definition": "Test plugin. Mean absolute sample value of each 16-bit PCM WAV clip, read with the Python wave module, divided by 32768.",
      "scores": [
        {
          "name": "amplitude",
          "kind": "clip",
          "value": 0.1629783702055613,
          "n": 12,
          "std": 0.02251561374961659,
          "ci": {
            "method": "bootstrap-percentile",
            "level": 0.95,
            "n_resamples": 1000,
            "seed": 0,
            "low": 0.1514537176932891,
            "high": 0.17459488541523616
          }
        }
      ],
      "clips_failed": [],
      "per_clip_file": "per_clip/fake.clip@1.csv",
      "upstream": {
        "package": "python-stdlib",
        "version": "3.12.7",
        "invocation": "wave.open(path).readframes(); mean(abs(x)) / 32768"
      },
      "env": {
        "env_id": "fake_clip-ff9ebfb1",
        "lock_sha256": "34e5c74c9958cbfba688a1c30a27c909294b2e60fa38cb9aeb58199f325246a6",
        "python": "3.12.7",
        "device": "cpu"
      },
      "licence": {
        "code": {
          "name": null,
          "status": "not_applicable"
        },
        "weights": {
          "name": null,
          "status": "not_applicable"
        },
        "data": {
          "name": null,
          "status": "not_applicable"
        },
        "commercial_ok": "unknown"
      },
      "warnings": [],
      "error": null,
      "timing_s": 0.15256247436627746
    },
    {
      "metric_id": "fake.set@1",
      "plugin_id": "fake_set",
      "kind": "set",
      "status": "ok",
      "primary": "n_files",
      "definition": "Test plugin. Number of files in the staged generated folder. Also reports the number of files in the staged reference folder as n_ref_files.",
      "scores": [
        {
          "name": "n_files",
          "kind": "set",
          "value": 12.0,
          "n": null,
          "std": null,
          "ci": null,
          "ci_reason": "set-level metric, no confidence interval in 0.1"
        },
        {
          "name": "n_ref_files",
          "kind": "aux",
          "value": 12.0,
          "n": null,
          "std": null,
          "ci": null,
          "ci_reason": "set-level metric, no confidence interval in 0.1"
        }
      ],
      "clips_failed": [],
      "per_clip_file": null,
      "upstream": {
        "package": "python-stdlib",
        "version": "3.12.7",
        "invocation": "len(os.listdir(generated.dir))"
      },
      "env": {
        "env_id": "fake_set-ff9ebfb1",
        "lock_sha256": "34e5c74c9958cbfba688a1c30a27c909294b2e60fa38cb9aeb58199f325246a6",
        "python": "3.12.7",
        "device": "cpu"
      },
      "licence": {
        "code": {
          "name": null,
          "status": "not_applicable"
        },
        "weights": {
          "name": null,
          "status": "not_applicable"
        },
        "data": {
          "name": null,
          "status": "not_applicable"
        },
        "commercial_ok": "unknown"
      },
      "warnings": [],
      "error": null,
      "timing_s": 0.002677906770259142
    }
  ],
  "warnings": []
}
```

`report.md` is not written yet (M6). The warning rules of section 10.2 that depend on the data
or the licence (for example `UNKNOWN_LICENCE`, `FEW_CLIPS`) are also M6, so the sample has no
warnings.

### Isolation test (section 11.4)

```text
$ uv run pytest -m slow -v tests/integration/test_isolation.py
configfile: pyproject.toml
collecting ... collected 1 item

tests/integration/test_isolation.py::test_fake_np1_and_fake_np2_are_isolated PASSED [100%]

============================== 1 passed in 2.01s ===============================
exit code: 0
```

The same two plugins run with the installed wheel, showing the `env` blocks from `results.json`:

```text
$ MUSEGAUGE_HOME=./home2 MUSEGAUGE_PLUGIN_PATH=<repo>/tests/fake_plugins musegauge run --generated fixtures/gen_small --metrics fake.np1@1,fake.np2@1 --out out_iso
musegauge: 12 clip(s) readable, 0 skipped
musegauge: run 20261002T164939Z-3efcfd, output .../gate1/out_iso
musegauge: plugin fake_np1: preparing environment
musegauge: metric fake.np1@1: running
musegauge: metric fake.np1@1: ok
musegauge: plugin fake_np2: preparing environment
musegauge: metric fake.np2@1: running
musegauge: metric fake.np2@1: ok
musegauge: wrote .../gate1/out_iso/results.json
exit code: 0

core (musegauge itself): python 3.12.7 | numpy 2.5.3 | .../gate1/wheelenv/lib/python3.12/site-packages/numpy/__init__.py
fake.np1@1 ok | env_id fake_np1-c82e7f69 | python 3.11.17 | numpy 1.26.4
    numpy_file: ./home2/envs/fake_np1-c82e7f69/lib/python3.11/site-packages/numpy/__init__.py
    sys_version: 3.11.17 (main, Oct  1 2026, 20:58:47) [Clang 22.1.3 ]
fake.np2@1 ok | env_id fake_np2-f1b5ee8c | python 3.12.7 | numpy 2.0.2
    numpy_file: ./home2/envs/fake_np2-f1b5ee8c/lib/python3.12/site-packages/numpy/__init__.py
    sys_version: 3.12.7 | packaged by Anaconda, Inc. | (main, Oct  4 2024, 13:27:36) [GCC 11.2.0]
```

### The core imports no torch or TensorFlow

```text
$ python -X importtime -c "import musegauge" 2>&1 | grep -i -E "torch|tensorflow"
(grep exit code: 1 -> 1 means no match)

$ python -X importtime -c "import musegauge.cli, musegauge.runner, musegauge.results, musegauge.stats, ..." 2>&1 | grep -i -E "torch|tensorflow|fadtk|kadtk|audiobox|laion_clap"
(grep exit code: 1 -> 1 means no match)
```

### Wheel contents (section 5)

```text
$ python -m zipfile -l dist/musegauge-0.1.0.dev0-py3-none-any.whl   (unzip is not installed)
musegauge/_runtime/musegauge_runtime/__init__.py
musegauge/_runtime/musegauge_runtime/run.py
musegauge/plugins/README.md
musegauge/schemas/{clip,manifest,prefetch,request,response,results,suite}.schema.json
musegauge/suites/t2m-basic@1.yaml
musegauge/suites/t2m-full@1.yaml
(plus the Python modules and dist-info)
```

`plugins/` holds only its README until the first real plugin (M3).

GATE 1 passed: Roy said "Go" on 2026-10-03 and answered the four questions (amendments A1 to A4
in `docs/DECISIONS.md`).

## M2. Command line

Date: 2026-10-03. Status: **passed**.

Help texts are checked against section 7 by `tests/unit/test_cli.py::test_command_help_matches_section_7`.
Exit codes 0, 2, 3, 4, 5, 6 and 10 are each produced by a real `musegauge` process in
`tests/integration/test_exit_codes.py` (also 2, 3, 4 in `tests/unit/test_cli.py`).

```text
$ SOX_PATH=~/tools/sox/bin/sox musegauge doctor
OK    platform: linux-x86_64
OK    uv: 0.12.22 at .venv/bin/uv
OK    sox: ~/tools/sox/bin/sox (via SOX_PATH): ~/tools/sox/bin/sox:      SoX v14.4.2
OK    ffmpeg: /usr/bin/ffmpeg: ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
OK    MUSEGAUGE_HOME: <a temporary folder> is writable; 158.5 GB free
OK    nvidia-smi: /usr/bin/nvidia-smi: 6 GPU(s), first: NVIDIA L40S, 560.35.03
OK    https://pypi.org: HTTP 200
OK    https://huggingface.co: HTTP 200
WARN  plugins: no plugins found
exit code: 0

$ uv run pytest
collected 228 items / 1 deselected / 227 selected

tests/integration/test_e2e_fakes.py ...........                          [  4%]
tests/integration/test_exit_codes.py ...........                         [  9%]
tests/unit/test_cli.py .................................                 [ 24%]
tests/unit/test_clips.py ......................                          [ 33%]
tests/unit/test_config.py .......                                        [ 37%]
tests/unit/test_envs.py ........                                         [ 40%]
tests/unit/test_errors.py ..                                             [ 41%]
tests/unit/test_registry.py ...............................              [ 55%]
tests/unit/test_report.py .....                                          [ 57%]
tests/unit/test_results.py ..............                                [ 63%]
tests/unit/test_runner.py ..........                                     [ 67%]
tests/unit/test_runtime.py .............                                 [ 73%]
tests/unit/test_schemas.py ..............................                [ 86%]
tests/unit/test_staging.py ...........                                   [ 91%]
tests/unit/test_stats.py ............                                    [ 96%]
tests/unit/test_verify_facts.py ...                                      [ 98%]
tests/unit/test_version.py .                                             [ 98%]
tests/unit/test_warnings.py ...                                          [100%]

====================== 227 passed, 1 deselected in 21.29s ======================
exit code: 0

$ uv run ruff check
All checks passed!
exit code: 0
```

"no plugins found" is expected: the real plugins come in M3 to M5.

## M3. Plugin `aesthetics_audiobox`

Date: 2026-10-03. Status: **passed**.

The first lock failed its smoke check (`ModuleNotFoundError: No module named 'requests'`). I
stopped and asked Roy; the fix is in `UPSTREAM_NOTES.md` and `DECISIONS.md`.

Environment built from the lock:

```text
$ musegauge setup --metrics aesthetics.audiobox@1 --fetch-weights
musegauge: plugin aesthetics_audiobox: building or checking its environment
musegauge: plugin aesthetics_audiobox: environment ready: ~/.cache/musegauge/envs/aesthetics_audiobox-76e395f1
musegauge: prefetch aesthetics.audiobox@1: ok (4.5 s)
    note: cached files for facebook/audiobox-aesthetics: 2
exit code: 0
```

(The weights had already been downloaded by the two test environments used to check the fixes,
into the same cache, so prefetch found them.)

`import torchaudio`, a WAV load, and a GPU check inside the environment (GPU with the most free memory):

```text
chosen GPU (most free memory): 5
$ CUDA_VISIBLE_DEVICES=5 ENV/bin/python -c 'import torchaudio; torchaudio.load(gen_000.wav); torch.cuda...; small GPU op'
torchaudio 2.7.0+cu126 load: sample rate 32000 shape (1, 320000) backends ['ffmpeg', 'soundfile']
torch 2.7.0+cu126 built for CUDA 12.6 | cuda available True | device NVIDIA L40S
small GPU op (512x512 matmul) ok, result finite: True
driver: 560.35.03
```

Golden test (CPU and one L40S), broken clip, and torchaudio load tests:

```text
$ nvidia-smi --query-gpu=index,memory.free --format=csv,noheader
0, 31291 MiB;1, 34422 MiB;2, 33135 MiB;3, 33135 MiB;4, 33752 MiB;5, 33135 MiB;
$ uv run pytest -m slow -v -s tests/integration/test_golden.py tests/integration/test_plugin_aesthetics.py
tests/integration/test_golden.py::test_golden[aesthetics_audiobox-gen_small-cpu] 
GOLDEN aesthetics_audiobox gen_small cpu (cpu, torch 2.7.0+cu126): 48 values, largest |harness - upstream| = 0, smallest tolerance = 1e-06, 0 outside
tests/integration/test_golden.py::test_golden[aesthetics_audiobox-gen_small-cuda] 
GOLDEN aesthetics_audiobox gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 48 values, largest |harness - upstream| = 0, smallest tolerance = 1e-06, 0 outside
tests/integration/test_plugin_aesthetics.py::test_environment_loads_wav_with_torchaudio PASSED
tests/integration/test_plugin_aesthetics.py::test_broken_clip_is_listed_and_others_are_scored PASSED
tests/integration/test_plugin_aesthetics.py::test_core_run_skips_unreadable_file_and_scores_the_rest PASSED
============================== 5 passed in 51.01s ==============================
```

The fast set after M3: `227 passed, 6 deselected`; `ruff check`: `All checks passed!`.

## M4. Plugin `clapscore_laion`

Date: 2026-10-03. Status: **passed**.

```text
$ musegauge setup --metrics clapscore.laion-music@1 --fetch-weights
musegauge: plugin clapscore_laion: building or checking its environment
musegauge: plugin clapscore_laion: environment ready: ~/.cache/musegauge/envs/clapscore_laion-a3ecbe8b
musegauge: prefetch clapscore.laion-music@1: ok (39.1 s)
    downloaded: lukewys/laion_clap/music_audioset_epoch_15_esc_90.14.pt
    downloaded: roberta-base/model.safetensors
    note: cached files: lukewys/laion_clap/music_audioset_epoch_15_esc_90.14.pt, roberta-base/config.json, roberta-base/merges.txt, roberta-base/model.safetensors, roberta-base/tokenizer.json, roberta-base/tokenizer_config.json, roberta-base/vocab.json
exit code: 0
```

(The tokenizer files arrived one step earlier, during the environment's smoke check, because
`import laion_clap` downloads them. See `docs/UPSTREAM_NOTES.md`.)

Wrapper against the direct script (golden, section 11.6 tolerance), score range, `no_prompt`,
and `NO_PROMPTS`:

```text
$ uv run pytest -m slow -v -s tests/integration/test_plugin_clap.py tests/integration/test_golden.py -k "clap"
tests/integration/test_plugin_clap.py::test_prefetch_fills_the_weights_folder PASSED
tests/integration/test_plugin_clap.py::test_scores_are_cosines_and_clips_without_prompt_are_listed PASSED
tests/integration/test_plugin_clap.py::test_no_prompts_skips_the_metric PASSED
tests/integration/test_golden.py::test_golden[clapscore_laion-gen_small-cpu] 
GOLDEN clapscore_laion gen_small cpu (cpu, torch 2.7.0+cu126): 12 values, largest |harness - upstream| = 1.39e-17, smallest tolerance = 1e-06, 0 outside
tests/integration/test_golden.py::test_golden[clapscore_laion-gen_small-cuda] 
GOLDEN clapscore_laion gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 12 values, largest |harness - upstream| = 2.78e-17, smallest tolerance = 1e-06, 0 outside
================== 5 passed, 2 deselected in 83.89s (0:01:23) ==================
```

GPU check in the environment: torch 2.7.0+cu126, `torch.version.cuda` 12.6,
`torch.cuda.is_available()` True on an NVIDIA L40S, 512×512 matmul OK (`docs/VERIFIED_FACTS.md`).

## M5. Plugins `fad_fadtk` and `kad_kadtk`

Date: 2026-10-03. Status: **passed, waiting at GATE 2**.

Before building, reading the 1.1.0 sources and two proof runs showed four things the spec did
not describe. I stopped and asked Roy; the answers are amendments A5 to A8 (`docs/DECISIONS.md`):
no sox needed (A6), start-up CLAP downloads kept (A8), `trust_remote_code: true` (A7), new
warning `UNSEEDED_RANDOMNESS` (A5). The first golden test run then failed on two GPU cases. The
causes were found and proven, and Roy chose the fixes: the reference is staged fresh for every
run (A9) and random scores get a presence check only (A10). Details in `docs/UPSTREAM_NOTES.md`
and `docs/DECISIONS.md`.

Environments built from the locks, with all weights fetched:

```text
$ musegauge setup --metrics fad.vggish@1,fad.clap-laion-music@1,fad.encodec-emb@1,kad.vggish@1,kad.clap-laion-music@1 --fetch-weights
musegauge: plugin fad_fadtk: building or checking its environment
musegauge: plugin fad_fadtk: environment ready: ~/.cache/musegauge/envs/fad_fadtk-f7a67ac7
musegauge: prefetch fad.vggish@1: ok (56.7 s)
    downloaded: ~/.cache/musegauge/envs/fad_fadtk-f7a67ac7/lib/python3.11/site-packages/fadtk/.model-checkpoints/630k-audioset-best.pt
    downloaded: ~/.cache/musegauge/envs/fad_fadtk-f7a67ac7/lib/python3.11/site-packages/fadtk/.model-checkpoints/CLAP_weights_2023.pth
    downloaded: ~/.cache/musegauge/envs/fad_fadtk-f7a67ac7/lib/python3.11/site-packages/fadtk/.model-checkpoints/music_audioset_epoch_15_esc_90.14.pt
    note: fadtk model vggish loaded on the CPU
musegauge: prefetch fad.clap-laion-music@1: ok (27.4 s)
    note: fadtk model clap-laion-music loaded on the CPU
musegauge: prefetch fad.encodec-emb@1: ok (3.3 s)
    downloaded: ~/.cache/musegauge/weights/torch/hub/checkpoints/encodec_24khz-d7cc33bc.th
    note: fadtk model encodec-emb loaded on the CPU
musegauge: plugin kad_kadtk: building or checking its environment
musegauge: plugin kad_kadtk: environment ready: ~/.cache/musegauge/envs/kad_kadtk-391cfe89
musegauge: prefetch kad.vggish@1: ok (67.1 s)
    downloaded: ~/.cache/musegauge/envs/kad_kadtk-391cfe89/lib/python3.11/site-packages/kadtk/.model-checkpoints/630k-audioset-best.pt
    downloaded: ~/.cache/musegauge/envs/kad_kadtk-391cfe89/lib/python3.11/site-packages/kadtk/.model-checkpoints/CLAP_weights_2023.pth
    downloaded: ~/.cache/musegauge/envs/kad_kadtk-391cfe89/lib/python3.11/site-packages/kadtk/.model-checkpoints/music_audioset_epoch_15_esc_90.14.pt
    note: kadtk model vggish loaded on the CPU
musegauge: prefetch kad.clap-laion-music@1: ok (23.6 s)
    note: kadtk model clap-laion-music loaded on the CPU
exit code: 0
```

GPU check in each environment (GPU with the most free memory, alone):

```text
--- fad_fadtk-f7a67ac7
torch 2.7.0+cu126 | torch.version.cuda 12.6 | cuda available True | NVIDIA L40S
512x512 matmul ok, finite: True
--- kad_kadtk-391cfe89
torch 2.5.1+cu124 | torch.version.cuda 12.4 | cuda available True | NVIDIA L40S
512x512 matmul ok, finite: True
driver: 560.35.03
```

### The two-torch run (GATE 2)

```text
$ CUDA_VISIBLE_DEVICES=5 musegauge run --generated fixtures/gen_small --reference fixtures/ref_small --metrics fad.vggish@1,kad.vggish@1 --device cuda --out out
musegauge: 12 clip(s) readable, 0 skipped
musegauge: reference: 12 of 12 audio files readable
musegauge: run 20261003T023220Z-3c14ec, output out
musegauge: plugin fad_fadtk: preparing environment
musegauge: metric fad.vggish@1: running
musegauge: metric fad.vggish@1: ok
musegauge: plugin kad_kadtk: preparing environment
musegauge: metric kad.vggish@1: running
musegauge: metric kad.vggish@1: ok
warning TRUST_REMOTE_CODE [fad.vggish@1]: The plugin runs code downloaded from a model repository (see `musegauge info`).
warning UNSEEDED_RANDOMNESS [fad.vggish@1]: fad_inf and fad_inf_r2 come from fadtk's score_inf, which samples embedding frames with numpy.random.choice without a seed; they change from run to run.
warning TRUST_REMOTE_CODE [kad.vggish@1]: The plugin runs code downloaded from a model repository (see `musegauge info`).
musegauge: wrote out/results.json and out/report.md
exit code: 0
```

Excerpt of that `results.json` (tool, reference and the two metrics; the file validates against
`results.schema.json`):

```json
{
  "tool": {
    "name": "musegauge",
    "version": "0.1.0.dev0",
    "git_commit": null,
    "uv_version": "0.12.22",
    "python": "3.12.7",
    "platform": "linux-x86_64"
  },
  "reference": {
    "kind": "dir",
    "name": null,
    "ref_hash": "e38692a8aea06972572f25e5eaffd79cea62a9dd44601347cf07f098a5825ded",
    "n_clips": 12,
    "total_duration_s": 120.0
  },
  "metrics": {
    "fad.vggish@1": {
      "status": "ok",
      "scores": [
        {
          "name": "fad",
          "kind": "set",
          "value": 6.40373404221544,
          "n": null,
          "std": null,
          "ci": null,
          "ci_reason": "set-level metric, no confidence interval in 0.1"
        },
        {
          "name": "fad_inf",
          "kind": "set",
          "value": 6.552051865451903,
          "n": null,
          "std": null,
          "ci": null,
          "ci_reason": "set-level metric, no confidence interval in 0.1"
        },
        {
          "name": "fad_inf_r2",
          "kind": "aux",
          "value": 0.08352369809303573,
          "n": null,
          "std": null,
          "ci": null,
          "ci_reason": "set-level metric, no confidence interval in 0.1"
        }
      ],
      "upstream": {
        "package": "fadtk",
        "version": "1.1.0",
        "invocation": "~/.cache/musegauge/envs/fad_fadtk-f7a67ac7/bin/fadtk vggish ~/.cache/musegauge/work/20261003T023220Z-3c14ec/fad_fadtk/ref ~/.cache/musegauge/work/20261003T023220Z-3c14ec/fad_fadtk/gen ~/.cache/musegauge/work/20261003T023220Z-3c14ec/fad_fadtk/fadtk-vggish-plain.csv -w 8 ; ~/.cache/musegauge/envs/fad_fadtk-f7a67ac7/bin/fadtk vggish ~/.cache/musegauge/work/20261003T023220Z-3c14ec/fad_fadtk/ref ~/.cache/musegauge/work/20261003T023220Z-3c14ec/fad_fadtk/gen ~/.cache/musegauge/work/20261003T023220Z-3c14ec/fad_fadtk/fadtk-vggish-inf.csv -w 8 --inf"
      },
      "env": {
        "env_id": "fad_fadtk-f7a67ac7",
        "lock_sha256": "6ba0018287ca66ae6bcb64a2970200baa743a7bef52bd7a3eaca011312876cde",
        "python": "3.11.17",
        "torch": "2.7.0+cu126",
        "torch_cuda": "12.6",
        "cuda_available": true,
        "device": "cuda",
        "gpu_name": "NVIDIA L40S"
      },
      "warnings": [
        {
          "code": "TRUST_REMOTE_CODE",
          "scope": "metric",
          "message": "The plugin runs code downloaded from a model repository (see `musegauge info`).",
          "metric_id": "fad.vggish@1"
        },
        {
          "code": "UNSEEDED_RANDOMNESS",
          "scope": "metric",
          "message": "fad_inf and fad_inf_r2 come from fadtk's score_inf, which samples embedding frames with numpy.random.choice without a seed; they change from run to run.",
          "metric_id": "fad.vggish@1"
        }
      ]
    },
    "kad.vggish@1": {
      "status": "ok",
      "scores": [
        {
          "name": "kad",
          "kind": "set",
          "value": 6.871777534484863,
          "n": null,
          "std": null,
          "ci": null,
          "ci_reason": "set-level metric, no confidence interval in 0.1"
        }
      ],
      "upstream": {
        "package": "kadtk",
        "version": "1.1.0",
        "invocation": "~/.cache/musegauge/envs/kad_kadtk-391cfe89/bin/kadtk vggish ~/.cache/musegauge/work/20261003T023220Z-3c14ec/kad_kadtk/ref ~/.cache/musegauge/work/20261003T023220Z-3c14ec/kad_kadtk/gen --csv ~/.cache/musegauge/work/20261003T023220Z-3c14ec/kad_kadtk/kadtk-vggish.csv --device cuda -w 8"
      },
      "env": {
        "env_id": "kad_kadtk-391cfe89",
        "lock_sha256": "93a6d82b23b39750dc2a785f3550ff1181947b0febab7ff46ca7f17ea9357175",
        "python": "3.11.17",
        "torch": "2.5.1+cu124",
        "torch_cuda": "12.4",
        "cuda_available": true,
        "device": "cuda",
        "gpu_name": "NVIDIA L40S",
        "tensorflow": "2.21.0"
      },
      "warnings": [
        {
          "code": "TRUST_REMOTE_CODE",
          "scope": "metric",
          "message": "The plugin runs code downloaded from a model repository (see `musegauge info`).",
          "metric_id": "kad.vggish@1"
        }
      ]
    }
  }
}
```

### Golden tests and the other M5 checks (all slow tests)

Each `GOLDEN` line is printed by `tests/integration/test_golden.py`. Every deterministic score
uses the section 11.6 tolerance; `fad_inf` and `fad_inf_r2` are random (A10).

```text
$ uv run pytest -m slow -v -s
platform linux -- Python 3.12.7, pytest-9.1.1, pluggy-1.6.0 -- .venv/bin/python
GOLDEN aesthetics_audiobox gen_small cpu (cpu, torch 2.7.0+cu126): 48 values, 0 outside tolerance; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
GOLDEN aesthetics_audiobox gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 48 values, 0 outside tolerance; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
GOLDEN clapscore_laion gen_small cpu (cpu, torch 2.7.0+cu126): 12 values, 0 outside tolerance; closest to its limit: gen_007/clap_cosine |diff| 1.39e-17 vs tolerance 1e-06
GOLDEN clapscore_laion gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 12 values, 0 outside tolerance; closest to its limit: gen_011/clap_cosine |diff| 2.78e-17 vs tolerance 1e-06
GOLDEN fad_fadtk vggish-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 6.1609 (random, upstream runs 6.7483, 6.4565, 6.3994); fad_inf_r2 0.2774 (random, upstream runs 0.1014, 0.0020, 0.0590); 0 problems
GOLDEN fad_fadtk vggish-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 6.4136 (random, upstream runs 6.6578, 6.3824, 6.1813); fad_inf_r2 0.0147 (random, upstream runs 0.0135, 0.0974, 0.3448); 0 problems
GOLDEN fad_fadtk vggish-fma_pop cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 24.4810 (random, upstream runs 24.1832, 24.9652, 23.4238); fad_inf_r2 0.0882 (random, upstream runs 0.2724, 0.0001, 0.4002); 0 problems
GOLDEN fad_fadtk vggish-fma_pop cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 24.7827 (random, upstream runs 25.5994, 25.9826, 26.0684); fad_inf_r2 0.0743 (random, upstream runs 0.0153, 0.0124, 0.0054); 0 problems
GOLDEN fad_fadtk clap-laion-music-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 0.1569 (random, upstream runs 0.1555, 0.1578, 0.1576); fad_inf_r2 0.4450 (random, upstream runs 0.6319, 0.5412, 0.5044); 0 problems
GOLDEN fad_fadtk clap-laion-music-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 0.1589 (random, upstream runs 0.1608, 0.1575, 0.1593); fad_inf_r2 0.5068 (random, upstream runs 0.3462, 0.5662, 0.6251); 0 problems
GOLDEN fad_fadtk encodec-emb-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 169.8234 (random, upstream runs 170.1929, 169.8897, 170.1665); fad_inf_r2 0.6348 (random, upstream runs 0.7593, 0.5717, 0.5742); 0 problems
GOLDEN fad_fadtk encodec-emb-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 170.6502 (random, upstream runs 170.4848, 170.0837, 170.2865); fad_inf_r2 0.7221 (random, upstream runs 0.1155, 0.8008, 0.5406); 0 problems
GOLDEN kad_kadtk vggish-dir cpu (cpu, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk vggish-dir cuda (NVIDIA L40S, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk clap-laion-music-dir cpu (cpu, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk clap-laion-music-dir cuda (NVIDIA L40S, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
tests/integration/test_isolation.py::test_fake_np1_and_fake_np2_are_isolated PASSED
tests/integration/test_plugin_aesthetics.py::test_environment_loads_wav_with_torchaudio PASSED
tests/integration/test_plugin_aesthetics.py::test_broken_clip_is_listed_and_others_are_scored PASSED
tests/integration/test_plugin_aesthetics.py::test_core_run_skips_unreadable_file_and_scores_the_rest PASSED
tests/integration/test_plugin_clap.py::test_prefetch_fills_the_weights_folder PASSED
tests/integration/test_plugin_clap.py::test_scores_are_cosines_and_clips_without_prompt_are_listed PASSED
tests/integration/test_plugin_clap.py::test_no_prompts_skips_the_metric PASSED
tests/integration/test_plugin_fad_kad.py::test_two_torch_versions_in_one_run_and_inputs_untouched PASSED
tests/integration/test_plugin_fad_kad.py::test_fad_with_bundled_reference_and_per_clip PASSED
tests/integration/test_plugin_fad_kad.py::test_kad_runs_on_cpu_without_a_gpu PASSED
tests/integration/test_plugin_fad_kad.py::test_kad_refuses_the_bundled_reference PASSED
=============== 27 passed, 229 deselected in 2225.35s (0:37:05) ================
```

What each M5 check maps to:

- Both golden tests pass: the `GOLDEN fad_fadtk` and `GOLDEN kad_kadtk` lines (CPU and one L40S).
- Two torch versions in one run: the run above and `test_two_torch_versions_in_one_run_and_inputs_untouched`.
- Folder and bundled `fma_pop` references for FAD: the `vggish-dir` and `vggish-fma_pop` golden cases and `test_fad_with_bundled_reference_and_per_clip`.
- `--per-clip` writes `per_clip/fad.vggish@1.csv`: `test_fad_with_bundled_reference_and_per_clip`.
- Inputs untouched (section 11.5): `test_two_torch_versions_in_one_run_and_inputs_untouched` hashes both input folders before and after, and checks that no `embeddings`, `convert`, `stats` or `kernel_stats` folder appears in them.
- KAD with `--device cpu` on a machine without a GPU: `test_kad_runs_on_cpu_without_a_gpu` (`CUDA_VISIBLE_DEVICES=""`).

### Fast set after M5

```text
collected 256 items / 27 deselected / 229 selected

tests/integration/test_e2e_fakes.py ...........                          [  4%]
tests/integration/test_exit_codes.py ...........                         [  9%]
tests/unit/test_cli.py ..................................                [ 24%]
tests/unit/test_clips.py ......................                          [ 34%]
tests/unit/test_config.py .......                                        [ 37%]
tests/unit/test_envs.py ........                                         [ 40%]
tests/unit/test_errors.py ..                                             [ 41%]
tests/unit/test_registry.py ...............................              [ 55%]
tests/unit/test_report.py .....                                          [ 57%]
tests/unit/test_results.py ...............                               [ 63%]
tests/unit/test_runner.py ..........                                     [ 68%]
tests/unit/test_runtime.py .............                                 [ 73%]
tests/unit/test_schemas.py ..............................                [ 86%]
tests/unit/test_staging.py ...........                                   [ 91%]
tests/unit/test_stats.py ............                                    [ 96%]
tests/unit/test_verify_facts.py ...                                      [ 98%]
tests/unit/test_version.py .                                             [ 98%]
tests/unit/test_warnings.py ...                                          [100%]

===================== 229 passed, 27 deselected in 19.78s ======================
```

`uv run ruff check`: `All checks passed!`

GATE 2 passed: Roy said "Go" on 2026-10-03 with answers (`docs/DECISIONS.md`, "GATE 2 answers",
amendments A11 and A12).

## M6. Statistics, warnings and report card

Date: 2026-10-03. Status: **passed**.

- Every warning code of section 10.2 plus `NO_LOCK`, `UNSEEDED_RANDOMNESS` and `FAD_INF_FAILED`
  has a test that raises it and one that does not (`tests/unit/test_warnings.py` checks this list).
- `--threads N` (A11), `run.threads` in `results.json`, `torch_threads` per plugin environment.
- The report's software section shows the thread setting, torch threads per environment, and
  that the VGGish code is not pinned (A7).
- `docs/examples/report.md` is a real `t2m-basic` run on the synthetic fixtures (GPU 1); its first
  line is "Example from synthetic audio. The numbers mean nothing." `musegauge report` on that
  run's `results.json` printed text identical to its `report.md` (`diff` empty).

Statistics, warnings, wrapper-warning and report tests:

```text
$ uv run pytest tests/unit/test_warnings.py tests/unit/test_wrappers.py tests/unit/test_stats.py tests/unit/test_report.py -v
tests/unit/test_warnings.py::test_raises_and_does_not_raise[SHORT_CLIPS] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[MIXED_SAMPLE_RATES] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[MIXED_DURATIONS] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[REF_SMALL] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[REF_GEN_OVERLAP] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[FEW_CLIPS] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[NONCOMMERCIAL_WEIGHTS] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[UNKNOWN_LICENCE] PASSED
tests/unit/test_warnings.py::test_raises_and_does_not_raise[KAD_NEGATIVE] PASSED
tests/unit/test_warnings.py::test_few_clips_only_for_set_metrics PASSED
tests/unit/test_warnings.py::test_licence_warning_for_commercial_ok_yes_is_none PASSED
tests/unit/test_warnings.py::test_kad_negative_ignores_other_scores_and_null PASSED
tests/unit/test_warnings.py::test_clips_skipped_lists_ids_and_reasons PASSED
tests/unit/test_warnings.py::test_short_clips_names_the_shortest PASSED
tests/unit/test_warnings.py::test_limits_are_the_documented_defaults PASSED
tests/unit/test_warnings.py::test_every_warning_matches_the_results_schema PASSED
tests/unit/test_warnings.py::test_emit_prints_to_stderr PASSED
tests/unit/test_warnings.py::test_every_code_has_a_raise_and_a_no_raise_test PASSED
tests/unit/test_wrappers.py::test_fad_and_fad_inf_with_unseeded_randomness PASSED
tests/unit/test_wrappers.py::test_no_inf_means_no_unseeded_randomness PASSED
tests/unit/test_wrappers.py::test_failed_inf_keeps_fad_and_adds_fad_inf_failed PASSED
tests/unit/test_wrappers.py::test_successful_inf_has_no_fad_inf_failed PASSED
tests/unit/test_wrappers.py::test_new_cache_files_raise_network_fetch PASSED
tests/unit/test_wrappers.py::test_no_new_files_no_network_fetch PASSED
tests/unit/test_wrappers.py::test_per_clip_maps_paths_back_to_clip_ids PASSED
tests/unit/test_wrappers.py::test_cpu_request_hides_the_gpus PASSED
tests/unit/test_stats.py::test_same_inputs_give_the_same_interval PASSED
tests/unit/test_stats.py::test_interval_contains_the_mean_and_has_the_fields PASSED
tests/unit/test_stats.py::test_seed_and_names_change_the_stream PASSED
tests/unit/test_stats.py::test_stream_key_is_first_8_bytes_big_endian PASSED
tests/unit/test_stats.py::test_matches_a_direct_computation_of_the_spec_recipe PASSED
tests/unit/test_stats.py::test_order_of_metrics_does_not_change_intervals PASSED
tests/unit/test_stats.py::test_summary_mean_std_n PASSED
tests/unit/test_stats.py::test_n_of_one_gives_no_interval PASSED
tests/unit/test_stats.py::test_bootstrap_zero_turns_intervals_off PASSED
tests/unit/test_stats.py::test_null_and_missing_values_are_left_out PASSED
tests/unit/test_stats.py::test_several_score_names_keep_their_order PASSED
tests/unit/test_stats.py::test_set_scores_get_no_interval PASSED
tests/unit/test_report.py::test_render_matches_the_stored_expected_text PASSED
tests/unit/test_report.py::test_render_is_pure PASSED
tests/unit/test_report.py::test_error_and_skipped_rows_and_error_in_warnings PASSED
tests/unit/test_report.py::test_numbers_are_rounded_to_3_decimals PASSED
tests/unit/test_report.py::test_reference_lines PASSED
```

Fast set:

```text
$ uv run pytest
============================= test session starts ==============================
platform linux -- Python 3.12.7, pytest-9.1.1, pluggy-1.6.0
rootdir: ~/musegauge
configfile: pyproject.toml
testpaths: tests
collected 289 items / 29 deselected / 260 selected

tests/integration/test_e2e_fakes.py ..............                       [  5%]
tests/integration/test_exit_codes.py ...........                         [  9%]
tests/unit/test_cli.py ...................................               [ 23%]
tests/unit/test_clips.py ......................                          [ 31%]
tests/unit/test_config.py .........                                      [ 35%]
tests/unit/test_envs.py ........                                         [ 38%]
tests/unit/test_errors.py ..                                             [ 38%]
tests/unit/test_registry.py ...............................              [ 50%]
tests/unit/test_report.py .....                                          [ 52%]
tests/unit/test_results.py ...............                               [ 58%]
tests/unit/test_runner.py ............                                   [ 63%]
tests/unit/test_runtime.py .............                                 [ 68%]
tests/unit/test_schemas.py ..............................                [ 79%]
tests/unit/test_staging.py ...........                                   [ 83%]
tests/unit/test_stats.py ............                                    [ 88%]
tests/unit/test_verify_facts.py ...                                      [ 89%]
tests/unit/test_version.py .                                             [ 90%]
tests/unit/test_warnings.py ..................                           [ 96%]
tests/unit/test_wrappers.py ........                                     [100%]

===================== 260 passed, 29 deselected in 21.52s ======================
exit code: 0
$ uv run ruff check
All checks passed!
```

Measured on the way (GATE 2 request): CPU numbers depend on the thread count. `--threads 4`
against the default-thread golden runs: `fad` differs by 1.3e-6, Audiobox by up to 2.86e-6
(`docs/VERIFIED_FACTS.md`). The CPU golden numbers are therefore being recorded again under
`nice -n 19 taskset -c 0-15`, and golden files now store the core count (results in M7).

## M7. Docker and Apptainer (and the GATE 2 network items)

Date: 2026-10-03. Status: **done as far as this machine allows, waiting at GATE 3**.

### Section 12 checks for M7

| Check | Result |
| --- | --- |
| `docker build --target slim`, `docker run --rm musegauge:slim doctor` | **Not run**: Docker is not installed on the build machine. `docker/Dockerfile` (targets `slim`, `full`), `docker/README.md` and `.github/workflows/docker.yml` are written. Base and uv image tags were checked through the registry APIs. |
| Fake plugins inside `slim` with `--network none` | **Not run** (no Docker). `docker.yml` contains the step. |
| Offline test: `setup --fetch-weights`, then `--network none --no-fetch` | **Done natively**, not in Docker: `--no-fetch` now makes the network unreachable for every plugin process (GATE 2 item 3a). All six metrics of `t2m-full` passed with exit 0, no file was added to any weight cache (82 / 82). Output below. |
| GPU in a container | **Not tested**; `docs/INSTALL.md` says so. |
| Apptainer commands | **Not tested** (no Apptainer); `docs/INSTALL.md` says so. |

### GATE 2 item 3: github.com on every FAD/KAD run

(a) `unshare -rn` is not permitted here (`unshare: unshare failed: Operation not permitted`), so the
proxy approach was tested:

```text
$ env -i ... TORCH_HOME=<weights>/torch HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY= ENV/bin/python ...
Using cache found in ~/.cache/musegauge/weights/torch/hub/harritaylor_torchvggish_master
direct request to github.com: URLError - [Errno 111] Connection refused
torch 2.7.0+cu126 | torch.hub.load(vggish) OK: VGGish
(the same in the kad environment with torch 2.5.1+cu124)

$ CUDA_VISIBLE_DEVICES=1 nice -n 19 taskset -c 16-31 musegauge run --generated fixtures/gen_small --prompts fixtures/prompts.csv --reference fixtures/ref_small --suite t2m-full --no-fetch --out out
musegauge: 12 clip(s) readable, 0 skipped
musegauge: reference: 12 of 12 audio files readable
musegauge: metric fad.vggish@1: ok
musegauge: metric fad.clap-laion-music@1: ok
musegauge: metric clapscore.laion-music@1: ok
musegauge: metric aesthetics.audiobox@1: ok
musegauge: metric kad.vggish@1: ok
musegauge: metric kad.clap-laion-music@1: ok
exit code: 0
files in the weight caches before / after: 82 / 82
"Using cache found in" in the FAD and KAD logs: 17 and 17
```

(b) `NETWORK_ERROR`: tested by `tests/unit/test_runner.py` (detector and classification) and
`tests/integration/test_e2e_fakes.py::test_torch_hub_http_error_becomes_network_error` (a fake plugin
whose output shows a torch.hub HTTP error) and `test_other_failures_keep_their_error_type`.

(c) Not needed: (a) works.

### Install paths tested here

```text
$ python3 -m venv .venv && .venv/bin/pip install dist/musegauge-0.1.0.dev0-py3-none-any.whl
$ musegauge --version
musegauge 0.1.0.dev0
$ musegauge doctor          (exit code 0; sox WARN, everything else OK; full output in docs/VERIFIED_FACTS.md)

$ uvx --from . musegauge --version
musegauge 0.1.0.dev0
```

### Golden numbers recorded again, and the full slow suite, on 16 cores

CPU numbers depend on the thread count (`docs/VERIFIED_FACTS.md`), so every golden number was
recorded again under `nice -n 19 taskset -c 0-15` (GATE 2 instruction), and golden files now store
`cpu_cores`. The first recording job was stopped by the 2-hour limit for background jobs during
its last stage (KAD on the CPU); that stage was then run alone and finished.

```text
$ nice -n 19 taskset -c 0-15 uv run pytest -m slow -v -s -rxX
GOLDEN aesthetics_audiobox gen_small cpu (cpu, torch 2.7.0+cu126): 48 values, 0 outside tolerance; largest |diff| 0; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
GOLDEN aesthetics_audiobox gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 48 values, 0 outside tolerance; largest |diff| 0; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
GOLDEN clapscore_laion gen_small cpu (cpu, torch 2.7.0+cu126): 12 values, 0 outside tolerance; largest |diff| 1.39e-17; closest to its limit: gen_007/clap_cosine |diff| 1.39e-17 vs tolerance 1e-06
GOLDEN clapscore_laion gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 12 values, 0 outside tolerance; largest |diff| 2.78e-17; closest to its limit: gen_011/clap_cosine |diff| 2.78e-17 vs tolerance 1e-06
GOLDEN fad_fadtk vggish-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 6.1032 (random, upstream runs 6.3621, 6.3383, 6.4098); fad_inf_r2 0.2155 (random, upstream runs 0.0000, 0.0723, 0.0051); 0 problems
GOLDEN fad_fadtk vggish-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 6.3533 (random, upstream runs 6.4707, 6.1517, 6.3737); fad_inf_r2 0.0571 (random, upstream runs 0.0002, 0.3192, 0.1045); 0 problems
GOLDEN fad_fadtk vggish-fma_pop cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 25.0885 (random, upstream runs 25.4694, 25.2026, 25.5261); fad_inf_r2 0.0186 (random, upstream runs 0.0001, 0.0374, 0.0011); 0 problems
GOLDEN fad_fadtk vggish-fma_pop cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 24.6988 (random, upstream runs 25.9646, 26.0237, 24.0403); fad_inf_r2 0.1259 (random, upstream runs 0.0664, 0.0200, 0.3263); 0 problems
GOLDEN fad_fadtk clap-laion-music-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 0.1605 (random, upstream runs 0.1577, 0.1572, 0.1593); fad_inf_r2 0.4307 (random, upstream runs 0.5478, 0.6080, 0.4534); 0 problems
GOLDEN fad_fadtk clap-laion-music-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 0.1607 (random, upstream runs 0.1573, 0.1578, 0.1589); fad_inf_r2 0.2299 (random, upstream runs 0.4682, 0.5621, 0.5716); 0 problems
GOLDEN fad_fadtk encodec-emb-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 170.3219 (random, upstream runs 169.8447, 169.7705, 169.3401); fad_inf_r2 0.6828 (random, upstream runs 0.7997, 0.8213, 0.7144); 0 problems
GOLDEN fad_fadtk encodec-emb-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 169.7941 (random, upstream runs 170.4249, 170.2566, 170.4968); fad_inf_r2 0.6325 (random, upstream runs 0.5586, 0.6773, 0.5123); 0 problems
GOLDEN kad_kadtk vggish-dir cpu (cpu, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk vggish-dir cuda (NVIDIA L40S, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk clap-laion-music-dir cpu (cpu, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk clap-laion-music-dir cuda (NVIDIA L40S, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN-THREADS4 fad_fadtk vggish-dir cpu (torch 2.7.0+cu126): fad |diff| 1.3e-06 vs tolerance 1e-06; fad_inf 5.9967 (random, upstream runs 6.3621, 6.3383, 6.4098); fad_inf_r2 0.3053 (random, upstream runs 0.0000, 0.0723, 0.0051); 1 problems
GOLDEN-THREADS4 aesthetics_audiobox gen_small cpu (torch 2.7.0+cu126): 48 values, 2 outside tolerance; largest |diff| 1.91e-06; closest to its limit: gen_011/CU |diff| 1.91e-06 vs tolerance 1e-06
tests/integration/test_isolation.py::test_fake_np1_and_fake_np2_are_isolated PASSED
tests/integration/test_plugin_aesthetics.py::test_environment_loads_wav_with_torchaudio PASSED
tests/integration/test_plugin_aesthetics.py::test_broken_clip_is_listed_and_others_are_scored PASSED
tests/integration/test_plugin_aesthetics.py::test_core_run_skips_unreadable_file_and_scores_the_rest PASSED
tests/integration/test_plugin_clap.py::test_prefetch_fills_the_weights_folder PASSED
tests/integration/test_plugin_clap.py::test_scores_are_cosines_and_clips_without_prompt_are_listed FAILED
tests/integration/test_plugin_clap.py::test_no_prompts_skips_the_metric FAILED
tests/integration/test_plugin_fad_kad.py::test_two_torch_versions_in_one_run_and_inputs_untouched PASSED
tests/integration/test_plugin_fad_kad.py::test_fad_with_bundled_reference_and_per_clip PASSED
tests/integration/test_plugin_fad_kad.py::test_kad_runs_on_cpu_without_a_gpu PASSED
tests/integration/test_plugin_fad_kad.py::test_kad_refuses_the_bundled_reference PASSED
===== 2 failed, 25 passed, 260 deselected, 2 xfailed in 3228.94s (0:53:48) =====
```

The two clap failures were assertions written before M6 (they expected no licence warning).
After updating them:

```text
tests/integration/test_plugin_clap.py::test_prefetch_fills_the_weights_folder PASSED [ 33%]
tests/integration/test_plugin_clap.py::test_scores_are_cosines_and_clips_without_prompt_are_listed PASSED [ 66%]
tests/integration/test_plugin_clap.py::test_no_prompts_skips_the_metric PASSED [100%]
============================== 3 passed in 28.42s ==============================
```

The two XFAIL lines are the `--threads 4` check: CPU results with 4 threads differ from the
16-thread golden runs by up to 1.9e-6 (documented, GATE 2 item 4).

### Fast set

```text
tests/unit/test_wrappers.py ........                                     [100%]

===================== 260 passed, 29 deselected in 20.89s ======================
$ uv run ruff check
All checks passed!
```

GATE 3 passed: Roy said "Go" on 2026-10-03 with answers (amendments A15 to A20, `docs/DECISIONS.md`).

## M8. Documentation

Date: 2026-10-03. Status: **passed**.

Written or rewritten: `README.md`, `docs/INSTALL.md`, `docs/METRICS.md`, `docs/LICENCES.md`
(generated from the manifests), `docs/PLUGIN_GUIDE.md` (its steps were run with a copy of
`fake_clip`), `docs/UPSTREAM_NOTES.md`, `docs/plugins/*.md`, `docs/TESTING_REAL_PLUGINS.md`,
`docker/README.md`, and the amendment list in `docs/DECISIONS.md` (said / built / why).

GATE 3 changes made in this milestone: `run --no-fetch` with a missing environment exits 4 (A15);
the Docker `full` target is removed (A16); CI is `ci.yml` and `slow.yml` plus
`scripts/run_golden.sh` (A17); `docs/TESTING_REAL_PLUGINS.md` (A18); the `--threads 4` check is a
normal test with the 10-times rule (A20).

### Fresh clone, following only the README, in a clean shell

The shell was started with `env -i` and an **empty home folder** (so no uv cache, no uv-managed
Python, no musegauge cache), `PATH=~/miniconda3/bin:/usr/local/bin:/usr/bin:/bin` (the
system Python 3.12.3 here has no `ensurepip`; see the README note), and `CUDA_VISIBLE_DEVICES=1`
(GPU 0 was busy with another user's job). The commands are the README's "Try it on synthetic
audio" section, with the local repository path for `<repo>`.

```text
$ env -i HOME=<empty folder> PATH=... CUDA_VISIBLE_DEVICES=1 bash --noprofile --norc readme_steps.sh
$ git clone ~/musegauge musegauge && cd musegauge
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install .

$ python tests/make_fixtures.py fixtures
gen_small: fixtures/gen_small
ref_small: fixtures/ref_small
mixed_rates: fixtures/mixed_rates
short_clip: fixtures/short_clip.wav
broken_clip: fixtures/broken_clip.wav
empty_file: fixtures/empty_file.wav
prompts_csv: fixtures/prompts.csv
prompts_jsonl: fixtures/prompts.jsonl
$ musegauge run --generated fixtures/gen_small --metrics aesthetics.audiobox@1 --out out
musegauge: 12 clip(s) readable, 0 skipped
musegauge: run 20261003T130935Z-a4dcb7, output ~/musegauge/out
musegauge: plugin aesthetics_audiobox: preparing environment
musegauge: metric aesthetics.audiobox@1: running
musegauge: metric aesthetics.audiobox@1: ok
warning UNKNOWN_LICENCE [aesthetics.audiobox@1]: The licence has not been checked (commercial_ok: unknown). Do not assume commercial use is allowed.
warning NETWORK_FETCH [aesthetics.audiobox@1]: Downloaded from huggingface.co/facebook/audiobox-aesthetics: config.json, model.safetensors
musegauge: wrote ~/musegauge/out/results.json and ~/musegauge/out/report.md
...
| aesthetics.audiobox@1 | CE | 2.405 ± 0.557 | [2.115, 2.705] | 12 | ok |
| aesthetics.audiobox@1 | CU | 5.455 ± 0.959 | [4.861, 5.922] | 12 | ok |
| aesthetics.audiobox@1 | PC | 1.780 ± 0.141 | [1.712, 1.862] | 12 | ok |
| aesthetics.audiobox@1 | PQ | 6.228 ± 0.827 | [5.757, 6.655] | 12 | ok |
(script exit 0, 33 s)
```

Everything was downloaded in that run: the plugin log shows `Downloading cpython-3.11.17` and the
torch and CUDA packages, the run warned `NETWORK_FETCH` for the Audiobox weights, and the new
home's uv cache holds the package files (hard-linked into the environment).

### Other checks in this milestone

```text
$ MUSEGAUGE_HOME=./empty_home musegauge run --generated fixtures/gen_small --prompts fixtures/prompts.csv --no-fetch --out out
musegauge: 12 clip(s) readable, 0 skipped
musegauge: error: --no-fetch: the environments for these metrics are not built yet: fad.vggish@1, fad.clap-laion-music@1, clapscore.laion-music@1, aesthetics.audiobox@1. Building them needs the network. Run `musegauge setup --metrics fad.vggish@1,fad.clap-laion-music@1,clapscore.laion-music@1,aesthetics.audiobox@1 --fetch-weights` first, then run with --no-fetch.
exit code: 4

$ nice -n 19 taskset -c 0-15 uv run pytest -m slow -v -s tests/integration/test_golden.py -k threads
GOLDEN-THREADS4 fad_fadtk vggish-dir cpu (torch 2.7.0+cu126): 1 values, largest |diff| 1.3e-06, limit 1.3e-05 (10 x observed)
PASSED
GOLDEN-THREADS4 aesthetics_audiobox gen_small cpu (torch 2.7.0+cu126): 48 values, largest |diff| 1.91e-06, limit 2.9e-05 (10 x observed)
PASSED
====================== 2 passed, 16 deselected in 32.54s =======================

$ scripts/run_golden.sh 16 -k "aesthetics and not threads"
golden files:
  tests/golden/aesthetics_audiobox.json: cpu on 16 cores, torch 2.7.0+cu126; cuda on 16 cores, torch 2.7.0+cu126
  tests/golden/clapscore_laion.json: cpu on 16 cores, torch 2.7.0+cu126; cuda on 16 cores, torch 2.7.0+cu126
  tests/golden/fad_fadtk.json: cpu on 16 cores, torch 2.7.0+cu126; cuda on 16 cores, torch 2.7.0+cu126
  tests/golden/kad_kadtk.json: cpu on 16 cores, torch 2.5.1+cu124; cuda on 16 cores, torch 2.5.1+cu124
recording script: tests/golden_scripts/record_golden.py (numbers from this machine only)
running on cores 0-15 with nice -n 19
GOLDEN aesthetics_audiobox gen_small cpu (cpu, torch 2.7.0+cu126): 48 values, 0 outside tolerance; largest |diff| 0; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
PASSED
GOLDEN aesthetics_audiobox gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 48 values, 0 outside tolerance; largest |diff| 0; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
PASSED
====================== 2 passed, 16 deselected in 16.36s =======================
```

Fast set: `261 passed, 29 deselected in 22.05s`; `ruff check`: `All checks passed!`

## M9. Release checklist

Date: 2026-10-03. Status: **passed**.

- Version set to 0.1.0; `CHANGELOG.md` written.
- `uv build`, then `uvx twine check dist/*`: both files PASSED.
- The wheel installed into a clean `python3 -m venv`: `musegauge --version` printed `musegauge 0.1.0`.
- `docs/BUILD_REPORT.md` written (section 13.3), with the final test output.
- At Roy's final message: Apache-2.0 `LICENSE` added (D2), the wheel rebuilt and smoke-tested
  (`--version`, `list`), the name checked on GitHub, and the files checked for institution names
  and internal paths (results in `BUILD_REPORT.md`).
- Nothing is published.

Final slow run on the final code:

```text
$ nice -n 19 taskset -c 0-15 uv run pytest -m slow -v -s
GOLDEN aesthetics_audiobox gen_small cpu (cpu, torch 2.7.0+cu126): 48 values, 0 outside tolerance; largest |diff| 0; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
GOLDEN aesthetics_audiobox gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 48 values, 0 outside tolerance; largest |diff| 0; closest to its limit: gen_000/CE |diff| 0 vs tolerance 1e-06
GOLDEN clapscore_laion gen_small cpu (cpu, torch 2.7.0+cu126): 12 values, 0 outside tolerance; largest |diff| 1.39e-17; closest to its limit: gen_007/clap_cosine |diff| 1.39e-17 vs tolerance 1e-06
GOLDEN clapscore_laion gen_small cuda (NVIDIA L40S, torch 2.7.0+cu126): 12 values, 0 outside tolerance; largest |diff| 2.78e-17; closest to its limit: gen_011/clap_cosine |diff| 2.78e-17 vs tolerance 1e-06
GOLDEN fad_fadtk vggish-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 6.3887 (random, upstream runs 6.3621, 6.3383, 6.4098); fad_inf_r2 0.0221 (random, upstream runs 0.0000, 0.0723, 0.0051); 0 problems
GOLDEN fad_fadtk vggish-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 6.4520 (random, upstream runs 6.4707, 6.1517, 6.3737); fad_inf_r2 0.0012 (random, upstream runs 0.0002, 0.3192, 0.1045); 0 problems
GOLDEN fad_fadtk vggish-fma_pop cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 23.8507 (random, upstream runs 25.4694, 25.2026, 25.5261); fad_inf_r2 0.1743 (random, upstream runs 0.0001, 0.0374, 0.0011); 0 problems
GOLDEN fad_fadtk vggish-fma_pop cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 25.0290 (random, upstream runs 25.9646, 26.0237, 24.0403); fad_inf_r2 0.0391 (random, upstream runs 0.0664, 0.0200, 0.3263); 0 problems
GOLDEN fad_fadtk clap-laion-music-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 0.1592 (random, upstream runs 0.1577, 0.1572, 0.1593); fad_inf_r2 0.4225 (random, upstream runs 0.5478, 0.6080, 0.4534); 0 problems
GOLDEN fad_fadtk clap-laion-music-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 0.1587 (random, upstream runs 0.1573, 0.1578, 0.1589); fad_inf_r2 0.4453 (random, upstream runs 0.4682, 0.5621, 0.5716); 0 problems
GOLDEN fad_fadtk encodec-emb-dir cpu (cpu, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 169.6381 (random, upstream runs 169.8447, 169.7705, 169.3401); fad_inf_r2 0.8692 (random, upstream runs 0.7997, 0.8213, 0.7144); 0 problems
GOLDEN fad_fadtk encodec-emb-dir cuda (NVIDIA L40S, torch 2.7.0+cu126): fad |diff| 0 vs tolerance 1e-06; fad_inf 170.5663 (random, upstream runs 170.4249, 170.2566, 170.4968); fad_inf_r2 0.4688 (random, upstream runs 0.5586, 0.6773, 0.5123); 0 problems
GOLDEN kad_kadtk vggish-dir cpu (cpu, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk vggish-dir cuda (NVIDIA L40S, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk clap-laion-music-dir cpu (cpu, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN kad_kadtk clap-laion-music-dir cuda (NVIDIA L40S, torch 2.5.1+cu124): kad |diff| 0 vs tolerance 1e-06; 0 problems
GOLDEN-THREADS4 fad_fadtk vggish-dir cpu (torch 2.7.0+cu126): 1 values, largest |diff| 1.3e-06, limit 1.3e-05 (10 x observed)
GOLDEN-THREADS4 aesthetics_audiobox gen_small cpu (torch 2.7.0+cu126): 48 values, largest |diff| 1.91e-06, limit 2.9e-05 (10 x observed)
tests/integration/test_isolation.py::test_fake_np1_and_fake_np2_are_isolated PASSED
tests/integration/test_plugin_aesthetics.py::test_environment_loads_wav_with_torchaudio PASSED
tests/integration/test_plugin_aesthetics.py::test_broken_clip_is_listed_and_others_are_scored PASSED
tests/integration/test_plugin_aesthetics.py::test_core_run_skips_unreadable_file_and_scores_the_rest PASSED
tests/integration/test_plugin_clap.py::test_prefetch_fills_the_weights_folder PASSED
tests/integration/test_plugin_clap.py::test_scores_are_cosines_and_clips_without_prompt_are_listed PASSED
tests/integration/test_plugin_clap.py::test_no_prompts_skips_the_metric PASSED
tests/integration/test_plugin_fad_kad.py::test_two_torch_versions_in_one_run_and_inputs_untouched PASSED
tests/integration/test_plugin_fad_kad.py::test_fad_with_bundled_reference_and_per_clip PASSED
tests/integration/test_plugin_fad_kad.py::test_kad_runs_on_cpu_without_a_gpu PASSED
tests/integration/test_plugin_fad_kad.py::test_kad_refuses_the_bundled_reference PASSED
=============== 29 passed, 261 deselected in 3347.07s (0:55:47) ================
exit code: 0
```

Final fast run:

```text
$ uv run pytest
rootdir: ~/musegauge
configfile: pyproject.toml
testpaths: tests
collected 290 items / 29 deselected / 261 selected

tests/integration/test_e2e_fakes.py ..............                       [  5%]
tests/integration/test_exit_codes.py ............                        [  9%]
tests/unit/test_cli.py ...................................               [ 23%]
tests/unit/test_clips.py ......................                          [ 31%]
tests/unit/test_config.py .........                                      [ 35%]
tests/unit/test_envs.py ........                                         [ 38%]
tests/unit/test_errors.py ..                                             [ 39%]
tests/unit/test_registry.py ...............................              [ 50%]
tests/unit/test_report.py .....                                          [ 52%]
tests/unit/test_results.py ...............                               [ 58%]
tests/unit/test_runner.py ............                                   [ 63%]
tests/unit/test_runtime.py .............                                 [ 68%]
tests/unit/test_schemas.py ..............................                [ 79%]
tests/unit/test_staging.py ...........                                   [ 83%]
tests/unit/test_stats.py ............                                    [ 88%]
tests/unit/test_verify_facts.py ...                                      [ 89%]
tests/unit/test_version.py .                                             [ 90%]
tests/unit/test_warnings.py ..................                           [ 96%]
tests/unit/test_wrappers.py ........                                     [100%]

===================== 261 passed, 29 deselected in 22.45s ======================
exit code: 0
```

