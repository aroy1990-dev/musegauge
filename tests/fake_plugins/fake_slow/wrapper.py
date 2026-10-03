"""Test plugin fake_slow: starts a child process, then sleeps (for the timeout test)."""

from __future__ import annotations

import os
import subprocess
import sys
import time


def run(request):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    with open(os.path.join(request["paths"]["work_dir"], "pids.txt"), "w") as fh:
        fh.write(f"{os.getpid()} {child.pid}\n")
    time.sleep(float(request["options"].get("sleep_s", 600)))
    return {"clip_scores": [], "upstream": None, "env": {}}


def prefetch(metric_id, options):
    return {"downloaded": [], "notes": []}
