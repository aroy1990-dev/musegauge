"""Run the fadtk command directly, as a user would (golden test, spec section 11.6).

Run inside the fad_fadtk environment:
    ENV/bin/python fad_direct.py --model vggish --ref DIR|fma_pop --gen DIR --workers 8 --out FILE
Runs `fadtk MODEL REF GEN CSV -w N` and `... --inf` with fresh CSV files. fadtk picks the
device itself (hide GPUs with CUDA_VISIBLE_DEVICES= for cpu).
"""

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import subprocess
import sys

import torch


def last_row(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--gen", required=True)
    ap.add_argument("--workers", default="8")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    fadtk = os.path.join(os.path.dirname(sys.executable), "fadtk")
    work = os.path.dirname(os.path.abspath(args.out))
    plain, inf = os.path.join(work, "plain.csv"), os.path.join(work, "inf.csv")
    cmds = [[fadtk, args.model, args.ref, args.gen, plain, "-w", args.workers],
            [fadtk, args.model, args.ref, args.gen, inf, "-w", args.workers, "--inf"]]
    for cmd in cmds:
        subprocess.run(cmd, check=True, cwd=work)
    cuda = torch.cuda.is_available()
    out = {
        "scores": {"fad": float(last_row(plain)["score"]), "fad_inf": float(last_row(inf)["score"]),
                   "fad_inf_r2": float(last_row(inf)["inf_r2"])},
        "device": "cuda" if cuda else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "upstream_version": importlib.metadata.version("fadtk"),
        "python": platform.python_version(),
        "invocation": " ; ".join(" ".join(c[1:]) for c in cmds),
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
