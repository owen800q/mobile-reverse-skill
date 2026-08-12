#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  fetch)
    shift
    exec /opt/cloakbrowser-ci/fetch.sh "$@"
    ;;
  verify-target)
    shift
    exec /opt/cloakbrowser-ci/verify_target.sh "$@"
    ;;
  restore-session)
    python - <<'PY'
import json
import os
from pathlib import Path

raw = os.environ.get("KANXUE_SESSION_STATE", "")
if not raw:
    raise SystemExit("KANXUE_SESSION_STATE is empty")
state = json.loads(raw)
cookies = state.get("cookies") or []
if not cookies:
    raise SystemExit("KANXUE_SESSION_STATE has no cookies")
path = Path("/repo/tools/kanxue-crawler/.session-state.json")
path.write_text(raw)
path.chmod(0o600)
print(f"restored {len(cookies)} cookies")
PY
    ;;
  verify-stealth)
    shift
    export CRAWLER_BROWSER_EXECUTABLE=/opt/cloakbrowser-ci/launch_cloakbrowser.sh
    # --headed needs a display and the image has no X server, so give it a virtual one
    # rather than dying with Playwright's "Missing X server or $DISPLAY".  This is worth
    # having beyond convenience: a browser on a real (if virtual) display is a different
    # signal to anti-bot systems than --headless=new, which is the reason to reach for
    # --headed in the first place.
    if [[ " $* " == *" --headed "* && -z "${DISPLAY:-}" ]]; then
      exec xvfb-run -a --server-args="-screen 0 1440x950x24" \
        python /opt/cloakbrowser-ci/verify_stealth.py "$@"
    fi
    exec python /opt/cloakbrowser-ci/verify_stealth.py "$@"
    ;;
  crawl)
    shift
    git config --global --add safe.directory /repo
    export CRAWLER_BROWSER_EXECUTABLE=/opt/cloakbrowser-ci/launch_cloakbrowser.sh
    # In the container there is no bundled Chromium to fall back to, so a lost env var
    # would fail at launch anyway - but fail with a sentence that says why.
    export CRAWLER_REQUIRE_CLOAK=1
    exec "$@"
    ;;
  shell)
    shift
    exec bash "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
