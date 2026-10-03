"""Paths, environment variables and defaults."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path

import musegauge

AUDIO_EXTENSIONS = (".wav", ".flac", ".ogg", ".mp3")
DEFAULT_SUITE = "t2m-basic"
DEFAULT_DEVICE = "auto"
DEVICES = ("auto", "cpu", "cuda", "mps")
DEFAULT_SEED = 0
DEFAULT_BOOTSTRAP = 1000
CI_LEVEL = 0.95
BOOTSTRAP_BLOCK = 100

# Warning limits (section 10.2). These are the harness's own defaults, not values from any paper.
FEW_CLIPS_MIN = 100
SHORT_CLIP_S = 10.0
MIXED_DURATION_RATIO = 2.0
REF_SMALL_MIN = 100

# Variables passed from the core's environment to a plugin process (section 4.4).
PASSED_ENV_VARS = (
    "PATH",
    "HOME",
    "LANG",
    "TMPDIR",
    "CUDA_VISIBLE_DEVICES",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "SOX_PATH",
)
PASSED_ENV_PREFIX = "MUSEGAUGE_"
# With --no-fetch, plugin processes get this proxy for HTTP and HTTPS, so every download or
# network check fails at once as a connection error. torch.hub then uses its cache (its
# connection-error fallback), and nothing is fetched (GATE 2 item 3a). Port 9 on the local
# machine is expected to be closed.
NO_FETCH_PROXY = "http://127.0.0.1:9"
# Set for plugins only when `run --threads N` is given (GATE 2 decision, amendment A11).
THREAD_ENV_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")

RUNTIME_DIR = Path(musegauge.__file__).resolve().parent / "_runtime"
BUILTIN_PLUGINS_DIR = Path(musegauge.__file__).resolve().parent / "plugins"
SUITES_DIR = Path(musegauge.__file__).resolve().parent / "suites"
SCHEMAS_DIR = Path(musegauge.__file__).resolve().parent / "schemas"


def musegauge_home() -> Path:
    """MUSEGAUGE_HOME, else $XDG_CACHE_HOME/musegauge, else ~/.cache/musegauge."""
    home = os.environ.get("MUSEGAUGE_HOME")
    if home:
        return Path(home).expanduser().resolve()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return (base / "musegauge").resolve()


def envs_dir(home: Path) -> Path:
    """MUSEGAUGE_ENVS_DIR, else $MUSEGAUGE_HOME/envs (section 8.3)."""
    value = os.environ.get("MUSEGAUGE_ENVS_DIR")
    return Path(value).expanduser().resolve() if value else home / "envs"


def plugin_search_paths() -> list[Path]:
    """Folders from MUSEGAUGE_PLUGIN_PATH (colon separated). Each holds plugin folders."""
    value = os.environ.get("MUSEGAUGE_PLUGIN_PATH", "")
    return [Path(p).expanduser().resolve() for p in value.split(os.pathsep) if p]


def plugin_process_env(
    home: Path, no_fetch: bool, runtime: bool = True, threads: int | None = None
) -> dict[str, str]:
    """Environment for a process inside a plugin environment (section 4.4).

    Only PASSED_ENV_VARS and MUSEGAUGE_* pass through. The core's site-packages are
    never put on the path. With runtime=True, PYTHONPATH points at the runtime shim.
    With threads set, THREAD_ENV_VARS are set to that number; otherwise they are not passed,
    so the tools behave exactly as upstream.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k in PASSED_ENV_VARS or k.startswith(PASSED_ENV_PREFIX)
    }
    weights = home / "weights"
    env["MUSEGAUGE_HOME"] = str(home)
    env["HF_HOME"] = str(weights / "hf")
    env["TORCH_HOME"] = str(weights / "torch")
    env["XDG_CACHE_HOME"] = str(weights / "xdg")
    env["PYTHONNOUSERSITE"] = "1"
    if runtime:
        env["PYTHONPATH"] = str(RUNTIME_DIR)
    if no_fetch:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = NO_FETCH_PROXY
        env["NO_PROXY"] = ""
    if threads:
        env.update({name: str(threads) for name in THREAD_ENV_VARS})
    return env


def platform_tag() -> str:
    """Lock file key for this machine, for example linux-x86_64."""
    system = {"linux": "linux", "darwin": "macos"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    return f"{system}-{machine}"


def default_workers() -> int:
    return min(8, os.cpu_count() or 1)


@dataclass
class Reference:
    """The reference given with --reference or by the suite default."""

    kind: str  # dir, bundled or none
    name: str | None = None
    dir: Path | None = None

    @classmethod
    def parse(cls, value: str | None) -> Reference:
        if not value:
            return cls("none")
        if value.startswith("bundled:"):
            return cls("bundled", name=value[len("bundled:"):])
        return cls("dir", dir=Path(value).expanduser().resolve())

    def describe(self) -> str:
        if self.kind == "bundled":
            return f"bundled:{self.name}"
        if self.kind == "dir":
            return str(self.dir)
        return "none"


@dataclass
class RunConfig:
    """Everything one run needs, taken from the command line and the environment."""

    home: Path
    out: Path | None = None
    generated: Path | None = None
    manifest: Path | None = None
    prompts: Path | None = None
    reference: str | None = None
    suite: str | None = None
    metrics: list[str] | None = None
    device: str = DEFAULT_DEVICE
    workers: int = field(default_factory=default_workers)
    batch_size: int | None = None
    seed: int = DEFAULT_SEED
    bootstrap: int = DEFAULT_BOOTSTRAP
    per_clip: bool = False
    timeout_min: float | None = None
    keep_work: bool = False
    no_fetch: bool = False
    commercial: bool = False
    allow_unlocked: bool = False
    threads: int | None = None
    json: bool = False
    command: str = ""
    verbose: bool = False

    @property
    def envs_dir(self) -> Path:
        return envs_dir(self.home)

    @property
    def work_root(self) -> Path:
        return self.home / "work"

    @property
    def refs_root(self) -> Path:
        return self.home / "refs"

    @property
    def weights_dir(self) -> Path:
        return self.home / "weights"
