#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`crawl.py thread <url|tid>` - the manual, board-scan-free path.

Two properties matter and neither is obvious from reading cmd_thread alone:

  * it fetches what you named, with no reply-count or date filter and regardless of
    done.json - that is the whole point of a manual test run;
  * it leaves output/*.json alone.  That state is the daily pipeline's resume log, so a
    manual run marking a thread "done" - possibly one whose article a --dry-run then
    throws away - would make the next scheduled crawl skip real work.

Runs without a browser or network: Browser/goto/fetch_thread are stubbed, which is
everything cmd_thread touches outside its own bookkeeping.

    python test_manual_thread.py
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crawl  # noqa: E402


class _Args(object):
    def __init__(self, **kw):
        self.targets = ["292554"]
        self.headless = True
        self.no_replies = False
        self.no_like = False
        self.max_reply_pages = 0
        self.__dict__.update(kw)


class _FakePage(object):
    context = None


class _FakeBrowser(object):
    def __init__(self, *a, **kw):
        self.page = _FakePage()
        self.ctx = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


ARTICLE = ({"title": "测试帖", "date": "2026-01-01", "replies": 3}, "正文", [])


def _run(args, fetch_result=(ARTICLE, None), state=None):
    """Drive cmd_thread with everything external stubbed.  -> (rc, stdout)."""
    calls = []

    def fake_fetch_thread(page, meta, **kw):
        calls.append(meta["tid"])
        return fetch_result

    saved = {k: getattr(crawl, k) for k in
             ("Browser", "goto", "is_logged_in", "save_session", "fetch_thread",
              "save_article", "like_thread", "nap")}
    crawl.Browser = _FakeBrowser
    crawl.goto = lambda *a, **kw: None
    crawl.is_logged_in = lambda *a, **kw: True
    crawl.save_session = lambda *a, **kw: None
    crawl.nap = lambda *a, **kw: None
    crawl.fetch_thread = fake_fetch_thread
    crawl.like_thread = lambda page: True
    crawl.save_article = lambda page, tid, fm, body, atts: os.path.join(
        crawl.ARTICLES_DIR, "%s.md" % tid)

    for name, value in (state or {}).items():
        crawl.save_json(getattr(crawl, name), value)

    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            rc = crawl.cmd_thread(args)
    finally:
        for k, v in saved.items():
            setattr(crawl, k, v)
    return rc, buf.getvalue(), calls


def _state_files():
    return sorted(f for f in os.listdir(crawl.OUT_DIR) if f.endswith(".json"))


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("a named thread is fetched")
def _():
    rc, out, calls = _run(_Args())
    return rc == 0 and calls == [292554], "rc=%s calls=%s" % (rc, calls)


@case("a thread already in done.json is fetched again")
def _():
    rc, out, calls = _run(_Args(), state={"DONE_JSON": {"292554": {"title": "old"}}})
    return calls == [292554], "manual mode must ignore done.json, got %s" % calls


@case("a URL target works, not just a bare tid")
def _():
    rc, out, calls = _run(_Args(targets=["https://bbs.kanxue.com/thread-292554.htm"]))
    return calls == [292554], "got %s" % calls


@case("several targets are all fetched")
def _():
    rc, out, calls = _run(_Args(targets=["1", "thread-2.htm"]))
    return calls == [1, 2], "got %s" % calls


@case("no crawl state is written on success")
def _():
    _run(_Args())
    left = _state_files()
    return left == [], "manual mode wrote %s" % left


@case("no crawl state is written for a gated thread")
def _():
    _run(_Args(no_like=True), fetch_result=(None, "回复可见"))
    left = _state_files()
    return left == [], "manual mode wrote %s" % left


@case("no crawl state is written when the fetch raises")
def _():
    # fetch_result=None makes the stub's return unpack as a TypeError inside the loop -
    # the same "the fetch blew up" path a real PWError takes.
    rc, out, _ = _run(_Args(), fetch_result=None)
    left = _state_files()
    return left == [] and rc == 1, "rc=%s left=%s" % (rc, left)


@case("a gated thread is 点赞-retried unless --no-like")
def _():
    # a second fetch attempt is the retry after 点赞
    _, _, calls = _run(_Args(), fetch_result=(None, "回复可见"))
    _, _, calls2 = _run(_Args(no_like=True), fetch_result=(None, "回复可见"))
    return len(calls) == 2 and len(calls2) == 1, \
        "with-like=%d with--no-like=%d" % (len(calls), len(calls2))


@case("a bad target is rejected before opening a browser")
def _():
    rc, out, calls = _run(_Args(targets=["https://bbs.kanxue.com/forum-161-1.htm"]))
    return rc == 1 and calls == [], "rc=%s calls=%s" % (rc, calls)


@case("no target at all is an error")
def _():
    rc, out, calls = _run(_Args(targets=[]))
    return rc == 1 and calls == [], "rc=%s" % rc


def main():
    tmp = tempfile.mkdtemp(prefix="kanxue-thread-test-")
    crawl.OUT_DIR = tmp
    crawl.ARTICLES_DIR = os.path.join(tmp, "articles")
    crawl.ATTACH_DIR = os.path.join(tmp, "attachments")
    crawl.URLS_JSON = os.path.join(tmp, "urls.json")
    crawl.DONE_JSON = os.path.join(tmp, "done.json")
    crawl.FAILED_JSON = os.path.join(tmp, "failed.json")
    crawl.LOCKED_JSON = os.path.join(tmp, "locked.json")

    failures = []
    try:
        for name, fn in CASES:
            for f in os.listdir(tmp):                  # each case starts from clean state
                p = os.path.join(tmp, f)
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            try:
                ok, why = fn()
            except Exception as exc:                   # noqa: BLE001
                ok, why = False, "%s: %s" % (type(exc).__name__, exc)
            print("%-4s %s%s" % ("ok" if ok else "FAIL", name, "" if ok else "  <- " + str(why)))
            if not ok:
                failures.append(name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d/%d passed" % (len(CASES) - len(failures), len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
