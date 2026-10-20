#!/usr/bin/env python3
"""Tests for il2cpp_metadata.py.

A small synthetic global-metadata.dat builder (ported from morluto/rea's fixture)
produces valid version 29, 31 and 39 files and deliberately damaged ones, so the
decoder is exercised end to end without shipping a real Unity artifact.
"""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCRIPT = SCRIPTS / "il2cpp_metadata.py"

spec = importlib.util.spec_from_file_location("il2cpp_metadata", SCRIPT)
il2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(il2)

SECTION_NAMES = il2.SECTION_NAMES

FIXTURE_IMAGES = [
    {"name": "Assembly-CSharp.dll", "type_start": 0, "type_count": 3},
    {"name": "mscorlib.dll", "type_start": 3, "type_count": 1},
]

FIXTURE_TYPES = [
    {"name": "Player", "namespace": "Game", "method_start": 0, "method_count": 2,
     "nested_type_start": 0, "nested_type_count": 1, "declaring_type": -1},
    {"name": "Slot", "namespace": "", "method_start": 2, "method_count": 1,
     "nested_type_start": -1, "nested_type_count": 0, "declaring_type": 0},
    {"name": "<Module>", "namespace": "", "method_start": -1, "method_count": 0,
     "nested_type_start": -1, "nested_type_count": 0, "declaring_type": -1},
    {"name": "Größe", "namespace": "System", "method_start": 3, "method_count": 2,
     "nested_type_start": -1, "nested_type_count": 0, "declaring_type": -1},
]

FIXTURE_METHODS = [
    {"name": ".ctor", "declaring_type": 0},
    {"name": "Update", "declaring_type": 0},
    {"name": "Add", "declaring_type": 1},
    {"name": ".ctor", "declaring_type": 3},
    {"name": "ToString", "declaring_type": 3},
]


def _width_for(entries):
    return 1 if entries <= 0xFF else 2 if entries <= 0xFFFF else 4


def _write_index(buf, offset, width, value):
    if width == 1:
        struct.pack_into("<B", buf, offset, 0xFF if value == -1 else value)
    elif width == 2:
        struct.pack_into("<H", buf, offset, 0xFFFF if value == -1 else value)
    else:
        struct.pack_into("<i", buf, offset, value)


def create_fixture(version=39, type_index_width=1, interface_offsets=True,
                   interface_offset_record_bytes=None, nesting_cycle=False,
                   empty_image=False, wide=None):
    """Build a synthetic global-metadata.dat; returns bytes plus expected rows."""
    wide = wide or {}
    fixed = version != 39
    T = 4 if fixed else type_index_width
    filler = wide.get("fillerTypes", 0)
    generic_containers = wide.get("genericContainers", 0)
    parameter_count = wide.get("parameters", 0)

    types = [dict(t) for t in FIXTURE_TYPES]
    methods = [dict(m) for m in FIXTURE_METHODS]
    last = len(FIXTURE_TYPES) + filler - 1
    for i in range(filler):
        types.append({
            "name": "Filler", "namespace": "",
            "method_start": len(FIXTURE_METHODS) if i == filler - 1 else -1,
            "method_count": 1 if i == filler - 1 else 0,
            "nested_type_start": -1, "nested_type_count": 0, "declaring_type": -1,
        })
    if filler:
        methods.append({"name": "Fill", "declaring_type": last})

    images = [dict(i) for i in FIXTURE_IMAGES]
    if empty_image:
        images.append({"name": "Empty.dll", "type_start": -1, "type_count": 0})

    D = 4 if fixed else _width_for(len(types))
    G = 4 if fixed else _width_for(generic_containers)
    P = 4 if fixed else _width_for(parameter_count)
    type_index_fields = 4 if fixed else 3
    return_token = 0 if version == 29 else 4

    type_rows = [dict(t) for t in types]
    nested_entries = [1, 0] if nesting_cycle else [1]
    if nesting_cycle:
        type_rows[1]["nested_type_start"] = 1
        type_rows[1]["nested_type_count"] = 1

    record_bytes = {
        "typeDefinitions": 68 + type_index_fields * T + G,
        "images": 32 + 2 * D,
        "methods": 16 + return_token + D + T + P + G,
    }

    string_index = {}
    string_parts = []
    string_bytes = [0]

    def intern(value):
        if value in string_index:
            return string_index[value]
        encoded = value.encode("utf-8") + b"\x00"
        string_index[value] = string_bytes[0]
        string_parts.append(encoded)
        string_bytes[0] += len(encoded)
        return string_index[value]

    for image in images:
        intern(image["name"])
    for t in FIXTURE_TYPES:
        intern(t["name"])
        intern(t["namespace"])
    for row in types + methods:
        intern(row["name"])
    strings = b"".join(string_parts)

    types_buf = bytearray(len(type_rows) * record_bytes["typeDefinitions"])
    for index, t in enumerate(type_rows):
        at = index * record_bytes["typeDefinitions"]
        struct.pack_into("<i", types_buf, at, intern(t["name"]))
        struct.pack_into("<i", types_buf, at + 4, intern(t["namespace"]))
        at += 8
        for _ in range(type_index_fields):
            _write_index(types_buf, at, T, 0x2A)
            at += T
        _write_index(types_buf, at, G, -1)
        at += G + 4
        starts = [-1, t["method_start"], -1, -1, t["nested_type_start"]]
        for field, value in enumerate(starts):
            struct.pack_into("<i", types_buf, at + field * 4, value)
        struct.pack_into("<i", types_buf, at + 20, -1)
        struct.pack_into("<i", types_buf, at + 24, -1)
        struct.pack_into("<i", types_buf, at + 28, -1)
        at += 32
        struct.pack_into("<H", types_buf, at, t["method_count"])
        struct.pack_into("<H", types_buf, at + 8, t["nested_type_count"])
        at += 16
        struct.pack_into("<I", types_buf, at, 0)
        struct.pack_into("<I", types_buf, at + 4, 0x02000001 + index)

    images_buf = bytearray(len(images) * record_bytes["images"])
    for index, image in enumerate(images):
        at = index * record_bytes["images"]
        struct.pack_into("<i", images_buf, at, intern(image["name"]))
        struct.pack_into("<i", images_buf, at + 4, index)
        _write_index(images_buf, at + 8, D, image["type_start"])
        struct.pack_into("<I", images_buf, at + 8 + D, image["type_count"])
        _write_index(images_buf, at + 12 + D, D, -1)
        struct.pack_into("<I", images_buf, at + 12 + 2 * D, 0)
        struct.pack_into("<i", images_buf, at + 16 + 2 * D, -1)

    methods_buf = bytearray(len(methods) * record_bytes["methods"])
    for index, method in enumerate(methods):
        at = index * record_bytes["methods"]
        struct.pack_into("<i", methods_buf, at, intern(method["name"]))
        _write_index(methods_buf, at + 4, D, method["declaring_type"])
        _write_index(methods_buf, at + 4 + D, T, 0)
        parameter_start = at + 4 + D + T + return_token
        _write_index(methods_buf, parameter_start, P, -1)
        _write_index(methods_buf, parameter_start + P, G, -1)
        struct.pack_into("<I", methods_buf, parameter_start + P + G, 0x06000001 + index)

    nested_buf = bytearray(len(nested_entries) * 4)
    for index, value in enumerate(nested_entries):
        struct.pack_into("<i", nested_buf, index * 4, value)

    interface_bytes = interface_offset_record_bytes
    if interface_bytes is None:
        interface_bytes = 4 + T

    contents = {
        "strings": (strings, len(string_index)),
        "methods": (bytes(methods_buf), len(methods)),
        "nestedTypes": (bytes(nested_buf), len(nested_entries)),
        "typeDefinitions": (bytes(types_buf), len(type_rows)),
        "images": (bytes(images_buf), len(images)),
    }
    if generic_containers:
        contents["genericContainers"] = (bytes(generic_containers * 16), generic_containers)
    if parameter_count:
        contents["parameters"] = (bytes(parameter_count * (8 + T)), parameter_count)
    if interface_offsets:
        contents["interfaceOffsets"] = (bytes(interface_bytes), 1)

    entry_bytes = 8 if fixed else 12
    header_bytes = 8 + len(SECTION_NAMES) * entry_bytes
    header = bytearray(header_bytes)
    struct.pack_into("<I", header, 0, 0xFAB11BAF)
    struct.pack_into("<i", header, 4, version)
    body = []
    cursor = header_bytes
    for index, name in enumerate(SECTION_NAMES):
        at = 8 + index * entry_bytes
        content = contents.get(name)
        struct.pack_into("<i", header, at, cursor)
        struct.pack_into("<i", header, at + 4, len(content[0]) if content else 0)
        if not fixed:
            struct.pack_into("<i", header, at + 8, content[1] if content else 0)
        if content:
            body.append(content[0])
            cursor += len(content[0])
    data = bytes(header) + b"".join(body)
    return data, {"images": images, "types": types, "methods": methods}


class Il2cppMetadataTests(unittest.TestCase):
    def _run(self, data, *args):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp)
        path = os.path.join(tmp, "global-metadata.dat")
        with open(path, "wb") as fh:
            fh.write(data)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), path, *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        return result, json.loads(result.stdout)

    def test_decodes_version_39_summary(self):
        data, expected = create_fixture(version=39)
        result, report = self._run(data)
        self.assertEqual(result.returncode, 0)
        self.assertIs(report["decoded"], True)
        self.assertEqual(report["metadata_version"], 39)
        self.assertEqual(report["magic"], il2.MAGIC)
        self.assertEqual(report["counts"], {"images": 2, "types": 4, "methods": 5})
        self.assertEqual([i["name"] for i in report["images"]],
                         [i["name"] for i in expected["images"]])
        self.assertNotIn("types", report)  # summary omits per-row arrays
        self.assertNotIn("methods", report)
        self.assertEqual(report["index_widths"]["type_definition"], 1)
        self.assertEqual(report["index_widths"]["type_width_source"], "interface-offsets-record")

    def test_complete_includes_rows_and_nesting(self):
        data, expected = create_fixture(version=39)
        _, report = self._run(data, "--detail", "complete")
        names = [(t["name"], t["namespace"], t["declaring_type"]) for t in report["types"]]
        self.assertIn(("Player", "Game", -1), names)
        self.assertIn(("Slot", "", 0), names)  # Slot nests inside Player via nestedTypes
        self.assertIn(("Größe", "System", -1), names)  # UTF-8 name round-trips
        self.assertEqual([m["name"] for m in report["methods"]],
                         [m["name"] for m in expected["methods"]])

    def test_fixed_width_versions_decode(self):
        for version in (29, 31):
            data, _ = create_fixture(version=version)
            _, report = self._run(data, "--detail", "complete")
            self.assertEqual(report["metadata_version"], version)
            self.assertEqual(report["index_widths"]["type_width_source"], "fixed-width-version")
            self.assertEqual(report["index_widths"]["type_definition"], 4)
            self.assertEqual(report["counts"]["methods"], 5)

    def test_wide_indices_select_two_byte_width(self):
        # 300 filler types push the type_definition index past one byte.
        data, _ = create_fixture(version=39,
                                 wide={"fillerTypes": 300, "genericContainers": 0, "parameters": 0})
        _, report = self._run(data)
        self.assertEqual(report["index_widths"]["type_definition"], 2)
        self.assertEqual(report["counts"]["types"], 304)

    def test_type_width_from_type_records_when_no_interface_offsets(self):
        data, _ = create_fixture(version=39, interface_offsets=False)
        _, report = self._run(data)
        self.assertEqual(report["index_widths"]["type_width_source"], "type-definition-record")
        self.assertEqual(report["index_widths"]["type"], 1)

    def test_bad_magic_is_unsupported(self):
        result, report = self._run(b"not metadata at all, really" + b"\x00" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertIs(report["decoded"], False)
        self.assertEqual(report["error_kind"], "unsupported")
        self.assertEqual(report["error_reason"], "unrecognized-magic")

    def test_unsupported_version(self):
        data = bytearray(create_fixture(version=39)[0])
        struct.pack_into("<i", data, 4, 24)  # version 24 is not decoded
        result, report = self._run(bytes(data))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["error_reason"], "unsupported-version")
        self.assertEqual(report["error_kind"], "unsupported")

    def test_nesting_cycle_is_corrupt(self):
        data, _ = create_fixture(version=39, nesting_cycle=True)
        result, report = self._run(data)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["error_kind"], "corrupt")
        self.assertEqual(report["error_reason"], "nested-type-conflict")

    def test_truncated_header_is_corrupt(self):
        data, _ = create_fixture(version=39)
        result, report = self._run(data[:20])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["error_kind"], "corrupt")
        self.assertEqual(report["error_reason"], "truncated-header")

    def test_empty_image_decodes(self):
        data, _ = create_fixture(version=39, empty_image=True)
        _, report = self._run(data)
        self.assertEqual(report["counts"]["images"], 3)
        self.assertEqual(report["images"][2]["name"], "Empty.dll")
        self.assertEqual(report["images"][2]["type_count"], 0)


if __name__ == "__main__":
    unittest.main()
