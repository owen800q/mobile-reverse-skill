#!/usr/bin/env python3
"""Group captured requests into endpoints by path template; values after '=' in a query string
and request-body values are never kept.

Usage:
    endpoint_inventory.py REQUESTS_JSON --out FILE [--literal VALUE | --literal-file FILE]

REQUESTS_JSON is the requests.json written by har_parse.py (or ecapture_parse.py).
Only "send" records are grouped. Each path segment is percent-decoded, then checked in
this order:

  - a UUID (8-4-4-4-12 hex digits) becomes {uuid};
  - an all-digit segment (any Unicode decimal digits) becomes {ts} when it has 10 or 13
    digits, otherwise {n}, so a 16-digit all-digit segment is {n}, not {hex};
  - a segment of 16 or more hex digits becomes {hex};
  - a segment of 20 or more characters from ASCII letters, digits, underscore, hyphen, plus,
    slash, equals sign and period, with at least one ASCII letter and one ASCII digit,
    becomes {token};
  - every other segment is kept as decoded text, so a plain word such as alice is kept.

Examples:

    /v1/users/12345/orders                                 -> /v1/users/{n}/orders
    /v1/users/3f2a9c1e-7b4d-4e8a-9f10-2c5d6e7f8a9b/orders  -> /v1/users/{uuid}/orders
    /v1/items/9f86d081884c7d65a5f0c3b1d2e4f5a6             -> /v1/items/{hex}
    /v1/sessions/Qm9vdHN0cmFwVG9rZW4x                      -> /v1/sessions/{token}
    /v1/export/1714000000000                               -> /v1/export/{ts}
    /v1/users/alice/orders                                 -> /v1/users/alice/orders

Query strings are removed from the template. Only parameter names are kept: a query part
with no "=" is kept as a parameter name, and query values are never kept. Anything after
"#" is dropped.

Request-body field names are listed in body_fields, and body values are never kept. A send
record contributes the names in its form_params (set by har_parse when postData.params is a
non-empty list) and the keys of every object in its body text, when that text parses as a
JSON object. The keys are found at any depth, by recursing through object values and array
items to at most MAX_NESTING levels, and the body is checked for nesting before it is parsed.
A body that is not a JSON object contributes nothing: plain or form-encoded text, a JSON
array or scalar, or a note such as "postData.text absent" or a withheld marker. Each key is
templated as a path segment is, after percent-decoding, so a UUID, token, timestamp, number
or hex key becomes {uuid}, {token}, {ts}, {n} or {hex}; a key containing an address such as
(local@domain.tld) becomes {email}; any other key is kept as decoded text. Each endpoint lists
its names sorted and de-duplicated, at most MAX_BODY_FIELDS (200) of them: the first ones met,
in file order, are kept and the rest are dropped.

The output holds the templates, the method (upper-cased), the host (kept as recorded),
the counts, the entry indices that produced each group (the first 50 distinct indices of
each group: the recorded entry_index, or, for a record without one as in ecapture_parse
output, its 0-based position in the requests list, which counts recv records too), the
query parameter names and the body field names (see below). It also names the
requests file by its base name.

Declared literals (--literal, --literal-file) are removed, as a final pass, from the host,
template, parameter-name and body field names, so a secret that survives templating is caught only in
the forms described below. Each literal is removed in the encodings listed in
redact_literals.variants(), wherever such a form appears as a substring of those fields; a
copy in any other form, such as a Unicode-normalised one, is not removed. A declared
literal inside a larger base64 value is found only when redact_literals' alignment forms
apply: the base64 of the 3-byte groups that lie wholly inside the literal, at the literal's
byte alignment, when those groups give at least 8 base64 characters. That is the coverage
of those forms, not every base64 position; the base64 characters of the partly covered
groups at each end of the literal are not searched. The method, counts, entry indices and
limitations are not scanned.

The templates are a grouping aid, not a claim about the API. Requests with the same method
and host whose paths differ only in templated segments are merged into one template, and a
fixed path word that matches a rule is shown as its placeholder. Check the entry indices
before citing a template.

Output: endpoints.json, plus a JSON summary on stdout. Exit codes: 0 done; 2 usage or
input error: a missing requests file, a requests file that cannot be read or parsed as
UTF-8 JSON (including JSON nested too deeply for the parser), a requests file that is not
a list, a file over 256 MiB, or a refused literal. Any other failure, such as an output
file that cannot be written, ends with an uncaught exception and exit code 1. Standard
library only.
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
MAX_NESTING = 200  # same limit as har_parse's JSON_MAX_DEPTH
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{16,}$")
DIGITS_RE = re.compile(r"^\d+$")
TS_RE = re.compile(r"^\d{10}$|^\d{13}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-+/=.]{20,}$")
# An address-shaped key such as user@example.com. The one character before the '@' is a single
# class, not [^\s@]+: a quantifier on both sides backtracks quadratically on a long key with no '@'.
EMAIL_KEY_RE = re.compile(r"[^\s@]@[^\s@]+\.[^\s@]")
MAX_BODY_FIELDS = 200  # distinct request-body field names kept per endpoint; the first ones met

LIMITATIONS = [
    "Templating rules, checked in this order for each path segment after percent-decoding: a UUID "
    "(8-4-4-4-12 hex digits) becomes {uuid}; an all-digit segment (any Unicode decimal digits) "
    "becomes {ts} when it has 10 or 13 digits, otherwise {n}; a segment of 16 or more hex digits "
    "becomes {hex}; a segment of 20 or more characters from ASCII letters, digits, underscore, "
    "hyphen, plus, slash, equals sign and period, with at least one ASCII letter and one ASCII "
    "digit, becomes {token}; every other segment is kept as decoded text",
    "Templates are a grouping aid: requests with the same method and host whose paths differ only "
    "in templated segments are merged, and a fixed path word that matches a rule is shown as its "
    "placeholder; check entry_indices before citing a template",
    "entry_indices holds the first 50 distinct entry indices of each group: the recorded "
    "entry_index, or, for a record without one (ecapture_parse output), its 0-based position in "
    "the requests file's list, which counts recv records too; count is the full number of send "
    "records in the group",
    "Query values are never kept. Parameter names come from the query string only, and a query "
    "part given with no '=' is kept as a parameter name; body field names are listed separately in "
    "body_fields, under the body_fields rules below",
    "body_fields holds request-body field names, never values, sorted and de-duplicated. It takes "
    "the names in a send record's form_params (set by har_parse when postData.params is a non-empty "
    "list) and the keys of every object in its body text when that text parses as a JSON object, at "
    "any depth: the body is checked for nesting first, and the keys are found by recursing through "
    "object values and array items to at most MAX_NESTING (200) levels. A body that is not a JSON "
    "object contributes nothing, so a form-encoded body is listed only through form_params, and a "
    "top-level JSON array of objects is not listed. Each key is templated as a path segment is, after "
    "percent-decoding: a UUID, token, timestamp, number or hex key becomes {uuid}, {token}, {ts}, {n} "
    "or {hex}, and a key containing an address such as local@domain.tld becomes {email}. Any other "
    "key is kept as decoded text, so a short mixed identifier such as cust_839201 can still appear. "
    "Declared literals are removed from each name. At most MAX_BODY_FIELDS (200) distinct names are "
    "kept per endpoint, the first ones met in file order; later new names are dropped without a marker",
    "Anything after '#' is dropped. The host is kept as recorded; the method is upper-cased",
    "Only send records are grouped. Response bodies and headers are not inventoried here",
    "Declared literals are removed from the host, template, parameter names and body_fields only, in the "
    "encodings listed in redact_literals.variants(); the method, counts, entry indices and "
    "limitations are not scanned",
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
                                        "count": 0, "entry_indices": [], "query_params": set(),
                                        "body_fields": set()})
        group["count"] += 1
        entry = rec.get("entry_index", index)
        if entry not in group["entry_indices"] and len(group["entry_indices"]) < 50:
            group["entry_indices"].append(entry)
        group["query_params"].update(params)
        _add_body_fields(group["body_fields"], rec)

    endpoints = []
    for group in sorted(groups.values(), key=lambda g: (g["host"], g["template"], g["method"])):
        item = {
            "method": group["method"],
            "host": group["host"],
            "template": group["template"],
            "count": group["count"],
            "entry_indices": group["entry_indices"],
            "query_params": sorted(group["query_params"]),
            "body_fields": sorted(group["body_fields"]),
        }
        if literals:
            item["host"] = redact_text(item["host"], literals)[0]
            item["template"] = redact_text(item["template"], literals)[0]
            item["query_params"] = [redact_text(p, literals)[0] for p in item["query_params"]]
            # Redacted names are de-duplicated again: two names that differ only in the encoded
            # form of a literal become one.
            item["body_fields"] = sorted({redact_text(n, literals)[0] for n in item["body_fields"]})
        endpoints.append(item)
    return endpoints, skipped


JSON_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|[\[\]{}]')


def nesting_exceeds(text: str, limit: int) -> bool:
    """True when brackets nest deeper than limit. Strings are skipped, so brackets inside them do not count.

    The check is done before json.loads, so the answer does not depend on the interpreter's recursion limit.
    """
    depth = 0
    for token in JSON_TOKEN_RE.finditer(text):
        ch = token.group(0)
        if ch in "[{":
            depth += 1
            if depth > limit:
                return True
        elif ch in "]}":
            depth -= 1
    return False


def _body_key_name(key: str) -> str:
    """The name listed for one body key: templated as a path segment is, after percent-decoding."""
    # A lone surrogate from a JSON \ud800 escape cannot be written as UTF-8, so it is shown escaped.
    text = urllib.parse.unquote(key.encode("utf-8", "backslashreplace").decode("utf-8"))
    name = template_segment(text)
    return "{email}" if EMAIL_KEY_RE.search(name) else name


def _add_body_name(names: set, key: str) -> None:
    """Add one key's listed name. Once MAX_BODY_FIELDS names are held, further new names are dropped."""
    name = _body_key_name(key)
    if name in names or len(names) < MAX_BODY_FIELDS:
        names.add(name)


def _add_body_keys(names: set, node, depth: int) -> None:
    """Add the keys of every object under node; values are walked for nested objects, never added."""
    if depth > MAX_NESTING:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                _add_body_name(names, key)
            _add_body_keys(names, value, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _add_body_keys(names, item, depth + 1)


def _add_body_fields(names: set, rec: dict) -> None:
    """Add the body field names of one send record: its form_params keys, then the keys of a JSON body."""
    form = rec.get("form_params")
    if isinstance(form, dict):
        for key in form:
            if isinstance(key, str):
                _add_body_name(names, key)
    body = rec.get("body")
    if not isinstance(body, str) or nesting_exceeds(body, MAX_NESTING):
        return
    try:
        parsed = json.loads(body)
    except (ValueError, RecursionError):
        return  # not JSON, such as form-encoded text, binary or a note: it contributes nothing
    if isinstance(parsed, dict):
        _add_body_keys(names, parsed, 1)


def run(requests_path: str, out_path: str, literals) -> dict:
    if os.path.getsize(requests_path) > MAX_REQUESTS_BYTES:
        raise InputError("requests file exceeds 256 MiB: %s" % requests_path)
    try:
        with open(requests_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, ValueError) as exc:
        # UnicodeDecodeError is a ValueError subclass.
        raise InputError("cannot read requests JSON: %s" % exc) from None
    if nesting_exceeds(text, MAX_NESTING):
        raise InputError("requests JSON is nested too deeply to parse (more than %d levels): %s"
                         % (MAX_NESTING, requests_path))
    try:
        records = json.loads(text)
    except RecursionError:
        raise InputError("requests JSON is nested too deeply to parse: %s"
                         % requests_path) from None
    except ValueError as exc:
        # json.JSONDecodeError is a ValueError subclass; so is a parser size limit error.
        raise InputError("cannot read requests JSON: %s" % exc) from None
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
