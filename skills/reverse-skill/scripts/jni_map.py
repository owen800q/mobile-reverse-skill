#!/usr/bin/env python3
"""Map Java native methods to the Java_* exports of an Android shared library, offline.

Usage:
    jni_map.py LIB.so --out FILE [--java-root DIR] [--max-java-files N]

LIB.so is a little-endian ELF32 or ELF64 shared object. The tool reads its dynamic symbol
table and lists the defined functions whose names start with Java_. Those are the statically
registered JNI methods. It also reports two signs of dynamic registration: a defined JNI_OnLoad,
and an imported RegisterNatives. Nothing is executed.

With --java-root DIR (jadx sources, or any Java tree), the tool reads the .java files below DIR
and records each `native` method declaration with its binary class name. A nested class is named
Outer$Inner, as the JVM names it. A declaration's JNI base name is Java_<mangled class>_<mangled
method>. An export matches a declaration when its name equals that base, or when it is the base
followed by "__" and an overload signature. The signature is decoded for the analyst. It is not
compared with the Java parameter types.

Output: JSON in FILE (mode 0600) and a summary on stdout. Exit codes: 0 done; 2 usage or input
error, including a file that is not a little-endian ELF, a malformed section table, a file over
the size limit, a Java root that is not a directory, or an output path that is a symbolic link.
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys

MAX_ELF_BYTES = 256 * 1024 * 1024
MAX_JAVA_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_JAVA_FILES = 100000
SHT_DYNSYM = 11
STT_FUNC = 2
SHN_UNDEF = 0
JNI_PREFIX = "Java_"

LIMITATIONS = [
    "Methods bound with RegisterNatives in JNI_OnLoad are not resolved; read that table with the IDA workflow (references/ida-workflow.md)",
    "A RegisterNatives import shows that the library can register methods at run time. It does not show which Java method each table entry binds",
    "The Java side is read line by line, not parsed. A native declaration split across lines, or an unusual layout, is not recorded",
    "Overloaded exports are matched by name. The decoded signature is for the analyst to compare with the Java parameter types",
    "A declaration with no export may be implemented in another library or registered at run time. An export with no declaration may come from a Java tree that lacks that class",
    "Obfuscated names are matched as they appear in the tree. A renamed class or method does not match the export built from its original name",
]


class InputError(Exception):
    """Unreadable or malformed input, or unusable arguments. Exit code 2."""


def _cstring(blob: bytes, offset: int) -> str:
    if offset >= len(blob):
        return ""
    end = blob.find(b"\x00", offset)
    if end < 0:
        end = len(blob)
    return blob[offset:end].decode("utf-8", errors="replace")


def read_dynamic_symbols(data: bytes) -> dict:
    """Return the ELF class, the machine number and the dynamic symbols of a little-endian file."""
    try:
        return _read_dynamic_symbols(data)
    except struct.error as exc:
        raise InputError("truncated ELF structure: %s" % exc) from None


def _read_dynamic_symbols(data: bytes) -> dict:
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise InputError("not an ELF file")
    if data[5] != 1:
        raise InputError("only little-endian ELF is supported")
    if data[4] == 2:
        header = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
        sh_fmt, sh_min, sym_fmt, sym_len = "<IIQQQQIIQQ", 64, "<IBBHQQ", 24
        elf_class = "ELF64"
    elif data[4] == 1:
        header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
        sh_fmt, sh_min, sym_fmt, sym_len = "<IIIIIIIIII", 40, "<IIIBBH", 16
        elf_class = "ELF32"
    else:
        raise InputError("unknown ELF class")
    machine, shoff, shentsize, shnum = header[1], header[5], header[10], header[11]
    if shoff == 0 or shnum == 0 or shentsize < sh_min:
        raise InputError("no section table; not a shared library")

    def section(index: int):
        off = shoff + index * shentsize
        if index >= shnum or off + sh_min > len(data):
            raise InputError("section header %d is outside the file" % index)
        fields = struct.unpack_from(sh_fmt, data, off)
        return fields[1], fields[4], fields[5], fields[6]  # type, offset, size, link

    dynsym = None
    for index in range(shnum):
        sec = section(index)
        if sec[0] == SHT_DYNSYM:
            dynsym = sec
            break
    if dynsym is None:
        raise InputError("no dynamic symbol table; not a shared library")
    _, sym_off, sym_bytes, link = dynsym
    _, str_off, str_bytes, _ = section(link)
    if sym_off + sym_bytes > len(data) or str_off + str_bytes > len(data):
        raise InputError("dynamic symbol table or its string table is outside the file")
    strtab = data[str_off:str_off + str_bytes]
    symbols = []
    for k in range(sym_bytes // sym_len):
        pos = sym_off + k * sym_len
        if elf_class == "ELF64":
            name_off, info, _, shndx, value, size = struct.unpack_from(sym_fmt, data, pos)
        else:
            name_off, value, size, info, _, shndx = struct.unpack_from(sym_fmt, data, pos)
        symbols.append((_cstring(strtab, name_off), value, size, info & 0xF, shndx))
    return {"elf_class": elf_class, "machine": machine, "symbols": symbols}


def classify_symbols(symbols: list) -> tuple:
    """Return (exports, JNI_OnLoad defined, RegisterNatives imported) from the symbol tuples."""
    exports = []
    jni_onload = False
    register_natives = False
    for name, value, size, stype, shndx in symbols:
        if name == "RegisterNatives" and shndx == SHN_UNDEF:
            register_natives = True
        if not name or shndx == SHN_UNDEF or stype != STT_FUNC:
            continue
        if name == "JNI_OnLoad":
            jni_onload = True
        if name.startswith(JNI_PREFIX):
            exports.append({"symbol": name, "address": "0x%x" % value, "size": size})
    return exports, jni_onload, register_natives


def mangle(text: str, path: bool = False) -> str:
    """JNI name mangling. With path, '/' and '.' become '_', a package or class separator. Then
    '_' becomes _1, ';' becomes _2, '[' becomes _3, and any other character becomes _0 followed by
    four lowercase hex digits for each UTF-16 code unit."""
    out = []
    for ch in text:
        if path and ch in "/.":
            out.append("_")
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch == "_":
            out.append("_1")
        elif ch == ";":
            out.append("_2")
        elif ch == "[":
            out.append("_3")
        else:
            data = ch.encode("utf-16-be")
            out.extend("_0%04x" % unit for (unit,) in struct.iter_unpack(">H", data))
    return "".join(out)


def jni_base(binary_class: str, method: str) -> str:
    """The JNI name of a method without its overload signature."""
    return JNI_PREFIX + mangle(binary_class.replace(".", "/"), path=True) + "_" + mangle(method)


def candidate_bases(symbol: str):
    """The symbol itself, then each prefix that ends before a "__". A method name can contain "__"
    too, so every split is tried."""
    yield symbol
    pos = symbol.find("__")
    while pos >= 0:
        yield symbol[:pos]
        pos = symbol.find("__", pos + 1)


def demangle_signature(text: str) -> str:
    """Decode a mangled overload signature: _0xxxx is a character, _1 is '_', _2 is ';', _3 is '[',
    and a lone '_' is the '/' that separates the parts of a class name."""
    out = []
    i = 0
    while i < len(text):
        if text[i] != "_":
            out.append(text[i])
            i += 1
            continue
        nxt = text[i + 1:i + 2]
        hexdigits = text[i + 2:i + 6]
        if nxt == "0" and len(hexdigits) == 4 and all(c in "0123456789abcdefABCDEF" for c in hexdigits):
            out.append(chr(int(hexdigits, 16)))
            i += 6
        elif nxt == "1":
            out.append("_")
            i += 2
        elif nxt == "2":
            out.append(";")
            i += 2
        elif nxt == "3":
            out.append("[")
            i += 2
        else:
            out.append("/")
            i += 1
    return "".join(out)


PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*;", re.M)
TYPE_RE = re.compile(r"\b(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)|\brecord\s+([A-Za-z_$][\w$]*)\s*[(<]")
NATIVE_RE = re.compile(r"\bnative\b[^;{}=]*?\b([A-Za-z_$][\w$]*)\s*\(")
LEXICAL_RE = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', re.S)


def _blank(match) -> str:
    text = match.group(0)
    if text.startswith("//") or text.startswith("/*"):
        return "".join("\n" if ch == "\n" else " " for ch in text)
    return '""' if text[0] == '"' else "''"


def strip_java(text: str) -> str:
    """Blank out comments and string literals and keep the line breaks, so that braces and keywords
    inside them are not read."""
    return LEXICAL_RE.sub(_blank, text)


def natives_in_source(text: str, rel: str) -> list:
    """The native method declarations in one Java file, with their binary class names."""
    cleaned = strip_java(text)
    package_match = PACKAGE_RE.search(cleaned)
    package = re.sub(r"\s+", "", package_match.group(1)) if package_match else ""
    stack = []      # (simple name, brace depth of the class body)
    pending = None  # a class header whose body has not opened yet
    depth = 0
    found = []
    for lineno, line in enumerate(cleaned.split("\n"), 1):
        type_match = TYPE_RE.search(line)
        if type_match:
            pending = type_match.group(1) or type_match.group(2)
        native_match = NATIVE_RE.search(line)
        if native_match and stack:
            binary = "$".join(name for name, _ in stack)
            found.append({
                "class": ".".join(part for part in (package, binary) if part),
                "method": native_match.group(1),
                "file": rel,
                "line": lineno,
            })
        for ch in line:
            if ch == "{":
                depth += 1
                if pending is not None:
                    stack.append((pending, depth))
                    pending = None
            elif ch == "}":
                if stack and stack[-1][1] == depth:
                    stack.pop()
                depth = max(depth - 1, 0)
    return found


def scan_java_tree(root: str, max_files: int):
    """Scan the .java files below root. Returns (declarations, files scanned, files skipped, truncated)."""
    found = []
    scanned = skipped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fname in sorted(filenames):
            if not fname.endswith(".java"):
                continue
            path = os.path.join(dirpath, fname)
            if scanned >= max_files:
                return found, scanned, skipped, True
            if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > MAX_JAVA_BYTES:
                skipped += 1
                continue
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", errors="replace")
            scanned += 1
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            found.extend(natives_in_source(text, rel))
    return found, scanned, skipped, False


def match_exports(exports: list, natives: list) -> None:
    """Attach the Java declarations to each export and the exports to each declaration, in place."""
    index = {}
    for decl in natives:
        decl["jni_base"] = jni_base(decl["class"], decl["method"])
        decl["exports"] = []
        index.setdefault(decl["jni_base"], []).append(decl)
    for exp in exports:
        symbol = exp["symbol"]
        hits = []
        for base in candidate_bases(symbol):
            overloaded = base != symbol
            signature = demangle_signature(symbol[len(base) + 2:]) if overloaded else None
            for decl in index.get(base, []):
                hits.append({
                    "class": decl["class"],
                    "method": decl["method"],
                    "file": decl["file"],
                    "line": decl["line"],
                    "overloaded": overloaded,
                    "signature_jni": signature,
                })
                decl["exports"].append(symbol)
        exp["java"] = hits
        exp["status"] = "matched" if hits else "no_java_declaration"
        exp["ambiguous"] = len(hits) > 1
    for decl in natives:
        decl["status"] = "matched" if decl["exports"] else "no_export"


def write_output(path: str, result: dict) -> None:
    if os.path.islink(path):
        raise InputError("output path is a symbolic link; refusing to write through it")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(path, 0o600)


def run(library: str, out: str, java_root, max_java_files: int) -> dict:
    if max_java_files < 1:
        raise InputError("--max-java-files must be at least 1")
    if os.path.getsize(library) > MAX_ELF_BYTES:
        raise InputError("library is larger than %d bytes" % MAX_ELF_BYTES)
    with open(library, "rb") as fh:
        data = fh.read()
    elf = read_dynamic_symbols(data)
    exports, jni_onload, register_natives = classify_symbols(elf["symbols"])
    result = {
        "tool": "jni_map.py",
        "library": os.path.basename(library),
        "library_sha256": hashlib.sha256(data).hexdigest(),
        "elf": {"class": elf["elf_class"], "machine": elf["machine"], "dynamic_symbols": len(elf["symbols"])},
        "dynamic_registration": {"jni_onload_exported": jni_onload, "register_natives_imported": register_natives},
        "exports": exports,
        "limitations": list(LIMITATIONS),
    }
    summary = {"jni_exports": len(exports)}
    if java_root is not None:
        if not os.path.isdir(java_root):
            raise InputError("--java-root is not a directory")
        natives, scanned, skipped, truncated = scan_java_tree(java_root, max_java_files)
        match_exports(exports, natives)
        result["java"] = {
            "root": os.path.basename(os.path.normpath(java_root)),
            "files_scanned": scanned,
            "files_skipped": skipped,
            "truncated": truncated,
            "native_declarations": len(natives),
        }
        result["java_natives"] = natives
        summary.update({
            "java_natives": len(natives),
            "exports_matched": sum(1 for e in exports if e["status"] == "matched"),
            "exports_without_java": sum(1 for e in exports if e["status"] == "no_java_declaration"),
            "ambiguous_exports": sum(1 for e in exports if e["ambiguous"]),
            "java_natives_without_export": sum(1 for d in natives if d["status"] == "no_export"),
        })
    result["summary"] = summary
    write_output(out, result)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Map Java native methods to the Java_ exports of an ELF library.")
    ap.add_argument("library", help="little-endian ELF32 or ELF64 shared object")
    ap.add_argument("--out", required=True, help="output JSON file (mode 0600)")
    ap.add_argument("--java-root", default=None, help="directory of .java files, such as jadx sources")
    ap.add_argument("--max-java-files", type=int, default=DEFAULT_MAX_JAVA_FILES,
                    help="stop reading after this many .java files (default %d)" % DEFAULT_MAX_JAVA_FILES)
    args = ap.parse_args(argv)
    try:
        result = run(args.library, args.out, args.java_root, args.max_java_files)
    except (InputError, OSError, ValueError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
