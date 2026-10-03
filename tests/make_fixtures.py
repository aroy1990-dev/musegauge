"""Synthetic audio fixtures (spec section 11.2), built at test time with fixed seeds.

Scores on this audio mean nothing about quality. The fixtures test plumbing only.
No audio file is committed.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import soundfile as sf

N_SMALL = 12
SMALL_RATE = 32000
SMALL_SECONDS = 10.0


def synth_clip(rng: np.random.Generator, sample_rate: int, seconds: float) -> np.ndarray:
    """A mixture of sine tones and low-pass filtered noise, peak 0.5."""
    t = np.arange(round(sample_rate * seconds)) / sample_rate
    x = np.zeros_like(t)
    for _ in range(rng.integers(2, 5)):
        freq = rng.uniform(110.0, 1760.0)
        x += rng.uniform(0.2, 1.0) * np.sin(2 * np.pi * freq * t + rng.uniform(0, 2 * np.pi))
    width = int(rng.integers(4, 32))
    noise = np.convolve(rng.normal(size=t.size), np.ones(width) / width, mode="same")
    x += rng.uniform(0.05, 0.3) * noise
    return (0.5 * x / np.max(np.abs(x))).astype(np.float32)


def write_wav(path: Path, data: np.ndarray, sample_rate: int) -> Path:
    sf.write(str(path), data, sample_rate, subtype="PCM_16")
    return path


def make_set(folder: Path, prefix: str, seed: int, n: int = N_SMALL,
             sample_rate: int = SMALL_RATE, seconds: float = SMALL_SECONDS) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    for i in range(n):
        write_wav(folder / f"{prefix}_{i:03d}.wav", synth_clip(rng, sample_rate, seconds), sample_rate)
    return folder


def make_gen_small(root: Path) -> Path:
    return make_set(root / "gen_small", "gen", seed=1)


def make_ref_small(root: Path) -> Path:
    return make_set(root / "ref_small", "ref", seed=2)


def make_mixed_rates(root: Path) -> Path:
    folder = root / "mixed_rates"
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(3)
    for rate in (16000, 32000, 44100):
        write_wav(folder / f"rate_{rate}.wav", synth_clip(rng, rate, 2.0), rate)
    return folder


def make_short_clip(root: Path) -> Path:
    rng = np.random.default_rng(4)
    return write_wav(root / "short_clip.wav", synth_clip(rng, SMALL_RATE, 0.5), SMALL_RATE)


def make_broken_clip(root: Path) -> Path:
    path = root / "broken_clip.wav"
    path.write_bytes(np.random.default_rng(5).integers(0, 256, size=4096, dtype=np.uint8).tobytes())
    return path


def make_empty_file(root: Path) -> Path:
    path = root / "empty_file.wav"
    path.write_bytes(b"")
    return path


def prompt_for(clip_id: str) -> str:
    return f"synthetic test audio {clip_id}, tones and noise"


def write_prompts(root: Path, clip_ids: list[str]) -> tuple[Path, Path]:
    """prompts.csv and prompts.jsonl with one prompt per clip (section 6.1)."""
    csv_path, jsonl_path = root / "prompts.csv", root / "prompts.jsonl"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["clip_id", "prompt"])
        for cid in clip_ids:
            writer.writerow([cid, prompt_for(cid)])
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for cid in clip_ids:
            fh.write(json.dumps({"clip_id": cid, "prompt": prompt_for(cid)}) + "\n")
    return csv_path, jsonl_path


def make_all(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    gen = make_gen_small(root)
    prompts_csv, prompts_jsonl = write_prompts(root, [p.stem for p in sorted(gen.glob("*.wav"))])
    return {
        "gen_small": gen,
        "ref_small": make_ref_small(root),
        "mixed_rates": make_mixed_rates(root),
        "short_clip": make_short_clip(root),
        "broken_clip": make_broken_clip(root),
        "empty_file": make_empty_file(root),
        "prompts_csv": prompts_csv,
        "prompts_jsonl": prompts_jsonl,
    }


if __name__ == "__main__":
    import sys

    for name, path in make_all(Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures")).items():
        print(f"{name}: {path}")
