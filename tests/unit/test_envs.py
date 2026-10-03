"""Plugin environments: hash, build steps, .ready marker, file lock (spec section 4.2)."""

from __future__ import annotations

import os
import shutil
import threading

import pytest
import yaml

from musegauge.envs import READY, UvBackend, env_hash8
from musegauge.errors import EnvError, NoLockError
from musegauge.registry import load_plugin


def test_hash8_same_inputs_same_hash():
    assert env_hash8("3.11", b"numpy==1.26.4\n") == env_hash8("3.11", b"numpy==1.26.4\n")
    assert len(env_hash8("3.11", b"")) == 8


def test_hash8_changes_with_one_byte_or_the_python():
    base = env_hash8("3.11", b"numpy==1.26.4\n")
    assert env_hash8("3.11", b"numpy==1.26.5\n") != base
    assert env_hash8("3.12", b"numpy==1.26.4\n") != base


@pytest.fixture
def backend(tmp_path, mg_env):
    return UvBackend(tmp_path / "envs", tmp_path)


@pytest.fixture
def plugin(fake_plugin_root):
    return load_plugin(fake_plugin_root / "fake_clip")


def copy_plugin(fake_plugin_root, tmp_path, change=None, name="fake_clip"):
    dst = shutil.copytree(fake_plugin_root / name, tmp_path / "plugins" / name)
    if change:
        data = yaml.safe_load((dst / "manifest.yaml").read_text())
        change(data)
        (dst / "manifest.yaml").write_text(yaml.safe_dump(data))
    return load_plugin(dst)


def test_env_id_and_paths(backend, plugin, tmp_path):
    env = backend.describe(plugin)
    lock = (plugin.dir / "locks" / "linux-x86_64.txt").read_bytes()
    assert env.env_id == f"fake_clip-{env_hash8(plugin.python, lock)}"
    assert env.path == tmp_path / "envs" / env.env_id
    assert env.python == env.path / "bin" / "python"
    assert env.reproducible and len(env.lock_sha256) == 64


def test_build_writes_ready_last_and_reuses(backend, plugin, monkeypatch):
    env = backend.ensure(plugin)
    ready = env.path / READY
    assert ready.is_file() and env.python.exists()
    ready_mtime = os.lstat(ready).st_mtime_ns
    others = [p for p in env.path.rglob("*") if p != ready]
    assert others and all(os.lstat(p).st_mtime_ns <= ready_mtime for p in others)
    calls = []
    monkeypatch.setattr(UvBackend, "_build", lambda self, p, e: calls.append(p))
    assert backend.ensure(plugin) == env and calls == []


def test_partial_folder_without_ready_is_rebuilt(backend, plugin):
    env = backend.describe(plugin)
    env.path.mkdir(parents=True)
    (env.path / "half_built.txt").write_text("x")
    backend.ensure(plugin)
    assert not (env.path / "half_built.txt").exists() and (env.path / READY).is_file()


def test_failed_smoke_deletes_the_folder_and_reports_output(backend, fake_plugin_root, tmp_path):
    bad = copy_plugin(fake_plugin_root, tmp_path, lambda d: d.update(
        smoke=["python", "-c", "print('smoke output here'); raise SystemExit(3)"]))
    with pytest.raises(EnvError) as info:
        backend.ensure(bad)
    assert not backend.describe(bad).path.exists()
    assert "smoke output here" in info.value.output_tail
    assert "exited with code 3" in str(info.value)


def test_missing_lock_skips_unless_allowed(tmp_path, mg_env, fake_plugin_root):
    plugin = copy_plugin(fake_plugin_root, tmp_path, lambda d: d.update(locks={}))
    with pytest.raises(NoLockError, match="no lock file"):
        UvBackend(tmp_path / "envs", tmp_path).ensure(plugin)
    env = UvBackend(tmp_path / "envs", tmp_path, allow_unlocked=True).ensure(plugin)
    assert env.reproducible is False and env.lock_sha256 is None
    assert (env.path / READY).is_file()


def test_two_builds_at_once_one_waits_for_the_lock(tmp_path, mg_env, plugin, monkeypatch):
    builds = []
    original = UvBackend._build

    def counting_build(self, p, e):
        builds.append(threading.get_ident())
        original(self, p, e)

    monkeypatch.setattr(UvBackend, "_build", counting_build)
    results, errors = [], []

    def worker():
        try:
            results.append(UvBackend(tmp_path / "envs", tmp_path).ensure(plugin))
        except Exception as exc:  # noqa: BLE001 - report any failure from the thread
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert not errors
    assert len(results) == 2 and results[0] == results[1]
    assert len(builds) == 1
    assert (results[0].path / READY).is_file()
