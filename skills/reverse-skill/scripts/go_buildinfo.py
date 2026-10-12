#!/usr/bin/env python3
"""Read the Go toolchain version, module graph and build settings from a Go binary.

Usage:
    go_buildinfo.py BINARY [--out FILE]

Go embeds a build-info block in every binary built with module support. This reads
it without executing the binary, the same way Go's debug/buildinfo does for the
inline-string format used since Go 1.18:

  header   a 32-byte block starting with the magic "\\xff Go buildinf:". Byte 14 is
           the pointer size. Byte 15 is the flags byte; bit 0x2 means the strings
           that follow are inline, prefixed with unsigned varint lengths.
  version  the toolchain version, such as go1.22.3.
  modinfo  "path", "mod", "dep", "=>" (replace) and "build" lines, wrapped in a
           16-byte sentinel on each side.

The output is the Go version, the main package and module, dependencies with their
replacements, and build settings (GOOS, GOARCH, CGO_ENABLED, vcs.revision and so
on). It contains no file contents and nothing from the binary besides these
strings. Hashes are recorded for the input.

Limitations: builds before Go 1.18 store the build info through pointers, which this
does not follow, so they are reported as undecoded. The magic is searched for at
16-byte-aligned offsets. A binary that has been modified to remove or corrupt the
block is reported as having no build info; that is not evidence the binary was not
built by Go.

Output: JSON on stdout, or to --out. Exit codes: 0 read, 1 no Go build info found,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

MAGIC = b"\xff Go buildinf:"
HEADER_SIZE = 32
ALIGN = 16
FLAG_INLINE = 0x2
SENTINEL = 16
MAX_BINARY_BYTES = 512 * 1024 * 1024
GO_VERSION_RE = re.compile(r"^go\d+(\.\d+)*([a-z]+\d*)?$")

LIMITATIONS = [
    "Builds before Go 1.18 keep build info behind pointers, which are not followed; they are reported as undecoded",
    "The magic is searched at 16-byte-aligned file offsets; a block at another alignment is not found",
    "No build info does not show that a binary was not built by Go; it may be stripped or modified",
    "Build settings are what the toolchain recorded, not a verified reproduction of the build",
]


class InputError(Exception):
    """Unreadable input. Exit code 2."""


def read_uvarint(data: bytes, pos: int):
    value, shift = 0, 0
    while True:
        if pos >= len(data) or shift > 63:
            raise ValueError("truncated or oversized varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7


def read_string(data: bytes, pos: int):
    length, pos = read_uvarint(data, pos)
    if length > len(data) - pos:
        raise ValueError("string length exceeds the data")
    return data[pos:pos + length].decode("utf-8", "replace"), pos + length


def find_blocks(data: bytes):
    """Yield the offset of every aligned build-info header."""
    pos = data.find(MAGIC)
    while pos != -1:
        if pos % ALIGN == 0:
            yield pos
        pos = data.find(MAGIC, pos + 1)


def parse_modinfo(text: str) -> dict:
    info = {"main_path": None, "main_module": None, "deps": [], "replacements": [], "build": {}}
    last_dep = None
    for line in text.splitlines():
        parts = line.split("\t")
        kind = parts[0]
        if kind == "path" and len(parts) >= 2:
            info["main_path"] = parts[1]
        elif kind == "mod" and len(parts) >= 3:
            info["main_module"] = {"path": parts[1], "version": parts[2]}
        elif kind == "dep" and len(parts) >= 3:
            last_dep = {"path": parts[1], "version": parts[2], "replaced_by": None}
            info["deps"].append(last_dep)
        elif kind == "=>" and len(parts) >= 3:
            replacement = {"path": parts[1], "version": parts[2]}
            if last_dep is not None:
                last_dep["replaced_by"] = replacement
            info["replacements"].append(replacement)
        elif kind == "build" and len(parts) >= 2 and "=" in parts[1]:
            key, _, value = parts[1].partition("=")
            info["build"][key] = value
    return info


def decode_block(data: bytes, offset: int):
    """Decode one header at offset. Returns a dict, or None when the block is pointer-based."""
    header = data[offset:offset + HEADER_SIZE]
    if len(header) < HEADER_SIZE:
        raise ValueError("header is truncated")
    flags = header[15]
    if not flags & FLAG_INLINE:
        return {"offset": offset, "encoding": "pointer", "decoded": False}
    body = data[offset + HEADER_SIZE:]
    version, pos = read_string(body, 0)
    modinfo, _ = read_string(body, pos)
    if len(modinfo) >= 2 * SENTINEL + 1 and modinfo[-SENTINEL - 1] == "\n":
        modinfo = modinfo[SENTINEL:-SENTINEL]
    else:
        modinfo = ""
    return {
        "offset": offset,
        "encoding": "inline",
        "decoded": True,
        "pointer_size": header[14],
        "go_version": version,
        "modinfo": modinfo,
    }


def read_binary_info(path: str) -> dict:
    size = os.path.getsize(path)
    if size > MAX_BINARY_BYTES:
        raise InputError("binary exceeds 512 MiB: %s" % path)
    with open(path, "rb") as fh:
        data = fh.read()
    sha = hashlib.sha256(data).hexdigest()

    result = {
        "binary": os.path.basename(path),
        "sha256": sha,
        "size": size,
        "found": False,
        "blocks": [],
        "limitations": list(LIMITATIONS),
    }
    for offset in find_blocks(data):
        try:
            block = decode_block(data, offset)
        except (ValueError, UnicodeDecodeError) as exc:
            result["blocks"].append({"offset": offset, "decoded": False, "error": str(exc)})
            continue
        if block.get("decoded"):
            version = block["go_version"]
            block["go_version_valid"] = bool(GO_VERSION_RE.match(version))
            block.update(parse_modinfo(block.pop("modinfo")))
        result["blocks"].append(block)

    decoded = [b for b in result["blocks"] if b.get("decoded")]
    if decoded:
        first = decoded[0]
        result["found"] = True
        result["go_version"] = first["go_version"]
        result["go_version_valid"] = first["go_version_valid"]
        for key in ("main_path", "main_module", "deps", "replacements", "build"):
            result[key] = first.get(key)
    result["block_count"] = len(result["blocks"])
    result["undecoded_blocks"] = sum(1 for b in result["blocks"] if not b.get("decoded"))
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read Go build info (toolchain, modules, build settings) from a binary.")
    ap.add_argument("binary", help="Go binary (ELF, PE or Mach-O)")
    ap.add_argument("--out", default=None, help="write JSON to FILE instead of stdout")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.binary):
        sys.stderr.write("ERROR: binary not found: %s\n" % args.binary)
        return 2
    try:
        result = read_binary_info(args.binary)
    except (InputError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        os.chmod(args.out, 0o600)
    else:
        print(text)
    return 0 if result["found"] else 1


if __name__ == "__main__":
    sys.exit(main())
