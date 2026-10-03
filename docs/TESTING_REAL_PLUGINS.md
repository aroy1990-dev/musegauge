# Testing the real plugins

(This file replaces `docs/GPU_TESTS.md` of the spec layout; amendment A18.)

The real plugin environments take about 24 GB and their golden numbers are tied to the machine
they were recorded on, so hosted CI runs only the fake plugins (amendment A17). The tests with
the real plugins are run **by hand on a server**.

## How to run them

```bash
musegauge setup --all --fetch-weights          # once, with network
scripts/run_golden.sh 16                       # all golden cases on cores 0-15, nice -n 19
scripts/run_golden.sh 16 -k "kad and cpu"      # a subset
nice -n 19 taskset -c 0-15 uv run pytest -m slow -v -s    # every slow test
```

`scripts/run_golden.sh CORES` prints the golden files and the conditions they were recorded
under, then runs `tests/integration/test_golden.py` under `nice -n 19 taskset -c 0-(CORES-1)`.
GPU cases use the GPU with the most free memory, alone (`CUDA_VISIBLE_DEVICES`), and need at
least 4,000 MiB free; otherwise they are skipped with a message.

## Rules the golden tests follow (spec section 11.6 and amendments)

- Golden numbers come only from direct runs of the upstream tools on this machine
  (`tests/golden_scripts/record_golden.py PLUGIN --device cpu|cuda`, three runs each, on fresh
  copies of the synthetic fixtures).
- Tolerance per value: `max(10 * standard deviation of the three runs, 1e-6)`.
- A case is skipped (with a message) when the device, the torch version, or, for CPU cases, the
  number of cores differs from the stored one. CPU results change with the thread count by about
  1e-6 to 5e-6 (`docs/VERIFIED_FACTS.md`).
- Scores from randomness the harness cannot seed (`fad_inf`, `fad_inf_r2`) are only checked to be
  present and finite (A10).
- `--threads 4` check: fails only if a CPU difference is larger than 10 times the one observed on
  2026-10-03 (1.3e-6 for `fad`, 2.9e-6 for Audiobox).
- A golden file also stores the SHA-256 of the fixture folders; if the synthetic fixtures change,
  the test fails and the numbers must be recorded again on this machine.

## Where the stored numbers came from

All stored golden numbers (`tests/golden/*.json`) were recorded on 2026-10-03 (UTC times in the
files) on one machine:

| Item | Value |
| --- | --- |
| Machine | Linux container on a server, Ubuntu 24.04.1 LTS, kernel 6.8.0-48 |
| CPU | 2 × AMD EPYC 9554 64-Core (256 hardware threads); runs limited to cores 0-15 with `taskset -c 0-15`, `nice -n 19` |
| Memory | 377 GiB |
| GPU | 6 × NVIDIA L40S (46,068 MiB); one GPU per run (GPU 0 for every recording); shared with other users' jobs earlier that day |
| NVIDIA driver | 560.35.03 (CUDA 12.6) |
| torch threads | 16 (`torch.get_num_threads()` under `taskset -c 0-15`) |
| uv | 0.12.22 |
| Python in the plugin environments | 3.11.17 (uv-managed CPython) |

| Plugin | Environment | Upstream | torch | Cases (CPU and CUDA each) |
| --- | --- | --- | --- | --- |
| `aesthetics_audiobox` | `aesthetics_audiobox-76e395f1` | audiobox-aesthetics 0.0.4 | 2.7.0+cu126 | `gen_small` (48 per-clip values) |
| `clapscore_laion` | `clapscore_laion-a3ecbe8b` | laion-clap 1.1.7 | 2.7.0+cu126 | `gen_small` (12 per-clip values) |
| `fad_fadtk` | `fad_fadtk-f7a67ac7` | fadtk 1.1.0 | 2.7.0+cu126 | `vggish-dir`, `vggish-fma_pop`, `clap-laion-music-dir`, `encodec-emb-dir` |
| `kad_kadtk` | `kad_kadtk-391cfe89` | kadtk 1.1.0 | 2.5.1+cu124 | `vggish-dir`, `clap-laion-music-dir` |

The environment id ends in the first 8 hex characters of the SHA-256 over the Python version and
the lock file, so a changed lock gives a new id; the golden files store it.

## Last full run

On 2026-10-03, `nice -n 19 taskset -c 0-15 uv run pytest -m slow -v -s` passed all 16 golden
cases, the isolation test and every plugin test (the output is in `docs/PROGRESS.md`, M7 and M8).
In every set of three upstream runs, each deterministic score was identical, so every
tolerance was 1e-6, and every harness value differed from the upstream one by 0 (about 1e-17 for
the CLAP cosine).

## GPU in a container

Not tested: the build machine has no Docker.
