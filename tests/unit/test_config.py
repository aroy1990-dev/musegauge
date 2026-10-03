"""Paths, defaults and the environment of plugin processes (spec sections 4.2, 4.4)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from musegauge import config

SET_BY_CORE = {"MUSEGAUGE_HOME", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME", "PYTHONNOUSERSITE",
               "PYTHONPATH", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", *config.THREAD_ENV_VARS}
# Python itself may set LC_CTYPE in a child under the C locale (PEP 538 locale coercion).
SET_BY_PYTHON = {"LC_CTYPE"}


def test_home_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSEGAUGE_HOME", str(tmp_path / "mg"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert config.musegauge_home() == tmp_path / "mg"
    monkeypatch.delenv("MUSEGAUGE_HOME")
    assert config.musegauge_home() == tmp_path / "xdg" / "musegauge"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert config.musegauge_home() == Path.home().resolve() / ".cache" / "musegauge"


def test_envs_dir_override(monkeypatch, tmp_path):
    monkeypatch.delenv("MUSEGAUGE_ENVS_DIR", raising=False)
    assert config.envs_dir(tmp_path) == tmp_path / "envs"
    monkeypatch.setenv("MUSEGAUGE_ENVS_DIR", str(tmp_path / "opt"))
    assert config.envs_dir(tmp_path) == tmp_path / "opt"


def test_plugin_search_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSEGAUGE_PLUGIN_PATH", f"{tmp_path / 'a'}:{tmp_path / 'b'}:")
    assert config.plugin_search_paths() == [tmp_path / "a", tmp_path / "b"]


def test_platform_tag_on_this_machine():
    tag = config.platform_tag()
    assert tag.count("-") == 1
    if sys.platform == "linux" and config.platform.machine() == "x86_64":
        assert tag == "linux-x86_64"


def test_reference_parse(tmp_path):
    assert config.Reference.parse(None).kind == "none"
    bundled = config.Reference.parse("bundled:fma_pop")
    assert (bundled.kind, bundled.name) == ("bundled", "fma_pop")
    folder = config.Reference.parse(str(tmp_path))
    assert (folder.kind, folder.dir) == ("dir", tmp_path)


@pytest.fixture
def dirty_environ(monkeypatch):
    for key, value in {
        "SECRET_TOKEN": "x", "PYTHONPATH": "/core/site-packages", "VIRTUAL_ENV": "/core/.venv",
        "LD_PRELOAD": "/x.so", "PYTHONHOME": "/x", "CUDA_VISIBLE_DEVICES": "1", "SOX_PATH": "/bin/sox",
        "MUSEGAUGE_ANYTHING": "kept", "HTTPS_PROXY": "http://proxy:3128", "CONDA_PREFIX": "/conda",
    }.items():
        monkeypatch.setenv(key, value)


def test_plugin_env_has_only_allowed_variables(dirty_environ, tmp_path):
    env = config.plugin_process_env(tmp_path, no_fetch=False)
    allowed = set(config.PASSED_ENV_VARS) | SET_BY_CORE
    assert all(k in allowed or k.startswith("MUSEGAUGE_") for k in env)
    assert env["PYTHONPATH"] == str(config.RUNTIME_DIR)
    assert env["CUDA_VISIBLE_DEVICES"] == "1" and env["MUSEGAUGE_ANYTHING"] == "kept"
    assert env["HF_HOME"] == str(tmp_path / "weights" / "hf")
    assert env["TORCH_HOME"] == str(tmp_path / "weights" / "torch")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / "weights" / "xdg")
    assert env["PYTHONNOUSERSITE"] == "1"
    assert "HF_HUB_OFFLINE" not in env
    offline = config.plugin_process_env(tmp_path, no_fetch=True)
    assert offline["HF_HUB_OFFLINE"] == "1" and offline["TRANSFORMERS_OFFLINE"] == "1"


def test_child_process_sees_only_allowed_variables(dirty_environ, tmp_path):
    env = config.plugin_process_env(tmp_path, no_fetch=True)
    out = subprocess.run(
        [sys.executable, "-c", "import os, json; print(json.dumps(sorted(os.environ)))"],
        env=env, capture_output=True, text=True, check=True,
    )
    seen = set(json.loads(out.stdout))
    allowed = set(config.PASSED_ENV_VARS) | SET_BY_CORE | SET_BY_PYTHON
    unexpected = {k for k in seen if k not in allowed and not k.startswith("MUSEGAUGE_")}
    assert unexpected == set()
    assert not {"SECRET_TOKEN", "VIRTUAL_ENV", "LD_PRELOAD", "PYTHONHOME", "CONDA_PREFIX"} & seen


def test_threads_are_passed_only_when_set(dirty_environ, monkeypatch, tmp_path):
    for name in config.THREAD_ENV_VARS:
        monkeypatch.setenv(name, "99")  # set in the core's environment: never passed through
    plain = config.plugin_process_env(tmp_path, no_fetch=False)
    assert not set(config.THREAD_ENV_VARS) & set(plain)
    limited = config.plugin_process_env(tmp_path, no_fetch=False, threads=4)
    assert {name: limited[name] for name in config.THREAD_ENV_VARS} == {
        "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4"}


def test_no_fetch_makes_the_network_unreachable(dirty_environ, monkeypatch, tmp_path):
    monkeypatch.setenv("NO_PROXY", "github.com")
    normal = config.plugin_process_env(tmp_path, no_fetch=False)
    assert normal["HTTPS_PROXY"] == "http://proxy:3128" and normal["NO_PROXY"] == "github.com"
    offline = config.plugin_process_env(tmp_path, no_fetch=True)
    assert offline["HTTP_PROXY"] == offline["HTTPS_PROXY"] == config.NO_FETCH_PROXY
    assert offline["NO_PROXY"] == ""  # nothing bypasses the unreachable proxy

