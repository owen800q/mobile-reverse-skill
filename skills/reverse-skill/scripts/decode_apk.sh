#!/usr/bin/env bash
# decode_apk.sh — P0 "decode" step for the reverse-skill.
# Merges/adapts haikow decode.sh + creditone decompile.sh into a single,
# self-contained decode: jadx (Java) + apktool (res/manifest/smali) + optional
# dex2jar, with bundle/split handling and a machine-readable summary.
#
# Usage: decode_apk.sh <apk|xapk|apks|apkm> [--out DIR] [--skip-jadx] [--skip-apktool] [--deobf]
#   --out DIR       output root (default: ./re_out)
#   --skip-jadx     do not run jadx
#   --skip-apktool  do not run apktool
#   --deobf         pass --deobf to jadx. OFF by default, so --deobf is not passed.
#                   Whether jadx's class names then match the runtime names (for a
#                   later Frida FindClass) is not checked by this script.
#
# Human summary -> stderr. Machine data (decode_summary.json) -> stdout + file.
# No network calls. Written to avoid bash-4-only constructs. It was not run on macOS
# here. filesize() tries the BSD stat form first and uses GNU stat -c only as a fallback.
set -euo pipefail

# ------------------------------------------------------------------ helpers ---
log() { printf '%s\n' "$*" >&2; }

usage() {
  cat >&2 <<'EOF'
Usage: decode_apk.sh <apk|xapk|apks|apkm> [--out DIR] [--skip-jadx] [--skip-apktool] [--deobf]
  --out DIR       output root (default: ./re_out)
  --skip-jadx     skip jadx decompile
  --skip-apktool  skip apktool decode
  --deobf         enable jadx --deobf (default OFF: --deobf is not passed to jadx)
EOF
}

abspath() {
  # Portable realpath (no coreutils dependency).
  local p="$1" d b
  if [ -d "$p" ]; then
    (cd "$p" && pwd)
  else
    d="$(dirname "$p")"; b="$(basename "$p")"
    printf '%s/%s\n' "$(cd "$d" && pwd)" "$b"
  fi
}

filesize() {
  # Bytes; try BSD stat, then GNU stat, then wc -c.
  local f="$1"
  if stat -f%z "$f" >/dev/null 2>&1; then stat -f%z "$f"
  elif stat -c%s "$f" >/dev/null 2>&1; then stat -c%s "$f"
  else wc -c < "$f" | tr -d ' '; fi
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# SHA-256 hex digest of a file; GNU sha256sum, then BSD/macOS shasum. Empty if neither exists.
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else printf ''; fi
}

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

json_or_null() {
  if [ -z "${1:-}" ]; then printf 'null'; else printf '"%s"' "$(json_escape "$1")"; fi
}

count_java() {
  local d="$1" n
  [ -d "$d" ] || { printf '0'; return 0; }
  n="$(find "$d" -type f -name '*.java' 2>/dev/null | wc -l | tr -d ' ')" || n=0
  printf '%s' "${n:-0}"
}

# Prefer a file named base*.apk, else the largest apk.
choose_base() {
  local f bn best="" bestsize=-1 sz
  for f in "$@"; do
    bn="$(basename "$f")"
    case "$bn" in
      base.apk) printf '%s\n' "$f"; return 0;;
    esac
  done
  for f in "$@"; do
    bn="$(basename "$f")"
    case "$bn" in
      base*.apk) printf '%s\n' "$f"; return 0;;
    esac
  done
  for f in "$@"; do
    sz="$(filesize "$f")"
    if [ "${sz:-0}" -gt "$bestsize" ]; then bestsize="$sz"; best="$f"; fi
  done
  printf '%s\n' "$best"
}

# ---------------------------------------------------------------- cleanup -----
TMP=""; INNER_TMP=""; SO_SCAN=""; SO_LIST_RAW=""
cleanup() {
  [ -n "${TMP:-}" ]         && rm -rf "$TMP"         2>/dev/null || true
  [ -n "${INNER_TMP:-}" ]   && rm -rf "$INNER_TMP"   2>/dev/null || true
  [ -n "${SO_SCAN:-}" ]     && rm -rf "$SO_SCAN"     2>/dev/null || true
  [ -n "${SO_LIST_RAW:-}" ] && rm -f  "$SO_LIST_RAW" 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------- args --------
INPUT=""; OUT="./re_out"; SKIP_JADX=0; SKIP_APKTOOL=0; DEOBF=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out)          OUT="${2:?--out needs a value}"; shift 2;;
    --skip-jadx)    SKIP_JADX=1; shift;;
    --skip-apktool) SKIP_APKTOOL=1; shift;;
    --deobf)        DEOBF=1; shift;;
    -h|--help)      usage; exit 0;;
    -*)             log "Unknown option: $1"; usage; exit 1;;
    *)              INPUT="$1"; shift;;
  esac
done

if [ -z "$INPUT" ]; then log "ERROR: no input file given"; usage; exit 1; fi
if [ ! -f "$INPUT" ]; then log "ERROR: input not found: $INPUT"; exit 1; fi

# Digest the input before anything reads it: before bundle extraction (unzip) and before
# any tool runs. input_sha256 is this digest. The tools read TARGET_APK (the input, or an
# APK extracted from it), not the input/ copy. If the original changes after this point,
# input_sha256 may not match the bytes the tools decode.
INPUT_ABS="$(abspath "$INPUT")"
INPUT_SHA256="$(sha256_of "$INPUT_ABS")"

# ---------------------------------------------------------------- tools -------
HAVE_JADX=0;    if command -v jadx    >/dev/null 2>&1; then HAVE_JADX=1;    fi
HAVE_APKTOOL=0; if command -v apktool >/dev/null 2>&1; then HAVE_APKTOOL=1; fi

if [ "$SKIP_JADX" -eq 0 ] && [ "$HAVE_JADX" -eq 0 ]; then
  log "hint: jadx not on PATH -> brew install jadx  (or: https://github.com/skylot/jadx)"
fi
if [ "$SKIP_APKTOOL" -eq 0 ] && [ "$HAVE_APKTOOL" -eq 0 ]; then
  log "hint: apktool not on PATH -> brew install apktool  (or: apt-get install apktool)"
fi
if [ "$HAVE_JADX" -eq 0 ] && [ "$HAVE_APKTOOL" -eq 0 ]; then
  log "ERROR: neither jadx nor apktool found on PATH; cannot decode. Install: brew install jadx apktool"
  exit 1
fi

RUN_JADX=0;    if [ "$SKIP_JADX" -eq 0 ]    && [ "$HAVE_JADX" -eq 1 ];    then RUN_JADX=1;    fi
RUN_APKTOOL=0; if [ "$SKIP_APKTOOL" -eq 0 ] && [ "$HAVE_APKTOOL" -eq 1 ]; then RUN_APKTOOL=1; fi

# ---------------------------------------------------------------- input --------
EXT="$(lower "${INPUT_ABS##*.}")"
TARGET_APK="$INPUT_ABS"
SPLITS=()          # basenames of non-target (split) apks
APK_FILES=("$INPUT_ABS")   # every relevant apk (for native-lib extraction)

IS_BUNDLE=0
case "$EXT" in
  apk)                 IS_BUNDLE=0;;
  xapk|apks|apkm|zip)  IS_BUNDLE=1;;
  *)                   log "note: unrecognized extension '.$EXT'; treating as a plain APK"; IS_BUNDLE=0;;
esac

if [ "$IS_BUNDLE" -eq 1 ]; then
  if ! command -v unzip >/dev/null 2>&1; then log "ERROR: unzip required for bundle input"; exit 1; fi
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/decode_apk.XXXXXX")"
  log "[bundle] extracting $(basename "$INPUT_ABS") -> tmp"
  unzip -qo "$INPUT_ABS" -d "$TMP" >/dev/null 2>&1 || log "warn: unzip returned non-zero (continuing)"
  ALL_APKS=()
  while IFS= read -r f; do ALL_APKS+=("$f"); done < <(find "$TMP" -type f -name '*.apk' | sort)
  if [ "${#ALL_APKS[@]}" -eq 0 ]; then log "ERROR: no .apk found inside bundle"; exit 1; fi
  TARGET_APK="$(choose_base "${ALL_APKS[@]}")"
  APK_FILES=("${ALL_APKS[@]}")
  for f in "${ALL_APKS[@]}"; do
    if [ "$f" != "$TARGET_APK" ]; then SPLITS+=("$(basename "$f")"); fi
  done
  log "[bundle] base -> $(basename "$TARGET_APK"); splits: ${#SPLITS[@]}"
fi

# ---------------------------------------------------------------- outputs ------
mkdir -p "$OUT"
OUT_ABS="$(abspath "$OUT")"
# Copy the input to input/ once the output directory exists. The copy is taken after the
# digest and after bundle extraction, so it can differ from input_sha256 if the original
# changed in between.
mkdir -p "$OUT_ABS/input"
INPUT_SNAPSHOT=""
if cp -p "$INPUT_ABS" "$OUT_ABS/input/" 2>/dev/null; then
  INPUT_SNAPSHOT="$OUT_ABS/input/$(basename "$INPUT_ABS")"
else
  log "warn: could not snapshot input (continuing)"
fi
TARGET_SHA256="$(sha256_of "$TARGET_APK")"
JADX_OUT="$OUT_ABS/jadx"
APKTOOL_OUT="$OUT_ABS/apktool"
JADX_RC="null"; APKTOOL_RC="null"

run_jadx() {
  # $1 = apk
  rm -rf "$JADX_OUT"; mkdir -p "$JADX_OUT"
  local jadx_args
  jadx_args=(-d "$JADX_OUT" --show-bad-code)
  if [ "$DEOBF" -eq 1 ]; then jadx_args+=(--deobf); fi
  jadx_args+=("$1")
  set +e
  jadx "${jadx_args[@]}" >&2
  JADX_RC=$?
  set -e
}

# ---------------------------------------------------------------- jadx ---------
if [ "$RUN_JADX" -eq 1 ]; then
  log "[jadx] decompiling $(basename "$TARGET_APK") -> $JADX_OUT (deobf=$DEOBF)"
  run_jadx "$TARGET_APK"
  JC="$(count_java "$JADX_OUT")"
  if [ "$JADX_RC" != "0" ] && [ "$JC" -gt 0 ]; then
    log "[jadx] exited $JADX_RC but emitted $JC java files -> partial success (continuing)"
  fi

  # CreditTone case: a split/stub wrapper yields <=10 java files. Re-point at the
  # inner base.apk (largest / base*.apk) contained in the wrapper.
  if [ "$JC" -le 10 ] && command -v unzip >/dev/null 2>&1; then
    INNER_TMP="$(mktemp -d "${TMPDIR:-/tmp}/decode_inner.XXXXXX")"
    unzip -qo "$TARGET_APK" '*.apk' -d "$INNER_TMP" >/dev/null 2>&1 || true
    inner_apks=()
    while IFS= read -r f; do inner_apks+=("$f"); done < <(find "$INNER_TMP" -type f -name '*.apk' | sort)
    if [ "${#inner_apks[@]}" -gt 0 ]; then
      newbase="$(choose_base "${inner_apks[@]}")"
      log "[jadx] only $JC java files -> split/stub detected; re-pointing at $(basename "$newbase")"
      SPLITS=()
      for f in "${inner_apks[@]}"; do
        if [ "$f" != "$newbase" ]; then SPLITS+=("$(basename "$f")"); fi
      done
      TARGET_APK="$newbase"
      TARGET_SHA256="$(sha256_of "$TARGET_APK")"
      APK_FILES=("${inner_apks[@]}")
      run_jadx "$TARGET_APK"
    else
      rm -rf "$INNER_TMP"; INNER_TMP=""
    fi
  fi
else
  log "[jadx] skipped"
fi

# ---------------------------------------------------------------- apktool ------
if [ "$RUN_APKTOOL" -eq 1 ]; then
  log "[apktool] d -f -o $APKTOOL_OUT $(basename "$TARGET_APK")"
  set +e
  apktool d -f -o "$APKTOOL_OUT" "$TARGET_APK" >&2
  APKTOOL_RC=$?
  set -e
  if [ "$APKTOOL_RC" != "0" ]; then log "[apktool] exited $APKTOOL_RC (continuing)"; fi
else
  log "[apktool] skipped"
fi

# ---------------------------------------------------------------- dex2jar ------
DEX2JAR_OK=false
D2J=""
if   command -v d2j-dex2jar    >/dev/null 2>&1; then D2J="d2j-dex2jar"
elif command -v dex2jar        >/dev/null 2>&1; then D2J="dex2jar"
elif command -v d2j-dex2jar.sh >/dev/null 2>&1; then D2J="d2j-dex2jar.sh"
fi
if [ -n "$D2J" ]; then
  log "[dex2jar] $D2J -> $OUT_ABS/classes.jar (best-effort)"
  set +e
  "$D2J" -f -o "$OUT_ABS/classes.jar" "$TARGET_APK" >&2
  set -e
  if [ -f "$OUT_ABS/classes.jar" ]; then DEX2JAR_OK=true; fi
fi

# ---------------------------------------------------------------- metadata -----
MANIFEST="$APKTOOL_OUT/AndroidManifest.xml"

# aapt / aapt2 badging (used for package + launcher activity fallback)
BADGING=""
if command -v aapt >/dev/null 2>&1; then
  BADGING="$(aapt dump badging "$TARGET_APK" 2>/dev/null || true)"
fi
if [ -z "$BADGING" ] && command -v aapt2 >/dev/null 2>&1; then
  BADGING="$(aapt2 dump badging "$TARGET_APK" 2>/dev/null || true)"
fi

# Package name.
PKG=""
if [ -f "$MANIFEST" ]; then
  PKG="$(grep -aoE 'package="[^"]+"' "$MANIFEST" | head -1 | sed 's/^package="//; s/"$//' || true)"
fi
if [ -z "$PKG" ] && [ -n "$BADGING" ]; then
  PKG="$(printf '%s\n' "$BADGING" | grep -oE "package: name='[^']+'" | head -1 | sed "s/^package: name='//; s/'$//" || true)"
fi

# Launcher / main activity.
MAIN_ACT=""
if [ -n "$BADGING" ]; then
  MAIN_ACT="$(printf '%s\n' "$BADGING" | grep -oE "launchable-activity: name='[^']+'" | head -1 | sed "s/.*name='//; s/'$//" || true)"
fi
if [ -z "$MAIN_ACT" ] && [ -f "$MANIFEST" ]; then
  # Fallback: walk the decoded manifest for the activity carrying LAUNCHER.
  MAIN_ACT="$(awk '
    /<activity/ { if (match($0, /android:name="[^"]+"/)) name=substr($0, RSTART+14, RLENGTH-15) }
    /android.intent.category.LAUNCHER/ { if (name != "") { print name; exit } }
  ' "$MANIFEST" || true)"
fi
case "$MAIN_ACT" in
  .*) if [ -n "$PKG" ]; then MAIN_ACT="$PKG$MAIN_ACT"; fi;;
esac

# Exported components (best-effort: attribute each exported="true" to the most
# recent component tag). The awk counter assumes apktool writes one attribute per line
# in AndroidManifest.xml; that layout was not checked against apktool output here.
exported_counts() {
  [ -f "$MANIFEST" ] || return 0
  awk '
    /<activity/ { last="activity" }
    /<service/  { last="service"  }
    /<receiver/ { last="receiver" }
    /<provider/ { last="provider" }
    /android:exported="true"/ { if (last != "") { c[last]++; last="" } }
    END { printf "%d %d %d %d", c["activity"]+0, c["service"]+0, c["receiver"]+0, c["provider"]+0 }
  ' "$MANIFEST"
}
EXP="$(exported_counts)"; if [ -z "$EXP" ]; then EXP="0 0 0 0"; fi
set -- $EXP
EXP_ACT="$1"; EXP_SVC="$2"; EXP_RCV="$3"; EXP_PROV="$4"

# ---------------------------------------------------------------- .so files ----
# Pull native libs out of every relevant apk (base + splits hold ABI-specific
# .so), then also scan jadx/apktool outputs. Dedup by name; collect ABIs.
SO_SCAN="$(mktemp -d "${TMPDIR:-/tmp}/decode_libs.XXXXXX")"
if command -v unzip >/dev/null 2>&1; then
  i=0
  for apk in "${APK_FILES[@]}"; do
    unzip -qo "$apk" 'lib/*' -d "$SO_SCAN/a$i" >/dev/null 2>&1 || true
    i=$((i + 1))
  done
fi

SO_LIST_RAW="$(mktemp "${TMPDIR:-/tmp}/decode_so.XXXXXX")"
{
  for d in "$JADX_OUT" "$APKTOOL_OUT" "$SO_SCAN"; do
    if [ -n "$d" ] && [ -d "$d" ]; then find "$d" -type f -name '*.so' 2>/dev/null; fi
  done
} | while IFS= read -r sofile; do
  printf '%s\t%s\n' "$(basename "$sofile")" "$(basename "$(dirname "$sofile")")"
done | sort -u > "$SO_LIST_RAW" || true

SO_NAMES="$(cut -f1 "$SO_LIST_RAW" 2>/dev/null | sort -u || true)"

build_so_json() {
  local first=1 name abi abis abi_json af
  printf '['
  while IFS= read -r name; do
    [ -z "$name" ] && continue
    abis="$(awk -F'\t' -v n="$name" '$1==n{print $2}' "$SO_LIST_RAW" 2>/dev/null | sort -u || true)"
    abi_json=""; af=1
    for abi in $abis; do
      [ -z "$abi" ] && continue
      if [ "$af" -eq 1 ]; then abi_json="\"$(json_escape "$abi")\""; af=0
      else abi_json="$abi_json,\"$(json_escape "$abi")\""; fi
    done
    if [ "$first" -eq 1 ]; then first=0; else printf ','; fi
    printf '{"name":"%s","abis":[%s]}' "$(json_escape "$name")" "$abi_json"
  done <<NAMES_EOF
$SO_NAMES
NAMES_EOF
  printf ']'
}

build_splits_json() {
  local first=1 s
  printf '['
  for s in "${SPLITS[@]:-}"; do
    [ -z "$s" ] && continue
    if [ "$first" -eq 1 ]; then first=0; else printf ','; fi
    printf '"%s"' "$(json_escape "$s")"
  done
  printf ']'
}

JAVA_N="$(count_java "$JADX_OUT")"
SO_N="$(printf '%s\n' "$SO_NAMES" | grep -c . || true)"; SO_N="${SO_N:-0}"

# ---------------------------------------------------------------- summary ------
SUMMARY="$OUT_ABS/decode_summary.json"
{
  printf '{\n'
  printf '  "input": %s,\n'         "$(json_or_null "$INPUT_ABS")"
  printf '  "input_sha256": %s,\n'  "$(json_or_null "$INPUT_SHA256")"
  printf '  "input_snapshot": %s,\n' "$(json_or_null "$INPUT_SNAPSHOT")"
  printf '  "target_apk": %s,\n'    "$(json_or_null "$(basename "$TARGET_APK")")"
  printf '  "target_apk_sha256": %s,\n' "$(json_or_null "$TARGET_SHA256")"
  printf '  "package": %s,\n'       "$(json_or_null "$PKG")"
  printf '  "main_activity": %s,\n' "$(json_or_null "$MAIN_ACT")"
  printf '  "java_files": %s,\n'    "${JAVA_N:-0}"
  printf '  "so_files": %s,\n'      "$(build_so_json)"
  printf '  "splits": %s,\n'        "$(build_splits_json)"
  printf '  "exported": {"activity": %s, "service": %s, "receiver": %s, "provider": %s},\n' \
         "${EXP_ACT:-0}" "${EXP_SVC:-0}" "${EXP_RCV:-0}" "${EXP_PROV:-0}"
  printf '  "tools": {"jadx": %s, "apktool": %s, "dex2jar": %s}\n' \
         "$JADX_RC" "$APKTOOL_RC" "$DEX2JAR_OK"
  printf '}\n'
} > "$SUMMARY"

# Human summary -> stderr.
log ""
log "==================== decode summary ===================="
log "input          : $INPUT_ABS"
log "input sha256   : ${INPUT_SHA256:-unavailable}"
log "target sha256  : ${TARGET_SHA256:-unavailable}"
log "target apk     : $(basename "$TARGET_APK")"
log "package        : ${PKG:-<unknown>}"
log "main activity  : ${MAIN_ACT:-<unknown>}"
log "java files     : ${JAVA_N:-0}   (jadx -> $JADX_OUT/sources)"
log "native .so     : ${SO_N} unique"
log "splits         : ${#SPLITS[@]}"
log "exported       : act=$EXP_ACT svc=$EXP_SVC rcv=$EXP_RCV prov=$EXP_PROV"
log "tools          : jadx=$JADX_RC apktool=$APKTOOL_RC dex2jar=$DEX2JAR_OK"
log "apktool out    : $APKTOOL_OUT"
if [ "$DEX2JAR_OK" = "true" ]; then log "classes.jar    : $OUT_ABS/classes.jar"; fi
log "summary json   : $SUMMARY"
log "========================================================"

# Machine data -> stdout.
cat "$SUMMARY"
