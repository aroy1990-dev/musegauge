"""Warnings (spec section 10.2, with amendments A3 and A5 and the GATE 2 additions).

A warning is {code, scope, message} and, for metric warnings, metric_id. A warning never
changes an exit code. The numeric limits are in config.py (the harness's own defaults, not
values from any paper).

Raised by the core: CLIPS_SKIPPED, SHORT_CLIPS, MIXED_SAMPLE_RATES, MIXED_DURATIONS,
REF_GEN_OVERLAP, REF_SMALL, UNLOCKED_ENV, NO_LOCK (run scope); FEW_CLIPS,
NONCOMMERCIAL_WEIGHTS, UNKNOWN_LICENCE, NO_PROMPTS, TRUST_REMOTE_CODE, KAD_NEGATIVE (metric).
Raised by wrappers or the runtime shim and passed through: NETWORK_FETCH, NAN_SCORE,
UNSEEDED_RANDOMNESS, FAD_INF_FAILED (metric).
"""

from __future__ import annotations

import sys

from musegauge import config

WRAPPER_CODES = ("NETWORK_FETCH", "NAN_SCORE", "UNSEEDED_RANDOMNESS", "FAD_INF_FAILED")


def make(code: str, scope: str, message: str, metric_id: str | None = None) -> dict:
    warning = {"code": code, "scope": scope, "message": message}
    if metric_id is not None:
        warning["metric_id"] = metric_id
    return warning


def emit(warning: dict) -> None:
    """Every warning also prints to standard error."""
    where = f" [{warning['metric_id']}]" if "metric_id" in warning else ""
    print(f"warning {warning['code']}{where}: {warning['message']}", file=sys.stderr)


# --- run scope -------------------------------------------------------------------------------


def clips_skipped(skipped: list[dict]) -> dict:
    listing = "; ".join(f"{s['clip_id']}: {s['reason']}" for s in skipped)
    return make(
        "CLIPS_SKIPPED", "run", f"{len(skipped)} clip(s) could not be read and were skipped: {listing}"
    )


def short_clips(durations: dict[str, float]) -> dict | None:
    """durations: clip_id -> seconds, for the clips that were scored."""
    short = {cid: d for cid, d in durations.items() if d < config.SHORT_CLIP_S}
    if not short:
        return None
    cid = min(short, key=short.get)
    return make(
        "SHORT_CLIPS",
        "run",
        f"{len(short)} clip(s) are shorter than {config.SHORT_CLIP_S:g} s (shortest: {cid}, "
        f"{short[cid]:.2f} s). The tools in 0.1 work on 10 s windows; short clips are padded or "
        "weighted.",
    )


def mixed_sample_rates(rates: dict[str, int]) -> dict | None:
    """rates: sample rate (as text) -> number of clips."""
    if len(rates) <= 1:
        return None
    listing = ", ".join(f"{r} Hz ({n} clips)" for r, n in rates.items())
    return make("MIXED_SAMPLE_RATES", "run", f"Clips have more than one sample rate: {listing}. "
                "The tools resample internally.")


def mixed_durations(durations: dict[str, float]) -> dict | None:
    if not durations:
        return None
    shortest, longest = min(durations.values()), max(durations.values())
    if longest <= config.MIXED_DURATION_RATIO * shortest:
        return None
    return make(
        "MIXED_DURATIONS",
        "run",
        f"The longest clip ({longest:.2f} s) is more than {config.MIXED_DURATION_RATIO:g} times "
        f"the shortest ({shortest:.2f} s). Scores may mix clips of very different length.",
    )


def ref_small(n_files: int) -> dict | None:
    """For a folder reference only; never for a bundled one."""
    if n_files >= config.REF_SMALL_MIN:
        return None
    return make("REF_SMALL", "run", f"The reference folder has {n_files} readable file(s), fewer "
                f"than {config.REF_SMALL_MIN}. The reference set is small.")


def ref_gen_overlap(gen_hashes: dict[str, str], ref_hashes: dict[str, str]) -> dict | None:
    """gen_hashes: clip_id -> SHA-256; ref_hashes: reference file name -> SHA-256."""
    by_hash: dict[str, list[str]] = {}
    for name, digest in ref_hashes.items():
        by_hash.setdefault(digest, []).append(name)
    pairs = [(cid, ref) for cid, digest in gen_hashes.items() for ref in by_hash.get(digest, [])]
    if not pairs:
        return None
    listing = ", ".join(f"{cid} = {ref}" for cid, ref in pairs[:10]) + (" ..." if len(pairs) > 10 else "")
    return make("REF_GEN_OVERLAP", "run", f"{len(pairs)} generated clip(s) are byte-identical to a "
                f"reference file: {listing}. Only identical files are detected, not similar ones.")


def unlocked_env(plugin_ids: list[str]) -> dict:
    return make(
        "UNLOCKED_ENV",
        "run",
        "Environment resolved fresh from requirements.in for: "
        f"{', '.join(plugin_ids)}. Results are marked reproducible: false.",
    )


def no_lock(plugin_id: str, platform_tag: str, metric_ids: list[str]) -> dict:
    """A plugin was skipped because it has no lock file for this platform (amendment A3)."""
    return make(
        "NO_LOCK",
        "run",
        f"Plugin {plugin_id} has no lock file for {platform_tag}, so it was skipped "
        f"(metrics: {', '.join(metric_ids)}). Use --allow-unlocked to resolve it from "
        "requirements.in; results are then marked reproducible: false.",
    )


# --- metric scope ----------------------------------------------------------------------------


def few_clips(metric_id: str, kind: str, n_clips: int) -> dict | None:
    if kind != "set" or n_clips >= config.FEW_CLIPS_MIN:
        return None
    return make("FEW_CLIPS", "metric", f"Only {n_clips} generated clip(s); set metrics such as FAD "
                f"and KAD are unreliable with fewer than {config.FEW_CLIPS_MIN}. Treat the number as "
                "rough.", metric_id)


def licence(metric_id: str, commercial_ok: str) -> dict | None:
    if commercial_ok == "no":
        return make("NONCOMMERCIAL_WEIGHTS", "metric", "The manifest says commercial_ok: no. "
                    "Weights are not for commercial use.", metric_id)
    if commercial_ok == "unknown":
        return make("UNKNOWN_LICENCE", "metric", "The licence has not been checked "
                    "(commercial_ok: unknown). Do not assume commercial use is allowed.", metric_id)
    return None


def no_prompts(metric_id: str) -> dict:
    return make(
        "NO_PROMPTS",
        "metric",
        "This metric needs prompts and no clip has one. Metric skipped.",
        metric_id,
    )


def trust_remote_code(metric_id: str) -> dict:
    return make(
        "TRUST_REMOTE_CODE",
        "metric",
        "The plugin runs code downloaded from a model repository (see `musegauge info`).",
        metric_id,
    )


def kad_negative(metric_id: str, scores: list[dict]) -> dict | None:
    negative = [s for s in scores if s["name"] == "kad" and s["value"] is not None and s["value"] < 0]
    if not negative:
        return None
    return make("KAD_NEGATIVE", "metric", f"KAD is {negative[0]['value']:.6g}, below zero. KAD can be "
                "negative; this is not an error.", metric_id)


def nan_score(metric_id: str, names: list[str]) -> dict:
    return make(
        "NAN_SCORE",
        "metric",
        f"Non-finite value replaced by null: {', '.join(names)}.",
        metric_id,
    )
