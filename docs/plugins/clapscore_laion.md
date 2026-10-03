# Plugin `clapscore_laion`

Metric: `clapscore.laion-music@1` (clip level). Score per clip: `clap_cosine`.

This is a **harness-defined metric**. No upstream tool computes it. The harness calls
laion-clap's own functions for every embedding and chooses the audio steps below.

## Upstream

- Package: `laion-clap==1.1.7` (PyPI), Python 3.11.
- Lock: `locks/linux-x86_64.txt`, made with
  `uv pip compile requirements.in --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --generate-hashes -o locks/linux-x86_64.txt`.
  Key pins: torch 2.7.0, torchaudio 2.7.0, torchvision 0.22.0 (CUDA 12.6 builds on Linux),
  transformers 4.57.6, tokenizers 0.22.2, huggingface-hub 0.36.2, numpy 1.26.4, librosa 0.11.0.
- Functions called, in order:
  1. `laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base", device=D)`
  2. `model.load_ckpt(ckpt=<path>, verbose=False)`, path from
     `huggingface_hub.hf_hub_download("lukewys/laion_clap", "music_audioset_epoch_15_esc_90.14.pt")`
  3. per clip: `librosa.load(path, sr=48000, mono=True)`
  4. `laion_clap.training.data.int16_to_float32(float32_to_int16(audio))`
  5. 10 s windows with a 10 s hop, last window zero padded, real lengths kept
  6. `model.get_audio_embedding_from_data(windows, use_tensor=False)`, then the mean of the
     window embeddings weighted by real length
  7. `model.get_text_embedding([prompt], use_tensor=False)`
  8. cosine similarity of the two vectors (numpy)

Device: `cuda:0` when `--device cuda`, or `auto` with CUDA available; otherwise `cpu`.
`--batch-size` is not used: each clip's windows go to laion-clap in one call, one clip at a time.

## Behaviour of laion-clap that matters here (read from the 1.1.7 wheel)

- `get_audio_embedding_from_data(x, use_tensor=False)` runs the same int16 round trip again
  inside laion-clap. A second round trip changes none of the 65,535 possible int16 values
  (checked with laion-clap's own functions and numpy 1.26.4), so the result is the same as one
  round trip.
- `get_audio_features` crops at random only when a window is longer than 480,000 samples, and
  repeats audio to fill a shorter one. The harness gives it exactly 480,000 samples, so neither
  happens and no randomness is involved.
- The library default is `amodel="HTSAT-tiny"`; the music checkpoint needs `HTSAT-base`
  (spec F14), so the harness passes it.
- `load_state_dict` deletes `text_branch.embeddings.position_ids` for transformers 4.31 and
  newer, so transformers 4.57.6 loads the checkpoint without errors.
- Embeddings are L2-normalised by laion-clap. The weighted mean of window embeddings is not;
  the cosine handles that.

## Files read and written

- Read: the staged clips in `work/<run-id>/clapscore_laion/gen/` (symbolic links to the
  user's files) and the prompts from the request.
- Written by upstream: the Hugging Face cache under `$MUSEGAUGE_HOME/weights/hf`.
- Written by the harness: `request.json`, `response.json`, the plugin log.

## Downloads

All from huggingface.co into `$MUSEGAUGE_HOME/weights/hf`. Sizes as stored on 2026-10-03.

| Repo (revision) | File | Size (bytes) | When | Licence as stated on the page |
| --- | --- | --- | --- | --- |
| lukewys/laion_clap (b3708341862f581175dba5c356a4ebf74a9b6651) | music_audioset_epoch_15_esc_90.14.pt | 2,352,471,003 | first run or prefetch | cc0-1.0 (model card, spec F7) |
| roberta-base (e2da8e2f811d1448a5b465c236feacd80ffbac7b) | model.safetensors | 498,818,054 | building the model (text tower is created with `RobertaModel.from_pretrained`, then overwritten by the checkpoint) | mit (model card field, not confirmed) |
| roberta-base | config.json, merges.txt, tokenizer.json, tokenizer_config.json, vocab.json | 481; 456,318; 1,355,863; 25; 898,823 | `import laion_clap` | same |
| bert-base-uncased (86b5e0934494bd15c9632b12f734a8a67f723594) | config.json, tokenizer.json, tokenizer_config.json, vocab.txt | 570; 466,062; 48; 231,508 | `import laion_clap` | apache-2.0 (model card field, not confirmed) |
| facebook/bart-base (aadd2ab0ae0c8268c7c9693540e9904811f36177) | config.json, merges.txt, tokenizer.json, vocab.json | 1,716; 456,318; 1,355,863; 898,823 | `import laion_clap` | apache-2.0 (model card field, not confirmed) |

`import laion_clap` downloads three tokenizers because `laion_clap/training/data.py` loads
them at module level (lines 44 to 46). The import happens in the environment's smoke check,
so these files arrive when the environment is built. `musegauge setup --metrics
clapscore.laion-music@1 --fetch-weights` then downloads the checkpoint and roberta-base.

## Where the harness differs from upstream defaults

Everything in "Functions called" steps 3 to 8 is a harness choice written into the metric
definition: librosa loading at 48 kHz mono, the explicit int16 round trip, 10 s windows with a
10 s hop and zero padding, the length-weighted mean, and the cosine. laion-clap's own
`get_audio_embedding_from_filelist` would instead load the whole file and crop it at random
when it is longer than 10 s.

Dependencies added to the lock: `huggingface_hub<1.0` (agreed with Roy; see
`UPSTREAM_NOTES.md`) and `torchvision==0.22.0` (laion-clap imports it without declaring it;
spec section 4.2 pins it with torch).

## Prompts

A clip with no prompt is listed in `clips_failed` with reason `no_prompt`. If no clip has a
prompt, the core skips the metric with `NO_PROMPTS` (needs.prompts is true).

## Golden numbers

`tests/golden/clapscore_laion.json`: three runs of `tests/golden_scripts/clap_direct.py` (a
plain step-by-step script that does not import the wrapper) per device, CPU and one NVIDIA L40S,
on `gen_small` with `prompts.jsonl`. Largest standard deviation over the three runs: about
1e-17 on both devices.
