"""Results aggregation, per-clip files and exit codes (spec sections 6.5, 6.6, 7.3)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from musegauge import results
from musegauge.envs import Env
from musegauge.errors import SchemaError
from musegauge.registry import load_plugin
from musegauge.results import Outcome

DATA = Path(__file__).resolve().parents[1] / "data"


def statuses(*values):
    return {"metrics": [{"status": v} for v in values]}


@pytest.mark.parametrize("values,code", [
    (["ok"], 0), (["ok", "ok"], 0), (["ok", "skipped"], 0), (["skipped"], 0),
    (["ok", "error"], 10), (["error", "ok", "skipped"], 10),
    (["error"], 5), (["error", "error"], 5), (["error", "skipped"], 5),
])
def test_exit_code(values, code):
    assert results.exit_code(statuses(*values)) == code


def response(**kw):
    base = {"schema": 1, "status": "ok", "metric_id": "fake.clip@1", "scores": [], "clip_scores": [],
            "clips_failed": [], "upstream": {"package": "p", "version": "1", "invocation": "i"},
            "env": {"python": "3.12.7", "device": "cpu"}, "warnings": [], "timing_s": 1.0, "error": None}
    base.update(kw)
    return base


@pytest.fixture
def clip_plugin(fake_plugin_root):
    return load_plugin(fake_plugin_root / "fake_clip")


ENV = Env("fake_clip-12345678", Path("/e"), Path("/e/bin/python"), "a" * 64, True)


def test_clip_metric_entry_summarizes_and_writes_per_clip(tmp_path, clip_plugin):
    resp = response(
        clip_scores=[{"clip_id": "b", "scores": {"amplitude": 0.2}}, {"clip_id": "a", "scores": {"amplitude": None}}],
        clips_failed=[{"clip_id": "c", "reason": "bad"}],
        warnings=[{"code": "NAN_SCORE", "message": "m"}],
    )
    entry = results.metric_entry(Outcome("fake.clip@1", clip_plugin, "ok", resp, ENV), 0, 100, tmp_path, ["a", "b", "c"])
    assert entry["kind"] == "clip" and entry["status"] == "ok"
    assert entry["definition"] == clip_plugin.metrics["fake.clip@1"]["definition"]
    assert entry["licence"] == clip_plugin.metrics["fake.clip@1"]["licence"]
    (score,) = entry["scores"]
    assert score["name"] == "amplitude" and score["n"] == 1 and score["ci"] is None
    assert entry["clips_failed"] == [{"clip_id": "c", "reason": "bad"}]
    assert entry["env"] == {"env_id": "fake_clip-12345678", "lock_sha256": "a" * 64, "python": "3.12.7", "device": "cpu"}
    assert [w["code"] for w in entry["warnings"]] == ["UNKNOWN_LICENCE", "NAN_SCORE"]
    assert entry["warnings"][1] == {"code": "NAN_SCORE", "scope": "metric", "message": "m", "metric_id": "fake.clip@1"}
    assert entry["per_clip_file"] == "per_clip/fake.clip@1.csv"
    with open(tmp_path / entry["per_clip_file"], newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows == [["clip_id", "amplitude"], ["a", ""], ["b", "0.2"]]


def test_set_metric_per_clip_scores_are_written_but_not_averaged(tmp_path, fake_plugin_root):
    plugin = load_plugin(fake_plugin_root / "fake_set")
    resp = response(metric_id="fake.set@1", scores=[{"name": "n_files", "value": 12.0, "kind": "set"}],
                    clip_scores=[{"clip_id": "a", "scores": {"indiv": 1.0}}])
    entry = results.metric_entry(Outcome("fake.set@1", plugin, "ok", resp, ENV), 0, 100, tmp_path, ["a"])
    assert [s["name"] for s in entry["scores"]] == ["n_files"]
    assert entry["scores"][0]["ci_reason"] == "set-level metric, no confidence interval in 0.1"
    assert (tmp_path / "per_clip" / "fake.set@1.csv").is_file()


def test_trust_remote_code_warning_comes_from_the_manifest(tmp_path, clip_plugin):
    resp = response(clip_scores=[{"clip_id": "a", "scores": {"amplitude": 0.2}}])
    plain = results.metric_entry(Outcome("fake.clip@1", clip_plugin, "ok", resp, ENV), 0, 10, tmp_path, ["a"])
    assert "TRUST_REMOTE_CODE" not in [w["code"] for w in plain["warnings"]]
    clip_plugin.manifest["trust_remote_code"] = True
    flagged = results.metric_entry(Outcome("fake.clip@1", clip_plugin, "ok", resp, ENV), 0, 10, tmp_path, ["a"])
    (w,) = [w for w in flagged["warnings"] if w["code"] == "TRUST_REMOTE_CODE"]
    assert w["scope"] == "metric" and w["metric_id"] == "fake.clip@1"


def test_error_and_skipped_entries(tmp_path, clip_plugin):
    err = {"type": "EnvError", "message": "m", "traceback_tail": "t"}
    entry = results.metric_entry(Outcome("fake.clip@1", clip_plugin, "error", error=err), 0, 10, tmp_path, [])
    assert entry["status"] == "error" and entry["error"] == err and entry["scores"] == [] and entry["env"] is None
    warning = {"code": "NO_PROMPTS", "scope": "metric", "message": "m", "metric_id": "fake.clip@1"}
    entry = results.metric_entry(Outcome("fake.clip@1", clip_plugin, "skipped", warnings=[warning]), 0, 10, tmp_path, [])
    assert entry["status"] == "skipped" and entry["warnings"][1:] == [warning]
    assert entry["warnings"][0]["code"] == "UNKNOWN_LICENCE"  # licence warnings apply to every selected metric


def test_error_response_keeps_upstream_error(tmp_path, clip_plugin):
    err = {"type": "RuntimeError", "message": "x", "traceback_tail": None}
    resp = response(status="error", error=err)
    entry = results.metric_entry(Outcome("fake.clip@1", clip_plugin, "error", resp, ENV, err), 0, 10, tmp_path, [])
    assert entry["error"] == err and entry["scores"] == [] and entry["per_clip_file"] is None


def test_write_results_checks_schema_and_rejects_nan(tmp_path):
    doc = json.loads((DATA / "results.example.json").read_text())
    path = results.write_results(doc, tmp_path)
    assert json.loads(path.read_text()) == doc
    doc["metrics"][0]["scores"][0]["value"] = float("nan")
    with pytest.raises(ValueError):
        results.write_results(doc, tmp_path)
    doc["metrics"][0]["scores"][0]["value"] = 1.0
    doc["run"].pop("seed")
    with pytest.raises(SchemaError):
        results.write_results(doc, tmp_path)
