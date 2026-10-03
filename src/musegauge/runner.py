"""The core loop (spec section 4.5) and starting plugin processes (section 4.4)."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from musegauge import config, schemas
from musegauge import warnings_ as W
from musegauge.clips import (
    Clip,
    ClipSet,
    probe_audio,
    read_folder,
    read_manifest,
    strict_json_loads,
)
from musegauge.config import Reference, RunConfig
from musegauge.envs import EnvBackend, UvBackend, find_uv, uv_version
from musegauge.errors import (
    EnvError,
    FatalEnvironmentError,
    InputError,
    LicenceRefusal,
    NoLockError,
    SchemaError,
    UsageError,
)
from musegauge.registry import Plugin, Registry, Suite
from musegauge.report import write_report
from musegauge.results import (
    Outcome,
    exit_code,
    generated_block,
    metric_entry,
    tool_block,
    write_results,
)
from musegauge.staging import (
    ReferenceSet,
    file_hashes,
    safe_rmtree,
    scan_reference,
    stage_generated,
    stage_reference,
)

KILL_GRACE_S = 5.0
LOG_TAIL_LINES = 80
NETWORK_ERROR_ADVICE = (
    "The plugin failed and its output shows an HTTP error raised in torch.hub (torch/hub.py). "
    "Retry the run, or run `musegauge setup --fetch-weights` once and then use --no-fetch."
)


def looks_like_torch_hub_http_error(text: str) -> bool:
    """True if the text shows an HTTP error raised inside torch.hub. Nothing else is guessed."""
    return "torch/hub.py" in text and ("HTTPError" in text or "HTTP Error" in text)


def classify_network_error(error: dict, log_tail: str) -> dict:
    """Turn an error into NETWORK_ERROR when the error text or the log tail shows a torch.hub
    HTTP error (GATE 2 item 3b). The original type and message are kept in the message."""
    text = "\n".join([error.get("message") or "", error.get("traceback_tail") or "", log_tail])
    if error.get("type") == "NETWORK_ERROR" or not looks_like_torch_hub_http_error(text):
        return error
    return {
        "type": "NETWORK_ERROR",
        "message": f"{NETWORK_ERROR_ADVICE} Original error: {error.get('type')}: {error.get('message')}",
        "traceback_tail": error.get("traceback_tail"),
    }


def say(msg: str) -> None:
    """Progress messages go to standard error."""
    print(f"musegauge: {msg}", file=sys.stderr, flush=True)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(3)


@dataclass
class Preflight:
    skips: dict[str, dict]  # metric id -> warning that explains the skip
    reference: Reference
    refset: ReferenceSet | None


@dataclass
class Stage:
    work_dir: Path
    gen_dir: Path
    clips: list[dict]
    reference: dict


def check_usage(cfg: RunConfig) -> None:
    """Command line combinations that are wrong before any file is read (exit code 2)."""
    if bool(cfg.generated) == bool(cfg.manifest):
        raise UsageError("give exactly one of --generated DIR and --manifest FILE")
    if cfg.suite and cfg.metrics:
        raise UsageError("--suite and --metrics cannot be combined")
    if cfg.manifest and cfg.prompts:
        raise UsageError("--prompts is for folder mode (--generated); put prompts in the clips file")


def read_clips(cfg: RunConfig) -> ClipSet:
    if cfg.manifest:
        return read_manifest(cfg.manifest)
    clipset = read_folder(cfg.generated, cfg.prompts)
    if clipset.unknown_prompt_ids:
        say(
            f"{len(clipset.unknown_prompt_ids)} prompt(s) name a clip_id with no audio file; "
            "they are ignored"
        )
    return clipset


def resolve_metrics(cfg: RunConfig, registry: Registry) -> tuple[list[str], Suite | None]:
    suite = cfg.suite or (None if cfg.metrics else config.DEFAULT_SUITE)
    return registry.resolve_metrics(suite, cfg.metrics)


def tool_found(name: str) -> bool:
    if name == "sox" and os.environ.get("SOX_PATH"):
        return shutil.which(os.environ["SOX_PATH"]) is not None
    return shutil.which(name) is not None


def preflight(
    plan: dict[str, list[str]],
    registry: Registry,
    cfg: RunConfig,
    ok: list[Clip],
    suite: Suite | None,
) -> Preflight:
    """Checks that run before any environment is built (section 7.1)."""
    reference = Reference.parse(cfg.reference or (suite.default_reference if suite else None))
    skips: dict[str, dict] = {}
    has_prompts = any(c.prompt for c in ok)
    for plugin_id, mids in plan.items():
        plugin = registry.plugins[plugin_id]
        if plugin.needs_reference:
            if reference.kind == "none":
                raise InputError(f"metric {mids[0]} needs reference audio; give --reference DIR")
            if reference.kind not in plugin.manifest["reference_modes"]:
                raise InputError(
                    f"metric {mids[0]} cannot use a {reference.kind} reference "
                    f"({reference.describe()}); it accepts: "
                    f"{', '.join(plugin.manifest['reference_modes']) or 'none'}"
                )
            if reference.kind == "bundled" and reference.name not in plugin.manifest["bundled_references"]:
                raise InputError(
                    f"metric {mids[0]} has no bundled reference named {reference.name!r}"
                )
        if plugin.needs_prompts and not has_prompts:
            for mid in mids:
                skips[mid] = W.no_prompts(mid)
    for plugin_id, mids in plan.items():
        if all(m in skips for m in mids):
            continue
        for tool in registry.plugins[plugin_id].manifest["system_tools"]["required"]:
            if not tool_found(tool):
                raise FatalEnvironmentError(f"{tool} not found; plugin {plugin_id} needs it")
    if cfg.commercial:
        refused = [
            mid
            for mids in plan.values()
            for mid in mids
            if registry.metric(mid)["licence"]["commercial_ok"] != "yes"
        ]
        if refused:
            raise LicenceRefusal(
                "--commercial refuses metrics whose commercial_ok is not yes: " + ", ".join(refused)
            )
    refset = None
    if reference.kind == "dir":
        refset = scan_reference(reference.dir, cfg.refs_root)
        say(f"reference: {len(refset.files)} of {refset.n_found} audio files readable")
    return Preflight(skips, reference, refset)


def stage_audio(plugin: Plugin, ok: list[Clip], pre: Preflight, cfg: RunConfig, run_dir: Path) -> Stage:
    work_dir = run_dir / plugin.plugin_id
    gen_dir = work_dir / "gen"
    clips = stage_generated(ok, gen_dir)
    ref = {"kind": "none", "name": None, "dir": None, "n_clips": None}
    if plugin.needs_reference and pre.reference.kind == "bundled":
        ref = {"kind": "bundled", "name": pre.reference.name, "dir": None, "n_clips": None}
    elif plugin.needs_reference and pre.refset is not None:
        ref_dir = stage_reference(pre.refset, work_dir / "ref")
        ref = {"kind": "dir", "name": None, "dir": str(ref_dir), "n_clips": len(pre.refset.files)}
    return Stage(work_dir, gen_dir, clips, ref)


def build_request(metric_id: str, plugin: Plugin, stage: Stage, cfg: RunConfig, run_id: str) -> dict:
    options = dict(plugin.metrics[metric_id]["options"])
    options["per_clip"] = cfg.per_clip
    return {
        "schema": 1,
        "run_id": run_id,
        "metric_id": metric_id,
        "options": options,
        "device": cfg.device,
        "seed": cfg.seed,
        "workers": cfg.workers,
        "batch_size": cfg.batch_size,
        "generated": {"dir": str(stage.gen_dir), "clips": stage.clips},
        "reference": stage.reference,
        "paths": {"work_dir": str(stage.work_dir), "weights_dir": str(cfg.weights_dir)},
    }


def kill_group(proc: subprocess.Popen) -> None:
    """Stop the plugin process and everything it started (its own process group).

    SIGTERM to the group, wait up to KILL_GRACE_S for the leader, then SIGKILL
    whatever is left in the group.
    """
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:  # the group is already empty
        proc.wait()
        return
    try:
        proc.wait(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def _error(kind: str, message: str, tail: str | None = None) -> dict:
    return {"type": kind, "message": message, "traceback_tail": tail}


def read_response(path: Path, request: dict) -> tuple[dict | None, dict | None]:
    """(response, None) if valid, else (None, error block)."""
    try:
        resp = strict_json_loads(path.read_text(encoding="utf-8"))
        schemas.check(resp, "response")
    except FileNotFoundError:
        return None, _error("NoResponse", "the plugin process wrote no response file")
    except (OSError, ValueError, SchemaError) as exc:
        return None, _error("InvalidResponse", f"{path.name}: {exc}")
    if resp["metric_id"] != request["metric_id"]:
        return None, _error(
            "InvalidResponse", f"response is for {resp['metric_id']}, not {request['metric_id']}"
        )
    known = {c["clip_id"] for c in request["generated"]["clips"]}
    unknown = sorted({r["clip_id"] for r in resp["clip_scores"]} - known)
    if unknown:
        return None, _error("InvalidResponse", f"scores for unknown clip ids: {', '.join(unknown)}")
    return resp, None


def run_plugin(env, plugin: Plugin, request: dict, cfg: RunConfig, out: Path, work_dir: Path) -> Outcome:
    mid = request["metric_id"]
    req_path = out / "requests" / f"{mid}.request.json"
    resp_path = out / "responses" / f"{mid}.response.json"
    log_path = out / "logs" / f"{plugin.plugin_id}.log"
    schemas.check(request, "request")
    req_path.write_text(json.dumps(request, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    resp_path.unlink(missing_ok=True)
    cmd = [
        str(env.python), "-m", "musegauge_runtime.run",
        "--plugin-dir", str(plugin.dir),
        "--request", str(req_path),
        "--response", str(resp_path),
    ]
    timeout = cfg.timeout_min * 60.0 if cfg.timeout_min else None
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"=== {utc_now()} metric {mid}\n$ {' '.join(cmd)}\n")
        log.flush()
        log_start = log.tell()
        proc = subprocess.Popen(
            cmd,
            cwd=work_dir,
            env=config.plugin_process_env(cfg.home, cfg.no_fetch, threads=cfg.threads),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_group(proc)
            return Outcome(mid, plugin, "error", env=env, error=_error(
                "Timeout", f"plugin {plugin.plugin_id} was stopped after --timeout-min {cfg.timeout_min}"
            ))
        except BaseException:
            kill_group(proc)
            raise
        kill_group(proc)  # anything the wrapper left running
    resp, err = read_response(resp_path, request)
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        fh.seek(log_start)
        log_tail = "\n".join(fh.read().splitlines()[-LOG_TAIL_LINES:])
    if err is not None:
        err["message"] += f" (exit code {code}; see logs/{plugin.plugin_id}.log)"
        return Outcome(mid, plugin, "error", env=env, error=classify_network_error(err, log_tail))
    if resp["status"] == "error":
        resp["error"] = classify_network_error(resp["error"], log_tail)
    return Outcome(mid, plugin, resp["status"], response=resp, env=env, error=resp["error"])


def run_prefetch(env, plugin: Plugin, metric_id: str, home: Path, work_dir: Path) -> dict:
    """Run the shim in prefetch mode for one metric. Returns the prefetch response (or an error).

    The core writes the metric's manifest options as JSON (amendment A2), because the shim
    cannot read YAML.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    safe = metric_id.replace("@", "_")
    options_path = work_dir / f"{safe}.options.json"
    resp_path = work_dir / f"{safe}.prefetch.json"
    log_path = work_dir / f"{plugin.plugin_id}.log"
    options_path.write_text(json.dumps(plugin.metrics[metric_id]["options"], allow_nan=False))
    resp_path.unlink(missing_ok=True)
    cmd = [
        str(env.python), "-m", "musegauge_runtime.run",
        "--plugin-dir", str(plugin.dir),
        "--prefetch", metric_id,
        "--options", str(options_path),
        "--response", str(resp_path),
    ]
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"=== {utc_now()} prefetch {metric_id}\n$ {' '.join(cmd)}\n")
        log.flush()
        proc = subprocess.Popen(
            cmd, cwd=work_dir, env=config.plugin_process_env(home, no_fetch=False),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            code = proc.wait()
        except BaseException:
            kill_group(proc)
            raise
        kill_group(proc)
    try:
        out = strict_json_loads(resp_path.read_text(encoding="utf-8"))
        schemas.check(out, "prefetch")
    except (OSError, ValueError, SchemaError) as exc:
        out = {"schema": 1, "status": "error", "metric_id": metric_id, "downloaded": [], "notes": [],
               "timing_s": None, "error": _error("InvalidResponse", f"{exc} (exit code {code})")}
    out["log"] = str(log_path)
    return out


def check_envs_ready_for_no_fetch(plan, registry: Registry, pre: Preflight, backend: EnvBackend) -> None:
    """With --no-fetch, every needed environment must already exist: building one downloads
    packages. Stops with exit code 4 before anything runs (GATE 3 decision)."""
    ready = getattr(backend, "ready", None)
    if ready is None:
        return
    missing: list[str] = []
    for plugin_id, mids in plan.items():
        todo = [m for m in mids if m not in pre.skips]
        if not todo:
            continue
        try:
            if not ready(registry.plugins[plugin_id]):
                missing += todo
        except NoLockError:
            continue  # skipped later with NO_LOCK
    if missing:
        raise FatalEnvironmentError(
            "--no-fetch: the environments for these metrics are not built yet: "
            f"{', '.join(missing)}. Building them needs the network. Run "
            f"`musegauge setup --metrics {','.join(missing)} --fetch-weights` first, then run with --no-fetch."
        )


def check_home_writable(home: Path) -> None:
    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / f".write_test_{os.getpid()}"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        raise FatalEnvironmentError(f"MUSEGAUGE_HOME {home} is not writable: {exc}") from exc


def run(cfg: RunConfig, registry: Registry | None = None, backend: EnvBackend | None = None) -> int:
    started = utc_now()
    check_usage(cfg)
    registry = registry or Registry.discover()
    clipset = read_clips(cfg)
    ok, skipped = probe_audio(clipset.clips)
    say(f"{len(ok)} clip(s) readable, {len(skipped)} skipped")
    if not ok:
        raise InputError("no clip can be read: " + "; ".join(f"{s['clip_id']}: {s['reason']}" for s in skipped))
    metric_ids, suite = resolve_metrics(cfg, registry)
    plan = registry.group_by_plugin(metric_ids)
    check_home_writable(cfg.home)
    pre = preflight(plan, registry, cfg, ok, suite)

    uv_bin = find_uv()
    if backend is None:
        backend = UvBackend(cfg.envs_dir, cfg.home, allow_unlocked=cfg.allow_unlocked, uv_bin=uv_bin)
    if cfg.no_fetch:
        check_envs_ready_for_no_fetch(plan, registry, pre, backend)
    run_id = new_run_id()
    out = (cfg.out or Path.cwd() / "musegauge-out" / run_id).resolve()
    for sub in ("logs", "requests", "responses"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    run_dir = cfg.work_root / run_id
    say(f"run {run_id}, output {out}")

    outcomes: list[Outcome] = []
    unlocked: list[str] = []
    run_warnings: list[dict] = []
    try:
        for plugin_id, mids in plan.items():
            plugin = registry.plugins[plugin_id]
            for mid in mids:
                if mid in pre.skips:
                    outcomes.append(Outcome(mid, plugin, "skipped", warnings=[pre.skips[mid]]))
            todo = [m for m in mids if m not in pre.skips]
            if not todo:
                continue
            if hasattr(backend, "log_path"):
                backend.log_path = out / "logs" / f"{plugin_id}.log"
            say(f"plugin {plugin_id}: preparing environment")
            try:
                env = backend.ensure(plugin)
            except NoLockError:
                outcomes += [Outcome(m, plugin, "skipped") for m in todo]
                run_warnings.append(W.no_lock(plugin_id, config.platform_tag(), todo))
                continue
            except EnvError as exc:
                err = _error("EnvError", str(exc), exc.output_tail)
                outcomes += [Outcome(m, plugin, "error", error=err) for m in todo]
                continue
            if not env.reproducible:
                unlocked.append(plugin_id)
            stage = stage_audio(plugin, ok, pre, cfg, run_dir)
            for mid in todo:
                say(f"metric {mid}: running")
                request = build_request(mid, plugin, stage, cfg, run_id)
                outcome = run_plugin(env, plugin, request, cfg, out, stage.work_dir)
                say(f"metric {mid}: {outcome.status}")
                outcomes.append(outcome)
    finally:
        if not cfg.keep_work and run_dir.exists():
            safe_rmtree(run_dir, cfg.work_root)

    durations = {c.clip_id: c.duration_s for c in ok}
    data_warnings = [
        W.clips_skipped(skipped) if skipped else None,
        W.short_clips(durations),
        W.mixed_sample_rates(generated_block(ok, skipped, clipset.manifest_sha256)["sample_rates_hz"]),
        W.mixed_durations(durations),
    ]
    if pre.refset is not None:
        gen_hashes = file_hashes({c.clip_id: c.path for c in ok}, cfg.refs_root)
        data_warnings += [W.ref_small(len(pre.refset.files)),
                          W.ref_gen_overlap(gen_hashes, pre.refset.file_hashes)]
    run_warnings = [w for w in data_warnings if w] + run_warnings
    if unlocked:
        run_warnings.append(W.unlocked_env(unlocked))
    order = [c.clip_id for c in ok]
    rs = pre.refset
    results = {
        "schema": 1,
        "suite": suite.ref if suite else None,
        "tool": tool_block(uv_version(uv_bin), config.platform_tag()),
        "run": {
            "run_id": run_id,
            "started_utc": started,
            "finished_utc": utc_now(),
            "command": cfg.command,
            "seed": cfg.seed,
            "device_requested": cfg.device,
            "reproducible": not unlocked,
            "threads": cfg.threads,
        },
        "generated": generated_block(ok, skipped, clipset.manifest_sha256),
        "reference": {
            "kind": pre.reference.kind,
            "name": pre.reference.name,
            "ref_hash": rs.ref_hash if rs else None,
            "n_clips": len(rs.files) if rs else None,
            "total_duration_s": rs.total_duration_s if rs else None,
        },
        "metrics": [metric_entry(o, cfg.seed, cfg.bootstrap, out, order, len(ok)) for o in outcomes],
        "warnings": run_warnings,
    }
    for w in results["warnings"] + [w for m in results["metrics"] for w in m["warnings"]]:
        W.emit(w)
    path = write_results(results, out)
    write_report(results, out)
    say(f"wrote {path} and {out / 'report.md'}")
    if cfg.json:
        print(path)
    return exit_code(results)
