"""Command line: argparse, command dispatch and exit codes (spec section 7).

Progress and messages go to standard error. Standard output is only for `list`, `info`,
`report` and `run --json`.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from musegauge import __version__
from musegauge.errors import (
    EXIT_ALL_FAILED,
    EXIT_ENVIRONMENT,
    EXIT_INPUT,
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_PARTIAL,
    EXIT_USAGE,
    MusegaugeError,
    UsageError,
)

NETWORK_TIMEOUT_S = 5
CLEAN_TARGETS = ("envs", "work", "refs", "weights")


def err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _int_at_least(minimum: int):
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"must be at least {minimum}")
        return value

    return parse


def _positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not value > 0:
        raise argparse.ArgumentTypeError("must be above 0")
    return value


def _metric_list(text: str) -> list[str]:
    return [m.strip() for m in text.split(",") if m.strip()]


def build_parser() -> argparse.ArgumentParser:
    from musegauge.config import DEVICES, default_workers

    parser = argparse.ArgumentParser(
        prog="musegauge",
        description="Score generated music with several existing metrics in one command.",
    )
    parser.add_argument("--home", metavar="DIR", help="cache folder (sets MUSEGAUGE_HOME)")
    parser.add_argument("-v", "--verbose", action="store_true", help="print more detail")
    parser.add_argument("--version", action="version", version=f"musegauge {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    run = sub.add_parser("run", help="score generated audio", description="Score generated audio.")
    run.add_argument("--generated", metavar="DIR", type=Path,
                     help="folder of audio files (.wav .flac .ogg .mp3); use this or --manifest")
    run.add_argument("--manifest", metavar="FILE", type=Path, help="clips file in JSON lines format")
    run.add_argument("--prompts", metavar="FILE", type=Path,
                     help="prompts for folder mode: .jsonl or .csv with clip_id and prompt")
    run.add_argument("--reference", metavar="DIR|bundled:NAME",
                     help="reference audio folder, or bundled:fma_pop (default: the suite's default)")
    run.add_argument("--suite", metavar="NAME[@N]",
                     help="named list of metrics; without @N the highest version (default: t2m-basic)")
    run.add_argument("--metrics", metavar="ID,ID,...", type=_metric_list,
                     help="explicit metric ids; cannot be combined with --suite")
    run.add_argument("--out", metavar="DIR", type=Path,
                     help="output folder (default: ./musegauge-out/<run-id>)")
    run.add_argument("--device", choices=DEVICES, default="auto", help="default: auto")
    run.add_argument("--workers", metavar="N", type=_int_at_least(1), default=default_workers(),
                     help="data loading workers passed to plugins (default: min(8, CPU count))")
    run.add_argument("--batch-size", metavar="N", type=_int_at_least(1),
                     help="batch size for clip-level metrics (default: the plugin's own)")
    run.add_argument("--seed", metavar="N", type=int, default=0,
                     help="seed for bootstrap and plugins (default: 0)")
    run.add_argument("--bootstrap", metavar="N", type=_int_at_least(0), default=1000,
                     help="bootstrap resamples; 0 turns confidence intervals off (default: 1000)")
    run.add_argument("--per-clip", action="store_true",
                     help="also write per-clip scores for set metrics that support it (fad.* in 0.1)")
    run.add_argument("--timeout-min", metavar="N", type=_positive_float,
                     help="time limit per plugin, in minutes (default: none)")
    run.add_argument("--keep-work", action="store_true", help="keep work/<run-id> after the run")
    run.add_argument("--no-fetch", action="store_true",
                     help="do not allow downloads (run `musegauge setup --fetch-weights` first)")
    run.add_argument("--commercial", action="store_true",
                     help="refuse any metric whose commercial_ok is not yes (exit code 6)")
    run.add_argument("--allow-unlocked", action="store_true",
                     help="allow plugins with no lock file for this platform (reproducible: false)")
    run.add_argument("--json", action="store_true", help="print the path of results.json on standard output")
    run.add_argument("--threads", metavar="N", type=_int_at_least(1),
                     help="limit CPU threads in each plugin (sets OMP_NUM_THREADS, MKL_NUM_THREADS, "
                          "OPENBLAS_NUM_THREADS, NUMEXPR_NUM_THREADS); default: not set, as upstream")

    lst = sub.add_parser("list", help="list suites and metrics",
                         description="Print every suite and metric: id, kind, plugin, needs, commercial_ok.")
    lst.add_argument("--json", action="store_true", help="print JSON")

    info = sub.add_parser("info", help="show one metric's manifest entry",
                          description="Print the manifest entry for one metric: definition, upstream "
                          "package and version, Python version, runtime downloads, and the three "
                          "licence blocks with their status and check_urls.")
    info.add_argument("metric_id", metavar="METRIC_ID")

    sub.add_parser("doctor", help="check this machine",
                   description="Print one line per check as OK, WARN or FAIL. Exit code 0 if there "
                   "is no FAIL, otherwise 4.")

    setup = sub.add_parser("setup", help="build plugin environments ahead of time",
                           description="Build the environments for the chosen plugins. With "
                           "--fetch-weights, also download what each metric needs at run time.")
    which = setup.add_mutually_exclusive_group()
    which.add_argument("--suite", metavar="NAME", help="metrics of this suite (default: t2m-basic)")
    which.add_argument("--metrics", metavar="ID,ID,...", type=_metric_list, help="explicit metric ids")
    which.add_argument("--all", action="store_true", help="every metric of every plugin")
    setup.add_argument("--fetch-weights", action="store_true",
                       help="run each wrapper's prefetch so weights land in the cache")

    clean = sub.add_parser("clean", help="delete cached files inside MUSEGAUGE_HOME",
                           description="Show the size of what would be deleted and ask for "
                           "confirmation unless --yes. Deletes only inside MUSEGAUGE_HOME.")
    for target in CLEAN_TARGETS:
        clean.add_argument(f"--{target}", action="store_true", help=f"delete {target}/")
    clean.add_argument("--all", action="store_true", help="all of the above")
    clean.add_argument("--yes", action="store_true", help="do not ask for confirmation")

    report = sub.add_parser("report", help="print the report card for a results.json",
                            description="Print the reporting card and table for an existing results file.")
    report.add_argument("results", metavar="RESULTS_JSON", type=Path)

    validate = sub.add_parser("validate", help="check a file against its schema",
                              description="Check a file against its schema and print each problem "
                              "on its own line. Exit code 3 if any problem is found.")
    target = validate.add_mutually_exclusive_group(required=True)
    target.add_argument("--clips", metavar="FILE", type=Path, help="a clips file (JSON lines)")
    target.add_argument("--plugin", metavar="DIR", type=Path, help="a plugin folder")
    target.add_argument("--results", metavar="FILE", type=Path, help="a results.json")
    return parser


# --- run -------------------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace, argv: list[str]) -> int:
    from musegauge import config, runner

    cfg = config.RunConfig(
        home=config.musegauge_home(),
        out=args.out,
        generated=args.generated,
        manifest=args.manifest,
        prompts=args.prompts,
        reference=args.reference,
        suite=args.suite,
        metrics=args.metrics,
        device=args.device,
        workers=args.workers,
        batch_size=args.batch_size,
        seed=args.seed,
        bootstrap=args.bootstrap,
        per_clip=args.per_clip,
        timeout_min=args.timeout_min,
        keep_work=args.keep_work,
        no_fetch=args.no_fetch,
        commercial=args.commercial,
        allow_unlocked=args.allow_unlocked,
        threads=args.threads,
        json=args.json,
        command=shlex.join(["musegauge", *argv]),
        verbose=args.verbose,
    )
    return runner.run(cfg)


# --- list and info ---------------------------------------------------------------------------


def _needs(plugin) -> str:
    needs = [k for k in ("reference", "prompts") if plugin.manifest["needs"][k]]
    return ",".join(needs) or "-"


def cmd_list(args: argparse.Namespace) -> int:
    from musegauge.registry import Registry

    reg = Registry.discover()
    suites = [
        {"suite": s.ref, "description": s.data["description"], "metrics": s.metrics,
         "default_reference": s.default_reference,
         "missing_metrics": [m for m in s.metrics if m not in reg.metric_index]}
        for versions in reg.suites.values() for s in sorted(versions.values(), key=lambda s: s.version)
    ]
    metrics = [
        {"metric_id": mid, "kind": reg.plugins[pid].kind, "plugin_id": pid,
         "needs": dict(reg.plugins[pid].manifest["needs"]),
         "commercial_ok": reg.metric(mid)["licence"]["commercial_ok"]}
        for mid, pid in sorted(reg.metric_index.items())
    ]
    if args.json:
        print(json.dumps({"suites": suites, "metrics": metrics}, indent=2))
        return EXIT_OK
    print("Suites:")
    for s in suites:
        ref = f" (default reference: {s['default_reference']})" if s["default_reference"] else ""
        print(f"  {s['suite']}: {s['description']}{ref}")
        for mid in s["metrics"]:
            print(f"    {mid}{'  [not installed]' if mid in s['missing_metrics'] else ''}")
    print("Metrics:")
    rows = [("METRIC", "KIND", "PLUGIN", "NEEDS", "COMMERCIAL_OK")] + [
        (m["metric_id"], m["kind"], m["plugin_id"], _needs(reg.plugins[m["plugin_id"]]), m["commercial_ok"])
        for m in metrics
    ]
    widths = [max(len(r[i]) for r in rows) for i in range(5)]
    for r in rows:
        print("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
    return EXIT_OK


def cmd_info(args: argparse.Namespace) -> int:
    import yaml

    from musegauge.registry import Registry

    reg = Registry.discover()
    if args.metric_id not in reg.metric_index:
        raise UsageError(f"unknown metric {args.metric_id!r} (see `musegauge list`)")
    plugin = reg.plugin_for(args.metric_id)
    m = plugin.metrics[args.metric_id]
    entry = {
        "metric_id": args.metric_id,
        "plugin_id": plugin.plugin_id,
        "kind": plugin.kind,
        "definition": m["definition"],
        "primary": m["primary"],
        "options": m["options"],
        "upstream": dict(plugin.manifest["upstream"]),
        "python": plugin.python,
        "runtime_downloads": plugin.manifest["runtime_downloads"],
        "trust_remote_code": plugin.manifest["trust_remote_code"],
        "needs": dict(plugin.manifest["needs"]),
        "reference_modes": plugin.manifest["reference_modes"],
        "bundled_references": plugin.manifest["bundled_references"],
        "system_tools": dict(plugin.manifest["system_tools"]),
        "licence": m["licence"],
    }
    print(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True, width=100), end="")
    return EXIT_OK


# --- doctor ----------------------------------------------------------------------------------


def _reachable(url: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": f"musegauge/{__version__}"})
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT_S) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:  # the server answered
        return True, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        return False, str(getattr(exc, "reason", exc))


def _first_line(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"(could not run: {exc})"
    lines = (out.stdout or out.stderr).strip().splitlines()
    return lines[0].strip() if lines else ""


def find_sox() -> str | None:
    """sox through SOX_PATH, else PATH."""
    if os.environ.get("SOX_PATH"):
        return shutil.which(os.environ["SOX_PATH"])
    return shutil.which("sox")


def doctor_checks() -> list[tuple[str, str, str]]:
    from musegauge import config
    from musegauge.envs import find_uv, uv_version
    from musegauge.errors import FatalEnvironmentError
    from musegauge.registry import Registry

    checks: list[tuple[str, str, str]] = []
    tag = config.platform_tag()
    if tag == "linux-x86_64":
        checks.append(("OK", "platform", tag))
    elif tag.startswith("macos"):
        checks.append(("WARN", "platform", f"{tag}: best effort in 0.1, no lock files"))
    else:
        checks.append(("FAIL", "platform", f"{tag}: not supported in 0.1"))
    try:
        uv_bin = find_uv()
        checks.append(("OK", "uv", f"{uv_version(uv_bin)} at {uv_bin}"))
    except FatalEnvironmentError as exc:
        checks.append(("FAIL", "uv", str(exc)))
    sox = find_sox()
    via = "SOX_PATH" if os.environ.get("SOX_PATH") else "PATH"
    if sox:
        checks.append(("OK", "sox", f"{sox} (via {via}): {_first_line([sox, '--version'])}"))
    else:
        # Amendment A6: no 0.1 plugin runs sox, so a missing sox is only reported.
        checks.append(("WARN", "sox", f"not found through {via} (not used by any 0.1 plugin)"))
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        checks.append(("OK", "ffmpeg", f"{ffmpeg}: {_first_line([ffmpeg, '-version'])}"))
    else:
        checks.append(("WARN", "ffmpeg", "not found on PATH"))
    home = config.musegauge_home()
    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / f".doctor_{os.getpid()}"
        probe.write_text("ok")
        probe.unlink()
        free = shutil.disk_usage(home).free
        checks.append(("OK", "MUSEGAUGE_HOME", f"{home} is writable; {free / 1e9:.1f} GB free"))
    except OSError as exc:
        checks.append(("FAIL", "MUSEGAUGE_HOME", f"{home} is not writable: {exc}"))
    smi = shutil.which("nvidia-smi")
    if smi:
        gpus = _first_line([smi, "--query-gpu=name,driver_version", "--format=csv,noheader"])
        count = _first_line([smi, "--query-gpu=count", "--format=csv,noheader"])
        checks.append(("OK", "nvidia-smi", f"{smi}: {count} GPU(s), first: {gpus}"))
    else:
        checks.append(("WARN", "nvidia-smi", "not found (no NVIDIA driver; GPU metrics will run on CPU)"))
    for url in ("https://pypi.org", "https://huggingface.co"):
        ok, detail = _reachable(url)
        checks.append(("OK" if ok else "WARN", url, detail if ok else f"not reachable: {detail}"))
    try:
        reg = Registry.discover()
    except MusegaugeError as exc:
        checks.append(("FAIL", "plugins", str(exc)))
        return checks
    if not reg.plugins:
        checks.append(("WARN", "plugins", "no plugins found"))
    for pid, plugin in sorted(reg.plugins.items()):
        lock = plugin.lock_path(tag)
        if lock:
            checks.append(("OK", f"plugin {pid}", f"lock for {tag}: {lock.name}"))
        else:
            checks.append(("WARN", f"plugin {pid}", f"no lock for {tag}; skipped unless --allow-unlocked"))
    return checks


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = doctor_checks()
    for status, name, detail in checks:
        err(f"{status:<4}  {name}: {detail}")
    return EXIT_ENVIRONMENT if any(c[0] == "FAIL" for c in checks) else EXIT_OK


# --- setup -----------------------------------------------------------------------------------


def cmd_setup(args: argparse.Namespace) -> int:
    from musegauge import config, runner
    from musegauge.envs import UvBackend
    from musegauge.errors import EnvError, NoLockError
    from musegauge.registry import Registry
    from musegauge.staging import safe_rmtree

    reg = Registry.discover()
    if args.all:
        metric_ids = sorted(reg.metric_index)
    else:
        suite = args.suite or (None if args.metrics else config.DEFAULT_SUITE)
        metric_ids, _ = reg.resolve_metrics(suite, args.metrics)
    home = config.musegauge_home()
    runner.check_home_writable(home)
    backend = UvBackend(config.envs_dir(home), home)
    work = home / "work" / f"setup-{runner.new_run_id()}"
    ok = failed = 0
    for plugin_id, mids in reg.group_by_plugin(metric_ids).items():
        plugin = reg.plugins[plugin_id]
        backend.log_path = work / f"{plugin_id}.log"
        err(f"musegauge: plugin {plugin_id}: building or checking its environment")
        try:
            env = backend.ensure(plugin)
        except NoLockError as exc:
            err(f"musegauge: plugin {plugin_id}: skipped: {exc}")
            continue
        except EnvError as exc:
            err(f"musegauge: plugin {plugin_id}: FAILED: {exc}\n{exc.output_tail}")
            failed += len(mids)
            continue
        err(f"musegauge: plugin {plugin_id}: environment ready: {env.path}")
        if not args.fetch_weights:
            ok += len(mids)
            continue
        for mid in mids:
            res = runner.run_prefetch(env, plugin, mid, home, work)
            if res["status"] == "ok":
                ok += 1
                err(f"musegauge: prefetch {mid}: ok ({res['timing_s']:.1f} s)")
                for item in res["downloaded"]:
                    err(f"    downloaded: {item}")
                for note in res["notes"]:
                    err(f"    note: {note}")
            else:
                failed += 1
                e = res["error"]
                err(f"musegauge: prefetch {mid}: FAILED: {e['type']}: {e['message']} (log: {res['log']})")
    if failed == 0 and work.exists():
        safe_rmtree(work, home / "work")
    if failed:
        return EXIT_PARTIAL if ok else EXIT_ALL_FAILED
    return EXIT_OK


# --- clean -----------------------------------------------------------------------------------


def folder_size(path: Path) -> int:
    """Disk use of the files under a folder. Symbolic links are not followed, and a file with
    several hard links (uv links package files from its cache) is counted once."""
    total, seen = 0, set()
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                st = os.lstat(os.path.join(root, name))
            except OSError:
                continue
            if (st.st_dev, st.st_ino) in seen:
                continue
            seen.add((st.st_dev, st.st_ino))
            total += st.st_size
    return total


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n} B"


def cmd_clean(args: argparse.Namespace) -> int:
    from musegauge import config
    from musegauge.staging import safe_rmtree

    chosen = [t for t in CLEAN_TARGETS if args.all or getattr(args, t)]
    if not chosen:
        raise UsageError("choose what to delete: --envs, --work, --refs, --weights or --all")
    home = config.musegauge_home()
    paths = {t: (config.envs_dir(home) if t == "envs" else home / t) for t in chosen}
    refused = [t for t, p in paths.items() if home.resolve() not in p.resolve().parents]
    for t in refused:
        err(f"musegauge: refusing to delete {paths[t]}: it is outside MUSEGAUGE_HOME {home}")
    todo = {t: p for t, p in paths.items() if t not in refused and p.exists()}
    if not todo:
        err("musegauge: nothing to delete")
        return EXIT_USAGE if refused else EXIT_OK
    for t, p in todo.items():
        err(f"  {t}: {p} ({human(folder_size(p))})")
    if not args.yes:
        err("Delete these folders? [y/N] ")
        try:
            answer = input()
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            err("musegauge: nothing deleted")
            return EXIT_OK
    for t, p in todo.items():
        safe_rmtree(p, home)
        err(f"musegauge: deleted {p}")
    return EXIT_USAGE if refused else EXIT_OK


# --- report and validate ---------------------------------------------------------------------


def _load_results(path: Path) -> dict:
    from musegauge import schemas
    from musegauge.clips import strict_json_loads
    from musegauge.errors import InputError

    try:
        doc = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    found = schemas.problems(doc, "results")
    if found:
        raise InputError(f"{path} is not a valid results file: " + "; ".join(found[:5]))
    return doc


def cmd_report(args: argparse.Namespace) -> int:
    from musegauge.report import render

    sys.stdout.write(render(_load_results(args.results)))
    return EXIT_OK


def validate_problems(args: argparse.Namespace) -> list[str]:
    from musegauge import schemas
    from musegauge.clips import strict_json_loads
    from musegauge.registry import manifest_problems

    if args.plugin:
        path = args.plugin / "manifest.yaml"
        if not path.is_file():
            return [f"{args.plugin}: no manifest.yaml"]
        import yaml

        try:
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            return [f"{path}: cannot read YAML: {exc}"]
        return [f"{path}: {p}" for p in manifest_problems(args.plugin.resolve(), manifest)]
    path = args.clips or args.results
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: cannot read: {exc}"]
    if args.results:
        try:
            doc = strict_json_loads(text)
        except ValueError as exc:
            return [f"{path}: not valid JSON: {exc}"]
        return [f"{path}: {p}" for p in schemas.problems(doc, "results")]
    found, seen = [], set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = strict_json_loads(line)
        except ValueError as exc:
            found.append(f"{path}:{lineno}: not valid JSON: {exc}")
            continue
        found += [f"{path}:{lineno}: {p}" for p in schemas.problems(obj, "clip")]
        cid = obj.get("clip_id") if isinstance(obj, dict) else None
        if isinstance(cid, str):
            if cid in seen:
                found.append(f"{path}:{lineno}: duplicate clip_id {cid!r}")
            seen.add(cid)
    if not seen and not found:
        found.append(f"{path}: no clips in the file")
    return found


def cmd_validate(args: argparse.Namespace) -> int:
    found = validate_problems(args)
    for line in found:
        err(line)
    if found:
        return EXIT_INPUT
    err("OK")
    return EXIT_OK


# --- main ------------------------------------------------------------------------------------

COMMANDS = {
    "list": cmd_list,
    "info": cmd_info,
    "doctor": cmd_doctor,
    "setup": cmd_setup,
    "clean": cmd_clean,
    "report": cmd_report,
    "validate": cmd_validate,
}


def main(argv: list[str] | None = None) -> int:
    if sys.platform.startswith("win"):
        print("Windows is not supported in 0.1", file=sys.stderr)
        return EXIT_ENVIRONMENT
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    args = parser.parse_args(argv)  # exits with code 2 on wrong usage
    if args.home:
        os.environ["MUSEGAUGE_HOME"] = str(Path(args.home).expanduser().resolve())
    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    start = time.monotonic()
    try:
        if args.command == "run":
            return cmd_run(args, argv)
        return COMMANDS[args.command](args)
    except MusegaugeError as exc:
        err(f"musegauge: error: {exc}")
        return exc.exit_code
    except KeyboardInterrupt:
        err(f"musegauge: interrupted after {time.monotonic() - start:.0f} s")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())
