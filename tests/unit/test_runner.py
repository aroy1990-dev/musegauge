"""Preflight, requests, response checks and process control (spec sections 4.4, 4.5, 7.1)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time

import pytest
import yaml
from conftest import pid_running

from musegauge import runner, schemas
from musegauge.clips import probe_audio, read_folder
from musegauge.config import RunConfig
from musegauge.errors import FatalEnvironmentError, InputError, LicenceRefusal
from musegauge.registry import Registry


def custom_registry(tmp_path, fake_plugin_root, edits):
    """A registry with modified copies of fake plugins. edits: {new_id: (source, change)}."""
    root = tmp_path / "plugins"
    for new_id, (source, change) in edits.items():
        dst = shutil.copytree(fake_plugin_root / source, root / new_id)
        data = yaml.safe_load((dst / "manifest.yaml").read_text())
        data["plugin_id"] = new_id
        data["family"] = new_id.replace("_", "")
        for m in data["metrics"]:
            m["id"] = f"{data['family']}.{m['id'].split('.', 1)[1]}"
        change(data)
        (dst / "manifest.yaml").write_text(yaml.safe_dump(data))
    return Registry.discover([root])


@pytest.fixture
def ok_clips(fixtures):
    ok, _ = probe_audio(read_folder(fixtures["gen_small"]).clips)
    return ok


def cfg(tmp_path, **kw):
    return RunConfig(home=tmp_path / "home", **kw)


def test_reference_needed_but_missing(tmp_path, fake_plugin_root, ok_clips):
    reg = Registry.discover([fake_plugin_root])
    with pytest.raises(InputError, match="needs reference audio"):
        runner.preflight({"fake_set": ["fake.set@1"]}, reg, cfg(tmp_path), ok_clips, None)


def test_reference_mode_not_accepted(tmp_path, fake_plugin_root, ok_clips):
    reg = Registry.discover([fake_plugin_root])
    with pytest.raises(InputError, match="cannot use a bundled reference"):
        runner.preflight({"fake_set": ["fake.set@1"]}, reg, cfg(tmp_path, reference="bundled:fma_pop"), ok_clips, None)


def test_bundled_name_must_be_listed(tmp_path, fake_plugin_root, ok_clips):
    def allow_bundled(d):
        d["reference_modes"] = ["dir", "bundled"]
        d["bundled_references"] = ["fma_pop"]

    reg = custom_registry(tmp_path, fake_plugin_root, {"bset": ("fake_set", allow_bundled)})
    plan = {"bset": ["bset.set@1"]}
    pre = runner.preflight(plan, reg, cfg(tmp_path, reference="bundled:fma_pop"), ok_clips, None)
    assert pre.reference.kind == "bundled" and pre.refset is None
    with pytest.raises(InputError, match="no bundled reference named 'other'"):
        runner.preflight(plan, reg, cfg(tmp_path, reference="bundled:other"), ok_clips, None)


def test_folder_reference_is_scanned(tmp_path, fake_plugin_root, ok_clips, fixtures):
    reg = Registry.discover([fake_plugin_root])
    c = cfg(tmp_path, reference=str(fixtures["ref_small"]))
    pre = runner.preflight({"fake_set": ["fake.set@1"]}, reg, c, ok_clips, None)
    assert len(pre.refset.files) == 12 and len(pre.refset.ref_hash) == 64


def test_metric_that_needs_prompts_is_skipped_with_no_prompts(tmp_path, fake_plugin_root, ok_clips):
    reg = custom_registry(tmp_path, fake_plugin_root, {
        "pclip": ("fake_clip", lambda d: d["needs"].update(prompts=True))})
    pre = runner.preflight({"pclip": ["pclip.clip@1"]}, reg, cfg(tmp_path), ok_clips, None)
    assert pre.skips["pclip.clip@1"]["code"] == "NO_PROMPTS"
    ok_clips[0].prompt = "a prompt"
    assert runner.preflight({"pclip": ["pclip.clip@1"]}, reg, cfg(tmp_path), ok_clips, None).skips == {}


def test_missing_system_tool_is_exit_4(tmp_path, fake_plugin_root, ok_clips, monkeypatch):
    reg = custom_registry(tmp_path, fake_plugin_root, {
        "tclip": ("fake_clip", lambda d: d["system_tools"].update(required=["sox"]))})
    monkeypatch.setenv("PATH", str(tmp_path / "empty_bin"))
    monkeypatch.delenv("SOX_PATH", raising=False)
    with pytest.raises(FatalEnvironmentError, match="sox not found") as info:
        runner.preflight({"tclip": ["tclip.clip@1"]}, reg, cfg(tmp_path), ok_clips, None)
    assert info.value.exit_code == 4
    fake_sox = tmp_path / "bin" / "my-sox"
    fake_sox.parent.mkdir()
    fake_sox.write_text("#!/bin/sh\n")
    fake_sox.chmod(0o755)
    monkeypatch.setenv("SOX_PATH", str(fake_sox))
    runner.preflight({"tclip": ["tclip.clip@1"]}, reg, cfg(tmp_path), ok_clips, None)


def test_commercial_refuses_unknown_licences(tmp_path, fake_plugin_root, ok_clips):
    reg = Registry.discover([fake_plugin_root])
    with pytest.raises(LicenceRefusal) as info:
        runner.preflight({"fake_clip": ["fake.clip@1"]}, reg, cfg(tmp_path, commercial=True), ok_clips, None)
    assert info.value.exit_code == 6
    reg2 = custom_registry(tmp_path, fake_plugin_root, {
        "yclip": ("fake_clip", lambda d: d["metrics"][0]["licence"].update(commercial_ok="yes"))})
    runner.preflight({"yclip": ["yclip.clip@1"]}, reg2, cfg(tmp_path, commercial=True), ok_clips, None)


def test_build_request_is_schema_valid(tmp_path, fake_plugin_root, ok_clips):
    reg = Registry.discover([fake_plugin_root])
    plugin = reg.plugins["fake_badclip"]
    pre = runner.Preflight({}, runner.Reference("none"), None)
    stage = runner.stage_audio(plugin, ok_clips, pre, cfg(tmp_path), tmp_path / "work" / "run")
    req = runner.build_request("fake.badclip@1", plugin, stage, cfg(tmp_path, per_clip=True), "RUN")
    schemas.check(req, "request")
    assert req["options"] == {"bad_clip": "gen_003", "per_clip": True}
    assert req["reference"] == {"kind": "none", "name": None, "dir": None, "n_clips": None}
    assert req["generated"]["dir"] == str(tmp_path / "work" / "run" / "fake_badclip" / "gen")


def write(path, obj):
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return path


def good_response(**kw):
    resp = {"schema": 1, "status": "ok", "metric_id": "fake.clip@1", "scores": [], "clip_scores": [],
            "clips_failed": [], "upstream": None, "env": {}, "warnings": [], "timing_s": 0.1, "error": None}
    resp.update(kw)
    return resp


REQUEST = {"metric_id": "fake.clip@1", "generated": {"clips": [{"clip_id": "a"}]}}


def test_read_response_checks(tmp_path):
    resp, err = runner.read_response(write(tmp_path / "r.json", good_response()), REQUEST)
    assert err is None and resp["status"] == "ok"
    _, err = runner.read_response(tmp_path / "missing.json", REQUEST)
    assert err["type"] == "NoResponse"
    _, err = runner.read_response(write(tmp_path / "r.json", good_response(metric_id="fake.other@1")), REQUEST)
    assert err["type"] == "InvalidResponse" and "not fake.clip@1" in err["message"]
    _, err = runner.read_response(write(tmp_path / "r.json", good_response(
        clip_scores=[{"clip_id": "zz", "scores": {"x": 1.0}}])), REQUEST)
    assert "unknown clip ids: zz" in err["message"]
    _, err = runner.read_response(write(tmp_path / "r.json", '{"schema": 1, "value": NaN}'), REQUEST)
    assert err["type"] == "InvalidResponse"
    _, err = runner.read_response(write(tmp_path / "r.json", {"schema": 1}), REQUEST)
    assert err["type"] == "InvalidResponse"


def test_kill_group_stops_the_process_and_its_children(tmp_path):
    pids_file = tmp_path / "pids"
    code = (
        "import subprocess, sys, time, os; "
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)']); "
        f"open({str(pids_file)!r}, 'w').write(f'{{os.getpid()}} {{c.pid}}'); time.sleep(600)"
    )
    proc = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    deadline = time.monotonic() + 30
    while not pids_file.exists() or len(pids_file.read_text().split()) < 2:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    pids = [int(p) for p in pids_file.read_text().split()]
    runner.kill_group(proc)
    time.sleep(0.2)
    assert proc.returncode is not None
    assert not any(pid_running(p) for p in pids)


TORCH_HUB_HTTP_ERROR = """Traceback (most recent call last):
  File "/env/lib/python3.11/site-packages/torch/hub.py", line 199, in _parse_repo_info
    with urlopen(f"https://github.com/{repo_owner}/{repo_name}/tree/main/"):
  File "/usr/lib/python3.11/urllib/request.py", line 643, in http_error_default
    raise HTTPError(req.full_url, code, msg, hdrs, fp)
urllib.error.HTTPError: HTTP Error 429: Too Many Requests"""


def test_torch_hub_http_error_is_detected():
    assert runner.looks_like_torch_hub_http_error(TORCH_HUB_HTTP_ERROR)
    assert not runner.looks_like_torch_hub_http_error("urllib.error.HTTPError: HTTP Error 500 (in requests)")
    assert not runner.looks_like_torch_hub_http_error('File ".../torch/hub.py", line 5\nValueError: x')


def test_network_error_classification_keeps_the_original():
    err = {"type": "RuntimeError", "message": "fadtk exited with code 1", "traceback_tail": None}
    out = runner.classify_network_error(err, log_tail=TORCH_HUB_HTTP_ERROR)
    assert out["type"] == "NETWORK_ERROR"
    assert "musegauge setup --fetch-weights" in out["message"] and "--no-fetch" in out["message"]
    assert "Original error: RuntimeError: fadtk exited with code 1" in out["message"]
    assert runner.classify_network_error(err, log_tail="something else") == err

