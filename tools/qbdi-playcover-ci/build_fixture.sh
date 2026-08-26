#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
out="${1:-$root/test-output/qbdi-fixture}"
deb="${2:-${QBDI_TRACER_DEB:-}}"

if [ -z "$deb" ] || [ ! -f "$deb" ]; then
  echo "usage: $0 OUT_DIR TRACER.deb" >&2
  exit 2
fi
if [ "$(uname -m)" != "arm64" ]; then
  echo "build_fixture.sh requires an Apple-Silicon macOS runner" >&2
  exit 2
fi

sdk="$(xcrun --sdk iphoneos --show-sdk-path)"
original="$out/original/Payload/QBDIFixture.app"
ported="$out/ported/QBDIFixture.app"
manifest="$out/ported/port-manifest.json"
config="$out/config/config.json"

mkdir -p "$original" "$out/config"
cp "$root/tools/qbdi-playcover-ci/fixture/Info.plist" "$original/Info.plist"

xcrun --sdk iphoneos clang \
  -target arm64-apple-ios15.0 \
  -isysroot "$sdk" \
  -fobjc-arc -Os \
  -framework Foundation -framework UIKit \
  "$root/tools/qbdi-playcover-ci/fixture/main.m" \
  -o "$original/QBDIFixture"
chmod +x "$original/QBDIFixture"

start_vm="$(nm -gU "$original/QBDIFixture" | awk '$3 == "_qbdi_fixture_target" {print "0x" $1; exit}')"
end_vm="$(nm -gU "$original/QBDIFixture" | awk '$3 == "_qbdi_fixture_target_end" {print "0x" $1; exit}')"
text_vm="$(otool -l "$original/QBDIFixture" | awk '
  $1 == "segname" && $2 == "__TEXT" {in_text=1; next}
  in_text && $1 == "vmaddr" {print $2; exit}
')"
if [ -z "$start_vm" ] || [ -z "$end_vm" ] || [ -z "$text_vm" ]; then
  echo "failed to resolve fixture trace symbols" >&2
  exit 1
fi

read -r start_offset end_offset <<EOF
$(python3 - "$start_vm" "$end_vm" "$text_vm" <<'PY'
import sys
start, end, base = (int(value, 0) for value in sys.argv[1:])
print(hex(start - base), hex(end - base))
PY
)
EOF

python3 "$root/skills/reverse-skill/scripts/playcover_qbdi_port.py" port-app \
  --deb "$deb" \
  --input-app "$original" \
  --output-app "$ported" \
  --manifest "$manifest"

python3 "$root/skills/reverse-skill/scripts/playcover_qbdi_port.py" make-config \
  --output "$config" \
  --bundle-id test.qbdi.playcover.fixture \
  --app-name QBDIFixture \
  --module QBDIFixture \
  --start "$start_offset" \
  --end "$end_offset" \
  --count 1 \
  --delay 0 \
  --log-mask 0x1f

python3 "$root/skills/reverse-skill/scripts/playcover_qbdi_port.py" verify-app --app "$ported"

mkdir -p "$out/packages/original/Payload" "$out/packages/ported/Payload"
ditto "$original" "$out/packages/original/Payload/QBDIFixture.app"
ditto "$ported" "$out/packages/ported/Payload/QBDIFixture.app"
(cd "$out/packages/original" && zip -qry "$out/QBDIFixture-original.ipa" Payload)
(cd "$out/packages/ported" && zip -qry "$out/QBDIFixture-ported.ipa" Payload)

printf 'start=%s\nend=%s\nmodule=QBDIFixture\n' "$start_offset" "$end_offset" > "$out/fixture-offsets.txt"
shasum -a 256 "$deb" "$original/QBDIFixture" "$ported/QBDIFixture" "$ported/Frameworks/TracerEngine.dylib"
