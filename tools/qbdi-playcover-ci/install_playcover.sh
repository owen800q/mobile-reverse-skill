#!/usr/bin/env bash
# Install PlayCover on a macOS runner by direct DMG download.
#
# Homebrew hard-refuses the PlayCover cask ("untrusted tap"), so we fetch the
# notarized release DMG, strip the download quarantine, and copy the app into
# /Applications. Best-effort: the caller runs this under continue-on-error.
set -euo pipefail

version="${PLAYCOVER_VERSION:-3.1.0}"
url="https://github.com/PlayCover/PlayCover/releases/download/${version}/PlayCover_${version}.dmg"
dmg="${TMPDIR:-/tmp}/PlayCover.dmg"
mnt="${TMPDIR:-/tmp}/pc-mnt"

if [ -d "/Applications/PlayCover.app" ]; then
  echo "PlayCover already present"
  exit 0
fi

echo "downloading $url"
curl -fL --retry 3 "$url" -o "$dmg"
hdiutil attach "$dmg" -nobrowse -quiet -mountpoint "$mnt"
trap 'hdiutil detach "$mnt" -quiet || true' EXIT
cp -R "$mnt/PlayCover.app" /Applications/
# curl marks the download as quarantined; Gatekeeper would block first launch.
xattr -dr com.apple.quarantine /Applications/PlayCover.app 2>/dev/null || true
echo "installed /Applications/PlayCover.app ($version)"
