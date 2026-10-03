# Licences per metric

Three licences matter for every metric: the **code** of the upstream package, the model
**weights** it downloads, and the **data** (for FAD: the bundled reference statistics). This table
is generated from the plugin manifests (`src/musegauge/plugins/*/manifest.yaml`), which are the
source of truth; `musegauge info METRIC_ID` prints the same blocks.

Rules (spec rule 5): the builder never guesses a licence. `unknown` stays `unknown` until Roy has
read the sources and decided. Only Roy changes `commercial_ok` to `yes` or `no`. In 0.1 every
metric has `commercial_ok: unknown`, so every run warns `UNKNOWN_LICENCE`, and `--commercial`
refuses every metric.

Status values: `read_from_file` (read from a licence file in the package), `stated_on_page` (a
web page says so), `unknown`, `not_applicable`.

## `aesthetics.audiobox@1` (plugin `aesthetics_audiobox`)

| Part | Licence |
| --- | --- |
| code | `CC-BY-4.0`; status `read_from_file`; source: LICENSE inside the audiobox-aesthetics 0.0.4 wheel (Creative Commons Attribution 4.0 International); note: The README inside the same wheel says portions from https://github.com/microsoft/unilm are under the MIT licence. |
| weights | —; status `unknown`; check: https://huggingface.co/facebook/audiobox-aesthetics; note: The model card metadata said cc-by-4.0 when read on 2026-10-03. Not yet confirmed by Roy. |
| data | —; status `not_applicable` |
| commercial_ok | `unknown` |

## `clapscore.laion-music@1` (plugin `clapscore_laion`)

| Part | Licence |
| --- | --- |
| code | `CC0-1.0`; status `read_from_file`; source: LICENSE inside the laion-clap 1.1.7 wheel (CC0 1.0 Universal); note: The same wheel's metadata also has the classifier 'License :: OSI Approved :: Apache Software License', which disagrees with the LICENSE file. |
| weights | `CC0-1.0`; status `stated_on_page`; source: https://huggingface.co/lukewys/laion_clap (model card licence field cc0-1.0, read 2026-10-03); check: https://huggingface.co/lukewys/laion_clap, https://huggingface.co/FacebookAI/roberta-base; note: The text tower also downloads roberta-base (tokenizer and initial weights) from Hugging Face; its model card licence field said mit on 2026-10-03, not confirmed by Roy. |
| data | —; status `not_applicable` |
| commercial_ok | `unknown` |

## `fad.clap-laion-music@1` (plugin `fad_fadtk`)

| Part | Licence |
| --- | --- |
| code | `MIT`; status `read_from_file`; source: LICENSE inside the fadtk 1.1.0 wheel (Copyright (c) 2023 Microsoft Corporation) |
| weights | —; status `unknown`; check: https://huggingface.co/lukewys/laion_clap |
| data | —; status `unknown`; check: https://github.com/microsoft/fadtk; note: Applies to the bundled fma_pop statistics (fadtk/stats/fma_pop.npz). With a folder reference, the data is the user's. |
| commercial_ok | `unknown` |

## `fad.encodec-emb@1` (plugin `fad_fadtk`)

| Part | Licence |
| --- | --- |
| code | `MIT`; status `read_from_file`; source: LICENSE inside the fadtk 1.1.0 wheel (Copyright (c) 2023 Microsoft Corporation) |
| weights | —; status `unknown`; check: https://github.com/facebookresearch/encodec, https://dl.fbaipublicfiles.com/encodec/v0/encodec_24khz-d7cc33bc.th |
| data | —; status `unknown`; check: https://github.com/microsoft/fadtk; note: Applies to the bundled fma_pop statistics (fadtk/stats/fma_pop.npz). With a folder reference, the data is the user's. |
| commercial_ok | `unknown` |

## `fad.vggish@1` (plugin `fad_fadtk`)

| Part | Licence |
| --- | --- |
| code | `MIT`; status `read_from_file`; source: LICENSE inside the fadtk 1.1.0 wheel (Copyright (c) 2023 Microsoft Corporation) |
| weights | —; status `unknown`; check: https://github.com/harritaylor/torchvggish, https://github.com/tensorflow/models/tree/master/research/audioset |
| data | —; status `unknown`; check: https://github.com/microsoft/fadtk; note: Applies to the bundled fma_pop statistics (fadtk/stats/fma_pop.npz). With a folder reference, the data is the user's. |
| commercial_ok | `unknown` |

## `kad.clap-laion-music@1` (plugin `kad_kadtk`)

| Part | Licence |
| --- | --- |
| code | `MIT`; status `read_from_file`; source: LICENSE inside the kadtk 1.1.0 wheel (Copyright (c) 2025 yoonjinxd) |
| weights | —; status `unknown`; check: https://huggingface.co/lukewys/laion_clap |
| data | —; status `not_applicable` |
| commercial_ok | `unknown` |

## `kad.vggish@1` (plugin `kad_kadtk`)

| Part | Licence |
| --- | --- |
| code | `MIT`; status `read_from_file`; source: LICENSE inside the kadtk 1.1.0 wheel (Copyright (c) 2025 yoonjinxd) |
| weights | —; status `unknown`; check: https://github.com/harritaylor/torchvggish, https://github.com/tensorflow/models/tree/master/research/audioset |
| data | —; status `not_applicable` |
| commercial_ok | `unknown` |

## What the pages said (not decisions)

Read on 2026-10-03 for U4 (`docs/VERIFIED_FACTS.md`); recorded so Roy can check them, not used to
set any status: torchvggish repository Apache-2.0 (the README says the weights are ported from
tensorflow/models; whether the repository licence covers the weight files is not stated);
LAION-CLAP model card cc0-1.0; Audiobox Aesthetics model card cc-by-4.0; roberta-base model card
mit; bert-base-uncased and facebook/bart-base model cards apache-2.0; EnCodec repository README:
code MIT, weights not stated; MS-CLAP model card ms-pl (downloaded by fadtk and kadtk at start,
not used by any 0.1 metric). The fma_pop statistics and the PANNs weights were not checked.

## Other files downloaded but not used by a 0.1 metric

fadtk and kadtk download `630k-audioset-best.pt` (LAION-CLAP) and `CLAP_weights_2023.pth`
(MS-CLAP) at every start until present, even though no 0.1 metric uses them (amendment A8).
`import laion_clap` downloads the bert-base-uncased and facebook/bart-base tokenizers. Their
licences are listed above under "What the pages said".
