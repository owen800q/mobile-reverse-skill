#!/usr/bin/env bash
set -euo pipefail

app="${1:?usage: runtime_test.sh APP.app CONFIG.json [EXPECTED_PATTERN]}"
config="${2:?usage: runtime_test.sh APP.app CONFIG.json [EXPECTED_PATTERN]}"
expected="${3:-QBDIFixture!}"
timeout_seconds="${QBDI_TRACE_TIMEOUT:-45}"
trace_root="/tmp/QBDITracer"
run_root="${QBDI_TEST_OUTPUT:-$PWD/test-output/qbdi-runtime}"

if [ "$(uname -m)" != "arm64" ]; then
  echo "runtime trace requires Apple Silicon" >&2
  exit 2
fi
if [ ! -d "$app" ] || [ ! -f "$config" ]; then
  echo "missing app or config" >&2
  exit 2
fi

mkdir -p "$trace_root" "$run_root/preexisting-logs" "$run_root/results"
cp "$config" "$trace_root/config.json"

# Preserve prior trace logs instead of deleting them.
find /tmp -maxdepth 1 -type f -name 'qbdi_trace_*.log' -exec mv {} "$run_root/preexisting-logs/" \; 2>/dev/null || true

started="$(date +%s)"
open "$app"

found=""
while [ "$(($(date +%s) - started))" -lt "$timeout_seconds" ]; do
  found="$(find /tmp -maxdepth 1 -type f -name 'qbdi_trace_*.log' -print -quit 2>/dev/null || true)"
  if [ -n "$found" ] && grep -q "$expected" "$found"; then
    break
  fi
  sleep 1
done

if [ -z "$found" ]; then
  echo "no qbdi_trace log appeared within ${timeout_seconds}s" >&2
  exit 1
fi
cp "$found" "$run_root/results/"
if ! grep -q "$expected" "$found"; then
  echo "trace log did not contain expected pattern: $expected" >&2
  sed -n '1,240p' "$found" >&2
  exit 1
fi
if ! grep -Eq '^0x[0-9a-f]+ \([^!]+!0x[0-9a-f]+\):' "$found"; then
  echo "trace log has no instruction records" >&2
  sed -n '1,240p' "$found" >&2
  exit 1
fi

echo "trace_log=$found"
grep -m 5 "$expected" "$found"
