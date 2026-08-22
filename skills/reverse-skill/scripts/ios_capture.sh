#!/usr/bin/env bash
# ios_capture.sh — iP2 live TLS capture for iOS (PlayCover) mode.
# The iOS counterpart of ecapture_run.sh. There is no eBPF on macOS, so the
# default is a Frida Interceptor on the system BoringSSL record layer
# (assets/frida/ios/ssl_dump.js): plaintext below TLS, no proxy, no CA, pinning
# irrelevant. Output is reassembled by the EXISTING scripts/ecapture_parse.py
# (ssl_dump.js emits the same "Write/Read Data" + hexdump framing).
#
# Usage:
#   ios_capture.sh <ExecutableName | com.bundle.id | /path/App.app> [options]
#     --out DIR       output root (default: ./re_out)
#     --spawn         frida -f (spawn-gate): hook before the app's init runs
#                     (needed to beat early anti-debug; see the reference)
#     --attach        frida -n (default): attach to the running process
#     --anti          also load anti_debug_bypass.js (use with --spawn)
#     --socket        capture with socket_dump.js instead (non-HTTP transports)
#     --script FILE   load an additional/replacement Frida script
#     --proxy         set the macOS system proxy for a mitmproxy fallback and
#                     print the CA-trust + disable-h3 recipe (no Frida)
#     --unset-proxy   revert the system proxy changes made by --proxy
#     --service NAME  network service for --proxy (default: auto-detect)
#     --host HOST:PORT proxy endpoint for --proxy (default 127.0.0.1:8080)
#
# No network calls of its own. Portable; every mac-only tool degrades to a hint.
set -euo pipefail

log() { printf '%s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRIDA_DIR="$SKILL_DIR/assets/frida/ios"

usage() { awk 'NR>1 && /^#/{sub(/^# ?/,""); print; next} NR>1{exit}' "$0"; }

# ---------------------------------------------------------------- args --------
TARGET=""; OUT="./re_out"; MODE="attach"; ANTI=0; USE_SOCKET=0
EXTRA_SCRIPT=""; DO_PROXY=0; UNSET_PROXY=0; SERVICE=""; PROXY_HOST="127.0.0.1:8080"
while [ $# -gt 0 ]; do
  case "$1" in
    --out)         OUT="${2:?}"; shift 2;;
    --spawn)       MODE="spawn"; shift;;
    --attach)      MODE="attach"; shift;;
    --anti)        ANTI=1; shift;;
    --socket)      USE_SOCKET=1; shift;;
    --script)      EXTRA_SCRIPT="${2:?}"; shift 2;;
    --proxy)       DO_PROXY=1; shift;;
    --unset-proxy) UNSET_PROXY=1; shift;;
    --service)     SERVICE="${2:?}"; shift 2;;
    --host)        PROXY_HOST="${2:?}"; shift 2;;
    -h|--help)     usage; exit 0;;
    -*)            log "Unknown option: $1"; usage; exit 1;;
    *)             TARGET="$1"; shift;;
  esac
done

mkdir -p "$OUT"

# ---------------------------------------------------------------- proxy paths -
detect_service() {
  networksetup -listnetworkserviceorder 2>/dev/null \
    | awk -F'[()]' '/\([0-9]+\)/{print $2}' | sed 's/^ *//' | head -1
}

if [ "$UNSET_PROXY" -eq 1 ]; then
  have networksetup || { log "ERROR: networksetup is macOS-only"; exit 1; }
  [ -z "$SERVICE" ] && SERVICE="$(detect_service)"
  log "[proxy] disabling web/secure proxy on '$SERVICE'"
  networksetup -setwebproxystate "$SERVICE" off || true
  networksetup -setsecurewebproxystate "$SERVICE" off || true
  exit 0
fi

if [ "$DO_PROXY" -eq 1 ]; then
  have networksetup || { log "ERROR: networksetup is macOS-only"; exit 1; }
  [ -z "$SERVICE" ] && SERVICE="$(detect_service)"
  PH_HOST="${PROXY_HOST%%:*}"; PH_PORT="${PROXY_HOST##*:}"
  log "[proxy] setting system proxy on '$SERVICE' -> $PH_HOST:$PH_PORT"
  networksetup -setwebproxy "$SERVICE" "$PH_HOST" "$PH_PORT"
  networksetup -setsecurewebproxy "$SERVICE" "$PH_HOST" "$PH_PORT"
  cat >&2 <<EOF

[proxy] system proxy set. Fallback capture path (terminating TLS):
  1) Run mitmproxy:            mitmproxy            # or mitmweb, listens :8080
  2) Trust its CA (once):
       sudo security add-trusted-cert -d -r trustRoot \\
         -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem
  3) If the app PINS, add Frida unpinning:
       frida -n "<Exec>" -l "$FRIDA_DIR/ssl_unpin.js"
  4) If nothing shows up, the app may be on HTTP/3 (QUIC) — mitmproxy won't see
     it. Disable h3 / block outbound UDP 443 to force TLS-over-TCP, or use the
     default ssl_dump.js path instead (it needs none of this).
  Revert when done:            $0 --unset-proxy --service "$SERVICE"

Note: Flutter uses its own CA store — the system proxy will NOT intercept it.
EOF
  exit 0
fi

# ---------------------------------------------------------------- frida path --
[ -z "$TARGET" ] && { log "ERROR: no target (executable name / bundle id / .app)"; usage; exit 1; }

if ! have frida; then
  log "hint: frida not on PATH -> pip install frida-tools"
  log "      (iOS mode uses LOCAL host Frida — no device, no frida-server)"
  exit 1
fi

# Choose the capture script(s).
PRIMARY="$FRIDA_DIR/ssl_dump.js"
[ "$USE_SOCKET" -eq 1 ] && PRIMARY="$FRIDA_DIR/socket_dump.js"
[ -f "$PRIMARY" ] || { log "ERROR: capture script missing: $PRIMARY"; exit 1; }

LOAD_ARGS=()
if [ "$ANTI" -eq 1 ]; then LOAD_ARGS+=(-l "$FRIDA_DIR/anti_debug_bypass.js"); fi
LOAD_ARGS+=(-l "$PRIMARY")
[ -n "$EXTRA_SCRIPT" ] && LOAD_ARGS+=(-l "$EXTRA_SCRIPT")

LOG="$OUT/ssl_dump.log"
: > "$LOG"

log "[frida] mode=$MODE target=$TARGET"
log "[frida] scripts: ${LOAD_ARGS[*]}"
log "[frida] logging plaintext -> $LOG  (Ctrl-C to stop, then it auto-parses)"

# Run frida in the foreground, tee stdout to the log. On Ctrl-C, frida exits and
# we parse what we captured. `set +e` so a non-zero frida exit still parses.
set +e
if [ "$MODE" = "spawn" ]; then
  frida -f "$TARGET" "${LOAD_ARGS[@]}" --no-pause 2>&1 | tee -a "$LOG"
else
  frida -n "$TARGET" "${LOAD_ARGS[@]}" 2>&1 | tee -a "$LOG"
fi
set -e

# ---------------------------------------------------------------- parse -------
if [ -s "$LOG" ] && [ -f "$SCRIPT_DIR/ecapture_parse.py" ] && have python3; then
  log "[parse] ecapture_parse.py $LOG -> $OUT/requests.json"
  python3 "$SCRIPT_DIR/ecapture_parse.py" "$LOG" --out "$OUT" || \
    log "[parse] parser returned non-zero (log kept at $LOG)"
else
  log "[parse] skipped (empty log or parser/python3 unavailable); raw log at $LOG"
fi
