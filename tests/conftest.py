"""Shared test fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import make_fixtures
import pytest
import yaml

TESTS = Path(__file__).resolve().parent
FAKE_PLUGINS = TESTS / "fake_plugins"
DATA = TESTS / "data"
# Fakes that pin their own Python and numpy (isolation test). The others are "fast fakes".
PINNED_FAKES = {"fake_np1", "fake_np2"}
THIS_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory) -> dict[str, Path]:
    return make_fixtures.make_all(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture(scope="session")
def fake_plugin_root(tmp_path_factory) -> Path:
    """A copy of tests/fake_plugins. Fast fakes use the test interpreter's Python minor version
    (section 11.4), so building their environment needs no download."""
    root = tmp_path_factory.mktemp("fake_plugins")
    for src in sorted(FAKE_PLUGINS.iterdir()):
        if not src.is_dir() or src.name.startswith(("_", ".")):
            continue
        dst = root / src.name
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        if src.name not in PINNED_FAKES:
            manifest = yaml.safe_load((dst / "manifest.yaml").read_text())
            manifest["python"] = THIS_PYTHON
            (dst / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return root


@pytest.fixture(scope="session")
def session_home(tmp_path_factory) -> Path:
    """One MUSEGAUGE_HOME per test session, so fake environments are built once."""
    return tmp_path_factory.mktemp("mg_home")


@pytest.fixture
def mg_env(monkeypatch, session_home, fake_plugin_root) -> dict[str, str]:
    """Point the core at the session home and the fake plugins. No network for fast tests."""
    monkeypatch.setenv("MUSEGAUGE_HOME", str(session_home))
    monkeypatch.setenv("MUSEGAUGE_PLUGIN_PATH", str(fake_plugin_root))
    monkeypatch.delenv("MUSEGAUGE_ENVS_DIR", raising=False)
    monkeypatch.setenv("UV_PYTHON_DOWNLOADS", "never")
    monkeypatch.setenv("UV_OFFLINE", "1")
    return dict(os.environ)


def run_cli(args: list[str], env: dict[str, str], timeout: float = 300) -> subprocess.CompletedProcess:
    """Run `musegauge ARGS` in a fresh process, as a user would."""
    return subprocess.run(
        [sys.executable, "-m", "musegauge.cli", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def tree_digest(folder: Path) -> str:
    """SHA-256 over every path and file content under a folder (to prove it was not touched)."""
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        digest.update(str(path.relative_to(folder)).encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def pid_running(pid: int) -> bool:
    """True if the process exists and is not a zombie."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


GPU_MIN_FREE_MIB = 4000


def pick_gpu(min_free_mib: int = GPU_MIN_FREE_MIB) -> tuple[str, str, int] | None:
    """(index, name, free MiB) of the GPU with the most free memory, or None.

    The GPUs on the build machine are shared, so GPU tests use only this one device.
    """
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    out = subprocess.run([smi, "--query-gpu=index,name,memory.free", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=False)
    rows = [[x.strip() for x in line.split(",")] for line in out.stdout.strip().splitlines() if line]
    if out.returncode != 0 or not rows:
        return None
    index, name, free = max(rows, key=lambda r: int(r[2]))
    return (index, name, int(free)) if int(free) >= min_free_mib else None

