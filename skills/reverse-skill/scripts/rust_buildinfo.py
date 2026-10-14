#!/usr/bin/env python3
"""Read the crate dependency list and the rustc commit from a Rust binary.

Usage:
    rust_buildinfo.py BINARY [--out FILE]

cargo-auditable (a cargo wrapper that many Rust builds use) stores the resolved dependency
graph in a section named .dep-v0: a zlib stream of JSON with a "packages" list. Each package
has a name, a version, a source (for example crates.io or git), a kind (runtime or build), the
indices of its dependencies, and a root flag on the top-level crate. This tool reads that
section from an ELF, PE or thin 64-bit Mach-O file, without executing the binary.

It also lists each /rustc/<40 hex digits>/ path found in the file. Those paths name the
compiler commit that built the code, from panic locations and debug strings.

Limits on the section: 1 MiB compressed, 8 MiB inflated, and at most 64 times its compressed
size. Each package keeps its known fields, and any other field it carries is kept under extra.
A malformed section is reported with its error, and the file is not refused for it.

Output: JSON on stdout, or to --out (mode 0600). found is true when a .dep-v0 section decodes.
The output holds the package names, versions and sources, which show what the build linked,
so review it before sharing a binary's inventory. No other file contents are included.

Limitations: a universal (fat) Mach-O is not read, and neither is a Mach-O whose section table
runs past the file. A binary whose section was stripped reports found false; that is not
evidence the binary was built without cargo-auditable. The dependency list records what cargo
resolved at build time, not what the linker kept after dead-code removal. Versions and sources
are not checked against any registry, and the rustc paths are plain text matches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zlib

MAX_BINARY_BYTES = 512 * 1024 * 1024
SECTION_NAME = ".dep-v0"
MAX_SECTION_BYTES = 1024 * 1024
MAX_INFLATED_BYTES = 8 * 1024 * 1024
INFLATE_RATIO = 64
RUSTC_PATH_RE = re.compile(rb"/rustc/([0-9a-f]{40})/")
KNOWN_PACKAGE_KEYS = ("name", "version", "source", "kind", "dependencies", "root")
LC_SEGMENT_64 = 0x19

LIMITATIONS = [
    "The .dep-v0 section is read from ELF, PE and thin 64-bit Mach-O files. A universal Mach-O is not read.",
    "found false means no decodable .dep-v0 section was located. A stripped section is not evidence that cargo-auditable was not used.",
    "The dependency list is what cargo resolved for the build. It is not checked against the linked code, and it is not checked against any registry.",
    "Package sources and versions are copied as recorded. A source value is a string, not a verified URL.",
    "The rustc commit paths are plain-text matches in the file. Another source of the same text, such as a copied string, is reported the same way.",
]


class InputError(Exception):
    """Bad input. Exit code 2."""


def _elf_section(data: bytes, name: str):
    if len(data) < 64 or data[4] not in (1, 2):
        return None
    endian = "<" if data[5] == 1 else ">"
    if data[4] == 2:
        shoff, = struct.unpack_from(endian + "Q", data, 0x28)
        shentsize, shnum, shstrndx = struct.unpack_from(endian + "HHH", data, 0x3A)
        fields = "IIQQQQ"
    else:
        shoff, = struct.unpack_from(endian + "I", data, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from(endian + "HHH", data, 0x2E)
        fields = "IIIIII"
    if shoff == 0 or shnum == 0 or shstrndx >= shnum:
        return None
    headers = []
    for i in range(shnum):
        pos = shoff + i * shentsize
        if pos + shentsize > len(data):
            return None
        sh_name, _type, _flags, _addr, offset, size = struct.unpack_from(endian + fields, data, pos)[:6]
        headers.append((sh_name, offset, size))
    strtab_offset, strtab_size = headers[shstrndx][1], headers[shstrndx][2]
    strtab = data[strtab_offset:strtab_offset + strtab_size]
    for sh_name, offset, size in headers:
        end = strtab.find(b"\x00", sh_name)
        if end >= 0 and strtab[sh_name:end].decode("latin-1") == name:
            return offset, size
    return None


def _pe_section(data: bytes, name: str):
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    lfanew, = struct.unpack_from("<I", data, 0x3C)
    if data[lfanew:lfanew + 4] != b"PE\x00\x00":
        return None
    count, = struct.unpack_from("<H", data, lfanew + 6)
    opt_size, = struct.unpack_from("<H", data, lfanew + 20)
    table = lfanew + 24 + opt_size
    wanted = name.encode("ascii")
    for i in range(count):
        pos = table + i * 40
        if pos + 40 > len(data):
            return None
        raw_name = data[pos:pos + 8].rstrip(b"\x00")
        # SizeOfRawData at +16 and PointerToRawData at +20 of the 40-byte section header.
        size, = struct.unpack_from("<I", data, pos + 16)
        offset, = struct.unpack_from("<I", data, pos + 20)
        if raw_name == wanted:
            return offset, size
    return None


def _macho_section(data: bytes, name: str):
    if len(data) < 32 or data[:4] != b"\xcf\xfa\xed\xfe":
        return None
    ncmds, = struct.unpack_from("<I", data, 16)
    pos = 32
    for _ in range(ncmds):
        if pos + 8 > len(data):
            return None
        cmd, cmdsize = struct.unpack_from("<II", data, pos)
        if cmdsize < 8:
            return None
        if cmd == LC_SEGMENT_64:
            nsects, = struct.unpack_from("<I", data, pos + 64)
            for i in range(nsects):
                sec = pos + 72 + i * 80
                if sec + 80 > len(data):
                    return None
                sectname = data[sec:sec + 16].rstrip(b"\x00").decode("latin-1")
                size, = struct.unpack_from("<Q", data, sec + 40)
                offset, = struct.unpack_from("<I", data, sec + 48)
                if sectname == name:
                    return offset, size
        pos += cmdsize
    return None


def find_section(data: bytes, name: str):
    """(file offset, size) of the named section, or None. ELF, PE and thin Mach-O only."""
    for finder in (_elf_section, _pe_section, _macho_section):
        found = finder(data, name)
        if found is not None:
            return found
    return None


def inflate_section(blob: bytes) -> bytes:
    """Inflate the zlib stream, refusing trailing bytes and output past the limits."""
    limit = min(MAX_INFLATED_BYTES, len(blob) * INFLATE_RATIO)
    d = zlib.decompressobj()
    try:
        out = d.decompress(blob, limit)
    except zlib.error as exc:
        raise ValueError("section is not a valid zlib stream: %s" % exc)
    if d.unconsumed_tail:
        raise ValueError("inflated JSON exceeds the %d byte limit" % limit)
    if not d.eof:
        raise ValueError("zlib stream is truncated")
    if d.unused_data:
        raise ValueError("section has %d bytes after the zlib stream" % len(d.unused_data))
    return out


def decode_packages(doc):
    """Validate the packages list. Unknown package fields are kept under extra."""
    if not isinstance(doc, dict) or not isinstance(doc.get("packages"), list):
        raise ValueError("document has no packages list")
    packages = []
    count = len(doc["packages"])
    for index, raw in enumerate(doc["packages"]):
        if not isinstance(raw, dict):
            raise ValueError("package %d is not an object" % index)
        for key in ("name", "version", "source"):
            if key in raw and not isinstance(raw[key], str):
                raise ValueError("package %d field %s is not a string" % (index, key))
        name, version = raw.get("name"), raw.get("version")
        if not name or not version:
            raise ValueError("package %d has no name or version" % index)
        kind = raw.get("kind", "runtime")
        if kind not in ("runtime", "build"):
            raise ValueError("package %d kind %r is not runtime or build" % (index, kind))
        deps = raw.get("dependencies", [])
        if not isinstance(deps, list) or any(
                isinstance(d, bool) or not isinstance(d, int) or not 0 <= d < count for d in deps):
            raise ValueError("package %d has a dependency index out of range" % index)
        root = raw.get("root", False)
        if not isinstance(root, bool):
            raise ValueError("package %d root is not a boolean" % index)
        item = {"index": index, "name": name, "version": version,
                "source": raw.get("source"), "kind": kind, "dependencies": deps, "root": root}
        extra = {k: v for k, v in raw.items() if k not in KNOWN_PACKAGE_KEYS}
        if extra:
            item["extra"] = extra
        packages.append(item)
    return packages


def read_binary_info(path: str) -> dict:
    size = os.path.getsize(path)
    if size > MAX_BINARY_BYTES:
        raise InputError("binary exceeds 512 MiB: %s" % path)
    with open(path, "rb") as fh:
        data = fh.read()
    result = {
        "binary": os.path.basename(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": size,
        "found": False,
        "section": None,
        "packages": [],
        "root_indices": [],
        "dependency_edge_count": 0,
        "rustc_commits": [],
        "limitations": list(LIMITATIONS),
    }
    commits = {}
    for m in RUSTC_PATH_RE.finditer(data):
        key = m.group(1).decode("ascii")
        commits[key] = commits.get(key, 0) + 1
    result["rustc_commits"] = [{"commit": c, "count": n} for c, n in sorted(commits.items())]

    located = find_section(data, SECTION_NAME)
    if located is None:
        result["error"] = "no .dep-v0 section found in an ELF, PE or thin Mach-O header"
        return result
    offset, section_size = located
    if section_size == 0 or section_size > MAX_SECTION_BYTES or offset + section_size > len(data):
        result["section"] = {"name": SECTION_NAME, "file_offset": offset, "compressed_bytes": section_size}
        result["error"] = "the .dep-v0 section is empty, larger than 1 MiB, or runs past the file"
        return result
    blob = data[offset:offset + section_size]
    section = {"name": SECTION_NAME, "file_offset": offset, "compressed_bytes": section_size}
    result["section"] = section
    try:
        inflated = inflate_section(blob)
        doc = json.loads(inflated.decode("utf-8"))
        packages = decode_packages(doc)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        result["error"] = str(exc)
        return result
    section["uncompressed_bytes"] = len(inflated)
    section["format_version"] = doc.get("format")
    section["package_count"] = len(packages)
    result["found"] = True
    result["packages"] = packages
    result["root_indices"] = [p["index"] for p in packages if p["root"]]
    result["dependency_edge_count"] = sum(len(p["dependencies"]) for p in packages)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read the crate list and rustc commit from a Rust binary.")
    ap.add_argument("binary", help="Rust binary (ELF, PE or thin Mach-O)")
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
