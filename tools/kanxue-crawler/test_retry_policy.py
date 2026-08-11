#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Which threads does a run attempt? Exercises cmd_fetch's `wanted()` selection.

The policy is small but easy to get subtly wrong, and getting it wrong is expensive in
both directions: too strict and a 安全验证 failure is stranded forever (nothing else
revisits failed.json); too loose and a broken solver makes every daily run re-walk the
same threads until the job times out.

Runs without a browser or network - it drives cmd_fetch far enough to print its
selection line and then stops, which is where the whole decision lives.

    python test_retry_policy.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


class _Args(object):
    def __init__(self, **kw):
        self.retry_failed = False
        self.captcha_retry_max = 3
        self.limit = 0
        self.headless = True
        self.no_replies = False
        self.max_reply_pages = 0
        self.__dict__.update(kw)


def _run(crawl, threads, done, failed, locked, args):
    """Call cmd_fetch and return (fetching_count, printed_line).

    cmd_fetch stops on its own once the todo list is empty; when it is not, it would
    open a browser, so a sentinel exception is raised from the Browser constructor to
    cut it off right after the selection is printed.
    """
    crawl.save_json(crawl.URLS_JSON, {"threads": threads})
    crawl.save_json(crawl.DONE_JSON, done)
    crawl.save_json(crawl.FAILED_JSON, failed)
    crawl.save_json(crawl.LOCKED_JSON, locked)

    class _Stop(Exception):
        pass

    class _FakeBrowser(object):
        def __init__(self, *a, **kw):
            raise _Stop()

    real = crawl.Browser
    crawl.Browser = _FakeBrowser
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            try:
                crawl.cmd_fetch(args)
            except _Stop:
                pass
    finally:
        crawl.Browser = real
    line = next((l for l in buf.getvalue().splitlines() if "threads total" in l), "")
    n = int(line.split("fetching")[1].split()[0]) if "fetching" in line else -1
    return n, line


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


THREADS = [{"tid": i, "url": "u%d" % i, "title": "t%d" % i} for i in (1, 2, 3, 4)]
CAP = "CaptchaRequired: https://bbs.kanxue.com/thread-1.htm"


@case("a fresh thread is fetched")
def _(crawl):
    n, _ = _run(crawl, THREADS, {}, {}, {}, _Args())
    return n == 4, "expected 4, got %d" % n


@case("done and locked threads are skipped")
def _(crawl):
    n, _ = _run(crawl, THREADS, {"1": {}}, {}, {"2": {}}, _Args())
    return n == 2, "expected 2, got %d" % n


@case("a stale 安全验证 failure is retried by default")
def _(crawl):
    # the shape written by runs from before the solver existed: no attempts key
    n, line = _run(crawl, THREADS, {}, {"1": {"error": CAP}}, {}, _Args())
    return n == 4 and "retrying" in line, "expected 4 with a retry note, got %d (%s)" % (n, line)


@case("a 安全验证 failure stops being retried past the cap")
def _(crawl):
    n, _ = _run(crawl, THREADS, {}, {"1": {"error": CAP, "attempts": 3}}, {}, _Args())
    return n == 3, "expected 3, got %d" % n


@case("attempts below the cap are still retried")
def _(crawl):
    n, _ = _run(crawl, THREADS, {}, {"1": {"error": CAP, "attempts": 2}}, {}, _Args())
    return n == 4, "expected 4, got %d" % n


@case("a non-captcha failure is NOT retried by default")
def _(crawl):
    n, _ = _run(crawl, THREADS, {}, {"1": {"error": "PWTimeout: nope"}}, {}, _Args())
    return n == 3, "expected 3, got %d" % n


@case("--retry-failed retries everything regardless of kind or cap")
def _(crawl):
    failed = {"1": {"error": CAP, "attempts": 99}, "2": {"error": "PWTimeout: nope"}}
    n, _ = _run(crawl, THREADS, {}, failed, {}, _Args(retry_failed=True))
    return n == 4, "expected 4, got %d" % n


@case("--captcha-retry-max 0 disables the auto-retry")
def _(crawl):
    n, _ = _run(crawl, THREADS, {}, {"1": {"error": CAP}}, {}, _Args(captcha_retry_max=0))
    return n == 3, "expected 3, got %d" % n


@case("--no-auto-captcha stops auto-retrying too")
def _(crawl):
    # nothing would clear the interstitial this run, so re-walking it is pure waste
    crawl.CAPTCHA_AUTOSOLVE = False
    try:
        n, _ = _run(crawl, THREADS, {}, {"1": {"error": CAP}}, {}, _Args())
    finally:
        crawl.CAPTCHA_AUTOSOLVE = True
    return n == 3, "expected 3, got %d" % n


@case("a done thread wins over a failed entry")
def _(crawl):
    n, _ = _run(crawl, THREADS, {"1": {}}, {"1": {"error": CAP}}, {}, _Args())
    return n == 3, "expected 3, got %d" % n


def main():
    import crawl

    tmp = tempfile.mkdtemp(prefix="kanxue-retry-test-")
    crawl.OUT_DIR = tmp
    crawl.ARTICLES_DIR = os.path.join(tmp, "articles")
    crawl.URLS_JSON = os.path.join(tmp, "urls.json")
    crawl.DONE_JSON = os.path.join(tmp, "done.json")
    crawl.FAILED_JSON = os.path.join(tmp, "failed.json")
    crawl.LOCKED_JSON = os.path.join(tmp, "locked.json")

    failures = []
    try:
        for name, fn in CASES:
            try:
                ok, why = fn(crawl)
            except Exception as exc:                   # noqa: BLE001
                ok, why = False, "%s: %s" % (type(exc).__name__, exc)
            print("%-4s %s%s" % ("ok" if ok else "FAIL", name, "" if ok else "  <- " + why))
            if not ok:
                failures.append(name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d/%d passed" % (len(CASES) - len(failures), len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
