# Plugin `fad_fadtk`

Metrics (set level): `fad.vggish@1`, `fad.clap-laion-music@1`, `fad.encodec-emb@1`.
Scores: `fad` (set), `fad_inf` (set), `fad_inf_r2` (aux); with `--per-clip` also `fad_indiv` per clip
in `per_clip/<metric_id>.csv` (not averaged).

## Upstream

- Package: `fadtk==1.1.0` (PyPI), Python 3.11.
- Lock: `locks/linux-x86_64.txt`, made with
  `uv pip compile requirements.in --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --generate-hashes -o locks/linux-x86_64.txt`.
  Key pins: torch 2.7.0, torchaudio 2.7.0, torchvision 0.22.0 (CUDA 12.6 builds on Linux),
  laion-clap 1.1.7, msclap 1.3.4, encodec 0.1.1, transformers 4.57.6, numpy 1.26.4.
- Commands run (as subprocesses of the wrapper, in `work/<run-id>/fad_fadtk/`), each with a new CSV:
  1. `ENV/bin/fadtk MODEL BASELINE EVAL work/fadtk-MODEL-plain.csv -w N`, then the `score` column of the row it appends is `fad`.
  2. `ENV/bin/fadtk MODEL BASELINE EVAL work/fadtk-MODEL-inf.csv -w N --inf`, then `score` is `fad_inf` and `inf_r2` is `fad_inf_r2`.
  3. Only with `--per-clip`: `ENV/bin/fadtk MODEL BASELINE EVAL work/fadtk-MODEL-indiv.csv -w N --indiv`, rows `path,score`.
- `BASELINE` is the text `fma_pop` (bundled statistics) or the staged reference folder
  `work/<run-id>/fad_fadtk/ref/` (staged fresh for every run, amendment A9). `EVAL` is the staged generated folder `work/<run-id>/fad_fadtk/gen/`.
  `N` is `--workers` (default `min(8, CPU count)`).
- The upstream version in `results.json` is read from the installed package metadata.

## Behaviour of fadtk 1.1.0 that matters here (read from the wheel, checked by runs)

- **No sox and no ffmpeg.** `fad.py` line 24 hard-codes `TORCHAUDIO_RESAMPLING = True`. Audio is
  loaded with `torchaudio.load(..., backend=TORCHAUDIO_BACKEND)` (default `soundfile`), mixed to
  mono and resampled with `torchaudio.transforms.Resample` (Kaiser sinc, fixed parameters), then
  written as 16-bit WAV in `convert/<rate>/`. `SOX_PATH` is read but sox is never run. A run with
  no sox anywhere finished with exit 0 (amendment A6). The `-s/--sox-path` flag is parsed but not used.
- **Start-up downloads.** `fadtk` builds every model loader at start (`get_all_models()`). The
  CLAP loaders download their checkpoints into the package folder
  `ENV/lib/python3.11/site-packages/fadtk/.model-checkpoints/` if missing, even when the metric
  uses `vggish` (amendment A8). See the table below.
- **Device.** `cuda` when `torch.cuda.is_available()`, else `cpu`. There is no device flag.
- **Caches next to the audio (F9).** `<folder>/convert/<rate>/`, `<folder>/embeddings/<model>/`
  and `<folder>/stats/<model>/mu.npy, cov.npy`. A `stats` folder that exists is reused. The
  harness gives fadtk only its own staged folders (section 4.3), so these land in
  `work/<run-id>/fad_fadtk/gen/` and `work/<run-id>/fad_fadtk/ref/`, which are deleted after the
  run. They are never reused by a later run: a reused reference folder once mixed CPU-made
  reference statistics into a GPU run (amendment A9).
- **FAD-inf** (`score_inf`, 25 steps, `min_n=500` embedding frames) draws frames with
  `numpy.random.choice` without a seed, so `fad_inf` and `fad_inf_r2` change from run to run.
  With 12 clips of 10 s (about 120 VGGish frames) it raised no error; r² was 0.006 and 0.09 in two
  runs (U6). The wrapper adds `UNSEEDED_RANDOMNESS` (amendment A5).
- **`--indiv`** returns early without computing when its CSV already exists. The wrapper always
  gives it a new path inside `work_dir`.
- **Parallel first download.** With `-w` above 1 and an empty torch hub cache, the workers all
  download `harritaylor/torchvggish` at the same time and one fails
  (`FileNotFoundError: .../hubconf.py`). The wrapper loads VGGish once with `torch.hub.load`
  before calling `fadtk`.

## Files read and written

- Read: staged generated clips (symbolic links), the staged reference (symbolic links) or the
  bundled `fadtk/stats/fma_pop.npz` (82,302,832 bytes, statistics only, F11).
- Written by fadtk: the caches listed above, in tool-owned folders only; the three CSV files in
  `work_dir`; downloads listed below.
- Written by the harness: request and response files, the plugin log.

## Downloads

| What | From | Where it is stored | Size (bytes) | When |
| --- | --- | --- | --- | --- |
| `630k-audioset-best.pt` | huggingface.co/lukewys/laion_clap | `fadtk/.model-checkpoints/` in the environment | 1,863,587,645 | every `fadtk` start until present |
| `CLAP_weights_2023.pth` | huggingface.co/microsoft/msclap | same | 689,950,036 | same |
| `music_audioset_epoch_15_esc_90.14.pt` | huggingface.co/lukewys/laion_clap | same | 2,352,471,003 | same |
| torchvggish code (zip of the `master` branch) | github.com/harritaylor/torchvggish | `$TORCH_HOME/hub/harritaylor_torchvggish_master/` | about 260 KB unpacked | first `vggish` use |
| `vggish-10086976.pth` | github.com/harritaylor/torchvggish releases v0.1 | `$TORCH_HOME/hub/checkpoints/` | 288,567,937 | first `vggish` use |
| `vggish_pca_params-970ea276.pth` | same | same | 181,358 | first `vggish` use |
| `encodec_24khz-d7cc33bc.th` | dl.fbaipublicfiles.com/encodec/v0/ | `$TORCH_HOME/hub/checkpoints/` | 93,171,529 | first `encodec-emb` use |
| roberta-base, bert-base-uncased, facebook/bart-base tokenizer files; roberta-base weights | huggingface.co | `$HF_HOME` | see `clapscore_laion.md` | first `clap-laion-music` use (`import laion_clap`) |

`$TORCH_HOME` and `$HF_HOME` point into `$MUSEGAUGE_HOME/weights/` (section 4.4).
`musegauge setup --metrics fad.vggish@1,... --fetch-weights` does what `fadtk` does at start
(builds every model loader) and loads the metric's model once, so everything above is present.

**Remote code.** `torch.hub.load('harritaylor/torchvggish', 'vggish')` downloads and runs the
repository's code from its `master` branch. The manifest says `trust_remote_code: true` and
every run shows `TRUST_REMOTE_CODE` (amendment A7). Once cached, torch.hub uses the cached copy.

Licences: code MIT (LICENSE in the wheel). Weights and the bundled statistics: `unknown` in the
manifest. What the pages say is in `docs/VERIFIED_FACTS.md` (U4); for EnCodec, the repository
README says only that the code is MIT.

## Where the harness differs from upstream defaults

- `--device cpu` hides the GPUs (`CUDA_VISIBLE_DEVICES=""`) for the `fadtk` subprocess, because
  fadtk has no device flag. `--device cuda` stops with an error if CUDA is not available.
- Three separate `fadtk` calls (plain, `--inf`, `--indiv`) instead of one; embeddings are cached
  by fadtk between them, so the audio is embedded once.
- VGGish is loaded once before the first call (see "Parallel first download").
- A failed `--inf` call keeps `fad` and adds `FAD_INF_FAILED` with the upstream output.
- `fad_indiv` rows are mapped back from file paths to clip ids.
