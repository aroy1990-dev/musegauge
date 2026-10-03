"""Find plugins and suites, check manifests, and resolve metric ids (spec sections 5, 6.2, 7.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from musegauge import config, schemas
from musegauge.errors import ManifestError, SchemaError, UsageError

METRIC_ID_RE = re.compile(r"^[a-z0-9]+\.[a-z0-9-]+@[0-9]+$")
SUITE_FILE_RE = re.compile(r"^([a-z0-9-]+)@([0-9]+)\.yaml$")


def is_metric_id(text: str) -> bool:
    return bool(METRIC_ID_RE.match(text))


@dataclass
class Plugin:
    """One plugin folder: manifest.yaml, wrapper.py, requirements.in and locks/."""

    dir: Path
    manifest: dict

    @property
    def plugin_id(self) -> str:
        return self.manifest["plugin_id"]

    @property
    def kind(self) -> str:
        return self.manifest["kind"]

    @property
    def python(self) -> str:
        return self.manifest["python"]

    @property
    def needs_reference(self) -> bool:
        return self.manifest["needs"]["reference"]

    @property
    def needs_prompts(self) -> bool:
        return self.manifest["needs"]["prompts"]

    @property
    def metrics(self) -> dict[str, dict]:
        return {m["id"]: m for m in self.manifest["metrics"]}

    @property
    def requirements_in(self) -> Path:
        return self.dir / self.manifest["requirements_in"]

    def lock_path(self, platform_tag: str) -> Path | None:
        """The lock file for this platform, or None if the manifest has none or it is missing."""
        rel = self.manifest["locks"].get(platform_tag)
        if rel is None:
            return None
        path = self.dir / rel
        return path if path.is_file() else None


@dataclass
class Suite:
    suite_id: str
    version: int
    data: dict
    path: Path

    @property
    def ref(self) -> str:
        return f"{self.suite_id}@{self.version}"

    @property
    def metrics(self) -> list[str]:
        return list(self.data["metrics"])

    @property
    def default_reference(self) -> str | None:
        return self.data.get("default_reference")


def _read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"{path}: cannot read YAML: {exc}") from exc


def manifest_problems(plugin_dir: Path, manifest: object) -> list[str]:
    """All reasons to reject a manifest (section 6.2). Empty means valid."""
    found = schemas.problems(manifest, "manifest")
    if found:
        return found
    assert isinstance(manifest, dict)
    if manifest["plugin_id"] != plugin_dir.name:
        found.append(
            f"plugin_id {manifest['plugin_id']!r} differs from the folder name {plugin_dir.name!r}"
        )
    seen = set()
    for metric in manifest["metrics"]:
        mid = metric["id"]
        if mid.split(".", 1)[0] != manifest["family"]:
            found.append(f"metric id {mid!r} does not start with the family {manifest['family']!r}")
        if mid in seen:
            found.append(f"metric id {mid!r} appears twice")
        seen.add(mid)
    for name in ("wrapper.py", manifest["requirements_in"]):
        if not (plugin_dir / name).is_file():
            found.append(f"missing file {name}")
    return found


def load_plugin(plugin_dir: Path) -> Plugin:
    path = plugin_dir / "manifest.yaml"
    if not path.is_file():
        raise ManifestError(f"{plugin_dir}: no manifest.yaml")
    manifest = _read_yaml(path)
    found = manifest_problems(plugin_dir, manifest)
    if found:
        raise ManifestError(f"{path}: invalid manifest: " + "; ".join(found))
    return Plugin(dir=plugin_dir.resolve(), manifest=manifest)


def _plugin_folders(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
    )


def load_suite(path: Path) -> Suite:
    match = SUITE_FILE_RE.match(path.name)
    if not match:
        raise ManifestError(f"{path}: suite file name must be <suite_id>@<version>.yaml")
    data = _read_yaml(path)
    try:
        schemas.check(data, "suite")
    except SchemaError as exc:
        raise ManifestError(f"{path}: invalid suite: " + "; ".join(exc.problems)) from exc
    if data["suite_id"] != match.group(1) or data["version"] != int(match.group(2)):
        raise ManifestError(f"{path}: suite_id and version must match the file name")
    return Suite(data["suite_id"], data["version"], data, path)


@dataclass
class Registry:
    plugins: dict[str, Plugin] = field(default_factory=dict)
    metric_index: dict[str, str] = field(default_factory=dict)  # metric id -> plugin id
    suites: dict[str, dict[int, Suite]] = field(default_factory=dict)

    @classmethod
    def discover(
        cls, plugin_roots: list[Path] | None = None, suites_dir: Path | None = None
    ) -> Registry:
        """Built-in plugins plus those under MUSEGAUGE_PLUGIN_PATH, and the bundled suites."""
        roots = [config.BUILTIN_PLUGINS_DIR] + (
            plugin_roots if plugin_roots is not None else config.plugin_search_paths()
        )
        reg = cls()
        for root in roots:
            for folder in _plugin_folders(root):
                reg._add(load_plugin(folder))
        sdir = suites_dir or config.SUITES_DIR
        for path in sorted(sdir.glob("*.yaml")):
            suite = load_suite(path)
            reg.suites.setdefault(suite.suite_id, {})[suite.version] = suite
        return reg

    def _add(self, plugin: Plugin) -> None:
        if plugin.plugin_id in self.plugins:
            other = self.plugins[plugin.plugin_id].dir
            raise ManifestError(
                f"two plugins with plugin_id {plugin.plugin_id!r}: {other} and {plugin.dir}"
            )
        for mid in plugin.metrics:
            if mid in self.metric_index:
                raise ManifestError(
                    f"metric id {mid!r} is defined by both {self.metric_index[mid]!r} "
                    f"and {plugin.plugin_id!r}"
                )
        self.plugins[plugin.plugin_id] = plugin
        for mid in plugin.metrics:
            self.metric_index[mid] = plugin.plugin_id

    def plugin_for(self, metric_id: str) -> Plugin:
        return self.plugins[self.metric_index[metric_id]]

    def metric(self, metric_id: str) -> dict:
        return self.plugin_for(metric_id).metrics[metric_id]

    def suite(self, name: str) -> Suite:
        """Look up NAME or NAME@N. Without @N, the highest version."""
        suite_id, _, version = name.partition("@")
        versions = self.suites.get(suite_id)
        if not versions:
            raise UsageError(f"unknown suite {suite_id!r}")
        if not version:
            return versions[max(versions)]
        if not version.isdigit() or int(version) not in versions:
            raise UsageError(f"unknown suite version {name!r}")
        return versions[int(version)]

    def resolve_metrics(
        self, suite: str | None, metrics: list[str] | None
    ) -> tuple[list[str], Suite | None]:
        """Metric ids to run, from --suite or --metrics, in the given order without repeats."""
        if suite and metrics:
            raise UsageError("--suite and --metrics cannot be combined")
        chosen = self.suite(suite) if suite else None
        ids = chosen.metrics if chosen else list(metrics or [])
        if not ids:
            raise UsageError("no metrics selected")
        out: list[str] = []
        for mid in ids:
            if not is_metric_id(mid):
                raise UsageError(f"{mid!r} is not a metric id (pattern family.variant@N)")
            if mid not in self.metric_index:
                where = f" (from suite {chosen.ref})" if chosen else ""
                raise UsageError(f"unknown metric {mid!r}{where}")
            if mid not in out:
                out.append(mid)
        return out, chosen

    def group_by_plugin(self, metric_ids: list[str]) -> dict[str, list[str]]:
        plan: dict[str, list[str]] = {}
        for mid in metric_ids:
            plan.setdefault(self.metric_index[mid], []).append(mid)
        return plan
