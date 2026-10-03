"""Plain step-by-step laion-clap script for the CLAP score (spec sections 9.4 and 12, M4).

The CLAP score is harness-defined, so no upstream command exists to compare with. This script
calls the laion-clap functions directly, step by step, without any harness code:
    ENV/bin/python clap_direct.py --gen DIR --prompts PROMPTS.jsonl --out FILE
Device: cuda if visible, else cpu (hide GPUs with CUDA_VISIBLE_DEVICES= for cpu).
"""

import argparse
import importlib.metadata
import json
import os
import platform

import laion_clap
import librosa
import numpy as np
import torch
from huggingface_hub import hf_hub_download
from laion_clap.training.data import float32_to_int16, int16_to_float32

SR = 48000
WIN = 10 * SR  # 10 s windows
HOP = 10 * SR  # 10 s hop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    prompts = {}
    with open(args.prompts) as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                prompts[row["clip_id"]] = row["prompt"]

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base", device=device)
    model.load_ckpt(ckpt=hf_hub_download("lukewys/laion_clap", "music_audioset_epoch_15_esc_90.14.pt"), verbose=False)

    per_clip = {}
    for name in sorted(f for f in os.listdir(args.gen) if f.endswith(".wav")):
        clip_id = os.path.splitext(name)[0]
        # 1. load, mono, 48 kHz
        audio, _ = librosa.load(os.path.join(args.gen, name), sr=SR, mono=True)
        # 2. int16 round trip
        audio = int16_to_float32(float32_to_int16(audio))
        # 3. 10 s windows, 10 s hop, zero pad the last one, remember real lengths
        starts = list(range(0, len(audio), HOP))
        wins = np.zeros((len(starts), WIN), dtype=np.float32)
        lengths = np.zeros(len(starts))
        for i, s in enumerate(starts):
            piece = audio[s : s + WIN]
            wins[i, : len(piece)] = piece
            lengths[i] = len(piece)
        # 4. embed each window, weighted mean
        emb = model.get_audio_embedding_from_data(wins, use_tensor=False)
        a = (emb * lengths[:, None]).sum(axis=0) / lengths.sum()
        # 5. embed the prompt
        t = model.get_text_embedding([prompts[clip_id]], use_tensor=False)[0]
        # 6. cosine similarity
        per_clip[clip_id] = {"clap_cosine": float(np.dot(a, t) / (np.linalg.norm(a) * np.linalg.norm(t)))}

    out = {
        "per_clip": per_clip,
        "device": "cuda" if device.startswith("cuda") else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if device.startswith("cuda") else None,
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "upstream_version": importlib.metadata.version("laion-clap"),
        "python": platform.python_version(),
        "invocation": "CLAP_Module(enable_fusion=False, amodel='HTSAT-base'); load_ckpt(music ckpt); "
                      "get_audio_embedding_from_data(windows); get_text_embedding([prompt])",
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
