"""The runtime shim that runs inside plugin environments (spec sections 4.4 and 9.1)."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap

import pytest

from musegauge import config, schemas

SHIM = config.RUNTIME_DIR / "musegauge_runtime" / "run.py"


def test_shim_parses_with_python_3_9_grammar():
    for path in (SHIM, SHIM.parent / "__init__.py"):
        ast.parse(path.read_text(), feature_version=(3, 9))


def test_shim_imports_only_the_standard_library():
    tree = ast.parse(SHIM.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    assert names <= set(sys.stdlib_module_names) | {"__future__"}


def make_plugin(tmp_path, body):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "wrapper.py").write_text(textwrap.dedent(body))
    return plugin


def run_shim(tmp_path, plugin, *args):
    env = {"PYTHONPATH": str(config.RUNTIME_DIR), "PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1"}
    return subprocess.run([sys.executable, "-m", "musegauge_runtime.run", "--plugin-dir", str(plugin), *args],
                          env=env, capture_output=True, text=True, cwd=tmp_path, check=False)


def run_normal(tmp_path, body, request=None):
    plugin = make_plugin(tmp_path, body)
    req = tmp_path / "request.json"
    req.write_text(json.dumps(request or {"metric_id": "fake.x@1", "options": {}}))
    proc = run_shim(tmp_path, plugin, "--request", str(req), "--response", str(tmp_path / "response.json"))
    resp = json.loads((tmp_path / "response.json").read_text())
    schemas.check(resp, "response")
    return proc, resp


def test_normal_mode_fills_the_common_fields(tmp_path):
    proc, resp = run_normal(tmp_path, """
        def run(request):
            return {"scores": [{"name": "s", "value": 2.5, "kind": "set"}], "env": {"device": "cpu"}}
    """)
    assert proc.returncode == 0
    assert resp["status"] == "ok" and resp["metric_id"] == "fake.x@1" and resp["schema"] == 1
    assert resp["scores"] == [{"name": "s", "value": 2.5, "kind": "set"}]
    assert resp["timing_s"] >= 0 and resp["error"] is None and resp["clip_scores"] == []


def test_non_finite_scores_become_null_with_nan_score(tmp_path):
    _, resp = run_normal(tmp_path, """
        def run(request):
            return {"scores": [{"name": "s", "value": float("nan"), "kind": "set"}],
                    "clip_scores": [{"clip_id": "a", "scores": {"x": float("inf"), "y": 1.0}}]}
    """)
    assert resp["scores"][0]["value"] is None
    assert resp["clip_scores"][0]["scores"] == {"x": None, "y": 1.0}
    (warning,) = resp["warnings"]
    assert warning["code"] == "NAN_SCORE" and "s" in warning["message"] and "a:x" in warning["message"]
    assert "NaN" not in (tmp_path / "response.json").read_text()


def test_wrapper_exception_becomes_an_error_response(tmp_path):
    proc, resp = run_normal(tmp_path, """
        def run(request):
            raise RuntimeError("boom from wrapper")
    """)
    assert proc.returncode == 1
    assert resp["status"] == "error" and resp["scores"] == [] and resp["clip_scores"] == []
    assert resp["error"]["type"] == "RuntimeError" and resp["error"]["message"] == "boom from wrapper"
    assert "boom from wrapper" in resp["error"]["traceback_tail"]
    assert len(resp["error"]["traceback_tail"].splitlines()) <= 40


def test_error_status_clears_scores(tmp_path):
    _, resp = run_normal(tmp_path, """
        def run(request):
            return {"status": "error", "scores": [{"name": "s", "value": 1.0, "kind": "set"}],
                    "error": {"type": "X", "message": "m", "traceback_tail": None}}
    """)
    assert resp["status"] == "error" and resp["scores"] == []


def test_unserialisable_response_is_reported(tmp_path):
    _, resp = run_normal(tmp_path, """
        def run(request):
            return {"env": {"thing": object()}}
    """)
    assert resp["status"] == "error" and resp["error"]["type"] == "InvalidResponse"


def test_missing_wrapper_is_an_error_response(tmp_path):
    plugin = tmp_path / "empty_plugin"
    plugin.mkdir()
    (tmp_path / "request.json").write_text(json.dumps({"metric_id": "fake.x@1"}))
    proc = run_shim(tmp_path, plugin, "--request", str(tmp_path / "request.json"),
                    "--response", str(tmp_path / "response.json"))
    resp = json.loads((tmp_path / "response.json").read_text())
    assert proc.returncode == 1 and resp["status"] == "error"


def test_prefetch_mode_passes_the_options(tmp_path):
    plugin = make_plugin(tmp_path, """
        def run(request):
            return {}

        def prefetch(metric_id, options):
            return {"downloaded": [metric_id + ":" + options["model"]], "notes": ["n"]}
    """)
    (tmp_path / "options.json").write_text(json.dumps({"model": "vggish"}))
    proc = run_shim(tmp_path, plugin, "--prefetch", "fake.x@1", "--options", str(tmp_path / "options.json"),
                    "--response", str(tmp_path / "prefetch.json"))
    out = json.loads((tmp_path / "prefetch.json").read_text())
    schemas.check(out, "prefetch")
    assert proc.returncode == 0
    assert out["downloaded"] == ["fake.x@1:vggish"] and out["notes"] == ["n"] and out["status"] == "ok"


def test_prefetch_error_is_reported(tmp_path):
    plugin = make_plugin(tmp_path, """
        def prefetch(metric_id, options):
            raise OSError("no network")
    """)
    proc = run_shim(tmp_path, plugin, "--prefetch", "fake.x@1", "--response", str(tmp_path / "p.json"))
    out = json.loads((tmp_path / "p.json").read_text())
    schemas.check(out, "prefetch")
    assert proc.returncode == 1 and out["status"] == "error" and out["error"]["type"] == "OSError"


@pytest.mark.parametrize("args", [[], ["--request", "r.json"], ["--request", "r", "--prefetch", "m", "--response", "x"]])
def test_shim_usage_errors(tmp_path, args):
    proc = run_shim(tmp_path, tmp_path, *args)
    assert proc.returncode == 2
