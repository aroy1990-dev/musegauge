"""Statistics and bootstrap intervals (spec section 10.1)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from musegauge import stats

VALUES = np.array([3.1, 2.7, 4.4, 5.0, 3.9, 4.2, 2.2, 3.3, 4.8, 3.6, 2.9, 4.1])


def rows(values, name="x"):
    return [{"clip_id": f"c{i}", "scores": {name: v}} for i, v in enumerate(values)]


def test_same_inputs_give_the_same_interval():
    a = stats.bootstrap_ci(VALUES, "m.a@1", "x", seed=0, n_resamples=1000)
    b = stats.bootstrap_ci(VALUES, "m.a@1", "x", seed=0, n_resamples=1000)
    assert a == b


def test_interval_contains_the_mean_and_has_the_fields():
    ci = stats.bootstrap_ci(VALUES, "m.a@1", "x", seed=0, n_resamples=1000)
    assert ci["low"] <= VALUES.mean() <= ci["high"]
    assert ci["low"] < ci["high"]
    assert ci["method"] == "bootstrap-percentile" and ci["level"] == 0.95
    assert ci["n_resamples"] == 1000 and ci["seed"] == 0


def test_seed_and_names_change_the_stream():
    base = stats.bootstrap_ci(VALUES, "m.a@1", "x", 0, 1000)
    assert stats.bootstrap_ci(VALUES, "m.a@1", "x", 1, 1000) != base
    assert stats.bootstrap_ci(VALUES, "m.a@1", "y", 0, 1000) != base
    assert stats.bootstrap_ci(VALUES, "m.b@1", "x", 0, 1000) != base


def test_stream_key_is_first_8_bytes_big_endian():
    digest = hashlib.sha256(b"m.a@1:x").digest()
    assert stats.stream_key("m.a@1", "x") == int.from_bytes(digest[:8], "big")


def test_matches_a_direct_computation_of_the_spec_recipe():
    """Blocks of 100 draws from one generator: same as the spec's steps 1 to 3."""
    rng = np.random.default_rng(np.random.SeedSequence([0, stats.stream_key("m.a@1", "x")]))
    means = np.concatenate(
        [VALUES[rng.integers(0, VALUES.size, size=(size, VALUES.size))].mean(axis=1) for size in (100, 100, 50)]
    )
    low, high = np.percentile(means, [2.5, 97.5])
    ci = stats.bootstrap_ci(VALUES, "m.a@1", "x", 0, 250)
    assert (ci["low"], ci["high"]) == (low, high)


def test_order_of_metrics_does_not_change_intervals():
    first = stats.summarize_clip_scores(rows(VALUES), "m.a@1", 0, 500)
    stats.summarize_clip_scores(rows(VALUES[::-1]), "m.b@1", 0, 500)  # another metric in between
    again = stats.summarize_clip_scores(rows(VALUES), "m.a@1", 0, 500)
    assert first == again


def test_summary_mean_std_n():
    (entry,) = stats.summarize_clip_scores(rows(VALUES), "m.a@1", 0, 200)
    assert entry["name"] == "x" and entry["kind"] == "clip"
    assert entry["value"] == pytest.approx(VALUES.mean())
    assert entry["std"] == pytest.approx(VALUES.std(ddof=1))
    assert entry["n"] == 12 and entry["ci"] is not None and "ci_reason" not in entry


def test_n_of_one_gives_no_interval():
    (entry,) = stats.summarize_clip_scores(rows([2.0]), "m.a@1", 0, 1000)
    assert entry["n"] == 1 and entry["std"] is None and entry["ci"] is None
    assert entry["ci_reason"] == "n < 2"


def test_bootstrap_zero_turns_intervals_off():
    (entry,) = stats.summarize_clip_scores(rows(VALUES), "m.a@1", 0, 0)
    assert entry["ci"] is None and entry["ci_reason"] == "bootstrap turned off"


def test_null_and_missing_values_are_left_out():
    data = rows([1.0, None, 3.0]) + [{"clip_id": "z", "scores": {}}]
    (entry,) = stats.summarize_clip_scores(data, "m.a@1", 0, 100)
    assert entry["n"] == 2 and entry["value"] == 2.0


def test_several_score_names_keep_their_order():
    data = [{"clip_id": "a", "scores": {"CE": 1.0, "PQ": 2.0}}, {"clip_id": "b", "scores": {"CE": 3.0, "PQ": 4.0}}]
    assert [e["name"] for e in stats.summarize_clip_scores(data, "m.a@1", 0, 10)] == ["CE", "PQ"]


def test_set_scores_get_no_interval():
    entry = stats.set_score_entry({"name": "fad", "value": 1.5, "kind": "set"})
    assert entry == {"name": "fad", "kind": "set", "value": 1.5, "n": None, "std": None, "ci": None,
                     "ci_reason": "set-level metric, no confidence interval in 0.1"}
