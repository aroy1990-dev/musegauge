"""Warnings (spec section 10.2 and amendments): for each code, one case that raises and one that does not.

Codes raised by wrappers (UNSEEDED_RANDOMNESS, FAD_INF_FAILED, NETWORK_FETCH) are tested in
test_wrappers.py; NAN_SCORE in test_runtime.py; NO_PROMPTS in test_runner.py; NO_LOCK and
UNLOCKED_ENV in tests/integration/test_exit_codes.py. This file covers the core rules and
checks that every code has its tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from musegauge import config, schemas
from musegauge import warnings_ as W

TESTS = Path(__file__).resolve().parents[1]
ALL_CODES = {
    "FEW_CLIPS", "SHORT_CLIPS", "MIXED_SAMPLE_RATES", "MIXED_DURATIONS", "REF_GEN_OVERLAP", "REF_SMALL",
    "NONCOMMERCIAL_WEIGHTS", "UNKNOWN_LICENCE", "NO_PROMPTS", "CLIPS_SKIPPED", "NETWORK_FETCH",
    "TRUST_REMOTE_CODE", "NAN_SCORE", "KAD_NEGATIVE", "UNLOCKED_ENV",
    "NO_LOCK", "UNSEEDED_RANDOMNESS", "FAD_INF_FAILED",  # amendments A3, A5 and GATE 2
}

# (code, call that must raise it, call that must not)
CASES = [
    ("SHORT_CLIPS", lambda: W.short_clips({"a": 10.0, "b": 0.5}), lambda: W.short_clips({"a": 10.0, "b": 12.0})),
    ("MIXED_SAMPLE_RATES", lambda: W.mixed_sample_rates({"16000": 1, "32000": 2}),
     lambda: W.mixed_sample_rates({"32000": 12})),
    ("MIXED_DURATIONS", lambda: W.mixed_durations({"a": 10.0, "b": 20.5}),
     lambda: W.mixed_durations({"a": 10.0, "b": 20.0})),
    ("REF_SMALL", lambda: W.ref_small(12), lambda: W.ref_small(config.REF_SMALL_MIN)),
    ("REF_GEN_OVERLAP", lambda: W.ref_gen_overlap({"g1": "aa", "g2": "bb"}, {"r1.wav": "bb"}),
     lambda: W.ref_gen_overlap({"g1": "aa"}, {"r1.wav": "cc"})),
    ("FEW_CLIPS", lambda: W.few_clips("fad.x@1", "set", 99), lambda: W.few_clips("fad.x@1", "set", 100)),
    ("NONCOMMERCIAL_WEIGHTS", lambda: W.licence("m.x@1", "no"), lambda: W.licence("m.x@1", "yes")),
    ("UNKNOWN_LICENCE", lambda: W.licence("m.x@1", "unknown"), lambda: W.licence("m.x@1", "yes")),
    ("KAD_NEGATIVE", lambda: W.kad_negative("kad.x@1", [{"name": "kad", "value": -0.01}]),
     lambda: W.kad_negative("kad.x@1", [{"name": "kad", "value": 0.0}])),
]


@pytest.mark.parametrize("code,raises,quiet", CASES, ids=[c[0] for c in CASES])
def test_raises_and_does_not_raise(code, raises, quiet):
    warning = raises()
    assert warning["code"] == code
    assert quiet() is None


def test_few_clips_only_for_set_metrics():
    assert W.few_clips("aesthetics.x@1", "clip", 3) is None


def test_licence_warning_for_commercial_ok_yes_is_none():
    assert W.licence("m.x@1", "yes") is None


def test_kad_negative_ignores_other_scores_and_null():
    assert W.kad_negative("fad.x@1", [{"name": "fad", "value": -1.0}]) is None
    assert W.kad_negative("kad.x@1", [{"name": "kad", "value": None}]) is None


def test_clips_skipped_lists_ids_and_reasons():
    w = W.clips_skipped([{"clip_id": "x", "path": "p", "reason": "zero length"}])
    assert w["code"] == "CLIPS_SKIPPED" and "x: zero length" in w["message"]


def test_short_clips_names_the_shortest():
    w = W.short_clips({"a": 3.0, "b": 0.5})
    assert "b, 0.50 s" in w["message"] and w["message"].startswith("2 clip(s)")


def test_limits_are_the_documented_defaults():
    assert (config.FEW_CLIPS_MIN, config.SHORT_CLIP_S, config.MIXED_DURATION_RATIO, config.REF_SMALL_MIN) == \
        (100, 10.0, 2.0, 100)


def test_every_warning_matches_the_results_schema():
    samples = [raises() for _, raises, _ in CASES] + [
        W.clips_skipped([{"clip_id": "x", "path": "p", "reason": "r"}]), W.unlocked_env(["p"]),
        W.no_lock("p", "linux-x86_64", ["a.b@1"]), W.no_prompts("a.b@1"), W.trust_remote_code("a.b@1"),
        W.nan_score("a.b@1", ["s"]),
    ]
    warning_schema = schemas.load_schema("results")["$defs"]["warning"]
    for w in samples:
        assert set(w) <= set(warning_schema["properties"])
        assert ("metric_id" in w) == (w["scope"] == "metric")


def test_emit_prints_to_stderr(capsys):
    W.emit(W.no_prompts("a.b@1"))
    captured = capsys.readouterr()
    assert captured.out == "" and "NO_PROMPTS [a.b@1]" in captured.err


def test_every_code_has_a_raise_and_a_no_raise_test():
    """Codes tested elsewhere are found by name in those test files."""
    here = {c[0] for c in CASES}
    elsewhere = {
        "NO_PROMPTS": TESTS / "unit" / "test_runner.py",
        "CLIPS_SKIPPED": TESTS / "integration" / "test_e2e_fakes.py",
        "NETWORK_FETCH": TESTS / "unit" / "test_wrappers.py",
        "TRUST_REMOTE_CODE": TESTS / "unit" / "test_results.py",
        "NAN_SCORE": TESTS / "unit" / "test_runtime.py",
        "UNLOCKED_ENV": TESTS / "integration" / "test_exit_codes.py",
        "NO_LOCK": TESTS / "integration" / "test_exit_codes.py",
        "UNSEEDED_RANDOMNESS": TESTS / "unit" / "test_wrappers.py",
        "FAD_INF_FAILED": TESTS / "unit" / "test_wrappers.py",
    }
    assert here | set(elsewhere) == ALL_CODES
    for code, path in elsewhere.items():
        assert code in path.read_text(), (code, path)
