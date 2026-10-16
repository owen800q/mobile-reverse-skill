#!/usr/bin/env python3
"""Map Java native methods to the Java_* exports and RegisterNatives tables of an Android library.

Usage:
    jni_map.py LIB.so --out FILE [--java-root DIR] [--max-java-files N]

LIB.so is a little-endian ELF32 or ELF64 shared object. The tool reads its dynamic symbol table
and lists the defined functions whose names start with Java_. Those are the statically registered
JNI methods. It also looks for RegisterNatives tables: static arrays of JNINativeMethod entries,
{name, signature, function}, whose pointers the loader fills in through relocations. Each table
entry is a candidate binding for a Java method, not a proven one. Nothing is executed.

With --java-root DIR (jadx sources, or any Java tree), the tool reads the .java files below DIR and
records each `native` method declaration with its binary class name, parameter types and return
type. A nested class is named Outer$Inner. An export matches a declaration when its name is the
declaration's JNI base name, or that base followed by "__" and an overload signature. A table entry
is a candidate for each declaration with the same name and parameter count. Its signature is
compared with the Java types by simple name only.

Output: JSON in FILE (mode 0600) and a summary on stdout. Exit codes: 0 done; 2 usage or input
error, including a file that is not a little-endian ELF, a malformed section or program header
table, a file over the size limit, a Java root that is not a directory, or an output path that is a
symbolic link. Standard library only.
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
MAX_CSTRING = 4096
SHT_RELA = 4
SHT_REL = 9
SHT_DYNSYM = 11
SHF_ALLOC = 2
PT_LOAD = 1
PF_X = 1
STT_FUNC = 2
SHN_UNDEF = 0
JNI_PREFIX = "Java_"
EM_386, EM_ARM, EM_X86_64, EM_AARCH64 = 3, 40, 62, 183
# (RELATIVE, absolute pointer) relocation types, for the machines whose tables the scan reads.
RELOC_TYPES = {EM_AARCH64: (1027, 257), EM_ARM: (23, 2), EM_X86_64: (8, 1), EM_386: (8, 1)}

NAME_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
DESCRIPTOR_RE = re.compile(r"\((?:\[*(?:[ZBCSIJFD]|L[^;()\[]+;))*\)(?:V|\[*(?:[ZBCSIJFD]|L[^;()\[]+;))")
PRIMITIVE_NAMES = {"Z": "boolean", "B": "byte", "C": "char", "S": "short", "I": "int", "J": "long",
                   "F": "float", "D": "double", "V": "void"}
MODIFIER_WORDS = {"public", "private", "protected", "static", "final", "synchronized", "abstract",
                  "strictfp", "transient", "volatile"}

LIMITATIONS = [
    "A RegisterNatives table is found only when the compiler laid it out as a static array of pointers that the loader relocates. A table built by code at run time is not found",
    "A table entry names a method and a signature, not a class. Its class is a candidate: a Java declaration with that name and signature. class_string_present says whether the library holds that class path as a string. It is a hint, not proof",
    "A function pointer is checked only to lie in an executable segment. It is not checked against the Java declaration",
    "Java types are compared by simple name. Type variables, and types that share a simple name in different packages, can compare unequal or equal by mistake",
    "A Java declaration whose parameter list spans lines, or holds parentheses inside an annotation, is not compared with tables",
    "The Java side is read line by line, not parsed. A native declaration split across lines, or an unusual layout, is not recorded",
    "Overloaded exports are matched by name. The decoded signature is for the analyst to compare with the Java parameter types",
    "A declaration with no export and no table entry may be implemented in another library. An export with no declaration may come from a Java tree that lacks that class",
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
    """Return the ELF class, machine, dynamic symbols, PT_LOAD segments and relocation sections."""
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
        is64 = True
        header = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
        sh_fmt, sh_min, sym_fmt, sym_len = "<IIQQQQIIQQ", 64, "<IBBHQQ", 24
        ph_fmt, ph_min = "<IIQQQQQQ", 56
        elf_class = "ELF64"
    elif data[4] == 1:
        is64 = False
        header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
        sh_fmt, sh_min, sym_fmt, sym_len = "<IIIIIIIIII", 40, "<IIIBBH", 16
        ph_fmt, ph_min = "<IIIIIIII", 32
        elf_class = "ELF32"
    else:
        raise InputError("unknown ELF class")
    machine, phoff, shoff = header[1], header[4], header[5]
    phentsize, phnum, shentsize, shnum = header[8], header[9], header[10], header[11]
    if shoff == 0 or shnum == 0 or shentsize < sh_min:
        raise InputError("no section table; not a shared library")

    def section(index: int):
        off = shoff + index * shentsize
        if index >= shnum or off + sh_min > len(data):
            raise InputError("section header %d is outside the file" % index)
        fields = struct.unpack_from(sh_fmt, data, off)
        # type, offset, size, link, flags, address
        return fields[1], fields[4], fields[5], fields[6], fields[2], fields[3]

    dynsym = None
    relocations = []
    for index in range(shnum):
        sec = section(index)
        if sec[0] == SHT_DYNSYM and dynsym is None:
            dynsym = sec
        elif sec[0] in (SHT_RELA, SHT_REL):
            relocations.append((sec[0], sec[1], sec[2]))
    if dynsym is None:
        raise InputError("no dynamic symbol table; not a shared library")
    _, sym_off, sym_bytes, link, sym_flags, sym_addr = dynsym
    _, str_off, str_bytes, _, str_flags, str_addr = section(link)
    if sym_off + sym_bytes > len(data) or str_off + str_bytes > len(data):
        raise InputError("dynamic symbol table or its string table is outside the file")
    strtab = data[str_off:str_off + str_bytes]
    symbols = []
    for k in range(sym_bytes // sym_len):
        pos = sym_off + k * sym_len
        if is64:
            name_off, info, _, shndx, value, size = struct.unpack_from(sym_fmt, data, pos)
        else:
            name_off, value, size, info, _, shndx = struct.unpack_from(sym_fmt, data, pos)
        symbols.append((_cstring(strtab, name_off), value, size, info & 0xF, shndx))

    loads = []
    if phnum and phoff:
        if phentsize < ph_min or phoff + phnum * phentsize > len(data):
            raise InputError("program header table is outside the file")
        for k in range(phnum):
            fields = struct.unpack_from(ph_fmt, data, phoff + k * phentsize)
            if is64:
                p_type, p_flags, p_off, p_vaddr, p_filesz = fields[0], fields[1], fields[2], fields[3], fields[5]
            else:
                p_type, p_off, p_vaddr, p_filesz, p_flags = fields[0], fields[1], fields[2], fields[4], fields[6]
            if p_type == PT_LOAD:
                loads.append({"vaddr": p_vaddr, "offset": p_off, "filesz": p_filesz, "flags": p_flags})
    mapping_gaps = (_mapping_gap("dynamic symbol table", sym_flags, sym_addr, sym_off, sym_bytes, loads)
                    + _mapping_gap("dynamic symbol string table", str_flags, str_addr, str_off, str_bytes, loads))
    return {"elf_class": elf_class, "machine": machine, "symbols": symbols, "loads": loads,
            "relocations": relocations, "mapping_gaps": mapping_gaps}


def _mapping_gap(label: str, flags: int, addr: int, offset: int, size: int, loads: list) -> list:
    """Why an allocated table's section offset is not its one file-backed PT_LOAD reading, or [].

    The loader reads an allocated table through PT_LOAD, not through its section offset. The
    symbols are still read from the section offset; a disagreement is reported as a coverage gap.
    """
    if not flags & SHF_ALLOC or size == 0:
        return []
    covering = [seg for seg in loads
                if seg["vaddr"] <= addr and addr + size <= seg["vaddr"] + seg["filesz"]]
    if len(covering) != 1:
        return ["%s is not covered by exactly one file-backed PT_LOAD segment" % label]
    mapped = covering[0]["offset"] + (addr - covering[0]["vaddr"])
    if mapped != offset:
        return ["%s section offset 0x%x disagrees with its PT_LOAD mapping 0x%x" % (label, offset, mapped)]
    return []


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


def vaddr_to_offset(loads: list, vaddr: int):
    """File offset of a virtual address inside a PT_LOAD segment, or None."""
    for seg in loads:
        if seg["vaddr"] <= vaddr < seg["vaddr"] + seg["filesz"]:
            return vaddr - seg["vaddr"] + seg["offset"]
    return None


def relocated_targets(data: bytes, elf: dict):
    """Pointer slots that relocations fill: ({slot address: value the loader writes}, supported).

    A RELATIVE relocation gives the value directly. An absolute relocation against a defined symbol
    gives that symbol's value plus the addend. Other types are skipped, and so are entries outside
    the file. A REL section has no addend in its entry, so the addend is read from the file at the
    slot. A machine without known relocation types gives supported False.
    """
    types = RELOC_TYPES.get(elf["machine"])
    if types is None:
        return {}, False
    relative, absolute = types
    is64 = elf["elf_class"] == "ELF64"
    ptr = 8 if is64 else 4
    mask = (1 << (8 * ptr)) - 1
    symbols = elf["symbols"]
    targets = {}
    for sec_type, off, size in elf["relocations"]:
        if is64:
            entry, fmt = (24, "<QQq") if sec_type == SHT_RELA else (16, "<QQ")
        else:
            entry, fmt = (12, "<IIi") if sec_type == SHT_RELA else (8, "<II")
        for k in range(size // entry):
            pos = off + k * entry
            if pos + entry > len(data):
                break
            fields = struct.unpack_from(fmt, data, pos)
            r_off, info = fields[0], fields[1]
            addend = fields[2] if sec_type == SHT_RELA else None
            if is64:
                rtype, sym = info & 0xFFFFFFFF, info >> 32
            else:
                rtype, sym = info & 0xFF, info >> 8
            if rtype not in (relative, absolute):
                continue
            if addend is None:
                at = vaddr_to_offset(elf["loads"], r_off)
                if at is None or at + ptr > len(data):
                    continue
                addend = int.from_bytes(data[at:at + ptr], "little")
            if rtype == relative:
                value = addend
            else:
                if sym >= len(symbols):
                    continue
                _, s_value, _, _, s_shndx = symbols[sym]
                if s_shndx == SHN_UNDEF:
                    continue
                value = s_value + addend
            targets[r_off] = value & mask
    return targets, True


def find_register_tables(data: bytes, elf: dict, targets: dict) -> list:
    """Runs of JNINativeMethod-shaped entries among the relocated pointer slots.

    An entry is three pointer slots in a row: a name that is a Java identifier, a signature that is a
    JNI method descriptor, and a function address inside an executable segment. A run of entries is
    one table, listed at the address of its first slot.
    """
    ptr = 8 if elf["elf_class"] == "ELF64" else 4
    stride = 3 * ptr
    loads = elf["loads"]

    def cstring(vaddr):
        at = vaddr_to_offset(loads, vaddr)
        if at is None:
            return None
        end = data.find(b"\x00", at, min(at + MAX_CSTRING, len(data)))
        if end < 0:
            return None
        raw = data[at:end]
        return raw.decode("ascii") if raw.isascii() else None

    def executable(vaddr):
        return any(seg["flags"] & PF_X and seg["vaddr"] <= vaddr < seg["vaddr"] + seg["filesz"]
                   for seg in loads)

    def entry_at(slot):
        if not all(slot + k * ptr in targets for k in range(3)):
            return None
        name = cstring(targets[slot])
        signature = cstring(targets[slot + ptr])
        function = targets[slot + 2 * ptr]
        if not name or not NAME_RE.fullmatch(name):
            return None
        if not signature or not DESCRIPTOR_RE.fullmatch(signature):
            return None
        if not executable(function):
            return None
        return {"name": name, "signature": signature, "function": "0x%x" % function}

    tables = []
    used = set()
    for slot in sorted(targets):
        if slot in used:
            continue
        entries = []
        pos = slot
        while True:
            entry = entry_at(pos)
            if entry is None:
                break
            entries.append(entry)
            pos += stride
        if entries:
            tables.append({"address": "0x%x" % slot, "entries": entries})
            used.update(range(slot, pos, ptr))
    return tables


def descriptor_type_names(signature: str):
    """Simple Java type names of a JNI method descriptor: (parameter types, return type)."""

    def one(i):
        dims = 0
        while signature[i] == "[":
            dims += 1
            i += 1
        if signature[i] == "L":
            end = signature.index(";", i)
            base = signature[i + 1:end].replace("$", "/").rsplit("/", 1)[-1]
            i = end + 1
        else:
            base = PRIMITIVE_NAMES[signature[i]]
            i += 1
        return base + "[]" * dims, i

    close = signature.index(")")
    params = []
    i = 1
    while i < close:
        name, i = one(i)
        params.append(name)
    ret, _ = one(close + 1)
    return params, ret


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
NATIVE_RE = re.compile(r"\bnative\b([^;{}=(]*?)\b([A-Za-z_$][\w$]*)\s*\(")
ANNOTATION_RE = re.compile(r"@[\w.]+(?:\s*\([^()]*\))?")
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


def strip_generics(text: str) -> str:
    while True:
        reduced = re.sub(r"<[^<>]*>", "", text)
        if reduced == text:
            return text
        text = reduced


def simple_java_name(text: str) -> str:
    """The simple name of a Java type: no package, no generics, array brackets kept."""
    compact = re.sub(r"\s+", "", text)
    found = re.fullmatch(r"([\w$.]*)((?:\[\])*)", compact)
    if not found:
        return compact.rsplit(".", 1)[-1]
    return found.group(1).rsplit(".", 1)[-1] + found.group(2)


def java_return_name(head: str) -> str:
    words = [w for w in ANNOTATION_RE.sub(" ", strip_generics(head)).split() if w not in MODIFIER_WORDS]
    return simple_java_name(words[-1]) if words else ""


def java_param_names(text: str):
    """Simple type names of a parameter list, or None when a part has no words."""
    text = strip_generics(ANNOTATION_RE.sub(" ", text))
    if not text.strip():
        return []
    names = []
    for part in text.split(","):
        words = re.sub(r"\bfinal\b", " ", part.replace("...", "[]")).split()
        if not words:
            return None
        extra = ""
        if len(words) > 1:
            found = re.search(r"((?:\[\])*)$", words[-1])
            extra = found.group(1) if found else ""
            words = words[:-1]
        names.append(simple_java_name("".join(words) + extra))
    return names


def call_args(line: str, pos: int):
    """The text from pos up to the parenthesis that closes the one before pos, on this line, or None."""
    depth = 1
    for i in range(pos, len(line)):
        if line[i] == "(":
            depth += 1
        elif line[i] == ")":
            depth -= 1
            if depth == 0:
                return line[pos:i]
    return None


def natives_in_source(text: str, rel: str) -> list:
    """The native method declarations in one Java file, with binary class names and simple types."""
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
            params_text = call_args(line, native_match.end())
            found.append({
                "class": ".".join(part for part in (package, binary) if part),
                "method": native_match.group(2),
                "file": rel,
                "line": lineno,
                "return_type": java_return_name(native_match.group(1)),
                "params": java_param_names(params_text) if params_text is not None else None,
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


def match_register_tables(tables: list, natives: list, data: bytes) -> None:
    """Attach table entries to the Java declarations they could bind, and the reverse, in place.

    A declaration is a candidate when its name and parameter count agree with the entry. The entry is
    an exact match when the simple parameter and return types agree too. Only exact matches set a
    declaration to registered_candidate.
    """
    library_strings = set(data.split(b"\x00"))
    for table in tables:
        for index, entry in enumerate(table["entries"]):
            want_params, want_return = descriptor_type_names(entry["signature"])
            hits = []
            for decl in natives:
                if decl["method"] != entry["name"] or decl["params"] is None:
                    continue
                if len(decl["params"]) != len(want_params):
                    continue
                exact = decl["params"] == want_params and decl["return_type"] == want_return
                class_path = decl["class"].replace(".", "/").encode("utf-8")
                hits.append({
                    "class": decl["class"],
                    "file": decl["file"],
                    "line": decl["line"],
                    "signature_match": exact,
                    "class_string_present": class_path in library_strings,
                })
                if exact:
                    decl.setdefault("table_entries", []).append({
                        "table": table["address"], "index": index, "function": entry["function"]})
            entry["java"] = hits
            entry["ambiguous"] = sum(1 for hit in hits if hit["signature_match"]) > 1
    for decl in natives:
        if decl.get("status") == "no_export" and decl.get("table_entries"):
            decl["status"] = "registered_candidate"


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
    targets, reloc_supported = relocated_targets(data, elf)
    tables = find_register_tables(data, elf, targets) if reloc_supported else []
    result = {
        "tool": "jni_map.py",
        "library": os.path.basename(library),
        "library_sha256": hashlib.sha256(data).hexdigest(),
        "elf": {"class": elf["elf_class"], "machine": elf["machine"], "dynamic_symbols": len(elf["symbols"]),
                "mapping_gaps": elf["mapping_gaps"]},
        "dynamic_registration": {"jni_onload_exported": jni_onload, "register_natives_imported": register_natives},
        "exports": exports,
        "register_natives": {"relocations_read": reloc_supported, "tables": tables},
        "limitations": list(LIMITATIONS),
    }
    summary = {
        "jni_exports": len(exports),
        "register_tables": len(tables),
        "register_entries": sum(len(t["entries"]) for t in tables),
    }
    if java_root is not None:
        if not os.path.isdir(java_root):
            raise InputError("--java-root is not a directory")
        natives, scanned, skipped, truncated = scan_java_tree(java_root, max_java_files)
        match_exports(exports, natives)
        match_register_tables(tables, natives, data)
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
            "java_natives_registered_candidate": sum(1 for d in natives if d["status"] == "registered_candidate"),
            "java_natives_without_export": sum(1 for d in natives if d["status"] == "no_export"),
            "register_entries_with_java": sum(1 for t in tables for e in t["entries"] if e["java"]),
        })
    result["summary"] = summary
    write_output(out, result)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Map Java native methods to the Java_ exports and RegisterNatives tables of an ELF library.")
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
