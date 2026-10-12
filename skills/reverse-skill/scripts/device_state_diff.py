#!/usr/bin/env python3
"""Diff two file-state listings taken before and after one action on the user's own app.

Usage:
    device_state_diff.py BEFORE.tsv AFTER.tsv --out FILE --scope "TEXT"

Each listing is tab-separated, one file per line: relative_path, size_bytes, sha256.
Use "-" for a hash that was not taken. The listings are produced by the analyst, with
the access the agreed scope allows, and this tool does not collect them. Paths must be
relative and must not contain "..", so a listing cannot point the comparison outside
the app directory it describes.

The output lists files added, removed and changed (size or hash differs), plus the
number unchanged. It holds paths, sizes and hashes only. It never reads file contents,
and it does not print the bytes of any file. Paths can still reveal account names or
identifiers, so keep the output private.

--scope is required and is recorded in the output. An app's private storage can hold
personal data and session material, so the scope has to be stated before the diff is
made. A change does not establish cause: an app writes caches and logs without any
user action, so a changed file is a lead to check against the action, not a finding.

Output: JSON in FILE with mode 0600, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MAX_LISTING_LINES = 2_000_000

LIMITATIONS = [
    "Shows what changed in the listings only; it does not establish which action caused a change",
    "A hash of '-' means the file was not hashed, so a same-size change can be missed",
    "Directories are not listed; empty directories created or removed are not reported",
    "No file contents are read or printed",
]


class InputError(Exception):
    """Malformed listing or missing scope. Exit code 2."""


def read_listing(path: str) -> dict:
    files = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for number, line in enumerate(fh, 1):
            if number > MAX_LISTING_LINES:
                raise InputError("listing exceeds %d lines: %s" % (MAX_LISTING_LINES, path))
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                raise InputError("%s line %d: expected 3 tab-separated fields" % (path, number))
            rel, size, digest = parts
            if not rel or rel.startswith("/") or ".." in rel.split("/"):
                raise InputError("%s line %d: path must be relative with no '..': %r" % (path, number, rel))
            try:
                size_value = int(size)
            except ValueError:
                raise InputError("%s line %d: size is not an integer" % (path, number))
            files[rel] = {"size": size_value, "sha256": None if digest == "-" else digest.lower()}
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


def run(before_path: str, after_path: str, out_path: str, scope: str) -> dict:
    if not scope.strip():
        raise InputError("--scope must state the agreed scope for this app's storage")
    before = read_listing(before_path)
    after = read_listing(after_path)
    result = {
        "scope": scope.strip(),
        "before": {"source": os.path.basename(before_path), "files": len(before)},
        "after": {"source": os.path.basename(after_path), "files": len(after)},
        "summary": {},
        "diff": diff(before, after),
        "limitations": list(LIMITATIONS),
    }
    d = result["diff"]
    result["summary"] = {"added": len(d["added"]), "removed": len(d["removed"]),
                         "changed": len(d["changed"]), "unchanged": d["unchanged"]}
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(out_path, 0o600)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Diff two file-state listings (paths, sizes, hashes only).")
    ap.add_argument("before", help="listing taken before the action (tab-separated)")
    ap.add_argument("after", help="listing taken after the action (tab-separated)")
    ap.add_argument("--out", required=True, help="output JSON file")
    ap.add_argument("--scope", required=True, help="one line stating the agreed scope")
    args = ap.parse_args(argv)
    for path in (args.before, args.after):
        if not os.path.isfile(path):
            sys.stderr.write("ERROR: listing not found: %s\n" % path)
            return 2
    try:
        result = run(args.before, args.after, args.out, args.scope)
    except (InputError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
