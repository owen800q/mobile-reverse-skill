#!/usr/bin/env python3
"""Extract an Electron .asar archive to a directory, without executing anything.

Usage:
    asar_extract.py ARCHIVE.asar --out DIR [--unpacked-dir UNPACKED_DIR]

Layout, checked against @electron/asar output: uint32 LE 4 at offset 0; header
size H at offset 4; inner pickle payload H-4 at offset 8; JSON length L at
offset 12; JSON header in [16, 16+L), zero-padded to 8+H; file data starts at
8+H. File entries carry "size" and a decimal-string "offset" relative to the
data start. Entries with "unpacked": true have no offset; their bytes live in
the companion .unpacked directory (default ARCHIVE.asar.unpacked, if it exists).

Writes files under DIR in their original tree shape, plus DIR/manifest.json.
SHA256 integrity metadata (whole file and per block) is verified where present.
A mismatch goes to stderr and the manifest, and the file is still written.
Symlink entries are recorded, not created. Refuses to write into an existing
DIR. stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys

MAX_ARCHIVE_BYTES = 2 * 1024 ** 3
MAX_ENTRY_BYTES = 512 * 1024 ** 2
MAX_HEADER_BYTES = 64 * 1024 ** 2
CHUNK = 1024 * 1024
DRIVE_RE = re.compile(r"^[A-Za-z]:")
DIGITS_RE = re.compile(r"[0-9]+")

LIMITATIONS = [
    "No code was executed: the archive is read and written as bytes only.",
    "Unpacked entries are read from the companion .unpacked directory, which is outside the archive; their bytes are only as trustworthy as that directory.",
    "Integrity metadata is only as trustworthy as the archive: whoever rewrites the archive can rewrite the hashes. Only the in-archive SHA256 metadata was checked; the app-level ElectronAsarIntegrity value stored with the host app was not verified.",
    "Symlink entries are recorded as link targets and not created; executable flags are recorded and file permissions are not changed.",
    "Names containing '..', path separators or NUL, and entries that would resolve outside DIR, are rejected and not extracted.",
    "Duplicate keys in the header JSON keep the last value; the duplicated key names are listed under anomalies.",
]


class LayoutError(Exception):
    """The archive header is not consistent with the verified layout."""


def _show(text, limit=200):
    """Escape untrusted archive names before they reach the terminal."""
    s = str(text).encode("unicode_escape").decode("ascii")
    return s if len(s) <= limit else s[:limit] + "..."


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _bad_name(name):
    """Return why a header name is unsafe to create on disk, or None."""
    if not isinstance(name, str) or name in ("", ".", ".."):
        return "empty, '.' or '..' name"
    if "\x00" in name:
        return "NUL byte"
    if "/" in name or "\\" in name:
        return "path separator"
    if ".." in name:
        return "contains '..'"
    if DRIVE_RE.match(name):
        return "drive-style name"
    return None


def _inside(path, base):
    real_base = os.path.realpath(base)
    real = os.path.realpath(path)
    return real == real_base or real.startswith(real_base.rstrip(os.sep) + os.sep)


def _pairs_hook(anomalies):
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                anomalies.append(key)
            out[key] = value
        return out
    return hook


def _read_header(fh, size):
    """Check the verified layout and parse the JSON header. Raises LayoutError."""
    fh.seek(0)
    prefix = fh.read(16)
    if len(prefix) != 16:
        raise LayoutError("archive is shorter than the 16-byte prefix")
    magic, header_size, payload, json_len = struct.unpack("<4I", prefix)
    if magic != 4:
        raise LayoutError("uint32 at offset 0 is %d, expected 4" % magic)
    if header_size < 8 or 8 + header_size > size:
        raise LayoutError("header size %d does not fit a %d-byte archive" % (header_size, size))
    if payload != header_size - 4:
        raise LayoutError("inner pickle payload %d is not header size %d minus 4"
                          % (payload, header_size))
    if json_len > header_size - 8 or json_len > MAX_HEADER_BYTES:
        raise LayoutError("JSON length %d does not fit header size %d" % (json_len, header_size))
    if payload != 4 + ((json_len + 3) & ~3):
        raise LayoutError("pickle payload %d is inconsistent with JSON length %d"
                          % (payload, json_len))
    raw = fh.read(json_len)
    if len(raw) != json_len:
        raise LayoutError("archive ends inside the JSON header")
    anomalies = []
    try:
        tree = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_hook(anomalies))
    except (ValueError, RecursionError):
        raise LayoutError("JSON header is not valid UTF-8 JSON")
    if not isinstance(tree, dict) or not isinstance(tree.get("files"), dict):
        raise LayoutError("JSON header has no top-level 'files' object")
    return {"header_size": header_size, "json_len": json_len, "raw": raw,
            "tree": tree, "anomalies": anomalies}


def _flatten(tree):
    """Return (kind, parts, entry, reason) for every node, iteratively, in header order."""
    out = []
    stack = [((), tree["files"])]
    while stack:
        prefix, files = stack.pop()
        pending = []
        for name, ent in files.items():
            parts = prefix + (name,)
            reason = _bad_name(name)
            if reason:
                out.append(("rejected", parts, ent, "unsafe name: " + reason))
            elif not isinstance(ent, dict):
                out.append(("rejected", parts, ent, "entry is not an object"))
            elif isinstance(ent.get("files"), dict):
                out.append(("dir", parts, ent, None))
                pending.append((parts, ent["files"]))
            elif "link" in ent:
                out.append(("link", parts, ent, None))
            elif "size" in ent:
                out.append(("file", parts, ent, None))
            else:
                out.append(("rejected", parts, ent, "unknown entry type"))
        stack.extend(reversed(pending))
    return out


def _integrity_meta(integ):
    """Validate an integrity object. Returns a dict with problem, block_size, hash, blocks."""
    meta = {"problem": None, "block_size": None, "hash": None, "blocks": None}
    if not isinstance(integ, dict):
        meta["problem"] = "malformed integrity object"
        return meta
    algorithm = integ.get("algorithm")
    if not isinstance(algorithm, str) or algorithm.upper() != "SHA256":
        meta["problem"] = "unsupported integrity algorithm"
        return meta
    whole = integ.get("hash")
    blocks = integ.get("blocks")
    if whole is not None and not isinstance(whole, str):
        meta["problem"] = "malformed integrity hash"
        return meta
    if blocks is not None:
        if not isinstance(blocks, list) or not all(isinstance(b, str) for b in blocks):
            meta["problem"] = "malformed integrity blocks"
            return meta
        block_size = integ.get("blockSize")
        if not _is_int(block_size) or block_size <= 0:
            meta["problem"] = "invalid integrity blockSize"
            return meta
        meta["block_size"] = block_size
        meta["blocks"] = [b.lower() for b in blocks]
    if whole is None and blocks is None:
        meta["problem"] = "integrity has neither hash nor blocks"
        return meta
    meta["hash"] = whole.lower() if whole is not None else None
    return meta


def _verdict(meta, whole, blocks):
    if meta is None:
        return "absent", None
    if meta["problem"]:
        return "unavailable", meta["problem"]
    bad = []
    if meta["hash"] is not None and meta["hash"] != whole:
        bad.append("whole-file SHA256 differs")
    if meta["blocks"] is not None and meta["blocks"] != blocks:
        if len(meta["blocks"]) != len(blocks):
            bad.append("block count is %d, metadata says %d" % (len(blocks), len(meta["blocks"])))
        else:
            diff = [str(i) for i, (exp, got) in enumerate(zip(meta["blocks"], blocks)) if exp != got]
            bad.append("block(s) %s differ" % ", ".join(diff[:10]) + (" ..." if len(diff) > 10 else ""))
    if bad:
        return "mismatch", "; ".join(bad)
    return "verified", None


def _offset_value(value):
    if isinstance(value, str) and DIGITS_RE.fullmatch(value):
        return int(value)
    if _is_int(value) and value >= 0:
        return value
    return None


def _stream(chunks, block_size, out_fh):
    """Feed chunks through whole-file and per-block SHA256; optionally write them."""
    whole = hashlib.sha256()
    blocks = []
    cur = None
    filled = 0
    total = 0
    for chunk in chunks:
        total += len(chunk)
        whole.update(chunk)
        if out_fh is not None:
            out_fh.write(chunk)
        if block_size is None:
            continue
        view = memoryview(chunk)
        pos = 0
        while pos < len(chunk):
            if cur is None:
                cur, filled = hashlib.sha256(), 0
            take = min(block_size - filled, len(chunk) - pos)
            cur.update(view[pos:pos + take])
            filled += take
            pos += take
            if filled == block_size:
                blocks.append(cur.hexdigest())
                cur = None
    if block_size is not None:
        if cur is not None:
            blocks.append(cur.hexdigest())
        elif total == 0:
            blocks.append(hashlib.sha256().hexdigest())
    return whole.hexdigest(), blocks, total


def _span_chunks(fh, start, length):
    """Yield exactly length bytes starting at start; raises OSError on a short read."""
    fh.seek(start)
    left = length
    while left > 0:
        data = fh.read(min(CHUNK, left))
        if not data:
            raise OSError("archive ended early")
        left -= len(data)
        yield data


def _file_chunks(fh):
    """Yield the whole file, bounded by MAX_ENTRY_BYTES."""
    total = 0
    while True:
        data = fh.read(CHUNK)
        if not data:
            return
        total += len(data)
        if total > MAX_ENTRY_BYTES:
            raise OSError("companion file larger than 512 MiB")
        yield data


def _companion_path(parts, unpacked_dir):
    path = os.path.join(unpacked_dir, *parts)
    if not _inside(path, unpacked_dir):
        return None, "companion path resolves outside the unpacked directory"
    if os.path.islink(path):
        return None, "symlink in companion directory; not followed"
    if not os.path.isfile(path):
        return None, "companion file missing from the unpacked directory"
    return path, None


def _base_record(kind, parts, ent):
    return {
        "path": "/".join(parts),
        "kind": kind,
        "size": ent.get("size") if _is_int(ent.get("size")) else None,
        "offset": ent.get("offset") if isinstance(ent.get("offset"), str) else None,
        "sha256": None,
        "integrity": "absent" if ent.get("integrity") is None else "unavailable",
        "integrity_reason": None,
        "unpacked": ent.get("unpacked") is True,
        "executable": ent.get("executable") is True,
        "extracted": False,
        "skip_reason": None,
        "size_mismatch": False,
        "link_target": ent.get("link") if kind == "link" and isinstance(ent.get("link"), str)
        else None,
    }


def _extract_file(rec, parts, ent, ctx, fh):
    """Extract one file entry into ctx.out_dir and fill its manifest record."""
    size = ent.get("size")
    if not _is_int(size) or size < 0:
        rec["skip_reason"] = "invalid size"
        return
    if size > MAX_ENTRY_BYTES:
        rec["skip_reason"] = "entry larger than 512 MiB; not extracted"
        return
    meta = _integrity_meta(ent["integrity"]) if ent.get("integrity") is not None else None
    stream_block = meta["block_size"] if meta and not meta["problem"] else None
    target = os.path.join(ctx["out_dir"], *parts)
    if not _inside(target, ctx["out_dir"]):
        rec["skip_reason"] = "target resolves outside the output directory"
        return

    source = start = None
    if rec["unpacked"]:
        if ctx["unpacked_dir"] is None:
            rec["skip_reason"] = "unpacked entry; no companion directory supplied"
            return
        source, reason = _companion_path(parts, ctx["unpacked_dir"])
        if source is None:
            rec["skip_reason"] = reason
            return
    else:
        offset = _offset_value(ent.get("offset"))
        if offset is None:
            rec["skip_reason"] = "invalid offset"
            return
        start = ctx["data_start"] + offset
        if start + size > ctx["archive_size"]:
            rec["skip_reason"] = "entry span lies outside the archive"
            return

    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        if source is not None:
            with open(source, "rb") as src, open(target, "wb") as out:
                whole, blocks, total = _stream(_file_chunks(src), stream_block, out)
        else:
            with open(target, "wb") as out:
                whole, blocks, total = _stream(_span_chunks(fh, start, size), stream_block, out)
    except OSError as exc:
        if os.path.exists(target):
            os.remove(target)
        rec["skip_reason"] = "read failed: %s" % exc
        return

    rec["extracted"] = True
    rec["sha256"] = whole
    if source is not None and total != size:
        rec["size_mismatch"] = True
        sys.stderr.write("WARNING: companion size %d differs from declared %d: %s\n"
                         % (total, size, _show(rec["path"])))
    rec["integrity"], rec["integrity_reason"] = _verdict(meta, whole, blocks)


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tally(counts, rec):
    counts["integrity"][rec["integrity"]] = counts["integrity"].get(rec["integrity"], 0) + 1
    if rec["kind"] == "file":
        counts["files"] += 1
    elif rec["kind"] == "link":
        counts["links"] += 1
    elif rec["kind"] == "rejected":
        counts["rejected"] += 1
    if rec["extracted"]:
        counts["extracted"] += 1
    elif rec["kind"] == "file":
        counts["not_extracted"] += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract an Electron .asar archive without executing it.")
    ap.add_argument("archive", help="ARCHIVE.asar")
    ap.add_argument("--out", required=True, help="output directory (must not exist)")
    ap.add_argument("--unpacked-dir",
                    help="companion .unpacked directory (default: ARCHIVE.asar.unpacked if present)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.archive):
        sys.stderr.write("ERROR: archive not found: %s\n" % _show(args.archive))
        return 2
    size = os.path.getsize(args.archive)
    if size > MAX_ARCHIVE_BYTES:
        sys.stderr.write("ERROR: archive exceeds the 2 GiB limit: %s\n" % _show(args.archive))
        return 2
    if os.path.lexists(args.out):
        sys.stderr.write("ERROR: output directory already exists; refusing to write into it: %s\n"
                         % _show(args.out))
        return 2
    unpacked_dir = args.unpacked_dir
    if unpacked_dir is None:
        default = args.archive + ".unpacked"
        if os.path.isdir(default):
            unpacked_dir = default
    elif not os.path.isdir(unpacked_dir):
        sys.stderr.write("ERROR: unpacked directory not found: %s\n" % _show(unpacked_dir))
        return 2

    with open(args.archive, "rb") as fh:
        try:
            hdr = _read_header(fh, size)
        except LayoutError as exc:
            sys.stderr.write("ERROR: archive layout check failed: %s\n" % exc)
            return 1
        try:
            os.makedirs(args.out)
        except FileExistsError:
            sys.stderr.write("ERROR: output directory already exists; refusing to write into it\n")
            return 2

        ctx = {
            "out_dir": args.out,
            "unpacked_dir": unpacked_dir,
            "data_start": 8 + hdr["header_size"],
            "archive_size": size,
        }
        counts = {"files": 0, "links": 0, "directories": 0, "rejected": 0, "extracted": 0,
                  "not_extracted": 0,
                  "integrity": {"verified": 0, "mismatch": 0, "absent": 0, "unavailable": 0}}
        records, mismatches = [], []
        for kind, parts, ent, reason in _flatten(hdr["tree"]):
            if kind == "dir":
                counts["directories"] += 1
                target = os.path.join(args.out, *parts)
                if _inside(target, args.out):
                    os.makedirs(target, exist_ok=True)
                continue
            rec = _base_record(kind, parts, ent if isinstance(ent, dict) else {})
            if kind == "rejected":
                rec["skip_reason"] = reason
                sys.stderr.write("skipped %s: %s\n" % (_show(rec["path"]), reason))
            elif kind == "file":
                _extract_file(rec, parts, ent, ctx, fh)
                if rec["skip_reason"]:
                    sys.stderr.write("not extracted %s: %s\n"
                                     % (_show(rec["path"]), rec["skip_reason"]))
            if rec["integrity"] == "mismatch":
                mismatches.append(rec["path"])
                sys.stderr.write("WARNING: SHA256 integrity mismatch (%s), file still written: %s\n"
                                 % (rec["integrity_reason"], _show(rec["path"])))
            if rec["integrity"] == "unavailable" and rec["integrity_reason"] is None:
                rec["integrity_reason"] = rec["skip_reason"] or "not verified"
            _tally(counts, rec)
            records.append(rec)

    counts["integrity_mismatches"] = len(mismatches)
    manifest = {
        "archive": os.path.abspath(args.archive),
        "archive_sha256": _sha256_file(args.archive),
        "archive_size": size,
        "header_sha256": hashlib.sha256(hdr["raw"]).hexdigest(),
        "header_size": hdr["header_size"],
        "json_length": hdr["json_len"],
        "data_offset": ctx["data_start"],
        "unpacked_dir": os.path.abspath(unpacked_dir) if unpacked_dir else None,
        "out": os.path.abspath(args.out),
        "counts": counts,
        "integrity_mismatches": mismatches,
        "anomalies": hdr["anomalies"],
        "entries": records,
        "limitations": LIMITATIONS,
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    sys.stderr.write("asar_extract: %d file(s), %d link(s), %d rejected, %d extracted, "
                     "%d integrity mismatch(es) -> %s\n"
                     % (counts["files"], counts["links"], counts["rejected"],
                        counts["extracted"], len(mismatches), _show(args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
