#!/usr/bin/env python3
"""Identify a Flutter build from its APK or lib/<abi>/ directory: the Dart snapshot hash, engine build IDs and labeled version strings, and for one ABI the exported Dart AOT snapshot sections with a package: and dart: URI projection.

Usage:
    flutter_snapshot.py TARGET --out FILE [--abi ABI] [--max-pool N]

TARGET is an APK (or any zip) holding lib/<abi>/libapp.so and lib/<abi>/libflutter.so, or a
directory with the same lib/<abi>/ layout. Nothing is extracted to disk, executed, or looked up
externally. Mapping the snapshot hash to a Dart SDK release needs an external dataset, such as the
one reFlutter or Blutter use; this tool only reports the hash.

Identification scans byte patterns in every relevant library. The Dart snapshot hash sits 20 bytes
after each snapshot magic (f5 f5 dc dc). Engine facts are the GNU build-id from PT_NOTE segments
and labeled ASCII strings ("Dart VM version:", Android clang or LLVM lines). Release engines often
strip the version string; its absence is reported as null, not guessed.

AOT inspection reads the selected ABI's libapp.so. It locates the four _kDart*Snapshot* symbols
through the dynamic symbol table (jni_map.py's ELF reader: little-endian ELF32 or ELF64 with a
section table), checks each data section's header (magic, length, kind, hash), and projects
package: and dart: URIs from the isolate data section. The URI pool is a byte-pattern projection,
not a deserialized object graph.

Output: JSON in FILE (mode 0600) and a summary on stdout. Exit codes: 0 done; 2 usage or input
error, including a target with no zip or directory layout, an ELF that is not little-endian or has
no section table, an ABI that is not present, a library over the size limit, duplicate library
entries, or an output path that is a symbolic link. Standard library only; reuses jni_map.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jni_map as jm  # noqa: E402  (ELF symbol reader, vaddr mapping, output writer)

MAX_TARGET_BYTES = 2 * 1024 * 1024 * 1024
MAX_LIBRARY_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 768 * 1024 * 1024
MAX_CANDIDATES = 64
MAX_TOOLCHAIN_LINES = 4
DEFAULT_MAX_POOL = 500
ABI_PREFERENCE = ["arm64-v8a", "x86_64", "x86", "armeabi-v7a"]
LIBRARIES = ("libapp", "libflutter")
LIB_RE = re.compile(r"^lib/([^/]+)/(libapp|libflutter)\.so$")

DART_MAGIC = b"\xf5\xf5\xdc\xdc"
HASH_OFFSET = 20
HASH_LENGTH = 32
HASH_RE = re.compile(rb"[0-9a-f]{32}")
PRINTABLE_RUN = re.compile(rb"[\x20-\x7e]*")
DART_VERSION_LABEL = b"Dart VM version:"
DART_VERSION_RE = re.compile(rb"Dart VM version:[\x20-\x7e]{0,200}")
TOOLCHAIN_LABELS = (b"Android (", b"based on LLVM ")
TOOLCHAIN_RE = re.compile(
    rb"Android \([^)]{0,80}\) clang version [\x20-\x7e]{0,500}|based on LLVM \d[\x20-\x7e]{0,80}")
PACKAGE_URI_RE = re.compile(rb"package:[A-Za-z0-9_]+/[A-Za-z0-9_./\-]*")
DART_URI_RE = re.compile(rb"dart:[a-z_][a-z0-9_]*(?:/[A-Za-z0-9_./\-]*)?")

# Dart AOT snapshot symbols, in the order the report lists them.
AOT_SYMBOLS = (
    ("vm_data", "_kDartVmSnapshotData", True),
    ("vm_instructions", "_kDartVmSnapshotInstructions", False),
    ("isolate_data", "_kDartIsolateSnapshotData", True),
    ("isolate_instructions", "_kDartIsolateSnapshotInstructions", False),
)
SNAPSHOT_KIND_FULL_AOT = 3  # kind value of the FullAOT layout checked for complete structural coverage

LIMITATIONS = [
    "Identification scans bytes. A snapshot hash is reported as observed; it is not checked against any Dart SDK release",
    "snapshot_hash is set only when every observed hash agrees. Disagreeing hashes are kept as candidates with partial coverage",
    "The engine build-id comes from PT_NOTE segments only. A build-id that lies outside every declared note range is not reported",
    "Version and toolchain strings are reported verbatim when they carry their label. A release engine without the label reports null",
    "Structural checks require kind 3 (FullAOT in the Dart 2.14 layout). Other kinds keep their observed fields with partial coverage, because kind numbers vary across Dart releases",
    "The package: and dart: URI pool is a byte-pattern projection. It can include incidental matches and is bounded; a truncated pool reports partial coverage",
    "AOT inspection needs exported _kDart*Snapshot* symbols and a section table. A stripped image without them is refused, not guessed at",
    "Coverage is complete only for the parts that were read. Absence of libapp.so in every ABI is a complete negative answer",
]


class FlutterError(jm.InputError):
    """Input the tool refuses rather than reporting partial facts for."""


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _abi_order(abi):
    return (ABI_PREFERENCE.index(abi) if abi in ABI_PREFERENCE else len(ABI_PREFERENCE), abi)


def collect_libraries(target):
    """Return (target_sha256, {(abi, library): bytes}) for every lib/<abi>/libapp.so and libflutter.so."""
    if os.path.isdir(target):
        return None, _collect_directory(target)
    if not os.path.isfile(target):
        raise FlutterError("target is neither a file nor a directory")
    if os.path.getsize(target) > MAX_TARGET_BYTES:
        raise FlutterError("target is larger than %d bytes" % MAX_TARGET_BYTES)
    if not zipfile.is_zipfile(target):
        raise FlutterError("target is not an APK or zip, and not a directory with lib/<abi>/")
    digest = _sha256_file(target)
    with zipfile.ZipFile(target) as zf:
        members = {}
        total = 0
        for info in zf.infolist():
            match = LIB_RE.match(info.filename)
            if not match or info.is_dir():
                continue
            key = (match.group(1), match.group(2))
            if key in members:
                raise FlutterError("duplicate library entry for %s in %s" % ("/".join(key), info.filename))
            if info.file_size > MAX_LIBRARY_BYTES:
                raise FlutterError("%s is larger than %d bytes" % (info.filename, MAX_LIBRARY_BYTES))
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise FlutterError("libraries exceed the %d byte extraction budget" % MAX_TOTAL_BYTES)
            members[key] = info
        return digest, {key: zf.read(info) for key, info in members.items()}


def _collect_directory(root):
    libs_root = os.path.join(root, "lib")
    found = {}
    total = 0
    if not os.path.isdir(libs_root):
        return found
    for abi in sorted(os.listdir(libs_root)):
        for library in LIBRARIES:
            path = os.path.join(libs_root, abi, library + ".so")
            if not os.path.lexists(path):
                continue
            if os.path.islink(path):
                raise FlutterError("%s is a symbolic link; refusing to follow it" % path)
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            if size > MAX_LIBRARY_BYTES:
                raise FlutterError("%s is larger than %d bytes" % (path, MAX_LIBRARY_BYTES))
            total += size
            if total > MAX_TOTAL_BYTES:
                raise FlutterError("libraries exceed the %d byte extraction budget" % MAX_TOTAL_BYTES)
            with open(path, "rb") as fh:
                found[(abi, library)] = fh.read()
    return found


def scan_snapshot_hashes(data):
    """Every snapshot magic whose following 32 bytes are lowercase hex. Returns sources, candidates, capped."""
    sources = 0
    candidates = []
    capped = False
    pos = data.find(DART_MAGIC)
    while pos >= 0:
        field = data[pos + HASH_OFFSET:pos + HASH_OFFSET + HASH_LENGTH]
        if len(field) == HASH_LENGTH and HASH_RE.fullmatch(field):
            sources += 1
            text = field.decode("ascii")
            if text not in candidates:
                if len(candidates) >= MAX_CANDIDATES:
                    capped = True
                else:
                    candidates.append(text)
        pos = data.find(DART_MAGIC, pos + len(DART_MAGIC))
    return {"sources": sources, "candidates": candidates, "capped": capped}


def _labeled_run_start(data, at):
    """A label is taken only where its printable run begins, so a prefix glued to other text is not a label."""
    return at == 0 or not (0x20 <= data[at - 1] < 0x7F)


def scan_labeled_strings(data):
    """Dart VM version and toolchain lines, each verbatim. Malformed labeled runs set the capped flags."""
    version = None
    version_capped = False
    pos = data.find(DART_VERSION_LABEL)
    while pos >= 0:
        if _labeled_run_start(data, pos):
            run = PRINTABLE_RUN.match(data, pos).group()
            if not DART_VERSION_RE.fullmatch(run) or (version is not None and run.decode("ascii") != version):
                version_capped = True
            elif version is None:
                version = run.decode("ascii")
        pos = data.find(DART_VERSION_LABEL, pos + len(DART_VERSION_LABEL))

    lines = []
    toolchain_capped = False
    for label in TOOLCHAIN_LABELS:
        pos = data.find(label)
        while pos >= 0:
            if _labeled_run_start(data, pos):
                run = PRINTABLE_RUN.match(data, pos).group()
                if not TOOLCHAIN_RE.fullmatch(run):
                    toolchain_capped = True
                else:
                    text = run.decode("ascii")
                    if text not in lines:
                        if len(lines) >= MAX_TOOLCHAIN_LINES:
                            toolchain_capped = True
                        else:
                            lines.append(text)
            pos = data.find(label, pos + len(label))
    return {"dart_vm_version": version, "dart_vm_version_capped": version_capped,
            "toolchain_lines": lines, "toolchain_capped": toolchain_capped}


def read_build_ids(data):
    """GNU build-id notes from the PT_NOTE segments of a little-endian ELF. Returns ids, complete."""
    if len(data) < 52 or data[:4] != b"\x7fELF" or data[5] != 1:
        return [], False
    try:
        if data[4] == 2:
            phoff, = struct.unpack_from("<Q", data, 0x20)
            phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
            ph_min, seg = 56, "<IIQQQQQQ"
        elif data[4] == 1:
            phoff, = struct.unpack_from("<I", data, 0x1C)
            phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
            ph_min, seg = 32, "<IIIIIIII"
        else:
            return [], False
    except struct.error:
        return [], False
    if phnum == 0:
        return [], True
    if phentsize < ph_min or phoff + phnum * phentsize > len(data):
        return [], False
    ids = []
    complete = True
    for index in range(phnum):
        fields = struct.unpack_from(seg, data, phoff + index * phentsize)
        if fields[0] != 4:  # PT_NOTE
            continue
        if data[4] == 2:
            seg_off, seg_size = fields[2], fields[5]
        else:
            seg_off, seg_size = fields[1], fields[4]
        if seg_off + seg_size > len(data):
            complete = False
            continue
        pos, end = seg_off, seg_off + seg_size
        while pos + 12 <= end:
            namesz, descsz, ntype = struct.unpack_from("<III", data, pos)
            name_at = pos + 12
            desc_at = name_at + ((namesz + 3) & ~3)
            next_at = desc_at + ((descsz + 3) & ~3)
            if desc_at + descsz > end:
                complete = False
                break
            name = data[name_at:name_at + namesz]
            if ntype == 3 and name == b"GNU\x00":
                value = data[desc_at:desc_at + descsz].hex()
                if value not in ids:
                    ids.append(value)
            pos = next_at
    return ids, complete


def library_facts(data, library):
    """Per-library observations. libapp reports snapshot hashes; libflutter reports engine facts."""
    base = {"sha256": _sha256_bytes(data), "size": len(data)}
    if library == "libapp":
        hashes = scan_snapshot_hashes(data)
        base.update(snapshot_hash_sources=hashes["sources"],
                    snapshot_hash_candidates=hashes["candidates"],
                    snapshot_hash_capped=hashes["capped"])
        return base
    ids, notes_complete = read_build_ids(data)
    base["build_id_candidates"] = ids
    base["build_id"] = ids[0] if len(ids) == 1 and notes_complete else None
    base["build_id_complete"] = notes_complete
    base.update(scan_labeled_strings(data))
    return base


def _snapshot_header(data, offset, size):
    """Magic, length, kind and hash of a data section. Fields are read only when the magic matches."""
    if offset + 4 > len(data) or data[offset:offset + 4] != DART_MAGIC:
        return {"magic_valid": False, "kind": None, "header_length": None, "hash": None, "complete": False}
    fields_end = offset + HASH_OFFSET + HASH_LENGTH
    if fields_end > len(data):
        return {"magic_valid": True, "kind": None, "header_length": None, "hash": None, "complete": False}
    header_length, kind = struct.unpack_from("<QQ", data, offset + 4)
    field = data[offset + HASH_OFFSET:fields_end]
    hash_text = field.decode("ascii") if HASH_RE.fullmatch(field) else None
    complete = (
        kind == SNAPSHOT_KIND_FULL_AOT
        and header_length >= HASH_OFFSET + HASH_LENGTH - 4
        and header_length <= size - 4
        and hash_text is not None
    )
    return {"magic_valid": True, "kind": kind, "header_length": header_length,
            "hash": hash_text, "complete": complete}


def _uri_pool(region, pattern, max_pool):
    found = []
    seen = set()
    total = 0
    for match in pattern.finditer(region):
        text = match.group().decode("ascii")
        total += 1
        if text in seen:
            continue
        seen.add(text)
        found.append(text)
    kept = sorted(found)[:max_pool]
    return {"distinct": len(found), "occurrences": total, "retained": kept,
            "coverage": "complete" if len(kept) == len(found) else "partial"}


def inspect_aot(data, abi, max_pool):
    """Snapshot sections of one libapp.so: offsets, headers, hash agreement and the isolate URI pool."""
    symbols, loads, mapping_gaps = _elf_symbols(data)
    found = {}
    for name, value, size, stype, shndx in symbols:
        if not name.startswith("_kDart") or shndx == jm.SHN_UNDEF:
            continue
        found.setdefault(name, []).append((value, size))
    if not any(name in found for _, name, _ in AOT_SYMBOLS):
        raise FlutterError("no exported _kDart*Snapshot* symbols; the library is not a Dart AOT snapshot")

    coverage_partial = list(mapping_gaps)
    sections = {}
    hashes = {}
    isolate_region = None
    for key, name, is_data in AOT_SYMBOLS:
        entries = found.get(name, [])
        if not entries:
            coverage_partial.append("%s missing" % name)
            sections[key] = None
            continue
        if len(entries) > 1:
            coverage_partial.append("%s defined more than once" % name)
        value, size = entries[0]
        offset = jm.vaddr_to_offset(loads, value)
        if offset is None or offset + size > len(data):
            coverage_partial.append("%s is outside the file" % name)
            sections[key] = {"symbol": name, "offset": None, "size": size, "header": None}
            continue
        section = {"symbol": name, "offset": offset, "size": size, "header": None}
        if is_data:
            header = _snapshot_header(data, offset, size)
            section["header"] = {k: v for k, v in header.items() if k != "hash"}
            hashes[key] = header["hash"] if header["complete"] else None
            if not header["complete"]:
                coverage_partial.append("%s header is not a complete FullAOT layout" % name)
            if key == "isolate_data":
                isolate_region = data[offset:offset + size]
        sections[key] = section

    observed = [h for h in (hashes.get("vm_data"), hashes.get("isolate_data")) if h]
    if len(hashes) == 2 and len(observed) == 2 and observed[0] == observed[1]:
        snapshot_hash, hash_candidates = observed[0], [observed[0]]
    elif observed:
        snapshot_hash, hash_candidates = None, sorted(set(observed))
        coverage_partial.append("snapshot hash is not agreed by both sections")
    else:
        snapshot_hash, hash_candidates = None, []
        coverage_partial.append("no complete snapshot hash header")

    if isolate_region is not None:
        pool = {"package_uris": _uri_pool(isolate_region, PACKAGE_URI_RE, max_pool),
                "dart_uris": _uri_pool(isolate_region, DART_URI_RE, max_pool)}
        for part in pool.values():
            if part["coverage"] == "partial":
                coverage_partial.append("string pool truncated at %d entries" % max_pool)
                break
    else:
        pool = None
        coverage_partial.append("isolate data section unavailable for the URI pool")

    return {"sections": sections, "snapshot_hash": snapshot_hash,
            "snapshot_hash_candidates": hash_candidates, "string_pool": pool,
            "coverage": "partial" if coverage_partial else "complete",
            "coverage_gaps": coverage_partial}


def _elf_symbols(data):
    try:
        elf = jm.read_dynamic_symbols(data)
    except jm.InputError as exc:
        raise FlutterError(str(exc)) from None
    return elf["symbols"], elf["loads"], elf["mapping_gaps"]


def build_report(target, abi_request, max_pool):
    target_sha, libraries = collect_libraries(target)
    abis = sorted({abi for abi, _ in libraries}, key=_abi_order)
    per_abi = {}
    for abi in abis:
        app = libraries.get((abi, "libapp"))
        flutter = libraries.get((abi, "libflutter"))
        entry = {
            "libapp": library_facts(app, "libapp") if app is not None else None,
            "libflutter": library_facts(flutter, "libflutter") if flutter is not None else None,
        }
        gaps = []
        if app is None:
            gaps.append("libapp.so absent")
        if flutter is None:
            gaps.append("libflutter.so absent")
        entry["coverage"] = "partial" if gaps else "complete"
        entry["coverage_gaps"] = gaps
        per_abi[abi] = entry

    app_abis = [abi for abi in abis if per_abi[abi]["libapp"] is not None]
    detected = bool(app_abis)
    if abi_request is not None and abi_request not in app_abis:
        raise FlutterError("ABI %s has no libapp.so in this target" % abi_request)

    all_hashes = [c for abi in app_abis for c in per_abi[abi]["libapp"]["snapshot_hash_candidates"]]
    distinct_hashes = sorted(set(all_hashes))
    snapshot_hash = distinct_hashes[0] if len(distinct_hashes) == 1 else None
    hash_capped = any(per_abi[abi]["libapp"]["snapshot_hash_capped"] for abi in app_abis)

    gaps = []
    if detected:
        if snapshot_hash is None:
            gaps.append("snapshot hash is absent or disagrees across ABIs")
        if hash_capped:
            gaps.append("snapshot hash candidates exceed %d" % MAX_CANDIDATES)
        if any(per_abi[abi]["coverage"] == "partial" for abi in app_abis):
            gaps.append("an ABI carries only one of libapp.so and libflutter.so")
        engine_partial = any(
            per_abi[abi]["libflutter"]
            and (per_abi[abi]["libflutter"]["dart_vm_version_capped"]
                 or per_abi[abi]["libflutter"]["toolchain_capped"]
                 or not per_abi[abi]["libflutter"]["build_id_complete"])
            for abi in abis)
        if engine_partial:
            gaps.append("engine label or build-id coverage is partial")

    aot = None
    if detected:
        chosen = abi_request or app_abis[0]
        aot = {"abi": chosen}
        aot.update(inspect_aot(libraries[(chosen, "libapp")], chosen, max_pool))
    coverage = "partial" if gaps or (aot and aot["coverage"] == "partial") else "complete"

    return {
        "tool": "flutter_snapshot.py",
        "target": {"name": os.path.basename(os.path.normpath(target)), "sha256": target_sha},
        "flutter_detected": detected,
        "abis": per_abi,
        "snapshot_hash": snapshot_hash,
        "snapshot_hash_candidates": sorted(set(all_hashes)),
        "aot": aot,
        "coverage": coverage,
        "coverage_gaps": gaps,
        "limitations": LIMITATIONS,
    }


def run(target, out, abi_request, max_pool):
    if max_pool < 1:
        raise FlutterError("--max-pool must be at least 1")
    result = build_report(target, abi_request, max_pool)
    jm.write_output(out, result)
    return result


def _summary(result):
    lines = {
        "flutter_detected": result["flutter_detected"],
        "abis": sorted(result["abis"]),
        "snapshot_hash": result["snapshot_hash"],
        "coverage": result["coverage"],
    }
    if result["aot"]:
        lines["aot_abi"] = result["aot"]["abi"]
        lines["aot_snapshot_hash"] = result["aot"]["snapshot_hash"]
        lines["aot_coverage"] = result["aot"]["coverage"]
        pool = result["aot"]["string_pool"]
        if pool:
            lines["package_uris"] = pool["package_uris"]["distinct"]
            lines["dart_uris"] = pool["dart_uris"]["distinct"]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="Identify a Flutter build from its APK or lib/<abi>/ directory.")
    ap.add_argument("target", help="APK (zip) with lib/<abi>/libapp.so, or a directory with the same layout")
    ap.add_argument("--out", required=True, help="output JSON file (mode 0600)")
    ap.add_argument("--abi", default=None, help="ABI for AOT inspection (default arm64-v8a, x86_64, x86, armeabi-v7a, then the rest)")
    ap.add_argument("--max-pool", type=int, default=DEFAULT_MAX_POOL,
                    help="retain at most this many package: and dart: URIs (default %d)" % DEFAULT_MAX_POOL)
    args = ap.parse_args(argv)
    try:
        result = run(args.target, args.out, args.abi, args.max_pool)
    except (jm.InputError, OSError, ValueError, zipfile.BadZipFile) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
