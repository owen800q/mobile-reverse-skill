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
| `output/attachments/` | no | scratch copy of downloaded attachments; `kb/attachments/` is canonical |
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

### Crawling one named thread

The board scan keeps only threads with more than 10 replies that are newer than the
cutoff. That filter is a corpus-quality rule for *discovering* what to archive, so it
does not apply to a thread you name yourself — handy for testing a change against a
known thread, or for pulling in one specific writeup the filter would drop.

```bash
python crawl.py thread https://bbs.kanxue.com/thread-292554.htm   # URL, or a bare tid
python crawl.py thread 292554 291584 --no-like                    # several, never 点赞
./update.sh --thread 292554                                       # crawl + sync to the KB
./update.sh --thread 292554 --dry-run                             # crawl, change nothing
python test_manual_thread.py                                      # the rules, no browser
```

This path **never writes `output/*.json`**. That state is the daily pipeline's resume
log, and a manual run marking a thread "done" — possibly one whose article a `--dry-run`
then discards — would make the next scheduled crawl skip work it never actually did. So
a manual fetch always re-fetches, even a tid already archived, and records nothing. A
gated thread is 点赞-opened inline (`--no-like` to leave it alone) rather than going
through the bulk `unlock` pass.

## CI

`.github/workflows/kb-crawl.yml` runs `update.sh --headless --no-push` daily at
03:17 UTC (and on demand). It commits new articles plus the refreshed crawl state,
pushes, and then dispatches `kb-index.yml` to rebuild `INDEX.md` and
`embeddings.npy` — but only when `kb/articles/**` actually changed.

Two `workflow_dispatch` inputs make it a manual test harness:

| input | effect |
|-|-|
| `thread_url` | crawl only this thread (URL or tid; space-separate several) instead of scanning the board — no reply-count or date filter, and the crawl state is left untouched |
| `dry_run` | crawl but write nothing: no KB copy, no commit, no push |

Run it with `thread_url` alone to add one specific thread to the KB, or with `dry_run`
as well to exercise the crawler end to end — captcha, login, extraction, attachments —
and read the result off the job log without touching the repo.

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

### Attachments

Posts often ship an uploaded file — a sample, a PoC, an unpacked-dex dump, an AI
reverse-engineering trace. kanxue renders it as an 上传的附件 box whose download link
(`attach-download-{aid}-{token}.htm`) is obfuscated with the same `_XX` scheme as its
outbound links. `fetch`/`unlock` decode that link, pull the file through the crawl's
own logged-in browser context, and save it to `output/attachments/{tid}/`; `update.sh`
syncs those into `skills/reverse-skill/kb/attachments/{tid}/` next to the articles.

Each article's frontmatter gains an `attachments:` list (filename, aid, size, source
URL, local `path`, and whether the file was `downloaded`), and its body carries a
`## 附件` section linking the local copies, so the KB corpus keeps both the writeup and
its files together.

```bash
./update.sh                          # downloads attachments as part of the fetch
./update.sh --no-attachments         # list them in the frontmatter, download nothing
./update.sh --max-attachment-mb 100  # raise the size cap (default 25 MB)
python test_attachments.py           # parsing + link plumbing, no browser or network
```

A download needs the same logged-in session as the crawl — an unauthorised request
comes back as kanxue's gate HTML, which the crawler detects and skips rather than
saving. Files larger than `--max-attachment-mb` (default 25) are recorded in the
frontmatter with their source URL but not downloaded, so a stray multi-hundred-MB APK
never bloats the git history. An attachment-only change does not trigger the index
rebuild — attachments are not part of the search corpus.

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
