#!/usr/bin/env bash
# decode_ipa.sh — iP0 "decode" step for the reverse-skill iOS (PlayCover) mode.
# The iOS counterpart of decode_apk.sh: take a decrypted .ipa or an installed
# PlayCover .app and produce a machine-readable survey — main Mach-O, FairPlay
# cryptid state, arch, linked dylibs, embedded frameworks, engine fingerprint
# (PlayTools / Unity / Flutter / Hermes-RN), and a best-effort ObjC/Swift dump.
#
# Usage: decode_ipa.sh <app.ipa | Foo.app> [--out DIR] [--skip-classdump]
#   --out DIR         output root (default: ./re_out)
#   --skip-classdump  do not run ipsw/dsdump/class-dump
#
# Human summary -> stderr. Machine data (decode_summary.json) -> stdout + file.
# No network calls. Portable to macOS (bash 3.2) and Linux; every mac-only tool
# (otool/lipo/codesign/ipsw/class-dump) degrades to an install hint if absent.
# Plist reading uses python3 (a host prerequisite) so it works off a Mac too.
set -euo pipefail

# ------------------------------------------------------------------ helpers ---
log() { printf '%s\n' "$*" >&2; }

usage() {
  cat >&2 <<'EOF'
Usage: decode_ipa.sh <app.ipa | Foo.app> [--out DIR] [--skip-classdump]
  --out DIR         output root (default: ./re_out)
  --skip-classdump  skip ipsw/dsdump/class-dump ObjC/Swift dump
EOF
}

abspath() {
  local p="$1" d b
  if [ -d "$p" ]; then (cd "$p" && pwd)
  else d="$(dirname "$p")"; b="$(basename "$p")"; printf '%s/%s\n' "$(cd "$d" && pwd)" "$b"; fi
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
json_or_null() { if [ -z "${1:-}" ]; then printf 'null'; else printf '"%s"' "$(json_escape "$1")"; fi; }

have() { command -v "$1" >/dev/null 2>&1; }

# Portable plist reader: <plist> <key> -> value on stdout (empty if missing).
plist_get() {
  local plist="$1" key="$2"
  [ -f "$plist" ] || return 0
  if have python3; then
    python3 - "$plist" "$key" <<'PY' 2>/dev/null || true
import sys, plistlib
try:
    with open(sys.argv[1], "rb") as fh:
        d = plistlib.load(fh)
    v = d.get(sys.argv[2], "")
    print(v if isinstance(v, str) else ("" if v is None else v))
except Exception:
    pass
PY
  elif have /usr/libexec/PlistBuddy; then
    /usr/libexec/PlistBuddy -c "Print :$key" "$plist" 2>/dev/null || true
  fi
}

# ---------------------------------------------------------------- cleanup -----
TMP=""
cleanup() { [ -n "${TMP:-}" ] && rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT

# ---------------------------------------------------------------- args --------
INPUT=""; OUT="./re_out"; SKIP_CD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out)            OUT="${2:?--out needs a value}"; shift 2;;
    --skip-classdump) SKIP_CD=1; shift;;
    -h|--help)        usage; exit 0;;
    -*)               log "Unknown option: $1"; usage; exit 1;;
    *)                INPUT="$1"; shift;;
  esac
done
[ -z "$INPUT" ] && { log "ERROR: no input given"; usage; exit 1; }
[ -e "$INPUT" ] || { log "ERROR: input not found: $INPUT"; exit 1; }

INPUT_ABS="$(abspath "$INPUT")"
EXT="$(lower "${INPUT_ABS##*.}")"

# ---------------------------------------------------------------- locate .app -
APP_DIR=""
if [ -d "$INPUT_ABS" ] && [ "$EXT" = "app" ]; then
  APP_DIR="$INPUT_ABS"
elif [ "$EXT" = "ipa" ] || [ "$EXT" = "zip" ]; then
  have unzip || { log "ERROR: unzip required for .ipa input"; exit 1; }
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/decode_ipa.XXXXXX")"
  log "[ipa] extracting $(basename "$INPUT_ABS")"
  unzip -qo "$INPUT_ABS" -d "$TMP" >/dev/null 2>&1 || log "warn: unzip returned non-zero (continuing)"
  APP_DIR="$(find "$TMP/Payload" -maxdepth 1 -type d -name '*.app' 2>/dev/null | head -1 || true)"
  [ -z "$APP_DIR" ] && APP_DIR="$(find "$TMP" -type d -name '*.app' 2>/dev/null | head -1 || true)"
  [ -z "$APP_DIR" ] && { log "ERROR: no .app found inside $(basename "$INPUT_ABS")"; exit 1; }
else
  log "ERROR: expected a .ipa or a .app (got .$EXT)"; exit 1
fi
log "[app] $APP_DIR"

INFO_PLIST="$APP_DIR/Info.plist"
BUNDLE_ID="$(plist_get "$INFO_PLIST" CFBundleIdentifier)"
EXEC_NAME="$(plist_get "$INFO_PLIST" CFBundleExecutable)"
[ -z "$EXEC_NAME" ] && EXEC_NAME="$(basename "$APP_DIR" .app)"
EXEC_PATH="$APP_DIR/$EXEC_NAME"
[ -f "$EXEC_PATH" ] || log "warn: main executable not at $EXEC_PATH"

# ---------------------------------------------------------------- outputs ------
mkdir -p "$OUT"
OUT_ABS="$(abspath "$OUT")"

# ---------------------------------------------------------------- tools --------
have otool || log "hint: otool not on PATH (macOS Command Line Tools: xcode-select --install)"
have ipsw  || log "hint: ipsw not on PATH -> brew install blacktop/tap/ipsw  (primary Mach-O/ObjC/Swift tool)"

# ---------------------------------------------------------------- cryptid ------
# cryptid 0 = decrypted (required for PlayCover); 1 = still FairPlay-encrypted.
CRYPTID=""
if have otool && [ -f "$EXEC_PATH" ]; then
  CRYPTID="$(otool -l "$EXEC_PATH" 2>/dev/null | awk '/cryptid/ {print $2; exit}' || true)"
elif have ipsw && [ -f "$EXEC_PATH" ]; then
  CRYPTID="$(ipsw macho info "$EXEC_PATH" 2>/dev/null | awk '/cryptid/ {print $NF; exit}' || true)"
fi
case "$CRYPTID" in
  0) log "[cryptid] 0 -> decrypted (good)";;
  1) log "[cryptid] 1 -> STILL ENCRYPTED: won't run under PlayCover; obtain a decrypted IPA (jailbroken dump). See optional-platforms.md §1";;
  "") log "[cryptid] unknown (otool/ipsw unavailable or LC_ENCRYPTION_INFO absent)";;
esac

# ---------------------------------------------------------------- arch ---------
ARCH=""
if have lipo && [ -f "$EXEC_PATH" ]; then
  ARCH="$(lipo -info "$EXEC_PATH" 2>/dev/null | sed 's/.*: //' || true)"
elif have file && [ -f "$EXEC_PATH" ]; then
  ARCH="$(file -b "$EXEC_PATH" 2>/dev/null || true)"
fi
[ -n "$ARCH" ] && log "[arch] $ARCH"

# ---------------------------------------------------------------- dylibs -------
DYLIBS_RAW=""
if have otool && [ -f "$EXEC_PATH" ]; then
  DYLIBS_RAW="$(otool -L "$EXEC_PATH" 2>/dev/null | tail -n +2 | awk '{print $1}' | sort -u || true)"
fi

# ---------------------------------------------------------------- frameworks ---
FW_RAW=""
if [ -d "$APP_DIR/Frameworks" ]; then
  FW_RAW="$(find "$APP_DIR/Frameworks" -maxdepth 1 -name '*.framework' -o -maxdepth 1 -name '*.dylib' 2>/dev/null | while IFS= read -r f; do basename "$f"; done | sort -u || true)"
fi

# ---------------------------------------------------------------- engine flags -
has_str() { printf '%s\n%s\n' "$DYLIBS_RAW" "$FW_RAW" | grep -qi "$1"; }
PLAYTOOLS=false; UNITY=false; FLUTTER=false; HERMES=false; RN=false
has_str "PlayTools"      && PLAYTOOLS=true
has_str "UnityFramework" && UNITY=true
has_str "Flutter"        && FLUTTER=true
{ has_str "hermes" || [ -f "$APP_DIR/main.jsbundle" ] || find "$APP_DIR" -maxdepth 2 -name '*.jsbundle' 2>/dev/null | grep -q .; } && HERMES=true
{ has_str "React" || [ "$HERMES" = true ]; } && RN=true
# PlayTools may be injected as an LC_LOAD_DYLIB rather than a Frameworks entry.
if [ "$PLAYTOOLS" = false ] && have otool && [ -f "$EXEC_PATH" ]; then
  otool -L "$EXEC_PATH" 2>/dev/null | grep -qi "PlayTools" && PLAYTOOLS=true
fi
log "[engine] PlayTools=$PLAYTOOLS Unity=$UNITY Flutter=$FLUTTER Hermes/RN=$HERMES/$RN"
[ "$FLUTTER" = true ] && log "[engine] Flutter: own TLS/CA -> proxy & Cache.db won't intercept; SSL symbols are STRIPPED (pattern-scan/reFlutter). Dart snapshot in App.framework -> optional-platforms.md §4"
[ "$RN" = true ] && log "[engine] React Native/Hermes: NSURLSession-backed -> proxy/Cache.db/Frida-SSL all work; JS builders in the .jsbundle -> hermes-react-native.md"

# ---------------------------------------------------------------- class-dump ---
CD_OUT=""; CD_TOOL="none"
if [ "$SKIP_CD" -eq 0 ] && [ -f "$EXEC_PATH" ]; then
  CD_OUT="$OUT_ABS/classdump.txt"
  if have ipsw; then
    CD_TOOL="ipsw"
    log "[classdump] ipsw class-dump -> $CD_OUT (ObjC + Swift, best-effort)"
    ipsw class-dump "$EXEC_PATH" >"$CD_OUT" 2>/dev/null || { log "[classdump] ipsw failed (continuing)"; CD_OUT=""; }
  elif have dsdump; then
    CD_TOOL="dsdump"
    log "[classdump] dsdump -> $CD_OUT (ObjC + Swift; version-fragile on Swift 5.7+)"
    dsdump --objc --swift "$EXEC_PATH" >"$CD_OUT" 2>/dev/null || { log "[classdump] dsdump failed (continuing)"; CD_OUT=""; }
  elif have class-dump; then
    CD_TOOL="class-dump"
    log "[classdump] class-dump -> $CD_OUT (ObjC only, unmaintained)"
    class-dump "$EXEC_PATH" >"$CD_OUT" 2>/dev/null || { log "[classdump] class-dump failed (continuing)"; CD_OUT=""; }
  else
    CD_OUT=""
    log "hint: no class dumper found -> brew install blacktop/tap/ipsw  (or dsdump); Swift metadata otherwise needs IDA/Hopper/Ghidra"
  fi
fi

# ---------------------------------------------------------------- JSON arrays --
json_array_from_lines() {
  local first=1 line
  printf '['
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if [ "$first" -eq 1 ]; then first=0; else printf ','; fi
    printf '"%s"' "$(json_escape "$line")"
  done
  printf ']'
}

DYLIBS_JSON="$(printf '%s\n' "$DYLIBS_RAW" | json_array_from_lines)"
FW_JSON="$(printf '%s\n' "$FW_RAW" | json_array_from_lines)"

# ---------------------------------------------------------------- summary ------
SUMMARY="$OUT_ABS/decode_summary.json"
{
  printf '{\n'
  printf '  "input": %s,\n'          "$(json_or_null "$INPUT_ABS")"
  printf '  "app_dir": %s,\n'        "$(json_or_null "$APP_DIR")"
  printf '  "bundle_id": %s,\n'      "$(json_or_null "$BUNDLE_ID")"
  printf '  "executable": %s,\n'     "$(json_or_null "$EXEC_NAME")"
  printf '  "cryptid": %s,\n'        "$(json_or_null "$CRYPTID")"
  printf '  "arch": %s,\n'           "$(json_or_null "$ARCH")"
  printf '  "dylibs": %s,\n'         "$DYLIBS_JSON"
  printf '  "frameworks": %s,\n'     "$FW_JSON"
  printf '  "engine": {"playtools": %s, "unity": %s, "flutter": %s, "hermes_rn": %s},\n' \
         "$PLAYTOOLS" "$UNITY" "$FLUTTER" "$HERMES"
  printf '  "classdump": {"tool": %s, "out": %s}\n' \
         "$(json_or_null "$CD_TOOL")" "$(json_or_null "$CD_OUT")"
  printf '}\n'
} > "$SUMMARY"

log ""
log "==================== decode summary ===================="
log "app dir        : $APP_DIR"
log "bundle id      : ${BUNDLE_ID:-<unknown>}"
log "executable     : ${EXEC_NAME:-<unknown>}"
log "cryptid        : ${CRYPTID:-<unknown>}"
log "arch           : ${ARCH:-<unknown>}"
log "engine         : PlayTools=$PLAYTOOLS Unity=$UNITY Flutter=$FLUTTER Hermes/RN=$HERMES"
log "classdump      : ${CD_OUT:-<none>} (tool=$CD_TOOL)"
log "summary json   : $SUMMARY"
log "========================================================"

cat "$SUMMARY"
