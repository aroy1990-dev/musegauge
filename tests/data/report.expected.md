# Evaluation report card

Run `20261002T154501Z-a1b2c3` on 2026-10-02. Tool: musegauge 0.1.0. Suite: t2m-basic@1.

## Data
- Generated clips: 200 scored, 1 skipped. Total 0:33:20.
- Sample rates: 32000 Hz. Duration min / median / max: 10.000 / 10.000 / 10.000 s.
- Prompts: 200 of 200.
- Reference: bundled fma_pop.

## Scores
| Metric | Score | Mean ± std | 95% CI | n | Status |
| --- | --- | --- | --- | --- | --- |
| fad.vggish@1 | fad | 12.340 | — | — | ok |
| aesthetics.audiobox@1 | CE | 5.100 ± 0.900 | [4.900, 5.300] | 200 | ok |

## What each score is

`fad.vggish@1`: text copied from the manifest

`aesthetics.audiobox@1`: text copied from the manifest

## Software
| Metric | Upstream | Version | Device | Seed |
| --- | --- | --- | --- | --- |
| fad.vggish@1 | fadtk | 1.1.0 | cuda | 0 |
| aesthetics.audiobox@1 | audiobox-aesthetics | 0.0.4 | — | 0 |

- `fad_fadtk-1a2b3c4d`: Python 3.11.9, torch 2.7.0, lock ...
- `aesthetics_audiobox-0a1b2c3d`: Python 3.11.9, torch —, lock ...
- Core: Python 3.11.9, uv 0.0.0, platform linux-x86_64.
- CPU threads per plugin: not limited (upstream default).

Reproducible: yes

## Warnings
- `EXAMPLE` (run): text
- `UNKNOWN_LICENCE` (metric fad.vggish@1): text

## Notes for your paper
- Report the tool version, the suite id and version, the metric ids, the reference set, the number and length of clips, and the seed.
- The interval covers clip sampling only. It does not cover model or seed variation.
- The interval describes the spread caused by which clips were sampled. It does not cover model randomness, different seeds, or different prompts.
- Scores are comparable only with runs that use the same metric ids, reference set and clip length. Do not compare with numbers printed in other papers unless their setup is identical.
