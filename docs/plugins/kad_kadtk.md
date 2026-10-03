# Plugin `kad_kadtk`

Metrics (set level): `kad.vggish@1`, `kad.clap-laion-music@1`. Score: `kad` (set). KAD can be
below zero.

## Upstream

- Package: `kadtk==1.1.0` (PyPI, home page github.com/YoonjinXD/kadtk), Python 3.11.
- Lock: `locks/linux-x86_64.txt`, same `uv pip compile` flags as the other plugins.
  Key pins: torch 2.5.1, torchaudio 2.5.1, torchvision 0.20.1 (CUDA 12.4 builds on Linux),
  tensorflow 2.21.0, keras 3.15.1, kapre 0.3.6, transformers 4.46.3, laion-clap 1.1.7, numpy 1.26.4.
  kadtk needs `torch<2.6`, so it has its own plugin and environment (F3).
- Command run (subprocess of the wrapper, in `work/<run-id>/kad_kadtk/`):
  `ENV/bin/kadtk MODEL BASELINE EVAL --csv work/kadtk-MODEL.csv --device D -w N`; the `score`
  column of the row it appends is `kad`.
  `BASELINE` is the staged reference `work/<run-id>/kad_kadtk/ref/`, staged fresh for every run
  (amendment A9). A folder reference is required; kadtk has no bundled statistics. `D` is `cpu` or `cuda` (always passed, because the
  upstream default is `cuda`). `--fad`, `--inf`, `--indiv`, `--audio-len` and `--force-stats-calc`
  are never passed.

## Behaviour of kadtk 1.1.0 that matters here (read from the wheel, checked by runs)

- **No sox and no ffmpeg.** `emb_loader.py` line 19 hard-codes `TORCHAUDIO_RESAMPLING = True`;
  audio goes through `torchaudio.load` and `torchaudio.transforms.Resample`. A run with no sox
  finished with exit 0 (amendment A6).
- **`import kadtk` imports TensorFlow** (U1); start-up prints TensorFlow messages to the log.
- **Start-up downloads.** Like fadtk, `get_all_models()` makes the CLAP loaders download three
  checkpoints into `ENV/lib/python3.11/site-packages/kadtk/.model-checkpoints/` (amendment A8):
  `630k-audioset-best.pt` (1,863,587,645 bytes), `CLAP_weights_2023.pth` (689,950,036),
  `music_audioset_epoch_15_esc_90.14.pt` (2,352,471,003). PANNs weights (zenodo) are fetched only
  when a PANNs model is used, which no 0.1 metric does.
- **`--device` covers only the kernel step.** kadtk's embedding models use `cuda` whenever torch
  sees a GPU. So the wrapper also hides the GPUs (`CUDA_VISIBLE_DEVICES=""`) for `--device cpu`.
- **Caches next to the audio (F9):** `<folder>/convert/<rate>/`, `<folder>/embeddings/<model>/`
  and `<folder>/kernel_stats/<model>/`. They use the same `embeddings/<model>/` names as fadtk. In a
  manual test where kadtk was given a folder fadtk had already used, kadtk read 6 of fadtk's 12
  reference embedding files instead of computing its own. The harness stages each plugin's audio
  into its own folders for every run (section 4.3, amendment A9), so this cannot happen inside
  musegauge.
- **Known upstream bugs, avoided:** `--force-stats-calc` uses `shutil` without importing it
  (F12); `--audio-len` is declared with `type=Union[float,int]`, which argparse cannot call.
- **Parallel first download** of torchvggish, same as fadtk; the wrapper loads VGGish once first.

## Files read and written

- Read: staged generated clips and the staged reference (symbolic links).
- Written by kadtk: the caches above in tool-owned folders, the CSV in `work_dir`, the downloads.
- Written by the harness: request and response files, the plugin log.

## Downloads

The three CLAP checkpoints above (into the environment); the torchvggish code and weights into
`$TORCH_HOME` (shared with fad_fadtk; see `fad_fadtk.md`); for `clap-laion-music`, the Hugging Face
tokenizer files listed in `clapscore_laion.md`. `musegauge setup --metrics kad.vggish@1,... --fetch-weights`
fills all of them. `trust_remote_code: true` because of torch.hub (amendment A7).

## Where the harness differs from upstream defaults

- `--device` is always passed (upstream default `cuda` fails on machines without a GPU); for `cpu`
  the GPUs are also hidden.
- VGGish is loaded once before the call.
- The bandwidth is kadtk's default (adaptive, median pairwise distance).
- `KAD_NEGATIVE` is added by the core when `kad` is below zero (section 10.2, M6).
