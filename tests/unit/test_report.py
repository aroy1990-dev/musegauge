"""The report card (spec section 10.3)."""

from __future__ import annotations

import copy
import json

from conftest import DATA

from musegauge import report

EXAMPLE = json.loads((DATA / "results.example.json").read_text())


def test_render_matches_the_stored_expected_text():
    assert report.render(EXAMPLE) == (DATA / "report.expected.md").read_text()


def test_render_is_pure():
    doc = copy.deepcopy(EXAMPLE)
    report.render(doc)
    assert doc == EXAMPLE


def test_error_and_skipped_rows_and_error_in_warnings():
    doc = copy.deepcopy(EXAMPLE)
    doc["metrics"][0].update(status="error", scores=[],
                             error={"type": "EnvError", "message": "build failed", "traceback_tail": None})
    doc["metrics"][1].update(status="skipped", scores=[])
    text = report.render(doc)
    assert "| fad.vggish@1 | — | — | — | — | error |" in text
    assert "| aesthetics.audiobox@1 | — | — | — | — | skipped |" in text
    assert "- error (metric fad.vggish@1): EnvError: build failed" in text


def test_numbers_are_rounded_to_3_decimals():
    assert report.fmt(0.1629783702055613) == "0.163" and report.fmt(None) == "—"
    assert report.hms(3725.4) == "1:02:05"


def test_reference_lines():
    assert report._reference_line({"kind": "none"}) == "none"
    assert report._reference_line({"kind": "dir", "n_clips": 12, "ref_hash": "e38692a8aea0"}) == \
        "folder: 12 files, hash e38692a8"
