#!/usr/bin/env bash
set -euo pipefail

root="${CLOAKBROWSER_ROOT:-/repo/tools/cloakbrowser-ci/runtime}"
if [[ -n "${CLOAKBROWSER_BINARY:-}" ]]; then
  binary="$CLOAKBROWSER_BINARY"
elif [[ -s "$root/binary.path" ]]; then
  binary="$(sed -n '1p' "$root/binary.path")"
else
  binary="$root/browser/chrome"
fi
spec="${CLOAKBROWSER_PATCH_SPEC:-/opt/cloakbrowser-ci/patch-spec.json}"

exec python /opt/cloakbrowser-ci/runtime_patch.py \
  --binary "$binary" \
  --spec "$spec" \
  --exec -- "$@"
