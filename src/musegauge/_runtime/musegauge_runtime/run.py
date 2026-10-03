"""Runtime shim. Runs inside a plugin environment as `python -m musegauge_runtime.run`.

Standard library only, and it must parse on Python 3.9 (spec section 4.4).

Normal mode:   --plugin-dir DIR --request FILE --response FILE
Prefetch mode: --plugin-dir DIR --prefetch METRIC_ID --response FILE [--options FILE]

It loads wrapper.py from the plugin folder by file path and calls run(request) or
prefetch(metric_id, options). It always tries to write a response file, also when
the wrapper raises, so the core can record the error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import time
import traceback

TRACEBACK_LINES = 40
UNKNOWN_METRIC = "unknown.unknown@0"


def load_wrapper(plugin_dir):
    path = os.path.join(plugin_dir, "wrapper.py")
    spec = importlib.util.spec_from_file_location("musegauge_plugin_wrapper", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load " + path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _tail(text, n):
    return "\n".join(text.splitlines()[-n:])


def error_block(exc):
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback_tail": _tail(traceback.format_exc(), TRACEBACK_LINES),
    }


def _bad_float(value):
    return isinstance(value, float) and not math.isfinite(value)


def sanitize(response):
    """Replace non-finite scores with null and add the NAN_SCORE warning."""
    bad = []
    for score in response.get("scores", []):
        if _bad_float(score.get("value")):
            score["value"] = None
            bad.append(str(score.get("name")))
    for row in response.get("clip_scores", []):
        scores = row.get("scores", {})
        for name, value in scores.items():
            if _bad_float(value):
                scores[name] = None
                bad.append(f"{row.get('clip_id')}:{name}")
    if bad:
        shown = ", ".join(bad[:20]) + (" ..." if len(bad) > 20 else "")
        response.setdefault("warnings", []).append(
            {"code": "NAN_SCORE", "message": "Non-finite value replaced by null: " + shown}
        )
    return response


def complete(response, metric_id, timing_s):
    """Fill the fields every response has, so wrappers only return what they know."""
    response.setdefault("schema", 1)
    response.setdefault("status", "ok")
    response.setdefault("metric_id", metric_id)
    for key in ("scores", "clip_scores", "clips_failed", "warnings"):
        response.setdefault(key, [])
    response.setdefault("upstream", None)
    response.setdefault("env", {})
    response.setdefault("error", None)
    if response.get("timing_s") is None:
        response["timing_s"] = timing_s
    if response["status"] == "error":
        response["scores"] = []
        response["clip_scores"] = []
    return response


def error_response(metric_id, exc, timing_s):
    return complete({"status": "error", "error": error_block(exc)}, metric_id, timing_s)


def write_json(path, obj):
    """Write strict JSON (no NaN) atomically."""
    text = json.dumps(obj, allow_nan=False, indent=2)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    os.replace(tmp, path)


def run_normal(args):
    start = time.monotonic()
    metric_id = UNKNOWN_METRIC
    try:
        with open(args.request, encoding="utf-8") as fh:
            request = json.load(fh)
        metric_id = request.get("metric_id", UNKNOWN_METRIC)
        wrapper = load_wrapper(args.plugin_dir)
        response = wrapper.run(request)
        if not isinstance(response, dict):
            raise TypeError(f"wrapper.run must return a dict, got {type(response).__name__}")
        response = complete(sanitize(response), metric_id, time.monotonic() - start)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - any wrapper failure becomes an error response
        response = error_response(metric_id, exc, time.monotonic() - start)
    try:
        write_json(args.response, response)
    except (TypeError, ValueError) as exc:  # not JSON serialisable, or NaN outside the scores
        response = error_response(metric_id, exc, time.monotonic() - start)
        response["error"]["type"] = "InvalidResponse"
        write_json(args.response, response)
    return 0 if response["status"] == "ok" else 1


def run_prefetch(args):
    start = time.monotonic()
    out = {"schema": 1, "status": "ok", "metric_id": args.prefetch, "downloaded": [], "notes": [],
           "timing_s": None, "error": None}
    try:
        options = {}
        if args.options:
            with open(args.options, encoding="utf-8") as fh:
                options = json.load(fh)
        wrapper = load_wrapper(args.plugin_dir)
        result = wrapper.prefetch(args.prefetch, options)
        out["downloaded"] = [str(x) for x in result.get("downloaded", [])]
        out["notes"] = [str(x) for x in result.get("notes", [])]
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - any wrapper failure becomes an error response
        out["status"] = "error"
        out["error"] = error_block(exc)
    out["timing_s"] = time.monotonic() - start
    write_json(args.response, out)
    return 0 if out["status"] == "ok" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="musegauge_runtime.run")
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--response", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--request")
    mode.add_argument("--prefetch", metavar="METRIC_ID")
    parser.add_argument("--options", help="prefetch mode: JSON file with the metric's options")
    args = parser.parse_args(argv)
    if args.prefetch:
        return run_prefetch(args)
    return run_normal(args)


if __name__ == "__main__":
    sys.exit(main())
