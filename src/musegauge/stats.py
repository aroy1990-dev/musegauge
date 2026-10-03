"""Summary statistics and bootstrap confidence intervals (spec section 10.1).

Only the core computes statistics. Wrappers return raw scores.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

from musegauge.config import BOOTSTRAP_BLOCK, CI_LEVEL

SET_CI_REASON = "set-level metric, no confidence interval in 0.1"


def stream_key(metric_id: str, score_name: str) -> int:
    """First 8 bytes of sha256(f"{metric_id}:{score_name}"), read as a big-endian integer."""
    digest = hashlib.sha256(f"{metric_id}:{score_name}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def bootstrap_ci(
    values: np.ndarray, metric_id: str, score_name: str, seed: int, n_resamples: int
) -> dict:
    """Percentile bootstrap interval of the mean at level 0.95.

    Resamples are drawn in blocks of at most BOOTSTRAP_BLOCK so memory stays small.
    The random stream depends only on (seed, metric_id, score_name), so the result
    does not depend on the order in which metrics run.
    """
    values = np.asarray(values, dtype=float)
    n = values.size
    rng = np.random.default_rng(np.random.SeedSequence([seed, stream_key(metric_id, score_name)]))
    means = np.empty(n_resamples, dtype=float)
    for start in range(0, n_resamples, BOOTSTRAP_BLOCK):
        size = min(BOOTSTRAP_BLOCK, n_resamples - start)
        idx = rng.integers(0, n, size=(size, n))
        means[start : start + size] = values[idx].mean(axis=1)
    tail = (1.0 - CI_LEVEL) / 2.0 * 100.0
    low, high = np.percentile(means, [tail, 100.0 - tail])
    return {
        "method": "bootstrap-percentile",
        "level": CI_LEVEL,
        "n_resamples": n_resamples,
        "seed": seed,
        "low": float(low),
        "high": float(high),
    }


def summarize_clip_scores(
    clip_scores: list[dict], metric_id: str, seed: int, n_resamples: int
) -> list[dict]:
    """One results score entry per score name: mean, sample std, n and interval of finite values."""
    names: list[str] = []
    for row in clip_scores:
        for name in row["scores"]:
            if name not in names:
                names.append(name)
    out = []
    for name in names:
        vals = [row["scores"].get(name) for row in clip_scores]
        finite = np.array(
            [v for v in vals if isinstance(v, (int, float)) and math.isfinite(v)], dtype=float
        )
        n = int(finite.size)
        entry = {
            "name": name,
            "kind": "clip",
            "value": float(finite.mean()) if n else None,
            "n": n,
            "std": float(finite.std(ddof=1)) if n >= 2 else None,
            "ci": None,
        }
        if n < 2:
            entry["ci_reason"] = "n < 2"
        elif n_resamples <= 0:
            entry["ci_reason"] = "bootstrap turned off"
        else:
            entry["ci"] = bootstrap_ci(finite, metric_id, name, seed, n_resamples)
        out.append(entry)
    return out


def set_score_entry(score: dict) -> dict:
    """A set-level or helper score: the value only, with no interval in 0.1."""
    return {
        "name": score["name"],
        "kind": score["kind"],
        "value": score["value"],
        "n": None,
        "std": None,
        "ci": None,
        "ci_reason": SET_CI_REASON,
    }
