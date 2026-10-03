#!/usr/bin/env bash
# Run the golden tests of the real plugins by hand on a server (docs/TESTING_REAL_PLUGINS.md).
#
#   scripts/run_golden.sh CORES [extra pytest arguments]
#   scripts/run_golden.sh 16                    # all golden cases, CPU and GPU
#   scripts/run_golden.sh 16 -k "fad and cpu"   # a subset
#
# Runs under `nice -n 19` and `taskset -c 0-(CORES-1)`. CPU golden numbers depend on the thread
# count, so the stored CPU numbers are compared only when CORES equals the core count they were
# recorded with (otherwise those cases are skipped with a message). The plugin environments and
# weights must already be set up: `musegauge setup --all --fetch-weights`.
set -euo pipefail

if [[ $# -lt 1 || ! "$1" =~ ^[0-9]+$ || "$1" -lt 1 ]]; then
  echo "usage: $0 CORES [pytest arguments]" >&2
  exit 2
fi
cores=$1
shift
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"

echo "golden files:"
for f in tests/golden/*.json; do
  python3 - "$f" <<'PY'
import json, sys
path = sys.argv[1]
g = json.load(open(path))
conds = sorted({(dev, r.get("cpu_cores"), r["torch"]) for case in g["cases"].values() for dev, r in case.items()})
print(f"  {path}: " + "; ".join(f"{d} on {c} cores, torch {t}" for d, c, t in conds))
PY
done
echo "recording script: tests/golden_scripts/record_golden.py (numbers from this machine only)"
echo "running on cores 0-$((cores - 1)) with nice -n 19"

if command -v uv >/dev/null 2>&1; then runner=(uv run pytest); else runner=(.venv/bin/pytest); fi
exec nice -n 19 taskset -c "0-$((cores - 1))" "${runner[@]}" -m slow -v -s tests/integration/test_golden.py "$@"
