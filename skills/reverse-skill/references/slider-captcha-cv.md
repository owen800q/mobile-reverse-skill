# Slider (jigsaw) captchas — computing the distance with computer vision

**When to load this.** A target gates registration, login, or a risk-triggered
re-verification behind a *drag the piece into the hole* captcha, and P2/P5 need to
get past it to reach the endpoint you are actually reversing. Common in Chinese
app/web stacks: 网易易盾 (NetEase Yidun), 极验 GeeTest, 顶象, 阿里滑块, and a long
tail of in-house clones.

Working implementation: [`tools/slider-cv/`](../../../tools/slider-cv/) —
`slider_cv.py` (detector, OpenCV only) and `slider_driver.py` (Playwright driver),
with the full derivation and measured accuracy in its `README.md`.

**Do not reach here first.** A slider is a *client-side* gate on a request you can
usually characterise without solving it at all. Check in this order:

1. Can the protected request be replayed with a token you already captured
   (ecapture, P2)? Then the captcha is not on your critical path — record the
   token as a Fact and move on.
2. Does the app expose the verify result as a single opaque `validate` string
   posted to your target endpoint? Then the *interesting* reverse is that string's
   server-side check, not the drag.
3. Only when you genuinely need to produce fresh sessions unattended — an archival
   crawler, a soak test against your own service — is solving the widget the right
   answer. Solving it does not recover an algorithm; it recovers *access*.

That ordering matters for the ledger too: a solved slider is evidence about the
**widget**, not about the app's signing scheme. It never justifies a rung above
`OBSERVED` for anything in `protocol_map`.

---

## 1. The problem, precisely

Two images come down the wire:

- **background** — the scene, with one puzzle-shaped region *veiled*: the same
  pixels under a translucent grey/white overlay plus a bevelled rim. It is not a
  hole, and there is no un-veiled copy to diff against.
- **piece** — an RGBA sprite, the puzzle shape cut from the scene, transparent
  elsewhere, overlaid on the background at `left: 0`.

You need one number: how far right the piece must travel.

**The single highest-value observation:** the piece only moves horizontally, so
the gap sits at *exactly* the piece's own vertical offset inside its sprite
canvas. Take the alpha channel's bounding box, and search only a ±5 px band at
that `y`. This collapses a 2-D template match to 1-D and removes most false
positives before you have chosen a detector at all.

---

## 2. What works, and what does not

| approach | verdict |
|-|-|
| Diff background against a clean background | Impossible — no clean copy is served. |
| `TM_CCORR_NORMED` of the piece texture | Weak. Not brightness-invariant, and the veil is exactly a brightness change. 6/13 on a live corpus. |
| Canny(bg) × Canny(silhouette) | Decent, and the usual published recipe. Noisy on busy scenes; sensitive to threshold choice. |
| **Gradient-orientation matched filter** | **Best.** 13/13. See below. |
| Masked ZNCC of the piece texture | Excellent on textured scenes, fails on flat sky/fog. Good refiner, bad primary. |
| Saturation/contrast drop inside the silhouette | Weak alone, uncorrelated with the others, useful tie-breaker. |
| Train a CNN / YOLO | Works, but it is a sledgehammer: needs labels, a runtime, and it silently rots when the widget restyles. Classical CV here is ~10 ms and explainable. |

### The gradient-orientation matched filter

Differentiate the piece's (blurred) alpha channel to get `(nx, ny)`: zero
everywhere except a thin ring on the puzzle outline, pointing inward. Correlate
that field with the background's gradient field:

```
response(x, y) = | Σ_p ∇I(x+p) · n(p) |    ÷ sqrt(local gradient energy)
```

It asks *does an intensity step run along this exact puzzle outline, all the way
round, here?* — and puzzle outlines with round tabs are rare enough in photographs
that the answer is decisive. It is texture-independent (keys on the rim, not the
scene), sign-agnostic via `| · |` (a lighter veil and a darker one are equally
good evidence), and two `TM_CCORR` passes cheap.

Normalising by the local gradient energy is not optional — without it, any busy
region outscores the real gap.

### Confidence you can compare

Raw correlation scores are not comparable across detectors or images. Score each
response map by **peak-to-sidelobe ratio** instead — the peak's height above the
map's mean in units of its standard deviation, excluding the peak's own lobe.
Then a vote across detectors is meaningful.

When you do vote, remember that failures are *correlated*: texture-based methods
all fail together on a flat background, and they agree with each other on the
wrong answer. Weight by prior × confidence, not by raw headcount.

---

## 3. Turning the gap into a drag

Three traps, all of which look like "the CV is wrong":

**Two render scales.** The sprites are rarely displayed at natural size and rarely
at the *same* scale as each other (a 60×158 piece drawn 60.75×160 over a 320×160
background is typical). Convert separately, in page coordinates:

```python
bg_scale    = bg.displayed_w    / bg.natural_w
piece_scale = piece.displayed_h / piece.natural_h
distance    = (bg.page_x + gap_x * bg_scale) - (piece.page_x + piece_x0 * piece_scale)
```

**The handle-to-piece transfer function is not 1:1.** Measured on 易盾: a ~10.5 px
dead zone, then 1:1, then saturation at `bgWidth − pieceWidth`. Other widgets scale
by `(bgWidth − pieceWidth) / (trackWidth − handleWidth)`. Do not model it — *close
the loop*: read the piece's rendered position mid-drag and correct until the
residual is sub-pixel. It survives the vendor changing the formula.

**The trace is scored.** Drag on an ease-out velocity profile with per-step jitter,
a small overshoot, two or three settling corrections, and a pause before release —
not a constant-speed interpolation.

**Read the verdict from the right node.** On 易盾 it is a modifier class on the
widget root (`.yidun--success` / `.yidun--error`), *not* the `.yidun_tips*`
elements, which exist empty from the start. A working solver that reads the wrong
node looks like a 0 % solver.

---

## 4. Recording it in the ledger

```bash
python scripts/findings.py add-fact \
  --rung OBSERVED \
  --claim "登录 is gated by a 网易易盾 jigsaw slider; solved offline by CV, 24/24 accepted" \
  --evidence "gap x=143.3 drag=140.3px conf=0.99 via contour+zncc; .yidun--success"
```

`OBSERVED`, not `VERIFIED`: you demonstrated that the widget accepts a drag you
computed. `VERIFIED` is reserved for recomputing an actual captured value from its
actual captured inputs, and the captcha's `validate` string is issued by the
vendor's server — you did not reproduce it, you obtained one.

---

## 5. Bounds

- This is a CV exercise against a widget you are authorised to exercise: your own
  account, your own service, or an engagement with scope covering it. Keep the
  request rate at human pace — one challenge at a time, in a real browser.
- It recovers **access**, not an algorithm. Nothing here belongs in a
  crypto-primitive Hypothesis.
- Vendors restyle. When the pass rate drops, dump the images and the annotated
  overlay first (`--captcha-debug-dir` in the crawler, `--debug` in the CLI); it is
  almost always the gap's *rendering* that changed, not the geometry.
