"""Plugin fad_fadtk: Frechet Audio Distance through the fadtk command (spec section 9.2).

Calls `fadtk MODEL BASELINE EVAL CSV -w N` as a subprocess, with a fresh CSV for every call,
all inside paths.work_dir. Upstream code is imported inside functions only.
"""

from __future__ import annotations

import csv
import importlib.metadata
import os
import platform
import subprocess
import sys

TAIL = 40
REMOTE_CODE_VGGISH = (
    "VGGish code from github.com/harritaylor/torchvggish, branch master, loaded through torch.hub "
    "at run time (or from the torch.hub cache); not pinned to a commit"
)


def _bin(name: str) -> str:
    return os.path.join(os.path.dirname(sys.executable), name)


def _set_device(requested: str) -> None:
    # fadtk picks cuda if torch sees a GPU; it has no device flag. Hide the GPUs for cpu.
    if requested == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""


def _env_block() -> dict:
    import torch

    cuda = torch.cuda.is_available()
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "torch_threads": torch.get_num_threads(),  # in the wrapper; fadtk runs with the same settings
        "cuda_available": cuda,
        "device": "cuda" if cuda else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
    }


def _cache_dirs() -> list[str]:
    import fadtk

    return [
        os.path.join(os.path.dirname(fadtk.__file__), ".model-checkpoints"),
        os.environ.get("TORCH_HOME", ""),
        os.environ.get("HF_HOME", ""),
    ]


def _files(dirs: list[str]) -> set[str]:
    found = set()
    for d in dirs:
        for root, _, names in os.walk(d) if d and os.path.isdir(d) else []:
            found.update(os.path.join(root, n) for n in names)
    return found


def _warm_up(model: str) -> None:
    """Load VGGish once, so fadtk's parallel workers do not all download it at the same time."""
    if model == "vggish":
        import torch

        torch.hub.load("harritaylor/torchvggish", "vggish")


def _run(cmd: list[str], work_dir: str) -> tuple[int, str]:
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=work_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          env=dict(os.environ), check=False)
    print(proc.stdout, flush=True)  # the plugin log
    return proc.returncode, "\n".join(proc.stdout.splitlines()[-TAIL:])


def _last_row(path: str) -> dict:
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise RuntimeError(f"fadtk wrote no row to {path}")
    return rows[-1]


def _float(text: str) -> float:
    return float(text)  # "nan" or "inf" stay non-finite; the runtime shim turns them into null


def run(request: dict) -> dict:
    _set_device(request["device"])
    import torch

    if request["device"] == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but torch.cuda.is_available() is False")
    options = request["options"]
    model = options["model"]
    work = request["paths"]["work_dir"]
    gen_dir = request["generated"]["dir"]
    ref = request["reference"]
    baseline = ref["name"] if ref["kind"] == "bundled" else ref["dir"]
    workers = str(request["workers"])
    before = _files(_cache_dirs())
    _warm_up(model)

    invocations, warnings, scores = [], [], []
    # 1. plain run
    csv_plain = os.path.join(work, f"fadtk-{model}-plain.csv")
    cmd = [_bin("fadtk"), model, baseline, gen_dir, csv_plain, "-w", workers]
    code, tail = _run(cmd, work)
    invocations.append(" ".join(cmd))
    if code != 0 or not os.path.exists(csv_plain):
        raise RuntimeError(f"fadtk exited with code {code}:\n{tail}")
    scores.append({"name": "fad", "value": _float(_last_row(csv_plain)["score"]), "kind": "set"})

    # 2. FAD-inf
    if options.get("inf"):
        csv_inf = os.path.join(work, f"fadtk-{model}-inf.csv")
        cmd = [_bin("fadtk"), model, baseline, gen_dir, csv_inf, "-w", workers, "--inf"]
        code, tail = _run(cmd, work)
        invocations.append(" ".join(cmd))
        if code == 0 and os.path.exists(csv_inf):
            row = _last_row(csv_inf)
            scores.append({"name": "fad_inf", "value": _float(row["score"]), "kind": "set"})
            scores.append({"name": "fad_inf_r2", "value": _float(row["inf_r2"]), "kind": "aux"})
            warnings.append({
                "code": "UNSEEDED_RANDOMNESS",
                "message": "fad_inf and fad_inf_r2 come from fadtk's score_inf, which samples embedding "
                           "frames with numpy.random.choice without a seed; they change from run to run.",
            })
        else:
            warnings.append({"code": "FAD_INF_FAILED",
                             "message": f"fadtk --inf exited with code {code}; fad is kept. Upstream output:\n{tail}"})

    # 3. per-clip FAD
    clip_scores = []
    if options.get("per_clip"):
        csv_indiv = os.path.join(work, f"fadtk-{model}-indiv.csv")
        cmd = [_bin("fadtk"), model, baseline, gen_dir, csv_indiv, "-w", workers, "--indiv"]
        code, tail = _run(cmd, work)
        invocations.append(" ".join(cmd))
        if code != 0 or not os.path.exists(csv_indiv):
            raise RuntimeError(f"fadtk --indiv exited with code {code}:\n{tail}")
        by_file = {c["file"]: c["clip_id"] for c in request["generated"]["clips"]}
        with open(csv_indiv, newline="") as fh:
            for path, value in csv.reader(fh):  # rows "path,score", no header
                clip_scores.append({"clip_id": by_file[os.path.basename(path)],
                                    "scores": {"fad_indiv": _float(value)}})

    fetched = sorted(_files(_cache_dirs()) - before)
    if fetched:
        warnings.append({"code": "NETWORK_FETCH",
                         "message": f"Downloaded {len(fetched)} file(s): " + ", ".join(os.path.basename(f) for f in fetched)})
    return {
        "scores": scores,
        "clip_scores": clip_scores,
        "upstream": {"package": "fadtk", "version": importlib.metadata.version("fadtk"),
                     "invocation": " ; ".join(invocations)},
        "env": {**_env_block(), **({"remote_code": REMOTE_CODE_VGGISH} if model == "vggish" else {})},
        "warnings": warnings,
    }


def prefetch(metric_id: str, options: dict) -> dict:
    """Do what the fadtk command does at start-up (build every model loader, which downloads the
    CLAP checkpoints into fadtk's package folder), then load this metric's model once."""
    _set_device("cpu")
    from fadtk.model_loader import get_all_models

    before = _files(_cache_dirs())
    models = {m.name: m for m in get_all_models()}
    models[options["model"]].load_model()
    after = _files(_cache_dirs())
    return {"downloaded": sorted(after - before),
            "notes": [f"fadtk model {options['model']} loaded on the CPU"]}
