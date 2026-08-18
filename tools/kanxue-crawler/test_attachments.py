#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attachment parsing + link plumbing.  No browser or network - the download itself needs
an authenticated context, but everything up to it is pure string work and is where the
easy mistakes live: decoding kanxue's xn-escaped download token, keeping the husk out of
the Markdown, and giving two same-named files distinct paths.

    python test_attachments.py
"""

from __future__ import annotations

import os
import sys

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crawl  # noqa: E402

BASE = crawl.BASE_URL

# The 上传的附件 fieldset exactly as kanxue serves it (tourist view; a member's anchor
# carries the same data-href).  The token is xn-encoded: _2B -> '+', _3D -> '='.
ATTACH_HTML = """
<div class="message" isfirst="1">
  <p>正文内容。</p>
  <fieldset class="fieldset"><legend>上传的附件：</legend>
    <ul class="attachlist attach_tourist">
      <li aid="403432">
        <a href="javascript:void(0)" class="modal-title" data-toggle="modal"
           data-href="attach-download-403432-a4ed2cc14e8e81f440fb8f6db5fc0473@_2B1uFBlRaVY7QfxxCUCAWtA_3D_3D.htm"
           data-target=".download_code" data-aid="403432">
          <i class="icon filetype zip"></i>
          ifeng.jsonl.zip
        </a>
        <span class="">（962.67kb，20次下载）</span>
      </li>
    </ul>
  </fieldset>
</div>
"""

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def _msg(html):
    return BeautifulSoup(html, "lxml").select_one("div.message")


@case("data-href is xn-decoded into the real download URL")
def _():
    att = crawl.parse_attachments(_msg(ATTACH_HTML), BASE)[0]
    want = (BASE + "attach-download-403432-"
            "a4ed2cc14e8e81f440fb8f6db5fc0473@+1uFBlRaVY7QfxxCUCAWtA==.htm")
    return att["url"] == want, "got %s" % att["url"]


@case("filename, aid and size are captured")
def _():
    att = crawl.parse_attachments(_msg(ATTACH_HTML), BASE)[0]
    ok = (att["filename"] == "ifeng.jsonl.zip" and att["aid"] == "403432"
          and att["info"] == "962.67kb，20次下载")
    return ok, "got %r" % att


@case("strip_attachment_boxes removes the 上传的附件 husk")
def _():
    msg = _msg(ATTACH_HTML)
    crawl.strip_attachment_boxes(msg)
    text = msg.get_text()
    return "上传的附件" not in text and "ifeng.jsonl.zip" not in text, text.strip()[:80]


@case("a non-attachment anchor is ignored")
def _():
    html = ('<div class="message"><ul class="attachlist"><li aid="1">'
            '<a href="thread-999.htm">看别的帖子</a></li></ul></div>')
    return crawl.parse_attachments(_msg(html), BASE) == [], "should be empty"


@case("assign_attachment_paths keeps same-named files distinct")
def _():
    atts = [{"aid": "10", "filename": "poc.zip"}, {"aid": "11", "filename": "poc.zip"}]
    crawl.assign_attachment_paths(atts, 42)
    names = [a["diskname"] for a in atts]
    ok = len(set(names)) == 2 and all(a["relpath"].startswith("../attachments/42/") for a in atts)
    return ok, "got %s" % names


@case("assign_attachment_paths sanitises unsafe names")
def _():
    atts = [{"aid": "9", "filename": "../../etc/passwd"}]
    crawl.assign_attachment_paths(atts, 1)
    name = atts[0]["diskname"]
    return "/" not in name and ".." not in name, "got %r" % name


@case("attachment_markdown links to the local relative path")
def _():
    atts = [{"aid": "1", "filename": "x.zip", "info": "1kb"}]
    crawl.assign_attachment_paths(atts, 7)
    md = crawl.attachment_markdown(atts)
    return "[x.zip](../attachments/7/x.zip) — 1kb" in md, md


@case("frontmatter entry carries url, path and downloaded flag")
def _():
    atts = [{"aid": "1", "filename": "x.zip", "url": "http://h/x.htm", "info": "1kb"}]
    crawl.assign_attachment_paths(atts, 7)
    atts[0]["downloaded"] = True
    d = crawl.frontmatter_attachment(atts[0])
    ok = (d["url"] == "http://h/x.htm" and d["path"] == "../attachments/7/x.zip"
          and d["downloaded"] is True and d["size"] == "1kb")
    return ok, "got %r" % d


def main():
    failures = []
    for name, fn in CASES:
        try:
            ok, why = fn()
        except Exception as exc:                       # noqa: BLE001
            ok, why = False, "%s: %s" % (type(exc).__name__, exc)
        print("%-4s %s%s" % ("ok" if ok else "FAIL", name, "" if ok else "  <- " + str(why)))
        if not ok:
            failures.append(name)
    print("\n%d/%d passed" % (len(CASES) - len(failures), len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
