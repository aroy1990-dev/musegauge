"""End-to-end runs of `musegauge run` with the fake plugins (spec sections 11.4, 11.5)."""

from __future__ import annotations

import csv
import os
import shutil
import signal
import subprocess
import sys
import time

import jsonschema
import pytest
import yaml
from conftest import load_json, pid_running, run_cli, tree_digest

from musegauge import schemas


def results_of(out):
    doc = load_json(out / "results.json")
    schemas.check(doc, "results")
    jsonschema.validate(doc, schemas.load_schema("results"))
    return doc


def by_id(doc):
    return {m["metric_id"]: m for m in doc["metrics"]}


def test_run_with_fake_clip_and_fake_set(tmp_path, fixtures, mg_env, session_home):
    before = {k: tree_digest(fixtures[k]) for k in ("gen_small", "ref_small")}
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--prompts", str(fixtures["prompts_csv"]),
                    "--reference", str(fixtures["ref_small"]), "--metrics", "fake.clip@1,fake.set@1",
                    "--out", str(out), "--json"], mg_env)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == str(out / "results.json")
    doc = results_of(out)
    assert doc["suite"] is None and doc["run"]["reproducible"] is True and doc["run"]["threads"] is None
    assert doc["generated"]["n_clips"] == 12 and doc["generated"]["n_with_prompt"] == 12
    assert doc["generated"]["sample_rates_hz"] == {"32000": 12}
    assert doc["reference"]["kind"] == "dir" and doc["reference"]["n_clips"] == 12
    metrics = by_id(doc)
    clip = metrics["fake.clip@1"]
    assert clip["status"] == "ok" and clip["kind"] == "clip"
    (amp,) = clip["scores"]
    assert amp["name"] == "amplitude" and amp["n"] == 12 and amp["ci"]["low"] <= amp["value"] <= amp["ci"]["high"]
    assert clip["per_clip_file"] == "per_clip/fake.clip@1.csv"
    with open(out / clip["per_clip_file"], newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["clip_id"] for r in rows] == [f"gen_{i:03d}" for i in range(12)]
    fset = metrics["fake.set@1"]
    assert {s["name"]: s["value"] for s in fset["scores"]} == {"n_files": 12.0, "n_ref_files": 12.0}
    assert fset["scores"][0]["ci"] is None
    for name in ("logs/fake_clip.log", "logs/fake_set.log", "requests/fake.clip@1.request.json",
                 "responses/fake.clip@1.response.json", "responses/fake.set@1.response.json"):
        assert (out / name).is_file(), name
    assert not (session_home / "work" / doc["run"]["run_id"]).exists()  # work folder cleaned
    assert not [p for p in (session_home / "refs").iterdir() if p.is_dir()]  # no reference reuse (A9)
    assert {k: tree_digest(fixtures[k]) for k in ("gen_small", "ref_small")} == before
    printed = run_cli(["report", str(out / "results.json")], mg_env)
    assert printed.returncode == 0 and printed.stdout == (out / "report.md").read_text()


def test_partial_failure_exits_10_and_all_failed_exits_5(tmp_path, fixtures, mg_env):
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.fail@1,fake.clip@1",
                    "--out", str(tmp_path / "a")], mg_env)
    assert proc.returncode == 10, proc.stderr
    metrics = by_id(results_of(tmp_path / "a"))
    assert metrics["fake.clip@1"]["status"] == "ok"
    assert metrics["fake.fail@1"]["status"] == "error"
    assert metrics["fake.fail@1"]["error"]["message"] == "fake_fail always fails"
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.fail@1",
                    "--out", str(tmp_path / "b")], mg_env)
    assert proc.returncode == 5


def test_bad_clip_is_listed_and_others_are_scored(tmp_path, fixtures, mg_env):
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.badclip@1",
                    "--out", str(tmp_path / "o")], mg_env)
    assert proc.returncode == 0, proc.stderr
    m = by_id(results_of(tmp_path / "o"))["fake.badclip@1"]
    assert m["clips_failed"] == [{"clip_id": "gen_003", "reason": "ValueError: fake_badclip refuses this clip"}]
    assert m["scores"][0]["n"] == 11


def test_unreadable_clips_are_skipped_not_dropped(tmp_path, fixtures, mg_env):
    gen = shutil.copytree(fixtures["gen_small"], tmp_path / "gen")
    shutil.copy(fixtures["broken_clip"], gen / "broken.wav")
    shutil.copy(fixtures["empty_file"], gen / "empty.wav")
    proc = run_cli(["run", "--generated", str(gen), "--metrics", "fake.clip@1", "--out", str(tmp_path / "o")], mg_env)
    assert proc.returncode == 0, proc.stderr
    doc = results_of(tmp_path / "o")
    assert doc["generated"]["n_skipped"] == 2
    assert {s["clip_id"] for s in doc["generated"]["skipped"]} == {"broken", "empty"}
    assert [w["code"] for w in doc["warnings"]] == ["CLIPS_SKIPPED"]


def test_timeout_kills_the_plugin_and_its_children(tmp_path, fixtures, mg_env):
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "home"))
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.slow@1",
                    "--timeout-min", "0.05", "--keep-work", "--out", str(tmp_path / "o")], env)
    assert proc.returncode == 5, proc.stderr
    doc = results_of(tmp_path / "o")
    assert by_id(doc)["fake.slow@1"]["error"]["type"] == "Timeout"
    (pids_file,) = (tmp_path / "home" / "work").glob("*/fake_slow/pids.txt")
    pids = [int(p) for p in pids_file.read_text().split()]
    assert len(pids) == 2 and not any(pid_running(p) for p in pids)


def test_interrupt_stops_plugins_and_the_next_run_works(tmp_path, fixtures, mg_env):
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "home"))
    cmd = [sys.executable, "-m", "musegauge.cli", "run", "--generated", str(fixtures["gen_small"]),
           "--metrics", "fake.slow@1", "--out", str(tmp_path / "o1")]
    core = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 60
    pids_files = []
    while not pids_files:
        assert time.monotonic() < deadline, "fake_slow did not start"
        time.sleep(0.1)
        pids_files = [p for p in (tmp_path / "home" / "work").glob("*/fake_slow/pids.txt")
                      if len(p.read_text().split()) == 2]
    pids = [int(p) for p in pids_files[0].read_text().split()]
    core.send_signal(signal.SIGINT)
    _, err = core.communicate(timeout=60)
    assert core.returncode == 130, err
    assert "interrupted" in err
    assert not any(pid_running(p) for p in pids)
    assert list((tmp_path / "home" / "work").iterdir()) == []
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.clip@1",
                    "--out", str(tmp_path / "o2")], env)
    assert proc.returncode == 0, proc.stderr


def test_killed_environment_build_is_rebuilt(tmp_path, fixtures, mg_env, fake_plugin_root):
    root = tmp_path / "plugins"
    plugin = shutil.copytree(fake_plugin_root / "fake_clip", root / "fake_clip")
    manifest = yaml.safe_load((plugin / "manifest.yaml").read_text())
    quick_smoke = manifest["smoke"]
    manifest["smoke"] = ["python", "-c", "import time; time.sleep(120)"]
    (plugin / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "home"), MUSEGAUGE_PLUGIN_PATH=str(root))
    cmd = [sys.executable, "-m", "musegauge.cli", "run", "--generated", str(fixtures["gen_small"]),
           "--metrics", "fake.clip@1", "--out", str(tmp_path / "o1")]
    core = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    envs = tmp_path / "home" / "envs"
    deadline = time.monotonic() + 60
    while not any(envs.glob("fake_clip-*/bin/python")):
        assert time.monotonic() < deadline, "the build did not start"
        time.sleep(0.05)
    time.sleep(0.5)  # now in the install or smoke step
    os.killpg(core.pid, signal.SIGKILL)
    core.wait(timeout=30)
    (folder,) = [p for p in envs.glob("fake_clip-*") if p.is_dir()]
    assert not (folder / ".ready").exists()
    manifest["smoke"] = quick_smoke  # the env hash does not depend on the smoke command
    (plugin / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    proc = run_cli(cmd[3:-1] + [str(tmp_path / "o2")], env)
    assert proc.returncode == 0, proc.stderr
    assert (folder / ".ready").is_file()


@pytest.mark.parametrize("extra,code", [
    (["--metrics", "fake.set@1"], 3),  # needs a reference, none given
    (["--metrics", "fake.set@1", "--reference", "bundled:fma_pop"], 3),
    (["--metrics", "fake.clip@1", "--commercial"], 6),
    (["--metrics", "fake.nothing@1"], 2),
])
def test_preflight_exit_codes(tmp_path, fixtures, mg_env, extra, code):
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--out", str(tmp_path / "o"), *extra], mg_env)
    assert proc.returncode == code, proc.stderr
    assert not (tmp_path / "o" / "results.json").exists()


def test_threads_reach_the_plugin_and_the_results(tmp_path, fixtures, mg_env, fake_plugin_root):
    """--threads N sets the four thread variables in the plugin process and is recorded."""
    root = tmp_path / "plugins"
    plugin = shutil.copytree(fake_plugin_root / "fake_clip", root / "fake_clip")
    wrapper = plugin / "wrapper.py"
    wrapper.write_text(wrapper.read_text().replace(
        '"env": {"python": platform.python_version(), "device": "cpu"},',
        '"env": {"python": platform.python_version(), "device": "cpu", '
        '"threads_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", '
        '"OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")}},'))
    env = dict(mg_env, MUSEGAUGE_PLUGIN_PATH=str(root), OMP_NUM_THREADS="77")
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.clip@1",
                    "--threads", "4", "--out", str(tmp_path / "a")], env)
    assert proc.returncode == 0, proc.stderr
    doc = results_of(tmp_path / "a")
    assert doc["run"]["threads"] == 4
    assert set(doc["metrics"][0]["env"]["threads_env"].values()) == {"4"}
    assert "CPU threads per plugin: 4." in (tmp_path / "a" / "report.md").read_text()
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.clip@1",
                    "--out", str(tmp_path / "b")], env)
    doc = results_of(tmp_path / "b")
    assert doc["run"]["threads"] is None
    assert set(doc["metrics"][0]["env"]["threads_env"].values()) == {None}  # not even the core's 77


def test_torch_hub_http_error_becomes_network_error(tmp_path, fixtures, mg_env, fake_plugin_root):
    """GATE 2 item 3b: a failing plugin whose output shows a torch.hub HTTP error gets NETWORK_ERROR."""
    root = tmp_path / "plugins"
    plugin = shutil.copytree(fake_plugin_root / "fake_fail", root / "fake_fail")
    (plugin / "wrapper.py").write_text(
        "def run(request):\n"
        "    print('Traceback (most recent call last):')\n"
        "    print('  File \"/env/lib/python3.11/site-packages/torch/hub.py\", line 199, in _parse_repo_info')\n"
        "    print('urllib.error.HTTPError: HTTP Error 429: Too Many Requests', flush=True)\n"
        "    raise RuntimeError('fadtk exited with code 1')\n"
        "\n"
        "def prefetch(metric_id, options):\n"
        "    return {}\n")
    env = dict(mg_env, MUSEGAUGE_PLUGIN_PATH=str(root))
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.fail@1",
                    "--out", str(tmp_path / "o")], env)
    assert proc.returncode == 5
    error = by_id(results_of(tmp_path / "o"))["fake.fail@1"]["error"]
    assert error["type"] == "NETWORK_ERROR" and "Original error: RuntimeError" in error["message"]


def test_other_failures_keep_their_error_type(tmp_path, fixtures, mg_env):
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", "fake.fail@1",
                    "--out", str(tmp_path / "o")], mg_env)
    assert proc.returncode == 5
    assert by_id(results_of(tmp_path / "o"))["fake.fail@1"]["error"]["type"] == "RuntimeError"

