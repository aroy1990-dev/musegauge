"""Record golden numbers by calling an upstream tool directly, three times (spec section 11.6).

    python tests/golden_scripts/record_golden.py PLUGIN_ID --device cpu|cuda

Builds (or reuses) the plugin's environment in MUSEGAUGE_HOME, makes the synthetic fixtures,
and runs each case's direct script in that environment three times, each time on a fresh copy
of the fixtures. Writes tests/golden/<PLUGIN_ID>.json. Only numbers from runs on this machine
go into golden files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
sys.path[:0] = [str(TESTS), str(HERE)]

from cases import CASES
from conftest import pick_gpu, tree_digest
from make_fixtures import make_all

from musegauge import config
from musegauge.envs import UvBackend
from musegauge.registry import Registry

REPEATS = 3


def fixture_digests(fx: dict) -> dict:
    return {
        "gen_small": tree_digest(fx["gen_small"]),
        "ref_small": tree_digest(fx["ref_small"]),
        "prompts_jsonl": hashlib.sha256(fx["prompts_jsonl"].read_bytes()).hexdigest(),
    }


def fill(args: list[str], fx: dict, work: Path) -> list[str]:
    values = {"gen": fx["gen_small"], "ref": fx["ref_small"], "prompts_jsonl": fx["prompts_jsonl"],
              "prompts_csv": fx["prompts_csv"], "work": work}
    return [a.format(**{k: str(v) for k, v in values.items()}) for a in args]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin_id")
    ap.add_argument("--device", choices=("cpu", "cuda"), required=True)
    args = ap.parse_args()
    home = config.musegauge_home()
    plugin = Registry.discover([]).plugins[args.plugin_id]
    env = UvBackend(config.envs_dir(home), home).ensure(plugin)
    proc_env = config.plugin_process_env(home, no_fetch=False, runtime=False)
    gpu = None
    if args.device == "cpu":
        proc_env["CUDA_VISIBLE_DEVICES"] = ""
    else:
        gpu = pick_gpu()
        if gpu is None:
            print("no GPU with enough free memory; nothing recorded", file=sys.stderr)
            return 1
        proc_env["CUDA_VISIBLE_DEVICES"] = gpu[0]
        print(f"using GPU {gpu[0]} ({gpu[1]}, {gpu[2]} MiB free)", file=sys.stderr)

    golden_path = TESTS / "golden" / f"{args.plugin_id}.json"
    golden = json.loads(golden_path.read_text()) if golden_path.exists() else {"plugin_id": args.plugin_id, "cases": {}}
    with tempfile.TemporaryDirectory() as tmp:
        base = make_all(Path(tmp) / "base")
        golden["fixture_sha256"] = fixture_digests(base)
        for case in CASES[args.plugin_id]:
            repeats = []
            for i in range(REPEATS):
                run_dir = Path(tmp) / f"{case['case']}-{i}"
                fx = {k: run_dir / v.relative_to(Path(tmp) / "base") for k, v in base.items()}
                shutil.copytree(Path(tmp) / "base", run_dir)
                out = run_dir / "direct.json"
                script, *rest = case["direct"]
                cmd = [str(env.python), str(HERE / script), *fill(rest, fx, run_dir), "--out", str(out)]
                print("$", " ".join(cmd), file=sys.stderr)
                t0 = time.monotonic()
                subprocess.run(cmd, env=proc_env, cwd=run_dir, check=True)
                result = json.loads(out.read_text())
                result["seconds"] = round(time.monotonic() - t0, 1)
                repeats.append(result)
            keys = ("device", "torch", "upstream_version", "python")
            first = {k: repeats[0][k] for k in keys}
            assert all({k: r[k] for k in keys} == first for r in repeats), "repeats differ in versions"
            golden["cases"].setdefault(case["case"], {})[first["device"]] = {
                "metric_id": case["metric_id"],
                **first,
                "gpu_name": repeats[0].get("gpu_name"),
                "invocation": repeats[0].get("invocation"),
                "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "env_id": env.env_id,
                # CPU numbers depend on the thread count, which follows the cores a process may use.
                "cpu_cores": len(os.sched_getaffinity(0)),
                "torch_threads": repeats[0].get("torch_threads"),
                "repeats": [{k: r[k] for k in ("per_clip", "scores", "seconds") if k in r} for r in repeats],
            }
    golden_path.write_text(json.dumps(golden, indent=2, sort_keys=False) + "\n")
    print(f"wrote {golden_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
