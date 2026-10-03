"""Test plugin fake_set: number of generated files. Standard library only."""

from __future__ import annotations

import os
import platform


def count_files(folder):
    return sum(1 for name in os.listdir(folder) if os.path.isfile(os.path.join(folder, name)))


def run(request):
    scores = [{"name": "n_files", "value": float(count_files(request["generated"]["dir"])), "kind": "set"}]
    ref = request["reference"]
    if ref["kind"] == "dir":
        scores.append({"name": "n_ref_files", "value": float(count_files(ref["dir"])), "kind": "aux"})
    return {
        "scores": scores,
        "upstream": {"package": "python-stdlib", "version": platform.python_version(),
                     "invocation": "len(os.listdir(generated.dir))"},
        "env": {"python": platform.python_version(), "device": "cpu"},
    }


def prefetch(metric_id, options):
    return {"downloaded": [], "notes": []}
