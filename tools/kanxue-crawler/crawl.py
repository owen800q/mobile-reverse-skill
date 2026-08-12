#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl 看雪 (bbs.kanxue.com) Android 安全版块的帖子 into clean Markdown.

Two stages:
  1) `urls`  - paginate forum-161 (digest=0, orderby=tid), parse each row's date and
               reply count (only threads with more than 10 replies are kept, as a
               quality filter), early-exit once we are consistently before the
               cutoff. -> output/urls.json
  2) `fetch` - open each thread, extract OP + replies with kanxue-specific selectors,
               convert to Markdown (code blocks preserved). -> output/articles/{tid}-{slug}.md

Auth: a Playwright *persistent context* (user-data-dir) keeps the login + JS-challenge
cookies alive across runs. Log in once with `crawl.py login` (or import a cookie export).
No credentials or cookies are hardcoded here.

安全验证: kanxue guards some threads with a 网易易盾 jigsaw slider. `tools/slider-cv`
clears it - OpenCV locates the gap, the driver drags the handle - so a headless run is
no longer blocked by it. Disable with `--no-auto-captcha`; a headed run still falls
back to waiting for you if the solver comes up short.

Usage:
    python crawl.py login                 # opens a browser, you log in, session is saved
    python crawl.py login --cookies c.json
    python crawl.py urls
    python crawl.py fetch --limit 10
    python crawl.py unlock                # 点赞 the 回复可见 threads, then fetch them
    python crawl.py dry-run               # urls + first 10 threads
    python crawl.py all
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import frontmatter
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from tqdm import tqdm

try:
    from playwright.sync_api import Error as PWError
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sys.exit("playwright is not installed.  pip install -r requirements.txt "
             "&& python -m playwright install chromium")

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------

BASE_URL = "https://bbs.kanxue.com/"
FORUM_ID = 161
BOARD_NAME = "Android安全"
LIST_URL = BASE_URL + "forum-{fid}-{page}.htm?orderby=tid&digest=0"
THREAD_URL = BASE_URL + "thread-{tid}.htm"
THREAD_PAGE_URL = BASE_URL + "thread-{tid}-{page}.htm"

CUTOFF_DATE = date(2023, 1, 1)
MIN_REPLIES = 10        # quality filter: only keep threads with >= 10 replies

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")
ARTICLES_DIR = os.path.join(OUT_DIR, "articles")
PROFILE_DIR = os.path.join(HERE, ".browser-profile")   # persistent context (gitignore this)
STATE_JSON = os.path.join(HERE, ".session-state.json")  # cookie jar (gitignore this too)

URLS_JSON = os.path.join(OUT_DIR, "urls.json")
DONE_JSON = os.path.join(OUT_DIR, "done.json")
FAILED_JSON = os.path.join(OUT_DIR, "failed.json")
LOCKED_JSON = os.path.join(OUT_DIR, "locked.json")

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

SLEEP_THREAD = (2.0, 4.0)   # between threads
SLEEP_PAGE = (2.0, 4.0)     # between list pages / reply pages
NAV_TIMEOUT_MS = 45_000
RETRIES = 3

# kanxue truncates gated bodies with a `.expandNoteBox` overlay.  Its wording tells us
# which kind of gate it is:
#   "登录后可查看完整内容"      -> our session is dead    -> stop the crawl
#   "回复或点赞可查看完整内容"  -> 回复可见 thread        -> record in locked.json, skip
LOGIN_WALL_MARKERS = ("登录后可查看完整内容", "登录后查看", "请先登录后再查看")

# Secondary, text-based 回复可见 / paid-content markers.  Matched only against *short
# standalone lines* so an article merely discussing these words is not flagged.
LOCK_PATTERNS = [
    r"回复.{0,6}可查看",
    r"回复.{0,6}可见",
    r"回复.{0,6}(才能|方可|后).{0,4}(查看|浏览|可见)",
    r"本帖.{0,8}隐藏",
    r"隐藏.{0,4}内容.{0,8}(回复|购买)",
    r"购买主题",
    r"支付.{0,8}(看雪币|吾爱币|论坛币)",
    r"需要.{0,10}(积分|看雪币).{0,8}(查看|下载)",
]
LOCK_RE = re.compile("|".join(LOCK_PATTERNS))
LOCK_SELECTORS = [".reply_visible", ".hidden_content", ".hide_content", ".buy_thread"]

# Chrome inside the message body that is never content.
DROP_SELECTORS = [
    "script", "style", "noscript", "input", "iframe",
    ".expandNoteBox",              # gated-content gradient overlay
    ".signature", ".sign",         # signature blocks
    ".ggBox", ".adBox", ".ad", ".advertisement",
    "a.bbs_thread",                # site-wide promo link appended to every post
    ".text-muted.font-italic",     # "最后于 X 被 Y 编辑，原因：" footer
    ".pagination", "nav",
    ".attach_nopermission",
]

TAG_LINK_RE = re.compile(r"forum-\d+-\d+-\d+")

LANG_RE = re.compile(r"language-([A-Za-z0-9_+#-]+)")
DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?")

# kanxue obfuscates outbound links (plugin/link/kx_url_decrypt.js).  The page's own JS
# normally un-mangles them on DOMContentLoaded; we redo it in Python so the output is
# correct even if that script is slow, blocked, or changed.
KX_PAIRS = {
    'K9': 'a', 'L8': 'b', 'M7': 'c', 'N6': 'd', 'P5': 'e', 'Q4': 'f', 'R3': 'g',
    'S2': 'h', 'T1': 'i', 'U0': 'j', 'V1': 'k', 'W2': 'l', 'X3': 'm', 'Y4': 'n',
    'Z5': 'o', 'A6': 'p', 'B7': 'q', 'C8': 'r', 'D9': 's', 'E0': 't', 'F1': 'u',
    'G2': 'v', 'H3': 'w', 'I4': 'x', 'J5': 'y', 'K6': 'z',
    'l9': 'A', 'm8': 'B', 'n7': 'C', 'o6': 'D', 'p5': 'E', 'q4': 'F', 'r3': 'G',
    's2': 'H', 't1': 'I', 'u0': 'J', 'v1': 'K', 'w2': 'L', 'x3': 'M', 'y4': 'N',
    'z5': 'O', 'a6': 'P', 'b7': 'Q', 'c8': 'R', 'd9': 'S', 'e0': 'T', 'f1': 'U',
    'g2': 'V', 'h3': 'W', 'i4': 'X', 'j5': 'Y', 'k6': 'Z',
    '@1': '0', '#2': '1', '$3': '2', '%4': '3', '^5': '4', '&6': '5', '*7': '6',
    '(8': '7', ')9': '8', '!0': '9', '-_': '+', '|~': '/', '`.': '=',
}
XN_ESCAPE_RE = re.compile(r"_([0-9a-fA-F]{2})")

# Every page renders the viewer's uid into an inline script: '0' means anonymous.
# That is server-side truth, unlike "is the 登录 button visible" (a modal hides it).
UID_RE = re.compile(r"var\s+uid\s*=\s*['\"](\d+)['\"]")


# --------------------------------------------------------------------------------------
# small utils
# --------------------------------------------------------------------------------------

class LoginRequired(Exception):
    """Raised when the session is not (or no longer) authenticated."""


class CaptchaRequired(Exception):
    """Raised when kanxue serves its 安全验证 interstitial and we could not clear it.

    The interstitial is a 网易易盾 jigsaw slider.  `tools/slider-cv` locates the gap
    with OpenCV and drags the handle, which is what lets a headless CI run get past
    it; a headed run additionally falls back to waiting for the operator.  This is
    raised only once both routes are exhausted.
    """


def ensure_dirs():
    for d in (OUT_DIR, ARTICLES_DIR):
        os.makedirs(d, exist_ok=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=False)
    os.replace(tmp, path)


def nap(bounds):
    time.sleep(random.uniform(*bounds))


def now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def slugify(title, maxlen=60):
    """Filesystem-safe slug that keeps CJK (titles here are mostly Chinese)."""
    t = re.sub(r"^\s*[\[【][^\]】]{1,12}[\]】]\s*", "", title or "")  # drop [原创] prefix
    t = re.sub(r"[^\w一-鿿]+", "-", t, flags=re.UNICODE)
    t = re.sub(r"-{2,}", "-", t).strip("-_")
    return (t[:maxlen].strip("-_") or "thread")


def kx_url_decrypt(s):
    """Port of plugin/link/kx_url_decrypt.js + xn.urldecode.  Returns '' on failure."""
    import base64
    if not s or "http://" in s or "https://" in s or s.startswith("www."):
        return s or ""
    body = s[3:]                                     # drop the 3-char salt
    for pat, rep in KX_PAIRS.items():
        body = body.replace(pat, rep)
    body = re.sub(r"[^A-Za-z0-9+/=]", "", body)
    body += "=" * (-len(body) % 4)
    try:
        decoded = base64.b64decode(body).decode("utf-8", "replace")
    except Exception:
        return ""
    decoded = XN_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), decoded)
    return decoded if decoded.startswith(("http://", "https://", "www.", "ftp://")) else ""


def deobfuscate_links(el):
    """Undo kanxue's <mark>-wrapped and elink@-prefixed link obfuscation, in place."""
    for mark in el.find_all("mark"):
        decoded = kx_url_decrypt(mark.get_text(strip=True))
        if decoded:
            mark.string = decoded
        mark.unwrap()
    for a in el.find_all("a", href=True):
        href = a["href"].strip()
        m = re.match(r"^(?:https?://[^/]+/)?elink@(.+)$", href)
        if m:
            decoded = kx_url_decrypt(m.group(1))
            if decoded:
                a["href"] = decoded
            else:
                del a["href"]
    return el


def title_prefix_tag(title):
    m = re.match(r"^\s*[\[【]([^\]】]{1,12})[\]】]", title or "")
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------------------

def check_robots(verbose=True):
    """Return True if the board + thread paths are crawlable for UA '*'."""
    rp = RobotFileParser()
    url = urljoin(BASE_URL, "/robots.txt")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        body = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception as exc:
        print("! could not fetch robots.txt (%s) - assuming allowed" % exc)
        return True
    rp.parse(body.splitlines())
    probes = [
        LIST_URL.format(fid=FORUM_ID, page=1),
        THREAD_URL.format(tid=292066),
    ]
    blocked = [u for u in probes if not rp.can_fetch("*", u)]
    if blocked:
        print("robots.txt DISALLOWS the following paths for User-agent: *")
        for u in blocked:
            print("   ", u)
        return False
    if verbose:
        print("robots.txt: board and thread paths are allowed.")
    return True


# --------------------------------------------------------------------------------------
# Markdown conversion
# --------------------------------------------------------------------------------------

class KanxueConverter(MarkdownConverter):
    """markdownify tuned for kanxue post bodies.

    The single most important job is code-block fidelity: kanxue renders code as
    <pre><code class="language-xxx hljs">...<span class="hljs-*">...</span></pre>, so we
    take the raw text of the <code> node (highlight spans flattened) and re-fence it.
    """

    def __init__(self, base_url=BASE_URL, **kwargs):
        kwargs.setdefault("escape_asterisks", False)
        kwargs.setdefault("escape_underscores", False)
        kwargs.setdefault("heading_style", "ATX")
        kwargs.setdefault("bullets", "-")
        super().__init__(**kwargs)
        self.base_url = base_url

    # ---- code -------------------------------------------------------------------
    def convert_pre(self, el, text, convert_as_inline):
        code_el = el.find("code")
        node = code_el if code_el is not None else el
        raw = node.get_text()
        raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        if not raw.strip():
            return ""
        lang = ""
        classes = " ".join(node.get("class", []) or []) + " " + " ".join(el.get("class", []) or [])
        m = LANG_RE.search(classes)
        if m:
            lang = m.group(1)
            if lang in ("plaintext", "text", "nohighlight", "undefined"):
                lang = ""
        fence = "```"
        while fence in raw:                      # widen the fence if the code contains ```
            fence += "`"
        # Tag our own fences so tidy_markdown() can tell them apart from a post whose
        # literal text is backticks (people do reply with just "```"), which would
        # otherwise open a block that swallows the rest of the document.
        return "\n\n%s%s%s\n%s\n%s%s\n\n" % (FENCE_MARK, fence, lang, raw, FENCE_MARK, fence)

    # ---- links / images ---------------------------------------------------------
    def convert_a(self, el, text, convert_as_inline):
        href = (el.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#")):
            return text
        el["href"] = urljoin(self.base_url, href)
        return super().convert_a(el, text, convert_as_inline)

    def convert_img(self, el, text, convert_as_inline):
        src = (el.get("src") or el.get("data-src") or el.get("data-original") or "").strip()
        if not src:
            return ""
        alt = (el.get("alt") or "").strip() or "image"
        return "![%s](%s)" % (alt, urljoin(self.base_url, src))

    # ---- tables -----------------------------------------------------------------
    def convert_table(self, el, text, convert_as_inline):
        rows = el.find_all("tr")
        if not rows:
            return ""
        grid = []
        for tr in rows:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            grid.append([re.sub(r"\s*\n\s*", " ", self.process_tag(c, False, children_only=True)).strip()
                         for c in cells])
        if not grid:
            return ""
        width = max(len(r) for r in grid)
        grid = [r + [""] * (width - len(r)) for r in grid]
        out = ["| " + " | ".join(c.replace("|", "\\|") for c in grid[0]) + " |",
               "|" + "|".join(["-"] * width) + "|"]
        for r in grid[1:]:
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
        return "\n\n" + "\n".join(out) + "\n\n"

    def convert_tr(self, el, text, convert_as_inline):
        return text  # handled by convert_table

    def convert_td(self, el, text, convert_as_inline):
        return text

    def convert_th(self, el, text, convert_as_inline):
        return text


FENCE_MARK = "\ue000"                      # private-use sentinel, stripped by tidy_markdown
STRAY_FENCE_RE = re.compile(r"^(`{3,})([ \t]*)$", re.M)
BULLET_FENCE_RE = re.compile(r"^([ \t]*)(?:[-*+]|\d+\.)[ \t]+(`{3,}\w*)[ \t]*$", re.M)


def tidy_markdown(md):
    md = md.replace(" ", " ").replace("​", "")
    # A <pre> that was the only content of an <li> lands as "- ```", which opens a fence
    # mid-line and breaks both the list and the code block.  The bullet carries no text of
    # its own, so drop it and let the fence start its own line.
    md = BULLET_FENCE_RE.sub(r"\1\2", md)
    # A line of bare backticks that we did NOT emit is literal post content; escape it
    # so it cannot open a code block.  Our own fences carry FENCE_MARK.
    md = STRAY_FENCE_RE.sub(r"\\\1\2", md)
    md = md.replace(FENCE_MARK, "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def html_to_markdown(el, base_url):
    return tidy_markdown(KanxueConverter(base_url=base_url).convert_soup(el))


def clean_message(el):
    """Strip nav/ads/signature/etc. from a message element (mutates the soup)."""
    for sel in DROP_SELECTORS:
        for node in el.select(sel):
            node.decompose()
    # avatars inside quoted replies are pure noise
    for img in el.find_all("img", src=True):
        if "/upload/avatar/" in img["src"]:
            img.decompose()
    deobfuscate_links(el)
    # kanxue wraps the login-wall overlay in a 1px-tall relative div; drop the husk
    for node in el.find_all("div"):
        if not node.get_text(strip=True) and not node.find(["img", "pre", "code", "table"]):
            style = (node.get("style") or "").replace(" ", "")
            if "height:1px" in style:
                node.decompose()
    return el


# --------------------------------------------------------------------------------------
# Stage 1 - thread list
# --------------------------------------------------------------------------------------

def parse_list_date(text, today=None):
    """kanxue shows '2天前' / '昨天 09:12' / '2026-7-18 23:09'.  -> datetime.date | None"""
    if not text:
        return None
    today = today or date.today()
    t = text.strip().lstrip("・·•").strip()
    m = DATE_RE.search(t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d+)\s*(秒|分钟|小时|天|周|个月|月|年)前", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = {"秒": 0, "分钟": 0, "小时": 0, "天": n, "周": n * 7,
                "个月": n * 30, "月": n * 30, "年": n * 365}[unit]
        return today - timedelta(days=days)
    if t.startswith("刚刚") or t.startswith("今天"):
        return today
    if t.startswith("昨天"):
        return today - timedelta(days=1)
    if t.startswith("前天"):
        return today - timedelta(days=2)
    return None


def parse_list_page(html):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for tr in soup.select("tr.thread[data-tid]"):
        tid = tr.get("data-tid")
        if not tid or not tid.isdigit():
            continue
        subj = tr.select_one("div.subject")
        title_a = None
        for a in (subj.select("a[href^='thread-']") if subj else []):
            if a.get_text(strip=True):
                title_a = a
                break
        title = title_a.get_text(" ", strip=True) if title_a else ""
        author_a = tr.select_one("a.username")
        date_span = tr.select_one("span.date")
        raw_date = date_span.get_text(" ", strip=True).lstrip("・·• ") if date_span else ""
        # the right-hand counters are two divs: views first, replies last
        replies = None
        tright = tr.select_one("div.text-right")
        counter_divs = tright.find_all("div", recursive=False) if tright else []
        if counter_divs:
            span = counter_divs[-1].find("span")
            txt = span.get_text(strip=True) if span else ""
            if txt.isdigit():
                replies = int(txt)
        out.append({
            "tid": int(tid),
            "url": THREAD_URL.format(tid=tid),
            "title": title,
            "author": author_a.get_text(strip=True) if author_a else "",
            "date_raw": raw_date,
            "date": None,          # filled by caller
            "replies": replies,
            # sticky rows carry class "top_1"/"top_2"/"top_3"
            "sticky": any(c.startswith("top") for c in (tr.get("class") or [])),
        })
    has_next = bool(soup.select_one("ul.pagination a.page-link"))
    return out, has_next


def collect_urls(page, cutoff=CUTOFF_DATE, max_pages=200, old_page_tolerance=2, verbose=True,
                 min_replies=MIN_REPLIES):
    threads, seen = [], set()
    old_pages = 0
    n_low_replies = 0
    today = date.today()

    for page_no in range(1, max_pages + 1):
        url = LIST_URL.format(fid=FORUM_ID, page=page_no)
        try:
            with_retry(lambda: goto(page, url, wait_for="tr.thread"),
                       "list page %d" % page_no)
        except (PWTimeout, PWError) as exc:
            # deep pagination can hit throttling; a partial scan is still useful,
            # the next run picks up where this one stalled
            if verbose:
                print("page %d: unreachable after retries (%s) - keeping the %d "
                      "thread(s) collected so far" % (page_no, str(exc)[:120], len(threads)))
            break
        rows, has_next = parse_list_page(page.content())
        if not rows:
            if verbose:
                print("page %d: no rows, stopping." % page_no)
            break

        fresh_on_page = 0
        for r in rows:
            if r["sticky"]:
                continue  # announcements/events, not technical content; also ignored for exit
            r["date"] = parse_list_date(r["date_raw"], today)
            d = r["date"]
            if d is None or d >= cutoff:
                fresh_on_page += 1
                # quality filter: an unknown count fails open, a known low one is skipped
                if min_replies and r["replies"] is not None and r["replies"] < min_replies:
                    n_low_replies += 1
                    continue
                if r["tid"] not in seen:
                    seen.add(r["tid"])
                    threads.append({
                        "tid": r["tid"], "url": r["url"], "title": r["title"],
                        "author": r["author"],
                        "date": d.isoformat() if d else None,
                        "date_raw": r["date_raw"], "replies": r["replies"],
                        "list_page": page_no,
                    })

        if verbose:
            first, last = rows[0]["date_raw"], rows[-1]["date_raw"]
            print("page %2d: %2d rows, %2d >= cutoff  (%s ... %s)  total=%d"
                  % (page_no, len(rows), fresh_on_page, first, last, len(threads)))

        if fresh_on_page == 0:
            old_pages += 1
            if old_pages >= old_page_tolerance:
                if verbose:
                    print("early exit: %d consecutive pages entirely before %s"
                          % (old_pages, cutoff))
                break
        else:
            old_pages = 0

        if not has_next:
            break
        nap(SLEEP_PAGE)

    if verbose and min_replies and n_low_replies:
        print("skipped %d thread(s) with fewer than %d replies" % (n_low_replies, min_replies))
    threads.sort(key=lambda t: t["tid"], reverse=True)
    return threads


# --------------------------------------------------------------------------------------
# Stage 2 - thread extraction
# --------------------------------------------------------------------------------------

def _first_date_text(container):
    for span in container.select("span.date"):
        m = DATE_RE.search(span.get_text(" ", strip=True))
        if m:
            return m.group(0)
    return ""


def _first_named_user(container):
    """First user link that actually carries a name (the avatar link has none)."""
    for a in container.select("a.username_box, a[href^='user-home-'], a[href^='user-']"):
        name = a.get_text(" ", strip=True)
        if name:
            return name
    return ""


def _norm_date(raw):
    m = DATE_RE.search(raw or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def parse_op(soup, base_url):
    msg = soup.select_one('div.message[isfirst="1"]') or soup.select_one("div.message")
    if msg is None:
        raise ValueError("no OP message element found")

    # title
    title = ""
    h = soup.select_one("h3.subject, h1.subject, .subject h3, h1")
    if h:
        title = h.get_text(" ", strip=True)
    if not title and soup.title:
        title = re.sub(r"-%s-.*$" % re.escape(BOARD_NAME), "", soup.title.get_text(strip=True)).strip()
        title = re.sub(r"-看雪.*$", "", title).strip()

    # walk up until we find the post header (author link + date)
    author, raw_date = "", ""
    node = msg.parent
    for _ in range(8):
        if node is None:
            break
        name = _first_named_user(node)
        if name:
            author = author or name
            raw_date = raw_date or _first_date_text(node)
            if author and raw_date:
                break
        node = node.parent

    gate = detect_gate(msg)
    tags = extract_thread_tags(msg)
    body = html_to_markdown(clean_message(msg), base_url)
    return {
        "title": title, "author": author, "date_raw": raw_date,
        "date": _norm_date(raw_date), "body": body, "gate": gate, "tags": tags,
    }


def parse_replies(soup, base_url):
    replies = []
    for tr in soup.select("table.postlist tr.post[data-pid]"):
        msg = tr.select_one("div.message")
        if msg is None:
            continue
        floor_el = tr.select_one("span.floor")
        author_el = tr.select_one("a.username_box") or tr.select_one("a[href^='user-home-']")
        body = html_to_markdown(clean_message(msg), base_url)
        if not body.strip():
            continue
        replies.append({
            "pid": tr.get("data-pid"),
            "floor": floor_el.get_text(strip=True) if floor_el else "",
            "author": author_el.get_text(" ", strip=True) if author_el else "匿名",
            "date_raw": _first_date_text(tr),
            "body": body,
        })
    return replies


def detect_gate(msg_el):
    """Classify a truncated body.

    Returns ('login', text) when the session is dead, ('locked', text) for a
    回复可见 / 点赞可见 / paid thread, or None when the body is fully readable.
    """
    box = msg_el.select_one(".expandNoteBox")
    if box is not None:
        txt = box.get_text(" ", strip=True)[:120]
        kind = "login" if any(m in txt for m in ("登录", "登陆")) else "locked"
        return (kind, txt or "expandNoteBox")
    for sel in LOCK_SELECTORS:
        node = msg_el.select_one(sel)
        if node is not None:
            return ("locked", node.get_text(" ", strip=True)[:120] or sel)
    # The text fallback must not see the chrome we are about to strip - an author's edit
    # reason ("改成点赞回复可见") is *about* a gate, not a gate.
    scan = copy.copy(msg_el)
    for sel in DROP_SELECTORS:
        for node in scan.select(sel):
            node.decompose()
    for line in scan.get_text("\n", strip=True).split("\n"):
        line = line.strip()
        if len(line) <= 60 and LOCK_RE.search(line):
            return ("locked", line[:120])
    return None


def extract_thread_tags(msg_el):
    """Pull the '#逆向分析' tag chips out of the OP body (and remove them from it)."""
    tags = []
    for a in msg_el.select("a[href]"):
        text = a.get_text(strip=True)
        if text.startswith("#") and TAG_LINK_RE.search(a.get("href", "")):
            tag = text.lstrip("#").strip()
            if tag and tag not in tags:
                tags.append(tag)
            a.decompose()
    return tags


def thread_page_count(soup, tid):
    pages = {1}
    for a in soup.select("table.postlist ul.pagination a.page-link, ul.pagination a.page-link"):
        m = re.search(r"thread-%d-(\d+)\.htm" % tid, a.get("href") or "")
        if m:
            pages.add(int(m.group(1)))
    return max(pages)


def assert_logged_in(html):
    for marker in LOGIN_WALL_MARKERS:
        if marker in html:
            raise LoginRequired("page shows '%s' - the session is not logged in" % marker)


def fetch_thread(page, meta, with_replies=True, max_reply_pages=0):
    """Fetch one thread (all reply pages) and return (frontmatter_dict, markdown_body)."""
    tid = meta["tid"]
    url = THREAD_URL.format(tid=tid)
    goto(page, url, wait_for="div.message")
    html = page.content()
    assert_logged_in(html)
    soup = BeautifulSoup(html, "lxml")

    op = parse_op(soup, url)
    if op["gate"]:
        kind, text = op["gate"]
        if kind == "login":
            raise LoginRequired("thread %d shows '%s'" % (tid, text))
        return None, text

    replies, truncated = [], False
    if with_replies:
        replies = parse_replies(soup, url)
        total_pages = thread_page_count(soup, tid)
        last = total_pages
        if max_reply_pages and total_pages > max_reply_pages:
            last = max_reply_pages
            truncated = True
        for p in range(2, last + 1):
            nap(SLEEP_PAGE)
            purl = THREAD_PAGE_URL.format(tid=tid, page=p)
            goto(page, purl, wait_for="table.postlist")
            phtml = page.content()
            assert_logged_in(phtml)
            replies.extend(parse_replies(BeautifulSoup(phtml, "lxml"), purl))
    else:
        total_pages = thread_page_count(soup, tid)

    title = op["title"] or meta.get("title") or ("thread-%d" % tid)
    tags = [BOARD_NAME]
    prefix = title_prefix_tag(title)
    if prefix:
        tags.append(prefix)
    for t in op["tags"]:
        if t not in tags:
            tags.append(t)

    fm = {
        "title": title,
        "url": url,
        "tid": tid,
        "author": op["author"] or meta.get("author", ""),
        "date": op["date"] or meta.get("date") or "",
        "tags": tags,
        "crawled_at": now_iso(),
        "replies": len(replies),
    }

    parts = [op["body"]]
    if replies:
        parts.append("---\n\n# 回复")
        for r in replies:
            head = "## 回复 by %s (#%s)" % (r["author"], r["floor"] or "?")
            if r["date_raw"]:
                head += "\n\n*%s*" % r["date_raw"]
            parts.append(head + "\n\n" + r["body"])
    if truncated:
        parts.append("> 注：本帖共 %d 页回复，仅抓取前 %d 页。" % (total_pages, max_reply_pages))

    return (fm, tidy_markdown("\n\n".join(parts))), None


# --------------------------------------------------------------------------------------
# Playwright plumbing
# --------------------------------------------------------------------------------------

CAPTCHA_WAIT_S = 300         # how long to let a human clear the interstitial
CAPTCHA_INTERACTIVE = True   # headed runs can also fall back to a human
CAPTCHA_AUTOSOLVE = True     # try tools/slider-cv before anything else
CAPTCHA_ATTEMPTS = 4         # slider attempts per interstitial
CAPTCHA_DEBUG_DIR = None     # dump the images + an annotated overlay per attempt

SLIDER_CV_DIR = os.path.normpath(os.path.join(HERE, "..", "slider-cv"))


def _load_slider_solver():
    """Import tools/slider-cv lazily so a missing OpenCV only costs the auto-solve."""
    if SLIDER_CV_DIR not in sys.path:
        sys.path.insert(0, SLIDER_CV_DIR)
    try:
        from slider_driver import YIDUN, solve_with_retries
        return YIDUN, solve_with_retries
    except ImportError as exc:
        print("! slider auto-solve unavailable (%s).  "
              "pip install -r tools/slider-cv/requirements.txt" % exc)
        return None, None


def page_is_captcha(page):
    """True only for the standalone 安全验证 interstitial served *instead of* a thread.

    Matching on the string "NECaptchaValidate" anywhere in the document is not enough:
    kanxue's login modal lazily injects the same 易盾 widget into an ordinary thread
    page a few seconds after load, and treating that as an interstitial fails threads
    that had in fact loaded fine.  The interstitial is the page whose whole body is the
    verify form, so key on that form, and on the title it always carries.
    """
    try:
        if page.title().strip() == "安全验证":
            return True
        return page.query_selector("form#verifyForm input#NECaptchaValidate") is not None
    except PWError:
        return False


def solve_captcha(page, url):
    """Clear the 安全验证 slider with computer vision.  True if the page moved on."""
    profile, solve = _load_slider_solver()
    if solve is None:
        return False
    print("安全验证 slider at %s - solving (%d attempts)" % (url, CAPTCHA_ATTEMPTS))
    sys.stdout.flush()
    rep = solve(page, profile, attempts=CAPTCHA_ATTEMPTS, debug_dir=CAPTCHA_DEBUG_DIR)
    print("  gap x=%.1f drag=%.1fpx confidence=%.2f via %s -> %s%s"
          % (rep.gap_x, rep.distance, rep.confidence, rep.method or "?",
             "accepted" if rep.ok else "rejected",
             (" (%s)" % rep.error) if rep.error else ""))
    sys.stdout.flush()
    if not rep.ok:
        return False
    # 易盾 accepting the drag is not the end of it: the host page submits its own form
    # after a short countdown, and mid-navigation `page_is_captcha` answers False simply
    # because it cannot read the document.  Reading the body there yields a half-built
    # page.  So wait for a load state and require the verdict to hold twice.
    deadline = time.time() + 25
    while time.time() < deadline:
        page.wait_for_timeout(500)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            if page_is_captcha(page):
                continue
            page.wait_for_timeout(400)
            if not page_is_captcha(page):
                return True
        except (PWError, PWTimeout):
            continue          # still navigating - ask again
    return False


def wait_out_captcha(page, url):
    """Pause so the operator can clear kanxue's 安全验证 page in the visible browser."""
    print("\n" + "=" * 72)
    print("看雪 is showing its 安全验证 (captcha) page for:\n    %s" % url)
    print("Please solve it in the browser window - one pass covers the next hour.")
    print("The crawl resumes by itself; waiting up to %ds." % CAPTCHA_WAIT_S)
    print("=" * 72)
    sys.stdout.flush()
    deadline = time.time() + CAPTCHA_WAIT_S
    while time.time() < deadline:
        time.sleep(3)
        try:
            if not page_is_captcha(page):
                print("captcha cleared - resuming.\n")
                sys.stdout.flush()
                return True
        except PWError:
            continue
    return False


def goto(page, url, wait_for=None, timeout=NAV_TIMEOUT_MS):
    resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    if resp is not None and resp.status >= 400:
        raise PWError("HTTP %d for %s" % (resp.status, url))
    if page_is_captcha(page):
        cleared = CAPTCHA_AUTOSOLVE and solve_captcha(page, url)
        if not cleared and CAPTCHA_INTERACTIVE:
            cleared = wait_out_captcha(page, url)
        if not cleared:
            raise CaptchaRequired(url)
        if page_is_captcha(page):        # cleared onto some other page - reload the target
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    if wait_for:
        page.wait_for_selector(wait_for, timeout=timeout)
    page.wait_for_timeout(250)   # let xn_urldecode() rewrite obfuscated links
    return resp


def with_retry(fn, what, attempts=RETRIES, base=2.0):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except (LoginRequired, CaptchaRequired):
            raise
        except (PWTimeout, PWError, ValueError) as exc:
            last = exc
            if i < attempts - 1:
                delay = base * (2 ** i) + random.uniform(0, 1.5)
                tqdm.write("  retry %d/%d for %s in %.1fs (%s)"
                           % (i + 1, attempts - 1, what, delay, str(exc)[:120]))
                time.sleep(delay)
    raise last


def logged_in_uid(html):
    """0 = anonymous, >0 = the logged-in uid, None = marker not present."""
    m = UID_RE.search(html or "")
    return int(m.group(1)) if m else None


def is_logged_in(page):
    uid = logged_in_uid(page.content())
    if uid is not None:
        return uid > 0
    return page.evaluate("""() => {                      // fallback if the marker moves
        const btns = Array.from(document.querySelectorAll('a.login_btn, a[href*="user-login"]'));
        return !btns.some(b => b.offsetParent !== null);
    }""")


def save_session(ctx):
    """Persist cookies ourselves - Chromium drops session cookies on clean exit."""
    try:
        ctx.storage_state(path=STATE_JSON)
        os.chmod(STATE_JSON, 0o600)
    except Exception as exc:
        print("! could not save session state: %s" % exc)


def load_session(ctx):
    if not os.path.exists(STATE_JSON):
        return
    try:
        with open(STATE_JSON, "r", encoding="utf-8") as fh:
            cookies = json.load(fh).get("cookies") or []
        if cookies:
            ctx.add_cookies(cookies)
    except Exception as exc:
        print("! could not restore session state: %s" % exc)


def resolve_browser_executable():
    """Return the patched-CloakBrowser launcher, or None for stock Chromium.

    CI sets CRAWLER_BROWSER_EXECUTABLE (see tools/cloakbrowser-ci/entrypoint.sh) to the
    wrapper that in-memory patches and execs the pinned CloakBrowser build.  A local run
    without it silently used to fall back to Playwright's own Chromium, which is a very
    different browser to be crawling with - so the fallback now says so, and
    CRAWLER_REQUIRE_CLOAK=1 turns it into a hard error for runs that must not take it.
    """
    executable = (os.environ.get("CRAWLER_BROWSER_EXECUTABLE") or "").strip() or None
    required = (os.environ.get("CRAWLER_REQUIRE_CLOAK") or "").strip().lower() \
        in ("1", "true", "yes")
    if required and not executable:
        sys.exit("CRAWLER_REQUIRE_CLOAK is set but CRAWLER_BROWSER_EXECUTABLE is empty - "
                 "refusing to fall back to stock Chromium.")
    return executable


class Browser(object):
    def __init__(self, headless=False):
        self.headless = headless
        self._pw = None
        self.ctx = None
        self.page = None

    def __enter__(self):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        self._pw = sync_playwright().start()
        launch_options = {
            "headless": self.headless,
            "viewport": {"width": 1440, "height": 950},
            "locale": "zh-CN",
        }
        executable = resolve_browser_executable()
        if executable:
            # CloakBrowser presents its own coherent fingerprint.  Do NOT set user_agent
            # here: Playwright's override only partially propagates, so the old
            # macOS/Chrome-130 UA left the browser contradicting itself - measured with
            # tools/cloakbrowser-ci/verify_stealth.py --user-agent:
            #   navigator.userAgent      Chrome/130.0.0.0, Mac OS X
            #   userAgentData.brands     Chromium 141          <- real major leaks
            #   navigator.platform       Linux x86_64          <- real platform leaks
            # which is a sharper bot signal than no spoofing at all.
            # --disable-blink-features=AutomationControlled is the same kind of leftover:
            # a stock-Chromium trick that CloakBrowser handles natively, and a detectable
            # flag in its own right.
            launch_options["executable_path"] = executable
            print("browser  : %s (CRAWLER_BROWSER_EXECUTABLE)" % executable)
        else:
            launch_options["user_agent"] = USER_AGENT
            launch_options["args"] = ["--disable-blink-features=AutomationControlled"]
            print("browser  : stock Playwright Chromium (CRAWLER_BROWSER_EXECUTABLE is "
                  "unset) - fingerprint spoofing is the hand-rolled UA override only")
        self.ctx = self._pw.chromium.launch_persistent_context(
            PROFILE_DIR, **launch_options
        )
        self.ctx.set_default_timeout(NAV_TIMEOUT_MS)
        load_session(self.ctx)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        # Log what the page actually reports, not what we asked for: this is the one line
        # in a CI log that tells you which browser really ran.
        try:
            print("user-agent: %s" % self.page.evaluate("navigator.userAgent"))
        except Exception as exc:
            print("! could not read navigator.userAgent: %s" % exc)
        return self

    def __exit__(self, *exc):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self._pw:
                self._pw.stop()


def import_cookies(ctx, path):
    """Accept a browser-extension cookie export (list of dicts) or a Playwright state file."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    raw = data.get("cookies", data) if isinstance(data, dict) else data
    cookies = []
    for c in raw:
        ck = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain") or ".kanxue.com",
            "path": c.get("path", "/"),
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", True)),
        }
        exp = c.get("expirationDate") or c.get("expires")
        if exp and float(exp) > 0:
            ck["expires"] = float(exp)
        ss = c.get("sameSite")
        if ss in ("Lax", "Strict", "None"):
            ck["sameSite"] = ss
        cookies.append(ck)
    ctx.add_cookies(cookies)
    print("imported %d cookies from %s" % (len(cookies), path))


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------

def cmd_login(args):
    with Browser(headless=False) as b:
        if args.cookies:
            import_cookies(b.ctx, args.cookies)
        goto(b.page, LIST_URL.format(fid=FORUM_ID, page=1), wait_for="tr.thread")
        if is_logged_in(b.page):
            save_session(b.ctx)
            print("Already logged in (uid %s) - session saved to %s"
                  % (logged_in_uid(b.page.content()), STATE_JSON))
            return 0
        print("\nNot logged in.  A browser window is open on bbs.kanxue.com:")
        print("  click 登录, sign in (finish any captcha / JS challenge) - that's it.")
        print("  This waits up to %ds and exits by itself once the session appears.\n"
              % args.wait)
        deadline = time.time() + args.wait
        ok = False
        while time.time() < deadline:
            time.sleep(3)
            try:
                ok = is_logged_in(b.page)
            except PWError:
                continue          # page mid-navigation
            if ok:
                break
            left = int(deadline - time.time())
            if left % 30 < 3:
                print("  ... still waiting for login (%ds left)" % left)
                sys.stdout.flush()
        if ok:
            goto(b.page, LIST_URL.format(fid=FORUM_ID, page=1), wait_for="tr.thread")
            ok = is_logged_in(b.page)
            if ok:
                save_session(b.ctx)
                print("login OK (uid %s).  Session saved to %s"
                      % (logged_in_uid(b.page.content()), STATE_JSON))
                return 0
        print("login NOT detected - the page still reports uid 0.  Nothing was saved.")
        return 1


def cmd_urls(args):
    ensure_dirs()
    with Browser(headless=args.headless) as b:
        threads = collect_urls(b.page, cutoff=args.cutoff, max_pages=args.max_pages,
                               min_replies=args.min_replies)
    save_json(URLS_JSON, {
        "board": BOARD_NAME, "forum_id": FORUM_ID, "digest_only": False,
        "min_replies": args.min_replies,
        "cutoff": args.cutoff.isoformat(), "collected_at": now_iso(),
        "count": len(threads), "threads": threads,
    })
    print("\ncollected %d threads >= %s -> %s" % (len(threads), args.cutoff, URLS_JSON))
    return 0


def cmd_fetch(args):
    ensure_dirs()
    data = load_json(URLS_JSON, None)
    if not data:
        print("no %s - run `crawl.py urls` first." % URLS_JSON)
        return 1
    threads = data["threads"]

    done = load_json(DONE_JSON, {})
    failed = load_json(FAILED_JSON, {})
    locked = load_json(LOCKED_JSON, {})

    def wanted(tid):
        """Should this run attempt `tid`?

        A CaptchaRequired is no longer a permanent verdict.  Entries recorded before
        tools/slider-cv existed - or on a run where it came up short - are *stale*, not
        dead, and nothing else would ever revisit them: `fetch` skips everything already
        in failed.json, so they would sit there forever.  Retry them by default, bounded
        by an attempt count so that a genuinely broken solver cannot make every run
        re-walk the same threads.  Every other failure kind keeps the old behaviour and
        waits for an explicit --retry-failed.
        """
        if tid in done or tid in locked:
            return False
        entry = failed.get(tid)
        if entry is None:
            return True
        if args.retry_failed:
            return True
        if not (CAPTCHA_AUTOSOLVE and "CaptchaRequired" in (entry.get("error") or "")):
            return False
        return int(entry.get("attempts", 1)) < args.captcha_retry_max

    todo = [t for t in threads if wanted(str(t["tid"]))]
    skipped = len(threads) - len(todo)
    n_recover = sum(1 for t in todo if str(t["tid"]) in failed)
    if args.limit:
        todo = todo[:args.limit]

    print("%d threads total | %d already done/locked/failed | fetching %d%s"
          % (len(threads), skipped, len(todo),
             (" (%d retrying a previous 安全验证)" % n_recover) if n_recover else ""))
    if not todo:
        return 0

    n_ok = n_fail = n_lock = 0
    with Browser(headless=args.headless) as b:
        goto(b.page, LIST_URL.format(fid=FORUM_ID, page=1), wait_for="tr.thread")
        if not is_logged_in(b.page):
            print("\nNot logged in.  Run `python crawl.py login` first "
                  "(locked/truncated bodies otherwise).")
            return 1

        for meta in tqdm(todo, desc="threads", unit="t"):
            tid = str(meta["tid"])
            try:
                result, lock_reason = with_retry(
                    lambda: fetch_thread(b.page, meta,
                                         with_replies=not args.no_replies,
                                         max_reply_pages=args.max_reply_pages),
                    what="tid %s" % tid)
                if result is None:
                    locked[tid] = {"url": meta["url"], "title": meta.get("title", ""),
                                   "reason": lock_reason, "seen_at": now_iso()}
                    save_json(LOCKED_JSON, locked)
                    n_lock += 1
                    tqdm.write("  locked (回复可见): %s  [%s]" % (meta["url"], lock_reason))
                else:
                    fm, body = result
                    fname = "%s-%s.md" % (tid, slugify(fm["title"]))
                    path = os.path.join(ARTICLES_DIR, fname)
                    post = frontmatter.Post(body, **fm)
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(frontmatter.dumps(post, sort_keys=False,
                                                   allow_unicode=True,
                                                   default_flow_style=None,
                                                   width=10_000))
                        fh.write("\n")
                    done[tid] = {"file": os.path.relpath(path, OUT_DIR),
                                 "title": fm["title"], "date": fm["date"],
                                 "replies": fm["replies"], "crawled_at": fm["crawled_at"]}
                    save_json(DONE_JSON, done)
                    failed.pop(tid, None)
                    n_ok += 1
            except LoginRequired as exc:
                print("\n! %s\n! stopping; run `python crawl.py login` and resume." % exc)
                break
            except CaptchaRequired as exc:
                # Count attempts so `wanted()` can retry this a bounded number of times
                # on later runs instead of either stranding it or looping on it forever.
                attempts = int((failed.get(tid) or {}).get("attempts", 0)) + 1
                failed[tid] = {"url": meta["url"], "error": "CaptchaRequired: %s" % exc,
                               "at": now_iso(), "attempts": attempts}
                save_json(FAILED_JSON, failed)
                n_fail += 1
                if not CAPTCHA_INTERACTIVE:
                    print("\n! 安全验证 slider at %s survived %d auto-solve attempts and\n"
                          "! this run is headless, so there is no human to hand it to.\n"
                          "! Check tools/slider-cv (--captcha-debug-dir shows what it saw),\n"
                          "! or rerun without --headless and then `--retry-failed`."
                          % (exc, CAPTCHA_ATTEMPTS))
                    break
                tqdm.write("  captcha not cleared in time: %s" % exc)
            except KeyboardInterrupt:
                print("\ninterrupted - state saved, rerun to resume.")
                break
            except Exception as exc:  # noqa: BLE001 - keep the crawl alive
                failed[tid] = {"url": meta["url"], "error": "%s: %s" % (type(exc).__name__, exc),
                               "at": now_iso()}
                save_json(FAILED_JSON, failed)
                n_fail += 1
                tqdm.write("  FAILED %s: %s" % (meta["url"], str(exc)[:160]))
            nap(SLEEP_THREAD)
        save_session(b.ctx)          # keep rotating cookies fresh for the next run

    save_json(DONE_JSON, done)
    save_json(FAILED_JSON, failed)
    save_json(LOCKED_JSON, locked)
    print("\n--- summary ---")
    print("success : %d (this run)   total done: %d" % (n_ok, len(done)))
    print("failed  : %d (this run)   total failed: %d" % (n_fail, len(failed)))
    print("locked  : %d (this run)   total locked: %d" % (n_lock, len(locked)))
    print("skipped : %d (already in done/locked/failed)" % skipped)
    print("articles-> %s" % ARTICLES_DIR)
    return 0


def already_liked(page):
    return page.locator("#collection_thumb i.icon-thumbs-up").count() > 0


def like_thread(page):
    """Click 点赞 on the current thread with golds=0.

    kanxue's 赞 button opens a 赞赏 modal that can also tip 雪币; we force the amount to
    0 so this is a plain like with the site's own canned 「为你点赞！」 note.  It adds no
    reply floor and does not bump the thread.
    """
    if already_liked(page):
        return True
    btn = page.locator("#collection_thumb a.thumbsBox")
    if btn.count() == 0:
        return False
    btn.first.scroll_into_view_if_needed()
    btn.first.click()
    page.wait_for_selector("#thumbModal.show", timeout=15_000)
    page.fill("#thumb-xb", "0")                     # never spend the user's 雪币
    amount = page.input_value("#thumb-xb")
    if amount.strip() not in ("0", ""):
        raise RuntimeError("refusing to like: 雪币 field is %r, not 0" % amount)
    page.click("#thumbModal .thumbPost")
    try:
        page.wait_for_selector("#thumbModal.show", state="hidden", timeout=15_000)
    except PWTimeout:
        return False
    page.wait_for_timeout(500)
    return True


def cmd_unlock(args):
    """点赞 each 回复可见 thread so its body opens, then fetch it normally."""
    ensure_dirs()
    locked = load_json(LOCKED_JSON, {})
    done = load_json(DONE_JSON, {})
    failed = load_json(FAILED_JSON, {})
    by_tid = {str(t["tid"]): t for t in (load_json(URLS_JSON, {}) or {}).get("threads", [])}

    todo = [t for t in sorted(locked, key=int, reverse=True) if t not in done]
    if args.limit:
        todo = todo[:args.limit]
    print("%d locked threads | unlocking %d by 点赞 (0 雪币, no reply posted)"
          % (len(locked), len(todo)))
    if not todo:
        return 0

    n_ok = n_still = n_fail = 0
    with Browser(headless=args.headless) as b:
        goto(b.page, LIST_URL.format(fid=FORUM_ID, page=1), wait_for="tr.thread")
        if not is_logged_in(b.page):
            print("\nNot logged in.  Run `python crawl.py login` first.")
            return 1

        for tid in tqdm(todo, desc="unlock", unit="t"):
            meta = by_tid.get(tid) or {"tid": int(tid), "url": THREAD_URL.format(tid=tid),
                                       "title": locked[tid].get("title", ""), "date": None,
                                       "author": ""}
            try:
                goto(b.page, meta["url"], wait_for="div.message")
                liked = like_thread(b.page)
                result, reason = with_retry(
                    lambda: fetch_thread(b.page, meta,
                                         with_replies=not args.no_replies,
                                         max_reply_pages=args.max_reply_pages),
                    what="tid %s" % tid)
                if result is None:
                    locked[tid]["reason"] = reason
                    locked[tid]["liked"] = liked
                    locked[tid]["retried_at"] = now_iso()
                    n_still += 1
                    tqdm.write("  still locked after 点赞(%s): %s" % (liked, meta["url"]))
                else:
                    fm, body = result
                    path = os.path.join(ARTICLES_DIR,
                                        "%s-%s.md" % (tid, slugify(fm["title"])))
                    post = frontmatter.Post(body, **fm)
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(frontmatter.dumps(post, sort_keys=False, allow_unicode=True,
                                                   default_flow_style=None, width=10_000))
                        fh.write("\n")
                    done[tid] = {"file": os.path.relpath(path, OUT_DIR), "title": fm["title"],
                                 "date": fm["date"], "replies": fm["replies"],
                                 "crawled_at": fm["crawled_at"], "unlocked_by": "点赞"}
                    locked.pop(tid, None)
                    n_ok += 1
                save_json(DONE_JSON, done)
                save_json(LOCKED_JSON, locked)
            except LoginRequired as exc:
                print("\n! %s\n! stopping; run `python crawl.py login` and resume." % exc)
                break
            except KeyboardInterrupt:
                print("\ninterrupted - state saved, rerun to resume.")
                break
            except Exception as exc:  # noqa: BLE001
                failed[tid] = {"url": meta["url"], "error": "%s: %s" % (type(exc).__name__, exc),
                               "at": now_iso()}
                save_json(FAILED_JSON, failed)
                n_fail += 1
                tqdm.write("  FAILED %s: %s" % (meta["url"], str(exc)[:160]))
            nap(SLEEP_THREAD)
        save_session(b.ctx)

    print("\n--- unlock summary ---")
    print("unlocked+saved : %d" % n_ok)
    print("still locked   : %d" % n_still)
    print("errored        : %d" % n_fail)
    return 0


def cmd_dry_run(args):
    args.limit = args.limit or 10
    rc = cmd_urls(args)
    if rc:
        return rc
    return cmd_fetch(args)


def cmd_all(args):
    rc = cmd_urls(args)
    if rc:
        return rc
    return cmd_fetch(args)


def parse_args(argv):
    global CAPTCHA_WAIT_S, CAPTCHA_INTERACTIVE, CAPTCHA_AUTOSOLVE
    global CAPTCHA_ATTEMPTS, CAPTCHA_DEBUG_DIR
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command",
                   choices=["login", "urls", "fetch", "unlock", "dry-run", "all", "robots"])
    p.add_argument("--limit", type=int, default=0, help="max threads to fetch this run")
    p.add_argument("--max-pages", type=int, default=200, help="max list pages to walk")
    p.add_argument("--min-replies", type=int, default=MIN_REPLIES,
                   help="only keep threads with at least this many replies "
                        "(default %d, i.e. more than 10; 0 disables)" % MIN_REPLIES)
    p.add_argument("--max-reply-pages", type=int, default=0,
                   help="cap reply pages per thread (0 = all; truncation is noted in the file)")
    p.add_argument("--no-replies", action="store_true", help="OP only, skip replies")
    p.add_argument("--headless", action="store_true", help="run without a visible window")
    p.add_argument("--retry-failed", action="store_true",
                   help="re-attempt every tid in failed.json, whatever the reason")
    p.add_argument("--captcha-retry-max", type=int, default=3,
                   help="how many times a 安全验证 failure is re-attempted on later runs "
                        "before it needs an explicit --retry-failed (default 3, 0 disables)")
    p.add_argument("--cutoff", default=CUTOFF_DATE.isoformat(), help="YYYY-MM-DD (default 2023-01-01)")
    p.add_argument("--cookies", help="login: import a cookie export (JSON) into the profile")
    p.add_argument("--wait", type=int, default=420,
                   help="login: seconds to wait for you to finish signing in")
    p.add_argument("--captcha-wait", type=int, default=CAPTCHA_WAIT_S,
                   help="seconds to pause so you can clear a 安全验证 page (headed runs)")
    p.add_argument("--no-auto-captcha", action="store_true",
                   help="do not try to clear the 安全验证 slider with tools/slider-cv")
    p.add_argument("--captcha-attempts", type=int, default=CAPTCHA_ATTEMPTS,
                   help="slider attempts per interstitial (default %d)" % CAPTCHA_ATTEMPTS)
    p.add_argument("--captcha-debug-dir",
                   help="dump each slider attempt's images + annotated overlay here")
    p.add_argument("--ignore-robots", action="store_true")
    a = p.parse_args(argv)
    a.cutoff = datetime.strptime(a.cutoff, "%Y-%m-%d").date()
    CAPTCHA_WAIT_S = a.captcha_wait
    CAPTCHA_INTERACTIVE = not a.headless      # only a headed run can hand off to a human
    CAPTCHA_AUTOSOLVE = not a.no_auto_captcha
    CAPTCHA_ATTEMPTS = a.captcha_attempts
    CAPTCHA_DEBUG_DIR = a.captcha_debug_dir
    return a


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "robots":
        return 0 if check_robots() else 2
    if not args.ignore_robots and not check_robots(verbose=(args.command != "fetch")):
        print("Stopping: robots.txt disallows this path.  (--ignore-robots to override)")
        return 2
    return {
        "login": cmd_login, "urls": cmd_urls, "fetch": cmd_fetch,
        "unlock": cmd_unlock, "dry-run": cmd_dry_run, "all": cmd_all,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
