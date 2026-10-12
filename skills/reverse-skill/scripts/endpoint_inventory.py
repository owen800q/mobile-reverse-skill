#!/usr/bin/env python3
"""Group captured requests into endpoints by path template, without keeping raw values.

Usage:
    endpoint_inventory.py REQUESTS_JSON --out FILE [--literal VALUE | --literal-file FILE]

REQUESTS_JSON is the requests.json written by har_parse.py (or ecapture_parse.py).
Only "send" records are grouped. Each request's path is turned into a template:

    /v1/users/12345/orders            -> /v1/users/{n}/orders
    /v1/users/3f2a...c9 (uuid)        -> /v1/users/{uuid}/...
    /v1/items/9f86d081884c7d65...     -> /v1/items/{hex}      (16+ hex digits)
    /v1/sessions/Qm9vdHN0cmFwVG9rZW4  -> /v1/sessions/{token} (long mixed token)
    /v1/export/1714000000000          -> /v1/export/{ts}      (10 or 13 digits)

Query strings are removed from the template and only their parameter names are
kept. The inventory holds templates, method, host, counts, the entry indices that
produced each group, and parameter names. It never holds a raw path or a value.
Declared literals (--literal, --literal-file) are removed, as a final pass, from the
host, template and parameter-name fields, so a secret that survives templating is
still caught. The counts, indices and limitations carry no request values and are not
scanned.

The templates are a grouping aid, not a claim about the API. Two endpoints that
differ only in a segment that happens to look like a token will be merged, and an
endpoint whose static segment is itself a hex or long token will be shown as {hex}
or {token}. Check the entry indices before citing a template.

Output: endpoints.json, plus a JSON summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_literals import (  # noqa: E402
    LiteralError, add_literal_args, redact_text, resolve_literal_args,
)

MAX_REQUESTS_BYTES = 256 * 1024 * 1024
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{16,}$")
DIGITS_RE = re.compile(r"^\d+$")
TS_RE = re.compile(r"^\d{10}$|^\d{13}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-+/=.]{20,}$")

LIMITATIONS = [
    "Templates are a grouping aid; a static segment that looks like a token or hex value is shown as {token} or {hex}",
    "Two endpoints that differ only in such a segment are merged; check entry_indices before citing a template",
    "Only send records are grouped. Response bodies and headers are not inventoried here",
    "Parameter names come from the query string only; form and JSON body fields are not listed",
]


class InputError(Exception):
    """Bad input file or arguments. Exit code 2."""


def _has_mixed_chars(segment: str) -> bool:
    return any(c.isdigit() for c in segment) and any(c.isalpha() for c in segment)


def template_segment(segment: str) -> str:
    if not segment:
        return segment
    if UUID_RE.match(segment):
        return "{uuid}"
    if DIGITS_RE.match(segment):
        return "{ts}" if TS_RE.match(segment) else "{n}"
    if HEX_RE.match(segment):
        return "{hex}"
    if TOKEN_RE.match(segment) and _has_mixed_chars(segment):
        return "{token}"
    return segment


def template_path(raw_path: str):
    """Return (template, parameter_names) for a request path that may carry a query string."""
    if "://" in raw_path:
        base = raw_path
    else:
        # Keep the host placeholder separate from the path, so "users/1" does not become "xusers/1".
        base = "http://x" + ("" if raw_path.startswith("/") else "/") + raw_path
    parsed = urllib.parse.urlsplit(base)
    path = parsed.path or "/"
    segments = [template_segment(urllib.parse.unquote(s)) for s in path.split("/")]
    names = sorted({name for name, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)})
    return "/".join(segments), names


def build_inventory(records, literals):
    groups = {}
    skipped = 0
    for index, rec in enumerate(records):
        if not isinstance(rec, dict) or rec.get("direction") != "send":
            continue
        method = rec.get("method")
        path = rec.get("path")
        if not isinstance(method, str) or not isinstance(path, str):
            skipped += 1
            continue
        template, params = template_path(path)
        host = rec.get("host") or ""
        key = (method.upper(), host, template)
        group = groups.setdefault(key, {"method": method.upper(), "host": host, "template": template,
                                        "count": 0, "entry_indices": [], "query_params": set()})
        group["count"] += 1
        entry = rec.get("entry_index", index)
        if entry not in group["entry_indices"] and len(group["entry_indices"]) < 50:
            group["entry_indices"].append(entry)
        group["query_params"].update(params)

    endpoints = []
    for group in sorted(groups.values(), key=lambda g: (g["host"], g["template"], g["method"])):
        item = {
            "method": group["method"],
            "host": group["host"],
            "template": group["template"],
            "count": group["count"],
            "entry_indices": group["entry_indices"],
            "query_params": sorted(group["query_params"]),
        }
        if literals:
            item["host"] = redact_text(item["host"], literals)[0]
            item["template"] = redact_text(item["template"], literals)[0]
            item["query_params"] = [redact_text(p, literals)[0] for p in item["query_params"]]
        endpoints.append(item)
    return endpoints, skipped


def run(requests_path: str, out_path: str, literals) -> dict:
    if os.path.getsize(requests_path) > MAX_REQUESTS_BYTES:
        raise InputError("requests file exceeds 256 MiB: %s" % requests_path)
    try:
        with open(requests_path, "r", encoding="utf-8") as fh:
            records = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError("cannot read requests JSON: %s" % exc)
    if not isinstance(records, list):
        raise InputError("requests JSON must be a list of records")

    endpoints, skipped = build_inventory(records, literals)
    result = {
        "source": os.path.basename(requests_path),
        "send_records": sum(1 for r in records if isinstance(r, dict) and r.get("direction") == "send"),
        "skipped": skipped,
        "endpoint_count": len(endpoints),
        "literals_applied": len(literals),
        "endpoints": endpoints,
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
    ap = argparse.ArgumentParser(description="Group requests into endpoints by path template.")
    ap.add_argument("requests", help="requests.json from har_parse.py or ecapture_parse.py")
    ap.add_argument("--out", required=True, help="output file (endpoints.json)")
    add_literal_args(ap)
    args = ap.parse_args(argv)
    if not os.path.isfile(args.requests):
        sys.stderr.write("ERROR: requests file not found: %s\n" % args.requests)
        return 2
    try:
        literals = resolve_literal_args(args)
        result = run(args.requests, args.out, literals)
    except (InputError, LiteralError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps({k: v for k, v in result.items() if k != "endpoints"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
