#!/usr/bin/env python3
"""Tests for scripts/go_buildinfo.py using synthetic binaries in the documented layout."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "go_buildinfo.py"
sys.path.insert(0, str(SCRIPT.parent))

import go_buildinfo as gb  # noqa: E402

SENT = bytes(range(16))  # stand-in for the toolchain's 16-byte sentinel


def uvarint(n: int) -> bytes:
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def inline_block(version: str, modinfo: str, flags: int = 0x2) -> bytes:
    header = gb.MAGIC + bytes([8, flags]) + bytes(gb.HEADER_SIZE - len(gb.MAGIC) - 2)
    body = uvarint(len(version)) + version.encode()
    text = (SENT + modinfo.encode() + SENT) if modinfo else b""
    body += uvarint(len(text)) + text
    return header + body


MODINFO = (
    "path\texample.com/cmd/app\n"
    "mod\texample.com/app\tv1.2.3\th1:abc=\n"
    "dep\tgolang.org/x/net\tv0.20.0\th1:def=\n"
    "=>\tgithub.com/fork/net\tv0.20.1\th1:ghi=\n"
    "dep\tgithub.com/pkg/errors\tv0.9.1\th1:jkl=\n"
    "build\tGOOS=linux\n"
    "build\tGOARCH=arm64\n"
    "build\tCGO_ENABLED=0\n"
    "build\tvcs.revision=0123abcd\n"
)


def write_binary(directory: Path, content: bytes) -> str:
    path = directory / "app.bin"
    path.write_bytes(content)
    return str(path)


class BuildInfoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_inline_block_is_decoded_with_modules_and_settings(self):
        binary = b"\x7fELF" + b"\x00" * 12 + b"junk" * 3
        binary += b"\x00" * (-len(binary) % 16) + inline_block("go1.22.3", MODINFO)
        result = gb.read_binary_info(write_binary(self.dir, binary))
        self.assertTrue(result["found"])
        self.assertEqual(result["go_version"], "go1.22.3")
        self.assertTrue(result["go_version_valid"])
        self.assertEqual(result["main_path"], "example.com/cmd/app")
        self.assertEqual(result["main_module"], {"path": "example.com/app", "version": "v1.2.3"})
        deps = {d["path"]: d for d in result["deps"]}
        self.assertEqual(deps["golang.org/x/net"]["replaced_by"]["path"], "github.com/fork/net")
        self.assertIsNone(deps["github.com/pkg/errors"]["replaced_by"])
        self.assertEqual(result["build"]["GOARCH"], "arm64")
        self.assertEqual(result["build"]["vcs.revision"], "0123abcd")

    def test_misaligned_block_is_not_read(self):
        binary = b"x" * 5 + inline_block("go1.22.3", MODINFO)
        result = gb.read_binary_info(write_binary(self.dir, binary))
        self.assertFalse(result["found"])
        self.assertEqual(result["block_count"], 0)

    def test_pointer_based_block_is_reported_undecoded(self):
        binary = inline_block("go1.17.13", MODINFO, flags=0x0)
        result = gb.read_binary_info(write_binary(self.dir, binary))
        self.assertFalse(result["found"])
        self.assertEqual(result["undecoded_blocks"], 1)
        self.assertEqual(result["blocks"][0]["encoding"], "pointer")

    def test_invalid_version_string_is_flagged(self):
        result = gb.read_binary_info(write_binary(self.dir, inline_block("not-a-go-version", MODINFO)))
        self.assertTrue(result["found"])
        self.assertFalse(result["go_version_valid"])

    def test_missing_modinfo_still_yields_the_version(self):
        result = gb.read_binary_info(write_binary(self.dir, inline_block("go1.21.0", "")))
        self.assertEqual(result["go_version"], "go1.21.0")
        self.assertIsNone(result["main_path"])
        self.assertEqual(result["deps"], [])

    def test_truncated_block_is_recorded_not_fatal(self):
        binary = gb.MAGIC + bytes([8, 0x2]) + bytes(gb.HEADER_SIZE - len(gb.MAGIC) - 2)
        binary = binary + uvarint(99) + b"short"
        result = gb.read_binary_info(write_binary(self.dir, binary + b"\x00" * 16))
        self.assertFalse(result["found"])
        self.assertIn("error", result["blocks"][0])

    def test_cli_exit_codes_and_private_output(self):
        ok = write_binary(self.dir, inline_block("go1.22.3", MODINFO))
        out = self.dir / "info" / "buildinfo.json"
        done = subprocess.run([sys.executable, str(SCRIPT), ok, "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["go_version"], "go1.22.3")
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)

        empty = write_binary(self.dir, b"\x00" * 64)
        done = subprocess.run([sys.executable, str(SCRIPT), empty], capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)

        done = subprocess.run([sys.executable, str(SCRIPT), str(self.dir / "missing")],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
