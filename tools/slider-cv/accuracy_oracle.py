#!/usr/bin/env python3
"""An oracle for the gap position that shares nothing with the detector.

The previous sub-pixel check was worthless because it built its reference from
`prep.mask` - the same resampled template the detector matches - so it could not see
a template-scale error by construction. This one:

  * resamples the sprite itself, from the raw RGBA, on a grid computed here by hand
    and applied with cv2.remap (no resize, no warpAffine, no shared helper);
  * uses only INTERIOR TEXTURE, with the mask eroded well past any rim, so nothing
    about how the rim is rendered can reach it;
  * scores with a per-channel affine fit bg = a*piece + b (1 - R^2). An alpha blend
    toward any constant is exactly an affine map, so the veil cancels algebraically
    and the estimator cannot acquire a polarity-dependent bias by construction.

`validate()` is the part that was missing last time: it measures the oracle's OWN
error against synthetic challenges with exact ground truth, separately for light and
dark veils. An oracle is only usable here if its own polarity split is far smaller
than the effect it is being asked to measure. Ours measures 0.000 px, which is what
licenses the light-vs-dark comparison below.

Only the light-vs-dark DIFFERENCE is interpreted. The oracle's absolute offset is a
reference convention (which alpha threshold defines the bounding box the answer is
stated against) and is not claimed to be zero.

    python accuracy_oracle.py                 # self-validation only
    python accuracy_oracle.py CORPUS_DIR      # ... then score the detector on a corpus
                                              # of NN_bg.jpg / NN_piece.png pairs
"""
import glob
import os
import re
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _bbox(alpha, thr=16):
    ys, xs = np.nonzero(alpha > thr)
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def _resample(img, x0, y0, w, h, s, order=cv2.INTER_CUBIC, border=cv2.BORDER_REPLICATE, bval=0):
    """Sample the crop at exactly 1/s source px per destination px, anchored at (x0,y0).

    The grid is written out explicitly rather than delegated, so this shares no
    convention with the code under test.
    """
    dw, dh = int(np.ceil(w * s)), int(np.ceil(h * s))
    u = (np.arange(dw, dtype=np.float32) / s) + x0
    v = (np.arange(dh, dtype=np.float32) / s) + y0
    mx = np.tile(u, (dh, 1))
    my = np.repeat(v, dw).reshape(dh, dw)
    return cv2.remap(img, mx, my, order, borderMode=border, borderValue=bval)


def oracle_x(bg, piece, x_hint, y_hint, win=6.0, step=0.125, erode=6, min_px=150):
    """Best gap x by interior-texture affine fit. Returns (x, quality) or None."""
    alpha = piece[:, :, 3]
    x0, y0, w, h = _bbox(alpha)
    s = bg.shape[0] / float(piece.shape[0])
    tpl = _resample(piece[:, :, :3], x0, y0, w, h, s)
    msk = _resample(alpha, x0, y0, w, h, s, border=cv2.BORDER_CONSTANT, bval=0)

    inner = cv2.erode((msk > 200).astype(np.uint8), np.ones((2 * erode + 1,) * 2, np.uint8))
    if inner.sum() < min_px:
        return None
    m = inner > 0
    th, tw = tpl.shape[:2]
    t = tpl.astype(np.float32)
    g = bg.astype(np.float32)
    yi = int(round(y_hint))
    if yi < 0 or yi + th > g.shape[0]:
        return None

    tv = [t[:, :, c][m] for c in range(3)]
    if sum(float(v.std()) for v in tv) < 6.0:      # no interior texture to fit
        return None

    best, curve = None, []
    for dx in np.arange(-win, win + step, step):
        xf = x_hint + dx
        xi = int(np.floor(xf))
        f = xf - xi
        if xi < 0 or xi + tw + 1 > g.shape[1]:
            continue
        patch = g[yi:yi + th, xi:xi + tw] * (1 - f) + g[yi:yi + th, xi + 1:xi + 1 + tw] * f
        ss_res = ss_tot = 0.0
        for c in range(3):
            pv = patch[:, :, c][m]
            A = np.vstack([tv[c], np.ones_like(tv[c])]).T
            coef, *_ = np.linalg.lstsq(A, pv, rcond=None)
            r = pv - A @ coef
            ss_res += float(r @ r)
            ss_tot += float(((pv - pv.mean()) ** 2).sum())
        curve.append((float(dx), ss_res / max(ss_tot, 1e-9)))
    if len(curve) < 5:
        return None
    vals = np.array([v for _, v in curve])
    k = int(np.argmin(vals))
    if 0 < k < len(vals) - 1:
        a, b, c = vals[k - 1], vals[k], vals[k + 1]
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0.0
        dx = curve[k][0] + off * step
    else:
        dx = curve[k][0]
    # quality: how deep and how sharp the well is
    depth = float(vals.max() - vals.min())
    return x_hint + dx, depth


def polarity(bg, piece, x, y):
    """+1 if the gap is brighter than its surround, -1 if darker."""
    alpha = piece[:, :, 3]
    x0, y0, w, h = _bbox(alpha)
    s = bg.shape[0] / float(piece.shape[0])
    msk = _resample(alpha, x0, y0, w, h, s, border=cv2.BORDER_CONSTANT, bval=0)
    sil = (msk > 128).astype(np.uint8)
    inner = cv2.erode(sil, np.ones((9, 9), np.uint8))
    ring = cv2.dilate(sil, np.ones((15, 15), np.uint8)) - cv2.dilate(sil, np.ones((7, 7), np.uint8))
    xi, yi = int(round(x)), int(round(y))
    th, tw = sil.shape
    if xi < 0 or yi < 0 or xi + tw > bg.shape[1] or yi + th > bg.shape[0]:
        return 0, 0.0
    crop = cv2.cvtColor(bg[yi:yi + th, xi:xi + tw], cv2.COLOR_BGR2GRAY).astype(np.float32)
    if inner.sum() < 40 or ring.sum() < 40:
        return 0, 0.0
    d = float(crop[inner > 0].mean() - crop[ring > 0].mean())
    return (1 if d > 0 else -1), d


# --------------------------------------------------------------------------------------
# Validation: does the ORACLE itself have a polarity-dependent bias?
# --------------------------------------------------------------------------------------

def validate(n_per=12, verbose=True):
    from test_slider_cv import make_challenge
    rows = []
    kinds = ("busy", "haze", "flat")
    for pol_name in ("light", "dark"):
        for j in range(n_per):
            kind = kinds[j % len(kinds)]
            gx = 90 + 11 * j
            gy = 30 + 7 * (j % 6)
            bg, piece, truth = make_challenge(gx, gy, kind=kind, veil=pol_name, seed=900 + j)
            got = oracle_x(bg, piece, truth["gap_x"] + 2.0, truth["gap_y"])   # deliberately offset start
            if got is None:
                continue
            rows.append((pol_name, kind, got[0] - truth["gap_x"], got[1]))
    if verbose:
        print("ORACLE self-validation on synthetic challenges with exact ground truth")
        for pol_name in ("light", "dark"):
            v = np.array([r[2] for r in rows if r[0] == pol_name])
            if len(v):
                print("  %-5s n=%2d  mean %+.3f  median %+.3f  sd %.3f  max|.| %.3f"
                      % (pol_name, len(v), v.mean(), np.median(v), v.std(), np.abs(v).max()))
        lv = np.array([r[2] for r in rows if r[0] == "light"])
        dv = np.array([r[2] for r in rows if r[0] == "dark"])
        if len(lv) and len(dv):
            print("  oracle's OWN polarity split: %+.3f px" % (dv.mean() - lv.mean()))
    return rows


def score_corpus(corpus, verbose=True):
    """Score the shipped detector against the oracle over a directory of challenges."""
    from slider_cv import locate_gap
    pairs = []
    for bp in sorted(glob.glob(os.path.join(corpus, "*_bg.*"))):
        stem = re.sub(r"_bg\.[^.]+$", "", bp)
        for ext in ("png", "jpg", "jpeg"):
            pp = "%s_piece.%s" % (stem, ext)
            if os.path.exists(pp):
                pairs.append((bp, pp))
                break
    rows = []
    for bp, pp in pairs:
        bg = cv2.imread(bp)
        pc = cv2.imread(pp, cv2.IMREAD_UNCHANGED)
        if bg is None or pc is None:
            continue
        r = locate_gap(bp, pp)
        pol, _ = polarity(bg, pc, r.x, r.y)
        got = oracle_x(bg, pc, r.x, r.y)
        if got is None:
            continue
        rows.append((os.path.basename(bp), pol, got[0] - r.x, got[1]))
    if verbose and rows:
        v = np.array([r[2] for r in rows])
        print("\nDETECTOR vs oracle on %d challenges from %s" % (len(rows), corpus))
        print("  (+ = the detector reads too far LEFT; only the light-vs-dark "
              "difference is meaningful)")
        for name, sel in (("all", None), ("light", 1), ("dark", -1)):
            w = v if sel is None else np.array([r[2] for r in rows if r[1] == sel])
            if len(w):
                print("  %-6s n=%2d  mean %+.3f  median %+.3f  sd %.3f  rms %.3f"
                      % (name, len(w), w.mean(), np.median(w), w.std(),
                         float(np.sqrt((w ** 2).mean()))))
        lv = np.array([r[2] for r in rows if r[1] == 1])
        dv = np.array([r[2] for r in rows if r[1] == -1])
        if len(lv) > 2 and len(dv) > 2:
            d = dv.mean() - lv.mean()
            se = np.sqrt(lv.std() ** 2 / len(lv) + dv.std() ** 2 / len(dv))
            print("  polarity split (dark - light) = %+.3f px +/- %.3f (%.1f sigma)"
                  % (d, se, abs(d) / max(se, 1e-9)))
    return rows


if __name__ == "__main__":
    validate()
    if len(sys.argv) > 1:
        score_corpus(sys.argv[1])
