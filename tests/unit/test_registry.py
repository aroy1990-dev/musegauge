"""Plugin manifests, discovery, suites and metric resolution (spec sections 5, 6.2, 7.4)."""

from __future__ import annotations

import shutil

import pytest
import yaml

from musegauge.errors import ManifestError, UsageError
from musegauge.registry import Registry, is_metric_id, load_plugin, load_suite


@pytest.fixture
def plugin_copy(tmp_path, fake_plugin_root):
    """A writable copy of fake_clip under tmp_path/plugins."""
    root = tmp_path / "plugins"
    shutil.copytree(fake_plugin_root / "fake_clip", root / "fake_clip")
    return root / "fake_clip"


def edit_manifest(folder, change):
    data = yaml.safe_load((folder / "manifest.yaml").read_text())
    change(data)
    (folder / "manifest.yaml").write_text(yaml.safe_dump(data))


@pytest.mark.parametrize("text", ["fad.vggish@1", "kad.clap-laion-music@1", "a1.b-2@10"])
def test_metric_id_pattern_accepts(text):
    assert is_metric_id(text)


@pytest.mark.parametrize("text", ["FAD.vggish", "fad.vggish", "fad.vggish@x", "fad.VGG@1", "fad@1", "fad.a.b@1"])
def test_metric_id_pattern_rejects(text):
    assert not is_metric_id(text)


def test_fake_plugins_load(fake_plugin_root):
    reg = Registry.discover([fake_plugin_root])
    assert {"fake_clip", "fake_set", "fake_fail", "fake_badclip", "fake_slow", "fake_np1", "fake_np2"} <= set(reg.plugins)
    assert reg.metric_index["fake.clip@1"] == "fake_clip"


@pytest.mark.parametrize("field", ["plugin_id", "kind", "python", "smoke", "needs", "metrics", "upstream"])
def test_manifest_missing_field_is_rejected(plugin_copy, field):
    edit_manifest(plugin_copy, lambda d: d.pop(field))
    with pytest.raises(ManifestError, match=field):
        load_plugin(plugin_copy)


def test_manifest_missing_metric_field_is_rejected(plugin_copy):
    edit_manifest(plugin_copy, lambda d: d["metrics"][0].pop("definition"))
    with pytest.raises(ManifestError, match="definition"):
        load_plugin(plugin_copy)


def test_manifest_plugin_id_must_equal_folder_name(plugin_copy):
    edit_manifest(plugin_copy, lambda d: d.update(plugin_id="other_name"))
    with pytest.raises(ManifestError, match="differs from the folder name"):
        load_plugin(plugin_copy)


@pytest.mark.parametrize("bad", ["FAKE.clip@1", "fake.clip", "fake.clip@x"])
def test_manifest_bad_metric_id_is_rejected(plugin_copy, bad):
    edit_manifest(plugin_copy, lambda d: d["metrics"][0].update(id=bad))
    with pytest.raises(ManifestError):
        load_plugin(plugin_copy)


def test_manifest_metric_family_must_match(plugin_copy):
    edit_manifest(plugin_copy, lambda d: d["metrics"][0].update(id="other.clip@1"))
    with pytest.raises(ManifestError, match="family"):
        load_plugin(plugin_copy)


def test_manifest_commercial_ok_must_be_yes_no_or_unknown(plugin_copy):
    edit_manifest(plugin_copy, lambda d: d["metrics"][0]["licence"].update(commercial_ok="maybe"))
    with pytest.raises(ManifestError, match="commercial_ok"):
        load_plugin(plugin_copy)


def test_manifest_needs_wrapper_file(plugin_copy):
    (plugin_copy / "wrapper.py").unlink()
    with pytest.raises(ManifestError, match="wrapper.py"):
        load_plugin(plugin_copy)


def test_two_plugins_with_the_same_plugin_id_are_an_error(tmp_path, fake_plugin_root):
    for root in ("a", "b"):
        shutil.copytree(fake_plugin_root / "fake_clip", tmp_path / root / "fake_clip")
    with pytest.raises(ManifestError, match="two plugins"):
        Registry.discover([tmp_path / "a", tmp_path / "b"])


def test_two_plugins_with_the_same_metric_id_are_an_error(tmp_path, fake_plugin_root):
    shutil.copytree(fake_plugin_root / "fake_clip", tmp_path / "r" / "fake_clip")
    shutil.copytree(fake_plugin_root / "fake_clip", tmp_path / "r" / "fake_clip2")
    edit_manifest(tmp_path / "r" / "fake_clip2", lambda d: d.update(plugin_id="fake_clip2"))
    with pytest.raises(ManifestError, match="defined by both"):
        Registry.discover([tmp_path / "r"])


def test_bundled_suites_load_and_highest_version_wins(tmp_path):
    reg = Registry.discover([])
    assert reg.suite("t2m-basic").ref == "t2m-basic@1"
    assert reg.suite("t2m-full@1").metrics[-1] == "kad.clap-laion-music@1"
    assert reg.suite("t2m-full@1").default_reference is None
    for v in (1, 2):
        (tmp_path / f"s@{v}.yaml").write_text(yaml.safe_dump(
            {"schema": 1, "suite_id": "s", "version": v, "description": "", "metrics": [f"fake.clip@{v}"]}))
        reg.suites.setdefault("s", {})[v] = load_suite(tmp_path / f"s@{v}.yaml")
    assert reg.suite("s").version == 2
    assert reg.suite("s@1").version == 1
    with pytest.raises(UsageError):
        reg.suite("s@3")


def test_suite_file_name_must_match_contents(tmp_path):
    (tmp_path / "s@2.yaml").write_text(yaml.safe_dump(
        {"schema": 1, "suite_id": "s", "version": 1, "description": "", "metrics": ["a.b@1"]}))
    with pytest.raises(ManifestError, match="match the file name"):
        load_suite(tmp_path / "s@2.yaml")


def test_resolve_metrics(fake_plugin_root):
    reg = Registry.discover([fake_plugin_root])
    ids, suite = reg.resolve_metrics(None, ["fake.set@1", "fake.clip@1", "fake.set@1"])
    assert ids == ["fake.set@1", "fake.clip@1"] and suite is None
    assert reg.group_by_plugin(ids) == {"fake_set": ["fake.set@1"], "fake_clip": ["fake.clip@1"]}
    with pytest.raises(UsageError, match="cannot be combined"):
        reg.resolve_metrics("t2m-basic", ["fake.clip@1"])
    with pytest.raises(UsageError, match="unknown metric"):
        reg.resolve_metrics(None, ["fake.nothing@1"])
    with pytest.raises(UsageError, match="not a metric id"):
        reg.resolve_metrics(None, ["fake"])
    ids, suite = reg.resolve_metrics("t2m-basic", None)  # the built-in plugins exist since M5
    assert suite.ref == "t2m-basic@1" and ids == suite.metrics


def test_lock_path_for_platform(fake_plugin_root, tmp_path):
    plugin = load_plugin(fake_plugin_root / "fake_clip")
    assert plugin.lock_path("linux-x86_64").name == "linux-x86_64.txt"
    assert plugin.lock_path("macos-arm64") is None
