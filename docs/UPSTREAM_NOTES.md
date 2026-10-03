# Upstream notes

Problems found in upstream packages. Each note says how it was seen. Nothing here was patched.

## torchaudio 2.11.0 declares no torch requirement

Seen 2026-10-03 on the PyPI JSON page (`requires_dist`). Every torchaudio from 2.5.1 to 2.10.0
pins one exact torch version. 2.11.0 lists none. A resolver can then pair torchaudio 2.11.0
with an older torch. In the U1 check this happened for kadtk (torch 2.5.1 with torchaudio
2.11.0), and `import torchaudio` failed with `OSError: libcudart.so.13: cannot open shared
object file`. Every lock must pin torch and torchaudio as a matched pair (spec section 4.2).

## torchaudio 2.11.0 needs torchcodec for `torchaudio.load`

Seen 2026-10-03. With torch 2.14.1 and torchaudio 2.11.0, `torchaudio.load('x.wav')` raised
`ImportError: TorchCodec is required for load_with_torchcodec`. With torch 2.7.0 and torchaudio
2.7.0 it worked. Which torchaudio version first made this change was not checked.

## `import kadtk` imports TensorFlow

Seen 2026-10-03 with kadtk 1.1.0 and tensorflow 2.21.0: after `import kadtk`,
`"tensorflow" in sys.modules` is True. The import also prints TensorFlow start-up messages.

## kadtk `--force-stats-calc` uses `shutil` without importing it

Reported in the spec (F12). Not re-checked by the builder yet. The plugin never passes this flag.

## laion-clap 1.1.7 with an unpinned `huggingface_hub` does not install on Python 3.11

Seen 2026-10-02 (UTC) in the U1 check. `requirements.in` was `laion-clap==1.1.7` and
`huggingface_hub`. The resolver chose huggingface-hub 2.1.1, and then transformers 4.12.2, the
newest transformers without an upper bound on huggingface-hub. transformers 4.12.2 needs
tokenizers 0.10.3, which has no wheel for Python 3.11. Exact error from `uv pip install`:

```text
error: Failed to build `tokenizers==0.10.3`
  cause: The build backend returned an error
  cause: Call to `setuptools.build_meta.build_wheel` failed (exit status: 1)
  ...
         error: can't find Rust compiler
  ...
hint: Build failures usually indicate a problem with the package or the build environment
```

Constraint in the M4 lock (agreed with Roy): `huggingface_hub<1.0`. It resolves to
huggingface-hub 0.36.2, transformers 4.57.6 and tokenizers 0.22.2 (a wheel), and installs.

## Latest torch from PyPI does not use CUDA on this machine

Seen 2026-10-03. torch 2.14.1 (the latest resolve) printed `The NVIDIA driver on your system is
too old (found version 12060)`. The driver is 560.35.03 (CUDA 12.6). torch 2.7.0 and 2.5.1 from
PyPI found the GPUs. This is a machine fact more than an upstream bug, but it limits which torch
versions the locks can use if GPU runs on this machine are wanted.

## audiobox-aesthetics 0.0.4 imports `requests` without declaring it

Seen 2026-10-03. `audiobox_aesthetics/utils.py` line 12 is `import requests`. The wheel's
`Requires-Dist` lists numpy, torch, torchaudio, tqdm, submitit, huggingface_hub, rich and
safetensors only. huggingface_hub 0.30.2 and 0.36.0 require `requests`; 1.0.0 and 2.1.1 list it
only under an extra. With the newest huggingface_hub (2.1.1) the plugin's smoke check failed:

```text
$ ENV/bin/python -c "import audiobox_aesthetics.infer"
  File ".../audiobox_aesthetics/utils.py", line 12, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'
```

Fix in the lock (agreed with Roy): `huggingface_hub<1.0` and `requests` in `requirements.in`.
Both candidate fixes gave the same scores on a test clip.

## torchaudio 2.7.0 needs an audio backend from outside its wheel

Seen 2026-10-03. In the audiobox environment, `torchaudio.list_audio_backends()` returned
`['ffmpeg']` only: the FFmpeg backend uses the system FFmpeg libraries (FFmpeg 6.1.1 here).
Without them `torchaudio.load` has no backend. Fix in the lock (agreed with Roy): add
`soundfile`. The list is then `['ffmpeg', 'soundfile']`, and torchaudio still tries FFmpeg first.

## laion-clap 1.1.7 imports torchvision and PIL without declaring them

Seen 2026-10-03. `laion_clap/hook.py` imports `laion_clap/training/data.py`, which has
`import torchvision.datasets`, `import torchvision.transforms` and `from PIL import Image` at the
top. The wheel's `Requires-Dist` lists neither torchvision nor Pillow. The lock pins
`torchvision==0.22.0` with torch 2.7.0 (spec section 4.2); Pillow comes with torchvision.

## `import laion_clap` downloads three tokenizers

Seen 2026-10-03. `laion_clap/training/data.py` lines 44 to 46 call
`BertTokenizer.from_pretrained("bert-base-uncased")`,
`RobertaTokenizer.from_pretrained("roberta-base")` and
`BartTokenizer.from_pretrained("facebook/bart-base")` at import time. So the first import needs
the network, or a filled Hugging Face cache with `HF_HUB_OFFLINE=1`. The files are listed in
`docs/plugins/clapscore_laion.md`.

## laion-clap quantises audio inside `get_audio_embedding_from_data`

Read 2026-10-03 in `laion_clap/hook.py`: with `use_tensor=False` it runs
`int16_to_float32(float32_to_int16(x))` on every input row. Spec section 9.4 also asks for an
explicit int16 round trip before it. A second round trip changes none of the 65,535 int16
values (checked with numpy 1.26.4), so this does not change the numbers.

## fadtk 1.1.0 and kadtk 1.1.0 never run sox (spec F10 does not hold for these versions)

Read 2026-10-03 in the wheels and checked by runs. `fadtk/fad.py` line 24 and
`kadtk/emb_loader.py` line 19 set `TORCHAUDIO_RESAMPLING = True`, so audio is loaded and
resampled with torchaudio. The sox and ffmpeg code paths, and the "could not find SoX" error
(a log message in fadtk, an exception in kadtk), are only reached when that constant is False.
`find_sox_formats` catches every error and returns an empty list. With `PATH=/usr/bin:/bin`
(no sox) and no `SOX_PATH`, `fadtk vggish REF GEN out.csv -w 4` exited 0 with FAD 6.404002057871558,
and `kadtk vggish REF GEN --csv kad.csv --device cpu -w 1` exited 0 with KAD 6.871640682220459.
Agreed with Roy: sox is not required (amendment A6). The `-s/--sox-path` flag of both commands is
parsed but never used.

## fadtk and kadtk download three CLAP checkpoints at every start until present

Seen 2026-10-03. Both commands build every model loader (`get_all_models()`) before parsing the
model choice. `CLAPModel("2023")` and `CLAPLaionModel("audio" | "music")` download their files in
`__init__` into the package's own folder `.model-checkpoints/` (inside the environment):
`630k-audioset-best.pt` (1,863,587,645 bytes), `CLAP_weights_2023.pth` (689,950,036) and
`music_audioset_epoch_15_esc_90.14.pt` (2,352,471,003). This happened on a `vggish` run.
Consequences: about 4.9 GB per environment; the files are not under `$MUSEGAUGE_HOME/weights`; an
environment in a read-only place needs them already present. Kept as is (amendment A8).

## torch.hub VGGish: remote code from a branch, and a race with parallel workers

Seen 2026-10-03. fadtk and kadtk load VGGish with `torch.hub.load('harritaylor/torchvggish',
'vggish')`. torch prints "You are about to download and run code from an untrusted repository".
The code comes from the `master` branch, so a later change there would change what a fresh cache
gets; a filled cache is reused. Manifests say `trust_remote_code: true` (amendment A7).
With `-w 4` and an empty cache, fadtk's worker processes all downloaded and unpacked the zip at
once, and the run failed:

```text
FileNotFoundError: [Errno 2] No such file or directory: '~/.cache/musegauge/weights/torch/hub/harritaylor_torchvggish_master/hubconf.py'
```

The wrappers load VGGish once before calling the command.

## fadtk FAD-inf is not seeded and has no minimum size (U6)

Read in `fadtk/fad.py` (`score_inf`): 25 values of n from `min_n=500` to the number of embedding
frames, frames drawn with `numpy.random.choice` (no seed), FAD-inf is the intercept of a line fit
over 1/n. Seen 2026-10-03 on 12 clips of 10 s (about 120 VGGish frames): no error, FAD-inf 6.464 and
6.625 in two runs of the same command, r² 0.006 and 0.090. The command line gives no way to set a
seed (amendment A5).

## kadtk `--device` does not cover the embedding models

Read in `kadtk/model_loader.py`: `ModelLoader.device` is `cuda` whenever `torch.cuda.is_available()`.
The `--device` flag goes only to `KernelAudioDistance`. To run fully on the CPU the GPUs must be
hidden (`CUDA_VISIBLE_DEVICES=""`), which the wrapper does.

## kadtk `--audio-len` cannot work

`kadtk/__main__.py` line 44 declares `type=Union[float,int]`; argparse would call `Union` on the
text and fail. The plugin does not use the flag.

## fadtk and kadtk share cache names, so one can read the other's files (F9, seen)

Seen 2026-10-03 in a manual test outside musegauge: kadtk was run on a copy of a reference folder
where an earlier, interrupted fadtk run had left 6 files in `embeddings/vggish/`. kadtk computed
only the 6 missing embeddings and used fadtk's 6. (The final KAD value was the same as on clean
folders, because both tools produced the same VGGish embeddings here.) musegauge stages each
plugin's audio into separate folders (section 4.3), so this cannot happen in a musegauge run.

## torch.hub asks github.com on every VGGish load, even with a full cache

Read 2026-10-03 in torch 2.7.0 `torch/hub.py`, `_parse_repo_info`: when `torch.hub.load` gets a
repository without a branch (`'harritaylor/torchvggish'`), it requests
`https://github.com/harritaylor/torchvggish/tree/main/` to choose between `main` and `master`.
This happens on every call, before the cache is used. A 404 means `master`; no network at all
(`URLError`) falls back to the cache; any other HTTP error is raised.

fadtk and kadtk call `torch.hub.load` in every worker process (`-w N`). On 2026-10-03, after a
few hundred such calls in a few hours, a golden-recording run on the GPU failed inside a fadtk
worker with:

```text
multiprocessing.pool.MaybeEncodingError: Error sending result: '<multiprocessing.pool.ExceptionWithTraceback object at 0x7f5bb6727a10>'. Reason: 'TypeError("cannot pickle '_io.BufferedReader' object")'
```

An `HTTPError` holds an open response object, which cannot be pickled, so this fits an HTTP error
other than 404 in a worker (for example a rate limit). Not confirmed: the full log of that run was
not kept. Right after, the same URL answered HTTP 404 (the normal case). Consequence: a FAD or
KAD run with a filled cache still depends on github.com answering normally at that moment.

What musegauge does about it (GATE 2 decision, M7), without changing torch or the tools:
`--no-fetch` points `HTTP_PROXY`/`HTTPS_PROXY` of every plugin process at an address that does
not answer, so the GitHub check fails as a connection error and torch.hub uses its cache (tested
with torch 2.7.0 and 2.5.1; `docs/VERIFIED_FACTS.md`, M7 checks). Without `--no-fetch`, a failure
whose output shows an HTTP error from `torch/hub.py` is reported as `NETWORK_ERROR` with advice;
there are no automatic retries.

