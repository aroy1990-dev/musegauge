"""Plugin clapscore_laion: CLAP cosine between each clip and its prompt (spec section 9.4).

A harness-defined metric. The steps follow the manifest definition; every embedding comes from
laion-clap itself. Upstream code is imported inside functions only.
"""

from __future__ import annotations

import importlib.metadata
import platform
import random

# The checkpoint, plus the three tokenizers that `import laion_clap` loads at import time
# (laion_clap/training/data.py lines 44-46) and roberta-base for the text tower.
HF_REPOS = ("lukewys/laion_clap", "roberta-base", "bert-base-uncased", "facebook/bart-base")


def _resolve_device(torch, requested: str) -> str:
    if requested == "cpu":
        return "cpu"
    if requested == "cuda" or (requested == "auto" and torch.cuda.is_available()):
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda was requested but torch.cuda.is_available() is False")
        return "cuda:0"
    if requested == "mps":
        raise RuntimeError("--device mps is not supported by this plugin")
    return "cpu"


def _seed(seed: int) -> None:
    import numpy
    import torch

    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)


def _cached_files() -> set[str]:
    from huggingface_hub import scan_cache_dir

    try:
        info = scan_cache_dir()
    except Exception:  # noqa: BLE001 - no cache folder yet
        return set()
    return {
        f"{repo.repo_id}/{f.file_name}"
        for repo in info.repos
        if repo.repo_id in HF_REPOS
        for rev in repo.revisions
        for f in rev.files
    }


def _checkpoint(options: dict) -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(options["checkpoint_repo"], options["checkpoint_file"])


def load_model(options: dict, device: str):
    import laion_clap

    model = laion_clap.CLAP_Module(enable_fusion=False, amodel=options["amodel"], device=device)
    model.load_ckpt(ckpt=_checkpoint(options), verbose=False)
    return model


def windows(audio, sample_rate: int, window_s: float, hop_s: float):
    """10 s windows with a 10 s hop; the last one zero padded. Returns (windows, real lengths)."""
    import numpy as np

    win, hop = int(window_s * sample_rate), int(hop_s * sample_rate)
    starts = range(0, max(len(audio), 1), hop)
    out = np.zeros((len(starts), win), dtype=np.float32)
    lengths = []
    for i, start in enumerate(starts):
        piece = audio[start : start + win]
        out[i, : len(piece)] = piece
        lengths.append(len(piece))
    return out, np.asarray(lengths, dtype=np.float64)


def clip_cosine(model, path: str, prompt: str, options: dict) -> float:
    import librosa
    import numpy as np
    from laion_clap.training.data import float32_to_int16, int16_to_float32

    sr = options["sample_rate_hz"]
    audio, _ = librosa.load(path, sr=sr, mono=True)
    audio = int16_to_float32(float32_to_int16(audio))
    wins, lengths = windows(audio, sr, options["window_s"], options["hop_s"])
    emb = model.get_audio_embedding_from_data(wins, use_tensor=False)  # (n_windows, 512)
    audio_emb = (emb * lengths[:, None]).sum(axis=0) / lengths.sum()
    text_emb = model.get_text_embedding([prompt], use_tensor=False)[0]
    return float(np.dot(audio_emb, text_emb) / (np.linalg.norm(audio_emb) * np.linalg.norm(text_emb)))


def run(request: dict) -> dict:
    import os

    import torch

    device = _resolve_device(torch, request["device"])
    _seed(request["seed"])
    options = request["options"]
    before = _cached_files()
    model = load_model(options, device)
    fetched = sorted(_cached_files() - before)

    gen = request["generated"]
    clip_scores, failed = [], []
    for clip in gen["clips"]:
        if not clip["prompt"]:
            failed.append({"clip_id": clip["clip_id"], "reason": "no_prompt"})
            continue
        try:
            value = clip_cosine(model, os.path.join(gen["dir"], clip["file"]), clip["prompt"], options)
            clip_scores.append({"clip_id": clip["clip_id"], "scores": {"clap_cosine": value}})
        except Exception as exc:  # noqa: BLE001 - one bad clip must not fail the metric
            failed.append({"clip_id": clip["clip_id"], "reason": f"{type(exc).__name__}: {exc}"})

    warnings = []
    if fetched:
        warnings.append({"code": "NETWORK_FETCH", "message": "Downloaded from huggingface.co: " + ", ".join(fetched)})
    is_cuda = device.startswith("cuda")
    return {
        "clip_scores": clip_scores,
        "clips_failed": failed,
        "upstream": {
            "package": "laion-clap",
            "version": importlib.metadata.version("laion-clap"),
            "invocation": (
                f"laion_clap.CLAP_Module(enable_fusion=False, amodel={options['amodel']!r}, device={device!r}); "
                f"load_ckpt(ckpt={options['checkpoint_file']!r}); get_audio_embedding_from_data(windows); "
                "get_text_embedding([prompt]); one clip per call"
            ),
        },
        "env": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cuda" if is_cuda else "cpu",
            "gpu_name": torch.cuda.get_device_name(0) if is_cuda else None,
            "torch_cuda": torch.version.cuda,
            "torch_threads": torch.get_num_threads(),
            "transformers": importlib.metadata.version("transformers"),
            "librosa": importlib.metadata.version("librosa"),
            "numpy": importlib.metadata.version("numpy"),
        },
        "warnings": warnings,
    }


def prefetch(metric_id: str, options: dict) -> dict:
    """Download the checkpoint and build the model once on the CPU (fills the tokenizer cache)."""
    before = _cached_files()
    load_model(options, "cpu")
    after = _cached_files()
    return {"downloaded": sorted(after - before), "notes": [f"cached files: {', '.join(sorted(after))}"]}
