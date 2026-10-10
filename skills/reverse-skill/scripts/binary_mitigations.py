#!/usr/bin/env python3
"""Summarise static ELF hardening indicators: NX, PIE, RELRO, stack canary and fortify.

Usage:
    binary_mitigations.py PATH [--max-bytes N]

Reads the program headers, the dynamic section, and the dynamic and static symbol
names of one ELF file (32- or 64-bit, little or big endian). It never executes the
file and reads nothing outside it. Every field is a static inference:

  nx       PT_GNU_STACK without PF_X means the stack is not executable.
  pie      ET_DYN with PT_INTERP is reported as yes. That covers PIE executables and
           runnable shared libraries such as glibc's libc.so.6. ET_DYN without
           PT_INTERP is not-applicable (usually a shared object).
  relro    PT_GNU_RELRO. "full" also needs BIND_NOW (DT_FLAGS or DT_FLAGS_1).
  canary   __stack_chk_fail in the symbol tables. Its absence is not proof that
           functions are unprotected: canary code can be inlined or use other symbols.
           Unknown when a symbol table could not be read.
  fortify  *_chk symbols in the dynamic symbol table; null when that table is absent.

Output: one JSON object on stdout. Exit codes: 0 analysed, 1 not an ELF file or
malformed, 2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys

DEFAULT_MAX_BYTES = 512 * 1024 * 1024
MAX_PHDRS = 4096
MAX_SHDRS = 65535
MAX_DYN_ENTRIES = 4096
MAX_SYMBOLS = 500_000
MAX_TABLE_BYTES = 64 * 1024 * 1024  # unstripped desktop binaries carry string tables above 8 MiB
MAX_EXAMPLES = 10

PT_INTERP = 3
PT_DYNAMIC = 2
PT_GNU_STACK = 0x6474E551
PT_GNU_RELRO = 0x6474E552
PF_X = 0x1
DT_NULL = 0
DT_FLAGS = 30
DT_FLAGS_1 = 0x6FFFFFFB
DF_BIND_NOW = 0x8
DF_1_NOW = 0x1
SHT_SYMTAB = 2
SHT_DYNSYM = 11
ET_NAMES = {0: "NONE", 1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
E_MACHINE_NAMES = {
    3: "x86", 8: "MIPS", 20: "PowerPC", 21: "PowerPC64", 40: "ARM", 62: "x86-64",
    94: "Xtensa", 183: "AArch64", 243: "RISC-V",
}
CANARY_SYMBOLS = frozenset(("__stack_chk_fail", "__stack_chk_fail_local"))
FORTIFY_RE = re.compile(r"^__[a-z0-9_]+_chk$")

LIMITATIONS = [
    "Static inferences from program headers, dynamic tags and symbol names; nothing was executed",
    "A missing canary symbol is not proof that functions are unprotected; canary code can be inlined or use other symbols",
    "NX 'unknown' means there is no PT_GNU_STACK header; older toolchains defaulted to an executable stack",
    "Stripped binaries lack the static symbol table; dynamic symbols are still read when present",
    "PT_INTERP alone does not prove an executable: runnable shared libraries carry it too",
    "ET_DYN without PT_INTERP is reported as not-applicable for PIE, not as non-PIE",
]


class NotELF(Exception):
    """The file does not start with the ELF magic."""


class Malformed(Exception):
    """The ELF structures are inconsistent or exceed the read limits."""


def _read(fh, offset, size, limit=MAX_TABLE_BYTES):
    if size < 0 or size > limit:
        raise Malformed("table of %d bytes exceeds the read limit" % size)
    fh.seek(offset)
    data = fh.read(size)
    if len(data) != size:
        raise Malformed("truncated read of %d bytes at offset %d" % (size, offset))
    return data


def read_header(fh, file_size):
    fh.seek(0)
    if fh.read(4) != b"\x7fELF":
        raise NotELF()
    ident = _read(fh, 0, 16, 16)
    bits = {1: 32, 2: 64}.get(ident[4])
    order = {1: "<", 2: ">"}.get(ident[5])
    if bits is None or order is None:
        raise Malformed("invalid EI_CLASS or EI_DATA")
    head = _read(fh, 16, 48 if bits == 64 else 36, 64)
    fmt = order + ("HHIQQQIHHHHHH" if bits == 64 else "HHIIIIIHHHHHH")
    f = struct.unpack_from(fmt, head, 0)
    hdr = {
        "bits": bits, "order": order, "e_type": f[0], "e_machine": f[1],
        "phoff": f[4], "shoff": f[5], "phentsize": f[8], "phnum": f[9],
        "shentsize": f[10], "shnum": f[11],
    }
    if hdr["shoff"] and hdr["shoff"] > file_size:
        raise Malformed("section header table outside file")
    return hdr


def read_program_headers(fh, hdr, file_size):
    if hdr["phnum"] == 0:
        return []
    if hdr["phnum"] > MAX_PHDRS:
        raise Malformed("too many program headers")
    min_size = 56 if hdr["bits"] == 64 else 32
    if hdr["phentsize"] < min_size:
        raise Malformed("program header entry size %d is below %d" % (hdr["phentsize"], min_size))
    total = hdr["phnum"] * hdr["phentsize"]
    if hdr["phoff"] + total > file_size:
        raise Malformed("program header table outside file")
    raw = _read(fh, hdr["phoff"], total)
    order = hdr["order"]
    out = []
    for i in range(hdr["phnum"]):
        base = i * hdr["phentsize"]
        if hdr["bits"] == 64:
            p_type, p_flags, p_offset, _va, _pa, p_filesz = struct.unpack_from(
                order + "IIQQQQ", raw, base)
        else:
            p_type, p_offset, _va, _pa, p_filesz, _memsz, p_flags = struct.unpack_from(
                order + "IIIIIII", raw, base)
        out.append({"type": p_type, "flags": p_flags, "offset": p_offset, "filesz": p_filesz})
    return out


def read_dynamic_tags(fh, hdr, segment, file_size):
    if segment["offset"] + segment["filesz"] > file_size:
        raise Malformed("dynamic segment outside file")
    entry = 16 if hdr["bits"] == 64 else 8
    fmt = hdr["order"] + ("qQ" if hdr["bits"] == 64 else "iI")
    raw = _read(fh, segment["offset"], segment["filesz"])
    tags = {}
    for i in range(min(len(raw) // entry, MAX_DYN_ENTRIES)):
        tag, value = struct.unpack_from(fmt, raw, i * entry)
        if tag == DT_NULL:
            break
        tags.setdefault(tag, value)
    return tags


def read_sections(fh, hdr, file_size):
    if hdr["shnum"] == 0 or hdr["shoff"] == 0:
        return []
    if hdr["shnum"] > MAX_SHDRS:
        raise Malformed("too many section headers")
    min_size = 64 if hdr["bits"] == 64 else 40
    if hdr["shentsize"] < min_size:
        raise Malformed("section header entry size %d is below %d" % (hdr["shentsize"], min_size))
    total = hdr["shnum"] * hdr["shentsize"]
    if hdr["shoff"] + total > file_size:
        raise Malformed("section header table outside file")
    raw = _read(fh, hdr["shoff"], total)
    # Fields in order: name, type, flags, addr, offset, size, link, info, addralign, entsize.
    fmt = hdr["order"] + ("IIQQQQIIQQ" if hdr["bits"] == 64 else "IIIIIIIIII")
    out = []
    for i in range(hdr["shnum"]):
        fields = struct.unpack_from(fmt, raw, i * hdr["shentsize"])
        out.append({"type": fields[1], "offset": fields[4], "size": fields[5],
                    "link": fields[6], "entsize": fields[9]})
    return out


def read_symbol_names(fh, hdr, section, sections, file_size):
    if section["link"] >= len(sections):
        raise Malformed("symbol table links to a missing string table")
    strtab_section = sections[section["link"]]
    if section["offset"] + section["size"] > file_size or \
            strtab_section["offset"] + strtab_section["size"] > file_size:
        raise Malformed("symbol or string table outside file")
    min_entsize = 24 if hdr["bits"] == 64 else 16
    entsize = section["entsize"] or min_entsize
    if entsize < min_entsize:
        raise Malformed("symbol entry size %d is below %d" % (entsize, min_entsize))
    count = section["size"] // entsize
    if count > MAX_SYMBOLS:
        raise Malformed("symbol table has %d entries; the limit is %d" % (count, MAX_SYMBOLS))
    raw = _read(fh, section["offset"], count * entsize)
    strtab = _read(fh, strtab_section["offset"], strtab_section["size"])
    names = []
    for i in range(count):
        st_name = struct.unpack_from(hdr["order"] + "I", raw, i * entsize)[0]
        if st_name == 0 or st_name >= len(strtab):
            continue
        end = strtab.find(b"\x00", st_name)
        if end == -1:
            continue
        names.append(strtab[st_name:end].decode("ascii", "replace"))
    return names


def analyse(path, max_bytes):
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError("file is %d bytes; the limit is %d" % (size, max_bytes))
    with open(path, "rb") as fh:
        hdr = read_header(fh, size)
        phdrs = read_program_headers(fh, hdr, size)
        sections = read_sections(fh, hdr, size)

        interp = any(p["type"] == PT_INTERP for p in phdrs)
        stack = next((p for p in phdrs if p["type"] == PT_GNU_STACK), None)
        relro = any(p["type"] == PT_GNU_RELRO for p in phdrs)
        dynamic = next((p for p in phdrs if p["type"] == PT_DYNAMIC), None)
        tags = read_dynamic_tags(fh, hdr, dynamic, size) if dynamic else {}

        symbol_errors = []
        dynsym_names, symtab_names = None, None
        for section in sections:
            if section["type"] not in (SHT_DYNSYM, SHT_SYMTAB):
                continue
            try:
                names = read_symbol_names(fh, hdr, section, sections, size)
            except Malformed as exc:
                symbol_errors.append(str(exc))
                continue
            if section["type"] == SHT_DYNSYM:
                dynsym_names = (dynsym_names or []) + names
            else:
                symtab_names = (symtab_names or []) + names
        has_symtab = any(s["type"] == SHT_SYMTAB for s in sections)

    et = hdr["e_type"]
    if et == 2:
        kind, pie = "executable", "no"
    elif et == 3 and interp:
        # PIE executables carry PT_INTERP, and so do runnable shared libraries such as glibc's libc.so.6.
        kind, pie = "dyn-with-interp", "yes"
    elif et == 3:
        kind, pie = "dyn-without-interp", "not-applicable"
    elif et == 1:
        kind, pie = "relocatable", "not-applicable"
    elif et == 4:
        kind, pie = "core", "not-applicable"
    else:
        kind, pie = "unknown", "unknown"

    if stack is None:
        nx = {"status": "unknown", "evidence": "no PT_GNU_STACK header"}
    elif stack["flags"] & PF_X:
        nx = {"status": "executable-stack", "evidence": "PT_GNU_STACK flags 0x%x include PF_X" % stack["flags"]}
    else:
        nx = {"status": "enabled", "evidence": "PT_GNU_STACK flags 0x%x without PF_X" % stack["flags"]}

    if not relro:
        relro_info = {"status": "none", "evidence": "no PT_GNU_RELRO header"}
    else:
        bind_now = bool(tags.get(DT_FLAGS, 0) & DF_BIND_NOW) or bool(tags.get(DT_FLAGS_1, 0) & DF_1_NOW)
        relro_info = {
            "status": "full" if bind_now else "partial",
            "evidence": "PT_GNU_RELRO with BIND_NOW" if bind_now else "PT_GNU_RELRO without BIND_NOW",
        }

    symbol_names = (dynsym_names or []) + (symtab_names or [])
    readable = dynsym_names is not None or symtab_names is not None
    canary_hits = sorted(CANARY_SYMBOLS.intersection(symbol_names))
    if canary_hits:
        canary = {"status": "present", "evidence": "symbol %s" % canary_hits[0]}
    elif symbol_errors:
        canary = {"status": "unknown", "evidence": "a symbol table could not be read: %s" % symbol_errors[0]}
    elif readable:
        canary = {"status": "not-found", "evidence": "no canary symbol in the readable symbol tables"}
    else:
        canary = {"status": "unknown", "evidence": "no readable symbol table"}

    fortify_names = sorted(set(n for n in (dynsym_names or []) if FORTIFY_RE.match(n)))
    fortify_count = len(fortify_names) if dynsym_names is not None else None

    return {
        "path": os.path.abspath(path),
        "size": size,
        "sha256": _sha256(path),
        "format": "ELF",
        "class": hdr["bits"],
        "endianness": "LE" if hdr["order"] == "<" else "BE",
        "machine": E_MACHINE_NAMES.get(hdr["e_machine"], "unknown(%d)" % hdr["e_machine"]),
        "type": ET_NAMES.get(et, "unknown(%d)" % et),
        "kind": kind,
        "mitigations": {
            "nx": nx,
            "pie": {"status": pie, "evidence": "e_type %s, PT_INTERP %s"
                    % (ET_NAMES.get(et, et), "present" if interp else "absent")},
            "relro": relro_info,
            "canary": canary,
            "fortify": {"count": fortify_count, "examples": fortify_names[:MAX_EXAMPLES]},
        },
        "symbols": {
            "dynsym_names": len(dynsym_names) if dynsym_names is not None else None,
            "symtab_present": has_symtab,
            "stripped": not has_symtab,
            "errors": symbol_errors,
        },
        "limitations": list(LIMITATIONS),
    }


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser():
    ap = argparse.ArgumentParser(description="Summarise static ELF hardening indicators (JSON to stdout).")
    ap.add_argument("path", help="ELF file to inspect (read only, never executed)")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                    help="refuse files larger than this many bytes (default 512 MiB)")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not os.path.isfile(args.path):
        sys.stderr.write("ERROR: not a regular file: %s\n" % args.path)
        return 2
    if args.max_bytes < 1:
        sys.stderr.write("ERROR: --max-bytes must be at least 1\n")
        return 2
    try:
        report = analyse(args.path, args.max_bytes)
    except (ValueError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    except NotELF:
        print(json.dumps({"path": os.path.abspath(args.path), "status": "not_elf"}, indent=2))
        return 1
    except (Malformed, struct.error) as exc:
        print(json.dumps({"path": os.path.abspath(args.path), "status": "malformed",
                          "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
