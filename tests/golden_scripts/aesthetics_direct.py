"""Call audiobox-aesthetics directly, with no harness code (golden test, spec section 11.6).

Run inside the aesthetics_audiobox environment:
    ENV/bin/python aesthetics_direct.py --gen DIR --out FILE [--batch-size 8]
Every .wav file directly in DIR is scored, sorted by name, in batches of --batch-size.
The device is chosen by the upstream predictor (hide GPUs with CUDA_VISIBLE_DEVICES= for CPU).
"""

import argparse
import importlib.metadata
import json
import os
import platform

import torch
from audiobox_aesthetics.infer import initialize_predictor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=8)
    args = ap.parse_args()
    files = sorted(f for f in os.listdir(args.gen) if f.endswith(".wav"))
    predictor = initialize_predictor()
    per_clip = {}
    for start in range(0, len(files), args.batch_size):
        batch = files[start : start + args.batch_size]
        rows = predictor.forward([{"path": os.path.join(args.gen, f)} for f in batch])
        for name, row in zip(batch, rows):
            per_clip[os.path.splitext(name)[0]] = {k: float(v) for k, v in row.items()}
    device = predictor.device
    out = {
        "per_clip": per_clip,
        "device": device.type,
        "gpu_name": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "upstream_version": importlib.metadata.version("audiobox-aesthetics"),
        "python": platform.python_version(),
        "batch_size": args.batch_size,
        "invocation": "initialize_predictor(); predictor.forward([{'path': f}, ...]) per batch",
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
