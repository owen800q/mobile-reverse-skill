#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

root="${CLOAKBROWSER_ROOT:-/repo/tools/cloakbrowser-ci/runtime}"
if [[ -n "${1:-}" ]]; then
  binary="$1"
elif [[ -n "${CLOAKBROWSER_BINARY:-}" ]]; then
  binary="$CLOAKBROWSER_BINARY"
elif [[ -s "$root/binary.path" ]]; then
  binary="$(sed -n '1p' "$root/binary.path")"
else
  binary="$root/browser/chrome"
fi
spec="${2:-${CLOAKBROWSER_PATCH_SPEC:-$here/patch-spec.json}}"
instances="${CLOAK_VERIFY_INSTANCES:-3}"

unset CLOAKBROWSER_LICENSE_KEY
tmp="$(mktemp -d /tmp/cloak-target-verify.XXXXXX)"
runners=()
profiles=()
cleanup() {
  for profile in "${profiles[@]:-}"; do
    pgrep -f -- "--user-data-dir=$profile" | xargs -r kill -TERM 2>/dev/null || true
  done
  for pid in "${runners[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  rm -rf -- "$tmp" 2>/dev/null || true
}
trap cleanup EXIT

set +e
timeout 20 "$binary" \
  --headless=new --no-sandbox --disable-gpu \
  --user-data-dir="$tmp/unpatched" \
  --remote-debugging-port=0 about:blank \
  >"$tmp/unpatched.log" 2>&1
baseline_rc=$?
set -e
if [[ "$baseline_rc" -ne 77 ]]; then
  echo "expected the unpatched no-key baseline to exit 77; got $baseline_rc" >&2
  sed -n '1,160p' "$tmp/unpatched.log" >&2
  exit 20
fi

for i in $(seq 1 "$instances"); do
  profile="$tmp/patched-$i"
  profiles+=("$profile")
  python "$here/runtime_patch.py" \
    --binary "$binary" --spec "$spec" --exec -- \
    --headless=new --no-sandbox --disable-gpu \
    --user-data-dir="$profile" --remote-debugging-port=0 about:blank \
    >"$tmp/patched-$i.log" 2>&1 &
  runners+=("$!")
done

ready=0
for i in $(seq 1 "$instances"); do
  profile="$tmp/patched-$i"
  ok=0
  for _ in $(seq 1 150); do
    if [[ -s "$profile/DevToolsActivePort" ]]; then
      port="$(sed -n '1p' "$profile/DevToolsActivePort")"
      if curl -fsS "http://127.0.0.1:$port/json/version" \
        >"$tmp/version-$i.json"; then
        ok=1
        break
      fi
    fi
    sleep 0.1
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "patched instance $i did not expose DevTools" >&2
    sed -n '1,200p' "$tmp/patched-$i.log" >&2
    continue
  fi
  ready=$((ready + 1))
  jq -r "[\"instance=$i\", .Browser, .webSocketDebuggerUrl] | @tsv" \
    "$tmp/version-$i.json"
done

echo "baseline_rc=$baseline_rc patched_concurrent_ready=$ready"
[[ "$ready" -eq "$instances" ]]
