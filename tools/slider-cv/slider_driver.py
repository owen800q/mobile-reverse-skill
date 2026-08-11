#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drive a jigsaw-slider captcha in a Playwright page: measure, aim, drag, verify.

`slider_cv` answers *where the gap is* in background-image pixels. Getting the
piece there needs three more things, and each of them is a place naive solvers
lose:

1. **Two render scales.** The sprites are almost never displayed at their natural
   size, and rarely at the *same* scale as each other (a 60x158 piece drawn at
   60.75x160 over a 320x160 background is the common case). The gap's x and the
   piece's resting x therefore have to be converted into CSS pixels separately
   before they can be subtracted.

2. **The slider-to-piece transfer function.** Dragging the handle by N px does
   not move the piece by N px. 网易易盾 has a dead zone of ~10 px before the piece
   starts to follow, then tracks 1:1, then saturates when the piece reaches the
   right edge - other widgets scale by (bgWidth - pieceWidth) / (trackWidth -
   handleWidth) instead. Rather than hard-code any of that, this driver *closes
   the loop*: it reads the piece's real rendered position mid-drag and corrects.
   Overshoot-then-adjust is what a human does anyway.

3. **The trajectory.** These widgets score the mouse trace, so the drag is
   generated from an ease-out velocity profile with per-step jitter, a small
   overshoot, a settle, and a pause before release - not a straight interpolation
   at constant speed.

Use it as a library:

    from slider_driver import solve_slider, YIDUN
    ok = solve_slider(page, YIDUN)

or as a bench, which is how the accuracy numbers in README.md were produced:

    python slider_driver.py --url https://... --rounds 20
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slider_cv import locate_gap  # noqa: E402


# --------------------------------------------------------------------------------------
# Site profiles
# --------------------------------------------------------------------------------------

@dataclass
class SliderProfile:
    """Everything site-specific lives here; the algorithm below is generic."""
    name: str
    background: str          # <img> of the scene with the veiled gap
    piece: str               # <img> RGBA sprite that slides
    handle: str              # the element the user presses and drags
    ready: str               # appears once a challenge is loaded
    refresh: str = ""        # click to draw a new challenge
    success: str = ""        # appears on a correct solve
    failure: str = ""        # appears on a wrong one


YIDUN = SliderProfile(
    name="yidun",
    background=".yidun_bg-img",
    piece=".yidun_jigsaw",
    handle=".yidun_slider",
    ready=".yidun_bg-img",
    refresh=".yidun_refresh, .yidun_refresh-icon, .yidun_control-refresh",
    # The verdict is a modifier class on the widget root, not a tip element: the
    # `.yidun_tips*` nodes exist (empty) from the start and never carry it.
    success=".yidun--success",
    failure=".yidun--error, .yidun--fail, .yidun--warn",
)

PROFILES = {"yidun": YIDUN}


# --------------------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------------------

_GEOM_JS = """(sel) => {
  const q = s => document.querySelector(s);
  const box = el => { const r = el.getBoundingClientRect();
                      return {x: r.x, y: r.y, w: r.width, h: r.height}; };
  const bg = q(sel.background), pc = q(sel.piece), hd = q(sel.handle);
  if (!bg || !pc || !hd) return null;
  if (!bg.complete || !pc.complete || !bg.naturalWidth || !pc.naturalWidth) return null;
  return {bg: box(bg), bgNat: {w: bg.naturalWidth, h: bg.naturalHeight}, bgSrc: bg.currentSrc || bg.src,
          piece: box(pc), pieceNat: {w: pc.naturalWidth, h: pc.naturalHeight},
          pieceSrc: pc.currentSrc || pc.src, handle: box(hd)};
}"""


def read_geometry(page, profile, timeout_ms=30000):
    """Wait for a fully decoded challenge and return the DOM geometry."""
    page.wait_for_selector(profile.ready, timeout=timeout_ms)
    sel = {"background": profile.background, "piece": profile.piece, "handle": profile.handle}
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        g = page.evaluate(_GEOM_JS, sel)
        if g:
            return g
        page.wait_for_timeout(200)
    raise TimeoutError("captcha images never finished loading")


def fetch_images(page, geom):
    """Pull both sprites through the page's own request context.

    Using `page.request` keeps the cookies, referer and proxy of the session, so a
    CDN that rejects a bare urllib fetch still serves us the exact bytes the
    browser is displaying.
    """
    bg = page.request.get(geom["bgSrc"]).body()
    piece = page.request.get(geom["pieceSrc"]).body()
    return bg, piece


def compute_distance(geom, gap):
    """CSS pixels the piece must travel, from the gap result and the two render scales."""
    bg_scale = geom["bg"]["w"] / float(geom["bgNat"]["w"])
    piece_scale = geom["piece"]["h"] / float(geom["pieceNat"]["h"])
    # Where the piece's left edge sits now, and where it has to end up - both in page
    # coordinates, because the two <img> elements need not share an origin.
    piece_now = geom["piece"]["x"] + gap.piece_x * piece_scale
    target = geom["bg"]["x"] + gap.x * bg_scale
    return target - piece_now, piece_now, target


def piece_page_x(page, profile, piece_x, piece_scale):
    """Current page-x of the piece's opaque left edge (what we are steering)."""
    box = page.evaluate("""(s) => { const el = document.querySelector(s);
        const r = el.getBoundingClientRect(); return {x: r.x, h: r.height}; }""", profile.piece)
    return box["x"] + piece_x * piece_scale


# --------------------------------------------------------------------------------------
# Trajectory
# --------------------------------------------------------------------------------------

def human_track(distance, rng=random):
    """An ease-out drag with a small overshoot and a settle, as (dx, dt_ms) steps.

    Velocity rises fast and decays - the shape a real arm produces - and every step
    is jittered so no two drags share a profile. The overshoot-and-correct tail is
    both realistic and useful: it leaves the piece approaching its target from the
    right, which is where the closed-loop correction picks up.
    """
    steps = []
    if distance <= 0:
        return steps
    overshoot = rng.uniform(2.0, 7.0) if distance > 40 else rng.uniform(0.5, 2.0)
    peak = distance + overshoot
    n = max(14, min(60, int(distance / rng.uniform(3.0, 6.0))))
    travelled = 0.0
    for i in range(1, n + 1):
        # ease-out cubic on position, so velocity decays smoothly to ~0
        t = i / float(n)
        want = peak * (1 - (1 - t) ** 3)
        dx = want - travelled
        dx *= rng.uniform(0.86, 1.14)                       # per-step speed jitter
        travelled += dx
        dt = rng.uniform(7, 16) + (10 * (t ** 2) if t > 0.7 else 0)   # slow down near the end
        steps.append((dx, rng.uniform(-0.6, 0.6), dt))
    # settle back from the overshoot in two or three human-sized corrections
    back = travelled - distance
    for k in range(rng.randint(2, 3)):
        d = -back / (2.0 if k == 0 else 1.0)
        back += d
        steps.append((d, rng.uniform(-0.4, 0.4), rng.uniform(40, 90)))
    return steps


# --------------------------------------------------------------------------------------
# Solve
# --------------------------------------------------------------------------------------

@dataclass
class SolveReport:
    ok: bool = False
    distance: float = 0.0
    gap_x: float = 0.0
    confidence: float = 0.0
    method: str = ""
    residual: float = 0.0        # px between the piece and the gap at release
    corrections: int = 0
    error: str = ""
    detections: list = field(default_factory=list)


def drag_to(page, profile, geom, distance, piece_x, piece_scale, rng=random,
            max_corrections=3, tolerance=0.6):
    """Press the handle, run the trajectory, then close the loop on the real position."""
    h = geom["handle"]
    sx = h["x"] + h["w"] / 2.0
    sy = h["y"] + h["h"] / 2.0
    target = piece_page_x(page, profile, piece_x, piece_scale) + distance

    page.mouse.move(sx + rng.uniform(-2, 2), sy + rng.uniform(-2, 2))
    page.wait_for_timeout(int(rng.uniform(60, 180)))
    page.mouse.down()
    page.wait_for_timeout(int(rng.uniform(40, 120)))

    cx, cy = sx, sy
    for dx, dy, dt in human_track(distance, rng):
        cx += dx
        cy += dy
        page.mouse.move(cx, cy)
        page.wait_for_timeout(int(dt))

    # Closed loop: the handle-to-piece transfer is unknown (dead zones, scaling,
    # saturation), so steer on the piece's *measured* position instead of trusting it.
    corrections = 0
    residual = target - piece_page_x(page, profile, piece_x, piece_scale)
    for _ in range(max_corrections):
        if abs(residual) <= tolerance:
            break
        before = piece_page_x(page, profile, piece_x, piece_scale)
        step = residual
        cx += step
        page.mouse.move(cx, cy)
        page.wait_for_timeout(int(rng.uniform(60, 140)))
        after = piece_page_x(page, profile, piece_x, piece_scale)
        corrections += 1
        moved = after - before
        if abs(step) > 0.5 and abs(moved) < 0.1:
            # dead zone or saturation: nudge harder once, then give up on precision
            cx += math.copysign(max(6.0, abs(step)), step)
            page.mouse.move(cx, cy)
            page.wait_for_timeout(int(rng.uniform(60, 140)))
        residual = target - piece_page_x(page, profile, piece_x, piece_scale)

    page.wait_for_timeout(int(rng.uniform(120, 320)))
    page.mouse.up()
    return residual, corrections


def solve_slider(page, profile=YIDUN, rng=random, settle_ms=1600, debug_dir=None):
    """Solve one challenge on the current page. Returns a SolveReport."""
    rep = SolveReport()
    try:
        geom = read_geometry(page, profile)
        bg_bytes, piece_bytes = fetch_images(page, geom)
        gap = locate_gap(bg_bytes, piece_bytes)
        piece_scale = geom["piece"]["h"] / float(geom["pieceNat"]["h"])
        distance, _, _ = compute_distance(geom, gap)

        rep.distance = distance
        rep.gap_x = gap.x
        rep.confidence = gap.confidence
        rep.method = gap.method
        rep.detections = [(d.method, round(d.x, 1), round(d.score, 3)) for d in gap.detections]

        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            stamp = "%d" % (time.time() * 1000)
            open(os.path.join(debug_dir, stamp + "_bg.jpg"), "wb").write(bg_bytes)
            open(os.path.join(debug_dir, stamp + "_piece.png"), "wb").write(piece_bytes)
            from slider_cv import annotate
            annotate(bg_bytes, piece_bytes, gap, os.path.join(debug_dir, stamp + "_gap.png"))

        rep.residual, rep.corrections = drag_to(
            page, profile, geom, distance, gap.piece_x, piece_scale, rng)
        page.wait_for_timeout(settle_ms)
        rep.ok = verify(page, profile)
    except Exception as exc:                       # a captcha failure must never kill a crawl
        rep.error = "%s: %s" % (type(exc).__name__, exc)
    return rep


def verify(page, profile):
    """Did the widget accept it? Falls back to 'the challenge is gone' when it has no tip."""
    if profile.success:
        try:
            if page.query_selector(profile.success):
                return True
        except Exception:
            pass
    if profile.failure:
        try:
            if page.query_selector(profile.failure):
                return False
        except Exception:
            pass
    try:                     # the widget tears itself down (or the page navigates) on success
        return page.query_selector(profile.handle) is None
    except Exception:
        return True


def refresh(page, profile):
    if not profile.refresh:
        return False
    try:
        el = page.query_selector(profile.refresh)
        if el:
            el.click()
            page.wait_for_timeout(1200)
            return True
    except Exception:
        pass
    return False


def solve_with_retries(page, profile=YIDUN, attempts=4, rng=random, debug_dir=None):
    """Try until the widget accepts, redrawing the challenge between attempts."""
    last = SolveReport(error="no attempt made")
    for i in range(attempts):
        last = solve_slider(page, profile, rng=rng, debug_dir=debug_dir)
        if last.ok:
            return last
        if i < attempts - 1:
            refresh(page, profile)
            page.wait_for_timeout(int(rng.uniform(600, 1400)))
    return last


# --------------------------------------------------------------------------------------
# Bench
# --------------------------------------------------------------------------------------

def _bench(argv=None):
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description="Measure solve accuracy against a live widget")
    ap.add_argument("--url", required=True)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--profile", default="yidun", choices=sorted(PROFILES))
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--browser", default=os.environ.get("CRAWLER_BROWSER_EXECUTABLE", ""))
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY", ""))
    ap.add_argument("--browser-arg", action="append", default=[])
    ap.add_argument("--debug-dir", default="")
    ap.add_argument("--fresh", action="store_true",
                    help="click refresh before each round; a reload alone can re-serve a "
                         "cached challenge, which flatters the pass rate")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    profile = PROFILES[a.profile]

    launch = {"headless": not a.headed,
              "args": ["--no-sandbox", "--disable-dev-shm-usage"] + a.browser_arg}
    if a.browser:
        launch["executable_path"] = a.browser
    if a.proxy:
        launch["proxy"] = {"server": a.proxy}

    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(**launch)
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(a.url, wait_until="domcontentloaded", timeout=60000)
        seen = set()
        for i in range(a.rounds):
            if a.fresh:
                try:
                    read_geometry(page, profile, timeout_ms=20000)
                except Exception:
                    page.goto(a.url, wait_until="domcontentloaded", timeout=60000)
                refresh(page, profile)
            try:
                seen.add(read_geometry(page, profile)["bgSrc"])
            except Exception:
                pass
            r = solve_slider(page, profile, debug_dir=a.debug_dir or None)
            results.append(r)
            print("%2d %-4s dist=%7.2f gap=%6.1f conf=%.2f via %-22s resid=%+5.2f corr=%d %s"
                  % (i, "PASS" if r.ok else "fail", r.distance, r.gap_x, r.confidence,
                     r.method, r.residual, r.corrections, r.error))
            sys.stdout.flush()
            if not refresh(page, profile):
                page.goto(a.url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
        b.close()

    ok = sum(1 for r in results if r.ok)
    print("\n%d/%d passed (%.0f%%) over %d distinct challenge image(s)"
          % (ok, len(results), 100.0 * ok / max(1, len(results)), len(seen)))
    if a.json:
        print(json.dumps([r.__dict__ for r in results], indent=1, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_bench())
