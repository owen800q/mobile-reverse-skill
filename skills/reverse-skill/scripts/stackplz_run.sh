#!/usr/bin/env bash
#
# stackplz_run.sh - Trace arbitrary native functions, syscalls, or a hardware
# breakpoint in an Android app using SeeFlowerX/stackplz (eBPF), WITHOUT Frida.
# This is the stealthy counterpart to ecapture_run.sh: ecapture ground-truths
# TLS only; stackplz extends the same low-detection eBPF surface (uprobe / perf
# hardware breakpoint / syscall) to any 64-bit userspace code. Because the code
# executes in place (never relocated into a DBI code cache), it is invisible to
# the code-cache PC-divergence checks that catch Frida Stalker / QBDI
# (see references/dbi-detection.md).
#
# REQUIRES: a ROOTED Android device (eBPF needs root), arm64/aarch64, kernel
# >= 5.10 (4.14 works if CONFIG_HAVE_HW_BREAKPOINT is set).
#
# Modes:
#   syscall  trace syscalls (by name or %group) with args/stack/hexdump
#   uprobe   hook an exported/offset symbol in a .so, dump args + backtrace
#   brk      set a hardware breakpoint at a lib-relative offset (the crypto
#            sink you found in P1/P4); dump registers + memory at call time
#
# Usage:
#   stackplz_run.sh --pkg com.x --mode syscall [--syscalls connect,sendto,recvfrom]
#   stackplz_run.sh --pkg com.x --mode uprobe --lib libfoo.so --point 'Java_a_b_sign[str,int]'
#   stackplz_run.sh --pkg com.x --mode brk --lib libfoo.so --brk 0xf3a4 [--brk-type x]
#
#   [--serial S] [--out DIR] [--bin PATH] [--buffer MB] [--duration SECS]
#   [--extra "raw stackplz args appended verbatim"]
#
# Defaults: --out ./re_out, --mode syscall, --syscalls %net, --brk-type x.
#
set -euo pipefail

# ---- defaults -------------------------------------------------------------
SERIAL=""
OUT="./re_out"
PKG=""
BIN=""
MODE="syscall"
SYSCALLS="%net"
LIB=""
POINT=""
BRK=""
BRK_TYPE="x"
BUFFER=""
DURATION=""
EXTRA=""

REMOTE_BIN="/data/local/tmp/stackplz"
REMOTE_JSON="/data/local/tmp/stackplz.json"

# ---- helpers --------------------------------------------------------------
err() { printf '%s\n' "$*" >&2; }
die() { err "ERROR: $*"; exit 1; }

usage() {
  err "Usage: stackplz_run.sh --pkg com.x --mode syscall|uprobe|brk [options]"
  err "  syscall: [--syscalls connect,sendto,recvfrom | %net,%file]"
  err "  uprobe:  --lib libfoo.so --point 'sym[argspec]'"
  err "  brk:     --lib libfoo.so --brk 0xOFFSET [--brk-type r|w|x|rw]"
  err "  common:  [--serial S] [--out DIR] [--bin PATH] [--buffer MB] [--duration SECS] [--extra '...']"
}

# ---- arg parsing ----------------------------------------------------------
while [ "$#" -gt 0 ]; do
  case "$1" in
    --serial)    SERIAL="${2:-}"; shift 2 ;;
    --out)       OUT="${2:-}"; shift 2 ;;
    --pkg)       PKG="${2:-}"; shift 2 ;;
    --bin)       BIN="${2:-}"; shift 2 ;;
    --mode)      MODE="${2:-}"; shift 2 ;;
    --syscalls)  SYSCALLS="${2:-}"; shift 2 ;;
    --lib)       LIB="${2:-}"; shift 2 ;;
    --point)     POINT="${2:-}"; shift 2 ;;
    --brk)       BRK="${2:-}"; shift 2 ;;
    --brk-type)  BRK_TYPE="${2:-}"; shift 2 ;;
    --buffer)    BUFFER="${2:-}"; shift 2 ;;
    --duration)  DURATION="${2:-}"; shift 2 ;;
    --extra)     EXTRA="${2:-}"; shift 2 ;;
    -h|--help)   usage; exit 0 ;;
    *)           usage; die "Unknown argument: $1" ;;
  esac
done

case "$MODE" in
  syscall) ;;
  uprobe)  [ -n "$LIB" ]   || die "uprobe mode needs --lib libfoo.so"
           [ -n "$POINT" ] || die "uprobe mode needs --point 'sym[argspec]'" ;;
  brk)     [ -n "$LIB" ]   || die "brk mode needs --lib libfoo.so"
           [ -n "$BRK" ]   || die "brk mode needs --brk 0xOFFSET (lib-relative)" ;;
  *)       die "Invalid --mode '$MODE' (expected syscall|uprobe|brk)" ;;
esac

case "$BRK_TYPE" in r|w|x|rw) ;; *) die "Invalid --brk-type '$BRK_TYPE' (r|w|x|rw)" ;; esac

[ -n "$PKG" ] || die "--pkg is required (stackplz filters by package name via -n)."

# ---- adb wrapper (honours --serial) --------------------------------------
command -v adb >/dev/null 2>&1 || die "adb not found in PATH. Install Android platform-tools."

ADB=(adb)
if [ -n "$SERIAL" ]; then
  ADB=(adb -s "$SERIAL")
fi
adbx() { "${ADB[@]}" "$@"; }

# ---- device presence ------------------------------------------------------
if [ -z "$SERIAL" ]; then
  DEV_COUNT="$(adb devices | awk 'NR>1 && $2=="device" {c++} END {print c+0}')"
  case "$DEV_COUNT" in
    0) die "No adb device connected. Plug in / start emulator, or pass --serial." ;;
    1) ;;
    *) die "Multiple adb devices found ($DEV_COUNT). Disambiguate with --serial." ;;
  esac
fi
adbx get-state >/dev/null 2>&1 || die "adb device not reachable (check --serial / connection)."

# ---- ABI / kernel notes ---------------------------------------------------
ABI="$(adbx shell getprop ro.product.cpu.abi 2>/dev/null | tr -d '\r')"
KREL="$(adbx shell uname -r 2>/dev/null | tr -d '\r')"
err "Device ABI: ${ABI:-unknown}  kernel: ${KREL:-unknown}"
case "$ABI" in
  arm64-v8a) err "Use the stackplz android/aarch64 build." ;;
  *)         err "WARNING: stackplz targets aarch64; ABI '$ABI' may be unsupported (aarch32 syscall trace is planned upstream)." ;;
esac

# ---- resolve / push binary ------------------------------------------------
download_hint() {
  err ""
  err "stackplz binary not found. Download an Android build from:"
  err "  https://github.com/SeeFlowerX/stackplz/releases   (pick the aarch64 asset)"
  err "Then re-run with --bin /path/to/stackplz (or place ./stackplz here)."
}

push_local_bin() {
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
elif [ -f "./stackplz" ]; then
  push_local_bin "./stackplz"
else
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

# ---- brk mode needs a live PID -------------------------------------------
PID=""
if [ "$MODE" = "brk" ]; then
  PID="$(adbx shell su -c "pidof $PKG" 2>/dev/null | tr -d '\r' | awk '{print $1}')"
  [ -n "$PID" ] || die "brk mode: '$PKG' is not running. Launch the app first (the breakpoint attaches to a live process)."
  err "brk target pid: $PID"
fi

# ---- output dir -----------------------------------------------------------
mkdir -p "$OUT"
LOCAL_STDOUT="$OUT/stackplz_stdout.log"
LOCAL_JSON="$OUT/stackplz_events.json"

# ---- build the remote stackplz command -----------------------------------
# stackplz streams events to stdout; -o also writes them to a file we pull.
# --json makes both machine-parseable (schema varies by version; the parser
# degrades gracefully). --stack/--regs/--dumphex give the RE payload.
BUF_ARG=""
[ -n "$BUFFER" ] && BUF_ARG="-b $BUFFER"

case "$MODE" in
  syscall)
    REMOTE_CMD="$REMOTE_BIN -n $PKG --syscall $SYSCALLS --stack --dumphex --json -o $REMOTE_JSON $BUF_ARG $EXTRA"
    ;;
  uprobe)
    REMOTE_CMD="$REMOTE_BIN -n $PKG --lib $LIB --point '$POINT' --stack --regs --dumphex --json -o $REMOTE_JSON $BUF_ARG $EXTRA"
    ;;
  brk)
    # Lib-relative offset mode (--brk-lib). Only lib offsets are used here;
    # never a raw kernel address, which stackplz warns can reboot the device.
    REMOTE_CMD="$REMOTE_BIN --pid $PID --brk ${BRK}:${BRK_TYPE} --brk-lib $LIB --stack --regs --dumphex --json -o $REMOTE_JSON $BUF_ARG $EXTRA"
    ;;
esac

# ---- cleanup / artifact pull ---------------------------------------------
cleanup() {
  trap - INT TERM EXIT
  err ""
  err "Stopping trace; killing remote stackplz ..."
  adbx shell su -c "pkill -x stackplz" >/dev/null 2>&1 \
    || adbx shell su -c "pkill stackplz" >/dev/null 2>&1 || true
  sleep 1
  err "Pulling $REMOTE_JSON -> $LOCAL_JSON ..."
  adbx pull "$REMOTE_JSON" "$LOCAL_JSON" >/dev/null 2>&1 \
    || err "WARNING: could not pull $REMOTE_JSON (did any event fire? try --duration or a different --point/--brk)."
  err "Artifacts in: $OUT"
  err "Next: python3 scripts/stackplz_parse.py $LOCAL_JSON --out $OUT   (falls back to $LOCAL_STDOUT)"
}
trap cleanup INT TERM EXIT

# ---- BIG reminder ---------------------------------------------------------
err "########################################################################"
err "#  stackplz starting in '$MODE' mode on $PKG.                            "
err "#  >>> Now trigger the target action in the app (e.g. LOGIN). <<<        "
err "#  Press Ctrl-C (or wait for --duration) to STOP and pull artifacts.     "
err "########################################################################"
[ -n "$DURATION" ] && err "Auto-stop after ${DURATION}s."
err "Remote command: su -c \"$REMOTE_CMD\""

# ---- run ------------------------------------------------------------------
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

run_stream() {
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" "$DURATION" "${ADB[@]}" shell su -c "$REMOTE_CMD"
  else
    adbx shell su -c "$REMOTE_CMD"
  fi
}

set +e
run_stream | tee "$LOCAL_STDOUT"
RC="${PIPESTATUS[0]}"
set -e

if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ] && [ "$RC" -ne 130 ] && [ "$RC" -ne 143 ]; then
  err "NOTE: stackplz exited with code $RC."
fi

# cleanup() runs via EXIT trap and pulls artifacts.
exit 0
