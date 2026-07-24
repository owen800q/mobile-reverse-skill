#!/usr/bin/env python3
"""P1 static API extraction for an Android reverse-engineering skill (LOGIN-focused).

Scans a jadx / decompiled source tree (.java / .kt / .smali) for HTTP client
usage (Retrofit, OkHttp, Volley, HttpURLConnection, WebView), hardcoded URLs,
and secret / signing hints. Login/auth-related hits are ranked and boosted to
the top as "login candidates".

Adapted and merged from:
  - endpoint_extractor.py (fausto-ai-mobile)
  - secret_scanner.py (fausto-ai-mobile)
  - api-extraction-patterns.md (creditone-android-re)

Stdlib only. No network access.

Usage:
    api_extract.py <jadx_src_dir> [--out DIR] [--keyword login,auth,sign]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

SCAN_EXTENSIONS = {".java", ".kt", ".kts", ".smali"}
EXCLUDE_DIRS = {".git", "__pycache__", ".idea", "build", "dist", "out", "node_modules"}
DEFAULT_MAX_SIZE_KB = 4096
CONTEXT_BEFORE = 3
CONTEXT_AFTER = 3
MAX_URLS_PER_FILE = 500
MAX_SECRETS_PER_FILE = 300
MAX_LOGIN_CANDIDATES = 400

# Keywords that promote a hit into the "login candidate" bucket. The user's
# --keyword list is unioned with this built-in ranking set.
RANK_KEYWORDS = {
    "login", "logon", "signin", "sign-in", "signup", "auth", "authenticate",
    "authorization", "oauth", "session", "token", "sign", "signature", "credential",
    "password", "passwd", "account", "otp",
}
# Strong signals: heavily boost the score when present.
STRONG_KEYWORDS = {"login", "logon", "signin", "sign-in", "oauth", "authenticate"}

# --------------------------------------------------------------------------- #
# Regexes
# --------------------------------------------------------------------------- #

# Retrofit HTTP method annotations (Java / Kotlin). Case-sensitive to avoid
# matching stray words like "post"/"head".
RE_HTTP_ANN = re.compile(r"@(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|HTTP)\b")
RE_QUOTED = re.compile(r"""["']([^"']*)["']""")
RE_HTTP_METHOD_KW = re.compile(r"""method\s*=\s*["']([A-Za-z]+)["']""")
RE_HTTP_PATH_KW = re.compile(r"""path\s*=\s*["']([^"']*)["']""")

# Retrofit parameter / header annotations (Java / Kotlin).
RE_PARAM_ANN = re.compile(
    r"@(Query|QueryMap|Path|Body|Field|FieldMap|Part|PartMap|Header|HeaderMap|Url)\b"
)
RE_HEADERS_ANN = re.compile(r"@Headers\b")
RE_BASEURL = re.compile(r"\.baseUrl\s*\(")

# Retrofit annotations in smali form (Lretrofit2/http/GET; etc.).
RE_SMALI_HTTP = re.compile(r"Lretrofit2/http/(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|HTTP);")
RE_SMALI_PARAM = re.compile(
    r"Lretrofit2/http/(Query|QueryMap|Path|Body|Field|FieldMap|Part|PartMap|Header|HeaderMap|Url|Headers);"
)
RE_SMALI_VALUE = re.compile(r'value\s*=\s*"([^"]*)"')

# OkHttp signals.
RE_OKHTTP = re.compile(
    r"(Request\s*\.\s*Builder|\.\s*newCall\s*\(|\.\s*enqueue\s*\(|\.\s*execute\s*\(|\.\s*url\s*\()"
)
RE_INTERCEPTOR = re.compile(
    r"(addNetworkInterceptor\s*\(|addInterceptor\s*\(|\bintercept\s*\()"
)

# Volley signals.
RE_VOLLEY = re.compile(r"\b(StringRequest|JsonObjectRequest|JsonArrayRequest|RequestQueue)\b")

# HttpURLConnection signals.
RE_HURL = re.compile(r"\b(openConnection|setRequestMethod|setRequestProperty)\b")

# WebView signals.
RE_WEBVIEW = re.compile(
    r"(\bloadUrl\s*\(|\bevaluateJavascript\s*\(|\baddJavascriptInterface\s*\(|@JavascriptInterface\b)"
)

# Hardcoded URLs and base-url constants.
RE_URL = re.compile(r"https?://[^\s\"'<>\\)]+", re.IGNORECASE)
RE_BASE_CONST = re.compile(
    r"\b(BASE_URL|API_URL|API_BASE|BASE_API|SERVER_URL|HOST_URL|ENDPOINT|API_HOST|API_ENDPOINT)\b"
)

# Secret / signing-hint rules: (type, compiled_regex).
SECRET_RULES = [
    ("api_key", re.compile(r"(?i)api[_-]?key")),
    ("bearer", re.compile(r"(?i)\bbearer\b")),
    ("access_token", re.compile(r"(?i)access[_-]?token")),
    ("client_secret", re.compile(r"(?i)client[_-]?secret")),
    ("signing_hint:sign", re.compile(r"(?i)\bsign\b")),
    ("signing_hint:signature", re.compile(r"(?i)signature")),
    ("signing_hint:hmac", re.compile(r"(?i)\bhmac\b")),
    ("signing_hint:aes", re.compile(r"(?i)\baes\b")),
    ("signing_hint:encrypt", re.compile(r"(?i)encrypt")),
    ("signing_hint:x-sign", re.compile(r"(?i)x-sign")),
]

# Trailing junk to trim off captured URL / path literals.
_URL_TRAILERS = "\"'`),;>}]\\ "


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Static API/login extraction from a jadx/decompiled source tree.",
    )
    parser.add_argument("src", help="jadx source directory (decompiled .java/.kt/.smali tree)")
    parser.add_argument("--out", default="./re_out", help="Output directory (default: ./re_out)")
    parser.add_argument(
        "--keyword",
        default="login,auth,sign",
        help="Comma-separated login/auth keywords to boost (default: login,auth,sign)",
    )
    parser.add_argument(
        "--max-size-kb",
        type=int,
        default=DEFAULT_MAX_SIZE_KB,
        help="Skip files larger than this many KB (default: %(default)s)",
    )
    return parser.parse_args()


def build_keywords(raw: str) -> list:
    user = {k.strip().lower() for k in (raw or "").split(",") if k.strip()}
    return sorted(RANK_KEYWORDS | user)


def is_excluded_dir(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    return any(part in EXCLUDE_DIRS for part in parts)


def read_text(path: Path, max_bytes: int):
    """Read a text file, skipping binaries and capping bytes. Returns None to skip."""
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > max_bytes:
        return None
    try:
        with path.open("rb") as handle:
            chunk = handle.read(max_bytes)
    except OSError:
        return None
    if b"\x00" in chunk[:8192]:  # crude binary guard
        return None
    return chunk.decode("utf-8", errors="ignore")


def clean_literal(value: str) -> str:
    return value.strip().strip(_URL_TRAILERS).strip()


def snippet(line: str, limit: int = 200) -> str:
    text = " ".join(line.split())
    return text[:limit]


def context_text(lines, idx: int, rel_path: str) -> str:
    """Lowercased context window (plus the file path) used for keyword scoring."""
    start = max(0, idx - CONTEXT_BEFORE)
    end = min(len(lines), idx + CONTEXT_AFTER + 1)
    joined = " ".join(lines[start:end])
    return (rel_path + " " + joined).lower()


def keyword_hits(text: str, keywords) -> list:
    low = text.lower()
    return sorted({k for k in keywords if k in low})


def score_candidate(primary: str, context: str, keywords) -> tuple:
    """Return (score, matched_keywords). Path/primary matches weigh more."""
    primary_hits = set(keyword_hits(primary, keywords))
    context_hits = set(keyword_hits(context, keywords))
    all_hits = primary_hits | context_hits
    if not all_hits:
        return 0, []
    score = len(primary_hits) * 3 + len(context_hits - primary_hits)
    if primary_hits & STRONG_KEYWORDS:
        score += 5
    elif context_hits & STRONG_KEYWORDS:
        score += 2
    return score, sorted(all_hits)


# --------------------------------------------------------------------------- #
# Endpoint annotation gathering
# --------------------------------------------------------------------------- #


def gather_retrofit_annotations(lines, idx: int, is_smali: bool) -> list:
    """Collect Retrofit param/header annotation names attached to an endpoint."""
    anns = set()
    if is_smali:
        end = min(len(lines), idx + 400)
        for j in range(idx, end):
            line = lines[j]
            if j > idx and ".end method" in line:
                break
            m = RE_SMALI_PARAM.search(line)
            if m:
                anns.add(m.group(1))
    else:
        # @Headers may sit just above the HTTP annotation.
        for j in range(max(0, idx - 3), idx):
            if RE_HEADERS_ANN.search(lines[j]):
                anns.add("Headers")
        end = min(len(lines), idx + 15)
        for j in range(idx, end):
            line = lines[j]
            if RE_HEADERS_ANN.search(line):
                anns.add("Headers")
            for m in RE_PARAM_ANN.finditer(line):
                anns.add(m.group(1))
            if j > idx and ("{" in line or line.rstrip().endswith(";")):
                break
    return sorted(anns)


def smali_endpoint_path(lines, idx: int) -> str:
    for j in range(idx, min(len(lines), idx + 6)):
        m = RE_SMALI_VALUE.search(lines[j])
        if m:
            return m.group(1)
    return ""


# --------------------------------------------------------------------------- #
# Per-file scan
# --------------------------------------------------------------------------- #


def scan_file(path: Path, rel_path: str, text: str, keywords, store: dict) -> None:
    lines = text.splitlines()
    is_smali = path.suffix.lower() == ".smali"

    endpoints = store["endpoints"]
    interceptors = store["interceptors"]
    hardcoded_urls = store["hardcoded_urls"]
    network_calls = store["network_calls"]
    secrets = store["secrets"]
    candidates = store["_candidates"]
    url_seen = store["_url_seen"]

    file_url_count = 0
    file_secret_count = 0

    def add_candidate(line_no: int, primary: str, source: str, library, method, path_value):
        ctx = context_text(lines, line_no - 1, rel_path)
        score, matched = score_candidate(primary, ctx, keywords)
        if score <= 0:
            return
        candidates.append(
            {
                "file": rel_path,
                "line": line_no,
                "score": score,
                "source": source,
                "library": library,
                "method": method,
                "path": path_value,
                "keywords": matched,
                "snippet": snippet(lines[line_no - 1]),
            }
        )

    for idx, line in enumerate(lines):
        line_no = idx + 1

        # ---- Retrofit endpoints ------------------------------------------- #
        if is_smali:
            m = RE_SMALI_HTTP.search(line)
            if m:
                method = m.group(1)
                path_value = smali_endpoint_path(lines, idx)
                anns = gather_retrofit_annotations(lines, idx, True)
                endpoints.append(
                    {
                        "method": method,
                        "path": path_value,
                        "file": rel_path,
                        "line": line_no,
                        "annotations": anns,
                        "library": "retrofit",
                    }
                )
                add_candidate(line_no, method + " " + path_value, "endpoint", "retrofit", method, path_value)
        else:
            m = RE_HTTP_ANN.search(line)
            if m:
                method = m.group(1)
                path_value = ""
                rest = line[m.end():]
                if method == "HTTP":
                    mk = RE_HTTP_METHOD_KW.search(line)
                    if mk:
                        method = mk.group(1).upper()
                    pk = RE_HTTP_PATH_KW.search(line)
                    if pk:
                        path_value = pk.group(1)
                    else:
                        q = RE_QUOTED.search(rest)
                        if q:
                            path_value = q.group(1)
                else:
                    q = RE_QUOTED.search(rest)
                    if q:
                        path_value = q.group(1)
                anns = gather_retrofit_annotations(lines, idx, False)
                endpoints.append(
                    {
                        "method": method,
                        "path": path_value,
                        "file": rel_path,
                        "line": line_no,
                        "annotations": anns,
                        "library": "retrofit",
                    }
                )
                add_candidate(line_no, method + " " + path_value, "endpoint", "retrofit", method, path_value)

        # ---- Retrofit .baseUrl( ------------------------------------------- #
        if RE_BASEURL.search(line):
            network_calls.append(
                {"library": "retrofit", "signal": "baseUrl(", "file": rel_path,
                 "line": line_no, "text": snippet(line)}
            )

        # ---- OkHttp ------------------------------------------------------- #
        for m in RE_OKHTTP.finditer(line):
            sig = m.group(0).replace(" ", "")
            network_calls.append(
                {"library": "okhttp", "signal": sig, "file": rel_path,
                 "line": line_no, "text": snippet(line)}
            )
            add_candidate(line_no, sig + " " + line, "network_call", "okhttp", None, None)

        # ---- Interceptors ------------------------------------------------- #
        for m in RE_INTERCEPTOR.finditer(line):
            sig = m.group(0).replace(" ", "")
            interceptors.append(
                {"library": "okhttp", "signal": sig, "file": rel_path,
                 "line": line_no, "text": snippet(line)}
            )
            add_candidate(line_no, sig + " " + line, "interceptor", "okhttp", None, None)

        # ---- Volley ------------------------------------------------------- #
        for m in RE_VOLLEY.finditer(line):
            network_calls.append(
                {"library": "volley", "signal": m.group(1), "file": rel_path,
                 "line": line_no, "text": snippet(line)}
            )
            add_candidate(line_no, m.group(1) + " " + line, "network_call", "volley", None, None)

        # ---- HttpURLConnection ------------------------------------------- #
        for m in RE_HURL.finditer(line):
            network_calls.append(
                {"library": "httpurlconnection", "signal": m.group(1), "file": rel_path,
                 "line": line_no, "text": snippet(line)}
            )
            add_candidate(line_no, m.group(1) + " " + line, "network_call", "httpurlconnection", None, None)

        # ---- WebView ------------------------------------------------------ #
        for m in RE_WEBVIEW.finditer(line):
            sig = m.group(0).replace(" ", "")
            network_calls.append(
                {"library": "webview", "signal": sig, "file": rel_path,
                 "line": line_no, "text": snippet(line)}
            )
            add_candidate(line_no, sig + " " + line, "network_call", "webview", None, None)

        # ---- Hardcoded URLs ----------------------------------------------- #
        for m in RE_URL.finditer(line):
            value = clean_literal(m.group(0))
            if not value:
                continue
            key = (rel_path, line_no, value)
            if key in url_seen:
                continue
            url_seen.add(key)
            if file_url_count < MAX_URLS_PER_FILE:
                hardcoded_urls.append(
                    {"value": value, "file": rel_path, "line": line_no, "kind": "url"}
                )
                file_url_count += 1
                add_candidate(line_no, value, "hardcoded_url", None, None, value)

        # ---- Base URL constants ------------------------------------------- #
        if RE_BASE_CONST.search(line):
            q = RE_QUOTED.search(line)
            value = clean_literal(q.group(1)) if q else snippet(line)
            hardcoded_urls.append(
                {"value": value, "file": rel_path, "line": line_no, "kind": "base_const"}
            )
            add_candidate(line_no, value + " " + line, "base_const", None, None, value)

        # ---- Secrets / signing hints -------------------------------------- #
        if file_secret_count < MAX_SECRETS_PER_FILE:
            for sec_type, regex in SECRET_RULES:
                if regex.search(line):
                    q = RE_QUOTED.search(line)
                    preview = clean_literal(q.group(1)) if q else snippet(line)
                    if len(preview) > 120:
                        preview = preview[:60] + "..." + preview[-20:]
                    secrets.append(
                        {"type": sec_type, "value_preview": preview,
                         "file": rel_path, "line": line_no}
                    )
                    file_secret_count += 1
                    if file_secret_count >= MAX_SECRETS_PER_FILE:
                        break


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def dedup_login_candidates(candidates: list) -> list:
    """Keep the highest-scoring candidate per (file, line)."""
    best = {}
    for cand in candidates:
        key = (cand["file"], cand["line"])
        current = best.get(key)
        if current is None or cand["score"] > current["score"]:
            best[key] = cand
    ranked = sorted(
        best.values(),
        key=lambda c: (-c["score"], c["file"], c["line"]),
    )
    return ranked


def collect_files(src: Path, max_size_kb: int):
    max_bytes = max_size_kb * 1024
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        rel_path = str(path.relative_to(src))
        if is_excluded_dir(rel_path):
            continue
        text = read_text(path, max_bytes)
        if text is None or not text.strip():
            continue
        yield path, rel_path, text


def main() -> int:
    args = parse_args()
    src = Path(args.src).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()

    if not src.is_dir():
        sys.stderr.write("error: source directory not found: %s\n" % src)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    keywords = build_keywords(args.keyword)

    store = {
        "endpoints": [],
        "interceptors": [],
        "hardcoded_urls": [],
        "network_calls": [],
        "secrets": [],
        "_candidates": [],
        "_url_seen": set(),
    }

    scanned = 0
    for path, rel_path, text in collect_files(src, args.max_size_kb):
        scanned += 1
        scan_file(path, rel_path, text, keywords, store)

    login_candidates = dedup_login_candidates(store["_candidates"])[:MAX_LOGIN_CANDIDATES]

    lib_counter = Counter(nc["library"] for nc in store["network_calls"])
    meta = {
        "tool": "api_extract.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "src_dir": str(src),
        "keywords": keywords,
        "max_size_kb": args.max_size_kb,
        "files_scanned": scanned,
        "counts": {
            "endpoints": len(store["endpoints"]),
            "interceptors": len(store["interceptors"]),
            "hardcoded_urls": len(store["hardcoded_urls"]),
            "network_calls": len(store["network_calls"]),
            "login_candidates": len(login_candidates),
            "secrets": len(store["secrets"]),
        },
        "network_libraries": dict(lib_counter),
    }

    api_out = {
        "meta": meta,
        "endpoints": store["endpoints"],
        "interceptors": store["interceptors"],
        "hardcoded_urls": store["hardcoded_urls"],
        "network_calls": store["network_calls"],
        "login_candidates": login_candidates,
    }
    secrets_out = {
        "meta": {
            "tool": "api_extract.py",
            "generated_at": meta["generated_at"],
            "src_dir": str(src),
            "total": len(store["secrets"]),
        },
        "secrets": store["secrets"],
    }

    api_path = out / "api_endpoints.json"
    secrets_path = out / "secrets.json"
    api_path.write_text(json.dumps(api_out, ensure_ascii=False, indent=2), encoding="utf-8")
    secrets_path.write_text(json.dumps(secrets_out, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Report top login candidates to stderr ---------------------------- #
    sys.stderr.write("api_extract.py: scanned %d files\n" % scanned)
    sys.stderr.write(
        "endpoints=%d  interceptors=%d  urls=%d  network=%d  secrets=%d  login_candidates=%d\n"
        % (
            len(store["endpoints"]),
            len(store["interceptors"]),
            len(store["hardcoded_urls"]),
            len(store["network_calls"]),
            len(store["secrets"]),
            len(login_candidates),
        )
    )
    sys.stderr.write("--- top login candidates ---\n")
    if not login_candidates:
        sys.stderr.write("(none matched login/auth keywords)\n")
    for cand in login_candidates[:10]:
        sys.stderr.write(
            "[score %d] %s:%d  %s\n    %s\n"
            % (cand["score"], cand["file"], cand["line"],
               ",".join(cand["keywords"]) or "-", cand["snippet"])
        )

    # stdout: machine-friendly paths to the two output files.
    print(str(api_path))
    print(str(secrets_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
