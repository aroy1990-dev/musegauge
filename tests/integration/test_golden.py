"""Golden tests (spec section 11.6): the harness gives the same numbers as the upstream tool.

Golden numbers come from tests/golden_scripts/record_golden.py, run on this machine. A test
is skipped when the stored device or torch version differs from the harness run.
tolerance = max(10 * standard deviation of the three upstream runs, 1e-6), per value.
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import pytest
from conftest import TESTS, load_json, pick_gpu, run_cli, tree_digest

sys.path.insert(0, str(TESTS / "golden_scripts"))
from cases import CASES

MIN_TOL = 1e-6


def params():
    for plugin_id, cases in CASES.items():
        for case in cases:
            for device in ("cpu", "cuda"):
                marks = [pytest.mark.slow] + ([pytest.mark.gpu] if device == "cuda" else [])
                yield pytest.param(plugin_id, case, device, marks=marks,
                                   id=f"{plugin_id}-{case['case']}-{device}")


@pytest.fixture
def real_env(monkeypatch):
    """The user's MUSEGAUGE_HOME (environments and weights are reused), built-in plugins only."""
    env = dict(os.environ)
    env.pop("MUSEGAUGE_PLUGIN_PATH", None)
    return env


def fill(args, fixtures):
    values = {"gen": fixtures["gen_small"], "ref": fixtures["ref_small"],
              "prompts_jsonl": fixtures["prompts_jsonl"], "prompts_csv": fixtures["prompts_csv"]}
    return [a.format(**{k: str(v) for k, v in values.items()}) for a in args]


def compare(golden_values: list[dict], harness: dict, random_keys=()) -> tuple[list, list[str]]:
    """Per key in golden_values[0]: (key, |harness - upstream mean|, tolerance) and the problems.

    Keys in random_keys come from randomness the harness cannot seed. They are only checked to be
    present and finite (amendment A10); their row has tolerance None.
    """
    rows, problems = [], []
    for key in golden_values[0]:
        runs = np.array([g[key] for g in golden_values], dtype=float)
        if key in random_keys:
            value = harness.get(key)
            rows.append((key, value, None, runs))
            if value is None or not np.isfinite(value):
                problems.append(f"{key}: missing or not finite ({value!r})")
            continue
        tol = max(10 * runs.std(), MIN_TOL)
        diff = abs(harness[key] - runs.mean())
        rows.append((key, diff, tol, runs))
        if diff > tol:
            problems.append(f"{key}: harness {harness[key]!r}, upstream mean {runs.mean()!r}, tolerance {tol:.3g}")
    return rows, problems


def run_case(plugin_id, case, device, fixtures, env, tmp_path, extra=()):
    """Run the harness for one golden case. Returns (stored golden entry, rows, problems, metric)."""
    golden = json.loads((TESTS / "golden" / f"{plugin_id}.json").read_text())
    current = {"gen_small": tree_digest(fixtures["gen_small"]), "ref_small": tree_digest(fixtures["ref_small"])}
    for name, digest in current.items():
        assert golden["fixture_sha256"][name] == digest, (
            f"fixture {name} changed since the golden numbers were recorded; re-record them on this machine")
    stored = golden["cases"].get(case["case"], {}).get(device)
    if stored is None:
        pytest.skip(f"no golden numbers recorded for device {device}")
    env = dict(env)
    if device == "cuda":
        gpu = pick_gpu()
        if gpu is None:
            pytest.skip("no GPU with enough free memory")
        env["CUDA_VISIBLE_DEVICES"] = gpu[0]
    out = tmp_path / "out"
    args = ["run", "--generated", str(fixtures["gen_small"]), *fill(case["harness"], fixtures),
            "--device", device, *extra, "--out", str(out)]
    proc = run_cli(args, env, timeout=3600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    results = load_json(out / "results.json")
    (metric,) = [m for m in results["metrics"] if m["metric_id"] == case["metric_id"]]
    assert metric["status"] == "ok", metric["error"]
    if metric["env"]["torch"] != stored["torch"]:
        pytest.skip(f"torch {metric['env']['torch']} differs from the golden file's {stored['torch']}")
    cores = len(os.sched_getaffinity(0))
    if device == "cpu" and stored.get("cpu_cores") != cores:
        pytest.skip(f"CPU numbers depend on the thread count: golden recorded on {stored.get('cpu_cores')} "
                    f"cores, this run may use {cores} (run under the same taskset)")
    assert metric["env"]["device"] == device
    reps = stored["repeats"]
    if "per_clip" in reps[0]:
        with open(out / metric["per_clip_file"], newline="") as fh:
            rows = {r["clip_id"]: r for r in csv.DictReader(fh)}
        flat_golden = [{f"{c}/{k}": v for c, s in r["per_clip"].items() for k, v in s.items()} for r in reps]
        harness = {key: float(rows[key.split("/")[0]][key.split("/")[1]]) for key in flat_golden[0]}
    else:
        flat_golden = [r["scores"] for r in reps]
        harness = {s["name"]: s["value"] for s in metric["scores"]}
    rows, problems = compare(flat_golden, harness, case.get("random_scores", []))
    return stored, rows, problems, metric


def describe(head: str, rows: list, problems: list) -> str:
    checked = [r for r in rows if r[2] is not None]
    if len(checked) > 6:  # per-clip metrics: one summary line
        worst = max(checked, key=lambda r: r[1] / r[2])
        largest = max(r[1] for r in checked)
        return (f"{head}: {len(checked)} values, {len(problems)} outside tolerance; largest |diff| "
                f"{largest:.3g}; closest to its limit: {worst[0]} |diff| {worst[1]:.3g} vs tolerance {worst[2]:.3g}")
    parts = []
    for key, d, t, runs in rows:
        if t is None:
            parts.append(f"{key} {d:.4f} (random, upstream runs {', '.join(f'{x:.4f}' for x in runs)})")
        else:
            parts.append(f"{key} |diff| {d:.3g} vs tolerance {t:.3g}")
    return f"{head}: " + "; ".join(parts) + f"; {len(problems)} problems"


@pytest.mark.parametrize("plugin_id,case,device", list(params()))
def test_golden(plugin_id, case, device, fixtures, real_env, tmp_path):
    stored, rows, problems, metric = run_case(plugin_id, case, device, fixtures, real_env, tmp_path)
    gpu_name = metric["env"].get("gpu_name")
    head = f"GOLDEN {plugin_id} {case['case']} {device} ({gpu_name or 'cpu'}, torch {stored['torch']})"
    print("\n" + describe(head, rows, problems))
    assert not problems, "\n".join(problems[:20])


# --threads 4 against golden numbers recorded with the default thread count (GATE 2 and GATE 3).
# CPU results depend on the thread count. Observed on 2026-10-03, on the build machine:
#   fad_fadtk vggish-dir, score fad:           |diff| 1.3e-6
#   aesthetics_audiobox gen_small, any score:  |diff| up to 2.9e-6
# Rule (Roy, GATE 3): this test fails only if a difference exceeds 10 times the observed one,
# that is 1.3e-5 for fad and 2.9e-5 for Audiobox. Random scores (A10) are only checked to be
# present and finite.
THREADS_CASES = {
    ("fad_fadtk", "vggish-dir"): 1.3e-6,
    ("aesthetics_audiobox", "gen_small"): 2.9e-6,
}
THREADS_FACTOR = 10


@pytest.mark.slow
@pytest.mark.parametrize("plugin_id,case_id", list(THREADS_CASES), ids=[f"{p}-{c}" for p, c in THREADS_CASES])
def test_golden_cpu_with_threads_4(plugin_id, case_id, fixtures, real_env, tmp_path):
    (case,) = [c for c in CASES[plugin_id] if c["case"] == case_id]
    stored, rows, _, metric = run_case(plugin_id, case, "cpu", fixtures, real_env, tmp_path,
                                       extra=("--threads", "4"))
    assert metric["env"].get("device") == "cpu" and metric["env"].get("torch_threads") == 4
    limit = THREADS_FACTOR * THREADS_CASES[(plugin_id, case_id)]
    checked = [(key, diff) for key, diff, tol, _ in rows if tol is not None]
    largest = max(diff for _, diff in checked)
    print(f"\nGOLDEN-THREADS4 {plugin_id} {case_id} cpu (torch {stored['torch']}): {len(checked)} values, "
          f"largest |diff| {largest:.3g}, limit {limit:.3g} (10 x observed)")
    too_far = [f"{key}: |diff| {diff:.3g} > {limit:.3g}" for key, diff in checked if diff > limit]
    assert not too_far, "\n".join(too_far)
    for key, value, tol, _ in rows:
        if tol is None:
            assert value is not None and np.isfinite(value), key
