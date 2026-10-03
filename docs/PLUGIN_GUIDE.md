# Writing a plugin

A plugin runs one family of metrics in its own Python environment. The core never imports it:
it builds the environment with uv, writes a `request.json`, starts the plugin's Python with the
runtime shim, and reads back a `response.json`. This guide adds a plugin step by step, using the
test plugin `tests/fake_plugins/fake_clip` as the template. The steps below were run on
2026-10-03 and worked as shown.

## 1. Copy the template

A plugin is a folder with four things:

```text
my_plugins/loudness_simple/
  manifest.yaml       # what the plugin is and which metrics it has
  wrapper.py          # run(request) and prefetch(metric_id, options)
  requirements.in     # what to install
  locks/linux-x86_64.txt   # the fully pinned lock made from requirements.in
```

```bash
mkdir my_plugins
cp -r tests/fake_plugins/fake_clip my_plugins/loudness_simple
```

The folder name must equal `plugin_id` in the manifest. Built-in plugins live in
`src/musegauge/plugins/`; outside plugins are found through `MUSEGAUGE_PLUGIN_PATH` (one or more
folders that contain plugin folders, separated by `:`). Two plugins with the same `plugin_id` or
the same metric id are an error.

## 2. Edit the manifest

In `my_plugins/loudness_simple/manifest.yaml` set at least:

- `plugin_id: loudness_simple` (pattern `^[a-z0-9_]+$`, equal to the folder name)
- `family: loudness` (the first part of every metric id in this plugin)
- each metric `id`, for example `loudness.mean-abs@1` (pattern `family.variant@N`)

Then go through the other fields (the schema is `src/musegauge/schemas/manifest.schema.json`; a
full example is `tests/data/manifest.example.yaml`):

| Field | Meaning |
| --- | --- |
| `kind` | `clip` (one score per clip; the core averages) or `set` (compares sets; needs a reference) |
| `python` | Python version for the environment, for example `"3.11"`; uv downloads it if missing |
| `smoke` | a command run once after the build, for example `["python", "-c", "import mypackage"]` |
| `system_tools` | programs that must exist (`required`, exit 4 if missing) or should (`optional`) |
| `needs` | `reference: true` if a reference is required; `prompts: true` if prompts are required |
| `reference_modes`, `bundled_references` | which reference forms the plugin accepts (`dir`, `bundled`) |
| `upstream` | the upstream package and version (informational; the wrapper reports the installed one) |
| `trust_remote_code` | `true` if the plugin runs code downloaded at run time (the core warns) |
| `runtime_downloads` | `torch_hub`, `huggingface`, `zenodo`, `other`: what `setup --fetch-weights` must fill |
| `metrics[].options` | passed to the wrapper in `request.options` (plus `per_clip`) |
| `metrics[].primary` | a display choice only |
| `metrics[].definition` | what is computed and by which package version; copied into results and the report |
| `metrics[].licence` | `code`, `weights`, `data` blocks and `commercial_ok`. Never guess: use `status: unknown` with `check_urls`, and `commercial_ok: unknown` |

Check it:

```bash
musegauge validate --plugin my_plugins/loudness_simple      # prints OK, or one line per problem
MUSEGAUGE_PLUGIN_PATH=my_plugins musegauge info loudness.mean-abs@1
```

## 3. Requirements and lock

`requirements.in` names the upstream package with an exact version. If torch is involved, pin
torch, torchaudio (and torchvision if the package imports it) as a matched set: look up the torch
requirement of that torchaudio version on PyPI (`docs/VERIFIED_FACTS.md`, U3). Add any package the
upstream code imports without declaring it, and say why in a comment.

Make the lock from the plugin folder (flags checked with uv 0.12.22):

```bash
uv pip compile requirements.in --python-version 3.11 --python-platform x86_64-unknown-linux-gnu \
  --generate-hashes -o locks/linux-x86_64.txt
```

A plugin without a lock for the current platform is skipped with `NO_LOCK`, unless the user
passes `--allow-unlocked` (then the results say `reproducible: false`). A plugin with no
dependencies can use a lock file that holds only a comment, as the fake plugins do.

## 4. Write the wrapper

`wrapper.py` defines two functions. The runtime shim (`musegauge_runtime.run`) loads it by file
path in the plugin's own environment, with only the allowed environment variables
(`docs/DECISIONS.md`, section 4.4 and A11, A13).

```python
def run(request: dict) -> dict: ...
def prefetch(metric_id: str, options: dict) -> dict: ...   # {"downloaded": [...], "notes": [...]}
```

`request` follows `src/musegauge/schemas/request.schema.json` (example:
`tests/data/request.example.json`). The staged clips are in `request["generated"]["dir"]`, one
file per entry of `request["generated"]["clips"]` (`clip_id`, `file`, `prompt`, `duration_s`,
`sample_rate_hz`, `channels`). The reference, if any, is in `request["reference"]`.

Return what you know; the shim fills `schema`, `metric_id`, `status: ok`, empty lists,
`upstream: null`, `env: {}`, `error: null` and `timing_s`, turns non-finite numbers into `null`
with `NAN_SCORE`, and turns an exception into an error response with the last 40 lines of the
traceback. The response follows `response.schema.json` (example: `tests/data/response.example.json`):

- clip metric: `clip_scores = [{"clip_id": ..., "scores": {"name": value, ...}}, ...]`
- set metric: `scores = [{"name": ..., "value": ..., "kind": "set" | "aux"}]`
- `clips_failed = [{"clip_id": ..., "reason": ...}]` for clips you could not score
- `upstream = {"package": ..., "version": importlib.metadata.version(...), "invocation": "the real call"}`
- `env = {"python": ..., "torch": ..., "device": ..., ...}` (any extra keys are kept)
- `warnings = [{"code": "UPPER_CASE", "message": ...}]`

Rules every wrapper follows (spec section 9.1):

1. Import the upstream package inside the functions, not at the top of the file.
2. Never edit or monkey-patch upstream code. If something cannot be fixed with a flag, return an
   error and write it into `docs/UPSTREAM_NOTES.md`.
3. Write only inside `request["paths"]["work_dir"]`; never into the audio folders.
4. Catch errors per clip, so one bad clip does not fail the metric; after a failed batch, retry its
   clips one by one.
5. Seed Python `random`, numpy and torch from `request["seed"]`; if the tool has randomness you
   cannot seed, add a warning.
6. Resolve `device: auto` yourself and report the device used in `env`.
7. Report the upstream version from the installed package metadata, never hard coded.

## 5. Build, fetch and run

```bash
export MUSEGAUGE_PLUGIN_PATH=my_plugins
musegauge setup --metrics loudness.mean-abs@1 --fetch-weights
python tests/make_fixtures.py fixtures
musegauge run --generated fixtures/gen_small --metrics loudness.mean-abs@1 --out out
```

Output of this walk-through on 2026-10-03:

```text
musegauge: plugin loudness_simple: environment ready: home/envs/loudness_simple-ff9ebfb1
musegauge: prefetch loudness.mean-abs@1: ok (0.0 s)
musegauge: metric loudness.mean-abs@1: ok
| loudness.mean-abs@1 | amplitude | 0.163 ± 0.023 | [0.152, 0.175] | 12 | ok |
```

If the run fails, look at `out/logs/<plugin_id>.log` and `out/responses/<metric_id>.response.json`.

## 6. Tests

- Fast tests: put a copy of the plugin under `tests/fake_plugins/` only if it has no dependencies.
- Golden test (section 11.6): write a direct script in `tests/golden_scripts/` that calls the
  upstream tool with no harness code, add a case to `tests/golden_scripts/cases.py`, record with
  `python tests/golden_scripts/record_golden.py PLUGIN_ID --device cpu|cuda` (numbers from your
  machine only), and run `scripts/run_golden.sh CORES` (`docs/TESTING_REAL_PLUGINS.md`).
- Write `docs/plugins/<plugin_id>.md`: the exact version and call, every file read and written,
  every download with its size and licence, and every difference from upstream defaults.

## 7. Changing a published metric

Once a metric id has been released, any change that can move its numbers (a new pin, checkpoint,
preprocessing, wrapper logic or option) needs a new version number after `@`, and a line in
`CHANGELOG.md`.
