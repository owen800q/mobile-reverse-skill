#!/usr/bin/env python3
"""Diff two file-state listings taken before and after one action on the user's own app.

Usage:
    device_state_diff.py BEFORE.tsv AFTER.tsv --out FILE --scope "TEXT" [--log FILE]

Each listing is tab-separated, one file per line: relative_path, size_bytes, sha256.
Use "-" for a hash that was not taken. The listings are produced by the analyst, with
the access the agreed scope allows, and this tool does not collect them. A path must be
relative and must not have a ".." path component: the check splits the path on "/" and
refuses a component that is exactly "..", so "a..b.txt" is accepted and "x/../y" is
refused. Backslashes are not separators for this check. A path is only a label: the
paths are compared as text, and the tool never opens the file a path names.

The output lists files added, removed and changed (size or hash differs), plus the
number unchanged. For each changed file it holds the path, the size before and after,
and whether its hash was compared. The output also holds the scope text, the listing file
names, file counts, summary counts and limitations. It holds no file hashes and no file
contents, and it does not print the bytes of any file. Paths can still reveal account
names or identifiers, so keep the output private.

--scope is required and is recorded in the output. An app's private storage can hold
personal data and session material, so the scope has to be stated before the diff is
made. A change does not establish cause: an app writes caches and logs without any
user action, so a changed file is a lead to check against the action, not a finding.

Trace log: every call to read_listing and run appends one JSON line to --log, and so does
a missing listing that main refuses. The default is device_state_diff.trace.jsonl in the
directory that holds --out, created mode 0600. Each line has a UTC timestamp, the tool and
function, and the outcome. A read_listing line holds the listing's file name, its SHA-256
and its entry count. A run line holds the scope length and SHA-256 (the scope text is not
logged), the output's path relative to the log, and the summary counts. Listing paths are
not logged.

Output: JSON in FILE with mode 0600, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

MAX_LISTING_LINES = 2_000_000
TOOL = "device_state_diff.py"
TRACE_NAME = "device_state_diff.trace.jsonl"

LIMITATIONS = [
    "Shows what changed in the listings only; it does not establish which action caused a change",
    "A hash of '-' means the file was not hashed, so a same-size change can be missed",
    "Directories are not listed; empty directories created or removed are not reported",
    "No file contents are read or printed",
]


class InputError(Exception):
    """Malformed listing or missing scope. Exit code 2."""


class Trace:
    """Append-only JSON-lines log for this tool's calls. The file is mode 0600."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)

    def rel(self, path: str) -> str:
        """Path relative to the log's directory, so the log holds no absolute paths."""
        return os.path.relpath(os.path.abspath(path), os.path.dirname(self.path))

    def write(self, function: str, **fields) -> None:
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": TOOL,
                  "function": function}
        record.update(fields)
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        os.chmod(self.path, 0o600)


def default_trace_path(out: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(out)), TRACE_NAME)


def describe(exc: Exception) -> str:
    """Error text for the log: an OSError's strerror, so no absolute path is logged."""
    return exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_listing(path: str) -> dict:
    name = os.path.basename(path)
    files = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for number, line in enumerate(fh, 1):
            if number > MAX_LISTING_LINES:
                raise InputError("%s: listing exceeds %d lines" % (name, MAX_LISTING_LINES))
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                raise InputError("%s line %d: expected 3 tab-separated fields" % (name, number))
            rel, size, digest = parts
            if not rel or rel.startswith("/") or ".." in rel.split("/"):
                raise InputError("%s line %d: path must be relative with no '..' component" % (name, number))
            try:
                size_value = int(size)
            except ValueError:
                raise InputError("%s line %d: size is not an integer" % (name, number))
            files[rel] = {"size": size_value, "sha256": None if digest == "-" else digest.lower()}
    return files


def read_listing(path: str, trace: Trace) -> dict:
    """Read one listing, and log the call with the listing's name, SHA-256 and entry count."""
    name = os.path.basename(path)
    try:
        digest = sha256_of(path)
        files = parse_listing(path)
    except (InputError, OSError) as exc:
        trace.write("read_listing", listing=name, status="input_error", error=describe(exc))
        raise
    trace.write("read_listing", listing=name, sha256=digest, entries=len(files), status="ok")
    return files


def diff(before: dict, after: dict) -> dict:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed, unchanged = [], 0
    for rel in sorted(set(before) & set(after)):
        b, a = before[rel], after[rel]
        size_changed = b["size"] != a["size"]
        hash_known = b["sha256"] is not None and a["sha256"] is not None
        hash_changed = hash_known and b["sha256"] != a["sha256"]
        if size_changed or hash_changed:
            changed.append({"path": rel, "size_before": b["size"], "size_after": a["size"],
                            "hash_compared": hash_known})
        else:
            unchanged += 1
    return {"added": added, "removed": removed, "changed": changed, "unchanged": unchanged}


def run(before_path: str, after_path: str, out_path: str, scope: str, log_path=None) -> dict:
    """Diff the two listings and write the result. Logs one run line for the call, with its outcome."""
    trace = Trace(log_path or default_trace_path(out_path))
    stated = scope.strip()
    try:
        result = _run(before_path, after_path, out_path, stated, trace)
    except (InputError, OSError) as exc:
        trace.write("run", status="input_error", exit_code=2, error=describe(exc),
                    output=trace.rel(out_path), scope_length=len(stated), scope_sha256=sha256_text(stated))
        raise
    trace.write("run", status="ok", exit_code=0, output=trace.rel(out_path), scope_length=len(stated),
                scope_sha256=sha256_text(stated), before=os.path.basename(before_path),
                after=os.path.basename(after_path), summary=result["summary"])
    return result


def _run(before_path: str, after_path: str, out_path: str, scope: str, trace: Trace) -> dict:
    if not scope:
        raise InputError("--scope must state the agreed scope for this app's storage")
    before = read_listing(before_path, trace)
    after = read_listing(after_path, trace)
    d = diff(before, after)
    result = {
        "scope": scope,
        "before": {"source": os.path.basename(before_path), "files": len(before)},
        "after": {"source": os.path.basename(after_path), "files": len(after)},
        "summary": {"added": len(d["added"]), "removed": len(d["removed"]),
                    "changed": len(d["changed"]), "unchanged": d["unchanged"]},
        "diff": d,
        "limitations": list(LIMITATIONS),
    }
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(out_path, 0o600)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Diff two file-state listings: paths and sizes out; hashes are compared, not printed.")
    ap.add_argument("before", help="listing taken before the action (tab-separated)")
    ap.add_argument("after", help="listing taken after the action (tab-separated)")
    ap.add_argument("--out", required=True, help="output JSON file")
    ap.add_argument("--scope", required=True, help="one line stating the agreed scope")
    ap.add_argument("--log", default=None, help="append-only trace log (default: %s beside --out)" % TRACE_NAME)
    args = ap.parse_args(argv)
    try:
        missing = [p for p in (args.before, args.after) if not os.path.isfile(p)]
        if missing:
            Trace(args.log or default_trace_path(args.out)).write(
                "main", status="input_error", exit_code=2, error="listing not found",
                listing=[os.path.basename(p) for p in missing])
            sys.stderr.write("ERROR: listing not found: %s\n" % ", ".join(missing))
            return 2
        result = run(args.before, args.after, args.out, args.scope, args.log)
    except (InputError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
