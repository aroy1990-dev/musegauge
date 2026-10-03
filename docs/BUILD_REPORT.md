# Build report: musegauge 0.1.0

Date: 2026-10-03. Builder: Claude Code, following Roy's build spec of 2026-10-02 (kept private,
not in this repository). Version 0.1.0 is built and checked on the build machine. The source is
published at https://github.com/aroy1990-dev/musegauge as one commit tagged `v0.1.0`; nothing is
on PyPI and no image is pushed. The milestone history (M0 to M9) is kept in a private backup.
The acceptance output of every milestone is in `docs/PROGRESS.md`. Every change from the spec is
in `docs/DECISIONS.md` ("Amendments to the spec": C1 to C4 and A1 to A22, each with what the spec
said, what was built and why).

## Status per spec section

| Section | Status | Notes |
| --- | --- | --- |
| 1. Read this first | done with a change | All "done" conditions hold except one: of the install paths, pip and uvx were tested, while Docker was written but not built and Apptainer not tested, because neither exists on the build machine. The Docker `full` image was removed (A16). Every metric shows its licence and `UNKNOWN_LICENCE`. |
| 2. Why uv | done | uv 0.12.22 (installed with pip) builds every environment; `uv.find_uv_bin()` is used; `EnvBackend` / `UvBackend`. |
| 3. Facts | done with a change | `scripts/verify_facts.py` passes 8 of 8. U1 to U10 answered or marked "not checked here" in `VERIFIED_FACTS.md`. F10 (fadtk needs sox) does not hold for fadtk/kadtk 1.1.0 (correction recorded; A6). F16 (Pythons on the machine) differs here: only 3.12 was installed; uv downloaded 3.11. |
| 4. Architecture | done with a change | Core loop, environments, staging, plugin start and environment scrubbing as specified, with: reference staged per run (A9), `--no-fetch` proxy block (A13), `NETWORK_ERROR` (A14), `--no-fetch` exit 4 without environments (A15), `--threads` variables (A11), symlink staging (C1), exit code 130 on interrupt. |
| 5. Repository layout | done with a change | As specified, except: `docs/GPU_TESTS.md` is `docs/TESTING_REAL_PLUGINS.md` (A18); suite files are named `<id>@<version>.yaml` (section 7.4); the schema validator is in `schemas/__init__.py` (C3); `.github/workflows/docker.yml` is folded into `ci.yml` (A17); `LICENSE` is Apache-2.0 (D2, answered at the end of M9); extra: `uv.lock`, `scripts/run_golden.sh`, `tests/data/`; the build spec is kept private (not in the repository). |
| 6. Data contracts | done with a change | Seven JSON Schemas, each with a valid example tested against our validator and jsonschema. Results additions (A1); `suite` at top level (C2); `manifest_sha256` defined (C4); `run.threads` (A11). `schema` is 1 everywhere. |
| 7. Command line | done with a change | All eight commands, the preflight table and exit codes 0, 2, 3, 4, 5, 6, 10 (each produced by a test). No `--plugin-path` (A4). New: `run --threads` (A11). `doctor` reports a missing sox as WARN (A6). |
| 8. Install and run paths | done with a change | pip and uvx tested. Docker `slim` written, not built; `full` removed (A16). Apptainer written, not tested. GPU in a container not tested. `INSTALL.md` labels each. |
| 9. Metric plugins | done with a change | Four plugins, seven metrics, golden tests passing on CPU and GPU. Locks with extra pins agreed with Roy (A21, A22). `trust_remote_code: true` for FAD and KAD (A7); start-up CLAP downloads kept (A8); `UNSEEDED_RANDOMNESS` and `FAD_INF_FAILED` (A5, A12). |
| 10. Statistics, warnings, report | done with a change | Bootstrap as specified; every warning code with raise and no-raise tests; `NO_LOCK`, `UNSEEDED_RANDOMNESS`, `FAD_INF_FAILED` added (A3, A5, A12). The report shows thread settings and the unpinned VGGish code (A7, A11). |
| 11. Test plan | done with a change | Fast set 261 tests, slow set 29 tests. Golden tests compare random scores for presence only (A10) and CPU numbers only at the recorded core count (A19); a `--threads 4` check (A20). CI: hosted runners run fakes only; real golden tests by hand (A17). Docker tests not run (no Docker). |
| 12. Milestones | done with a change | M0 to M9 passed with output in `PROGRESS.md`. M7: Docker and Apptainer checks not run (no Docker or Apptainer); the offline test was run natively with the proxy method. |

## Decisions that still need Roy

| ID | Question | Default in use now |
| --- | --- | --- |
| D1 | Name of the tool | `musegauge` (free on PyPI and GitHub when checked on 2026-10-03, U9) |
| D4 | Contents of the default suite | `t2m-basic@1` (fad.vggish, fad.clap-laion-music, clapscore.laion-music, aesthetics.audiobox, reference bundled fma_pop) |
| D7 | Owner of the container registry and where images go | nothing pushed; placeholder `ghcr.io/OWNER/musegauge:TAG` |

D2 is answered: Apache-2.0 (`LICENSE` added and `license = "Apache-2.0"` in `pyproject.toml`
on 2026-10-03, at Roy's request). D3 is answered: Roy's call; the source is published at
https://github.com/aroy1990-dev/musegauge (2026-10-03). D5 (bundled fma_pop for FAD only), D6 (Python 3.11 in plugins), D8 (Linux x86_64), D9 (no MERT or
MuQ) and D10 (no telemetry) use the spec defaults. For D5, whether fma_pop is the right baseline
for a study, and its data licence, are still for Roy to check (below).

## Every `unknown` licence

From the manifests (`docs/LICENCES.md`). `commercial_ok` is `unknown` for all seven metrics.

| Metric | Code | Weights | Data | commercial_ok |
| --- | --- | --- | --- | --- |
| `aesthetics.audiobox@1` | CC-BY-4.0 (read from the wheel; README: part MIT) | **unknown** (model card said cc-by-4.0) | not applicable | **unknown** |
| `clapscore.laion-music@1` | CC0-1.0 (read from the wheel; metadata classifier says Apache) | CC0-1.0, stated on the model page (roberta-base also downloaded: card said mit) | not applicable | **unknown** |
| `fad.vggish@1` | MIT (read from the wheel) | **unknown** (torchvggish repo Apache-2.0; weights ported from tensorflow/models) | **unknown** (fma_pop statistics) | **unknown** |
| `fad.clap-laion-music@1` | MIT | **unknown** (LAION-CLAP card cc0-1.0) | **unknown** (fma_pop) | **unknown** |
| `fad.encodec-emb@1` | MIT | **unknown** (EnCodec README: code MIT, weights not stated) | **unknown** (fma_pop) | **unknown** |
| `kad.vggish@1` | MIT | **unknown** | not applicable | **unknown** |
| `kad.clap-laion-music@1` | MIT | **unknown** | not applicable | **unknown** |

Also downloaded but not used by a 0.1 metric (A8, `import laion_clap`): `630k-audioset-best.pt`
(LAION card cc0-1.0), `CLAP_weights_2023.pth` (MS-CLAP card ms-pl), bert-base-uncased and
facebook/bart-base tokenizers (cards apache-2.0). Not checked at all: the fma_pop statistics, the
PANNs weights.

## Every "not tested" item

- Docker `slim`: `docker build`, `docker run ... doctor`, fake plugins with `--network none`.
- GPU inside a container (`torch.cuda.is_available()` in a container).
- Apptainer: build, run, and how to pass an environment variable (U8).
- `docker manifest inspect` (U7); image tags were checked through the registry HTTP APIs instead.
- `--no-fetch` with a truly blocked network: tested only with the proxy method (`unshare -rn` is not permitted on the build machine).
- The GitHub Actions workflows (`ci.yml`, `slow.yml`): never run before publishing.
- `pip install musegauge` and `uvx musegauge` from PyPI (not on PyPI); pip from a wheel and uvx from the source folder were tested.
- macOS (best effort, no lock files), Linux on ARM (not supported), Windows (refusal message tested by a unit test only).
- The sox check (A6) with mp3 or ogg input (WAV and FLAC at 16, 32 and 44.1 kHz were tested).
- `FAD_INF_FAILED` in a real run (the wrapper path is tested with stand-ins; fadtk never failed on `--inf` here).
- `NETWORK_ERROR` with a real GitHub refusal (tested with a fake plugin and recorded text; the one real refusal seen, during a recording, left no HTTP error text in its log).
- CPU golden numbers on any core count other than 16 (they are skipped there by design, A19).

## Unknowns left

- Every `unknown` in the manifests: the table above (weights of six metrics, fma_pop data of three FAD metrics, `commercial_ok` of all seven).
- Facts not checked here: U7 (`docker manifest inspect`), U8 (Apptainer commands), and U4 in part (weight licences read from pages, never confirmed).
- The cause of the one failed GPU recording on 2026-10-03 (`MaybeEncodingError ... cannot pickle '_io.BufferedReader'` in a fadtk worker) is not confirmed; an HTTP error from GitHub in torch.hub fits but its text was not kept (`UPSTREAM_NOTES.md`).
- The VGGish code is not pinned to a commit (A7): a change on github.com/harritaylor/torchvggish `master` would reach a new cache.

## Deviations from the spec

All are listed with what the spec said, what was built and why in `docs/DECISIONS.md`:
C1 to C4 (contradictions resolved before M1) and A1 to A22. In short: results fields (A1),
prefetch `--options` (A2), `NO_LOCK` (A3), no `--plugin-path` (A4), `UNSEEDED_RANDOMNESS` (A5),
sox not required (A6), `trust_remote_code: true` (A7), start-up CLAP downloads kept (A8),
reference staged per run (A9), random scores presence-only in golden tests (A10), `--threads`
(A11), `FAD_INF_FAILED` (A12), `--no-fetch` proxy block (A13), `NETWORK_ERROR` (A14), `--no-fetch`
exit 4 without environments (A15), no Docker `full` (A16), CI layout (A17),
`TESTING_REAL_PLUGINS.md` (A18), CPU golden per core count (A19), `--threads 4` check (A20),
audiobox lock additions (A21), clap lock constraint (A22). Builder choices that are not
amendments (for example exit 130 on interrupt, exit codes for skipped metrics, `doctor` levels)
are in the M0 to M7 sections of the same file.

## Roy's to-do

1. Answer D1, D4 and D7 (above).
2. Read the licence sources and set `commercial_ok` (and the `unknown` statuses) for all seven
   metrics, including the fma_pop statistics and the weights downloaded but not used (U4).
3. Decide whether fma_pop is the right FAD baseline for each study (D5).
4. On a host with Docker: build `slim`, run `doctor`, the fake plugins with `--network none`, the
   offline test with a named volume, and `torch.cuda.is_available()` in the container
   (`docker/README.md`). With Apptainer: the commands in `docs/INSTALL.md`.
5. On GitHub, check the first runs of `ci.yml` (it runs on every push) and `slow.yml`.
6. Real golden tests are run by hand: `scripts/run_golden.sh 16` on this server
   (`docs/TESTING_REAL_PLUGINS.md`). The stored numbers come from 16 cores of this machine and one
   NVIDIA L40S.

## Final test output

Release checks (M9):

```text
$ uv build
Successfully built dist/musegauge-0.1.0.tar.gz
Successfully built dist/musegauge-0.1.0-py3-none-any.whl
$ uvx twine check dist/*
Checking dist/musegauge-0.1.0-py3-none-any.whl: PASSED
Checking dist/musegauge-0.1.0.tar.gz: PASSED
$ python3 -m venv clean && clean/bin/pip install dist/musegauge-0.1.0-py3-none-any.whl
$ clean/bin/musegauge --version
musegauge 0.1.0
$ (wheel contents check, as in ci.yml)
dist/musegauge-0.1.0-py3-none-any.whl: 12 required files, 0 missing
$ python scripts/verify_facts.py
8 of 8 checks passed
$ git remote -v
(no remote)
```

After Roy's final message (D2 answered: Apache-2.0), the wheel was built again with `LICENSE`
and smoke-tested in a clean virtual environment:

```text
$ python3 -m venv smoke && smoke/bin/pip install dist/musegauge-0.1.0-py3-none-any.whl
$ musegauge --version
musegauge 0.1.0
$ musegauge list
Suites:
  t2m-basic@1: Text-to-music basics: FAD on the bundled reference, CLAP score, aesthetics (default reference: bundled:fma_pop)
  t2m-full@1: t2m-basic plus KAD. KAD needs reference audio, so give --reference DIR
Metrics:
  METRIC                   KIND  PLUGIN               NEEDS      COMMERCIAL_OK
  aesthetics.audiobox@1    clip  aesthetics_audiobox  -          unknown
  clapscore.laion-music@1  clip  clapscore_laion      prompts    unknown
  fad.clap-laion-music@1   set   fad_fadtk            reference  unknown
  fad.encodec-emb@1        set   fad_fadtk            reference  unknown
  fad.vggish@1             set   fad_fadtk            reference  unknown
  kad.clap-laion-music@1   set   kad_kadtk            reference  unknown
  kad.vggish@1             set   kad_kadtk            reference  unknown
exit code: 0
(wheel METADATA: License-Expression: Apache-2.0, License-File: LICENSE)
```

Pre-publication check (Roy's final message): institution names and the build server's paths were removed from the files, the build spec is kept private (it is not in this repository), there are no logos or image files and no e-mail addresses.

Fast set:

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
$ uv run ruff check
All checks passed!
```

Slow set (all real plugins, golden tests, isolation), final run on the final code:

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
