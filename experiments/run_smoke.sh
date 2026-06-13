#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${KERNELSCRIPT_REPO:-$ROOT/kernelscript}"
OUT="$ROOT/results/build/smoke_lo"
LOG="$ROOT/results/logs"
SRC="$ROOT/experiments/programs/smoke_lo.ks"
COMPILER="$REPO/_build/default/src/main.exe"

mkdir -p "$OUT" "$LOG"
rm -rf "$OUT"
mkdir -p "$OUT"

"$COMPILER" compile "$SRC" -o "$OUT" > "$LOG/smoke_lo.ks.stdout" 2> "$LOG/smoke_lo.ks.stderr"
(cd "$OUT" && make > "$LOG/smoke_lo.make.stdout" 2> "$LOG/smoke_lo.make.stderr")

if ! sudo -n true 2> /dev/null; then
  printf '{"status":"skipped","reason":"sudo -n is unavailable"}\n' > "$ROOT/results/smoke_summary.json"
  echo "smoke_lo skipped: sudo -n is unavailable"
  exit 0
fi

set +e
sudo -n "$OUT/smoke_lo" > "$LOG/smoke_lo.run.stdout" 2> "$LOG/smoke_lo.run.stderr"
rc=$?
set -e

if [ "$rc" -eq 0 ]; then
  status="ok"
else
  status="failed"
fi

python3 - "$ROOT/results/smoke_summary.json" "$status" "$rc" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(json.dumps({
    "status": sys.argv[2],
    "returncode": int(sys.argv[3]),
    "program": "smoke_lo",
    "target": "lo",
}, indent=2) + "\n", encoding="utf-8")
PY

cat "$LOG/smoke_lo.run.stdout"
cat "$LOG/smoke_lo.run.stderr" >&2
exit "$rc"
