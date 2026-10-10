#!/usr/bin/env python3
"""ios_container.py — iP2 passive scan of a PlayCover app's on-disk container.

The cheap, attach-free first look for iOS mode: before running Frida, read what
the app has already persisted. Three sources (all app/version-dependent and
frequently empty — hedge accordingly):

  1. NSURLCache `Cache.db` (SQLite, CFURLCache schema) — cached HTTP responses.
     What is reliably recoverable: the request URL and timestamps. Headers/bodies
     live in archived (NSKeyedArchiver) blobs and are best-effort here; RESPONSE
     bodies may sit on disk in `fsCachedData/` (referenced when isDataOnFS=1);
     REQUEST bodies are essentially absent (only cacheable GETs are stored).
  2. PlayKeychain — PlayCover's on-disk keychain shim. Readable plists ONLY when
     PlayCover's PlayKeychain toggle is enabled; otherwise items are in the macOS
     login keychain (use `security find-generic-password`). We list what's on disk.
  3. NSUserDefaults plist — Preferences/<bundleID>.plist (tokens, flags, config).

Locates the install by glob (paths drift across PlayCover versions) and, on a
Mac, notes the running pid/binary. Emits <out>/ios_container.json and appends
requests.json-compatible records to <out>/requests.json for the ledger.

Usage:
    ios_container.py [--bundle-id ID] [--app-dir DIR] [--container DIR] [--out DIR]

stdlib-only; no network. Prints a human summary to stderr, JSON to stdout.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import plistlib
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


HOME = Path(os.path.expanduser("~"))

# PlayCover install roots have moved across versions — glob all known shapes.
APP_ROOTS = [
    HOME / "Library/Containers/io.playcover.PlayCover/Applications",
    HOME / "Library/Application Support/PlayCover/Applications",
    HOME / "Library/Containers/io.playcover.PlayCover/Data/Applications",
]

SIG_KEY_RE = re.compile(
    r"(?i)^(authorization|x-?sign(ature)?|sign|signature|token|"
    r"access[-_]?token|refresh[-_]?token|nonce|timestamp|ts)$"
)
HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")


def log(*a):
    print(*a, file=sys.stderr)


# --- location -------------------------------------------------------------
def find_app_dir(bundle_id: str | None) -> str | None:
    for root in APP_ROOTS:
        if not root.is_dir():
            continue
        for app in sorted(root.glob("*.app")):
            if bundle_id is None:
                return str(app)
            info = app / "Info.plist"
            if info.is_file():
                try:
                    with open(info, "rb") as fh:
                        d = plistlib.load(fh)
                    if d.get("CFBundleIdentifier") == bundle_id:
                        return str(app)
                except Exception:
                    pass
    return None


def bundle_id_of(app_dir: str) -> str | None:
    info = Path(app_dir) / "Info.plist"
    if info.is_file():
        try:
            with open(info, "rb") as fh:
                return plistlib.load(fh).get("CFBundleIdentifier")
        except Exception:
            return None
    return None


def find_container(bundle_id: str) -> str | None:
    cand = HOME / "Library/Containers" / bundle_id / "Data"
    return str(cand) if cand.is_dir() else None


def running_process(exec_hint: str | None) -> dict:
    """Best-effort pid/binary lookup (macOS). Empty off-Mac or if not running."""
    if not exec_hint or sys.platform != "darwin":
        return {}
    try:
        out = subprocess.run(
            ["pgrep", "-fl", exec_hint], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if out:
            pid = out.split()[0]
            return {"pid": int(pid), "ps": out}
    except Exception:
        pass
    return {}


# --- NSKeyedArchiver best-effort walk -------------------------------------
# NSKeyedArchiver blobs are parsed with plistlib before anything is checked, so bound
# them first: a size cap, an object-count cap, and a per-dictionary pair cap.
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_OBJECTS = 100_000
MAX_PAIRS_PER_DICT = 1_000


def _load_archive(blob: bytes):
    """Parse an archive blob, or return None when it is oversized or malformed."""
    if len(blob) > MAX_ARCHIVE_BYTES:
        return None
    try:
        arch = plistlib.loads(blob)
    except Exception:
        return None
    return arch if isinstance(arch, dict) else None


def _deref(objs, u):
    if isinstance(u, plistlib.UID):
        try:
            return objs[u.data]
        except Exception:
            return None
    return u


def archive_headers(blob: bytes) -> dict:
    """Pull an HTTP-header-looking dict out of an NSKeyedArchiver blob.

    Best-effort only: returns {} when the archive can't be decoded or no header
    map is found (very common). Never raises.
    """
    arch = _load_archive(blob)
    objs = arch.get("$objects") if arch else None
    if not isinstance(objs, list) or len(objs) > MAX_ARCHIVE_OBJECTS:
        return {}
    best = {}
    for o in objs:
        if not (isinstance(o, dict) and "NS.keys" in o and "NS.objects" in o):
            continue
        if not isinstance(o["NS.keys"], list) or not isinstance(o["NS.objects"], list):
            continue
        try:
            keys = [_deref(objs, k) for k in o["NS.keys"][:MAX_PAIRS_PER_DICT]]
            vals = [_deref(objs, v) for v in o["NS.objects"][:MAX_PAIRS_PER_DICT]]
            pairs = {
                str(k): str(v)
                for k, v in zip(keys, vals)
                if isinstance(k, str) and isinstance(v, (str, int))
            }
        except Exception:
            continue
        # header maps look like {"Content-Type": "...", "Accept": "..."}
        header_ish = sum(1 for k in pairs if "-" in k or k.lower() in
                         ("host", "accept", "authorization", "cookie", "referer"))
        if header_ish and len(pairs) > len(best):
            best = pairs
    return best


def archive_method(blob: bytes) -> str | None:
    """Find an HTTP method token in an archived NSURLRequest. Best-effort."""
    arch = _load_archive(blob)
    objs = arch.get("$objects", []) if arch else []
    if not isinstance(objs, list) or len(objs) > MAX_ARCHIVE_OBJECTS:
        return None
    for o in objs:
        if isinstance(o, str) and o in HTTP_METHODS:
            return o
    return None


def sig_candidates(headers: dict) -> dict:
    found = {}
    for k, v in (headers or {}).items():
        if SIG_KEY_RE.match(str(k).strip()):
            found[str(k)] = str(v)[:200]
    return found


# --- Cache.db -------------------------------------------------------------
def find_cache_db(container: str, bundle_id: str) -> str | None:
    patterns = [
        os.path.join(container, "Library/Caches", bundle_id, "Cache.db"),
        os.path.join(container, "Library/Caches", "*", "Cache.db"),
    ]
    for pat in patterns:
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    return None


def parse_cache_db(db_path: str) -> list[dict]:
    """Parse CFURLCache Cache.db into requests.json-compatible records.

    Reliable: URL, timestamp. Best-effort: headers/method (archived), status.
    Response body: inline receiver_data, else flagged as on-disk (fsCachedData/).
    """
    records: list[dict] = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception as e:
        log(f"[cache] cannot open {db_path}: {e}")
        return records
    con.row_factory = sqlite3.Row
    try:
        # Column availability varies slightly by iOS version; select defensively.
        cols = {r[1] for r in con.execute("PRAGMA table_info(cfurl_cache_response)")}
        has_ts = "time_stamp" in cols
        q = (
            "SELECT r.entry_ID AS eid, r.request_key AS url"
            + (", r.time_stamp AS ts" if has_ts else "")
            + " FROM cfurl_cache_response r"
        )
        rows = list(con.execute(q))
    except Exception as e:
        log(f"[cache] unexpected schema, skipping: {e}")
        con.close()
        return records

    for row in rows:
        eid = row["eid"]
        url = row["url"] or ""
        parsed = urlparse(url)
        rec = {
            "direction": "cache",
            "source": "NSURLCache",
            "url": url,
            "host": parsed.netloc or None,
            "method": None,
            "path": (parsed.path + (("?" + parsed.query) if parsed.query else "")) or None,
            "version": None,
            "status": None,
            "timestamp": (row["ts"] if has_ts else None),
            "headers": {},
            "body": None,
            "body_on_fs": False,
            "sig_candidates": {},
        }
        # blob data: archived request/response objects (headers, method)
        try:
            b = con.execute(
                "SELECT request_object, response_object FROM cfurl_cache_blob_data WHERE entry_ID=?",
                (eid,),
            ).fetchone()
            if b:
                if b["request_object"]:
                    rec["method"] = archive_method(bytes(b["request_object"]))
                    rec["headers"] = archive_headers(bytes(b["request_object"])) or rec["headers"]
                if b["response_object"] and not rec["headers"]:
                    rec["headers"] = archive_headers(bytes(b["response_object"]))
        except Exception:
            pass
        # receiver data: response body (inline or on fs)
        try:
            d = con.execute(
                "SELECT receiver_data, isDataOnFS FROM cfurl_cache_receiver_data WHERE entry_ID=?",
                (eid,),
            ).fetchone()
            if d:
                if d["isDataOnFS"]:
                    rec["body_on_fs"] = True
                    rec["body"] = "<body on disk in fsCachedData/>"
                elif d["receiver_data"]:
                    raw = bytes(d["receiver_data"])
                    try:
                        rec["body"] = raw.decode("utf-8")[:2000]
                    except UnicodeDecodeError:
                        rec["body"] = f"<{len(raw)} bytes binary>"
        except Exception:
            pass
        rec["sig_candidates"] = sig_candidates(rec["headers"])
        records.append(rec)
    con.close()
    return records


# --- PlayKeychain + defaults ---------------------------------------------
def find_playkeychain(container: str, bundle_id: str) -> list[str]:
    hits: list[str] = []
    for pat in (
        os.path.join(container, "Documents/PlayChain*"),
        os.path.join(container, "Library/PlayKeychain*"),
        os.path.join(os.path.dirname(container), "PlayChain*"),
    ):
        hits.extend(glob.glob(pat))
    # Any plist files under a keychain-ish dir
    plists: list[str] = []
    for h in hits:
        if os.path.isdir(h):
            plists.extend(glob.glob(os.path.join(h, "**/*.plist"), recursive=True))
        elif h.endswith(".plist"):
            plists.append(h)
    return sorted(set(plists))


def find_defaults(container: str, bundle_id: str) -> str | None:
    p = os.path.join(container, "Library/Preferences", f"{bundle_id}.plist")
    return p if os.path.isfile(p) else None


# --- main -----------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle-id", help="app bundle identifier (else first app found)")
    ap.add_argument("--app-dir", help="explicit .app path (skips the install glob)")
    ap.add_argument("--container", help="explicit Data container path")
    ap.add_argument("--out", default="./re_out", help="output dir (default ./re_out)")
    args = ap.parse_args()

    app_dir = args.app_dir or find_app_dir(args.bundle_id)
    bundle_id = args.bundle_id or (bundle_id_of(app_dir) if app_dir else None)
    if not bundle_id:
        log("[locate] no bundle id (pass --bundle-id or --app-dir); PlayCover install not found.")
        log("[locate] roots checked: " + ", ".join(str(r) for r in APP_ROOTS))
    container = args.container or (find_container(bundle_id) if bundle_id else None)

    exec_hint = None
    if app_dir:
        info = Path(app_dir) / "Info.plist"
        if info.is_file():
            try:
                with open(info, "rb") as fh:
                    exec_hint = plistlib.load(fh).get("CFBundleExecutable")
            except Exception:
                pass

    proc = running_process(exec_hint)

    log(f"[locate] app_dir   : {app_dir or '<not found>'}")
    log(f"[locate] bundle_id : {bundle_id or '<unknown>'}")
    log(f"[locate] container : {container or '<not found>'}")
    if proc:
        log(f"[locate] running   : pid {proc.get('pid')} ({proc.get('ps')})")

    records: list[dict] = []
    cache_db = None
    playkeychain: list[str] = []
    defaults = None

    if container and bundle_id:
        cache_db = find_cache_db(container, bundle_id)
        if cache_db:
            log(f"[cache] {cache_db}")
            records = parse_cache_db(cache_db)
            log(f"[cache] {len(records)} cached entr{'y' if len(records)==1 else 'ies'}"
                + (" (URLs reliable; headers/bodies best-effort)" if records else " (empty)"))
        else:
            log("[cache] no Cache.db (app may use ephemeral sessions or no-store — normal)")
        playkeychain = find_playkeychain(container, bundle_id)
        if playkeychain:
            log(f"[keychain] PlayKeychain plists on disk: {len(playkeychain)} "
                "(readable only because the toggle is enabled)")
        else:
            log("[keychain] no on-disk PlayKeychain (toggle off? -> items are in the macOS login keychain: "
                "security find-generic-password)")
        defaults = find_defaults(container, bundle_id)
        if defaults:
            log(f"[defaults] {defaults}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "app_dir": app_dir,
        "bundle_id": bundle_id,
        "container": container,
        "process": proc,
        "cache_db": cache_db,
        "cache_entries": len(records),
        "playkeychain_plists": playkeychain,
        "nsuserdefaults_plist": defaults,
    }
    (out_dir / "ios_container.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )

    # Merge cache records into requests.json (append; dedup by url+timestamp).
    if records:
        req_path = out_dir / "requests.json"
        existing = []
        if req_path.is_file():
            try:
                existing = json.loads(req_path.read_text())
            except Exception:
                existing = []
        seen = {(r.get("url"), r.get("timestamp")) for r in existing if isinstance(r, dict)}
        for r in records:
            key = (r.get("url"), r.get("timestamp"))
            if key not in seen:
                existing.append(r)
                seen.add(key)
        req_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False, default=str))
        log(f"[out] merged {len(records)} record(s) into {req_path}")

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
