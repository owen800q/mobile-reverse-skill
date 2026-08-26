#!/usr/bin/env bash
set -euo pipefail

app="${1:?usage: sign_app.sh APP.app [--jit]}"
jit="${2:-}"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "codesigning requires macOS" >&2
  exit 2
fi
if [ ! -d "$app" ] || [ ! -f "$app/Info.plist" ]; then
  echo "invalid app bundle: $app" >&2
  exit 2
fi

exec_name="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app/Info.plist")"
main="$app/$exec_name"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/qbdi-sign.XXXXXX")"
trap 'case "$tmp" in */qbdi-sign.*) rm -rf -- "$tmp";; esac' EXIT
entitlements="$tmp/entitlements.plist"

if ! codesign -d --entitlements :- "$main" > "$entitlements" 2>/dev/null; then
  printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
    '<plist version="1.0"><dict/></plist>' > "$entitlements"
fi

/usr/libexec/PlistBuddy -c 'Delete :com.apple.security.get-task-allow' "$entitlements" 2>/dev/null || true
/usr/libexec/PlistBuddy -c 'Add :com.apple.security.get-task-allow bool true' "$entitlements"
/usr/libexec/PlistBuddy -c 'Delete :com.apple.security.cs.disable-library-validation' "$entitlements" 2>/dev/null || true
/usr/libexec/PlistBuddy -c 'Add :com.apple.security.cs.disable-library-validation bool true' "$entitlements"

if [ "$jit" = "--jit" ]; then
  /usr/libexec/PlistBuddy -c 'Delete :com.apple.security.cs.allow-jit' "$entitlements" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c 'Add :com.apple.security.cs.allow-jit bool true' "$entitlements"
  /usr/libexec/PlistBuddy -c 'Delete :com.apple.security.cs.allow-unsigned-executable-memory' "$entitlements" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c 'Add :com.apple.security.cs.allow-unsigned-executable-memory bool true' "$entitlements"
fi

# Sign every nested Mach-O leaf first. Framework bundle executables and plain
# dylibs are both detected by file(1); the main executable is deliberately last.
while IFS= read -r candidate; do
  [ "$candidate" = "$main" ] && continue
  if file -b "$candidate" | grep -q 'Mach-O'; then
    codesign -f -s - "$candidate"
  fi
done < <(find "$app" -type f -perm -111 -print | sort)

codesign -f -s - --entitlements "$entitlements" "$main"
codesign -f -s - --entitlements "$entitlements" "$app"
codesign --verify --strict --verbose=2 "$app"
codesign -d --entitlements :- "$main"
