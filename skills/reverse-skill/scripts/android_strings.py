#!/usr/bin/env python3
"""Project Android string resources across locales and configuration qualifiers.

Usage:
    android_strings.py APKTOOL_OUT [--name NAME ...] [--search TEXT] [--limit N]

APKTOOL_OUT is the apktool output directory. Every res/values*/strings.xml under it
is read. The directory suffix is the qualifier: "values" is the default, and
"values-fr", "values-b+sr+Latn" or "values-night" are kept as written, so a
translation is never guessed from a language code alone.

For each string name shown, the output gives the default value (null when the name has
no default declaration), the value in every qualifier that declares the name, and
missing_in: the non-default qualifiers that do not declare it. At most --limit names
are shown (default 200); truncated is true when more names match.

A name's translatable status comes from its default declaration when there is one.
Without one, it comes from the first qualifier that declares the name, in the order of
the qualifiers list in the output (default first, then the others alphabetically). The
status is written to the translatable field. When the status is false, missing_in is []
for that name, because a missing translation there is expected. A declaration is
untranslatable when its translatable attribute is "false", in double or single quotes.

The XML is read with a regular expression, not an XML parser, because the APK is
untrusted input and this avoids entity-expansion risk. XML comments, including
multi-line ones, are removed before matching; an unterminated comment runs to the end
of the file. Entities are decoded with html.unescape. The name and translatable
attributes accept single or double quotes.

Only <string name="..."> elements are read; a self-closing <string name="..."/> is read
as an empty value. <plurals> and <string-array> elements are not read at all and do not
appear in the output. A reference such as @string/other is shown as written and not
followed.

Output: JSON on stdout. Exit codes: 0 done, 1 no strings.xml found, 2 usage or
input error. Standard library only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

MAX_XML_BYTES = 16 * 1024 * 1024
DEFAULT_LIMIT = 200

COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
STRING_RE = re.compile(
    r"<string\s+(?P<before>[^>]*?)\bname\s*=\s*(?P<quote>[\"'])(?P<name>[^\"']+)(?P=quote)"
    r"(?P<after>[^>]*)>(?P<value>.*?)</string>", re.S)
SELF_CLOSING_RE = re.compile(r"<string\b[^>]*?/>")
TRANSLATABLE_RE = re.compile(r"translatable\s*=\s*([\"'])false\1")

LIMITATIONS = [
    "Only <string> elements are read; <plurals>, <string-array> and <item> entries are not projected",
    "Values are shown as written in the XML after entity decoding; @string/ references are not followed",
    "Qualifier order is not resolved: a value is shown under the exact qualifier it was declared in",
    "Parsing is regular-expression based; an unusual but valid XML layout may be missed and is not reported",
]


class InputError(Exception):
    """Bad arguments or unreadable input. Exit code 2."""


def find_strings_files(root: str):
    """Yield (qualifier, path) for every res/values*/strings.xml, qualifier 'default' for plain values."""
    res = os.path.join(root, "res")
    if not os.path.isdir(res):
        return
    for entry in sorted(os.listdir(res)):
        if entry != "values" and not entry.startswith("values-"):
            continue
        path = os.path.join(res, entry, "strings.xml")
        if os.path.isfile(path) and not os.path.islink(path):
            qualifier = "default" if entry == "values" else entry[len("values-"):]
            yield qualifier, path


def parse_strings(text: str):
    """Return {name: {"value": str, "translatable": bool}} for one strings.xml.

    Comments are removed before matching, and a self-closing <string/> becomes an empty
    element, so the match cannot run on to the next </string>. A name declared twice in
    one file keeps its last declaration.
    """
    found = {}
    cleaned = SELF_CLOSING_RE.sub(lambda m: m.group(0)[:-2].rstrip() + "></string>", COMMENT_RE.sub("", text))
    for match in STRING_RE.finditer(cleaned):
        attrs = match.group("before") + " " + match.group("after")
        name = match.group("name")
        value = html.unescape(match.group("value").strip())
        found[name] = {"value": value, "translatable": not TRANSLATABLE_RE.search(attrs)}
    return found


def project(root: str, names=None, search=None, limit=DEFAULT_LIMIT) -> dict:
    per_qualifier = {}
    sources = []
    for qualifier, path in find_strings_files(root):
        if os.path.getsize(path) > MAX_XML_BYTES:
            raise InputError("strings.xml exceeds 16 MiB: %s" % os.path.relpath(path, root))
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            per_qualifier[qualifier] = parse_strings(fh.read())
        sources.append(os.path.relpath(path, root).replace(os.sep, "/"))

    qualifiers = sorted(per_qualifier, key=lambda q: (q != "default", q))
    all_names = sorted({n for q in per_qualifier.values() for n in q})
    if names:
        wanted = set(names)
        selected = [n for n in all_names if n in wanted]
    elif search:
        needle = search.lower()
        selected = [n for n in all_names
                    if needle in n.lower()
                    or any(needle in q[n]["value"].lower() for q in per_qualifier.values() if n in q)]
    else:
        selected = all_names

    strings = {}
    for name in selected[:limit]:
        variants = {}
        for q in qualifiers:
            if name in per_qualifier[q]:
                variants[q] = per_qualifier[q][name]["value"]
        default_entry = per_qualifier.get("default", {}).get(name)
        # The default declaration decides. Without one, the first declaring qualifier in the
        # output order decides; every selected name is declared in at least one qualifier.
        if default_entry is not None:
            translatable = default_entry["translatable"]
        else:
            first = next(q for q in qualifiers if name in per_qualifier[q])
            translatable = per_qualifier[first][name]["translatable"]
        missing = [q for q in qualifiers if q != "default" and name not in per_qualifier[q]]
        strings[name] = {
            "default": default_entry["value"] if default_entry else None,
            "variants": variants,
            "missing_in": missing if translatable else [],
            "translatable": translatable,
        }

    return {
        "sources": sources,
        "qualifiers": qualifiers,
        "string_count": len(all_names),
        "matched": len(selected),
        "shown": len(strings),
        "truncated": len(selected) > limit,
        "strings": strings,
        "limitations": list(LIMITATIONS),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Project Android string resources across locales and qualifiers.")
    ap.add_argument("root", help="apktool output directory")
    ap.add_argument("--name", action="append", default=[], help="exact string name (repeatable)")
    ap.add_argument("--search", default=None, help="case-insensitive text in a name or value")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="maximum strings to show (default %d)" % DEFAULT_LIMIT)
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        sys.stderr.write("ERROR: apktool output directory not found: %s\n" % args.root)
        return 2
    if args.limit < 1:
        sys.stderr.write("ERROR: --limit must be at least 1\n")
        return 2
    try:
        result = project(args.root, args.name or None, args.search, args.limit)
    except InputError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["sources"] else 1


if __name__ == "__main__":
    sys.exit(main())
