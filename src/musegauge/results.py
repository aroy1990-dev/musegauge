"""Aggregate plugin responses into results.json (spec sections 6.5, 6.6 and 7.3)."""

from __future__ import annotations

import copy
import csv
import json
import os
import platform
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from musegauge import __version__, schemas, stats
from musegauge import warnings_ as W
from musegauge.errors import EXIT_ALL_FAILED, EXIT_OK, EXIT_PARTIAL

if TYPE_CHECKING:
    from musegauge.clips import Clip
    from musegauge.envs import Env
    from musegauge.registry import Plugin


@dataclass
class Outcome:
    """What happened to one metric in one run."""

    metric_id: str
    plugin: Plugin
    status: str  # ok, error or skipped
    response: dict | None = None
    env: Env | None = None
    error: dict | None = None
    warnings: list[dict] = field(default_factory=list)


def tool_block(uv_ver: str | None, platform_tag: str) -> dict:
    return {
        "name": "musegauge",
        "version": __version__,
        "git_commit": None,
        "uv_version": uv_ver,
        "python": platform.python_version(),
        "platform": platform_tag,
    }


def generated_block(ok: list[Clip], skipped: list[dict], manifest_sha256: str) -> dict:
    durations = [c.duration_s for c in ok]
    rates: dict[str, int] = {}
    for c in ok:
        rates[str(c.sample_rate_hz)] = rates.get(str(c.sample_rate_hz), 0) + 1
    return {
        "n_clips": len(ok),
        "n_skipped": len(skipped),
        "skipped": skipped,
        "n_with_prompt": sum(1 for c in ok if c.prompt),
        "total_duration_s": float(sum(durations)),
        "sample_rates_hz": dict(sorted(rates.items(), key=lambda kv: int(kv[0]))),
        "duration_s": {
            "min": float(min(durations)),
            "median": float(statistics.median(durations)),
            "max": float(max(durations)),
        },
        "manifest_sha256": manifest_sha256,
        "extra": {c.clip_id: c.extra for c in ok if c.extra},
    }


def write_per_clip_csv(out: Path, metric_id: str, clip_scores: list[dict], order: list[str]) -> str:
    """per_clip/<metric_id>.csv with columns clip_id and each score name. Returns its relative path."""
    names: list[str] = []
    for row in clip_scores:
        for name in row["scores"]:
            if name not in names:
                names.append(name)
    rank = {cid: i for i, cid in enumerate(order)}
    rows = sorted(clip_scores, key=lambda r: rank.get(r["clip_id"], len(rank)))
    rel = f"per_clip/{metric_id}.csv"
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["clip_id", *names])
        for row in rows:
            values = [row["scores"].get(n) for n in names]
            writer.writerow([row["clip_id"], *["" if v is None else repr(float(v)) for v in values]])
    return rel


def metric_entry(
    outcome: Outcome, seed: int, n_resamples: int, out: Path, order: list[str], n_clips: int | None = None
) -> dict:
    """One results entry. n_clips is the number of scored generated clips (for FEW_CLIPS)."""
    plugin = outcome.plugin
    spec = plugin.metrics[outcome.metric_id]
    entry = {
        "metric_id": outcome.metric_id,
        "plugin_id": plugin.plugin_id,
        "kind": plugin.kind,
        "status": outcome.status,
        "primary": spec["primary"],
        "definition": spec["definition"],
        "scores": [],
        "clips_failed": [],
        "per_clip_file": None,
        "upstream": None,
        "env": None,
        "licence": copy.deepcopy(spec["licence"]),
        "warnings": list(outcome.warnings),
        "error": outcome.error,
        "timing_s": None,
    }
    licence_warning = W.licence(outcome.metric_id, spec["licence"]["commercial_ok"])
    if licence_warning:
        entry["warnings"].insert(0, licence_warning)
    if outcome.env is not None:
        entry["env"] = {"env_id": outcome.env.env_id, "lock_sha256": outcome.env.lock_sha256}
    resp = outcome.response
    if resp is None:
        return entry
    if plugin.manifest["trust_remote_code"]:
        entry["warnings"].append(W.trust_remote_code(outcome.metric_id))
    entry["upstream"] = resp["upstream"]
    entry["timing_s"] = resp["timing_s"]
    entry["clips_failed"] = resp["clips_failed"]
    entry["env"] = {**(entry["env"] or {}), **resp["env"]}
    for w in resp["warnings"]:
        entry["warnings"].append(W.make(w["code"], "metric", w["message"], outcome.metric_id))
    if resp["status"] != "ok":
        entry["error"] = resp["error"]
        return entry
    entry["scores"] = [stats.set_score_entry(s) for s in resp["scores"]]
    if resp["clip_scores"]:
        entry["per_clip_file"] = write_per_clip_csv(out, outcome.metric_id, resp["clip_scores"], order)
        if plugin.kind == "clip":
            entry["scores"] += stats.summarize_clip_scores(
                resp["clip_scores"], outcome.metric_id, seed, n_resamples
            )
    for extra in (W.few_clips(outcome.metric_id, plugin.kind, n_clips if n_clips is not None else len(order)),
                  W.kad_negative(outcome.metric_id, entry["scores"])):
        if extra:
            entry["warnings"].append(extra)
    return entry


def exit_code(results: dict) -> int:
    """0 if no metric failed; 5 if some failed and none succeeded; 10 if some of each.

    A skipped metric (for example NO_PROMPTS) counts as neither.
    """
    statuses = [m["status"] for m in results["metrics"]]
    if "error" not in statuses:
        return EXIT_OK
    return EXIT_PARTIAL if "ok" in statuses else EXIT_ALL_FAILED


def write_results(results: dict, out: Path) -> Path:
    """Check results against its schema, then write results.json atomically."""
    schemas.check(results, "results")
    path = out / "results.json"
    tmp = out / f".results.json.tmp{os.getpid()}"
    tmp.write_text(json.dumps(results, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path
