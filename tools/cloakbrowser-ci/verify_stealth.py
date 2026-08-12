#!/usr/bin/env python3
"""Assert that the launched browser is actually cloaked, not merely alive.

verify_target.sh proves the patched binary boots and exposes DevTools.  That is not the
same as proving the fingerprint spoofing still works: the runtime patch neuters
LicenseRuntime::Start/End, and if CloakBrowser hangs any of its cloaking off that entry
point, the browser would still launch happily while behaving like plain headless
Chromium.  This script is the missing half of that check.

Two independent passes:

  local     in-page probes for the classic automation tells (navigator.webdriver, a
            HeadlessChrome UA, a SwiftShader/llvmpipe WebGL renderer, empty plugin and
            language lists, a UA that disagrees with the UA Client Hints).  No network,
            so this half is deterministic and safe to gate CI on.

  turnstile drives a live Cloudflare Turnstile widget and reports whether the widget
            issues a token.  Network-dependent and therefore advisory by default; pass
            --require-turnstile to make a failure fatal.

            NOTE the default URL, 2captcha's demo, embeds sitekey 3x00000000000000000000FF
            - Cloudflare's documented "always force an interactive challenge" test key.
            Passing it means the browser can complete a forced interactive challenge; the
            token it hands back is a test token with no server-side validity.  It is a
            behavioural smoke test, not a measurement of how a production Turnstile
            deployment would score this browser.

Usage:
    python verify_stealth.py --executable /opt/cloakbrowser-ci/launch_cloakbrowser.sh
    python verify_stealth.py --no-turnstile          # offline, local probes only
    python verify_stealth.py --headed --screenshot-dir out/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

try:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - the image always has it
    sys.exit("playwright is not installed.  pip install 'playwright>=1.40'")

DEFAULT_TURNSTILE_URL = "https://2captcha.com/demo/cloudflare-turnstile"

# Reads every signal in one round trip.  Kept to standard DOM/WebGL APIs so it behaves
# the same on the patched build and on stock Chromium, which is what makes the two
# comparable in a CI log.
PROBE_JS = r"""
() => {
  const out = {};
  out.userAgent = navigator.userAgent;
  out.webdriver = navigator.webdriver;
  out.platform = navigator.platform;
  out.languages = Array.from(navigator.languages || []);
  out.hardwareConcurrency = navigator.hardwareConcurrency;
  out.deviceMemory = navigator.deviceMemory ?? null;
  out.pluginCount = (navigator.plugins || []).length;
  out.mimeTypeCount = (navigator.mimeTypes || []).length;
  out.hasWindowChrome = typeof window.chrome === 'object' && window.chrome !== null;
  out.notificationPermission =
      (typeof Notification !== 'undefined') ? Notification.permission : null;

  // chromedriver injects a cdc_* property; CloakBrowser or plain Playwright should not.
  out.cdcKeys = Object.keys(window).filter(k => /^[$]?cdc_/.test(k));

  const uaData = navigator.userAgentData;
  if (uaData) {
    out.uaDataPlatform = uaData.platform;
    out.uaDataMobile = uaData.mobile;
    out.uaDataBrands = (uaData.brands || []).map(b => `${b.brand} ${b.version}`);
  } else {
    out.uaDataPlatform = null;
    out.uaDataBrands = null;
  }

  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      out.webglVendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null;
      out.webglRenderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null;
    } else {
      out.webglVendor = null;
      out.webglRenderer = null;
    }
  } catch (e) {
    out.webglError = String(e);
  }
  return out;
}
"""


def ua_major(ua: str):
    m = re.search(r"Chrome/(\d+)", ua or "")
    return int(m.group(1)) if m else None


def ua_platform(ua: str):
    ua = ua or ""
    if "Windows" in ua:
        return "Windows"
    if "Mac OS X" in ua or "Macintosh" in ua:
        return "macOS"
    if "Android" in ua:
        return "Android"
    if "Linux" in ua or "X11" in ua:
        return "Linux"
    return None


def evaluate(probe: dict) -> list[dict]:
    """Turn raw probe output into pass/fail rows."""
    checks = []

    def add(name, ok, detail, fatal=True):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "fatal": fatal})

    ua = probe.get("userAgent") or ""
    add("navigator.webdriver is not true",
        not probe.get("webdriver"),
        "navigator.webdriver=%r" % (probe.get("webdriver"),))
    add("UA is not a HeadlessChrome UA",
        "Headless" not in ua,
        ua)
    add("no chromedriver cdc_ globals",
        not probe.get("cdcKeys"),
        "cdcKeys=%r" % (probe.get("cdcKeys"),))
    add("window.chrome is present",
        probe.get("hasWindowChrome"),
        "hasWindowChrome=%r" % (probe.get("hasWindowChrome"),))
    add("navigator.plugins is not empty",
        (probe.get("pluginCount") or 0) > 0,
        "plugins=%s mimeTypes=%s"
        % (probe.get("pluginCount"), probe.get("mimeTypeCount")))
    add("navigator.languages is not empty",
        bool(probe.get("languages")),
        "languages=%r" % (probe.get("languages"),))
    add("hardwareConcurrency is plausible",
        (probe.get("hardwareConcurrency") or 0) > 0,
        "hardwareConcurrency=%r deviceMemory=%r"
        % (probe.get("hardwareConcurrency"), probe.get("deviceMemory")))

    renderer = probe.get("webglRenderer") or ""
    software = any(tag in renderer for tag in ("SwiftShader", "llvmpipe", "Mesa OffScreen"))
    add("WebGL renderer is not a software rasteriser",
        renderer and not software,
        "vendor=%r renderer=%r" % (probe.get("webglVendor"), renderer),
        fatal=False)   # a GPU-less runner legitimately has no hardware renderer

    # The checks the old launch options were actively failing: a UA claiming one
    # platform/version while the Client Hints claim another is a sharper signal than no
    # spoofing at all.  navigator.userAgentData only exists in a secure context, so on
    # about:blank these have nothing to compare and are reported as skipped rather than
    # passing vacuously.
    ua_plat, hints_plat = ua_platform(ua), probe.get("uaDataPlatform")
    brands = probe.get("uaDataBrands") or []
    if hints_plat is None and not brands:
        checks.append({"name": "UA agrees with UA Client Hints", "ok": True,
                       "skipped": True, "fatal": False,
                       "detail": "navigator.userAgentData unavailable "
                                 "(insecure context - probe over https to check this)"})
        return checks

    add("UA platform agrees with UA Client Hints",
        not (ua_plat and hints_plat) or ua_plat == hints_plat,
        "ua=%r uaData.platform=%r" % (ua_plat, hints_plat))

    # Playwright's user_agent option does reach userAgentData.platform, but nothing
    # rewrites navigator.platform - so a spoofed UA leaves this pair contradicting.
    nav_plat = probe.get("platform") or ""
    nav_plat_family = ("Windows" if "Win" in nav_plat else
                       "macOS" if "Mac" in nav_plat else
                       "Linux" if "Linux" in nav_plat or "X11" in nav_plat else None)
    add("UA platform agrees with navigator.platform",
        not (ua_plat and nav_plat_family) or ua_plat == nav_plat_family,
        "ua=%r navigator.platform=%r" % (ua_plat, nav_plat))

    brand_majors = {int(m.group(1))
                    for b in brands for m in [re.search(r"(\d+)$", b)] if m}
    major = ua_major(ua)
    add("UA Chrome major agrees with UA Client Hints",
        not (major and brand_majors) or major in brand_majors,
        "ua_major=%r brands=%r" % (major, brands))

    return checks


def run_turnstile(page, url, timeout_s, screenshot_dir, navigated=False,
                  failed_requests=None):
    """Return a result dict for the live Turnstile widget.

    `navigated` says the caller already loaded `url` (main does, so that the fingerprint
    probes run in a secure context where navigator.userAgentData exists), and
    `failed_requests` is the list it has been collecting since before that navigation.
    """
    started = time.time()
    result = {"url": url, "token": None, "elapsed_s": None, "ok": False, "note": "",
              "failed_requests": failed_requests if failed_requests is not None else []}
    if not navigated:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except PWTimeout:
            result["note"] = "navigation timed out"
            return result

    # Wait on page.frames, NOT on a DOM selector.  Cloudflare's challenge-platform frame
    # carries no matching src attribute in the DOM - querySelectorAll('iframe') does not
    # see it at all - so `iframe[src*=challenges.cloudflare.com]` reports "never mounted"
    # even while the widget is plainly running.
    def cf_frames():
        return [f for f in page.frames if "challenges.cloudflare.com" in f.url]

    bootstrap_deadline = time.time() + 30
    while not cf_frames() and time.time() < bootstrap_deadline:
        page.wait_for_timeout(500)
    if not cf_frames():
        result["note"] = "the Turnstile challenge frame never appeared"
        # Usually a blocked or failed challenges.cloudflare.com request rather than
        # anything about the fingerprint - say which, so the failure is actionable.
        blocked = [f for f in result.get("failed_requests", [])
                   if "cloudflare.com" in f["url"]]
        if blocked:
            result["note"] += " (%d cloudflare request(s) failed: %s)" % (
                len(blocked), blocked[0]["failure"])
        return result
    result["widget_rendered"] = False

    clicked = False
    deadline = started + timeout_s
    while time.time() < deadline:
        token = page.evaluate(
            "() => { const el = document.querySelector('[name=\"cf-turnstile-response\"]');"
            "        return el ? el.value : null; }"
        )
        if token:
            result.update(token=token, ok=True,
                          elapsed_s=round(time.time() - started, 1))
            break
        # A visible checkbox widget only exists once Cloudflare decides to render one.
        # Whether it ever does is itself the interesting signal on sitekey 3x...FF, which
        # forces the interactive variant: a client it dislikes gets stuck in the invisible
        # challenge loop and is never offered a checkbox to click.
        visible_widget = page.locator(".cf-turnstile iframe").count() > 0
        result["widget_rendered"] = result["widget_rendered"] or visible_widget
        if visible_widget and not clicked and time.time() - started > 4:
            try:
                frame = page.frame_locator(".cf-turnstile iframe")
                frame.locator("input[type='checkbox'], label").first.click(timeout=5_000)
                clicked = True
                result["note"] = "clicked the interactive checkbox"
            except Exception as exc:
                result["note"] = "could not click the checkbox: %s" % type(exc).__name__
                clicked = True   # do not spin on it
        page.wait_for_timeout(1_000)
    else:
        result["elapsed_s"] = round(time.time() - started, 1)
        if not result["note"]:
            result["note"] = ("no token before the timeout; Cloudflare never rendered a "
                              "visible widget" if not result.get("widget_rendered")
                              else "no token before the timeout")

    if screenshot_dir:
        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
        shot = Path(screenshot_dir) / ("turnstile-%s.png" % ("pass" if result["ok"] else "fail"))
        page.screenshot(path=str(shot), full_page=False)
        result["screenshot"] = str(shot)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executable",
                    default=os.environ.get("CRAWLER_BROWSER_EXECUTABLE"),
                    help="browser launcher (default: $CRAWLER_BROWSER_EXECUTABLE; "
                         "unset means Playwright's own Chromium, useful as a control)")
    ap.add_argument("--headed", action="store_true", help="show the window")
    ap.add_argument("--user-agent", default=None,
                    help="override navigator.userAgent, the way crawl.py used to "
                         "unconditionally.  Playwright applies this without touching the "
                         "UA Client Hints, so this is also how you reproduce the "
                         "UA/hints desync the consistency checks below look for.")
    ap.add_argument("--profile-dir", default=None,
                    help="persistent profile to launch with (default: a temp dir)")
    ap.add_argument("--proxy", default=None,
                    help="proxy server for the browser, e.g. http://127.0.0.1:8080")
    ap.add_argument("--ignore-https-errors", action="store_true",
                    help="needed behind a TLS-intercepting proxy")
    ap.add_argument("--browser-arg", action="append", default=[], metavar="ARG",
                    help="extra chromium flag, repeatable.  In a sandbox that MITMs "
                         "egress you will want --browser-arg=--no-proxy-server "
                         "--browser-arg=--ignore-certificate-errors, and should treat "
                         "the turnstile result as indicative only: the proxy re-originates "
                         "TLS, so Cloudflare fingerprints it and not this browser.")
    ap.add_argument("--url", default=DEFAULT_TURNSTILE_URL)
    ap.add_argument("--no-turnstile", action="store_true",
                    help="skip the network half, run the local probes only")
    ap.add_argument("--require-turnstile", action="store_true",
                    help="exit non-zero when the widget issues no token")
    ap.add_argument("--turnstile-timeout", type=int, default=90)
    ap.add_argument("--screenshot-dir", default=None)
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the full result as JSON to this path")
    a = ap.parse_args(argv)

    profile = a.profile_dir or tempfile.mkdtemp(prefix="cloak-stealth-")
    launch = {
        "headless": not a.headed,
        "viewport": {"width": 1440, "height": 950},
        "locale": "zh-CN",
        "ignore_https_errors": a.ignore_https_errors,
    }
    if a.executable:
        launch["executable_path"] = a.executable
    if a.proxy:
        launch["proxy"] = {"server": a.proxy}
    if a.browser_arg:
        launch["args"] = list(a.browser_arg)
    if a.user_agent:
        launch["user_agent"] = a.user_agent

    print("executable: %s" % (a.executable or "<playwright bundled chromium>"))
    print("profile   : %s" % profile)

    report = {"executable": a.executable, "checks": [], "turnstile": None}
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(profile, **launch)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            # Probe on the real page rather than about:blank: navigator.userAgentData is
            # gated on a secure context, and it is half of the UA-consistency check.
            navigated = False
            failed_requests = []
            page.on("requestfailed", lambda r: failed_requests.append(
                {"url": r.url, "failure": (r.failure or "")}))
            if not a.no_turnstile:
                try:
                    page.goto(a.url, wait_until="domcontentloaded", timeout=60_000)
                    navigated = True
                except PWTimeout:
                    print("! navigation to %s timed out; probing about:blank" % a.url)

            probe = page.evaluate(PROBE_JS)
            report["probe"] = probe
            report["checks"] = evaluate(probe)

            print("\n--- fingerprint probes ---")
            for c in report["checks"]:
                mark = ("SKIP" if c.get("skipped") else
                        "PASS" if c["ok"] else "FAIL" if c["fatal"] else "WARN")
                print("[%-4s] %-42s %s" % (mark, c["name"], c["detail"]))

            if not a.no_turnstile:
                print("\n--- cloudflare turnstile ---")
                report["turnstile"] = run_turnstile(
                    page, a.url, a.turnstile_timeout, a.screenshot_dir,
                    navigated=navigated, failed_requests=failed_requests)
                t = report["turnstile"]
                for f in t.get("failed_requests", [])[:5]:
                    print("       request failed: %s (%s)" % (f["url"][:100], f["failure"]))
                token = t.get("token") or ""
                print("[%s] %s" % ("PASS" if t["ok"] else "FAIL", t["url"]))
                print("       elapsed=%ss note=%s" % (t.get("elapsed_s"), t.get("note") or "-"))
                if token:
                    print("       token=%s... (%d chars)" % (token[:40], len(token)))
                if t.get("screenshot"):
                    print("       screenshot=%s" % t["screenshot"])
        finally:
            ctx.close()

    if a.json_out:
        Path(a.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print("\nwrote %s" % a.json_out)

    failed = [c["name"] for c in report["checks"] if c["fatal"] and not c["ok"]]
    warned = [c["name"] for c in report["checks"]
              if not c["fatal"] and not c["ok"] and not c.get("skipped")]
    skipped = [c["name"] for c in report["checks"] if c.get("skipped")]
    ran = len(report["checks"]) - len(skipped)
    print("\nsummary: %d/%d fingerprint checks passed, %d warning(s), %d skipped"
          % (ran - len(failed) - len(warned), ran, len(warned), len(skipped)))
    if report["turnstile"]:
        print("turnstile: %s" % ("token issued" if report["turnstile"]["ok"] else "no token"))
    if failed:
        print("FAILED: %s" % ", ".join(failed))
        return 1
    if a.require_turnstile and report["turnstile"] and not report["turnstile"]["ok"]:
        print("FAILED: turnstile issued no token and --require-turnstile was given")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
