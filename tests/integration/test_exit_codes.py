"""Each exit code of section 7.3 is produced by a real `musegauge` process."""

from __future__ import annotations

import json
import shutil

import pytest
import yaml
from conftest import load_json, run_cli


def with_plugin_copy(tmp_path, fake_plugin_root, env, source, new_id, change):
    root = tmp_path / "extra_plugins"
    dst = shutil.copytree(fake_plugin_root / source, root / new_id)
    data = yaml.safe_load((dst / "manifest.yaml").read_text())
    data["plugin_id"] = new_id
    data["family"] = new_id.replace("_", "")
    data["metrics"][0]["id"] = f"{data['family']}.{source.split('_')[1]}@1"
    change(data)
    (dst / "manifest.yaml").write_text(yaml.safe_dump(data))
    env = dict(env, MUSEGAUGE_PLUGIN_PATH=f"{env['MUSEGAUGE_PLUGIN_PATH']}:{root}")
    return env, data["metrics"][0]["id"]


def run_gen(fixtures, tmp_path, env, *extra):
    return run_cli(["run", "--generated", str(fixtures["gen_small"]), "--out", str(tmp_path / "out"), *extra], env)


def test_exit_0_everything_ran(tmp_path, fixtures, mg_env):
    assert run_gen(fixtures, tmp_path, mg_env, "--metrics", "fake.clip@1").returncode == 0


@pytest.mark.parametrize("extra", [
    ["--metrics", "fake.clip@1", "--suite", "t2m-basic"],
    ["--metrics", "fake.nothing@1"],
    ["--bootstrap", "x"],
])
def test_exit_2_usage(tmp_path, fixtures, mg_env, extra):
    assert run_gen(fixtures, tmp_path, mg_env, *extra).returncode == 2


def test_exit_3_input(tmp_path, fixtures, mg_env):
    clips = tmp_path / "clips.jsonl"
    clips.write_text(json.dumps({"clip_id": "a", "path": "x.wav"}) * 2 + "\n")
    assert run_cli(["run", "--manifest", str(clips), "--metrics", "fake.clip@1"], mg_env).returncode == 3
    clips.write_text(json.dumps({"clip_id": "a", "path": str(fixtures["broken_clip"])}) + "\n")
    proc = run_cli(["run", "--manifest", str(clips), "--metrics", "fake.clip@1"], mg_env)
    assert proc.returncode == 3 and "no clip can be read" in proc.stderr
    assert run_gen(fixtures, tmp_path, mg_env, "--metrics", "fake.set@1").returncode == 3
    proc = run_gen(fixtures, tmp_path, mg_env, "--metrics", "fake.set@1", "--reference", "bundled:fma_pop")
    assert proc.returncode == 3 and "cannot use a bundled reference" in proc.stderr


def test_exit_4_missing_system_tool(tmp_path, fixtures, mg_env, fake_plugin_root):
    env, mid = with_plugin_copy(tmp_path, fake_plugin_root, mg_env, "fake_clip", "tool_clip",
                                lambda d: d["system_tools"].update(required=["no-such-tool-xyz"]))
    proc = run_gen(fixtures, tmp_path, env, "--metrics", mid)
    assert proc.returncode == 4 and "no-such-tool-xyz not found" in proc.stderr


def test_exit_5_all_failed(tmp_path, fixtures, mg_env):
    assert run_gen(fixtures, tmp_path, mg_env, "--metrics", "fake.fail@1").returncode == 5


def test_exit_6_licence_policy(tmp_path, fixtures, mg_env):
    proc = run_gen(fixtures, tmp_path, mg_env, "--metrics", "fake.clip@1", "--commercial")
    assert proc.returncode == 6 and "commercial_ok is not yes" in proc.stderr


def test_exit_10_some_failed(tmp_path, fixtures, mg_env):
    assert run_gen(fixtures, tmp_path, mg_env, "--metrics", "fake.clip@1,fake.fail@1").returncode == 10


def test_no_lock_skips_the_plugin_with_a_run_warning(tmp_path, fixtures, mg_env, fake_plugin_root):
    env, mid = with_plugin_copy(tmp_path, fake_plugin_root, mg_env, "fake_clip", "nolock_clip",
                                lambda d: d.update(locks={}))
    proc = run_gen(fixtures, tmp_path, env, "--metrics", f"{mid},fake.clip@1")
    assert proc.returncode == 0, proc.stderr
    doc = load_json(tmp_path / "out" / "results.json")
    statuses = {m["metric_id"]: m["status"] for m in doc["metrics"]}
    assert statuses == {mid: "skipped", "fake.clip@1": "ok"}
    (warning,) = [w for w in doc["warnings"] if w["code"] == "NO_LOCK"]
    assert warning["scope"] == "run" and "nolock_clip" in warning["message"]
    assert doc["run"]["reproducible"] is True
    assert "NO_LOCK" in (tmp_path / "out" / "report.md").read_text()


def test_allow_unlocked_marks_the_run_not_reproducible(tmp_path, fixtures, mg_env, fake_plugin_root):
    env, mid = with_plugin_copy(tmp_path, fake_plugin_root, mg_env, "fake_clip", "unlocked_clip",
                                lambda d: d.update(locks={}))
    proc = run_gen(fixtures, tmp_path, env, "--metrics", mid, "--allow-unlocked")
    assert proc.returncode == 0, proc.stderr
    doc = load_json(tmp_path / "out" / "results.json")
    assert doc["run"]["reproducible"] is False
    assert [w["code"] for w in doc["warnings"]] == ["UNLOCKED_ENV"]
    assert doc["metrics"][0]["env"]["lock_sha256"] is None


def test_no_fetch_without_built_environment_exits_4(tmp_path, fixtures, mg_env):
    """GATE 3: run --no-fetch never builds an environment; it stops and says to run setup first."""
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "fresh_home"))
    proc = run_gen(fixtures, tmp_path, env, "--metrics", "fake.clip@1", "--no-fetch")
    assert proc.returncode == 4
    assert "musegauge setup --metrics fake.clip@1 --fetch-weights" in proc.stderr
    assert not (tmp_path / "fresh_home" / "envs").exists() or not any((tmp_path / "fresh_home" / "envs").iterdir())
    setup = run_cli(["setup", "--metrics", "fake.clip@1"], env)
    assert setup.returncode == 0, setup.stderr
    assert run_gen(fixtures, tmp_path, env, "--metrics", "fake.clip@1", "--no-fetch").returncode == 0

