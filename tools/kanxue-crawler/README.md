# kanxue crawler

Archives the threads with more than 10 replies (a quality filter) of the 看雪
[Android安全 board](https://bbs.kanxue.com/forum-161-1.htm?orderby=tid&digest=0)
as markdown and syncs them into `skills/reverse-skill/kb/articles/`, which is the
corpus the reverse-skill KB search runs over.

## Layout

| path | tracked | what it is |
|-|-|-|
| `crawl.py` | yes | the crawler (Playwright driving CloakBrowser; clears 安全验证 via [`../slider-cv`](../slider-cv/)) |
| `update.sh` | yes | the full pipeline: scan → fetch → unlock → sync → commit |
| `output/*.json` | yes | resume state, keyed by thread id — this is what stops the daily job re-fetching 635 threads |
| `output/articles/` | no | scratch copy of the markdown; `kb/articles/` is canonical |
| `.session-state.json` | **no** | a logged-in cookie jar. Secret. |
| `.browser-profile/` | no | Chromium profile |

## Local use

```bash
pip install -r requirements.txt && python -m playwright install chromium
python crawl.py login      # once, in a visible window
./update.sh                # scan, fetch, sync to the KB, commit, push
./update.sh --dry-run      # crawl but report instead of writing to the KB
```

That installs Playwright's own Chromium, which is what a local run uses unless you
point `CRAWLER_BROWSER_EXECUTABLE` at the patched CloakBrowser launcher — see
[Which browser actually ran](#which-browser-actually-ran) below. CI always uses
CloakBrowser.

`update.sh` finds the KB via `git rev-parse --show-toplevel`, so it works from this
checkout without configuration. Override with `KB_REPO=...` if you need to.

Every stage is keyed on thread id, so reruns are cheap and Ctrl-C is safe — state is
written after each thread.

## CI

`.github/workflows/kb-crawl.yml` runs `update.sh --headless --no-push` daily at
03:17 UTC (and on demand). It commits new articles plus the refreshed crawl state,
pushes, and then dispatches `kb-index.yml` to rebuild `INDEX.md` and
`embeddings.npy` — but only when `kb/articles/**` actually changed.

The CI crawl runs inside the image defined by
`tools/cloakbrowser-ci/Dockerfile`. Playwright receives the patched browser
launcher through `CRAWLER_BROWSER_EXECUTABLE`; the browser binary is downloaded,
verified, patched in memory, launched, and smoke-tested in Docker. See
`tools/cloakbrowser-ci/README.md` for the pinned build and local commands.

### Which browser actually ran

Playwright here is only the driver — a CDP client. The browser is CloakBrowser
whenever `CRAWLER_BROWSER_EXECUTABLE` points at the patched launcher, and
Playwright's own Chromium otherwise. Because that is the whole difference between
a cloaked crawl and a plainly-automated one, every run now prints it:

```
browser  : CloakBrowser via /opt/cloakbrowser-ci/launch_cloakbrowser.sh
user-agent: Mozilla/5.0 (X11; Linux x86_64) ... Chrome/150.0.0.0 Safari/537.36
```

Set `CRAWLER_REQUIRE_CLOAK=1` to turn the stock-Chromium fallback into a hard
error; the container's `crawl` entrypoint sets it for you.

Under CloakBrowser the crawler no longer forces a `user_agent` or passes
`--disable-blink-features=AutomationControlled`. Those were stock-Chromium
workarounds, and against a browser that spoofs natively they were actively
harmful: Playwright's UA override does not carry through to everything the page
can read, so the old macOS/Chrome-130 string left `userAgentData.brands` reporting
Chromium 141 and `navigator.platform` reporting `Linux x86_64` — a self-contradicting
browser is easier to spot than an un-spoofed one. Reproduce it with
`verify_stealth.py --user-agent '<the old string>'`. The stock-Chromium fallback
path keeps both settings, where they still help.

### The 安全验证 slider

kanxue guards some threads with a 网易易盾 jigsaw slider. It used to be the hard stop
for the daily job — nobody is watching a runner to drag it — so
[`tools/slider-cv`](../slider-cv/) now clears it: OpenCV locates the gap
(gradient-orientation matched filter, masked ZNCC and a veil detector, voting), and
the driver drags the handle with a closed loop on the piece's measured position.
24/24 accepted on the live widget, one attempt each.

The crawler calls it from `goto()` whenever a page comes back as 安全验证:

```bash
./update.sh --headless                                   # solved automatically
./update.sh --no-auto-captcha                            # off; headed runs wait for you
./update.sh --captcha-debug-dir output/captcha-debug     # keep what the solver saw
```

A headed run still falls back to pausing for you if the solver comes up short. The
workflow's `captcha_debug` input turns on the dump and uploads it as an artifact —
that is the first thing to look at if the pass rate ever drops, since it is almost
always the gap's *rendering* that changed.

**A 安全验证 failure is no longer permanent.** `fetch` skips everything already in
`failed.json`, so before the solver existed a thread that hit the interstitial was
stranded there for good — nothing ever revisited it. Those entries are now *stale*
rather than dead, so a run re-attempts them by default, bounded by an attempt count
(`--captcha-retry-max`, default 3) so a broken solver cannot make every daily run
re-walk the same threads. Every other failure kind keeps the old behaviour and waits
for an explicit `--retry-failed`.

```bash
./update.sh                          # retries stale 安全验证 failures, up to 3 times each
./update.sh --captcha-retry-max 0    # off: treat them as permanent again
./update.sh --retry-failed           # force everything in failed.json, any reason, no cap
python test_retry_policy.py          # the selection rules, no browser or network
```

### The session secret

CI authenticates with the `KANXUE_SESSION_STATE` repo secret: the verbatim contents
of your local `.session-state.json`.

```bash
gh secret set KANXUE_SESSION_STATE < .session-state.json
```

Cookies rotate on every crawl and the workflow cannot write the refreshed ones back
into the secret, so it goes stale eventually. When the job reports a dead session,
fix it locally:

```bash
python crawl.py login       # visible window, sign in
./update.sh                 # picks up where CI stopped
gh secret set KANXUE_SESSION_STATE < .session-state.json
```

### 点赞 on gated threads

Some threads hide their body behind 回复或点赞. `update.sh` clears those by liking
them, which is a real write to the forum under your account. The daily run does this
by default; a manual run can pass `unlock: false` to leave them in `locked.json`
instead.
