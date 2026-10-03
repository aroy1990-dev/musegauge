# Metrics in musegauge 0.1

Each metric id names what is computed and by which wrapper version (`family.variant@N`). The
number after `@` goes up whenever the numbers could change. Scores are comparable only between
runs with the same metric ids, reference set, clip length, device and thread setting (see
"Where numbers can differ" below).

No number here is an "official" score of a paper. Each one is what the named package version
computes on your files, as described in its definition.

## Overview

| Metric | Kind | Plugin | Upstream | Scores | Needs | Licence status (`commercial_ok`) |
| --- | --- | --- | --- | --- | --- | --- |
| `fad.vggish@1` | set | `fad_fadtk` | fadtk 1.1.0 | `fad`, `fad_inf`, `fad_inf_r2` | reference (folder or bundled `fma_pop`) | unknown |
| `fad.clap-laion-music@1` | set | `fad_fadtk` | fadtk 1.1.0 | `fad`, `fad_inf`, `fad_inf_r2` | reference (folder or bundled `fma_pop`) | unknown |
| `fad.encodec-emb@1` | set | `fad_fadtk` | fadtk 1.1.0 | `fad`, `fad_inf`, `fad_inf_r2` | reference (folder or bundled `fma_pop`) | unknown |
| `kad.vggish@1` | set | `kad_kadtk` | kadtk 1.1.0 | `kad` | reference folder | unknown |
| `kad.clap-laion-music@1` | set | `kad_kadtk` | kadtk 1.1.0 | `kad` | reference folder | unknown |
| `clapscore.laion-music@1` | clip | `clapscore_laion` | laion-clap 1.1.7 | `clap_cosine` | prompts | unknown |
| `aesthetics.audiobox@1` | clip | `aesthetics_audiobox` | audiobox-aesthetics 0.0.4 | `CE`, `CU`, `PC`, `PQ` | nothing | unknown |

Every metric has `commercial_ok: unknown`, so every run shows `UNKNOWN_LICENCE` for each metric.
Only Roy changes `unknown` to `yes` or `no`, after reading the sources. `musegauge info METRIC_ID`
prints the three licence blocks (code, weights, data) with their status and the URLs to check.

## Definitions

These are the `definition` texts of the manifests, shortened. The full text is in each
`results.json` and in `musegauge info`.

- **`fad.<model>@1`**: Frechet distance between Gaussian fits of fadtk `<model>` embeddings of the
  generated set and the reference set, as computed by fadtk 1.1.0. `fad_inf` is fadtk's FAD-inf
  extrapolation and `fad_inf_r2` its fit quality.
- **`kad.<model>@1`**: Kernel Audio Distance (MMD with a Gaussian kernel and kadtk's adaptive
  bandwidth) between kadtk `<model>` embeddings of the two sets, as computed by kadtk 1.1.0. KAD
  can be below zero; the core then adds `KAD_NEGATIVE`. This is not an error.
- **`clapscore.laion-music@1`**: a harness-defined metric, not an upstream one. For each clip with
  a prompt, the cosine similarity between the LAION-CLAP audio embedding (music checkpoint,
  10 s windows, length-weighted mean) and the text embedding of its prompt.
- **`aesthetics.audiobox@1`**: Audiobox Aesthetics predictions per clip on four axes: Content
  Enjoyment (CE), Content Usefulness (CU), Production Complexity (PC), Production Quality (PQ).

Set metrics have no confidence interval in 0.1. Clip metrics report mean, standard deviation, n
and a 95 % percentile bootstrap interval over clips; the interval covers clip sampling only.

## What "primary" means

Each metric names one `primary` score in its manifest (for example `CE` for
`aesthetics.audiobox@1`). It is a display choice only. In 0.1, `primary` is copied into
`results.json` and shown by `musegauge info`; nothing ranks, combines or hides scores by it.
`results.json` and `report.md` show all four Audiobox scores equally. `primary: CE` does not
mean CE is the best or most important Audiobox axis.

## Where numbers can differ

- **Device.** CPU and GPU give slightly different numbers (for example `fad.vggish@1` on the test
  fixtures: 6.404002 on the CPU, 6.403734 on an NVIDIA L40S). Golden numbers are kept per device.
- **CPU threads.** On the CPU, the number of threads changes results in about the 6th or 7th
  significant digit (checked: `--threads 4` against the default changed `fad` by 1.3e-6 and
  Audiobox scores by up to 2.9e-6; limiting a run to 16 cores changed Audiobox scores by up to
  4.8e-6). `results.json` records `run.threads` and each plugin's `torch_threads`.
- **Random parts.** `fad_inf` and `fad_inf_r2` come from fadtk's FAD-inf, which samples
  embedding frames without a seed. They change from run to run (`UNSEEDED_RANDOMNESS`). On small
  sets the fit quality can be close to 0. `fad` itself has no random part.

## Code downloaded at run time (not pinned)

The VGGish models (`fad.vggish@1`, `kad.vggish@1`) are loaded by fadtk and kadtk with
`torch.hub.load('harritaylor/torchvggish', 'vggish')`. That downloads the code of the GitHub
repository harritaylor/torchvggish from its **master branch** and runs it. It is not pinned to a
commit: a later change on that branch would change what a new cache gets, and with it possibly
the numbers. Once downloaded, the copy in `$MUSEGAUGE_HOME/weights/torch/hub/` is reused.
Because of this, the `fad_fadtk` and `kad_kadtk` manifests say `trust_remote_code: true` and runs
show `TRUST_REMOTE_CODE`; the report's software section says the same. (The flag is per plugin,
so it also appears for the clap-laion-music and encodec-emb variants of those plugins, which do
not load torch.hub code.)

## More detail

`docs/plugins/<plugin_id>.md` lists for each plugin the exact command or function, every file
read and written, every download with its size, and every difference from upstream defaults.
