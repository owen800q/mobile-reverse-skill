# kanxue crawler

Archives the threads of the 看雪 [Android安全 board](https://bbs.kanxue.com/forum-161-1.htm?orderby=tid&digest=0)
as markdown and syncs them into `skills/reverse-skill/kb/articles/`, which is the
corpus the reverse-skill KB search runs over.

## Layout

| path | tracked | what it is |
|-|-|-|
| `crawl.py` | yes | the crawler (Playwright + Chromium) |
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

`update.sh` finds the KB via `git rev-parse --show-toplevel`, so it works from this
checkout without configuration. Override with `KB_REPO=...` if you need to.

Every stage is keyed on thread id, so reruns are cheap and Ctrl-C is safe — state is
written after each thread.

## CI

`.github/workflows/kb-crawl.yml` runs `update.sh --headless --no-push` daily at
03:17 UTC (and on demand). It commits new articles plus the refreshed crawl state,
pushes, and then dispatches `kb-index.yml` to rebuild `INDEX.md` and
`embeddings.npy` — but only when `kb/articles/**` actually changed.

### The session secret

CI authenticates with the `KANXUE_SESSION_STATE` repo secret: the verbatim contents
of your local `.session-state.json`.

```bash
gh secret set KANXUE_SESSION_STATE < .session-state.json
```

Cookies rotate on every crawl and the workflow cannot write the refreshed ones back
into the secret, so it goes stale eventually. When the job reports a dead session or
a run lands threads in `failed.json` with `CaptchaRequired`, fix it locally:

```bash
python crawl.py login       # visible window, clear any 安全验证 captcha
./update.sh                 # picks up where CI stopped
gh secret set KANXUE_SESSION_STATE < .session-state.json
```

A 安全验证 captcha **cannot** be cleared headless — that is a hard limit of running
this on a runner, not a bug in the workflow.

### 点赞 on gated threads

Some threads hide their body behind 回复或点赞. `update.sh` clears those by liking
them, which is a real write to the forum under your account. The daily run does this
by default; a manual run can pass `unlock: false` to leave them in `locked.json`
instead.
