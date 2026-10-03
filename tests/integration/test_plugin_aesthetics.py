"""Plugin aesthetics_audiobox with the real upstream package (spec section 12, M3). Slow."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
from conftest import load_json, run_cli

from musegauge import config, schemas
from musegauge.envs import UvBackend
from musegauge.registry import Registry

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def plugin_env():
    home = config.musegauge_home()
    plugin = Registry.discover([]).plugins["aesthetics_audiobox"]
    return home, plugin, UvBackend(config.envs_dir(home), home).ensure(plugin)


def test_environment_loads_wav_with_torchaudio(plugin_env, fixtures):
    home, _, env = plugin_env
    wav = str(fixtures["gen_small"] / "gen_000.wav")
    code = f"import torchaudio; w, sr = torchaudio.load({wav!r}); print(sr, tuple(w.shape))"
    out = subprocess.run([str(env.python), "-c", code], env=config.plugin_process_env(home, False, False),
                         capture_output=True, text=True, check=True)
    assert out.stdout.split()[0] == "32000"


def test_broken_clip_is_listed_and_others_are_scored(plugin_env, fixtures, tmp_path):
    """The core's probe already skips unreadable files, so this sends a broken file straight to
    the wrapper, as a plugin would see a file that its own loader cannot read."""
    home, plugin, env = plugin_env
    gen = tmp_path / "gen"
    gen.mkdir()
    clips = []
    for cid in ("gen_000", "gen_001", "gen_002"):
        shutil.copy(fixtures["gen_small"] / f"{cid}.wav", gen / f"{cid}.wav")
        clips.append({"clip_id": cid, "file": f"{cid}.wav", "prompt": None, "duration_s": 10.0,
                      "sample_rate_hz": 32000, "channels": 1})
    shutil.copy(fixtures["broken_clip"], gen / "broken.wav")
    clips.insert(1, {"clip_id": "broken", "file": "broken.wav", "prompt": None, "duration_s": 1.0,
                     "sample_rate_hz": 32000, "channels": 1})
    request = {"schema": 1, "run_id": "test", "metric_id": "aesthetics.audiobox@1", "options": {"per_clip": False},
               "device": "cpu", "seed": 0, "workers": 1, "batch_size": None,
               "generated": {"dir": str(gen), "clips": clips},
               "reference": {"kind": "none", "name": None, "dir": None, "n_clips": None},
               "paths": {"work_dir": str(tmp_path), "weights_dir": str(home / "weights")}}
    schemas.check(request, "request")
    (tmp_path / "request.json").write_text(json.dumps(request))
    proc = subprocess.run(
        [str(env.python), "-m", "musegauge_runtime.run", "--plugin-dir", str(plugin.dir),
         "--request", str(tmp_path / "request.json"), "--response", str(tmp_path / "response.json")],
        env=config.plugin_process_env(home, no_fetch=True), cwd=tmp_path, capture_output=True, text=True,
        check=False)
    resp = json.loads((tmp_path / "response.json").read_text())
    schemas.check(resp, "response")
    assert proc.returncode == 0 and resp["status"] == "ok", resp["error"]
    assert [c["clip_id"] for c in resp["clips_failed"]] == ["broken"]
    assert resp["clips_failed"][0]["reason"]
    assert sorted(c["clip_id"] for c in resp["clip_scores"]) == ["gen_000", "gen_001", "gen_002"]
    assert all(set(c["scores"]) == {"CE", "CU", "PC", "PQ"} for c in resp["clip_scores"])
    assert resp["env"]["device"] == "cpu" and resp["env"]["torch"].startswith("2.7.0")


def test_core_run_skips_unreadable_file_and_scores_the_rest(fixtures, tmp_path):
    gen = shutil.copytree(fixtures["gen_small"], tmp_path / "gen")
    shutil.copy(fixtures["broken_clip"], gen / "broken.wav")
    env = dict(os.environ)
    env.pop("MUSEGAUGE_PLUGIN_PATH", None)
    proc = run_cli(["run", "--generated", str(gen), "--metrics", "aesthetics.audiobox@1", "--device", "cpu",
                    "--no-fetch", "--out", str(tmp_path / "out")], env, timeout=1800)
    assert proc.returncode == 0, proc.stderr[-2000:]
    doc = load_json(tmp_path / "out" / "results.json")
    (m,) = doc["metrics"]
    assert [s["clip_id"] for s in doc["generated"]["skipped"]] == ["broken"]
    assert {s["name"]: s["n"] for s in m["scores"]} == {"CE": 12, "CU": 12, "PC": 12, "PQ": 12}
    assert m["licence"]["commercial_ok"] == "unknown"
