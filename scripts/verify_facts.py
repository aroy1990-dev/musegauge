"""Re-check the upstream package facts that the build spec relies on (section 3).

Standard library only. Fetches the PyPI JSON page for each pinned version,
prints one line per check, and exits 1 if any check fails. A failure means an
upstream package or its rules changed: stop and tell Roy.
"""

from __future__ import annotations

import json
import sys
import urllib.request

PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"
TIMEOUT_S = 30

# (package, version, field, expected). For requires_python the value must be
# equal. For requires_dist one entry must equal the expected text, ignoring
# spaces and any environment marker after ";".
CHECKS = [
    ("fadtk", "1.1.0", "requires_python", "<=3.13,>=3.10"),
    ("fadtk", "1.1.0", "requires_dist", "torchvision>=0.22.0"),
    ("torchvision", "0.22.0", "requires_dist", "torch==2.7.0"),
    ("kadtk", "1.1.0", "requires_python", "<3.12,>=3.9"),
    ("kadtk", "1.1.0", "requires_dist", "torch<2.6,>=2.1"),
    ("audiobox-aesthetics", "0.0.4", "requires_python", ">=3.9"),
    ("audiobox-aesthetics", "0.0.4", "requires_dist", "torch>=2.2.0"),
    ("laion-clap", "1.1.7", "requires_dist", "numpy<2.0.0,>=1.23.5"),
]


def fetch_info(name: str, version: str) -> dict:
    url = PYPI_URL.format(name=name, version=version)
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        return json.load(resp)["info"]


def _norm(req: str) -> str:
    return req.split(";", 1)[0].replace(" ", "")


def check(info: dict, field: str, expected: str) -> tuple[bool, str]:
    value = info.get(field)
    if field == "requires_python":
        return value == expected, repr(value)
    entries = value or []
    for entry in entries:
        if _norm(entry) == _norm(expected):
            return True, repr(entry)
    return False, f"no matching entry among {len(entries)}"


def main() -> int:
    cache: dict[tuple[str, str], dict] = {}
    failures = 0
    for name, version, field, expected in CHECKS:
        key = (name, version)
        try:
            if key not in cache:
                cache[key] = fetch_info(name, version)
            ok, found = check(cache[key], field, expected)
        except (OSError, ValueError, KeyError) as exc:  # network or JSON problem fails the check
            ok, found = False, f"fetch error: {exc}"
        failures += not ok
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name}=={version}  {field} expected {expected!r}  found {found}")
    print(f"{len(CHECKS) - failures} of {len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
