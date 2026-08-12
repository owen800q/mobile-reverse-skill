#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

version="${CLOAKBROWSER_VERSION:-150.0.7871.114.6}"
platform="${CLOAKBROWSER_PLATFORM:-linux-x64}"
root="${CLOAKBROWSER_ROOT:-/repo/tools/cloakbrowser-ci/runtime}"
cache="$root/cache"
install="$root/browser"
archive_name="cloakbrowser-${platform}.tar.gz"
archive="$cache/$archive_name"
manifest="$cache/SHA256SUMS"
signature="$cache/SHA256SUMS.sig"
base="https://cloakbrowser.dev/releases/pro/chromium-v${version}"

mkdir -p "$cache"

if [[ ! -s "$manifest" || ! -s "$signature" ]]; then
  curl -fsSL "$base/SHA256SUMS" -o "$manifest"
  curl -fsSL "$base/SHA256SUMS.sig" -o "$signature"
fi

if [[ ! -s "$archive" ]]; then
  key="${CLOAKBROWSER_LICENSE_KEY:-}"
  if [[ -z "$key" ]]; then
    echo "CLOAKBROWSER_LICENSE_KEY is required on an empty browser cache." >&2
    exit 2
  fi
  tmp="$archive.part"
  trap 'rm -f "$tmp"' EXIT
  curl -fL --retry 3 \
    -H "Authorization: Bearer ${key}" \
    -H "X-Platform: ${platform}" \
    "https://cloakbrowser.dev/api/download/${version}" \
    -o "$tmp"
  mv "$tmp" "$archive"
  trap - EXIT
fi

python "$here/verify_release.py" \
  --archive "$archive" \
  --manifest "$manifest" \
  --signature "$signature" \
  --version "$version" \
  --archive-name "$archive_name"

rm -rf -- "$install"
mkdir -p "$install"
tar -xzf "$archive" -C "$install"

binary="$(find "$install" -type f \( -name chrome -o -name chromium \) -perm /111 -print -quit)"
if [[ -z "$binary" ]]; then
  echo "No executable chrome/chromium found after extraction." >&2
  exit 3
fi

expected="$(python -c 'import json; print(json.load(open("'"$here"'/patch-spec.json"))["sha256"])')"
actual="$(sha256sum "$binary" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "browser SHA-256 mismatch: $actual != $expected" >&2
  exit 4
fi
printf '%s\n' "$binary" > "$root/binary.path"
printf '%s  %s\n' "$actual" "$binary"
