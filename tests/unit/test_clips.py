"""Clips input and audio probe (spec section 6.1)."""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from musegauge.clips import probe_audio, read_folder, read_manifest, read_prompts
from musegauge.errors import InputError


def write_manifest(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_folder_mode_reads_audio_files_directly_inside(fixtures):
    cs = read_folder(fixtures["gen_small"])
    assert [c.clip_id for c in cs.clips] == [f"gen_{i:03d}" for i in range(12)]
    assert all(c.prompt is None for c in cs.clips)


def test_folder_mode_ignores_sub_folders_and_other_files(tmp_path, fixtures):
    shutil.copy(fixtures["gen_small"] / "gen_000.wav", tmp_path / "a.wav")
    (tmp_path / "sub").mkdir()
    shutil.copy(fixtures["gen_small"] / "gen_001.wav", tmp_path / "sub" / "b.wav")
    (tmp_path / "notes.txt").write_text("x")
    assert [c.clip_id for c in read_folder(tmp_path).clips] == ["a"]


def test_folder_mode_duplicate_stems_are_an_input_error(tmp_path, fixtures):
    shutil.copy(fixtures["gen_small"] / "gen_000.wav", tmp_path / "a.wav")
    shutil.copy(fixtures["gen_small"] / "gen_000.wav", tmp_path / "a.flac")
    with pytest.raises(InputError, match="same clip id"):
        read_folder(tmp_path)


def test_folder_mode_bad_file_name_is_an_input_error(tmp_path, fixtures):
    shutil.copy(fixtures["gen_small"] / "gen_000.wav", tmp_path / "has space.wav")
    with pytest.raises(InputError, match="valid clip ids"):
        read_folder(tmp_path)


def test_manifest_mode_relative_paths_extra_fields_and_hash(tmp_path, fixtures):
    shutil.copytree(fixtures["gen_small"], tmp_path / "audio")
    path = write_manifest(tmp_path / "clips.jsonl", [
        {"clip_id": "a", "path": "audio/gen_000.wav", "prompt": "p a", "prompt_id": "p1", "model": "m"},
        {"clip_id": "b", "path": str(tmp_path / "audio" / "gen_001.wav")},
    ])
    cs = read_manifest(path)
    assert cs.clips[0].path == (tmp_path / "audio" / "gen_000.wav").resolve()
    assert cs.clips[0].prompt == "p a" and cs.clips[0].prompt_id == "p1"
    assert cs.clips[0].extra == {"model": "m"}
    assert cs.clips[1].extra == {}
    assert cs.manifest_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_duplicate_ids_are_an_input_error(tmp_path):
    path = write_manifest(tmp_path / "c.jsonl", [{"clip_id": "a", "path": "x.wav"}, {"clip_id": "a", "path": "y.wav"}])
    with pytest.raises(InputError, match="duplicate clip_id"):
        read_manifest(path)


@pytest.mark.parametrize("row", [
    {"path": "x.wav"},
    {"clip_id": "a"},
    {"clip_id": "a b", "path": "x.wav"},
    {"clip_id": "a", "path": "x.wav", "prompt": "   "},
    {"clip_id": "a", "path": "x.wav", "prompt": 3},
])
def test_manifest_rows_that_break_the_contract(tmp_path, row):
    with pytest.raises(InputError):
        read_manifest(write_manifest(tmp_path / "c.jsonl", [row]))


def test_manifest_rejects_nan_and_bad_json(tmp_path):
    (tmp_path / "a.jsonl").write_text('{"clip_id": "a", "path": "x.wav", "score": NaN}\n')
    with pytest.raises(InputError, match="not valid JSON"):
        read_manifest(tmp_path / "a.jsonl")
    (tmp_path / "b.jsonl").write_text("{not json\n")
    with pytest.raises(InputError, match="not valid JSON"):
        read_manifest(tmp_path / "b.jsonl")


def test_missing_broken_and_empty_files_are_skipped_with_a_reason(tmp_path, fixtures):
    path = write_manifest(tmp_path / "c.jsonl", [
        {"clip_id": "good", "path": str(fixtures["gen_small"] / "gen_000.wav")},
        {"clip_id": "missing", "path": "nowhere.wav"},
        {"clip_id": "broken", "path": str(fixtures["broken_clip"])},
        {"clip_id": "empty", "path": str(fixtures["empty_file"])},
    ])
    ok, skipped = probe_audio(read_manifest(path).clips)
    assert [c.clip_id for c in ok] == ["good"]
    assert ok[0].duration_s == pytest.approx(10.0) and ok[0].sample_rate_hz == 32000 and ok[0].channels == 1
    reasons = {s["clip_id"]: s["reason"] for s in skipped}
    assert reasons["missing"] == "file not found"
    assert reasons["broken"].startswith("cannot read")
    assert reasons["empty"].startswith("cannot read") or reasons["empty"] == "zero length"


def test_probe_reads_each_sample_rate(fixtures):
    ok, skipped = probe_audio(read_folder(fixtures["mixed_rates"]).clips)
    assert not skipped
    assert sorted(c.sample_rate_hz for c in ok) == [16000, 32000, 44100]


def test_both_prompt_formats_give_the_same_prompts(fixtures):
    from_csv = read_prompts(fixtures["prompts_csv"])
    from_jsonl = read_prompts(fixtures["prompts_jsonl"])
    assert from_csv == from_jsonl and len(from_csv) == 12


def test_prompt_file_with_a_clip_that_has_no_prompt(tmp_path, fixtures):
    prompts = tmp_path / "p.csv"
    prompts.write_text("clip_id,prompt\ngen_000,a prompt\nnot_a_clip,other\n")
    cs = read_folder(fixtures["gen_small"], prompts)
    by_id = {c.clip_id: c.prompt for c in cs.clips}
    assert by_id["gen_000"] == "a prompt"
    assert by_id["gen_001"] is None
    assert cs.unknown_prompt_ids == ["not_a_clip"]


@pytest.mark.parametrize("name,text", [
    ("p.csv", "clip_id,text\na,b\n"),
    ("p.csv", "clip_id,prompt\na,\n"),
    ("p.csv", "clip_id,prompt\na,x\na,y\n"),
    ("p.jsonl", '{"clip_id": "a"}\n'),
    ("p.txt", "a,b\n"),
])
def test_bad_prompt_files(tmp_path, name, text):
    (tmp_path / name).write_text(text)
    with pytest.raises(InputError):
        read_prompts(tmp_path / name)


def test_folder_hash_depends_on_files_and_prompts_not_location(tmp_path, fixtures):
    a = read_folder(fixtures["gen_small"]).manifest_sha256
    copy_dir = shutil.copytree(fixtures["gen_small"], tmp_path / "elsewhere")
    assert read_folder(copy_dir).manifest_sha256 == a
    assert read_folder(copy_dir, fixtures["prompts_csv"]).manifest_sha256 != a
    (copy_dir / "gen_000.wav").rename(copy_dir / "gen_000.flac")
    assert read_folder(copy_dir).manifest_sha256 != a
