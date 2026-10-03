"""Link or copy audio into folders owned by the tool (spec section 4.3, amendment A9).

Nothing here writes into the user's folders. Originals are only read. Both the generated audio
and the reference are staged fresh for every run and plugin, so caches that the upstream tools
write next to the audio are never reused across runs, devices or environments.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from musegauge.clips import Clip, list_audio_files, probe_one
from musegauge.errors import InputError

HASH_CACHE_NAME = "hash_cache.json"


def link_or_copy(src: Path, dst: Path) -> str:
    """Make dst a symbolic link to src. If that fails, copy. Returns 'symlink' or 'copy'."""
    try:
        os.symlink(src, dst)
        return "symlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def staged_name(clip: Clip) -> str:
    return f"{clip.clip_id}{clip.path.suffix.lower()}"


def stage_generated(clips: list[Clip], dest: Path) -> list[dict]:
    """Stage generated clips as dest/<clip_id>.<ext>. Returns the request's clip entries."""
    dest.mkdir(parents=True, exist_ok=False)
    entries = []
    for clip in clips:
        name = staged_name(clip)
        link_or_copy(clip.path, dest / name)
        entries.append(
            {
                "clip_id": clip.clip_id,
                "file": name,
                "prompt": clip.prompt,
                "duration_s": clip.duration_s,
                "sample_rate_hz": clip.sample_rate_hz,
                "channels": clip.channels,
            }
        )
    return entries


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class HashCache:
    """Remembers each file's SHA-256 by (path, size, modified time), in one small JSON file."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.entries: dict = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.entries = {}
        self.changed = False

    def sha256(self, file: Path) -> str:
        st = file.stat()
        key = str(file.resolve())
        hit = self.entries.get(key)
        if hit and hit.get("size") == st.st_size and hit.get("mtime_ns") == st.st_mtime_ns:
            return hit["sha256"]
        value = file_sha256(file)
        self.entries[key] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": value}
        self.changed = True
        return value

    def save(self) -> None:
        if not self.changed:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(self.entries, allow_nan=False), encoding="utf-8")
        os.replace(tmp, self.path)
        self.changed = False


def file_hashes(files: dict[str, Path], refs_root: Path) -> dict[str, str]:
    """SHA-256 of each file (key -> digest), using the hash cache in refs_root."""
    cache = HashCache(refs_root / HASH_CACHE_NAME)
    out = {key: cache.sha256(path) for key, path in files.items()}
    cache.save()
    return out


def compute_ref_hash(file_hashes: dict[str, str]) -> str:
    """SHA-256 over the sorted list of (relative path, SHA-256 of content), as compact JSON."""
    items = sorted([rel, h] for rel, h in file_hashes.items())
    return hashlib.sha256(json.dumps(items, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class ReferenceSet:
    dir: Path
    files: list[Path]  # readable audio files, by name
    n_found: int
    ref_hash: str
    total_duration_s: float
    file_hashes: dict[str, str] = field(default_factory=dict)  # relative path -> SHA-256


def scan_reference(ref_dir: Path, refs_root: Path) -> ReferenceSet:
    """Find readable audio directly inside a reference folder and compute its ref_hash."""
    ref_dir = ref_dir.expanduser().resolve()
    if not ref_dir.is_dir():
        raise InputError(f"--reference {ref_dir} is not a folder")
    found = list_audio_files(ref_dir)
    readable, total = [], 0.0
    for f in found:
        info, _ = probe_one(f)
        if info is not None:
            readable.append(f)
            total += info.frames / info.samplerate
    if not readable:
        raise InputError(f"--reference {ref_dir}: no readable audio file ({len(found)} found)")
    cache = HashCache(refs_root / HASH_CACHE_NAME)
    hashes = {f.name: cache.sha256(f) for f in readable}
    cache.save()
    return ReferenceSet(ref_dir, readable, len(found), compute_ref_hash(hashes), total, hashes)


def stage_reference(refset: ReferenceSet, dest: Path) -> Path:
    """Stage the reference for one run and plugin, at dest (work/<run-id>/<plugin-id>/ref/).

    Amendment A9: no reuse across runs. A reused folder would carry embeddings and statistics
    that fadtk or kadtk made on another device or in another environment.
    """
    dest.mkdir(parents=True, exist_ok=False)
    for f in refset.files:
        link_or_copy(f, dest / f.name)
    return dest


def safe_rmtree(path: Path, inside: Path) -> None:
    """Delete path only if it lies strictly inside the given folder."""
    path, inside = path.resolve(), inside.resolve()
    if path == inside or inside not in path.parents:
        raise ValueError(f"refusing to delete {path}: not inside {inside}")
    if path.exists():
        shutil.rmtree(path)
