"""Plugin kad_kadtk: Kernel Audio Distance through the kadtk command (spec section 9.3).

Calls `kadtk MODEL BASELINE EVAL --csv FILE --device D -w N` as a subprocess, with a fresh CSV
inside paths.work_dir. Never passes --force-stats-calc (it crashes in 1.1.0) or --fad.
Upstream code is imported inside functions only.
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


def _device(requested: str) -> str:
    # kadtk's --device only covers the kernel computation; its embedding models use cuda
    # whenever torch sees a GPU. So for cpu the GPUs are hidden as well.
    if requested == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        return "cpu"
    import torch

    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but torch.cuda.is_available() is False")
    if requested == "mps":
        raise RuntimeError("--device mps is not supported by this plugin")
    return "cuda" if torch.cuda.is_available() else "cpu"


def _cache_dirs() -> list[str]:
    import importlib.util

    spec = importlib.util.find_spec("kadtk")
    pkg = os.path.dirname(spec.origin)
    return [os.path.join(pkg, ".model-checkpoints"), os.environ.get("TORCH_HOME", ""), os.environ.get("HF_HOME", "")]


def _files(dirs: list[str]) -> set[str]:
    found = set()
    for d in dirs:
        for root, _, names in os.walk(d) if d and os.path.isdir(d) else []:
            found.update(os.path.join(root, n) for n in names)
    return found


def _warm_up(model: str) -> None:
    """Load VGGish once, so kadtk's parallel workers do not all download it at the same time."""
    if model == "vggish":
        import torch

        torch.hub.load("harritaylor/torchvggish", "vggish")


def run(request: dict) -> dict:
    device = _device(request["device"])
    import torch

    options = request["options"]
    model = options["model"]
    work = request["paths"]["work_dir"]
    before = _files(_cache_dirs())
    _warm_up(model)
    out_csv = os.path.join(work, f"kadtk-{model}.csv")
    cmd = [_bin("kadtk"), model, request["reference"]["dir"], request["generated"]["dir"],
           "--csv", out_csv, "--device", device, "-w", str(request["workers"])]
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          env=dict(os.environ), check=False)
    print(proc.stdout, flush=True)  # the plugin log
    if proc.returncode != 0 or not os.path.exists(out_csv):
        tail = "\n".join(proc.stdout.splitlines()[-TAIL:])
        raise RuntimeError(f"kadtk exited with code {proc.returncode}:\n{tail}")
    with open(out_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    warnings = []
    fetched = sorted(_files(_cache_dirs()) - before)
    if fetched:
        warnings.append({"code": "NETWORK_FETCH",
                         "message": f"Downloaded {len(fetched)} file(s): " + ", ".join(os.path.basename(f) for f in fetched)})
    cuda = device == "cuda"
    return {
        "scores": [{"name": "kad", "value": float(rows[-1]["score"]), "kind": "set"}],
        "upstream": {"package": "kadtk", "version": importlib.metadata.version("kadtk"), "invocation": " ".join(cmd)},
        "env": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "torch_threads": torch.get_num_threads(),  # in the wrapper; kadtk runs with the same settings
            "cuda_available": torch.cuda.is_available(),
            "device": device,
            "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
            "tensorflow": importlib.metadata.version("tensorflow"),
            **({"remote_code": REMOTE_CODE_VGGISH} if model == "vggish" else {}),
        },
        "warnings": warnings,
    }


def prefetch(metric_id: str, options: dict) -> dict:
    """Do what the kadtk command does at start-up (build every model loader, which downloads the
    CLAP checkpoints into kadtk's package folder), then load this metric's model once."""
    _device("cpu")
    from kadtk.model_loader import get_all_models

    before = _files(_cache_dirs())
    models = {m.name: m for m in get_all_models()}
    models[options["model"]].load_model()
    after = _files(_cache_dirs())
    return {"downloaded": sorted(after - before), "notes": [f"kadtk model {options['model']} loaded on the CPU"]}
