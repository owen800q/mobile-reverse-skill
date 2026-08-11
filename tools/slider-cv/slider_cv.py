#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Locate the gap of a jigsaw ("slider") captcha with classical computer vision.

The problem
-----------
A slider captcha ships two images:

  background   the scene, with one puzzle-shaped region *veiled* - the site draws
               the piece's silhouette over the scene as a translucent grey/white
               overlay plus a bevelled rim.  That veiled region is the target.
  piece        a small RGBA sprite: the same scene content cut to the puzzle
               shape, transparent everywhere else.  The page overlays it on the
               background at x = 0 and the user drags it right onto the gap.

The answer is one number: how far right the piece must travel.  Because the
piece only ever moves horizontally, the gap sits at *exactly* the piece's own
vertical offset - which collapses a 2-D search into a 1-D one and removes most
of the false positives other implementations fight with.

Three detectors, one vote
-------------------------
No single cue survives every background, so this module scores three and lets
them vote (`locate_gap`):

`contour`   Matched filter on gradient *orientation*.  The alpha channel of the
            piece gives the exact silhouette; its gradient is the inward normal
            field along the puzzle contour.  Correlating that normal field with
            the background's gradient field answers "does an edge run along this
            exact puzzle outline here, everywhere at once?".  The overlay makes
            the gap either uniformly brighter or uniformly darker than its
            surroundings, so the response is strongly signed - we take |response|
            and stay agnostic about which.  Texture-independent, and the
            distinctive round tabs make it very selective.

`zncc`      Zero-mean normalised cross-correlation of the piece's texture,
            restricted to the alpha mask.  The gap is the same scene content
            under an affine brightness change (I = a*S + b), which is exactly
            what ZNCC is invariant to.  Near-perfect on textured scenes, noisy
            on flat sky/fog where the template carries almost no variance.
            OpenCV's own masked TM_CCOEFF_NORMED is unreliable, so the
            correlation is built here from TM_CCORR accumulations.

`veil`      Shape-matched filter on saturation and luma: the translucent overlay
            desaturates the region it covers, so the mean saturation inside the
            silhouette drops relative to a ring around it.  Cheap, and a good
            tie-breaker when the scene is flat enough to defeat `zncc`.

Voting is by agreement, not by raw score: detectors are calibrated differently,
but two independent methods landing within a few pixels of each other is strong
evidence.  A lone detector wins only on its own confidence.

Nothing here is site-specific: pass a background and an RGBA piece and it works.
`--dx` reports the drag distance once you tell it the two render scales.

CLI
---
    python slider_cv.py bg.jpg piece.png                  # gap x, per-method detail
    python slider_cv.py bg.jpg piece.png --debug out.png  # annotated overlay
    python slider_cv.py bg.jpg piece.png --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    sys.exit("slider_cv needs opencv + numpy:  pip install opencv-python-headless numpy")


# --------------------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------------------

@dataclass
class Detection:
    method: str
    x: float                 # gap left edge, in background pixels
    y: float                 # gap top edge, in background pixels
    score: float             # method-local confidence, roughly 0..1

    def as_tuple(self):
        return (self.x, self.y, self.score)


@dataclass
class GapResult:
    x: float                 # chosen gap left edge, in background pixels
    y: float
    confidence: float        # 0..1, folds in cross-method agreement
    method: str              # which detector (or consensus) produced `x`
    piece_x: float           # the piece's resting left edge, in *piece* pixels
    piece_y: float
    piece_w: float
    piece_h: float
    detections: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["detections"] = [asdict(x) if isinstance(x, Detection) else x for x in self.detections]
        return d

    def drag_distance(self, bg_scale=1.0, piece_scale=1.0):
        """Rendered pixels the piece must travel.

        `bg_scale`    displayed background width / natural background width
        `piece_scale` displayed piece height   / natural piece height

        The two sprites are often rendered at slightly different scales (a 60x158
        piece drawn 60.75x160 over a 320x160 background is the common case), so the
        subtraction has to happen in display space, not image space.
        """
        return self.x * bg_scale - self.piece_x * piece_scale


# --------------------------------------------------------------------------------------
# Shared preparation
# --------------------------------------------------------------------------------------

def _imread(src, flags=cv2.IMREAD_COLOR):
    """Accept a path, raw bytes, or an ndarray."""
    if isinstance(src, np.ndarray):
        return src
    if isinstance(src, (bytes, bytearray)):
        img = cv2.imdecode(np.frombuffer(bytes(src), np.uint8), flags)
    else:
        img = cv2.imread(str(src), flags)
    if img is None:
        raise ValueError("could not decode image")
    return img


def piece_bbox(alpha, thr=16):
    """Tight bounding box of the opaque part of the sprite."""
    ys, xs = np.nonzero(alpha > thr)
    if len(xs) == 0:
        raise ValueError("piece sprite has no opaque pixels - is it really RGBA?")
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


@dataclass
class _Prepared:
    bg: "np.ndarray"
    tpl: "np.ndarray"        # piece texture, cropped to the bbox, resampled to bg scale
    mask: "np.ndarray"       # matching alpha, 0..255
    x0: float                # bbox origin in *piece* pixels
    y0: float
    y0_bg: float             # the same origin expressed in background pixels
    w: int                   # template size in background pixels
    h: int


def _prepare(bg, piece):
    """Crop the sprite to its opaque bbox and resample it into background pixel scale."""
    if piece.ndim != 3 or piece.shape[2] != 4:
        raise ValueError("piece image must have an alpha channel (load with IMREAD_UNCHANGED)")
    alpha = piece[:, :, 3]
    x0, y0, w, h = piece_bbox(alpha)
    tpl = piece[y0:y0 + h, x0:x0 + w, :3]
    msk = alpha[y0:y0 + h, x0:x0 + w]
    # The sprite is usually authored a hair smaller than the background it overlays
    # (60x158 drawn over 320x160). Matching without this correction smears the peak.
    s = bg.shape[0] / float(piece.shape[0])
    if abs(s - 1.0) > 1e-3:
        tpl = cv2.resize(tpl, (max(1, int(round(w * s))), max(1, int(round(h * s)))),
                         interpolation=cv2.INTER_CUBIC)
        msk = cv2.resize(msk, (tpl.shape[1], tpl.shape[0]), interpolation=cv2.INTER_CUBIC)
    return _Prepared(bg=bg, tpl=tpl, mask=msk, x0=float(x0), y0=float(y0),
                     y0_bg=y0 * s, w=tpl.shape[1], h=tpl.shape[0])


def _psr(sub, peak_x, peak_y, guard=12):
    """Peak-to-sidelobe ratio: how far the winner stands out from the rest of the map.

    A raw correlation score says little on its own - 0.7 is excellent for ZNCC on a
    flat sky and mediocre on a textured one. PSR measures the peak in units of the
    map's own noise, which makes the three detectors' confidences comparable, and
    that comparability is what the vote runs on.
    """
    m = np.array(sub, dtype=np.float32, copy=True)
    m[~np.isfinite(m)] = np.nan
    peak = m[int(peak_y), int(peak_x)]
    x0, x1 = max(0, int(peak_x) - guard), min(m.shape[1], int(peak_x) + guard + 1)
    m[:, x0:x1] = np.nan                       # exclude the peak's own lobe
    vals = m[np.isfinite(m)]
    if vals.size < 32:
        return 0.0
    sd = float(vals.std())
    if sd < 1e-9:
        return 0.0
    return float((peak - vals.mean()) / sd)


def _conf(psr):
    """Squash a PSR into 0..1. ~3 is a weak peak, ~8+ is unambiguous."""
    return float(np.clip(1.0 - np.exp(-max(psr, 0.0) / 5.0), 0.0, 0.995))


def _best_in_band(res, y_center, x_min, band=5):
    """Argmax of a response map, constrained to the piece's own row band.

    The piece slides horizontally, so the gap's y is the piece's y. Searching a
    +/-band strip instead of the whole map is what makes single-shot accuracy
    possible: it throws away every false peak that is merely puzzle-*ish*.
    """
    lo = max(0, int(round(y_center)) - band)
    hi = min(res.shape[0], int(round(y_center)) + band + 1)
    if lo >= hi:
        lo, hi = 0, res.shape[0]
    sub = res[lo:hi, :].copy()
    x_min = max(0, int(round(x_min)))
    if x_min < sub.shape[1]:
        sub[:, :x_min] = -np.inf
    sub[~np.isfinite(sub)] = -np.inf
    idx = int(np.argmax(sub))
    yy, xx = divmod(idx, sub.shape[1])
    return float(xx), float(lo + yy), _conf(_psr(sub, xx, yy))


def _subpixel(res_row, x):
    """Parabolic fit around the peak - the gap rarely lands on an integer pixel."""
    x = int(x)
    if x <= 0 or x >= len(res_row) - 1:
        return float(x)
    a, b, c = float(res_row[x - 1]), float(res_row[x]), float(res_row[x + 1])
    d = a - 2 * b + c
    if abs(d) < 1e-9:
        return float(x)
    return x + 0.5 * (a - c) / d


# --------------------------------------------------------------------------------------
# Detector 1: contour-orientation matched filter
# --------------------------------------------------------------------------------------

def detect_contour(prep, band=5):
    """Correlate the silhouette's inward-normal field with the background gradient.

    Builds nx, ny = grad(smoothed alpha): a vector field that is zero except in a
    thin ring on the puzzle outline, where it points inward.  Correlating it with
    the image gradient asks whether an intensity step runs along that exact
    outline.  The response is normalised by the local gradient energy so that a
    busy region cannot win on sheer texture, and |.| is taken because a lighter
    overlay and a darker one give the same evidence with opposite signs.
    """
    bg, msk = prep.bg, prep.mask
    m = cv2.GaussianBlur((msk > 128).astype(np.float32), (0, 0), 1.2)
    nx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=3)
    ny = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=3)
    energy = float(np.sqrt((nx * nx + ny * ny).sum()))
    if energy < 1e-6:
        return None
    nx, ny = nx / energy, ny / energy

    g = cv2.GaussianBlur(cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY).astype(np.float32), (3, 3), 0)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)

    aligned = (cv2.matchTemplate(gx, nx, cv2.TM_CCORR) +
               cv2.matchTemplate(gy, ny, cv2.TM_CCORR))
    # local gradient energy under the same support, so flat and busy regions compare fairly
    support = np.ones_like(nx, dtype=np.float32) / float(nx.size)
    mag = cv2.matchTemplate(gx * gx + gy * gy, support, cv2.TM_CCORR)
    res = np.abs(aligned) / (np.sqrt(np.maximum(mag, 1e-6)) + 1e-6)
    res /= (np.abs(res).max() + 1e-9)

    x, y, s = _best_in_band(res, prep.y0_bg, prep.x0 + prep.w * 0.5, band)
    return Detection("contour", _subpixel(res[int(y)], x), y, float(s))


# --------------------------------------------------------------------------------------
# Detector 2: masked zero-mean normalised cross-correlation
# --------------------------------------------------------------------------------------

def _masked_zncc(img, tpl, mask):
    """ZNCC of `tpl` over `img` restricted to `mask`, built from TM_CCORR pieces.

    OpenCV's masked TM_CCOEFF_NORMED is documented as approximate and in practice
    returns values outside [-1, 1]; assembling it by hand is both correct and no
    slower.  Invariant to I = a*T + b with a > 0, which is what the captcha's
    translucent overlay does to the gap.
    """
    img = img.astype(np.float32)
    tpl = tpl.astype(np.float32)
    m = (mask > 128).astype(np.float32)
    n = float(m.sum())
    if n < 16:
        return None
    tc = (tpl - float((tpl * m).sum() / n)) * m       # zero-mean inside the mask, 0 outside
    tss = float((tc * tc).sum())
    if tss < 1e-6:
        return None
    num = cv2.matchTemplate(img, tc, cv2.TM_CCORR)
    s1 = cv2.matchTemplate(img, m, cv2.TM_CCORR)
    s2 = cv2.matchTemplate(img * img, m, cv2.TM_CCORR)
    var = np.maximum(s2 - (s1 * s1) / n, 1e-6)
    return num / np.sqrt(var * tss)


def detect_zncc(prep, band=5):
    g = cv2.cvtColor(prep.bg, cv2.COLOR_BGR2GRAY)
    t = cv2.cvtColor(prep.tpl, cv2.COLOR_BGR2GRAY)
    res = _masked_zncc(g, t, prep.mask)
    if res is None:
        return None
    x, y, s = _best_in_band(res, prep.y0_bg, prep.x0 + prep.w * 0.5, band)
    return Detection("zncc", _subpixel(res[int(y)], x), y, float(max(0.0, s)))


# --------------------------------------------------------------------------------------
# Detector 3: veil (saturation / luma drop inside the silhouette)
# --------------------------------------------------------------------------------------

def detect_veil(prep, band=5):
    """Shape-matched filter on saturation: a translucent overlay washes colour out."""
    inside = (prep.mask > 128).astype(np.uint8)
    ring = cv2.dilate(inside, np.ones((9, 9), np.uint8)) - inside
    if inside.sum() < 16 or ring.sum() < 16:
        return None
    k_in = inside.astype(np.float32) / float(inside.sum())
    k_out = ring.astype(np.float32) / float(ring.sum())

    hsv = cv2.cvtColor(prep.bg, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32)
    drop = (cv2.matchTemplate(sat, k_out, cv2.TM_CCORR) -
            cv2.matchTemplate(sat, k_in, cv2.TM_CCORR))
    # A grey veil also flattens local contrast; add that as a second, weaker term.
    g = cv2.cvtColor(prep.bg, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lvar = cv2.GaussianBlur(g * g, (0, 0), 2) - cv2.GaussianBlur(g, (0, 0), 2) ** 2
    flat = (cv2.matchTemplate(lvar, k_out, cv2.TM_CCORR) -
            cv2.matchTemplate(lvar, k_in, cv2.TM_CCORR))
    res = drop / (np.abs(drop).max() + 1e-6) + 0.5 * flat / (np.abs(flat).max() + 1e-6)
    res /= 1.5
    x, y, s = _best_in_band(res, prep.y0_bg, prep.x0 + prep.w * 0.5, band)
    return Detection("veil", _subpixel(res[int(y)], x), y, float(max(0.0, s)))


# --------------------------------------------------------------------------------------
# Voting
# --------------------------------------------------------------------------------------

# How much each detector's vote is worth. Measured against a corpus of live 网易易盾
# challenges (see README.md): `contour` was right on every one of them, including the
# flat-sky and fog backgrounds where `zncc` and `veil` both went far astray - and they
# go astray *together*, so raw agreement between the two cannot be allowed to outvote
# a confident contour lock.
_PRIOR = {"contour": 1.00, "zncc": 0.55, "veil": 0.35}
AGREE_PX = 6.0


def _vote(dets):
    """Cluster the detections by agreement and take the heaviest cluster.

    Weight is prior x confidence summed over the cluster, with a modest bonus for
    corroboration. Within the winning cluster the x's are averaged, weighted the
    same way, which buys back a fraction of a pixel of accuracy.
    """
    dets = [d for d in dets if d is not None]
    if not dets:
        raise ValueError("no detector produced a result")
    best_cluster, best_w = None, -1.0
    for d in dets:
        cluster = [o for o in dets if abs(o.x - d.x) <= AGREE_PX]
        w = sum(_PRIOR[o.method] * max(o.score, 0.05) for o in cluster) * (1.0 + 0.4 * (len(cluster) - 1))
        if w > best_w:
            best_cluster, best_w = cluster, w
    ws = [_PRIOR[o.method] * max(o.score, 0.05) for o in best_cluster]
    x = float(sum(o.x * w for o, w in zip(best_cluster, ws)) / sum(ws))
    y = float(sum(o.y * w for o, w in zip(best_cluster, ws)) / sum(ws))
    lead = max(best_cluster, key=lambda o: _PRIOR[o.method] * o.score)
    conf = min(0.99, lead.score * (1.0 + 0.25 * (len(best_cluster) - 1)))
    method = "+".join(sorted(o.method for o in best_cluster))
    return x, y, conf, method, dets


def locate_gap(background, piece, band=5):
    """Find the gap. `background` is BGR-ish, `piece` must carry an alpha channel.

    Both accept a path, raw bytes, or an ndarray.
    """
    bg = _imread(background, cv2.IMREAD_COLOR)
    pc = _imread(piece, cv2.IMREAD_UNCHANGED)
    prep = _prepare(bg, pc)
    dets = [detect_contour(prep, band), detect_zncc(prep, band), detect_veil(prep, band)]
    x, y, conf, method, dets = _vote(dets)
    return GapResult(x=x, y=y, confidence=conf, method=method,
                     piece_x=prep.x0, piece_y=prep.y0, piece_w=prep.w, piece_h=prep.h,
                     detections=dets)


def annotate(background, piece, result, path):
    """Write a debug overlay: every detector's box plus the chosen one."""
    bg = _imread(background, cv2.IMREAD_COLOR).copy()
    colours = {"contour": (0, 0, 255), "zncc": (0, 255, 0), "veil": (255, 128, 0)}
    for d in result.detections:
        c = colours.get(d.method, (200, 200, 200))
        cv2.rectangle(bg, (int(d.x), int(d.y)), (int(d.x + result.piece_w), int(d.y + result.piece_h)), c, 1)
        cv2.putText(bg, "%s %.0f" % (d.method[:4], d.x), (int(d.x) + 2, int(d.y) - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, c, 1)
    cv2.rectangle(bg, (int(result.x), int(result.y)),
                  (int(result.x + result.piece_w), int(result.y + result.piece_h)), (0, 255, 255), 2)
    cv2.imwrite(path, cv2.resize(bg, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("background")
    ap.add_argument("piece")
    ap.add_argument("--band", type=int, default=5,
                    help="vertical search half-height around the piece's own row (px)")
    ap.add_argument("--debug", metavar="PNG", help="write an annotated overlay here")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dx", nargs=2, type=float, metavar=("BG_SCALE", "PIECE_SCALE"),
                    help="also print the drag distance for these render scales")
    a = ap.parse_args(argv)

    r = locate_gap(a.background, a.piece, band=a.band)
    if a.debug:
        annotate(a.background, a.piece, r, a.debug)
    if a.json:
        out = r.to_dict()
        if a.dx:
            out["drag"] = r.drag_distance(*a.dx)
        print(json.dumps(out, indent=1))
    else:
        print("gap x=%.1f y=%.1f  confidence=%.2f  via %s" % (r.x, r.y, r.confidence, r.method))
        print("piece bbox (%.0f,%.0f) %dx%d" % (r.piece_x, r.piece_y, r.piece_w, r.piece_h))
        for d in r.detections:
            print("  %-8s x=%6.1f y=%5.1f score=%.3f" % (d.method, d.x, d.y, d.score))
        if a.dx:
            print("drag %.1f px" % r.drag_distance(*a.dx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
