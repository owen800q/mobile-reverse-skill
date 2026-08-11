#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression test for slider_cv: synthesise challenges with known ground truth.

Real challenges make a poor test fixture - the answer has to be eyeballed, the
images belong to someone else, and a test that needs the network is not a test.
So this renders its own: a procedural scene, a puzzle silhouette cut from it at a
known x, and the same translucent veil + bevel the real widget draws.

The cases are chosen to be the ones that actually break detectors:

  flat            a smooth gradient sky - almost no texture, which is where ZNCC
                  degenerates and the whole vote rests on `contour`
  dark_veil       the overlay darkens instead of lightens (both occur live), which
                  kills any detector that assumes a sign
  scaled          piece authored smaller than the background (60x158 over 320x160,
                  the real geometry) - catches a missing scale correction
  subpixel        gap at a non-integer x - catches an off-by-one in the parabolic fit
  low_contrast    heavy haze over texture: veil barely visible

    python test_slider_cv.py            # run them
    python test_slider_cv.py --dump DIR # also write the fixtures + overlays to look at
"""

from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slider_cv import locate_gap, annotate  # noqa: E402

TOLERANCE_PX = 2.0
PIECE = 55           # puzzle side, in background pixels


def _scene(w, h, kind, seed):
    """A background with a controllable amount of texture."""
    rng = np.random.RandomState(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if kind == "flat":
        base = 120 + 90 * (yy / h)                                  # smooth sky gradient
        img = np.dstack([base + 25, base + 12, base]).astype(np.float32)
    elif kind == "haze":
        base = 150 + 40 * (yy / h) + 8 * np.sin(xx / 9.0)
        noise = cv2.GaussianBlur(rng.normal(0, 14, (h, w)).astype(np.float32), (0, 0), 1.5)
        img = np.dstack([base + noise, base + noise * 0.9, base + noise * 0.8])
    else:                                                            # busy
        noise = rng.normal(0, 60, (h, w, 3)).astype(np.float32)
        img = cv2.GaussianBlur(noise, (0, 0), 1.1) + 128
        for _ in range(24):                                          # hard structural edges
            x0, y0 = rng.randint(0, w - 20), rng.randint(0, h - 20)
            cv2.rectangle(img, (x0, y0), (x0 + rng.randint(6, 40), y0 + rng.randint(6, 40)),
                          tuple(float(v) for v in rng.randint(0, 255, 3)), -1)
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return np.clip(img, 0, 255).astype(np.uint8)


def _silhouette(size):
    """A classic jigsaw outline: a square with one knob out and one notch in."""
    m = np.zeros((size, size), np.uint8)
    pad = size // 6
    cv2.rectangle(m, (pad, pad), (size - pad, size - pad), 255, -1)
    r = size // 7
    cv2.circle(m, (size // 2, pad), r, 255, -1)              # knob on the top edge
    cv2.circle(m, (size - pad, size // 2), r, 255, -1)       # knob on the right edge
    cv2.circle(m, (size // 2, size - pad), r, 0, -1)         # notch on the bottom edge
    return m


def make_challenge(gap_x, gap_y, kind="busy", veil="light", seed=0,
                   bg_size=(320, 160), piece_canvas=(60, 158), piece_x0=3):
    """Render (background_with_gap, RGBA piece). Returns them plus the truth."""
    bw, bh = bg_size
    scene = _scene(bw, bh, kind, seed)
    mask = _silhouette(PIECE)

    # --- the piece: the scene content at the gap, cut to the silhouette -----------
    gx, gy = int(round(gap_x)), int(round(gap_y))
    content = scene[gy:gy + PIECE, gx:gx + PIECE].copy()
    cw, ch = piece_canvas
    # Author the sprite at its own scale, the way the real widget does - but on an exact
    # sampling grid.  cv2.resize would stretch the crop to fill a rounded integer size
    # (55 -> 54 here, a magnification of 54/55 rather than 158/160), which puts a
    # geometric error in the *fixture*.  A test whose ground truth is off by half a pixel
    # measures the fixture, not the detector - and worse, it would silently reward a
    # detector carrying the matching error.
    s = ch / float(bh)
    side = int(np.ceil(PIECE * s))
    m = np.float32([[s, 0.0, 0.0], [0.0, s, 0.0]])
    content_s = cv2.warpAffine(content, m, (side, side), flags=cv2.INTER_AREA,
                               borderMode=cv2.BORDER_REPLICATE)
    mask_s = cv2.warpAffine(mask, m, (side, side), flags=cv2.INTER_AREA,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    piece = np.zeros((ch, cw, 4), np.uint8)
    py0 = int(round(gap_y * s))
    piece[py0:py0 + side, piece_x0:piece_x0 + side, :3] = content_s
    piece[py0:py0 + side, piece_x0:piece_x0 + side, 3] = mask_s
    # a bright bevel along the rim, as the widget draws
    rim = cv2.dilate(mask_s, np.ones((3, 3), np.uint8)) - cv2.erode(mask_s, np.ones((3, 3), np.uint8))
    sub = piece[py0:py0 + side, piece_x0:piece_x0 + side, :3]
    sub[rim > 128] = np.clip(sub[rim > 128].astype(np.int32) + 70, 0, 255).astype(np.uint8)

    # --- the background: veil the same region ------------------------------------
    bg = scene.copy()
    region = bg[gy:gy + PIECE, gx:gx + PIECE].astype(np.float32)
    a = (mask / 255.0)[:, :, None]
    if veil == "light":
        toward, alpha = np.float32(235), 0.55
    elif veil == "dark":
        toward, alpha = np.float32(45), 0.55
    else:                                       # subtle
        toward, alpha = np.float32(210), 0.30
    veiled = region * (1 - alpha) + toward * alpha
    bg[gy:gy + PIECE, gx:gx + PIECE] = np.clip(region * (1 - a) + veiled * a, 0, 255).astype(np.uint8)
    rimb = cv2.dilate(mask, np.ones((3, 3), np.uint8)) - cv2.erode(mask, np.ones((3, 3), np.uint8))
    patch = bg[gy:gy + PIECE, gx:gx + PIECE]
    patch[rimb > 128] = np.clip(patch[rimb > 128].astype(np.int32) + 45, 0, 255).astype(np.uint8)

    # Ground truth is stated the way `locate_gap` reports it: the left edge of the
    # *opaque* bounding box, not of the square block the silhouette was drawn into.
    # (The silhouette is inset by `pad` within its block, so the two differ by ~9 px -
    # exactly the kind of off-by-inset that makes a correct detector look broken.)
    mxs = np.nonzero(mask.max(axis=0) > 16)[0]
    mss = np.nonzero(mask_s.max(axis=0) > 16)[0]
    truth_gap_x = gx + int(mxs.min())
    truth_piece_x = piece_x0 + int(mss.min())
    piece_scale = bh / float(ch)
    return bg, piece, {"gap_x": float(truth_gap_x), "gap_y": float(gy),
                       "piece_x": float(truth_piece_x),
                       "drag": truth_gap_x * 1.0 - truth_piece_x * piece_scale,
                       "piece_scale": piece_scale, "bg_scale": 1.0}


CASES = [
    # name,          gap_x, gap_y, scene,  veil,      seed
    ("busy",           180,    50, "busy",  "light",   1),
    ("flat",           120,    90, "flat",  "light",   2),
    ("dark_veil",      210,    30, "busy",  "dark",    3),
    ("flat_dark",       95,    60, "flat",  "dark",    4),
    ("low_contrast",   150,    70, "haze",  "subtle",  5),
    ("near_left",       62,    20, "busy",  "light",   6),
    ("near_right",     255,    85, "busy",  "light",   7),
    ("haze_light",     200,    45, "haze",  "light",   8),
    ("subpixel",       137,    55, "busy",  "light",   9),
    ("flat_subtle",    170,    35, "flat",  "subtle", 10),
]


def run(dump=None):
    failures = []
    for name, gx, gy, kind, veil, seed in CASES:
        bg, piece, truth = make_challenge(gx, gy, kind=kind, veil=veil, seed=seed)
        bg_png = cv2.imencode(".png", bg)[1].tobytes()
        piece_png = cv2.imencode(".png", piece)[1].tobytes()
        r = locate_gap(bg_png, piece_png)
        err = r.x - truth["gap_x"]
        # the drag the driver would command, checked against the truth as well
        drag = r.drag_distance(truth["bg_scale"], truth["piece_scale"])
        derr = drag - truth["drag"]
        ok = abs(err) <= TOLERANCE_PX and abs(derr) <= TOLERANCE_PX
        print("%-14s gap %6.1f (truth %5.1f, err %+5.2f)  drag err %+5.2f  conf %.2f  %-22s %s"
              % (name, r.x, truth["gap_x"], err, derr, r.confidence, r.method,
                 "ok" if ok else "FAIL"))
        for d in r.detections:
            print("                 %-8s x=%6.1f err=%+6.2f score=%.2f"
                  % (d.method, d.x, d.x - truth["gap_x"], d.score))
        if dump:
            os.makedirs(dump, exist_ok=True)
            cv2.imwrite(os.path.join(dump, name + "_bg.png"), bg)
            cv2.imwrite(os.path.join(dump, name + "_piece.png"), piece)
            annotate(bg_png, piece_png, r, os.path.join(dump, name + "_found.png"))
        if not ok:
            failures.append(name)

    print("\n%d/%d within %.0f px" % (len(CASES) - len(failures), len(CASES), TOLERANCE_PX))
    if failures:
        print("FAILED: %s" % ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", help="write the fixtures and annotated overlays here")
    raise SystemExit(run(ap.parse_args().dump))
