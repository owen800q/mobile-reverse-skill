# slider-cv

Solve a jigsaw ("slider") captcha with classical computer vision: find the gap,
work out how far the piece has to travel, drag it there.

Written for the 网易易盾 (NetEase Yidun) slider that kanxue's **安全验证**
interstitial serves, which is what used to stop
[`kb-crawl.yml`](../../.github/workflows/kb-crawl.yml) dead on a headless runner.
Nothing in the detector is site-specific — it takes a background image and an RGBA
piece sprite — and the browser side keeps its selectors in one `SliderProfile`.

```
slider_cv.py        the CV: background + piece -> gap x        (opencv + numpy only)
slider_driver.py    the Playwright side: measure, aim, drag, verify
```

---

## 1. What the widget actually is

Reading the DOM of a live challenge:

| element | natural | displayed | meaning |
|-|-|-|-|
| `.yidun_bg-img` | 320 × 160 | 320 × 160 | the scene, with the gap drawn into it |
| `.yidun_jigsaw` | 60 × 158 | 60.75 × 160 | the RGBA piece sprite, `left: 0` at rest |
| `.yidun_slider` | — | 40 × 38 | the handle you drag |
| `.yidun_control` | — | 320 × 40 | the track it runs in |

The piece sprite is 60 px wide but its opaque content is a ~55 × 55 puzzle shape
sitting at an offset inside that canvas — typically `x0 = 3`, with `y0` reshuffled
every challenge. **`y0` is the whole trick**: the piece only ever moves
horizontally, so the gap is at exactly that row. Constraining the search to a
±5 px band around it turns a 2-D template match into a 1-D one and deletes almost
every false positive.

Two more things the DOM tells you, both of which are easy to get wrong:

* **The two sprites are drawn at different scales.** The background is 1:1; the
  piece is a 158 px-tall image stretched to 160. So the gap's x and the piece's
  resting x have to be converted to CSS pixels *separately* before subtracting.
  Skipping this is a ~1.3 % error — about 0.7 px on a 55 px piece, and more on
  the offset.

* **Dragging the handle N px does not move the piece N px.** Measured on the live
  widget:

  ```
  drag (css px)   20    50   100   150   200   260   279   300
  jigsaw left     10  39.5  89.5 139.5 189.5   249 258.5   259
  ```

  A ~10.5 px dead zone, then 1:1, then saturation at `bgWidth - pieceWidth`
  (259.25). Other widgets instead scale by
  `(bgWidth - pieceWidth) / (trackWidth - handleWidth)`. The driver hard-codes
  none of it — see §4.

### What the gap looks like

The gap is not a hole. It is the same scene content under a translucent veil plus
a bevelled rim — sometimes lighter than its surroundings, sometimes darker:

```
   piece sprite            the gap in the background
   (scene content)         (same content, veiled)
        ▓▓▒▒                      ░░▒▒
      ▓▓▓▒▒▒▒▒        vs        ░░░▒▒▒▒▒
        ▓▓▒▒                      ░░▒▒
```

That is the single most useful fact about the problem. It rules out plain
`TM_CCORR_NORMED` on the piece texture (which is not brightness-invariant, and
which is what most published solvers reach for first — it was right on 6 of our 13
sample challenges), and it rules out "diff the two images" entirely, because
there is no un-veiled copy of the background to diff against.

---

## 2. Three detectors

`locate_gap()` runs all three and votes.

### `contour` — matched filter on gradient orientation

The primary detector, and the only one that was right on every challenge tested.

Take the piece's alpha channel, blur it slightly, and differentiate: that gives a
vector field `(nx, ny)` which is zero everywhere except a thin ring on the puzzle
outline, where it points inward. Correlate that field with the background's own
gradient field:

```
response(x, y) = | Σ_p ∇I(x+p) · n(p) |   normalised by the local gradient energy
```

This asks a very specific question — *does an intensity step run along this exact
puzzle outline, all the way round, right here?* — and the round tabs make the
answer highly selective. Three properties matter:

* **Texture-independent.** It keys on the rim, not the scene, so flat sky and
  dense foliage behave the same.
* **Sign-agnostic.** A light veil and a dark veil give the same evidence with
  opposite signs, so the absolute value covers both.
* **Cheap.** Two `TM_CCORR` passes over a 320 × 160 image.

Normalising by `sqrt(Σ(Gx²+Gy²))` under the same support is what stops a busy
region winning on sheer texture.

### `zncc` — masked zero-mean normalised cross-correlation

Matches the piece's *texture* against the background, restricted to the alpha
mask. Because the veil is an affine brightness change (`I = a·S + b`, `a > 0`),
ZNCC is invariant to it — so on a textured scene it locks on hard and refines the
answer to a fraction of a pixel.

OpenCV's own masked `TM_CCOEFF_NORMED` is documented as approximate and in
practice returns values outside [-1, 1], so `_masked_zncc()` assembles it from
`TM_CCORR` accumulations instead:

```
num = Σ (I · Tc)                     Tc = (T - mean_M(T)) · M
var = Σ I²·M - (Σ I·M)² / n
zncc = num / sqrt(var · Σ Tc²)
```

Its weakness is structural: on a flat sky or fog the template carries almost no
variance and the peak is noise. That is exactly where it disagrees with
`contour` — and it is wrong every time it does.

### `veil` — saturation and contrast drop

The overlay washes colour out, so mean saturation inside the silhouette drops
relative to a ring around it; local variance drops too. A shape-matched
difference-of-kernels on those two channels. Weakest of the three on its own
(it has no idea what a puzzle piece is beyond its area), but cheap, uncorrelated
with the others, and a good sub-pixel tie-breaker.

### Voting

Each detector's raw score is useless for comparison — 0.7 is superb for ZNCC on
one image and mediocre on another — so every response map is scored by
**peak-to-sidelobe ratio** instead: the peak's height above the map's own mean,
in units of its standard deviation, with the peak's lobe excluded. That makes
the three confidences commensurable. Detections are then clustered by agreement
(≤ 6 px), each cluster weighted by `Σ prior × confidence` with a bonus for
corroboration, and the heaviest cluster's members averaged.

The priors (`contour` 1.0, `zncc` 0.55, `veil` 0.35) encode the measured failure
mode: `zncc` and `veil` do not fail independently — a flat background defeats
both, and they agree *with each other* on the wrong answer. Weighting purely by
agreement would let those two outvote a confident `contour` lock, which is
precisely backwards.

Agreement is then read at **two scales**, because it answers two different
questions. `AGREE_PX` (6 px) decides cluster membership — *did these detectors find
the same gap?* — and a peer 5 px away plainly did. `REFINE_PX` (2 px) decides which
cluster members may move the reported number. A loosely-agreeing peer corroborates
the *identification* while being no authority on the *position*, and averaging it in
drags the answer off the better detector: measured against the rim oracle below,
using one window for both cost up to 0.9 px on exactly the challenges where `zncc`
sat 4–5 px out.

---

## 3. Measured accuracy

**Offline, 29 distinct live challenges** harvested from the widget and deduplicated
by hash. Every pick was checked against an annotated overlay, and every case where
the detectors disagreed was resolved by cropping the background at each candidate
and comparing it to the piece:

| detector | correct | notes |
|-|-|-|
| `contour` | 29 / 29 | |
| `zncc` | 24 / 29 | the 5 misses are flat sky, fog and haze |
| `veil` | 21 / 29 | |
| naive `TM_CCORR_NORMED` on the piece texture | 18 / 29 | the common published approach |
| **vote** | **29 / 29** | follows `contour` every time; agreeing detectors refine it to ≤ 0.9 px |

**Sub-pixel accuracy.** "Correct" above means the right gap; this asks how well it
is centred. An independent measurement — align the piece's silhouette *boundary*
(centred on the alpha transition, not a dilated ring) to the background's gradient
magnitude, upsampled 4× and searched in 2-D at 0.25 px — puts the reported answer at:

```
dx: mean +0.06  median 0.00  sd 0.35  max|Δ| 1.00   (29 challenges)
dy: mean +0.14  median 0.00  sd 0.30  max|Δ| 0.75
```

So the answer is within one pixel of the finest available rim alignment on every
challenge, with no systematic offset. Two weaker oracles — an interior-texture
affine fit (`bg = a·piece + b` over the eroded mask) and a leftover-veil test —
lean about +0.5…+0.9 px, but both are confounded (the affine model explains only
15–65 % of the interior variance; the leftover ring is contaminated by the gap's
own outward bevel) and neither is precise enough to establish a bias that the rim
measurement does not see.

**End-to-end against the live widget** — CV, drag, and 易盾's own verdict:

```
python slider_driver.py --url https://bbs.kanxue.com/thread-285762.htm --rounds 24 --fresh
```

40/40 accepted across two runs (16 + 24), one attempt each, residual at release
|Δ| ≤ 0.6 px. **That number proves the plumbing, not the precision.** Deliberately
dragging to *gap + δ* and recording 易盾's verdict (54 + 60 trials) maps its
acceptance window:

```
δ  -14 -12 -11 -10  -9  -8  -6  -4  -2   0  +2  +4  +6  +8  +9 +10 +11 +12 +14
    ✗   ✗   ✗   ✗   ✗  1/6 ✓   ✓   ✓   ✓   ✓   ✓   ✓   ✓   ✗   ✗   ✗   ✗   ✗
```

The widget accepts roughly **±8 px**, so it would have accepted an answer eight
pixels wrong — a live pass rate simply cannot distinguish a good locator from a
mediocre one. Use the offline numbers for accuracy and the live numbers for the
drag, the transfer function and the verdict plumbing. (The window is very slightly
right-of-centre on our answer, but the δ = ±9…14 run was served the same cached
challenge throughout, so it measures one gap's tolerance, not a population's.)

Read the live figures with one more caveat: kanxue serves an anonymous client from
a small pool, so the 24-round run saw only **12 distinct** challenge images even
with `--fresh` clicking refresh every round — the bench prints the distinct count
for exactly this reason.

**A rejected idea, recorded so it is not retried.** A "does the piece fill the
hole?" arbiter — composite the piece at each detector's candidate and pick the one
leaving least contrast in a ring outside the silhouette — sounds like the ideal
tie-breaker, since it asks the captcha's own question. It is not: the ring
unavoidably contains the gap's outward bevel, its optimum is shallow (15–40 %
depth), and as a re-ranker it *disagreed with the correct answer on 4 of 29* real
challenges and turned 5 synthetic gross errors into 12. Measured, discarded.

**Synthetic regression test** — `test_slider_cv.py` renders challenges with known
ground truth (light and dark veils, flat gradients, heavy texture, sub-pixel
offsets, both render scales) and asserts the answer lands within 2 px. No network,
no third-party images, runs in a couple of seconds:

```bash
python test_slider_cv.py
```

---

## 4. Getting the piece there

Three things beyond the CV:

1. **Convert with both scales.**

   ```python
   bg_scale    = bg.displayed_w    / bg.natural_w
   piece_scale = piece.displayed_h / piece.natural_h
   distance    = (bg.page_x + gap_x * bg_scale) - (piece.page_x + piece_x0 * piece_scale)
   ```

   Page coordinates throughout, because the two `<img>` elements need not share an
   origin.

2. **Close the loop.** Rather than model the dead zone, the 1:1 stretch and the
   saturation above, the driver reads the piece's *rendered* position mid-drag and
   corrects toward the target, up to three times, until the residual is under
   0.6 px. If a correction produces no movement it nudges harder once (dead zone
   or saturation) and then stops chasing. The transfer function can change without
   breaking anything.

3. **Drag like a hand.** These widgets score the trace. `human_track()` generates
   an ease-out cubic velocity profile (fast rise, smooth decay), jitters every
   step by ±14 % with ±0.6 px of vertical wander, overshoots by a few pixels,
   settles back in two or three corrections, and pauses before release. Step count
   scales with distance; timings are randomised per step.

The verdict is a modifier class on the widget root — `.yidun--success` /
`.yidun--error` — *not* one of the `.yidun_tips*` nodes, which exist empty from
the start and never carry it. Getting this wrong makes a working solver look
like it fails 100 % of the time.

---

## 5. Use

```bash
pip install -r requirements.txt

# offline: two images in, gap out
python slider_cv.py bg.jpg piece.png
python slider_cv.py bg.jpg piece.png --debug overlay.png   # every detector's box
python slider_cv.py bg.jpg piece.png --json --dx 1.0 1.0127

# live: bench against a real widget
python slider_driver.py --url https://... --rounds 20 --fresh
```

In a Playwright script:

```python
from slider_driver import solve_with_retries, YIDUN

report = solve_with_retries(page, YIDUN, attempts=4)
if report.ok:
    ...  # report.distance, report.gap_x, report.confidence, report.method
```

Porting to another widget means one `SliderProfile` — the selectors for the
background, the piece, the handle, and the success/failure markers.

### Where it is wired in

`tools/kanxue-crawler/crawl.py` calls it from `goto()` whenever a page comes back
as 安全验证. Headed runs still fall back to waiting for a human if the solver comes
up short; headless runs (i.e. CI) record `CaptchaRequired` in `failed.json` as
before. `--no-auto-captcha` turns it off, `--captcha-debug-dir DIR` keeps every
attempt's images plus an annotated overlay — and `kb-crawl.yml`'s `captcha_debug`
input uploads that directory as an artifact.

---

## Scope

Written to keep one archival crawler running against a forum the operator has an
account on, at its existing polite crawl rate and under its `robots.txt` check.
It is a CV exercise on a public widget, not a bypass service: no token forging, no
API replay, no traffic amplification — the widget is solved the way a person
solves it, one challenge at a time in a real browser. Use it where you are
authorised to.
