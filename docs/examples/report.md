Example from synthetic audio. The numbers mean nothing.

# Evaluation report card

Run `20261003T025538Z-e4c0fa` on 2026-10-03. Tool: musegauge 0.1.0.dev0. Suite: t2m-basic@1.

## Data
- Generated clips: 12 scored, 0 skipped. Total 0:02:00.
- Sample rates: 32000 Hz. Duration min / median / max: 10.000 / 10.000 / 10.000 s.
- Prompts: 12 of 12.
- Reference: bundled fma_pop.

## Scores
| Metric | Score | Mean ± std | 95% CI | n | Status |
| --- | --- | --- | --- | --- | --- |
| fad.vggish@1 | fad | 25.369 | — | — | ok |
| fad.vggish@1 | fad_inf | 26.009 | — | — | ok |
| fad.vggish@1 | fad_inf_r2 | 0.049 | — | — | ok |
| fad.clap-laion-music@1 | fad | 1.274 | — | — | ok |
| fad.clap-laion-music@1 | fad_inf | 1.265 | — | — | ok |
| fad.clap-laion-music@1 | fad_inf_r2 | 0.820 | — | — | ok |
| clapscore.laion-music@1 | clap_cosine | 0.232 ± 0.059 | [0.200, 0.262] | 12 | ok |
| aesthetics.audiobox@1 | CE | 2.405 ± 0.557 | [2.115, 2.705] | 12 | ok |
| aesthetics.audiobox@1 | CU | 5.455 ± 0.959 | [4.861, 5.922] | 12 | ok |
| aesthetics.audiobox@1 | PC | 1.780 ± 0.141 | [1.712, 1.862] | 12 | ok |
| aesthetics.audiobox@1 | PQ | 6.228 ± 0.827 | [5.757, 6.655] | 12 | ok |

## What each score is

`fad.vggish@1`: Frechet distance between Gaussian fits of fadtk vggish embeddings of the generated set and the reference set (a staged folder, or the fma_pop statistics bundled with fadtk), as computed by fadtk 1.1.0 (`fadtk vggish BASELINE EVAL CSV`). Also reports fad_inf, the FAD-inf extrapolation of `fadtk --inf` (it samples embedding frames at random without a seed, so it changes from run to run), and fad_inf_r2, the fit quality of that extrapolation.

`fad.clap-laion-music@1`: Frechet distance between Gaussian fits of fadtk clap-laion-music embeddings of the generated set and the reference set (a staged folder, or the fma_pop statistics bundled with fadtk), as computed by fadtk 1.1.0 (`fadtk clap-laion-music BASELINE EVAL CSV`). Also reports fad_inf, the FAD-inf extrapolation of `fadtk --inf` (it samples embedding frames at random without a seed, so it changes from run to run), and fad_inf_r2, the fit quality of that extrapolation.

`clapscore.laion-music@1`: Harness-defined metric, not an upstream one. For each clip that has a prompt: the cosine similarity between the LAION-CLAP audio embedding of the clip and the LAION-CLAP text embedding of its prompt, computed with laion-clap 1.1.7, CLAP_Module(enable_fusion=False, amodel='HTSAT-base') and the checkpoint music_audioset_epoch_15_esc_90.14.pt from the Hugging Face repo lukewys/laion_clap. Audio steps chosen by the harness: librosa.load with sr=48000 and mono=True; a round trip through int16 with laion-clap's float32_to_int16 and int16_to_float32; 10 s windows with a 10 s hop, the last window zero padded; each window embedded with get_audio_embedding_from_data; the window embeddings averaged with weights equal to each window's real length. Text: get_text_embedding([prompt]). One number per clip; the core reports the mean over clips.

`aesthetics.audiobox@1`: Audiobox Aesthetics predictions for each clip on four axes: Content Enjoyment (CE), Content Usefulness (CU), Production Complexity (PC) and Production Quality (PQ), as computed by audiobox-aesthetics 0.0.4 (initialize_predictor() then predictor.forward) with the weights of the Hugging Face repo facebook/audiobox-aesthetics. The tool resamples to 16 kHz mono, scores 10 s windows with a 10 s hop (last window zero padded) and averages the windows weighted by their real length. The harness reports the mean, standard deviation and a bootstrap interval over clips.

## Software
| Metric | Upstream | Version | Device | Seed |
| --- | --- | --- | --- | --- |
| fad.vggish@1 | fadtk | 1.1.0 | cuda | 0 |
| fad.clap-laion-music@1 | fadtk | 1.1.0 | cuda | 0 |
| clapscore.laion-music@1 | laion-clap | 1.1.7 | cuda | 0 |
| aesthetics.audiobox@1 | audiobox-aesthetics | 0.0.4 | cuda | 0 |

- `fad_fadtk-f7a67ac7`: Python 3.11.17, torch 2.7.0+cu126, torch threads 16, lock 6ba0018287ca
- `clapscore_laion-a3ecbe8b`: Python 3.11.17, torch 2.7.0+cu126, torch threads 16, lock ea0a624bba2b
- `aesthetics_audiobox-76e395f1`: Python 3.11.17, torch 2.7.0+cu126, torch threads 16, lock b000cbf7d43f
- Core: Python 3.12.7, uv 0.12.22, platform linux-x86_64.
- CPU threads per plugin: not limited (upstream default).
- `fad.vggish@1`: VGGish code from github.com/harritaylor/torchvggish, branch master, loaded through torch.hub at run time (or from the torch.hub cache); not pinned to a commit

Reproducible: yes

## Warnings
- `UNKNOWN_LICENCE` (metric fad.vggish@1): The licence has not been checked (commercial_ok: unknown). Do not assume commercial use is allowed.
- `TRUST_REMOTE_CODE` (metric fad.vggish@1): The plugin runs code downloaded from a model repository (see `musegauge info`).
- `UNSEEDED_RANDOMNESS` (metric fad.vggish@1): fad_inf and fad_inf_r2 come from fadtk's score_inf, which samples embedding frames with numpy.random.choice without a seed; they change from run to run.
- `FEW_CLIPS` (metric fad.vggish@1): Only 12 generated clip(s); set metrics such as FAD and KAD are unreliable with fewer than 100. Treat the number as rough.
- `UNKNOWN_LICENCE` (metric fad.clap-laion-music@1): The licence has not been checked (commercial_ok: unknown). Do not assume commercial use is allowed.
- `TRUST_REMOTE_CODE` (metric fad.clap-laion-music@1): The plugin runs code downloaded from a model repository (see `musegauge info`).
- `UNSEEDED_RANDOMNESS` (metric fad.clap-laion-music@1): fad_inf and fad_inf_r2 come from fadtk's score_inf, which samples embedding frames with numpy.random.choice without a seed; they change from run to run.
- `FEW_CLIPS` (metric fad.clap-laion-music@1): Only 12 generated clip(s); set metrics such as FAD and KAD are unreliable with fewer than 100. Treat the number as rough.
- `UNKNOWN_LICENCE` (metric clapscore.laion-music@1): The licence has not been checked (commercial_ok: unknown). Do not assume commercial use is allowed.
- `UNKNOWN_LICENCE` (metric aesthetics.audiobox@1): The licence has not been checked (commercial_ok: unknown). Do not assume commercial use is allowed.

## Notes for your paper
- Report the tool version, the suite id and version, the metric ids, the reference set, the number and length of clips, and the seed.
- The interval covers clip sampling only. It does not cover model or seed variation.
- The interval describes the spread caused by which clips were sampled. It does not cover model randomness, different seeds, or different prompts.
- Scores are comparable only with runs that use the same metric ids, reference set and clip length. Do not compare with numbers printed in other papers unless their setup is identical.
