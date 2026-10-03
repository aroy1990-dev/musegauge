# Decisions

Choices made while building, and the defaults used for Roy's open decisions (spec section 13.1).

## Defaults in use for Roy's decisions

| ID | Default in use | Since |
| --- | --- | --- |
| D1 | Name `musegauge`. U9 found no GitHub repository or user with that name on 2026-10-03. | M0 |
| D2 | Answered 2026-10-03: Apache-2.0 (`LICENSE`, `license` in `pyproject.toml`). | M9 |
| D3 | Answered 2026-10-03 (Roy's call): source published at https://github.com/aroy1990-dev/musegauge; no PyPI. | M9 |
| D4 | Default suite `t2m-basic@1`. | M0 |
| D5 | Bundled `fma_pop` for FAD only. | M0 |
| D6 | Python 3.11 for the real plugin environments. | M0 |
| D7 | No image pushed. Placeholder `ghcr.io/OWNER/musegauge:TAG` in docs. | M0 |
| D8 | Linux x86_64 supported. Others as in the spec. | M0 |
| D9 | No MERT or MuQ metrics. | M0 |
| D10 | No telemetry. | M0 |

## Builder choices

### M0

- **Build backend: hatchling.** Check: `uv pip install --python .venv/bin/python hatchling --dry-run` exited 0 and would install hatchling 1.32.4 (2026-10-03, see `VERIFIED_FACTS.md`).
- **Repository root.** The spec's layout is applied at the repository root (no extra sub-folder named `musegauge/`). The build spec itself is kept private and is not in the repository.
- **Version in one place.** `src/musegauge/__init__.py` holds `__version__`. `pyproject.toml` reads it through `[tool.hatch.version]`.
- **Default pytest run.** `pyproject.toml` sets `addopts = "-m 'not slow and not network and not gpu and not docker'"`, so a plain `pytest` is the fast set (section 11.1). `pytest -m slow` replaces this filter (checked, see `VERIFIED_FACTS.md`).
- **How uv got onto this machine.** `python3.12 -m venv .venv`, then `.venv/bin/pip install uv`, then `.venv/bin/uv sync --extra dev`. `uv sync` wrote `uv.lock` for the core's development environment. It is committed. It is not used by end users or by plugin environments.
- **ruff.** Default rule set, line length 100, target Python 3.10.

### M1

Choices where the spec says nothing, or where I read it one way. Items that were marked "ask Roy" were answered at GATE 1; see "Amendments to the spec" below.

- **Results file fields beyond the section 6.5 example (approved, amendment A1).** Section 6.5 says its example is simplified. I added fields that other sections need: `generated.n_with_prompt` (the report's "Prompts" line, section 10.3, is made only from `results.json`), `generated.extra` (section 6.1 keeps extra clip fields "in the results under extra"; stored by clip_id, only for clips that have any), `metrics[].kind` (set or clip), `metrics[].clips_failed` (from the response), and `scores[].kind` (set, aux or clip). `metrics[].env` and `upstream` are `null` when the plugin never ran.
- **Prefetch mode takes `--options FILE` (approved, amendment A2).** Section 9.1 says the shim calls `prefetch` "with the options from the manifest", but the shim is standard library only and cannot read YAML. The core will write the metric's options as JSON and pass `--options FILE`. Without it, the options are `{}`. The prefetch response has its own schema, `prefetch.schema.json`.
- **Warning code `NO_LOCK` (approved with scope `run`, amendment A3).** Section 4.2 says a plugin with no lock for this platform is skipped "with a warning". The section 10.2 table had no code for it.
- **`--plugin-path` (answered, amendment A4).** Section 5 says "There is no command line flag for it in 0.1". Section 7 listed `--plugin-path DIR` as a global flag. Roy: section 5 is right.
- **Suite file names.** Section 5 shows `suites/t2m-basic.yaml`, section 7.4 says `<suite_id>@<version>.yaml`. I followed 7.4, because its rule "add a new file with the next version number" needs the version in the name.
- **Schema validator location.** The validator lives in `src/musegauge/schemas/__init__.py`, next to the schema files, so the section 5 module list is unchanged. It refuses any schema keyword it does not implement. Supported: `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`, `pattern`, `minLength`, `minimum`, `exclusiveMinimum`, `maximum`, `minItems`, `anyOf`, `$ref` (local `#/$defs/` only), `$defs`. A test compares it with jsonschema on several hundred altered copies of each example file.
- **Order of the environment lock.** `ensure` first looks for `.ready` without the lock, and only takes the lock to build (then checks `.ready` again under the lock). Result is the same as section 4.2, but a finished environment in a read-only folder (the Docker `full` image, section 8.3) can be used without creating a lock file there.
- **Smoke command.** A first word `python` becomes `ENV/bin/python`. Any other first word becomes `ENV/bin/<word>`. The smoke command runs with the scrubbed environment of section 4.4, without the runtime path.
- **Exit codes with skipped metrics.** A skipped metric (for example `NO_PROMPTS`, `NO_LOCK`) is neither a success nor a failure. Exit 0 if no metric failed; 5 if some failed and none succeeded; 10 if some failed and some succeeded.
- **Exit code 130 on interrupt.** Not in the section 7.3 table. On SIGINT the core stops the plugin's process group, deletes `work/<run-id>`, prints `musegauge: interrupted` and exits 130 (the shell convention).
- **Usage errors (exit 2).** Also used for: an unknown metric id or suite name, and `--prompts` together with `--manifest`. Usage errors are found before any input file is read.
- **Folder mode.** File extensions match without regard to case (`.WAV` counts). A staged file gets a lower-case extension. A file name that is not a valid clip id is an input error (exit 3) that lists the names.
- **Prompt files.** A prompt for a clip_id with no audio file is ignored, with a count printed to standard error. An empty prompt or a repeated clip_id is an input error.
- **Reference folders.** Same rule as folder mode: audio files directly inside the folder. Files `soundfile` cannot read are left out of staging and of `ref_hash`. `ref_hash` is SHA-256 over compact JSON of the sorted list of `[file name, SHA-256 of content]`. The hash cache is `$MUSEGAUGE_HOME/refs/hash_cache.json`.
- **Bootstrap key.** "First 8 bytes of sha256 read as an integer" is read big-endian (the same as the first 16 hex characters of the digest).
- **Process groups.** Each plugin process starts in its own session. On timeout or interrupt the core sends SIGTERM to the group, waits up to 5 s, then SIGKILL. After a normal exit it also stops anything the wrapper left running.
- **Proxy variables.** Only the upper-case names listed in section 4.4 pass to plugins. Lower-case `http_proxy` and friends do not. See `IDEAS.md`.
- **`tool.git_commit`** is always `null` in 0.1.
- **Shim defaults.** The shim fills `schema`, `metric_id`, `status` (`ok`), empty lists, `upstream` (`null`), `env` (`{}`), `error` (`null`) and `timing_s` when a wrapper leaves them out. When `status` is `error` it empties `scores` and `clip_scores`.
- **Fake plugins.** Fast fakes have `python: "3.12"` in the repository. `tests/conftest.py` copies them and sets the test interpreter's version (section 11.4). Fast tests set `UV_OFFLINE=1` and `UV_PYTHON_DOWNLOADS=never`, so they cannot use the network. `fake_np1` uses Python 3.11 with `numpy<2` (locked 1.26.4). `fake_np2` uses Python 3.12 with `numpy>=2,<2.1` (locked 2.0.2): with plain `numpy>=2` the lock would get the same numpy as the core (2.5.3) and the isolation test could not tell them apart. Python 3.11 is not installed on this machine; uv downloaded it (`VERIFIED_FACTS.md`).
- **Lock command for the fake plugins.** `uv pip compile requirements.in --python-version <v> --python-platform x86_64-unknown-linux-gnu --generate-hashes -o locks/linux-x86_64.txt`. The platform value for the real plugins is decided in M3, after checking which manylinux tag the torch wheels need.

### M2

- **Where command output goes.** Section 7 says standard output is only for `list`, `info`, `report` and `run --json`. So `doctor`, `setup`, `clean` and `validate` print to standard error.
- **`doctor` levels.** Platform: `linux-x86_64` OK, macOS WARN (best effort), anything else FAIL. `nvidia-smi` missing is WARN ("report only"). A plugin without a lock for this platform is WARN. sox missing is FAIL; ffmpeg missing is WARN (section 7.2).
- **`info`** prints the manifest entry as YAML.
- **`setup`** without `--suite`, `--metrics` or `--all` uses the default suite `t2m-basic`. Exit codes follow `run`: 5 if every metric failed, 10 if some did. Build and prefetch logs go to `$MUSEGAUGE_HOME/work/setup-<id>/`, which is deleted when nothing failed.
- **`clean`** needs at least one of `--envs`, `--work`, `--refs`, `--weights`, `--all` (else exit 2). Sizes count files only. Without `--yes` it reads the answer from standard input; no answer means nothing is deleted. A folder outside `MUSEGAUGE_HOME` (possible for `MUSEGAUGE_ENVS_DIR`) is refused with exit code 2.
- **`report`** checks the file against the results schema first; an invalid file is exit 3.
- **`validate --clips`** checks each line against the clip schema and looks for repeated clip ids. It does not check that the audio files exist.
- **Report card details (section 10.3).** For a set or helper score, the "Mean ± std" column shows the value alone. Errors are listed under Warnings as `error (metric ID): Type: message`. The software section lists each environment once, then one line for the core (Python, uv, platform). The section 10.1 sentence about the interval is added to "Notes for your paper".
- **sox location on the builder's machine.** `~/tools/sox/bin/sox`, SoX v14.4.2 from conda-forge, outside the repository, found through `SOX_PATH`. Steps in `docs/INSTALL.md`.

### M3

- **Missing `requests` and the torchaudio backend (asked Roy, 2026-10-03).** The audiobox smoke check failed on `import requests` (stop condition 3). Roy chose `huggingface_hub<1.0` plus `requests`, and `soundfile` so torchaudio always has a backend. Details in `UPSTREAM_NOTES.md`.
- **`primary: CE` for `aesthetics.audiobox@1` (ask Roy at GATE 2).** The manifest needs a `primary` score and the spec does not name one for Audiobox. I used CE, the first of the four in F15. It is not used in any calculation.
- **Lock platform value.** `--python-platform x86_64-unknown-linux-gnu` resolved torch 2.7.0 with its CUDA 12.6 libraries (`nvidia-*-cu12`), and the lock installed on this machine.
- **Device for Audiobox.** Upstream has no device argument. `--device cpu` hides the GPUs with `CUDA_VISIBLE_DEVICES=""` before torch starts; `--device cuda` stops with an error if CUDA is not available; `auto` lets upstream choose (cuda, mps, cpu).
- **Golden files.** One file per plugin, `tests/golden/<plugin_id>.json`, with numbers per case and per device, the versions, the GPU name and the SHA-256 of the fixture folders. The golden test fails (it does not skip) when the fixtures changed, because then the stored numbers no longer apply. Tolerance per value: `max(10 * std, 1e-6)` with numpy's default population standard deviation over the three runs.
- **Golden direct script uses the harness's batch grouping** (8). Batch grouping changed CPU scores in the 7th significant digit, so comparing different groupings would test batching, not the harness.
- **Slow tests use the user's `MUSEGAUGE_HOME`** (default `~/.cache/musegauge`), so environments and weights are built and downloaded once.
- **Choosing a GPU.** Tests and the golden recorder use the GPU with the most free memory, alone, and need at least 4,000 MiB free; otherwise the GPU case is skipped with a message.

### M4

- **torchvision in the clap lock.** laion-clap imports torchvision without declaring it. Spec section 4.2 says to pin torchvision with torch "if used", so the lock has `torchvision==0.22.0` (the pair for torch 2.7.0). I did not stop for this, because section 4.2 already covers it. Listed for GATE 2.
- **Explicit int16 round trip kept.** Spec step 2 is done in the wrapper even though laion-clap repeats it inside `get_audio_embedding_from_data`; the second round trip changes no value (checked), so the numbers are those of one round trip.
- **Audio loading.** `librosa.load(sr=48000, mono=True)` (librosa 0.11.0, default resampler), a dependency laion-clap already has. Written into the metric definition.
- **No batching across clips.** Each clip's windows go to laion-clap in one call, one clip at a time; prompts are embedded one at a time. `--batch-size` is not used by this plugin. This keeps the direct script and the wrapper doing the same computation.
- **Options in the manifest.** The checkpoint repo and file, `amodel`, sample rate, window and hop are manifest options, so `musegauge info` shows them and the wrapper reads them from the request.
- **Download tracking.** The wrapper's `NETWORK_FETCH` check and `prefetch` look at the Hugging Face cache entries of lukewys/laion_clap, roberta-base, bert-base-uncased and facebook/bart-base.

### M5

- **Questions asked before building (2026-10-03).** fadtk and kadtk do not use sox; they download three CLAP checkpoints at start; torch.hub runs remote code; FAD-inf is unseeded. Roy's answers are amendments A5 to A8. Two throwaway environments were built in a temporary folder to prove these points, then deleted.
- **Warning code `FAD_INF_FAILED` (ask Roy at GATE 2).** Section 9.2 says that when `--inf` fails, keep `fad` and "add a warning with the upstream error text", but names no code. The wrapper uses `FAD_INF_FAILED` (metric scope). It has not happened in any run here: fadtk raised no error even on 12 clips (U6).
- **All three FAD metrics use `inf: true`**, as in the section 6.2 example, so each reports `fad`, `fad_inf` and `fad_inf_r2`.
- **Torch sets.** `fad_fadtk`: torch 2.7.0, torchaudio 2.7.0, torchvision 0.22.0 (shared with the audiobox and clap environments, as Roy asked). `kad_kadtk`: torch 2.5.1, torchaudio 2.5.1, torchvision 0.20.1 (newest torch below 2.6).
- **`runtime_downloads`.** Both plugins list `torch_hub` and `huggingface`. The EnCodec weights come from dl.fbaipublicfiles.com but through torch.hub's URL loader into `$TORCH_HOME`, so they are counted as `torch_hub`.
- **VGGish warm-up.** Both wrappers call `torch.hub.load('harritaylor/torchvggish', 'vggish')` once before the command, to avoid the parallel-download race. With a filled cache this only reads files.
- **Device.** fadtk has no device flag and kadtk's flag covers only the kernel step, so `--device cpu` hides the GPUs for both. kadtk always gets an explicit `--device`.
- **Seeds.** The wrappers seed nothing that reaches the tools, because the tools run as separate commands. KAD (without `--inf`) and plain FAD have no sampling. FAD-inf is covered by `UNSEEDED_RANDOMNESS`.
- **Golden cases.** FAD: vggish with the `ref_small` folder, vggish with bundled `fma_pop`, clap-laion-music and encodec-emb with `ref_small`. KAD: vggish and clap-laion-music with `ref_small`. Each on CPU and on one GPU, three direct runs of the upstream command on fresh fixture copies, `-w 8` (the harness default here). `fad_inf` and `fad_inf_r2` are only checked to be present and finite (amendment A10).

### M6

- **Licence warnings on every selected metric.** `UNKNOWN_LICENCE` (or `NONCOMMERCIAL_WEIGHTS`) is added to every selected metric, also when it was skipped or failed, because it is a property of the metric, not of the run.
- **`FEW_CLIPS`** is added to set metrics that produced a response, counting the scored generated clips.
- **`REF_GEN_OVERLAP`** compares SHA-256 hashes of the generated files with those of a folder reference (only with a folder reference). Hashes are cached by path, size and modified time in `refs/hash_cache.json`.
- **`TRUST_REMOTE_CODE` is per plugin**, as section 6.2 defines `trust_remote_code`, so it also appears for `fad.clap-laion-music@1`, `fad.encodec-emb@1` and `kad.clap-laion-music@1`, which load no torch.hub code. The per-metric fact is in `env.remote_code` (only for VGGish metrics) and the report's software section.
- **`primary`.** No summary line exists in 0.1; `primary` is only copied into `results.json` and shown by `musegauge info`. `docs/METRICS.md` says it is a display choice only.
- **Metric ids stay `@1`.** The changes since the first plugin versions (for example A9) happened before any release, so no `@N` was bumped. From the first release on, every change that can move numbers bumps `@N` with a CHANGELOG line.
- **CPU golden numbers per core count.** Golden files store `cpu_cores` (from `os.sched_getaffinity`) and `torch_threads`; a CPU golden case is skipped with a message when the test runs on another core count. The `--threads 4` check is marked as an expected, documented difference (xfail, not strict).
- **`clean` sizes** count each hard-linked file once, so they match the disk space used.

### M7

- **`--no-fetch` network block.** Plugin processes get `HTTP_PROXY` and `HTTPS_PROXY` = `http://127.0.0.1:9` and `NO_PROXY` empty. It relies on nothing listening on local port 9 and on libraries honouring proxy variables. Tested end to end (`VERIFIED_FACTS.md`, M7 checks). `unshare -rn` was not allowed in the build container.
- **`NETWORK_ERROR` rule.** A failed metric gets error type `NETWORK_ERROR` only when its error text or the last 80 lines of its own section of the plugin log contain `torch/hub.py` together with `HTTPError` or `HTTP Error`. The original type and message stay in the message. Nothing is retried.
- **Docker.** Base `python:3.12-slim-bookworm` (tag checked through the Docker Hub API, not `docker manifest inspect`); uv copied from `ghcr.io/astral-sh/uv:0.12.22` as the uv Docker guide shows. The `full` target builds the environments with a temporary `MUSEGAUGE_HOME`, so tokenizer files fetched by smoke checks do not end up in the image. Nothing was built.
- **CI workflows.** `ci.yml`, `slow.yml` and `docker.yml` are written (section 11.7) with action versions checked to exist; none has run, because there is no GitHub remote (D3). `slow.yml` will skip CPU golden cases on runners that do not have 16 cores.

## Amendments to the spec

Each entry says what the spec said, what was built, and why. The build spec is kept private and
unchanged; these entries take precedence over it. C entries resolved contradictions before
M1; A entries changed the spec later. The data contracts are frozen: a further change needs
Roy's agreement and a new `schema` number.

### C1. 4.3 and 11.3, staging links

- **The spec said:** Section 4.3: stage with symbolic links, copy if a link fails. Section 11.3: "Hard link falls back to copy".
- **Built:** Symbolic links, copy as fallback; the test checks "symlink falls back to copy".
- **Why:** The two sections disagreed. Symlinks work across file systems (Docker mounts); fadtk and kadtk build cache paths from `Path(f).parent` without resolving links, so their caches stay in tool-owned folders. Roy, before M1.

### C2. 6.5 and 7.4, suite in results

- **The spec said:** Section 6.5 example: `suite` at the top level. Section 7.4: add `suite` to the `run` object.
- **Built:** Top level only.
- **Why:** The two sections disagreed; section 6 is the data contract. Roy, before M1.

### C3. 6 and 4.1, schema validation

- **The spec said:** Section 6: the code validates every file it reads or writes against its JSON Schema. Section 4.1: core dependencies are only uv, pyyaml, numpy, soundfile (jsonschema is dev only).
- **Built:** A small standard-library validator in `src/musegauge/schemas/__init__.py` for the keywords the schema files use; it refuses unknown keywords. Tests compare it with jsonschema on several hundred altered example documents.
- **Why:** Validation without breaking the dependency list. Roy, before M1.

### C4. 6.5, `generated.manifest_sha256`

- **The spec said:** The field is in the example but not defined; folder mode has no manifest file.
- **Built:** Manifest mode: SHA-256 of the clips file bytes. Folder mode: SHA-256 of a canonical JSON-lines list (clip_id, file name, prompt; sorted by clip_id). Never null.
- **Why:** So the field always identifies the input. Roy, before M1.

### A1. 6.5, results file

- **The spec said:** The example `results.json` ("simplified on purpose").
- **Built:** Added `generated.n_with_prompt`, `generated.extra`, `metrics[].kind`, `metrics[].clips_failed`, `scores[].kind`; `schema` stays 1.
- **Why:** Other sections need them: the report's Prompts line is made only from `results.json`; section 6.1 keeps extra clip fields "in the results under extra". GATE 1.

### A2. 9.1 rule 2, prefetch mode

- **The spec said:** `python -m musegauge_runtime.run --plugin-dir DIR --prefetch METRIC_ID --response FILE` calls `prefetch` "with the options from the manifest".
- **Built:** Prefetch mode also takes `--options FILE`; the core reads the manifest and writes the metric's options as JSON.
- **Why:** The runtime shim is standard library only and cannot read YAML. GATE 1.

### A3. 4.2 and 10.2, missing lock

- **The spec said:** Section 4.2: a plugin with no lock for the platform is skipped "with a warning". The 10.2 table had no code for it.
- **Built:** New warning `NO_LOCK`, scope `run`; the plugin's metrics get `status: skipped`. `UNLOCKED_ENV` stays for `--allow-unlocked`.
- **Why:** Every warning needs a code. GATE 1.

### A4. 5 and 7, plugin path flag

- **The spec said:** Section 5: no command line flag for outside plugins in 0.1. Section 7: global flag `--plugin-path DIR`.
- **Built:** No `--plugin-path`; only `MUSEGAUGE_PLUGIN_PATH`.
- **Why:** The two sections disagreed; section 5 is right. GATE 1.

### A5. 9.1 rule 7 and 10.2, uncontrolled randomness

- **The spec said:** Rule 7: if the upstream tool has randomness you cannot control, say so in warnings. No code in the table.
- **Built:** New warning `UNSEEDED_RANDOMNESS`, scope `metric`, added by the FAD wrapper whenever it reports `fad_inf` and `fad_inf_r2`.
- **Why:** fadtk's FAD-inf samples frames with `np.random.choice` and no seed; it runs as a separate command, so the wrapper cannot seed it (two identical runs: 6.464 and 6.625). Agreed before the M5 build.

### A6. F10, 7.1, 7.2, 9.2, sox

- **The spec said:** F10: fadtk needs sox; preflight checks it (exit 4); `doctor` checks it.
- **Built:** `fad_fadtk` has no required system tool; `doctor` reports a missing sox as WARN; `SOX_PATH` still passes to plugins.
- **Why:** fadtk 1.1.0 and kadtk 1.1.0 hard-code `TORCHAUDIO_RESAMPLING = True`. Runs with a logging fake sox (WAV and FLAC, 16, 32, 44.1 kHz): sox is only ever called as `sox -h`, and both tools work without it. mp3 and ogg not tested. Agreed before the M5 build, rechecked at GATE 2.

### A7. 6.2 and 10.2, trust_remote_code

- **The spec said:** The 6.2 example manifest for fad_fadtk says `trust_remote_code: false`; 10.2 says no 0.1 plugin runs downloaded code.
- **Built:** `fad_fadtk` and `kad_kadtk` say `trust_remote_code: true`, so FAD and KAD metrics show `TRUST_REMOTE_CODE`; VGGish metrics also record `env.remote_code`, shown in the report's software section.
- **Why:** VGGish loads through `torch.hub.load('harritaylor/torchvggish', 'vggish')`, which downloads and runs code from the repository's master branch; it is not pinned to a commit. Agreed before the M5 build.

### A8. 9.2, 9.3, 8.3, start-up downloads

- **The spec said:** The spec did not describe it.
- **Built:** Kept: the plugins call the `fadtk`/`kadtk` commands, which download three CLAP checkpoints (4.9 GB) into their own package folders inside the environment at every start until present; `prefetch` fills them; `musegauge clean --envs` removes them.
- **Why:** Calling the commands is what the spec asks; the alternative (calling Python functions) departs from 9.2/9.3. Agreed before the M5 build; the Docker consequence is A16.

### A9. 4.3, reference staging

- **The spec said:** Stage the reference once per content hash and plugin, at `refs/<ref_hash>/<plugin-id>/audio/`, and keep it.
- **Built:** The reference is staged fresh for every run and plugin, at `work/<run-id>/<plugin-id>/ref/`, and deleted with the work folder. `ref_hash` is still computed and reported.
- **Why:** The reuse let a GPU run use reference statistics that fadtk had made on the CPU: fad 6.402571304315046 instead of 6.40373404221544 (pure GPU); a direct fadtk run on the cached folder reproduced the mixed value. A better cache key is in `IDEAS.md`. Agreed after the first M5 golden run.

### A10. 11.6, golden tests

- **The spec said:** Tolerance `max(10 * std of three upstream runs, 1e-6)` for every value.
- **Built:** Scores from randomness the harness cannot seed (`fad_inf`, `fad_inf_r2`) are only checked to be present and finite, and printed next to the upstream runs. All other scores keep the tolerance.
- **Why:** Three runs cannot estimate the spread of a random value (fad_inf_r2 0.198 against runs of 0.015, 0.012, 0.005, while fad matched exactly). No tolerance was loosened. Agreed after the first M5 golden run.

### A11. 7.1, 4.4, 6.5, thread limit

- **The spec said:** No such option; section 4.4 lists the variables passed to plugins.
- **Built:** `run --threads N`. Unset: nothing changes. Set: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS` = N for plugins. `run.threads` in `results.json` (schema stays 1); `torch_threads` per environment.
- **Why:** CPU runs of fadtk/kadtk started over 2,000 threads on the 256-core build machine (load average about 700). GATE 2.

### A12. 9.2 and 10.2, failed FAD-inf

- **The spec said:** Keep `fad` and "add a warning with the upstream error text"; no code.
- **Built:** Warning `FAD_INF_FAILED`, scope `metric`, with the upstream output.
- **Why:** Every warning needs a code. Not seen in any run (fadtk raised no error even on 12 clips). GATE 2.

### A13. 4.4 and 7.1, `--no-fetch`

- **The spec said:** Set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; torch.hub has no offline switch.
- **Built:** Also set `HTTP_PROXY`/`HTTPS_PROXY` = `http://127.0.0.1:9` and an empty `NO_PROXY` for plugin processes. Documented as best effort: it blocks downloads from libraries that honour the proxy settings; a hard guarantee needs the network cut outside the tool.
- **Why:** torch.hub asks github.com on every VGGish load, even with a full cache; with the network unreachable it uses its cache (tested with torch 2.7.0 and 2.5.1, and end to end with all six metrics). Tested only with the proxy method, not with a truly blocked network. GATE 2 and GATE 3.

### A14. 4.4 and 6.4, network errors

- **The spec said:** A failing plugin is recorded with its error.
- **Built:** If the error text or the plugin's log shows an HTTP error raised in `torch/hub.py`, the error type becomes `NETWORK_ERROR` with advice (retry, or `setup --fetch-weights` then `--no-fetch`); the original error stays in the message. No automatic retries.
- **Why:** A GitHub refusal during the torch.hub check fails a run with a confusing error. GATE 2.

### A15. 4.2 and 7.3, `--no-fetch` without an environment

- **The spec said:** An environment that fails to build makes that plugin's metrics `status: error` (exit 5 or 10), not 4.
- **Built:** With `--no-fetch`, if a needed environment is not built yet, `run` stops before anything runs with exit code 4 and the `musegauge setup ...` command to run first. It never builds an environment.
- **Why:** Building an environment downloads packages, which `--no-fetch` forbids. GATE 3.

### A16. 8 and 8.3, Docker `full`

- **The spec said:** Two image targets, `slim` and `full` (environments in the image).
- **Built:** Only `slim`. `docker/Dockerfile`, `docker/README.md` and `docs/INSTALL.md` describe one image; the reason is in `IDEAS.md`.
- **Why:** fadtk and kadtk write 4.9 GB of CLAP checkpoints into their own environment folders at first run, which breaks a read-only or per-start image; weights may not be baked in, and nothing may be linked into installed packages. GATE 3.

### A17. 11.7, CI

- **The spec said:** `ci.yml` (core), `slow.yml` (real environments and CPU golden tests, nightly), `docker.yml` (slim image).
- **Built:** `ci.yml`: fast set, fake plugins, wheel checks, slim image build. `slow.yml`: isolation test and `verify_facts.py` only. No `docker.yml`. Real golden tests by hand with `scripts/run_golden.sh CORES`.
- **Why:** Real environments take about 24 GB and CPU golden numbers are tied to this server's core count. GATE 3.

### A18. 5, GPU test notes

- **The spec said:** `docs/GPU_TESTS.md`.
- **Built:** `docs/TESTING_REAL_PLUGINS.md`: how real golden tests are run by hand, and the machine, GPU, core count and versions the stored numbers came from.
- **Why:** The file covers CPU and GPU runs of the real plugins. GATE 3.

### A19. 11.6, CPU golden numbers and threads

- **The spec said:** Skip when device or torch version differ.
- **Built:** Golden files also store `cpu_cores` and `torch_threads`; a CPU case is skipped when the core count differs. All golden numbers were recorded, and slow tests are run, under `nice -n 19 taskset -c 0-15`.
- **Why:** CPU results depend on the thread count (16 versus 128 threads changed Audiobox scores by up to 4.8e-6). GATE 2 instruction (nice, taskset).

### A20. 11.6, `--threads 4` check

- **The spec said:** Not in the spec.
- **Built:** A normal slow test runs two CPU golden cases with `--threads 4`; it fails only if a difference exceeds 10 times the one observed on 2026-10-03 (1.3e-6 for `fad`, 2.9e-6 for Audiobox).
- **Why:** Measures the effect of A11 without hiding it. GATE 2 (the check) and GATE 3 (the rule).

### A21. 9.5, audiobox lock

- **The spec said:** `requirements.in`: the upstream package, with torch and torchaudio as a matched pair.
- **Built:** Also `huggingface_hub<1.0`, `requests` and `soundfile`.
- **Why:** audiobox-aesthetics 0.0.4 imports `requests` without declaring it (smoke check failed with huggingface_hub 2.1.1); without FFmpeg libraries torchaudio 2.7.0 has no audio backend. Roy, during M3.

### A22. 9.4, clap lock

- **The spec said:** Add `huggingface_hub` to `requirements.in` yourself.
- **Built:** `huggingface_hub<1.0`, plus `torchvision==0.22.0` with torch 2.7.0.
- **Why:** With an unbounded huggingface_hub the resolver picked transformers 4.12.2, whose tokenizers 0.10.3 failed to build (no Rust compiler). laion-clap imports torchvision without declaring it (section 4.2 pins torchvision "if used"). Roy's GATE 1 note for the constraint.

## Gate answers in short

- **GATE 1:** go; A1 to A4.
- **GATE 2:** go; `primary: CE` is a display choice only (`docs/METRICS.md`); A5 and A12 in the warnings table with tests; network items A13 and A14; `--threads` (A11); slow tests under `nice -n 19` and `taskset`; A6 rechecked; A7 stated in `METRICS.md` and the report; A9 accepted, cost documented; A8 disk use documented.
- **GATE 3:** go; A15 to A18 and A20; `--no-fetch` documented as best effort.
