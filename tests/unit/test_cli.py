"""The command line (spec section 7)."""

from __future__ import annotations

import json
import os
import shutil

import pytest
import yaml
from conftest import DATA, run_cli

from musegauge import __version__, cli


def test_version(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["--version"])
    assert info.value.code == 0 and capsys.readouterr().out.strip() == f"musegauge {__version__}"


def test_no_command_is_usage_error():
    assert cli.main([]) == 2


def help_of(*args) -> str:
    parser = cli.build_parser()
    if not args:
        return parser.format_help()
    sub = next(a for a in parser._actions if a.dest == "command")
    return sub.choices[args[0]].format_help()


def test_global_help_lists_commands_and_flags():
    text = help_of()
    for word in ("run", "list", "info", "doctor", "setup", "clean", "report", "validate",
                 "--home", "--verbose", "--version"):
        assert word in text
    assert "--plugin-path" not in text  # amendment A4


@pytest.mark.parametrize("command,flags", [
    ("run", ["--generated", "--manifest", "--prompts", "--reference", "--suite", "--metrics", "--out",
             "--device", "--workers", "--batch-size", "--seed", "--bootstrap", "--per-clip",
             "--timeout-min", "--keep-work", "--no-fetch", "--commercial", "--allow-unlocked", "--json",
             "bundled:NAME", "t2m-basic", "min(8, CPU count)", "1000"]),
    ("list", ["--json"]),
    ("info", ["METRIC_ID"]),
    ("doctor", ["OK, WARN or FAIL"]),
    ("setup", ["--suite", "--metrics", "--all", "--fetch-weights"]),
    ("clean", ["--envs", "--work", "--refs", "--weights", "--all", "--yes"]),
    ("report", ["RESULTS_JSON"]),
    ("validate", ["--clips", "--plugin", "--results"]),
])
def test_command_help_matches_section_7(command, flags):
    text = " ".join(help_of(command).split())
    for flag in flags:
        assert flag in text, flag


@pytest.mark.parametrize("args", [
    ["run"],
    ["run", "--generated", "a", "--manifest", "b"],
    ["run", "--generated", "a", "--suite", "t2m-basic", "--metrics", "fake.clip@1"],
    ["run", "--generated", "a", "--device", "tpu"],
    ["run", "--generated", "a", "--bootstrap", "-1"],
    ["run", "--manifest", "a.jsonl", "--prompts", "p.csv"],
    ["setup", "--suite", "t2m-basic", "--all"],
    ["validate"],
    ["clean"],
    ["info", "fake.nothing@1"],
    ["--plugin-path", "x", "list"],
])
def test_usage_errors_exit_2(args, mg_env):
    assert run_cli(args, mg_env).returncode == 2


def test_windows_is_refused(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "platform", "win32")
    assert cli.main(["run"]) == 4
    assert "Windows is not supported in 0.1" in capsys.readouterr().err


def test_list_text_and_json(mg_env):
    proc = run_cli(["list"], mg_env)
    assert proc.returncode == 0
    assert "t2m-basic@1" in proc.stdout and "fake.set@1" in proc.stdout and "reference" in proc.stdout
    data = json.loads(run_cli(["list", "--json"], mg_env).stdout)
    by_id = {m["metric_id"]: m for m in data["metrics"]}
    assert by_id["fake.set@1"] == {"metric_id": "fake.set@1", "kind": "set", "plugin_id": "fake_set",
                                   "needs": {"reference": True, "prompts": False}, "commercial_ok": "unknown"}
    assert {s["suite"] for s in data["suites"]} == {"t2m-basic@1", "t2m-full@1"}


def test_info_prints_the_manifest_entry(mg_env):
    proc = run_cli(["info", "fake.set@1"], mg_env)
    assert proc.returncode == 0
    entry = yaml.safe_load(proc.stdout)
    assert entry["metric_id"] == "fake.set@1" and entry["python"]
    assert set(entry["licence"]) == {"code", "weights", "data", "commercial_ok"}
    assert entry["licence"]["code"]["status"] == "not_applicable"
    for key in ("definition", "upstream", "runtime_downloads"):
        assert key in entry


@pytest.fixture
def no_network(monkeypatch):
    monkeypatch.setattr(cli, "_reachable", lambda url: (False, "network not used in tests"))


def test_doctor_ok_with_sox_through_sox_path(mg_env, no_network, monkeypatch, tmp_path, capsys):
    fake = tmp_path / "bin" / "my-sox"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\necho 'my-sox: SoX v0.0'\n")
    fake.chmod(0o755)
    monkeypatch.setenv("SOX_PATH", str(fake))
    code = cli.main(["doctor"])
    lines = capsys.readouterr().err.splitlines()
    names = [line.split(":", 1)[0].split(None, 1)[1] for line in lines]
    assert names[:6] == ["platform", "uv", "sox", "ffmpeg", "MUSEGAUGE_HOME", "nvidia-smi"]
    assert any(line.startswith("OK") and "my-sox" in line for line in lines)
    assert any(line.startswith("WARN") and "pypi.org" in line for line in lines)
    assert any("plugin fake_clip" in line for line in lines)
    assert all(line.split()[0] in ("OK", "WARN", "FAIL") for line in lines)
    assert code == (4 if any(line.startswith("FAIL") for line in lines) else 0)


def test_doctor_warns_without_sox(mg_env, no_network, monkeypatch, tmp_path, capsys):
    """Amendment A6: sox is not used by any 0.1 plugin, so missing sox is WARN, not FAIL."""
    monkeypatch.delenv("SOX_PATH", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    cli.main(["doctor"])
    lines = capsys.readouterr().err.splitlines()
    assert any(line.startswith("WARN") and "sox" in line for line in lines)
    assert not any(line.startswith("FAIL") and "sox" in line for line in lines)


def test_doctor_fails_without_writable_home(mg_env, no_network, monkeypatch, tmp_path, capsys):
    blocked = tmp_path / "file_not_folder"
    blocked.write_text("x")
    monkeypatch.setenv("MUSEGAUGE_HOME", str(blocked / "home"))
    assert cli.main(["doctor"]) == 4
    assert any(line.startswith("FAIL") and "MUSEGAUGE_HOME" in line for line in capsys.readouterr().err.splitlines())


def test_validate_modes(tmp_path, mg_env, fake_plugin_root):
    assert run_cli(["validate", "--clips", str(DATA / "clips.example.jsonl")], mg_env).returncode == 0
    assert run_cli(["validate", "--results", str(DATA / "results.example.json")], mg_env).returncode == 0
    assert run_cli(["validate", "--plugin", str(fake_plugin_root / "fake_set")], mg_env).returncode == 0
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"clip_id": "a b", "path": "x"}\n{"clip_id": "c"}\n{"clip_id": "c", "path": "y"}\nnot json\n')
    proc = run_cli(["validate", "--clips", str(bad)], mg_env)
    assert proc.returncode == 3
    assert len(proc.stderr.strip().splitlines()) == 4  # one line per problem
    plugin = shutil.copytree(fake_plugin_root / "fake_set", tmp_path / "wrong_name")
    proc = run_cli(["validate", "--plugin", str(plugin)], mg_env)
    assert proc.returncode == 3 and "differs from the folder name" in proc.stderr
    doc = json.loads((DATA / "results.example.json").read_text())
    del doc["run"]
    (tmp_path / "r.json").write_text(json.dumps(doc))
    proc = run_cli(["validate", "--results", str(tmp_path / "r.json")], mg_env)
    assert proc.returncode == 3 and "missing required field 'run'" in proc.stderr


def test_report_prints_the_report_card(mg_env):
    from musegauge.report import render

    proc = run_cli(["report", str(DATA / "results.example.json")], mg_env)
    assert proc.returncode == 0
    assert proc.stdout == render(json.loads((DATA / "results.example.json").read_text()))
    assert run_cli(["report", str(DATA / "clips.example.jsonl")], mg_env).returncode == 3


def make_home(tmp_path):
    home = tmp_path / "home"
    for name in ("envs", "work", "refs", "weights"):
        (home / name / "x").mkdir(parents=True)
        (home / name / "x" / "file.bin").write_bytes(b"0" * 2000)
    return home


def test_clean_asks_and_deletes_only_what_was_chosen(tmp_path, mg_env):
    home = make_home(tmp_path)
    env = dict(mg_env, MUSEGAUGE_HOME=str(home))
    proc = run_cli(["clean", "--work", "--refs"], env)  # no answer on stdin: nothing deleted
    assert proc.returncode == 0 and "2.0 KB" in proc.stderr and "nothing deleted" in proc.stderr
    assert (home / "work").exists()
    proc = run_cli(["clean", "--work", "--refs", "--yes"], env)
    assert proc.returncode == 0
    assert not (home / "work").exists() and not (home / "refs").exists()
    assert (home / "envs").exists() and (home / "weights").exists()
    proc = run_cli(["clean", "--all", "--yes"], env)
    assert proc.returncode == 0 and not (home / "envs").exists() and not (home / "weights").exists()
    assert home.exists()


def test_clean_refuses_paths_outside_home(tmp_path, mg_env):
    home = make_home(tmp_path)
    outside = tmp_path / "elsewhere_envs"
    outside.mkdir()
    env = dict(mg_env, MUSEGAUGE_HOME=str(home), MUSEGAUGE_ENVS_DIR=str(outside))
    proc = run_cli(["clean", "--envs", "--yes"], env)
    assert proc.returncode == 2 and "outside MUSEGAUGE_HOME" in proc.stderr
    assert outside.exists()


def test_setup_builds_envs_and_prefetches(tmp_path, mg_env):
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "home"))
    proc = run_cli(["setup", "--metrics", "fake.clip@1,fake.set@1", "--fetch-weights"], env)
    assert proc.returncode == 0, proc.stderr
    assert "prefetch fake.clip@1: ok" in proc.stderr and "note: fake_clip downloads nothing" in proc.stderr
    assert len(list((tmp_path / "home" / "envs").glob("fake_*/.ready"))) == 2
    assert list((tmp_path / "home" / "work").iterdir()) == []


def test_setup_reports_prefetch_failures(tmp_path, mg_env):
    env = dict(mg_env, MUSEGAUGE_HOME=str(tmp_path / "home"))
    proc = run_cli(["setup", "--metrics", "fake.fail@1,fake.clip@1", "--fetch-weights"], env)
    assert proc.returncode == 10
    assert "prefetch fake.fail@1: FAILED: RuntimeError: fake_fail always fails" in proc.stderr
    proc = run_cli(["setup", "--metrics", "fake.fail@1", "--fetch-weights"], env)
    assert proc.returncode == 5


def test_folder_size_counts_hard_links_once(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"0" * 1000)
    os.link(tmp_path / "a.bin", tmp_path / "b.bin")
    (tmp_path / "c.bin").symlink_to(tmp_path / "a.bin")
    assert cli.folder_size(tmp_path) == 1000 + len(str(tmp_path / "a.bin"))  # the link itself is small

