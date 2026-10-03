"""Run the kadtk command directly, as a user would (golden test, spec section 11.6).

Run inside the kad_kadtk environment:
    ENV/bin/python kad_direct.py --model vggish --ref DIR --gen DIR --workers 8 --out FILE
Runs `kadtk MODEL REF GEN --csv CSV --device D -w N`, with D = cuda if a GPU is visible, else cpu.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--gen", required=True)
    ap.add_argument("--workers", default="8")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    kadtk = os.path.join(os.path.dirname(sys.executable), "kadtk")
    work = os.path.dirname(os.path.abspath(args.out))
    out_csv = os.path.join(work, "kad.csv")
    cuda = torch.cuda.is_available()
    cmd = [kadtk, args.model, args.ref, args.gen, "--csv", out_csv, "--device", "cuda" if cuda else "cpu",
           "-w", args.workers]
    subprocess.run(cmd, check=True, cwd=work)
    with open(out_csv, newline="") as fh:
        score = float(list(csv.DictReader(fh))[-1]["score"])
    out = {
        "scores": {"kad": score},
        "device": "cuda" if cuda else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "upstream_version": importlib.metadata.version("kadtk"),
        "python": platform.python_version(),
        "invocation": " ".join(cmd[1:]),
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
