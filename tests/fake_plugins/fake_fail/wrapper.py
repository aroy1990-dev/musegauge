"""Test plugin fake_fail: always raises."""

from __future__ import annotations


def run(request):
    raise RuntimeError("fake_fail always fails")


def prefetch(metric_id, options):
    raise RuntimeError("fake_fail always fails")
