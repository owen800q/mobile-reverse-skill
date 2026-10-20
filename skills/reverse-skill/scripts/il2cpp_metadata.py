#!/usr/bin/env python3
"""Inventory a Unity IL2CPP ``global-metadata.dat`` file: images, types and methods.

Usage:
    il2cpp_metadata.py METADATA [--detail summary|complete] [--out FILE]

Unity games built with IL2CPP ship a ``global-metadata.dat`` alongside
``libil2cpp.so`` (Android) or the ``il2cpp`` binary (other platforms). It holds the
managed-metadata tables the runtime uses to map native code back to .NET types and
methods, so decoding it recovers the assembly images, the type definitions (namespace,
name and nesting) and the method names that native analysis otherwise lacks. This reads
the file offline: it parses the serialized tables without running the game, loading
``libil2cpp.so`` or decrypting anything.

Supported layouts: ``global-metadata.dat`` format versions 29, 31 and 39, the versions
covering Unity 2020.2 through current releases. Versions 29 and 31 use fixed 4-byte
indices; version 39 records per-section counts and selects 1-, 2- or 4-byte index
widths from them, with the TypeIndex width recovered from the interfaceOffsets record
size (or the typeDefinition record size when interfaceOffsets is empty). A file that
does not start with the magic 0xFAB11BAF, or whose version is not one of these, is
refused rather than guessed at: packers that encrypt or restructure the metadata are
reported as unsupported, not misdecoded.

The decode is bounds-checked throughout. Section ranges must stay inside the file and
not overlap; record sizes must divide their sections; every string index must start a
NUL-terminated UTF-8 string (an index into the middle of another string is rejected, so
a shifted section fails loudly instead of returning a wrong name); type/method/nested
ranges must stay in range; nested-type links must form a forest (no cycles); each type
belongs to at most one image; and a type's method range and a method's declaring type
must agree in both directions. A damaged or hostile file raises a format error naming
the first inconsistency; it does not return partial rows that look authoritative.

Output: JSON on stdout, or to --out. Always present: the input's name, size and SHA-256;
the magic and metadata_version; the resolved index_widths and how the TypeIndex width
was derived; the 31-entry section table (name, offset, size, header count); the image
list (assembly name and its contiguous type range); and the collection counts. With
--detail complete, every type row (name, namespace, method range, nesting, enclosing
type) and method row (name, declaring type) is included inline; the default summary
omits those two arrays, which run to hundreds of thousands of rows on a large game, and
reports only their counts. Names are copied verbatim from the metadata; review the
output before sharing it. Exit codes: 0 decoded, 1 the file is not supported IL2CPP
metadata or is corrupt, 2 usage or input error. Standard library only.

Ported from morluto/rea's IL2CPP metadata inspector.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys

MAGIC = 0xFAB11BAF

# Header section order shared by global-metadata.dat versions 29, 31 and 39.
SECTION_NAMES = (
    "stringLiterals",
    "stringLiteralData",
    "strings",
    "events",
    "properties",
    "methods",
    "parameterDefaultValues",
    "fieldDefaultValues",
    "fieldAndParameterDefaultValueData",
    "fieldMarshaledSizes",
    "parameters",
    "fields",
    "genericParameters",
    "genericParameterConstraints",
    "genericContainers",
    "nestedTypes",
    "interfaces",
    "vtableMethods",
    "interfaceOffsets",
    "typeDefinitions",
    "images",
    "assemblies",
    "fieldRefs",
    "referencedAssemblies",
    "attributeData",
    "attributeDataRanges",
    "unresolvedIndirectCallParameterTypes",
    "unresolvedIndirectCallParameterRanges",
    "windowsRuntimeTypeNames",
    "windowsRuntimeStrings",
    "exportedTypeDefinitions",
)

SUPPORTED_VERSIONS = (29, 31, 39)

NESTED_TYPE_ENTRY_BYTES = 4

# indexing, typeDefinitionTypeIndices, methodReturnParameterToken.
VERSION_LAYOUTS = {
    29: ("fixed", 4, False),
    31: ("fixed", 4, True),
    39: ("counted", 3, True),
}

UNSUPPORTED_REASONS = frozenset({"unrecognized-magic", "unsupported-version"})


class Il2cppMetadataError(Exception):
    """A file that is not supported IL2CPP metadata, or is corrupt.

    ``kind`` is "unsupported" for inputs outside decoder coverage (wrong magic or
    version) and "corrupt" for a damaged or inconsistent metadata file.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.kind = "unsupported" if reason in UNSUPPORTED_REASONS else "corrupt"


def _section_entry_bytes(version: int) -> int:
    return 12 if VERSION_LAYOUTS[version][0] == "counted" else 8


def _header_bytes(version: int) -> int:
    return 8 + len(SECTION_NAMES) * _section_entry_bytes(version)


def _index_width(entries: int) -> int:
    """Width the runtime selects for an index into a collection of this many entries."""
    if entries <= 0xFF:
        return 1
    if entries <= 0xFFFF:
        return 2
    return 4


def _read_index(data: bytes, offset: int, width: int) -> int:
    """Read a serialized index; the all-ones value of a narrow width means -1."""
    if width == 1:
        value = data[offset]
        return -1 if value == 0xFF else value
    if width == 2:
        value = struct.unpack_from("<H", data, offset)[0]
        return -1 if value == 0xFFFF else value
    return struct.unpack_from("<i", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _record_bytes_sizes(widths: dict, version: int) -> dict:
    """Record sizes implied by the index widths of one metadata version."""
    _, type_def_type_indices, method_return_token = VERSION_LAYOUTS[version]
    return {
        # Two string indices, the type indices, a generic container index, flags,
        # eight int32 starts, eight uint16 counts, bitfield and token.
        "typeDefinitions": 68
        + type_def_type_indices * widths["type"]
        + widths["generic_container"],
        # Name, assembly, two type-definition starts with uint32 counts, entry point,
        # token, custom-attribute start and count.
        "images": 32 + 2 * widths["type_definition"],
        # Name, declaring type, return type, optional return token, parameter start,
        # generic container, token and four uint16 fields.
        "methods": 16
        + (4 if method_return_token else 0)
        + widths["type_definition"]
        + widths["type"]
        + widths["parameter"]
        + widths["generic_container"],
    }


def _read_header(data: bytes) -> dict:
    magic = _u32(data, 0) if len(data) >= 4 else None
    if len(data) < 8 or magic != MAGIC:
        raise Il2cppMetadataError(
            "unrecognized-magic",
            "the file does not start with the IL2CPP global-metadata magic 0xFAB11BAF; "
            "encrypted or non-metadata inputs are not decoded",
        )
    version = _i32(data, 4)
    if version not in SUPPORTED_VERSIONS:
        raise Il2cppMetadataError(
            "unsupported-version",
            f"metadata version {version} is not supported; versions "
            f"{', '.join(str(v) for v in SUPPORTED_VERSIONS)} are decoded",
        )
    header_bytes = _header_bytes(version)
    if len(data) < header_bytes:
        raise Il2cppMetadataError(
            "truncated-header",
            f"the file has {len(data)} bytes, fewer than the {header_bytes}-byte "
            f"version {version} header",
        )
    entry_bytes = _section_entry_bytes(version)
    sections = []
    for index, name in enumerate(SECTION_NAMES):
        at = 8 + index * entry_bytes
        sections.append(
            {
                "name": name,
                "offset": _i32(data, at),
                "size": _i32(data, at + 4),
                "count": _i32(data, at + 8) if entry_bytes == 12 else None,
            }
        )
    return {"magic": magic, "version": version, "header_bytes": header_bytes, "sections": sections}


def _check_sections(data: bytes, header_bytes: int, sections: list) -> None:
    first = sections[0]
    if first["offset"] != header_bytes:
        raise Il2cppMetadataError(
            "unexpected-header-size",
            f"stringLiterals starts at {first['offset']}, not immediately after the "
            f"{header_bytes}-byte header",
        )
    for section in sections:
        count = section["count"] or 0
        if (
            section["offset"] < 0
            or section["size"] < 0
            or count < 0
            or section["offset"] + section["size"] > len(data)
        ):
            raise Il2cppMetadataError(
                "section-out-of-bounds",
                f"section {section['name']} (offset {section['offset']}, size "
                f"{section['size']}, count {section['count']}) is negative or extends "
                f"past the {len(data)}-byte file",
            )
        if section["size"] > 0 and section["offset"] < header_bytes:
            raise Il2cppMetadataError(
                "section-out-of-bounds",
                f"section {section['name']} starts at {section['offset']}, inside the "
                f"{header_bytes}-byte header",
            )
    # Empty sections may share an offset with any neighbor; gaps are padding.
    occupied = sorted(
        (s for s in sections if s["size"] > 0), key=lambda s: s["offset"]
    )
    for index in range(1, len(occupied)):
        previous = occupied[index - 1]
        current = occupied[index]
        if previous["offset"] + previous["size"] > current["offset"]:
            raise Il2cppMetadataError(
                "section-overlap",
                f"section {previous['name']} [{previous['offset']}, "
                f"{previous['offset'] + previous['size']}) overlaps {current['name']} "
                f"starting at {current['offset']}",
            )


def _header_count(section: dict) -> int:
    if section["count"] is None:
        raise TypeError(f"section {section['name']} has no header count")
    return section["count"]


def _record_bytes(section: dict):
    """Record size from a counted header; None for an empty section."""
    count = _header_count(section)
    if count == 0:
        if section["size"] != 0:
            raise Il2cppMetadataError(
                "record-size-mismatch",
                f"section {section['name']} declares {section['size']} bytes for zero "
                "records",
            )
        return None
    if section["size"] % count != 0:
        raise Il2cppMetadataError(
            "record-size-mismatch",
            f"section {section['name']} size {section['size']} is not a whole multiple "
            f"of its {count} records",
        )
    return section["size"] // count


def _entries_in(section: dict, entry_bytes: int) -> int:
    """Entry count of a section whose header records only its size."""
    if section["size"] % entry_bytes != 0:
        raise Il2cppMetadataError(
            "record-size-mismatch",
            f"section {section['name']} size {section['size']} is not a whole multiple "
            f"of its {entry_bytes}-byte records",
        )
    return section["size"] // entry_bytes


FIXED_WIDTHS = {
    "type_definition": 4,
    "generic_container": 4,
    "parameter": 4,
    "type": 4,
    "type_width_source": "fixed-width-version",
}


def _resolve_widths(section) -> dict:
    type_definition = _index_width(_header_count(section("typeDefinitions")))
    generic_container = _index_width(_header_count(section("genericContainers")))
    parameter = _index_width(_header_count(section("parameters")))
    # TypeIndex counts native types, so its width is recovered from records.
    interface_offset = _record_bytes(section("interfaceOffsets"))
    if interface_offset is not None:
        type_width = interface_offset - 4
        source = "interface-offsets-record"
    else:
        type_definition_bytes = _record_bytes(section("typeDefinitions"))
        type_width = (
            None
            if type_definition_bytes is None
            else (type_definition_bytes - 68 - generic_container) / 3
        )
        source = "type-definition-record"
    if type_width not in (1, 2, 4):
        raise Il2cppMetadataError(
            "type-index-width",
            f"the {source} does not imply a 1-, 2- or 4-byte TypeIndex",
        )
    return {
        "type_definition": type_definition,
        "generic_container": generic_container,
        "parameter": parameter,
        "type": int(type_width),
        "type_width_source": source,
    }


def _record_counts(version: int, section, expected: dict) -> dict:
    names = ("typeDefinitions", "images", "methods")
    if VERSION_LAYOUTS[version][0] == "fixed":
        counts = {name: _entries_in(section(name), expected[name]) for name in names}
        counts["nestedTypes"] = _entries_in(section("nestedTypes"), NESTED_TYPE_ENTRY_BYTES)
        return counts
    for name in names:
        actual = _record_bytes(section(name))
        if actual is not None and actual != expected[name]:
            raise Il2cppMetadataError(
                "record-size-mismatch",
                f"section {name} records are {actual} bytes, but the index widths imply "
                f"{expected[name]}",
            )
    nested = section("nestedTypes")
    if nested["size"] != _header_count(nested) * NESTED_TYPE_ENTRY_BYTES:
        raise Il2cppMetadataError(
            "record-size-mismatch",
            f"section nestedTypes size {nested['size']} does not hold {nested['count']} "
            "4-byte entries",
        )
    return {
        "typeDefinitions": _header_count(section("typeDefinitions")),
        "images": _header_count(section("images")),
        "methods": _header_count(section("methods")),
        "nestedTypes": _header_count(nested),
    }


def _check_range(label: str, start: int, length: int, total: int) -> None:
    if length == 0 and -1 <= start <= total:
        return
    if start < 0 or start + length > total:
        raise Il2cppMetadataError(
            "index-out-of-range",
            f"{label} range [{start}, {start + length}) is outside the {total} "
            "available entries",
        )


def _make_string_reader(data: bytes, strings: dict):
    """Decode NUL-terminated UTF-8 names once each from the strings section.

    An index must start a string, so a shifted section or a pointer into another name
    fails instead of returning a different name.
    """
    offset = strings["offset"]
    pool = data[offset : offset + strings["size"]]
    cache: dict = {}

    def read(index: int, label: str) -> str:
        if index in cache:
            return cache[index]
        end = pool.find(b"\x00", index) if 0 <= index < len(pool) else -1
        if end == -1:
            raise Il2cppMetadataError(
                "invalid-string",
                f"{label} string index {index} has no terminated entry inside the "
                f"{strings['size']}-byte string section",
            )
        if index > 0 and pool[index - 1] != 0:
            raise Il2cppMetadataError(
                "invalid-string",
                f"{label} string index {index} starts inside another string",
            )
        try:
            value = pool[index:end].decode("utf-8")
        except UnicodeDecodeError:
            raise Il2cppMetadataError(
                "invalid-string",
                f"{label} string index {index} is not valid UTF-8",
            )
        cache[index] = value
        return value

    return read


def _read_images(data, section, widths, sizes, counts, read_string) -> list:
    images = section("images")
    type_total = counts["typeDefinitions"]
    width = widths["type_definition"]
    result = []
    for index in range(counts["images"]):
        at = images["offset"] + index * sizes["images"]
        image = {
            "name": read_string(_i32(data, at), f"image {index} name"),
            "type_start": _read_index(data, at + 8, width),
            "type_count": _u32(data, at + 8 + width),
        }
        _check_range(f"image {index} types", image["type_start"], image["type_count"], type_total)
        result.append(image)
    return result


def _read_types(data, section, widths, sizes, counts, read_string, type_def_type_indices) -> list:
    type_definitions = section("typeDefinitions")
    method_total = counts["methods"]
    types = []
    for index in range(counts["typeDefinitions"]):
        at = type_definitions["offset"] + index * sizes["typeDefinitions"]
        # int32 starts follow both string indices, the type indices, the generic
        # container index and flags.
        starts = at + 12 + type_def_type_indices * widths["type"] + widths["generic_container"]
        counts_at = starts + 32
        type_row = {
            "name": read_string(_i32(data, at), f"type {index} name"),
            "namespace": read_string(_i32(data, at + 4), f"type {index} namespace"),
            "method_start": _i32(data, starts + 4),
            "method_count": _u16(data, counts_at),
            "nested_type_start": _i32(data, starts + 16),
            "nested_type_count": _u16(data, counts_at + 8),
            "declaring_type": -1,
        }
        _check_range(f"type {index} methods", type_row["method_start"], type_row["method_count"], method_total)
        types.append(type_row)
    _assign_nesting(data, section, counts, types)
    return types


def _assign_nesting(data, section, counts, types) -> None:
    """Record each type's enclosing type from its declaring type's nestedTypes range."""
    nested_types = section("nestedTypes")
    for index, type_row in enumerate(types):
        _check_range(
            f"type {index} nested types",
            type_row["nested_type_start"],
            type_row["nested_type_count"],
            counts["nestedTypes"],
        )
        for offset in range(type_row["nested_type_count"]):
            nested = _i32(
                data,
                nested_types["offset"]
                + (type_row["nested_type_start"] + offset) * NESTED_TYPE_ENTRY_BYTES,
            )
            if not 0 <= nested < len(types):
                raise Il2cppMetadataError(
                    "index-out-of-range",
                    f"type {index} lists nested type {nested} outside the {len(types)} "
                    "type definitions",
                )
            if nested == index:
                raise Il2cppMetadataError(
                    "nested-type-conflict", f"type {index} lists itself as a nested type"
                )
            if types[nested]["declaring_type"] != -1:
                raise Il2cppMetadataError(
                    "nested-type-conflict",
                    f"type {nested} is listed as nested in type {index} and type "
                    f"{types[nested]['declaring_type']}",
                )
            types[nested]["declaring_type"] = index
    _reject_nesting_cycles(types)


def _reject_nesting_cycles(types) -> None:
    """Each enclosing chain must reach a top-level type."""
    # 0 unvisited, 1 on the current chain, 2 reaches a top-level type.
    state = bytearray(len(types))
    for first in range(len(types)):
        chain = []
        current = first
        while current != -1 and state[current] == 0:
            state[current] = 1
            chain.append(current)
            current = types[current]["declaring_type"]
        if current != -1 and state[current] == 1:
            raise Il2cppMetadataError(
                "nested-type-conflict",
                f"type {current} is nested inside itself through its declaring types",
            )
        for index in chain:
            state[index] = 2


def _read_methods(data, section, widths, sizes, counts, read_string) -> list:
    methods = section("methods")
    type_total = counts["typeDefinitions"]
    result = []
    for index in range(counts["methods"]):
        at = methods["offset"] + index * sizes["methods"]
        method = {
            "name": read_string(_i32(data, at), f"method {index} name"),
            "declaring_type": _read_index(data, at + 4, widths["type_definition"]),
        }
        if method["declaring_type"] < -1 or method["declaring_type"] >= type_total:
            raise Il2cppMetadataError(
                "index-out-of-range",
                f"method {index} declares type {method['declaring_type']} outside the "
                f"{type_total} type definitions",
            )
        result.append(method)
    return result


def _check_method_owners(types, methods) -> None:
    """Type method ranges and method declaring types must agree in both directions."""
    for index, type_row in enumerate(types):
        for offset in range(type_row["method_count"]):
            method = type_row["method_start"] + offset
            declaring = methods[method]["declaring_type"]
            if declaring != index:
                raise Il2cppMetadataError(
                    "declaring-type-mismatch",
                    f"method {method} is in type {index}'s range but declares type "
                    f"{declaring}",
                )
    for index, method in enumerate(methods):
        declaring = method["declaring_type"]
        if 0 <= declaring < len(types):
            owner = types[declaring]
            if index < owner["method_start"] or index >= owner["method_start"] + owner["method_count"]:
                raise Il2cppMetadataError(
                    "declaring-type-mismatch",
                    f"method {index} declares type {declaring} but is outside its method "
                    "range",
                )


def _check_image_ranges(images) -> None:
    """Each type belongs to at most one image."""
    ranges = sorted(
        (
            (image["type_start"], image["type_start"] + image["type_count"], index)
            for index, image in enumerate(images)
            if image["type_count"] > 0
        ),
        key=lambda entry: entry[0],
    )
    for at in range(1, len(ranges)):
        previous = ranges[at - 1]
        current = ranges[at]
        if previous[1] > current[0]:
            raise Il2cppMetadataError(
                "image-range-overlap",
                f"image {previous[2]} types [{previous[0]}, {previous[1]}) overlap image "
                f"{current[2]} starting at type {current[0]}",
            )


def read_il2cpp_metadata(data: bytes) -> dict:
    """Decode image, type and method names without native binaries or decryption."""
    header = _read_header(data)
    version = header["version"]
    _check_sections(data, header["header_bytes"], header["sections"])
    by_name = {entry["name"]: entry for entry in header["sections"]}

    def section(name):
        return by_name[name]

    indexing, type_def_type_indices, _ = VERSION_LAYOUTS[version]
    widths = _resolve_widths(section) if indexing == "counted" else dict(FIXED_WIDTHS)
    expected = _record_bytes_sizes(widths, version)
    counts = _record_counts(version, section, expected)
    read_string = _make_string_reader(data, section("strings"))

    images = _read_images(data, section, widths, expected, counts, read_string)
    _check_image_ranges(images)
    types = _read_types(
        data, section, widths, expected, counts, read_string, type_def_type_indices
    )
    methods = _read_methods(data, section, widths, expected, counts, read_string)
    _check_method_owners(types, methods)
    return {
        "magic": header["magic"],
        "metadata_version": version,
        "index_widths": widths,
        "sections": header["sections"],
        "images": images,
        "types": types,
        "methods": methods,
    }


def build_report(path: str, data: bytes, detail: str) -> dict:
    decoded = read_il2cpp_metadata(data)
    report = {
        "artifact": {
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        },
        "magic": decoded["magic"],
        "metadata_version": decoded["metadata_version"],
        "index_widths": decoded["index_widths"],
        "sections": decoded["sections"],
        "images": decoded["images"],
        "counts": {
            "images": len(decoded["images"]),
            "types": len(decoded["types"]),
            "methods": len(decoded["methods"]),
        },
    }
    if detail == "complete":
        report["types"] = decoded["types"]
        report["methods"] = decoded["methods"]
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("metadata", help="path to a Unity IL2CPP global-metadata.dat file")
    parser.add_argument(
        "--detail",
        choices=("summary", "complete"),
        default="summary",
        help="summary (default) reports images and collection counts; complete adds "
        "every type and method row inline",
    )
    parser.add_argument("--out", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        with open(args.metadata, "rb") as handle:
            data = handle.read()
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        report = build_report(args.metadata, data, args.detail)
    except Il2cppMetadataError as error:
        failure = {
            "artifact": {
                "path": args.metadata,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            },
            "decoded": False,
            "error_kind": error.kind,
            "error_reason": error.reason,
            "error": str(error),
        }
        text = json.dumps(failure, indent=2, ensure_ascii=False)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
        else:
            print(text)
        return 1

    report["decoded"] = True
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
