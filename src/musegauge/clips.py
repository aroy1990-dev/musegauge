"""Read the clips manifest or folder, read prompts, and probe audio (spec section 6.1)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import soundfile

from musegauge import schemas
from musegauge.config import AUDIO_EXTENSIONS
from musegauge.errors import InputError, SchemaError

KNOWN_FIELDS = ("clip_id", "path", "prompt", "prompt_id")
CLIP_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")  # same pattern as clip.schema.json


@dataclass
class Clip:
    clip_id: str
    path: Path  # absolute path of the original file; never written to
    prompt: str | None = None
    prompt_id: str | None = None
    extra: dict = field(default_factory=dict)
    duration_s: float | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None


@dataclass
class ClipSet:
    clips: list[Clip]
    manifest_sha256: str
    unknown_prompt_ids: list[str] = field(default_factory=list)


def _reject_constant(name: str):
    raise ValueError(f"{name} is not valid JSON")


def strict_json_loads(text: str):
    """json.loads that refuses NaN and Infinity (JSON has neither)."""
    return json.loads(text, parse_constant=_reject_constant)


def list_audio_files(folder: Path) -> list[Path]:
    """Files directly inside the folder (not sub-folders) with an audio extension, by name."""
    return sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )


def read_manifest(path: Path) -> ClipSet:
    """Read a clips file in JSON lines format. Relative paths are relative to its folder."""
    path = path.expanduser().resolve()
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read clips file {path}: {exc}") from exc
    clips: list[Clip] = []
    seen: set[str] = set()
    for lineno, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{path}:{lineno}"
        try:
            obj = strict_json_loads(line)
        except ValueError as exc:
            raise InputError(f"{where}: not valid JSON: {exc}") from exc
        try:
            schemas.check(obj, "clip")
        except SchemaError as exc:
            raise InputError(f"{where}: " + "; ".join(exc.problems)) from exc
        if obj["clip_id"] in seen:
            raise InputError(f"{where}: duplicate clip_id {obj['clip_id']!r}")
        seen.add(obj["clip_id"])
        clip_path = Path(obj["path"]).expanduser()
        if not clip_path.is_absolute():
            clip_path = path.parent / clip_path
        clips.append(
            Clip(
                clip_id=obj["clip_id"],
                path=clip_path.resolve(),
                prompt=obj.get("prompt"),
                prompt_id=obj.get("prompt_id"),
                extra={k: v for k, v in obj.items() if k not in KNOWN_FIELDS},
            )
        )
    if not clips:
        raise InputError(f"{path}: no clips in the file")
    return ClipSet(clips, hashlib.sha256(data).hexdigest())


def read_prompts(path: Path) -> dict[str, str]:
    """Prompts for folder mode from a .jsonl or .csv file with clip_id and prompt."""
    path = path.expanduser().resolve()
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read prompts file {path}: {exc}") from exc
    rows: list[tuple[str, dict]] = []
    if suffix == ".jsonl":
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                obj = strict_json_loads(line)
            except ValueError as exc:
                raise InputError(f"{path}:{lineno}: not valid JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise InputError(f"{path}:{lineno}: each line must be a JSON object")
            rows.append((f"{path}:{lineno}", obj))
    elif suffix == ".csv":
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames or not {"clip_id", "prompt"} <= set(reader.fieldnames):
            raise InputError(f"{path}: the CSV needs the columns clip_id and prompt")
        for lineno, row in enumerate(reader, start=2):
            rows.append((f"{path}:{lineno}", row))
    else:
        raise InputError(f"{path}: prompts file must end in .jsonl or .csv")
    prompts: dict[str, str] = {}
    for where, row in rows:
        clip_id, prompt = row.get("clip_id"), row.get("prompt")
        if not isinstance(clip_id, str) or not clip_id:
            raise InputError(f"{where}: missing clip_id")
        if not isinstance(prompt, str) or not prompt.strip():
            raise InputError(f"{where}: prompt for {clip_id!r} is missing or empty")
        if clip_id in prompts:
            raise InputError(f"{where}: duplicate clip_id {clip_id!r}")
        prompts[clip_id] = prompt
    return prompts


def read_folder(folder: Path, prompts_file: Path | None = None) -> ClipSet:
    """Folder mode: one clip per audio file directly inside the folder."""
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise InputError(f"--generated {folder} is not a folder")
    files = list_audio_files(folder)
    if not files:
        raise InputError(f"no {', '.join(AUDIO_EXTENSIONS)} files directly inside {folder}")
    by_stem: dict[str, Path] = {}
    for f in files:
        if f.stem in by_stem:
            raise InputError(
                f"two files with the same clip id {f.stem!r}: {by_stem[f.stem].name}, {f.name}"
            )
        by_stem[f.stem] = f
    bad = [f.name for f in files if not CLIP_ID_RE.match(f.stem)]
    if bad:
        raise InputError(
            "these file names do not give valid clip ids (letters, digits, '.', '_', '-'; "
            f"at most 128): {', '.join(bad)}"
        )
    prompts = read_prompts(prompts_file) if prompts_file else {}
    clips = [Clip(clip_id=stem, path=f, prompt=prompts.get(stem)) for stem, f in by_stem.items()]
    canonical = "".join(
        json.dumps(
            {"clip_id": c.clip_id, "file": c.path.name, "prompt": c.prompt},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
        for c in sorted(clips, key=lambda c: c.clip_id)
    )
    return ClipSet(
        clips,
        hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        unknown_prompt_ids=sorted(set(prompts) - set(by_stem)),
    )


def probe_one(path: Path) -> tuple[soundfile._SoundFileInfo | None, str | None]:
    """soundfile.info on one file. Returns (info, None) or (None, reason)."""
    if not path.is_file():
        return None, "file not found"
    try:
        info = soundfile.info(str(path))
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        return None, f"cannot read: {exc}"
    if info.frames <= 0 or info.samplerate <= 0:
        return None, "zero length"
    return info, None


def probe_audio(clips: list[Clip]) -> tuple[list[Clip], list[dict]]:
    """Split clips into readable ones (with duration, rate, channels) and skipped ones."""
    ok: list[Clip] = []
    skipped: list[dict] = []
    for clip in clips:
        info, reason = probe_one(clip.path)
        if info is None:
            skipped.append({"clip_id": clip.clip_id, "path": str(clip.path), "reason": reason})
            continue
        clip.duration_s = info.frames / info.samplerate
        clip.sample_rate_hz = int(info.samplerate)
        clip.channels = int(info.channels)
        ok.append(clip)
    return ok, skipped
