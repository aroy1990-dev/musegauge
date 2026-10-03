"""Offline tests for the matching logic of scripts/verify_facts.py (no network)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_facts.py"
spec = importlib.util.spec_from_file_location("verify_facts", SCRIPT)
verify_facts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_facts)


def test_requires_python_must_be_equal():
    info = {"requires_python": "<=3.13,>=3.10"}
    assert verify_facts.check(info, "requires_python", "<=3.13,>=3.10")[0]
    assert not verify_facts.check(info, "requires_python", ">=3.10")[0]


def test_requires_dist_ignores_spaces_and_markers():
    info = {"requires_dist": ["numpy <2.0.0, >=1.23.5", 'torch==2.7.0; extra == "x"']}
    assert verify_facts.check(info, "requires_dist", "numpy<2.0.0,>=1.23.5")[0]
    assert verify_facts.check(info, "requires_dist", "torch==2.7.0")[0]


def test_requires_dist_missing_entry_fails():
    assert not verify_facts.check({"requires_dist": None}, "requires_dist", "torch==2.7.0")[0]
    assert not verify_facts.check({"requires_dist": ["torch>=2.7.0"]}, "requires_dist", "torch==2.7.0")[0]
