#!/usr/bin/env python3
"""Recover original sources from JavaScript source maps.

Usage:
    js_sourcemap_extract.py INPUT --out DIR [--max-map-bytes N]

INPUT is a directory (walked recursively, symlinks not followed) or one
.js/.mjs/.cjs/.map file. Every *.map file is parsed. The last sourceMappingURL
comment in each .js/.mjs/.cjs file is followed to a base64 data: URI or to a
local file inside INPUT. Remote and outside references are recorded, never
fetched. sourcesContent entries are written byte-for-byte (UTF-8) under
DIR/<map_slug>/, with source names sanitized so they stay inside that directory.

DIR must not exist; it is created. Writes DIR/manifest.json and prints a JSON
summary to stdout. Nothing is executed. stdlib only.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.parse

DEFAULT_MAX_MAP_BYTES = 64 * 1024 * 1024
MAX_JS_BYTES = 256 * 1024 * 1024
JS_EXTS = (".js", ".mjs", ".cjs")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
DRIVE_RE = re.compile(r"^[A-Za-z]:")
UNSAFE_RE = re.compile(r'[<>:"|?*\x00-\x1f]')
SLUG_BAD_RE = re.compile(r"[^A-Za-z0-9._-]+")
LINE_REF_RE = re.compile(rb"//[#@][ \t]*sourceMappingURL=(\S+)")
BLOCK_REF_RE = re.compile(rb"/\*[#@][ \t]*sourceMappingURL=([^\s*]+)[ \t]*\*/")
DATA_URI_RE = re.compile(r"^data:application/json(?:;[^;,]*)*;base64,(.*)$", re.S | re.I)

LIMITATIONS = [
    "Source maps hold whatever the build embedded and may not match the shipped JS; compare the shipped file's hash with the map before relying on the result.",
    "Recovered sources are not proof of runtime behavior: the build may have transformed, minified or omitted code.",
    "Nothing was executed: JavaScript was only searched for sourceMappingURL comments, never parsed or run.",
    "sourceRoot is recorded (source_root_set) but not applied to output paths.",
    "Source names were sanitized to stay inside each map's directory; every changed name is listed under sanitized_mappings.",
    "Only the last sourceMappingURL comment in each JS file is followed; maps referenced through HTTP headers or other tooling are not discovered.",
    "sourcesContent is written as UTF-8 byte-for-byte; lone surrogates, if any, are written with surrogatepass and are not valid UTF-8.",
]


def _show(text, limit=200):
    """Escape untrusted names before they reach the terminal."""
    s = str(text).encode("unicode_escape").decode("ascii")
    return s if len(s) <= limit else s[:limit] + "..."


def _rel(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def _inside(path, base):
    real_base = os.path.realpath(base)
    real = os.path.realpath(path)
    return real == real_base or real.startswith(real_base.rstrip(os.sep) + os.sep)


def _walk(root, skipped):
    """Return (rel, full) for regular files under root. Symlinks are recorded, not followed."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in dirnames:
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                skipped.append({"path": _rel(full, root), "reason": "symlinked directory not followed"})
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not os.path.isfile(full):
                skipped.append({"path": _rel(full, root),
                                "reason": "symlink or non-regular file not followed"})
            else:
                found.append((_rel(full, root), full))
    return found


def _last_ref(data):
    """Return the text of the last sourceMappingURL comment, or None."""
    best = None
    for rx in (LINE_REF_RE, BLOCK_REF_RE):
        for m in rx.finditer(data):
            if best is None or m.start() > best[0]:
                best = (m.start(), m.group(1))
    return None if best is None else best[1].decode("utf-8", "replace")


def _discover(root, map_files, js_files, missing, skipped):
    """Return (descriptors, js_files_read). Each map is keyed by file identity or inline JS."""
    maps = {}
    order = []

    def add_file(full, rel, referenced_by):
        key = "file:" + os.path.realpath(full)
        if key not in maps:
            maps[key] = {"kind": "file", "rel": rel, "full": full, "referenced_by": []}
            order.append(key)
        if referenced_by and referenced_by not in maps[key]["referenced_by"]:
            maps[key]["referenced_by"].append(referenced_by)

    for rel, full in map_files:
        add_file(full, rel, None)

    js_read = 0
    for rel, full in js_files:
        if os.path.getsize(full) > MAX_JS_BYTES:
            skipped.append({"path": rel, "reason": "JS file larger than 256 MiB; not scanned"})
            continue
        with open(full, "rb") as fh:
            data = fh.read()
        js_read += 1
        ref = _last_ref(data)
        if ref is None:
            continue
        if ref[:5].lower() == "data:":
            m = DATA_URI_RE.match(ref)
            if not m:
                missing.append({"js": rel, "ref": _show(ref, 120),
                                "reason": "data: URI is not base64 application/json"})
                continue
            key = "inline:" + rel
            maps[key] = {"kind": "inline", "rel": rel, "payload": m.group(1),
                         "referenced_by": [rel]}
            order.append(key)
            continue
        parts = urllib.parse.urlsplit(ref)
        if parts.scheme or parts.netloc:
            missing.append({"js": rel, "ref": _show(ref, 120), "reason": "remote or scheme URL; not fetched"})
            continue
        target = urllib.parse.unquote(parts.path)
        if not target:
            missing.append({"js": rel, "ref": _show(ref, 120), "reason": "empty reference path"})
            continue
        cand = os.path.normpath(os.path.join(os.path.dirname(full), target))
        if not _inside(cand, root):
            missing.append({"js": rel, "ref": _show(ref, 120), "reason": "resolves outside INPUT"})
        elif os.path.islink(cand):
            missing.append({"js": rel, "ref": _show(ref, 120), "reason": "symlink reference not followed"})
        elif not os.path.isfile(cand):
            missing.append({"js": rel, "ref": _show(ref, 120), "reason": "no such file inside INPUT"})
        else:
            add_file(cand, _rel(cand, root), rel)
    return [maps[k] for k in order], js_read


def _load_map_bytes(desc, max_bytes):
    """Return (bytes, None) or (None, reason)."""
    if desc["kind"] == "file":
        size = os.path.getsize(desc["full"])
        if size > max_bytes:
            return None, "skipped: %d bytes exceeds --max-map-bytes" % size
        with open(desc["full"], "rb") as fh:
            return fh.read(), None
    payload = desc["payload"]
    if len(payload) * 3 // 4 > max_bytes:
        return None, "skipped: inline map exceeds --max-map-bytes"
    try:
        return base64.b64decode("".join(payload.split()), validate=True), None
    except ValueError:
        return None, "inline data: URI is not valid base64"


def _parse_map(data):
    """Return (parsed_map, None) or (None, reason)."""
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (ValueError, RecursionError):
        return None, "not valid JSON"
    if not isinstance(obj, dict) or not isinstance(obj.get("sources"), list):
        return None, "no sources list"
    return obj, None


def _slugify(label, used):
    base = SLUG_BAD_RE.sub("_", label).strip("._") or "map"
    slug, n = base, 2
    while slug.lower() in used:
        slug = "%s-%d" % (base, n)
        n += 1
    used.add(slug.lower())
    return slug


def _segments(name, index):
    """Sanitize a source name into safe path segments (never empty, never '..')."""
    text = name if isinstance(name, str) else ""
    text = SCHEME_RE.sub("", text, count=1)
    text = text.lstrip("/\\")
    text = DRIVE_RE.sub("", text, count=1)
    text = text.lstrip("/\\")
    segs = []
    for piece in re.split(r"[\\/]", text):
        if piece in ("", ".", ".."):
            continue
        segs.append(UNSAFE_RE.sub("_", piece))
    return segs or ["_source_%d" % index]


def _place(segs, taken, dirs):
    """Return a collision-free segment list and record it. Falls back to one flat name."""
    candidate = list(segs)
    attempt = 0
    while True:
        key = "/".join(candidate).lower()
        ancestors = ["/".join(candidate[:i]).lower() for i in range(1, len(candidate))]
        if key not in taken and key not in dirs and not any(a in taken for a in ancestors):
            break
        attempt += 1
        stem, ext = os.path.splitext("__".join(segs))
        candidate = ["%s__%d%s" % (stem, attempt, ext)]
    taken.add(key)
    dirs.update(ancestors)
    return candidate


def _write_sources(obj, map_dir):
    """Write sourcesContent under map_dir. Returns (written, missing, mappings)."""
    sources = obj["sources"]
    contents = obj.get("sourcesContent")
    if not isinstance(contents, list):
        contents = None
    taken, dirs = set(), set()
    written, missing, mappings = 0, [], []
    for index, src in enumerate(sources):
        label = src if isinstance(src, str) else _show(src)
        if contents is None or index >= len(contents):
            missing.append({"index": index, "source": label, "reason": "sourcesContent absent"})
            continue
        content = contents[index]
        if content is None:
            missing.append({"index": index, "source": label, "reason": "sourcesContent null"})
            continue
        if not isinstance(content, str):
            missing.append({"index": index, "source": label, "reason": "sourcesContent not a string"})
            continue
        segs = _place(_segments(src, index), taken, dirs)
        target = os.path.join(map_dir, *segs)
        if not _inside(target, map_dir):
            segs = _place(["_source_%d" % index], taken, dirs)
            target = os.path.join(map_dir, *segs)
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(content.encode("utf-8", "surrogatepass"))
        except OSError as exc:
            missing.append({"index": index, "source": label, "reason": "write failed: %s" % exc})
            continue
        written += 1
        out_name = "/".join(segs)
        if out_name != label:
            mappings.append({"index": index, "original": label, "output": out_name})
    return written, missing, mappings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recover original sources from JavaScript source maps.")
    ap.add_argument("input", help="a directory, or one .js/.mjs/.cjs/.map file")
    ap.add_argument("--out", required=True, help="output directory (must not exist)")
    ap.add_argument("--max-map-bytes", type=int, default=DEFAULT_MAX_MAP_BYTES,
                    help="skip maps larger than N bytes (default 64 MiB)")
    args = ap.parse_args(argv)

    if args.max_map_bytes <= 0:
        sys.stderr.write("ERROR: --max-map-bytes must be positive\n")
        return 2
    if not os.path.exists(args.input):
        sys.stderr.write("ERROR: input not found: %s\n" % _show(args.input))
        return 2
    if os.path.lexists(args.out):
        sys.stderr.write("ERROR: output directory already exists; refusing to write into it: %s\n"
                         % _show(args.out))
        return 2

    skipped, missing = [], []
    if os.path.isdir(args.input):
        kind = "directory"
        root = args.input
        if _inside(args.out, root):
            sys.stderr.write("ERROR: output directory must not be inside INPUT\n")
            return 2
        files = _walk(root, skipped)
        map_files = [(rel, full) for rel, full in files if rel.lower().endswith(".map")]
        js_files = [(rel, full) for rel, full in files if rel.lower().endswith(JS_EXTS)]
    else:
        kind = "file"
        name = os.path.basename(args.input)
        root = os.path.dirname(os.path.abspath(args.input))
        if name.lower().endswith(".map"):
            map_files, js_files = [(name, args.input)], []
        elif name.lower().endswith(JS_EXTS):
            map_files, js_files = [], [(name, args.input)]
        else:
            sys.stderr.write("ERROR: INPUT must be a directory or a .js/.mjs/.cjs/.map file\n")
            return 2

    descs, js_read = _discover(root, map_files, js_files, missing, skipped)
    try:
        os.makedirs(args.out)
    except FileExistsError:
        sys.stderr.write("ERROR: output directory already exists; refusing to write into it\n")
        return 2

    used = {"manifest.json"}
    maps_out = []
    totals = {"maps_parsed": 0, "sources_written": 0, "missing_content": 0, "changed_names": 0}
    for desc in descs:
        label = desc["rel"] if desc["kind"] == "file" else desc["rel"] + "#inline"
        entry = {
            "path": desc["rel"], "kind": desc["kind"], "referenced_by": desc["referenced_by"],
            "slug": None, "sha256": None, "size": None, "version": None,
            "source_root_set": False, "sources_count": 0, "written_count": 0,
            "missing_content": [], "sanitized_mappings": [], "error": None,
        }
        maps_out.append(entry)
        data, error = _load_map_bytes(desc, args.max_map_bytes)
        if error:
            entry["error"] = error
            continue
        entry["size"] = len(data)
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        obj, error = _parse_map(data)
        if error:
            entry["error"] = error
            continue
        entry["version"] = obj.get("version")
        entry["source_root_set"] = bool(obj.get("sourceRoot"))
        entry["sources_count"] = len(obj["sources"])
        entry["slug"] = _slugify(label, used)
        map_dir = os.path.join(args.out, entry["slug"])
        os.makedirs(map_dir)
        written, missing_content, mappings = _write_sources(obj, map_dir)
        entry["written_count"] = written
        entry["missing_content"] = missing_content
        entry["sanitized_mappings"] = mappings
        totals["maps_parsed"] += 1
        totals["sources_written"] += written
        totals["missing_content"] += len(missing_content)
        totals["changed_names"] += len(mappings)
        sys.stderr.write("map %s: %d source(s), %d written, %d missing content, %d renamed\n"
                         % (_show(desc["rel"]), len(obj["sources"]), written,
                            len(missing_content), len(mappings)))

    counts = dict(totals, maps_found=len(descs), missing_map_refs=len(missing),
                  skipped=len(skipped), js_files_scanned=js_read)
    manifest = {
        "input": os.path.abspath(args.input),
        "input_kind": kind,
        "out": os.path.abspath(args.out),
        "max_map_bytes": args.max_map_bytes,
        "counts": counts,
        "maps": maps_out,
        "missing_map_refs": missing,
        "skipped": skipped,
        "limitations": LIMITATIONS,
    }
    manifest_path = os.path.join(args.out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    summary = {
        "out": os.path.abspath(args.out),
        "manifest": manifest_path,
        "counts": counts,
        "limitations": LIMITATIONS,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    sys.stderr.write("js_sourcemap_extract: %d map(s) parsed of %d found; %d source(s) written -> %s\n"
                     % (totals["maps_parsed"], len(descs), totals["sources_written"],
                        _show(args.out)))
    if missing:
        sys.stderr.write("%d map reference(s) unresolved; see missing_map_refs in the manifest\n"
                         % len(missing))
    return 0 if totals["maps_parsed"] else 1


if __name__ == "__main__":
    sys.exit(main())
