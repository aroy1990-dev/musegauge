"""Test plugin: reports the numpy and Python of its own environment (isolation test)."""

from __future__ import annotations

import platform
import sys


def run(request):
    import numpy

    major = float(numpy.__version__.split(".")[0])
    return {
        "clip_scores": [
            {"clip_id": c["clip_id"], "scores": {"numpy_major": major}}
            for c in request["generated"]["clips"]
        ],
        "upstream": {"package": "numpy", "version": numpy.__version__,
                     "invocation": "numpy.__version__"},
        "env": {
            "python": platform.python_version(),
            "sys_version": sys.version,
            "numpy": numpy.__version__,
            "numpy_file": numpy.__file__,
            "device": "cpu",
        },
    }


def prefetch(metric_id, options):
    return {"downloaded": [], "notes": []}
