"""The fad_fadtk wrapper's own logic, without fadtk or torch (fast).

torch, fadtk and the `fadtk` command are replaced by small stand-ins, so these tests check only
what the wrapper decides: which commands it runs, how it reads the CSV files, and which warnings
it adds (UNSEEDED_RANDOMNESS, FAD_INF_FAILED, NETWORK_FETCH). The real tools are covered by the
slow golden tests.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest

from musegauge import config

WRAPPER = config.BUILTIN_PLUGINS_DIR / "fad_fadtk" / "wrapper.py"


@pytest.fixture
def wrapper(monkeypatch, tmp_path):
    torch = types.ModuleType("torch")
    torch.__version__ = "0.0-test"
    torch.cuda = types.SimpleNamespace(is_available=lambda: False, get_device_name=lambda i: "none")
    torch.version = types.SimpleNamespace(cuda=None)
    torch.hub = types.SimpleNamespace(load=lambda *a, **k: None)
    torch.get_num_threads = lambda: 4
    fadtk = types.ModuleType("fadtk")
    fadtk.__file__ = str(tmp_path / "site" / "fadtk" / "__init__.py")
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "fadtk", fadtk)
    # The wrapper sets CUDA_VISIBLE_DEVICES itself for --device cpu; let pytest restore it after.
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch_home"))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf_home"))
    spec = importlib.util.spec_from_file_location("fad_wrapper_under_test", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "1.1.0")
    return module


def request(tmp_path, inf=True, per_clip=False):
    gen = tmp_path / "gen"
    gen.mkdir(exist_ok=True)
    return {
        "metric_id": "fad.vggish@1", "options": {"model": "vggish", "inf": inf, "per_clip": per_clip},
        "device": "cpu", "seed": 0, "workers": 2, "batch_size": None,
        "generated": {"dir": str(gen), "clips": [{"clip_id": "a", "file": "a.wav"}, {"clip_id": "b", "file": "b.wav"}]},
        "reference": {"kind": "bundled", "name": "fma_pop", "dir": None, "n_clips": None},
        "paths": {"work_dir": str(tmp_path), "weights_dir": str(tmp_path / "w")},
    }


def fake_fadtk(inf_fails=False, download_into=None):
    """A stand-in for subprocess.run(['fadtk', ...]) that writes the CSV files fadtk would write."""
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        csv = Path(cmd[4])
        if download_into:
            Path(download_into).mkdir(parents=True, exist_ok=True)
            (Path(download_into) / "vggish.pth").write_text("x")
        if "--inf" in cmd:
            if inf_fails:
                return subprocess.CompletedProcess(cmd, 1, stdout="Traceback ...\nValueError: too few frames")
            csv.write_text("model,baseline,eval,score,inf_r2,time\nvggish,fma_pop,gen,6.5,0.2,1\n")
        elif "--indiv" in cmd:
            gen = Path(cmd[3])
            csv.write_text(f"{gen / 'b.wav'},1.5\n{gen / 'a.wav'},2.5\n")
        else:
            csv.write_text("model,baseline,eval,score,inf_r2,time\nvggish,fma_pop,gen,6.4,None,1\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok")

    return run, calls


def codes(response):
    return [w["code"] for w in response["warnings"]]


def test_fad_and_fad_inf_with_unseeded_randomness(wrapper, monkeypatch, tmp_path):
    run, calls = fake_fadtk()
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    resp = wrapper.run(request(tmp_path))
    assert {s["name"]: s["value"] for s in resp["scores"]} == {"fad": 6.4, "fad_inf": 6.5, "fad_inf_r2": 0.2}
    assert codes(resp) == ["UNSEEDED_RANDOMNESS"]
    assert [c[1:4] for c in calls] == [["vggish", "fma_pop", str(tmp_path / "gen")]] * 2
    assert calls[1][-1] == "--inf" and calls[0][4] != calls[1][4]  # a new CSV for every call
    assert resp["env"]["device"] == "cpu" and "remote_code" in resp["env"]


def test_no_inf_means_no_unseeded_randomness(wrapper, monkeypatch, tmp_path):
    run, calls = fake_fadtk()
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    resp = wrapper.run(request(tmp_path, inf=False))
    assert [s["name"] for s in resp["scores"]] == ["fad"]
    assert "UNSEEDED_RANDOMNESS" not in codes(resp) and len(calls) == 1


def test_failed_inf_keeps_fad_and_adds_fad_inf_failed(wrapper, monkeypatch, tmp_path):
    run, _ = fake_fadtk(inf_fails=True)
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    resp = wrapper.run(request(tmp_path))
    assert [s["name"] for s in resp["scores"]] == ["fad"]
    assert codes(resp) == ["FAD_INF_FAILED"]
    assert "ValueError: too few frames" in resp["warnings"][0]["message"]


def test_successful_inf_has_no_fad_inf_failed(wrapper, monkeypatch, tmp_path):
    run, _ = fake_fadtk()
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert "FAD_INF_FAILED" not in codes(wrapper.run(request(tmp_path)))


def test_new_cache_files_raise_network_fetch(wrapper, monkeypatch, tmp_path):
    run, _ = fake_fadtk(download_into=tmp_path / "torch_home" / "hub" / "checkpoints")
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    resp = wrapper.run(request(tmp_path, inf=False))
    (w,) = [w for w in resp["warnings"] if w["code"] == "NETWORK_FETCH"]
    assert "vggish.pth" in w["message"]


def test_no_new_files_no_network_fetch(wrapper, monkeypatch, tmp_path):
    run, _ = fake_fadtk()
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert "NETWORK_FETCH" not in codes(wrapper.run(request(tmp_path, inf=False)))


def test_per_clip_maps_paths_back_to_clip_ids(wrapper, monkeypatch, tmp_path):
    run, calls = fake_fadtk()
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    resp = wrapper.run(request(tmp_path, inf=False, per_clip=True))
    assert calls[-1][-1] == "--indiv"
    assert sorted((c["clip_id"], c["scores"]["fad_indiv"]) for c in resp["clip_scores"]) == [("a", 2.5), ("b", 1.5)]


def test_cpu_request_hides_the_gpus(wrapper, monkeypatch, tmp_path):
    run, _ = fake_fadtk()
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    wrapper.run(request(tmp_path, inf=False))
    import os

    assert os.environ["CUDA_VISIBLE_DEVICES"] == ""
