#!/usr/bin/env python3

from __future__ import annotations

import io
import json
import lzma
import plistlib
import struct
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import playcover_qbdi_port as port  # noqa: E402


def make_macho(marker: bytes = b"fixture-code") -> bytes:
    section_offset = 0x4000
    segment_size = 72 + 80
    header = struct.pack(
        "<IiiIIIII",
        port.MH_MAGIC_64,
        port.CPU_TYPE_ARM64,
        0,
        2,
        1,
        segment_size,
        0x200085,
        0,
    )
    segment = struct.pack(
        "<II16sQQQQiiII",
        port.LC_SEGMENT_64,
        segment_size,
        b"__TEXT".ljust(16, b"\0"),
        0x100000000,
        0x8000,
        0,
        0x8000,
        7,
        5,
        1,
        0,
    )
    section = struct.pack(
        "<16s16sQQIIIIIIII",
        b"__text".ljust(16, b"\0"),
        b"__TEXT".ljust(16, b"\0"),
        0x100004000,
        0x100,
        section_offset,
        2,
        0,
        0,
        0x80000400,
        0,
        0,
        0,
    )
    blob = bytearray(0x8000)
    blob[: len(header)] = header
    blob[len(header) : len(header) + len(segment)] = segment
    blob[len(header) + len(segment) : len(header) + len(segment) + len(section)] = section
    blob[section_offset : section_offset + len(marker)] = marker
    return bytes(blob)


def make_engine() -> bytes:
    return (
        b"prefix\0"
        + port.OLD_CONFIG_ROOTS[0]
        + b"\0middle\0"
        + port.OLD_CONFIG_ROOTS[1]
        + b"\0suffix"
    )


def make_deb(path: Path, engine: bytes) -> None:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
        info = tarfile.TarInfo("./" + port.ENGINE_MEMBER)
        info.mode = 0o755
        info.size = len(engine)
        tf.addfile(info, io.BytesIO(engine))
    compressed = lzma.compress(tar_buffer.getvalue(), format=lzma.FORMAT_ALONE)

    def member(name: str, data: bytes) -> bytes:
        header = (
            f"{name + '/':<16}"
            f"{0:<12}"
            f"{0:<6}"
            f"{0:<6}"
            f"{0o100644:<8o}"
            f"{len(data):<10}`\n"
        ).encode("ascii")
        return header + data + (b"\n" if len(data) & 1 else b"")

    path.write_bytes(
        b"!<arch>\n"
        + member("debian-binary", b"2.0\n")
        + member("data.tar.lzma", compressed)
    )


class MachOPortTests(unittest.TestCase):
    def test_inject_load_command_preserves_code(self) -> None:
        original = make_macho()
        patched, change = port.inject_load_dylib(original, port.DEFAULT_LOAD_PATH)
        self.assertTrue(change["changed"])
        self.assertIn(port.DEFAULT_LOAD_PATH, port.dylib_paths(patched))
        before, _ = port.parse_macho(original)
        after, _ = port.parse_macho(patched)
        self.assertEqual(after.ncmds, before.ncmds + 1)
        self.assertEqual(patched[0x4000:0x400C], original[0x4000:0x400C])

    def test_second_injection_is_idempotent(self) -> None:
        once, _ = port.inject_load_dylib(make_macho(), port.DEFAULT_LOAD_PATH)
        twice, change = port.inject_load_dylib(once, port.DEFAULT_LOAD_PATH)
        self.assertFalse(change["changed"])
        self.assertEqual(once, twice)

    def test_refuses_nonzero_header_padding(self) -> None:
        blob = bytearray(make_macho())
        header, _ = port.parse_macho(blob)
        blob[port.MACH_HEADER_64_SIZE + header.sizeofcmds] = 1
        with self.assertRaises(port.PortError):
            port.inject_load_dylib(bytes(blob), port.DEFAULT_LOAD_PATH)


class EnginePortTests(unittest.TestCase):
    def test_patch_config_roots(self) -> None:
        patched, changes = port.patch_engine_config_roots(make_engine(), "/tmp/QBDITracer")
        self.assertEqual(len(changes), 2)
        self.assertEqual(patched.count(b"/tmp/QBDITracer"), 2)
        for old in port.OLD_CONFIG_ROOTS:
            self.assertNotIn(old, patched)

    def test_refuses_overlong_config_root(self) -> None:
        with self.assertRaises(port.PortError):
            port.patch_engine_config_roots(make_engine(), "/" + "x" * 100)


class EndToEndPortTests(unittest.TestCase):
    def test_port_app_copy_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            deb = root / "tracer.deb"
            make_deb(deb, make_engine())
            input_app = root / "Fixture.app"
            input_app.mkdir()
            with (input_app / "Info.plist").open("wb") as fh:
                plistlib.dump(
                    {
                        "CFBundleIdentifier": "test.qbdi.fixture",
                        "CFBundleExecutable": "Fixture",
                        "CFBundlePackageType": "APPL",
                    },
                    fh,
                )
            executable = input_app / "Fixture"
            executable.write_bytes(make_macho())
            executable.chmod(0o755)
            original_hash = port.sha256_file(executable)

            output_app = root / "Fixture-ported.app"
            manifest_path = root / "port-manifest.json"
            manifest = port.port_app(
                deb,
                input_app,
                output_app,
                port.DEFAULT_CONFIG_ROOT,
                port.DEFAULT_LOAD_PATH,
                manifest_path,
            )
            result = port.verify_ported_app(
                output_app, port.DEFAULT_CONFIG_ROOT, port.DEFAULT_LOAD_PATH
            )
            self.assertEqual(port.sha256_file(executable), original_hash)
            self.assertNotEqual(result["executable_sha256"], original_hash)
            self.assertEqual(manifest["input"]["bundle_id"], "test.qbdi.fixture")
            self.assertEqual(json.loads(manifest_path.read_text())["schema"], 1)


if __name__ == "__main__":
    unittest.main()
