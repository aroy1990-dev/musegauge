"""Plugin aesthetics_audiobox: Audiobox Aesthetics (CE, CU, PC, PQ) for each clip (spec section 9.5).

Calls the upstream Python API. Upstream code is imported inside functions only.
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import random

AXES = ("CE", "CU", "PC", "PQ")
DEFAULT_BATCH_SIZE = 8
HF_REPO = "facebook/audiobox-aesthetics"


def _hide_gpus_if_cpu(device: str) -> None:
    # The upstream predictor has no device argument; it picks cuda, then mps, then cpu.
    # For --device cpu the GPUs are hidden before torch starts CUDA.
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""


def _check_device(torch, device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but torch.cuda.is_available() is False")
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("--device mps was requested but torch.backends.mps.is_available() is False")


def _seed(seed: int) -> None:
    import numpy
    import torch

    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)


def _cached_files() -> list[str]:
    from huggingface_hub import scan_cache_dir

    try:
        info = scan_cache_dir()
    except Exception:  # noqa: BLE001 - no cache folder yet
        return []
    return sorted(
        str(f.file_path)
        for repo in info.repos if repo.repo_id == HF_REPO
        for rev in repo.revisions for f in rev.files
    )


def _env(torch, device) -> dict:
    is_cuda = device.type == "cuda"
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torchaudio": importlib.metadata.version("torchaudio"),
        "cuda_available": torch.cuda.is_available(),
        "device": device.type,
        "gpu_name": torch.cuda.get_device_name(device) if is_cuda else None,
        "torch_cuda": torch.version.cuda,
        "torch_threads": torch.get_num_threads(),
        # torchaudio.load picks the first of these (ffmpeg, sox, soundfile order)
        "torchaudio_backends": _torchaudio_backends(),
    }


def _torchaudio_backends() -> list[str]:
    import torchaudio

    return list(torchaudio.list_audio_backends())


def _scores(row: dict) -> dict:
    return {axis: float(row[axis]) for axis in AXES}


def run(request: dict) -> dict:
    _hide_gpus_if_cpu(request["device"])
    import torch

    _check_device(torch, request["device"])
    _seed(request["seed"])
    from audiobox_aesthetics.infer import initialize_predictor

    before = _cached_files()
    predictor = initialize_predictor()
    fetched = sorted(set(_cached_files()) - set(before))

    gen = request["generated"]
    clips = gen["clips"]
    paths = {c["clip_id"]: os.path.join(gen["dir"], c["file"]) for c in clips}
    batch_size = request["batch_size"] or DEFAULT_BATCH_SIZE
    clip_scores, failed = [], []
    for start in range(0, len(clips), batch_size):
        batch = clips[start : start + batch_size]
        try:
            rows = predictor.forward([{"path": paths[c["clip_id"]]} for c in batch])
        except Exception:  # noqa: BLE001 - retry this batch one clip at a time (rule 6)
            rows = None
        if rows is not None:
            clip_scores += [{"clip_id": c["clip_id"], "scores": _scores(r)} for c, r in zip(batch, rows)]
            continue
        for clip in batch:
            try:
                (row,) = predictor.forward([{"path": paths[clip["clip_id"]]}])
                clip_scores.append({"clip_id": clip["clip_id"], "scores": _scores(row)})
            except Exception as exc:  # noqa: BLE001 - one bad clip must not fail the metric
                failed.append({"clip_id": clip["clip_id"], "reason": f"{type(exc).__name__}: {exc}"})

    warnings = []
    if fetched:
        warnings.append({"code": "NETWORK_FETCH",
                         "message": f"Downloaded from huggingface.co/{HF_REPO}: "
                                    + ", ".join(os.path.basename(f) for f in fetched)})
    return {
        "clip_scores": clip_scores,
        "clips_failed": failed,
        "upstream": {
            "package": "audiobox-aesthetics",
            "version": importlib.metadata.version("audiobox-aesthetics"),
            "invocation": "audiobox_aesthetics.infer.initialize_predictor(); "
                          f"predictor.forward([{{'path': FILE}}, ...]) in batches of {batch_size}",
        },
        "env": _env(torch, predictor.device),
        "warnings": warnings,
    }


def prefetch(metric_id: str, options: dict) -> dict:
    """Load the predictor once on the CPU, so the weights land in HF_HOME."""
    _hide_gpus_if_cpu("cpu")
    from audiobox_aesthetics.infer import initialize_predictor

    before = _cached_files()
    initialize_predictor()
    after = _cached_files()
    return {
        "downloaded": sorted(set(after) - set(before)),
        "notes": [f"cached files for {HF_REPO}: {len(after)}"],
    }
