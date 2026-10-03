"""Staging audio into tool-owned folders (spec section 4.3)."""

from __future__ import annotations

import os
import shutil

import pytest
from conftest import tree_digest

from musegauge import staging
from musegauge.clips import probe_audio, read_folder


def test_staging_leaves_the_input_folders_unchanged(tmp_path, fixtures):
    before_gen, before_ref = tree_digest(fixtures["gen_small"]), tree_digest(fixtures["ref_small"])
    ok, _ = probe_audio(read_folder(fixtures["gen_small"]).clips)
    entries = staging.stage_generated(ok, tmp_path / "work" / "gen")
    refset = staging.scan_reference(fixtures["ref_small"], tmp_path / "refs")
    ref_dir = staging.stage_reference(refset, tmp_path / "work" / "ref")
    assert tree_digest(fixtures["gen_small"]) == before_gen
    assert tree_digest(fixtures["ref_small"]) == before_ref
    assert len(entries) == 12 and entries[0]["file"] == "gen_000.wav"
    assert entries[0]["duration_s"] == pytest.approx(10.0)
    assert (tmp_path / "work" / "gen" / "gen_000.wav").is_symlink()
    assert sorted(os.listdir(ref_dir)) == [f"ref_{i:03d}.wav" for i in range(12)]


def test_symlink_falls_back_to_copy(tmp_path, fixtures, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("links not allowed here")

    monkeypatch.setattr(staging.os, "symlink", refuse)
    src = fixtures["gen_small"] / "gen_000.wav"
    assert staging.link_or_copy(src, tmp_path / "x.wav") == "copy"
    assert not (tmp_path / "x.wav").is_symlink()
    assert (tmp_path / "x.wav").read_bytes() == src.read_bytes()


def test_staged_name_lowercases_the_extension(tmp_path, fixtures):
    shutil.copy(fixtures["gen_small"] / "gen_000.wav", tmp_path / "Loud.WAV")
    ok, _ = probe_audio(read_folder(tmp_path).clips)
    assert staging.stage_generated(ok, tmp_path / "gen")[0]["file"] == "Loud.wav"


def test_changed_reference_file_gives_a_new_ref_hash(tmp_path, fixtures):
    ref = shutil.copytree(fixtures["ref_small"], tmp_path / "ref")
    refs_root = tmp_path / "refs"
    first = staging.scan_reference(ref, refs_root).ref_hash
    assert staging.scan_reference(ref, refs_root).ref_hash == first
    shutil.copy(fixtures["gen_small"] / "gen_000.wav", ref / "ref_000.wav")
    assert staging.scan_reference(ref, refs_root).ref_hash != first


def test_ref_hash_does_not_depend_on_folder_location(tmp_path, fixtures):
    a = shutil.copytree(fixtures["ref_small"], tmp_path / "a")
    b = shutil.copytree(fixtures["ref_small"], tmp_path / "b")
    assert staging.scan_reference(a, tmp_path / "refs").ref_hash == staging.scan_reference(b, tmp_path / "refs").ref_hash


def test_hash_cache_skips_unchanged_files(tmp_path, fixtures, monkeypatch):
    refs_root = tmp_path / "refs"
    staging.scan_reference(fixtures["ref_small"], refs_root)
    assert (refs_root / staging.HASH_CACHE_NAME).is_file()
    calls = []
    monkeypatch.setattr(staging, "file_sha256", lambda p: calls.append(p) or "0" * 64)
    staging.scan_reference(fixtures["ref_small"], refs_root)
    assert calls == []


def test_reference_is_staged_fresh_for_each_run(tmp_path, fixtures):
    """Amendment A9: a cache left by one run (say on the CPU) is never seen by the next."""
    refset = staging.scan_reference(fixtures["ref_small"], tmp_path / "refs")
    first = staging.stage_reference(refset, tmp_path / "work" / "run1" / "p" / "ref")
    (first / "embeddings").mkdir()  # a cache an upstream tool might leave
    second = staging.stage_reference(refset, tmp_path / "work" / "run2" / "p" / "ref")
    assert second != first and not (second / "embeddings").exists()
    assert sorted(p.name for p in second.iterdir()) == [f"ref_{i:03d}.wav" for i in range(12)]
    assert all((second / f.name).is_symlink() for f in refset.files)
    # only the hash cache file lives in refs/ (glob("*/") also matches files before Python 3.11)
    assert not [p for p in (tmp_path / "refs").iterdir() if p.is_dir()]


def test_unreadable_files_are_not_in_the_reference(tmp_path, fixtures):
    ref = shutil.copytree(fixtures["ref_small"], tmp_path / "ref")
    shutil.copy(fixtures["broken_clip"], ref / "broken.wav")
    refset = staging.scan_reference(ref, tmp_path / "refs")
    assert refset.n_found == 13 and len(refset.files) == 12


def test_reference_without_readable_audio_is_an_input_error(tmp_path, fixtures):
    from musegauge.errors import InputError

    (tmp_path / "ref").mkdir()
    shutil.copy(fixtures["broken_clip"], tmp_path / "ref" / "x.wav")
    with pytest.raises(InputError, match="no readable audio"):
        staging.scan_reference(tmp_path / "ref", tmp_path / "refs")


def test_safe_rmtree_deletes_only_inside(tmp_path):
    inside = tmp_path / "home" / "work" / "run1"
    inside.mkdir(parents=True)
    with pytest.raises(ValueError):
        staging.safe_rmtree(tmp_path / "home", tmp_path / "home" / "work")
    with pytest.raises(ValueError):
        staging.safe_rmtree(tmp_path / "home" / "work", tmp_path / "home" / "work")
    staging.safe_rmtree(inside, tmp_path / "home" / "work")
    assert not inside.exists() and (tmp_path / "home" / "work").is_dir()


def test_removing_staged_links_keeps_the_originals(tmp_path, fixtures):
    ok, _ = probe_audio(read_folder(fixtures["gen_small"]).clips)
    staging.stage_generated(ok, tmp_path / "work" / "run" / "gen")
    staging.safe_rmtree(tmp_path / "work" / "run", tmp_path / "work")
    assert len(list(fixtures["gen_small"].glob("*.wav"))) == 12
