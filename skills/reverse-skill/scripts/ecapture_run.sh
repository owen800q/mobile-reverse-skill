#!/usr/bin/env bash
#
# ecapture_run.sh - Capture TLS plaintext from an Android app WITHOUT a CA cert,
# proxy, or SSL-pinning bypass, using gojue/ecapture (eBPF uprobe on libssl
# SSL_read/SSL_write). Replaces Burp/Frida-pinning workflows.
#
# REQUIRES: a ROOTED Android device (eBPF needs root; arm64 kernel >= 5.5).
#
# Usage:
#   ecapture_run.sh [--serial S] [--out DIR] [--pkg com.x] \
#                   [--bin PATH_TO_ECAPTURE] [--mode text|pcap|keylog] \
#                   [--duration SECS]
#
# Defaults: --out ./re_out, --mode text.
#
set -euo pipefail

# ---- defaults -------------------------------------------------------------
SERIAL=""
OUT="./re_out"
PKG=""
BIN=""
MODE="text"
DURATION=""

REMOTE_BIN="/data/local/tmp/ecapture"
REMOTE_PCAP="/data/local/tmp/ecapture.pcapng"
REMOTE_KEYLOG="/data/local/tmp/key.log"

# ---- helpers --------------------------------------------------------------
err() { printf '%s\n' "$*" >&2; }
die() { err "ERROR: $*"; exit 1; }

usage() {
  err "Usage: ecapture_run.sh [--serial S] [--out DIR] [--pkg com.x] [--bin PATH] [--mode text|pcap|keylog] [--duration SECS]"
}

# ---- arg parsing ----------------------------------------------------------
while [ "$#" -gt 0 ]; do
  case "$1" in
    --serial)   SERIAL="${2:-}"; shift 2 ;;
    --out)      OUT="${2:-}"; shift 2 ;;
    --pkg)      PKG="${2:-}"; shift 2 ;;
    --bin)      BIN="${2:-}"; shift 2 ;;
    --mode)     MODE="${2:-}"; shift 2 ;;
    --duration) DURATION="${2:-}"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *)          usage; die "Unknown argument: $1" ;;
  esac
done

case "$MODE" in
  text|pcap|keylog) ;;
  *) die "Invalid --mode '$MODE' (expected text|pcap|keylog)" ;;
esac

# ---- adb wrapper (honours --serial) --------------------------------------
command -v adb >/dev/null 2>&1 || die "adb not found in PATH. Install Android platform-tools."

ADB=(adb)
if [ -n "$SERIAL" ]; then
  ADB=(adb -s "$SERIAL")
fi

adbx() { "${ADB[@]}" "$@"; }

# ---- device presence ------------------------------------------------------
if [ -z "$SERIAL" ]; then
  # Count attached devices (lines after the header that are in 'device' state).
  DEV_COUNT="$(adb devices | awk 'NR>1 && $2=="device" {c++} END {print c+0}')"
  case "$DEV_COUNT" in
    0) die "No adb device connected. Plug in / start emulator, or pass --serial." ;;
    1) ;;
    *) die "Multiple adb devices found ($DEV_COUNT). Disambiguate with --serial." ;;
  esac
fi

# Sanity: the (possibly serial-scoped) device answers.
adbx get-state >/dev/null 2>&1 || die "adb device not reachable (check --serial / connection)."

# ---- ABI detection --------------------------------------------------------
ABI="$(adbx shell getprop ro.product.cpu.abi 2>/dev/null | tr -d '\r')"
err "Device ABI: ${ABI:-unknown}"
case "$ABI" in
  arm64-v8a)      err "Use the ecapture android/aarch64 build." ;;
  armeabi-v7a)    err "Use the ecapture android/arm build (note: ecapture targets arm64; 32-bit may be unsupported)." ;;
  x86_64|x86)     err "Use the ecapture android/x86_64 build (emulators; eBPF support varies)." ;;
  *)              err "Unknown ABI '$ABI'; pick the matching ecapture android build." ;;
esac

# ---- resolve / push binary ------------------------------------------------
download_hint() {
  err ""
  err "ecapture binary not found. Download an Android build from:"
  err "  https://github.com/gojue/ecapture/releases"
  err "  -> pick the 'android' asset for your ABI (arm64-v8a => aarch64)."
  err "Then re-run with --bin /path/to/ecapture (or place ./ecapture here)."
}

push_local_bin() {
  # $1 = local path
  local src="$1"
  err "Pushing $src -> $REMOTE_BIN ..."
  adbx push "$src" "$REMOTE_BIN" >/dev/null
  adbx shell su -c "chmod 755 $REMOTE_BIN" >/dev/null 2>&1 \
    || adbx shell chmod 755 "$REMOTE_BIN" >/dev/null 2>&1 \
    || die "Failed to chmod $REMOTE_BIN"
}

if [ -n "$BIN" ]; then
  [ -f "$BIN" ] || die "--bin '$BIN' does not exist."
  push_local_bin "$BIN"
elif [ -f "./ecapture" ]; then
  push_local_bin "./ecapture"
else
  # No local binary: is one already staged on the device?
  if adbx shell "[ -x $REMOTE_BIN ]" >/dev/null 2>&1; then
    err "Using existing on-device binary: $REMOTE_BIN"
    adbx shell su -c "chmod 755 $REMOTE_BIN" >/dev/null 2>&1 || true
  else
    download_hint
    exit 1
  fi
fi

# ---- verify root ----------------------------------------------------------
ID_OUT="$(adbx shell su -c id 2>/dev/null | tr -d '\r' || true)"
case "$ID_OUT" in
  *uid=0*) err "Root OK: $ID_OUT" ;;
  *) die "Root required: 'su -c id' did not report uid=0 (got: '${ID_OUT:-<none>}'). eBPF needs root." ;;
esac

# ---- optional package -> uid filter --------------------------------------
UID_FILTER=""
if [ -n "$PKG" ]; then
  # dumpsys prints e.g. "userId=10234"; fall back to pm list output if needed.
  APP_UID="$(adbx shell "dumpsys package $PKG 2>/dev/null | grep -m1 userId=" \
              | tr -d '\r' | sed -n 's/.*userId=\([0-9][0-9]*\).*/\1/p')"
  if [ -z "$APP_UID" ]; then
    # Confirm the package at least exists so we can warn precisely.
    if adbx shell "pm list packages 2>/dev/null | grep -q \"package:$PKG\$\"" >/dev/null 2>&1; then
      err "WARNING: found package '$PKG' but could not resolve its uid; capturing ALL uids."
    else
      err "WARNING: package '$PKG' not found; capturing ALL uids."
    fi
  else
    err "Package '$PKG' -> uid $APP_UID (ecapture --uid filter)."
    UID_FILTER="--uid $APP_UID"
  fi
fi

# ---- output dir -----------------------------------------------------------
mkdir -p "$OUT"

# ---- build the remote ecapture command -----------------------------------
# Assembled as a single string run under 'su -c'.
case "$MODE" in
  text)
    LOCAL_OUT="$OUT/ecapture_text.log"
    REMOTE_CMD="$REMOTE_BIN tls -m text --hex $UID_FILTER"
    ;;
  pcap)
    LOCAL_OUT="$OUT/ecapture.pcapng"
    REMOTE_CMD="$REMOTE_BIN tls -m pcap --pcapfile=$REMOTE_PCAP $UID_FILTER tcp port 443"
    ;;
  keylog)
    LOCAL_OUT="$OUT/key.log"
    REMOTE_CMD="$REMOTE_BIN tls -m keylog --keylogfile=$REMOTE_KEYLOG $UID_FILTER"
    ;;
esac

# ---- cleanup / artifact pull ---------------------------------------------
cleanup() {
  # Avoid recursive traps.
  trap - INT TERM EXIT
  err ""
  err "Stopping capture; killing remote ecapture ..."
  adbx shell su -c "pkill -x ecapture" >/dev/null 2>&1 \
    || adbx shell su -c "pkill ecapture" >/dev/null 2>&1 || true
  # Give it a moment to flush files.
  sleep 1

  case "$MODE" in
    pcap)
      err "Pulling $REMOTE_PCAP -> $LOCAL_OUT ..."
      adbx pull "$REMOTE_PCAP" "$LOCAL_OUT" >/dev/null 2>&1 \
        || err "WARNING: could not pull $REMOTE_PCAP (was any traffic captured?)."
      ;;
    keylog)
      err "Pulling $REMOTE_KEYLOG -> $LOCAL_OUT ..."
      adbx pull "$REMOTE_KEYLOG" "$LOCAL_OUT" >/dev/null 2>&1 \
        || err "WARNING: could not pull $REMOTE_KEYLOG."
      ;;
    text)
      : # text mode streamed straight to $LOCAL_OUT already.
      ;;
  esac
  err "Artifacts in: $OUT"
}
trap cleanup INT TERM EXIT

# ---- BIG reminder ---------------------------------------------------------
err "########################################################################"
err "#  ecapture is starting in '$MODE' mode.                                 "
err "#  >>> Now perform the LOGIN in the app. <<<                             "
err "#  Press Ctrl-C (or wait for --duration) to STOP and pull artifacts.     "
err "########################################################################"
if [ -n "$DURATION" ]; then
  err "Auto-stop after ${DURATION}s."
fi
err "Remote command: su -c '$REMOTE_CMD'"

# ---- run ------------------------------------------------------------------
# Wrap with `timeout` when --duration is set (portable: gtimeout on macOS).
TIMEOUT_BIN=""
if [ -n "$DURATION" ]; then
  if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_BIN="timeout"
  elif command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_BIN="gtimeout"
  else
    err "WARNING: no 'timeout'/'gtimeout' available; --duration ignored (use Ctrl-C)."
  fi
fi

run_stream_stdout() {
  # text/keylog also stream to stdout; text log is the primary artifact.
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" "$DURATION" "${ADB[@]}" shell su -c "$REMOTE_CMD"
  else
    adbx shell su -c "$REMOTE_CMD"
  fi
}

# `timeout` exits 124 on timeout; treat that as a normal stop.
set +e
if [ "$MODE" = "text" ]; then
  run_stream_stdout | tee "$LOCAL_OUT"
  RC="${PIPESTATUS[0]}"
else
  run_stream_stdout
  RC=$?
fi
set -e

if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ] && [ "$RC" -ne 130 ] && [ "$RC" -ne 143 ]; then
  err "NOTE: ecapture exited with code $RC."
fi

# cleanup() runs via EXIT trap and pulls artifacts.
exit 0
