# Plugin `aesthetics_audiobox`

Metric: `aesthetics.audiobox@1` (clip level). Scores per clip: `CE`, `CU`, `PC`, `PQ`.

## Upstream

- Package: `audiobox-aesthetics==0.0.4` (PyPI), Python 3.11.
- Lock: `locks/linux-x86_64.txt`, made with
  `uv pip compile requirements.in --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --generate-hashes -o locks/linux-x86_64.txt`.
  Key pins: torch 2.7.0, torchaudio 2.7.0 (CUDA 12.6 build on Linux), huggingface-hub 0.36.2,
  requests 2.34.2, soundfile 0.14.0, numpy 2.4.6.
- Function called: `audiobox_aesthetics.infer.initialize_predictor()` (no arguments), then
  `predictor.forward([{"path": FILE}, ...])` once per batch. The `audio-aes` command and its
  `--remote` flag are never used.

## What the upstream code does (read from the 0.0.4 wheel)

- Loads audio with `torchaudio.load`, mixes to mono, resamples to 16 kHz with
  `torchaudio.functional.resample`.
- Cuts each clip into 10 s windows with a 10 s hop. The last window is zero padded. Each window
  is weighted by its real length when the window scores are averaged.
- Device: `cuda` if `torch.cuda.is_available()`, else `mps`, else `cpu`. There is no device
  argument. Model precision comes from the checkpoint configuration (bf16).
- With no checkpoint path, weights load through `AesMultiOutput.from_pretrained("facebook/audiobox-aesthetics")`.

## Files read and written

- Read: the staged clips in `work/<run-id>/aesthetics_audiobox/gen/` (symbolic links to the
  user's files). Nothing else from the user.
- Written by upstream: the Hugging Face cache under `$MUSEGAUGE_HOME/weights/hf` (first run only).
- Written by the harness: `request.json`, `response.json`, the plugin log. Nothing in the user's
  folders.

## Downloads

| What | From | Size | Licence |
| --- | --- | --- | --- |
| `model.safetensors` | huggingface.co/facebook/audiobox-aesthetics (revision 9b1dd8e5df9af7216e836a98974fe3b82c56ded6) | 415,472,992 bytes | unknown in the manifest; the model card metadata said cc-by-4.0 on 2026-10-03 |
| `config.json` | same repo and revision | 492 bytes | same |

`musegauge setup --metrics aesthetics.audiobox@1 --fetch-weights` loads the predictor once on
the CPU, which fills the cache.

## Where the harness differs from upstream defaults

- **Batch size.** 8 clips per `forward` call unless `--batch-size` is given (spec section 9.5).
  The upstream `main_predict` default is 10 and the README example uses `--batch-size 100`.
  On the CPU, the batch grouping changed scores in the 7th significant digit in one check
  (gen_000 CE 2.0855901 alone, 2.0855906 in a batch of 8).
- **Failed batches** are retried one clip at a time. Clips that still fail go to `clips_failed`.
- **`--device cpu`** hides the GPUs (`CUDA_VISIBLE_DEVICES=""`) before torch starts, because the
  upstream predictor has no device argument. `--device cuda` stops with an error when CUDA is
  not available. `auto` lets upstream choose.
- **Dependencies added to the lock** (agreed with Roy 2026-10-03): `huggingface_hub<1.0` and
  `requests` (upstream imports `requests` without declaring it), and `soundfile` (gives
  torchaudio an audio backend on machines without FFmpeg). torchaudio prefers FFmpeg when it is
  present. The wrapper reports `torchaudio_backends` in `env`.
- **Seeds.** Python `random`, numpy and torch are seeded from `request.seed`. Upstream inference
  has no sampling; three runs per device gave identical numbers (golden file).

## Golden numbers

`tests/golden/aesthetics_audiobox.json`: three direct runs of
`tests/golden_scripts/aesthetics_direct.py` per device (CPU, and one NVIDIA L40S), on `gen_small`.
The three runs were identical on each device. CPU and GPU differ from each other in the 4th
decimal place, so the golden test compares only like devices.
