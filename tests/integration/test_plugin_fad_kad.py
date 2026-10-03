"""Plugins fad_fadtk and kad_kadtk with the real upstream tools (spec section 12, M5). Slow.

These runs use --device cpu: the GPU cases are in test_golden.py.
"""

from __future__ import annotations

import csv
import os
import shutil

import pytest
from conftest import load_json, run_cli, tree_digest

pytestmark = pytest.mark.slow
CACHE_FOLDERS = {"embeddings", "convert", "stats", "kernel_stats"}


@pytest.fixture
def real_env():
    env = dict(os.environ)
    env.pop("MUSEGAUGE_PLUGIN_PATH", None)
    return env


@pytest.fixture
def inputs(fixtures, tmp_path):
    """Fresh copies of gen_small and ref_small, so this test owns them."""
    return {k: shutil.copytree(fixtures[k], tmp_path / k) for k in ("gen_small", "ref_small")}


def torch_major_minor(version: str) -> tuple[int, int]:
    major, minor = version.split("+")[0].split(".")[:2]
    return int(major), int(minor)


def test_two_torch_versions_in_one_run_and_inputs_untouched(inputs, real_env, tmp_path):
    before = {k: tree_digest(v) for k, v in inputs.items()}
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(inputs["gen_small"]), "--reference", str(inputs["ref_small"]),
                    "--metrics", "fad.vggish@1,kad.vggish@1", "--device", "cpu", "--no-fetch", "--out", str(out)],
                   real_env, timeout=3600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    doc = load_json(out / "results.json")
    metrics = {m["metric_id"]: m for m in doc["metrics"]}
    fad, kad = metrics["fad.vggish@1"], metrics["kad.vggish@1"]
    assert fad["status"] == kad["status"] == "ok"
    assert torch_major_minor(fad["env"]["torch"]) == (2, 7) and fad["env"]["torch"].startswith("2.7.0")
    assert torch_major_minor(kad["env"]["torch"]) < (2, 6)
    assert {s["name"] for s in fad["scores"]} == {"fad", "fad_inf", "fad_inf_r2"}
    assert [s["name"] for s in kad["scores"]] == ["kad"]
    assert doc["reference"]["kind"] == "dir" and doc["reference"]["n_clips"] == 12
    # Inputs untouched (section 11.5, F9): same bytes, and no cache folders inside them.
    assert {k: tree_digest(v) for k, v in inputs.items()} == before
    for folder in inputs.values():
        assert not {p.name for p in folder.iterdir() if p.is_dir()} & CACHE_FOLDERS


def test_fad_with_bundled_reference_and_per_clip(inputs, real_env, tmp_path):
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(inputs["gen_small"]), "--reference", "bundled:fma_pop",
                    "--metrics", "fad.vggish@1", "--per-clip", "--device", "cpu", "--no-fetch", "--out", str(out)],
                   real_env, timeout=3600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    doc = load_json(out / "results.json")
    (m,) = doc["metrics"]
    assert doc["reference"] == {"kind": "bundled", "name": "fma_pop", "ref_hash": None, "n_clips": None,
                                "total_duration_s": None}
    assert m["status"] == "ok" and m["per_clip_file"] == "per_clip/fad.vggish@1.csv"
    with open(out / m["per_clip_file"], newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert sorted(r["clip_id"] for r in rows) == [f"gen_{i:03d}" for i in range(12)]
    assert all(float(r["fad_indiv"]) >= 0 for r in rows)
    assert {s["name"] for s in m["scores"]} == {"fad", "fad_inf", "fad_inf_r2"}  # per-clip FAD is not averaged


def test_kad_runs_on_cpu_without_a_gpu(inputs, real_env, tmp_path):
    env = dict(real_env, CUDA_VISIBLE_DEVICES="")  # a machine without a GPU, as far as torch can tell
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(inputs["gen_small"]), "--reference", str(inputs["ref_small"]),
                    "--metrics", "kad.vggish@1", "--device", "cpu", "--no-fetch", "--out", str(out)], env, timeout=3600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    (m,) = load_json(out / "results.json")["metrics"]
    assert m["status"] == "ok" and m["env"]["device"] == "cpu" and m["env"]["cuda_available"] is False
    assert "--device cpu" in m["upstream"]["invocation"]


def test_kad_refuses_the_bundled_reference(inputs, real_env, tmp_path):
    proc = run_cli(["run", "--generated", str(inputs["gen_small"]), "--reference", "bundled:fma_pop",
                    "--metrics", "kad.vggish@1", "--out", str(tmp_path / "out")], real_env, timeout=600)
    assert proc.returncode == 3 and "cannot use a bundled reference" in proc.stderr
