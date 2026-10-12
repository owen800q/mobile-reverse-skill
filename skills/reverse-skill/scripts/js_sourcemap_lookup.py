#!/usr/bin/env python3
"""Map one position in generated JavaScript back to its original source.

Usage:
    js_sourcemap_lookup.py GENERATED.js MAP.json LINE COLUMN

LINE and COLUMN are 1-based. COLUMN counts Unicode code points, so a leading U+FEFF
byte-order mark on line 1 is one column.
Source-map columns count UTF-16 code units, so the lookup converts between the two. The
target column is converted to UTF-16 units before the segment search, and the generated
text is read with the same conversion. The original column is converted back to code
points for "column", and the raw UTF-16 value is always given as "column_utf16". "column"
is null when the position is not inside the embedded original text (sourcesContent is
absent, or the position is past its end), because code points cannot be counted without
that text.

The segment used is the last one in the map's order on that generated line whose generated
column is at or before the target. The tool does not check that segments are in ascending
generated-column order, so on an out-of-order line this is not necessarily the segment that
starts closest before the position. A one-field segment has a generated column and no source.
It is a gap: a position at or after it gets no mapping, and the segment before the gap is not
used.

The answer is then checked against the bytes on each side, as far as the map allows:

  generated  the position must exist in GENERATED.js. The text at the segment's column is
             reported for reference: "generated_token" is the identifier there, cut to 60
             characters, and "generated_name" is "match" when that text is the name as a
             whole identifier, "differs" otherwise, or "no_name" when there is no name.
             Minified code usually differs from the original identifier, so this check
             never sets the verdict.
  original   checked only when the map embeds sourcesContent for that source. The original
             position must exist in that text, and when the segment has a name, the text
             there must start with it. Without sourcesContent no original check runs, and
             "original_text" is "not_embedded", which means no original check was possible.

"checks.verdict" is "mismatch" when the original-side check failed ("original_text" is
"mismatch" or "outside_source"), and "consistent" otherwise. "consistent" does not mean
every check ran: a map without sourcesContent gets "consistent" with no original check.

A failed original-side check gives "mismatch", not a silent pass, because a source map that
does not fit its generated file gives a confident but wrong original position. Source maps
do not record the generated file's hash, so the match is shown by these checks plus the
SHA-256 of both files, not by proof.

An indexed map ("sections") is resolved through the one section that covers the position:
the last section whose offset is at or before it. Offsets are counted in UTF-16 units, like
every map column, and a section's column offset applies on its first line only. The result
then has "map.indexed" true and "map.section" set to the section's path, such as "1", or
"0-2" for a section inside a section. Only that section's map is read and checked, so text
that is not valid in another section is not seen. A position before the first section gives
exit 1 with "checks.mapping" "no_section". A section that gives only a "url" is refused and
is not fetched. A leading U+FEFF and a ")]}'" transport line are dropped before the map is
parsed.

Output: a JSON object on stdout. Exit codes: 0 resolved; 1 no mapping covers that position
(outside the generated file, no segment at or before it, a gap, or before the first section
of an indexed map); 2 usage or input error: a missing, unreadable or oversized file, a file
that is not UTF-8, a map that is not JSON (or is nested too deeply to read), a map or
covering section with no "mappings" string, a section with no valid offset or no embedded
map, a map field of the wrong JSON type or with text that is not valid Unicode, invalid or
truncated VLQ text, or a segment whose field count is not 1, 4 or 5. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
B64_INDEX = {c: i for i, c in enumerate(B64)}
MAX_MAP_BYTES = 64 * 1024 * 1024
MAX_GENERATED_BYTES = 256 * 1024 * 1024
MAX_SECTION_DEPTH = 8
MAX_TOKEN_CHARS = 60
# Identifier-like text: a letter or '_', then letters, digits, '_' or '$'.
IDENT_RE = re.compile(r"(?:[^\W\d]|\$)[\w$]*")
IDENT_CHAR_RE = re.compile(r"[\w$]")

LIMITATIONS = [
    "COLUMN counts code points and the map counts UTF-16 units. column is null unless the "
    "position is inside the embedded original text; column_utf16 is always given. "
    "segment_generated_column is in UTF-16 units",
    "The segment used is the last one on the line at or before the position. A one-field "
    "segment is a gap with no source, so a position at or after it gets no mapping",
    "The original side is checked only when sourcesContent is embedded for that source. "
    "original_text not_embedded means no original check was possible",
    "The original-side name check tests only that the original text starts with the name, "
    "so the name 'a' also matches original text 'abc'. generated_name differs never sets the "
    "verdict",
    "mismatch means the original-side check failed: the text at the original position does "
    "not start with the name, or the position is outside the embedded source (its line is not "
    "in the embedded text, or its column is past the end of that line)",
    "The generated file's hash is not recorded in the map, so consistent does not prove the "
    "map belongs to that file; the match is shown by these checks and the SHA-256 values",
    "Indexed maps (sections) are resolved by offset, and only the section that covers the "
    "position is read and checked. A section that gives a url instead of an embedded map is "
    "refused and is not fetched",
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

    Columns are UTF-16 code units, as the map stores them. Fields after the generated column
    are relative to the previous segment, with the generated column reset at each line, as
    the source map v3 format defines.

    A one-field segment is a gap: it gives a generated column and no source. It is yielded
    with source_index, orig_line0, orig_col and name_index all None. It does not change the
    source, original or name values that later segments are relative to.
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
                yield gen_line, gen_col, None, None, None, None
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
    """Return the segment that covers col0 on line0, or None.

    col0 is a 0-based generated column in UTF-16 code units, as the map stores columns. The
    segment is the last one on line0 whose generated column is <= col0. It is returned as
    (generated column, source index, original line0, original column0, name index). None is
    returned when no segment on the line is at or before col0, and when that last segment is
    a one-field gap, which has no source.
    """
    best = None
    for gen_line, gen_col, src, oline, ocol, name in parse_mappings(mappings):
        if gen_line < line0:
            continue
        if gen_line > line0:
            break
        if gen_col <= col0:
            best = (gen_col, src, oline, ocol, name)
    if best is None or best[1] is None:
        return None
    return best


def _utf16_len(text: str) -> int:
    """Length of text in UTF-16 code units, as a JavaScript string counts it."""
    return len(text.encode("utf-16-le")) // 2


def _utf16_tail(line: str, units: int):
    """Text of line from a 0-based UTF-16 offset, or None when the offset is outside the line.

    An offset inside a surrogate pair gives text that starts with a lone low surrogate, which
    no name starts with.
    """
    raw = line.encode("utf-16-le")
    if units < 0 or 2 * units > len(raw):
        return None
    return raw[2 * units:].decode("utf-16-le", "surrogatepass")


def _code_point_index(line: str, units: int) -> int:
    """0-based code point index of a UTF-16 offset in line (0 to the line's length).

    An offset inside a surrogate pair maps to the character that contains it.
    """
    seen = 0
    for index, ch in enumerate(line):
        width = 2 if ord(ch) > 0xFFFF else 1
        if seen + width > units:
            return index
        seen += width
    return len(line)


def _names_whole_identifier(text: str, name: str) -> bool:
    """True when text starts with name and the name does not continue into a longer identifier."""
    if not text.startswith(name):
        return False
    return IDENT_CHAR_RE.match(text, len(name)) is None


def _read_text(path: str, limit: int) -> str:
    if os.path.getsize(path) > limit:
        raise InputError("file exceeds %d MiB: %s" % (limit // (1024 * 1024), path))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError as exc:
        raise InputError("file is not UTF-8: %s (%s)" % (path, exc.reason))


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


def _check_text(text: str, what: str) -> None:
    """Refuse text that is not valid Unicode, such as an escaped lone surrogate."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise InputError("%s is not valid Unicode text" % what)


def _map_list(data: dict, key: str) -> list:
    """Return a list field of the map. Absent or null gives []; entries must be strings or null."""
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise InputError("map field '%s' is not a list" % key)
    for item in value:
        if item is None:
            continue
        if not isinstance(item, str):
            raise InputError("map field '%s' has an entry that is not a string or null" % key)
        _check_text(item, "map field '%s'" % key)
    return value


def _check_mappings(mappings: str) -> None:
    """Decode every segment, so invalid text is an input error wherever it sits in the map."""
    for _ in parse_mappings(mappings):
        pass


def _leaf_fields(leaf: dict):
    """Check one map that holds mappings, the map itself or the map a section embeds.

    Returns (mappings, sources, names, sourcesContent). Raises InputError for a missing or
    non-string mappings field, text that is not valid Unicode, invalid VLQ text, or a list
    field of the wrong type.
    """
    if "mappings" not in leaf:
        raise InputError("map has no 'mappings' field")
    mappings = leaf["mappings"]
    if not isinstance(mappings, str):
        raise InputError("map field 'mappings' is not a string")
    _check_text(mappings, "map field 'mappings'")
    _check_mappings(mappings)
    return (mappings, _map_list(leaf, "sources"), _map_list(leaf, "names"),
            _map_list(leaf, "sourcesContent"))


def _json_text(text: str) -> str:
    """Drop a leading BOM and the )]}' transport line some servers prepend to a map."""
    text = text[1:] if text.startswith("\ufeff") else text
    if text.startswith(")]}'"):
        m = re.search(r"[\r\n]", text)
        text = text[m.start():] if m else ""
    return text


def _offset(section) -> tuple[int, int]:
    off = section.get("offset") if isinstance(section, dict) else None
    line = off.get("line") if isinstance(off, dict) else None
    col = off.get("column") if isinstance(off, dict) else None
    if (not isinstance(line, int) or isinstance(line, bool) or line < 0
            or not isinstance(col, int) or isinstance(col, bool) or col < 0):
        raise InputError("section has no valid offset {line, column}")
    return line, col


def select_leaf(node, line0: int, col0: int, base=(0, 0), path=()):
    """Descend an indexed map to the leaf covering the absolute position (line0, col0).

    col0 is a 0-based generated column in UTF-16 code units, the unit of every map column and
    of section offsets. Returns (leaf, (origin_line, origin_col), section_path), or
    (None, None, path) when no section covers the position. A section covers every position
    from its offset up to the next section's offset, as the spec defines. The origin is the
    leaf's start in the generated file; a leaf's column offset applies on its first line only.
    A map with no sections is its own leaf.
    """
    sections = node.get("sections")
    if sections is None:
        return node, base, path
    if not isinstance(sections, list):
        raise InputError("'sections' is not a list")
    if len(path) >= MAX_SECTION_DEPTH:
        raise InputError("sections nested deeper than %d" % MAX_SECTION_DEPTH)
    chosen = None
    for index, section in enumerate(sections):
        rel_line, rel_col = _offset(section)
        start = (base[0] + rel_line, rel_col + (base[1] if rel_line == 0 else 0))
        if start <= (line0, col0):
            chosen = (index, section, start)
        else:
            break
    if chosen is None:
        return None, None, path
    index, section, start = chosen
    inner = section.get("map")
    if not isinstance(inner, dict):
        raise InputError("section %s embeds no map (a url reference is not fetched)"
                         % "-".join(str(i) for i in path + (index,)))
    return select_leaf(inner, line0, col0, start, path + (index,))


def resolve(generated_path: str, map_path: str, line1: int, col1: int) -> tuple[dict, int]:
    """Return (result, exit code). Raises InputError for bad input."""
    if line1 < 1 or col1 < 1:
        raise InputError("LINE and COLUMN are 1-based and must be at least 1")
    generated = _read_text(generated_path, MAX_GENERATED_BYTES)
    map_text = _read_text(map_path, MAX_MAP_BYTES)
    try:
        data = json.loads(_json_text(map_text))
    except (ValueError, RecursionError) as exc:
        raise InputError("map is not JSON: %s" % exc)
    if not isinstance(data, dict) or ("mappings" not in data and "sections" not in data):
        raise InputError("map has no 'mappings' or 'sections' field")
    indexed = data.get("sections") is not None
    # A plain map is checked whole before anything else, wherever the position falls. An
    # indexed map is checked in the one section that covers the position.
    fields = None if indexed else _leaf_fields(data)

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

    # The map's columns and section offsets are UTF-16 units, so the code point column is
    # converted first.
    col16 = _utf16_len(gen_lines[line0][:col0])
    leaf, origin, section_path = select_leaf(data, line0, col16)
    if indexed:
        result["map"]["indexed"] = True
        result["map"]["section"] = "-".join(str(i) for i in section_path) or None
        if leaf is None:
            result["checks"]["mapping"] = "no_section"
            return result, 1
        fields = _leaf_fields(leaf)
    mappings, sources, names, contents = fields
    # Leaf coordinates: the section's column offset applies on its first line only.
    leaf_line0 = line0 - origin[0]
    shift = origin[1] if leaf_line0 == 0 else 0
    segment = find_segment(mappings, leaf_line0, col16 - shift)
    if segment is None:
        result["checks"]["mapping"] = "no_segment"
        return result, 1

    gen_col, src_index, oline0, ocol0, name_index = segment
    gen_col += shift
    source_name = sources[src_index] if 0 <= src_index < len(sources) else None
    name = names[name_index] if name_index is not None and 0 <= name_index < len(names) else None

    gen_tail = _utf16_tail(gen_lines[line0], gen_col) or ""
    token = IDENT_RE.match(gen_tail)
    result["checks"]["generated_token"] = token.group(0)[:MAX_TOKEN_CHARS] if token else None
    if name is not None:
        same = _names_whole_identifier(gen_tail, name)
        result["checks"]["generated_name"] = "match" if same else "differs"
    else:
        result["checks"]["generated_name"] = "no_name"

    original = contents[src_index] if 0 <= src_index < len(contents) else None
    original_column = None
    orig_tail = None
    if original is None:
        result["checks"]["original_text"] = "not_embedded"
    else:
        orig_lines = original.split("\n")
        if 0 <= oline0 < len(orig_lines):
            orig_tail = _utf16_tail(orig_lines[oline0], ocol0)
        if orig_tail is None:
            result["checks"]["original_text"] = "outside_source"
        else:
            original_column = _code_point_index(orig_lines[oline0], ocol0) + 1
            if name is not None:
                same = orig_tail.startswith(name)
                result["checks"]["original_text"] = "match" if same else "mismatch"
            else:
                result["checks"]["original_text"] = "in_range"

    result["resolved"] = True
    result["original"] = {
        "source": source_name,
        "line": oline0 + 1,
        "column": original_column,
        "column_utf16": ocol0 + 1,
        "name": name,
        "segment_generated_column": gen_col + 1,
    }
    if result["checks"]["original_text"] in ("mismatch", "outside_source"):
        result["checks"]["verdict"] = "mismatch"
    else:
        result["checks"]["verdict"] = "consistent"
    return result, 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resolve a generated JavaScript position through a source map.")
    ap.add_argument("generated", help="generated .js file")
    ap.add_argument("map", help="source map .map (JSON)")
    ap.add_argument("line", type=int, help="1-based line in the generated file")
    ap.add_argument("column", type=int, help="1-based code point column in the generated file")
    args = ap.parse_args(argv)
    try:
        result, code = resolve(args.generated, args.map, args.line, args.column)
    except (InputError, OSError, UnicodeDecodeError, ValueError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
