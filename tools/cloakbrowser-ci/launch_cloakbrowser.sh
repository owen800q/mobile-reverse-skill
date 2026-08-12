#!/usr/bin/env bash
set -euo pipefail

# Resolve siblings relative to this script rather than assuming the container's
# /opt/cloakbrowser-ci, so the launcher also works when run straight from a checkout
# (a headed local run, for instance - the image ships no X server).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="${CLOAKBROWSER_ROOT:-/repo/tools/cloakbrowser-ci/runtime}"
if [[ -n "${CLOAKBROWSER_BINARY:-}" ]]; then
  binary="$CLOAKBROWSER_BINARY"
elif [[ -s "$root/binary.path" ]]; then
  binary="$(sed -n '1p' "$root/binary.path")"
else
  binary="$root/browser/chrome"
fi
spec="${CLOAKBROWSER_PATCH_SPEC:-$here/patch-spec.json}"

exec python "$here/runtime_patch.py" \
  --binary "$binary" \
  --spec "$spec" \
  --exec -- "$@"
