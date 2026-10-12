#!/usr/bin/env python3
"""Map one position in generated JavaScript back to its original source, checked against bytes.

Usage:
    js_sourcemap_lookup.py GENERATED.js MAP.json LINE COLUMN

LINE is 1-based and COLUMN is 1-based, as an editor shows them. The lookup finds the
mapping segment at or before that position on the same generated line, then checks
the answer against the bytes on both sides:

  generated  the position must exist in GENERATED.js. When the segment names a
             symbol, the text at that position must start with the name.
  original   when the map embeds sourcesContent, the original position must exist in
             that source text, and the name must appear there too.

A check that fails is reported as "mismatch", not silently accepted, because a
source map that does not fit its generated file gives a confident but wrong
original position. Source maps do not record the generated file's hash, so the
match is shown by these checks plus the SHA-256 of both files, not by proof.

Columns are counted in Python code points. Source-map columns are UTF-16 code units,
so the two agree only for text without characters outside the Basic Multilingual
Plane. Such a position is reported with a limitation note.

Output: a JSON object on stdout. Exit codes: 0 resolved, 1 no mapping covers that
position, 2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
B64_INDEX = {c: i for i, c in enumerate(B64)}
MAX_MAP_BYTES = 64 * 1024 * 1024
MAX_GENERATED_BYTES = 256 * 1024 * 1024

LIMITATIONS = [
    "Columns are code points, not UTF-16 units; positions after non-BMP characters may differ",
    "The generated file's hash is not recorded in the map; the match is shown by bounds and name checks",
    "Only the first matching segment at or before the position is used, as the source map spec describes",
]


class InputError(Exception):
    """Bad input. Exit code 2."""


def decode_vlq(segment: str) -> list[int]:
    """Decode one base64 VLQ segment into its signed integer fields."""
    values, shift, acc = [], 0, 0
    for ch in segment:
        if ch not in B64_INDEX:
            raise InputError("invalid base64 VLQ character %r" % ch)
        digit = B64_INDEX[ch]
        acc += (digit & 31) << shift
        if digit & 32:
            shift += 5
            continue
        negative = acc & 1
        value = acc >> 1
        values.append(-value if negative else value)
        acc, shift = 0, 0
    if shift:
        raise InputError("truncated base64 VLQ segment")
    return values


def parse_mappings(mappings: str):
    """Yield (generated_line0, gen_col, source_index, orig_line0, orig_col, name_index or None).

    Fields after the generated column are relative to the previous segment, with the
    generated column reset at each line, as the source map v3 format defines.
    """
    src, orig_line, orig_col, name = 0, 0, 0, 0
    for gen_line, line in enumerate(mappings.split(";")):
        gen_col = 0
        for segment in line.split(","):
            if not segment:
                continue
            fields = decode_vlq(segment)
            if len(fields) not in (1, 4, 5):
                raise InputError("segment on generated line %d has %d fields" % (gen_line + 1, len(fields)))
            gen_col += fields[0]
            if len(fields) == 1:
                continue
            src += fields[1]
            orig_line += fields[2]
            orig_col += fields[3]
            name_index = None
            if len(fields) == 5:
                name += fields[4]
                name_index = name
            yield gen_line, gen_col, src, orig_line, orig_col, name_index


def find_segment(mappings: str, line0: int, col0: int):
    """Return the last segment on line0 whose generated column is <= col0, or None."""
    best = None
    for gen_line, gen_col, src, oline, ocol, name in parse_mappings(mappings):
        if gen_line < line0:
            continue
        if gen_line > line0:
            break
        if gen_col <= col0:
            best = (gen_col, src, oline, ocol, name)
        else:
            break
    return best


def _read_text(path: str, limit: int) -> str:
    if os.path.getsize(path) > limit:
        raise InputError("file exceeds %d MiB: %s" % (limit // (1024 * 1024), path))
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_at(lines, line0, col0):
    if line0 < 0 or line0 >= len(lines):
        return None
    line = lines[line0]
    if col0 < 0 or col0 > len(line):
        return None
    return line[col0:]


def resolve(generated_path: str, map_path: str, line1: int, col1: int) -> tuple[dict, int]:
    if line1 < 1 or col1 < 1:
        raise InputError("LINE and COLUMN are 1-based and must be at least 1")
    generated = _read_text(generated_path, MAX_GENERATED_BYTES)
    map_text = _read_text(map_path, MAX_MAP_BYTES)
    try:
        data = json.loads(map_text)
    except json.JSONDecodeError as exc:
        raise InputError("map is not JSON: %s" % exc)
    if not isinstance(data, dict) or "mappings" not in data:
        raise InputError("map has no 'mappings' field")

    result = {
        "generated": {"path": generated_path, "sha256": _sha256(generated_path),
                      "line": line1, "column": col1},
        "map": {"path": map_path, "sha256": _sha256(map_path)},
        "limitations": list(LIMITATIONS),
        "resolved": False,
        "checks": {},
    }
    line0, col0 = line1 - 1, col1 - 1
    gen_lines = generated.split("\n")
    if _text_at(gen_lines, line0, col0) is None:
        result["checks"]["generated_position"] = "outside_file"
        return result, 1

    try:
        segment = find_segment(data["mappings"], line0, col0)
    except InputError as exc:
        raise InputError("cannot read mappings: %s" % exc)
    if segment is None:
        result["checks"]["mapping"] = "no_segment"
        return result, 1

    gen_col, src_index, oline0, ocol0, name_index = segment
    sources = data.get("sources") or []
    names = data.get("names") or []
    source_name = sources[src_index] if 0 <= src_index < len(sources) else None
    name = names[name_index] if name_index is not None and 0 <= name_index < len(names) else None

    gen_tail = _text_at(gen_lines, line0, gen_col) or ""
    if name is not None:
        result["checks"]["generated_name"] = "match" if gen_tail.startswith(name) else "mismatch"
    else:
        result["checks"]["generated_name"] = "no_name"

    contents = data.get("sourcesContent") or []
    original = contents[src_index] if 0 <= src_index < len(contents) else None
    if original is None:
        result["checks"]["original_text"] = "not_embedded"
    else:
        orig_lines = original.split("\n")
        orig_tail = _text_at(orig_lines, oline0, ocol0)
        if orig_tail is None:
            result["checks"]["original_text"] = "outside_source"
        elif name is not None:
            result["checks"]["original_text"] = "match" if orig_tail.startswith(name) else "mismatch"
        else:
            result["checks"]["original_text"] = "in_range"

    result["resolved"] = True
    result["original"] = {
        "source": source_name,
        "line": oline0 + 1,
        "column": ocol0 + 1,
        "name": name,
        "segment_generated_column": gen_col + 1,
    }
    if "mismatch" in result["checks"].values() or "outside_source" in result["checks"].values():
        result["checks"]["verdict"] = "mismatch"
    else:
        result["checks"]["verdict"] = "consistent"
    return result, 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resolve a generated JavaScript position through a source map.")
    ap.add_argument("generated", help="generated .js file")
    ap.add_argument("map", help="source map .map (JSON)")
    ap.add_argument("line", type=int, help="1-based line in the generated file")
    ap.add_argument("column", type=int, help="1-based column in the generated file")
    args = ap.parse_args(argv)
    try:
        result, code = resolve(args.generated, args.map, args.line, args.column)
    except (InputError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
