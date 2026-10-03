"""Plugin clapscore_laion with the real laion-clap package (spec section 12, M4). Slow."""

from __future__ import annotations

import csv
import os

import pytest
from conftest import load_json, run_cli

from musegauge import config

pytestmark = pytest.mark.slow
METRIC = "clapscore.laion-music@1"


@pytest.fixture
def real_env():
    env = dict(os.environ)
    env.pop("MUSEGAUGE_PLUGIN_PATH", None)
    return env


def test_prefetch_fills_the_weights_folder(real_env):
    proc = run_cli(["setup", "--metrics", METRIC, "--fetch-weights"], real_env, timeout=3600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert f"prefetch {METRIC}: ok" in proc.stderr
    hub = config.musegauge_home() / "weights" / "hf" / "hub"
    ckpts = list((hub / "models--lukewys--laion_clap" / "snapshots").glob("*/music_audioset_epoch_15_esc_90.14.pt"))
    assert ckpts and ckpts[0].stat().st_size > 2_000_000_000
    for repo in ("models--roberta-base", "models--bert-base-uncased", "models--facebook--bart-base"):
        assert (hub / repo).is_dir(), repo


def test_scores_are_cosines_and_clips_without_prompt_are_listed(fixtures, real_env, tmp_path):
    prompts = tmp_path / "prompts.csv"
    prompts.write_text("".join(fixtures["prompts_csv"].read_text().splitlines(keepends=True)[:11]))  # 10 clips
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--prompts", str(prompts),
                    "--metrics", METRIC, "--device", "cpu", "--no-fetch", "--out", str(out)], real_env, timeout=3600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    (m,) = load_json(out / "results.json")["metrics"]
    assert m["status"] == "ok" and m["scores"][0]["n"] == 10
    assert m["clips_failed"] == [{"clip_id": "gen_010", "reason": "no_prompt"},
                                 {"clip_id": "gen_011", "reason": "no_prompt"}]
    with open(out / m["per_clip_file"], newline="") as fh:
        values = [float(r["clap_cosine"]) for r in csv.DictReader(fh)]
    assert len(values) == 10 and all(-1.0 <= v <= 1.0 for v in values)
    assert "NETWORK_FETCH" not in [w["code"] for w in m["warnings"]]  # --no-fetch: nothing downloaded


def test_no_prompts_skips_the_metric(fixtures, real_env, tmp_path):
    out = tmp_path / "out"
    proc = run_cli(["run", "--generated", str(fixtures["gen_small"]), "--metrics", METRIC,
                    "--out", str(out)], real_env, timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    (m,) = load_json(out / "results.json")["metrics"]
    assert m["status"] == "skipped"
    assert [w["code"] for w in m["warnings"]] == ["UNKNOWN_LICENCE", "NO_PROMPTS"]  # licence warning: M6
