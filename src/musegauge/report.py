"""The report card, report.md (spec section 10.3).

render() is a pure function of results.json. `musegauge report results.json` prints the
same text that a run writes to report.md. Numbers are rounded to 3 decimals here only;
results.json keeps full precision.
"""

from __future__ import annotations

import os
from pathlib import Path

CI_SENTENCE = (
    "The interval describes the spread caused by which clips were sampled. It does not cover "
    "model randomness, different seeds, or different prompts."
)


def fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def hms(seconds: float) -> str:
    total = round(seconds)
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _reference_line(ref: dict) -> str:
    if ref["kind"] == "bundled":
        return f"bundled {ref['name']}"
    if ref["kind"] == "dir":
        return f"folder: {ref['n_clips']} files, hash {ref['ref_hash'][:8]}"
    return "none"


def _score_rows(metric: dict) -> list[str]:
    mid, status = metric["metric_id"], metric["status"]
    if status != "ok" or not metric["scores"]:
        return [f"| {mid} | — | — | — | — | {status} |"]
    rows = []
    for s in metric["scores"]:
        if s["kind"] == "clip":
            mean = f"{fmt(s['value'])} ± {fmt(s['std'])}" if s["std"] is not None else fmt(s["value"])
        else:
            mean = fmt(s["value"])
        ci = f"[{fmt(s['ci']['low'])}, {fmt(s['ci']['high'])}]" if s["ci"] else "—"
        n = "—" if s["n"] is None else str(s["n"])
        rows.append(f"| {mid} | {s['name']} | {mean} | {ci} | {n} | {status} |")
    return rows


def _warning_lines(results: dict) -> list[str]:
    lines = []
    for w in results["warnings"]:
        lines.append(f"- `{w['code']}` (run): {w['message']}")
    for m in results["metrics"]:
        for w in m["warnings"]:
            lines.append(f"- `{w['code']}` (metric {m['metric_id']}): {w['message']}")
        if m["status"] == "error" and m["error"]:
            lines.append(f"- error (metric {m['metric_id']}): {m['error']['type']}: {m['error']['message']}")
    return lines or ["- none"]


def _remote_code_lines(results: dict) -> list[str]:
    """Code that a plugin downloaded at run time and that is not pinned (A7)."""
    return [
        f"- `{m['metric_id']}`: {m['env']['remote_code']}"
        for m in results["metrics"]
        if m["env"] and m["env"].get("remote_code")
    ]


def render(results: dict) -> str:
    run, gen, tool = results["run"], results["generated"], results["tool"]
    rates = ", ".join(f"{int(r)} Hz" for r in gen["sample_rates_hz"])
    d = gen["duration_s"]
    out = [
        "# Evaluation report card",
        "",
        (
            f"Run `{run['run_id']}` on {run['started_utc'][:10]}. Tool: musegauge {tool['version']}. "
            f"Suite: {results['suite'] or 'custom'}."
        ),
        "",
        "## Data",
        (
            f"- Generated clips: {gen['n_clips']} scored, {gen['n_skipped']} skipped. "
            f"Total {hms(gen['total_duration_s'])}."
        ),
        (
            f"- Sample rates: {rates}. Duration min / median / max: "
            f"{fmt(d['min'])} / {fmt(d['median'])} / {fmt(d['max'])} s."
        ),
        f"- Prompts: {gen['n_with_prompt']} of {gen['n_clips']}.",
        f"- Reference: {_reference_line(results['reference'])}.",
        "",
        "## Scores",
        "| Metric | Score | Mean ± std | 95% CI | n | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for m in results["metrics"]:
        out += _score_rows(m)
    out += ["", "## What each score is"]
    for m in results["metrics"]:
        out += ["", f"`{m['metric_id']}`: {m['definition']}"]
    out += [
        "",
        "## Software",
        "| Metric | Upstream | Version | Device | Seed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in results["metrics"]:
        up, env = m["upstream"] or {}, m["env"] or {}
        out.append(
            f"| {m['metric_id']} | {up.get('package', '—')} | {up.get('version') or '—'} | "
            f"{env.get('device', '—')} | {run['seed']} |"
        )
    out.append("")
    seen = set()
    for m in results["metrics"]:
        env = m["env"] or {}
        if not env.get("env_id") or env["env_id"] in seen:
            continue
        seen.add(env["env_id"])
        lock = (env.get("lock_sha256") or "none")[:12]
        threads = f", torch threads {env['torch_threads']}" if env.get("torch_threads") else ""
        out.append(
            f"- `{env['env_id']}`: Python {env.get('python', '—')}, torch {env.get('torch', '—')}"
            f"{threads}, lock {lock}"
        )
    out += [
        f"- Core: Python {tool['python']}, uv {tool['uv_version'] or '—'}, platform {tool['platform']}.",
        f"- CPU threads per plugin: {run['threads'] if run.get('threads') else 'not limited (upstream default)'}.",
        *_remote_code_lines(results),
        "",
        f"Reproducible: {'yes' if run['reproducible'] else 'no'}",
        "",
        "## Warnings",
        *_warning_lines(results),
        "",
        "## Notes for your paper",
        (
            "- Report the tool version, the suite id and version, the metric ids, the reference "
            "set, the number and length of clips, and the seed."
        ),
        "- The interval covers clip sampling only. It does not cover model or seed variation.",
        f"- {CI_SENTENCE}",
        (
            "- Scores are comparable only with runs that use the same metric ids, reference set "
            "and clip length. Do not compare with numbers printed in other papers unless their "
            "setup is identical."
        ),
        "",
    ]
    return "\n".join(out)


def write_report(results: dict, out: Path) -> Path:
    path = out / "report.md"
    tmp = out / f".report.md.tmp{os.getpid()}"
    tmp.write_text(render(results), encoding="utf-8")
    os.replace(tmp, path)
    return path
