"""Test plugin fake_clip: mean absolute amplitude of each clip. Standard library only."""

from __future__ import annotations

import array
import os
import platform
import sys
import wave


def mean_abs(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("only 16-bit PCM WAV is supported")
        raw = w.readframes(w.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder == "big":
        samples.byteswap()
    return sum(abs(s) for s in samples) / (len(samples) * 32768.0)


def run(request):
    gen = request["generated"]
    clip_scores, failed = [], []
    for clip in gen["clips"]:
        try:
            value = mean_abs(os.path.join(gen["dir"], clip["file"]))
            clip_scores.append({"clip_id": clip["clip_id"], "scores": {"amplitude": value}})
        except Exception as exc:  # noqa: BLE001 - one bad clip must not fail the metric
            failed.append({"clip_id": clip["clip_id"], "reason": f"{type(exc).__name__}: {exc}"})
    return {
        "clip_scores": clip_scores,
        "clips_failed": failed,
        "upstream": {"package": "python-stdlib", "version": platform.python_version(),
                     "invocation": "wave.open(path).readframes(); mean(abs(x)) / 32768"},
        "env": {"python": platform.python_version(), "device": "cpu"},
    }


def prefetch(metric_id, options):
    return {"downloaded": [], "notes": ["fake_clip downloads nothing"]}
