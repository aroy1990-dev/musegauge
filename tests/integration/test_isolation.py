"""Isolation test (spec section 11.4): two plugins, two Pythons, two numpy major versions.

Slow: builds two real environments. The first run downloads Python 3.11 (if uv does not
have it yet) and numpy wheels.
"""

from __future__ import annotations

import numpy
import pytest
from conftest import load_json, run_cli

from musegauge import schemas


@pytest.mark.slow
def test_fake_np1_and_fake_np2_are_isolated(tmp_path, fixtures, mg_env):
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "home"))
    env.pop("UV_OFFLINE", None)
    env.pop("UV_PYTHON_DOWNLOADS", None)
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.np1@1,fake.np2@1",
                    "--out", str(out)], env, timeout=1800)
    assert proc.returncode == 0, proc.stderr
    doc = load_json(out / "results.json")
    schemas.check(doc, "results")
    envs = {m["metric_id"]: m["env"] for m in doc["metrics"]}
    np1, np2 = envs["fake.np1@1"], envs["fake.np2@1"]
    assert np1["numpy"].split(".")[0] == "1"
    assert np2["numpy"].split(".")[0] == "2"
    assert np1["python"] != np2["python"]
    assert np1["python"].startswith("3.11.") and np2["python"].startswith("3.12.")
    assert numpy.__version__ not in (np1["numpy"], np2["numpy"])
    assert np1["env_id"] != np2["env_id"]
    assert np1["numpy_file"].startswith(str(tmp_path / "home" / "envs" / np1["env_id"]))
    assert np2["numpy_file"].startswith(str(tmp_path / "home" / "envs" / np2["env_id"]))
