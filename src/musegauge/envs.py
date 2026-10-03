"""Plugin environments: the EnvBackend interface and the uv backend (spec section 4.2)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from musegauge import config
from musegauge.errors import EnvError, FatalEnvironmentError, NoLockError

if TYPE_CHECKING:
    from musegauge.registry import Plugin

READY = ".ready"
TAIL_LINES = 50


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Exclusive lock on a file, held for the body of the with block. Waits if taken."""
    import fcntl  # Unix only; Windows stops earlier with exit code 4

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def env_hash8(python_spec: str, lock_bytes: bytes) -> str:
    """First 8 hex characters of SHA-256 over the Python spec, a newline, and the lock bytes."""
    return hashlib.sha256(python_spec.encode("utf-8") + b"\n" + lock_bytes).hexdigest()[:8]


def find_uv() -> str:
    """The uv binary: from the uv Python package, else from PATH."""
    try:
        import uv

        return uv.find_uv_bin()
    except (ImportError, FileNotFoundError):
        found = shutil.which("uv")
        if found:
            return found
    raise FatalEnvironmentError("uv not found. Install it with: pip install uv")


def uv_version(uv_bin: str) -> str | None:
    """The version number printed by `uv --version`, for example 0.12.22."""
    try:
        out = subprocess.run([uv_bin, "--version"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    parts = out.stdout.split()
    return parts[1] if len(parts) > 1 else None


@dataclass
class Env:
    env_id: str
    path: Path
    python: Path
    lock_sha256: str | None  # None when built from requirements.in (--allow-unlocked)
    reproducible: bool


class EnvBackend(ABC):
    @abstractmethod
    def ensure(self, plugin: Plugin) -> Env:
        """Build the plugin's environment, or reuse it if it is ready."""


class _StepFailed(Exception):
    pass


class UvBackend(EnvBackend):
    def __init__(
        self,
        envs_dir: Path,
        home: Path,
        *,
        allow_unlocked: bool = False,
        platform_tag: str | None = None,
        uv_bin: str | None = None,
        log_path: Path | None = None,
    ):
        self.envs_dir = envs_dir
        self.home = home
        self.allow_unlocked = allow_unlocked
        self.platform_tag = platform_tag or config.platform_tag()
        self.uv_bin = uv_bin or find_uv()
        self.log_path = log_path  # build output is appended here when set

    def requirements_for(self, plugin: Plugin) -> tuple[Path, bool]:
        """(file to install from, reproducible). The lock for this platform, if there is one."""
        lock = plugin.lock_path(self.platform_tag)
        if lock is not None:
            return lock, True
        if self.allow_unlocked:
            return plugin.requirements_in, False
        raise NoLockError(
            f"plugin {plugin.plugin_id} has no lock file for {self.platform_tag}; "
            "skipped (use --allow-unlocked to resolve from requirements.in)"
        )

    def describe(self, plugin: Plugin) -> Env:
        """The Env this plugin would use, without building it."""
        req_path, reproducible = self.requirements_for(plugin)
        data = req_path.read_bytes()
        env_id = f"{plugin.plugin_id}-{env_hash8(plugin.python, data)}"
        folder = self.envs_dir / env_id
        return Env(
            env_id=env_id,
            path=folder,
            python=folder / "bin" / "python",
            lock_sha256=hashlib.sha256(data).hexdigest() if reproducible else None,
            reproducible=reproducible,
        )

    def ready(self, plugin: Plugin) -> bool:
        """True if the plugin's environment is already built (its .ready marker exists)."""
        return (self.describe(plugin).path / READY).exists()

    def ensure(self, plugin: Plugin) -> Env:
        env = self.describe(plugin)
        if (env.path / READY).exists():
            return env
        with file_lock(self.envs_dir / f"{env.env_id}.lock"):
            if (env.path / READY).exists():  # another run built it while we waited
                return env
            self._build(plugin, env)
        return env

    def _build(self, plugin: Plugin, env: Env) -> None:
        req_path, _ = self.requirements_for(plugin)
        output: list[str] = []
        if env.path.exists():
            shutil.rmtree(env.path)
        smoke = list(plugin.manifest["smoke"])
        smoke[0] = str(env.python if smoke[0] == "python" else env.path / "bin" / smoke[0])
        try:
            self._step([self.uv_bin, "venv", "--python", plugin.python, str(env.path)], output)
            self._step(
                [self.uv_bin, "pip", "install", "--python", str(env.python), "-r", str(req_path)],
                output,
            )
            self._step(
                smoke,
                output,
                env=config.plugin_process_env(self.home, no_fetch=False, runtime=False),
                cwd=env.path,
            )
            ready = {
                "env_id": env.env_id,
                "python_spec": plugin.python,
                "requirements": str(req_path),
                "uv_version": uv_version(self.uv_bin),
                "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            (env.path / READY).write_text(json.dumps(ready, indent=2) + "\n", encoding="utf-8")
        except (_StepFailed, OSError) as exc:
            shutil.rmtree(env.path, ignore_errors=True)
            tail = "\n".join("".join(output).splitlines()[-TAIL_LINES:])
            raise EnvError(
                f"environment {env.env_id} for plugin {plugin.plugin_id} failed to build: {exc}",
                tail,
            ) from exc

    def _step(
        self, cmd: list[str], output: list[str], env: dict | None = None, cwd: Path | None = None
    ) -> None:
        header = "$ " + " ".join(cmd) + "\n"
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=cwd,
            check=False,
        )
        output.extend([header, proc.stdout])
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(header + proc.stdout)
        if proc.returncode != 0:
            raise _StepFailed(f"`{' '.join(cmd[:3])} ...` exited with code {proc.returncode}")
