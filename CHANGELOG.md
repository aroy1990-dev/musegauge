# Changelog

## 0.1.0 (2026-10-03, not published)

First version. No PyPI or TestPyPI upload and no image pushed (D7 is open). The code is under the
Apache License 2.0 (`LICENSE`, decision D2).

Metrics, all at version `@1`:

- `fad.vggish@1`, `fad.clap-laion-music@1`, `fad.encodec-emb@1`: plugin `fad_fadtk`, fadtk 1.1.0, torch 2.7.0
- `kad.vggish@1`, `kad.clap-laion-music@1`: plugin `kad_kadtk`, kadtk 1.1.0, torch 2.5.1
- `clapscore.laion-music@1`: plugin `clapscore_laion`, laion-clap 1.1.7, torch 2.7.0 (harness-defined metric)
- `aesthetics.audiobox@1`: plugin `aesthetics_audiobox`, audiobox-aesthetics 0.0.4, torch 2.7.0

Suites: `t2m-basic@1` (default), `t2m-full@1`.

Commands: `run`, `list`, `info`, `doctor`, `setup`, `clean`, `report`, `validate`.

Install: pip and uvx (tested), Docker `slim` image and Apptainer (written, not built or tested).

Changes from the build spec are listed in `docs/DECISIONS.md` (C1 to C4, A1 to A22). The metric
ids were not bumped during development, because nothing had been released; from this version on,
every change that can move a metric's numbers bumps its `@N` with a line here.
