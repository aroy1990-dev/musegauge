"""Test plugin fake_badclip: scores each clip by its length, but fails on one named clip."""

from __future__ import annotations

import platform


def score(clip, bad_clip):
    if clip["clip_id"] == bad_clip:
        raise ValueError("fake_badclip refuses this clip")
    return clip["duration_s"]


def run(request):
    bad_clip = request["options"].get("bad_clip")
    clip_scores, failed = [], []
    for clip in request["generated"]["clips"]:
        try:
            clip_scores.append({"clip_id": clip["clip_id"], "scores": {"length_s": score(clip, bad_clip)}})
        except Exception as exc:  # noqa: BLE001 - one bad clip must not fail the metric
            failed.append({"clip_id": clip["clip_id"], "reason": f"{type(exc).__name__}: {exc}"})
    return {
        "clip_scores": clip_scores,
        "clips_failed": failed,
        "upstream": {"package": "python-stdlib", "version": platform.python_version(),
                     "invocation": "request clip duration_s"},
        "env": {"python": platform.python_version(), "device": "cpu"},
    }


def prefetch(metric_id, options):
    return {"downloaded": [], "notes": []}
