#!/usr/bin/env python3
"""Tests for scripts/binary_mitigations.py: golden checks against readelf, plus synthetic ELF."""
import contextlib
import ctypes.util
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "binary_mitigations.py"
sys.path.insert(0, str(SCRIPT.parent))

import binary_mitigations as bm  # noqa: E402

CANARY_NAMES = {"__stack_chk_fail", "__stack_chk_fail_local"}
FORTIFY_RE = re.compile(r"^__[a-z0-9_]+_chk$")


def readelf(*args):
    return subprocess.run(["readelf", *args], capture_output=True, text=True, check=False).stdout


def symbol_names(output):
    names = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0].rstrip(":").isdigit():
            names.append(parts[7].split("@")[0])
    return names


def readelf_expectation(path):
    """Expected verdicts derived from readelf output, independent of binary_mitigations."""
    header = readelf("-hW", path)
    prog = readelf("-lW", path)
    dyn = readelf("-dW", path)
    dyn_names = set(symbol_names(readelf("--dyn-syms", "-W", path)))
    static_names = set(symbol_names(readelf("-sW", path)))
    etype = re.search(r"Type:\s+(\S+)", header).group(1)
    interp = re.search(r"^\s*INTERP\b", prog, re.M) is not None
    stack = re.search(r"GNU_STACK\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+([RWE]+)\s+0x", prog)
    relro = re.search(r"^\s*GNU_RELRO\b", prog, re.M) is not None
    bind_now = "BIND_NOW" in dyn or re.search(r"FLAGS_1.*\bNOW\b", dyn) is not None
    if etype == "DYN":
        kind = "dyn-with-interp" if interp else "dyn-without-interp"
    elif etype == "EXEC":
        kind = "executable"
    else:
        kind = etype.lower()
    pie = {"dyn-with-interp": "yes", "executable": "no"}.get(kind, "not-applicable")
    if stack is None:
        nx = "unknown"
    elif "E" in stack.group(1):
        nx = "executable-stack"
    else:
        nx = "enabled"
    if not relro:
        relro_status = "none"
    else:
        relro_status = "full" if bind_now else "partial"
    canary = "present" if CANARY_NAMES & (dyn_names | static_names) else "not-found"
    return {
        "kind": kind,
        "pie": pie,
        "nx": nx,
        "relro": relro_status,
        "canary": canary,
        "fortify": len({n for n in dyn_names if FORTIFY_RE.match(n)}),
        "stripped": re.search(r"\.symtab\b", readelf("-SW", path)) is None,
    }


def system_binaries():
    candidates = [shutil.which("ls"), shutil.which("sh"), shutil.which("env"),
                  ctypes.util.find_library("c")]
    found = []
    for name in candidates:
        if not name:
            continue
        real = os.path.realpath(name)
        if os.path.isfile(real) and real not in found:
            found.append(real)
    if os.path.isfile("/lib/x86_64-linux-gnu/libc.so.6"):
        real = os.path.realpath("/lib/x86_64-linux-gnu/libc.so.6")
        if real not in found:
            found.append(real)
    return found


@unittest.skipUnless(shutil.which("readelf"), "readelf is not installed")
class ReadelfGoldenTests(unittest.TestCase):
    def test_verdicts_match_readelf_on_system_binaries(self):
        binaries = system_binaries()
        if not binaries:
            self.skipTest("no system ELF binaries found")
        for path in binaries:
            with self.subTest(binary=path):
                ours = bm.analyse(path, bm.DEFAULT_MAX_BYTES)
                expected = readelf_expectation(path)
                mitigations = ours["mitigations"]
                self.assertEqual(ours["kind"], expected["kind"])
                self.assertEqual(mitigations["pie"]["status"], expected["pie"])
                self.assertEqual(mitigations["nx"]["status"], expected["nx"])
                self.assertEqual(mitigations["relro"]["status"], expected["relro"])
                self.assertEqual(mitigations["canary"]["status"], expected["canary"])
                self.assertEqual(mitigations["fortify"]["count"], expected["fortify"])
                self.assertEqual(ours["symbols"]["stripped"], expected["stripped"])


def elf64_le_with_broken_symtab():
    """ELF64 with a readable .dynsym (no canary symbol) and a .symtab whose string-table link is missing."""
    header = b"\x7fELF" + bytes([2, 1, 1]) + b"\x00" * 9
    header += struct.pack("<HHIQQQIHHHHHH", 2, 62, 1, 0, 0, 120, 0, 64, 56, 0, 64, 4, 0)
    strtab = b"\x00puts\x00"
    dynsym = bytes(24) + struct.pack("<IBBHQQ", 1, 0x12, 0, 0, 0, 0)

    def section(sh_type, offset, size, link=0, entsize=0):
        return struct.pack("<IIQQQQIIQQ", 0, sh_type, 0, 0, offset, size, link, 0, 1, entsize)

    body = header + strtab + dynsym
    body += bytes(120 - len(body))
    sections = (bytes(64)
                + section(3, 64, len(strtab))
                + section(11, 70, len(dynsym), link=1, entsize=24)
                + section(2, 70, len(dynsym), link=9, entsize=24))
    return body + sections


class SyntheticElfTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, data):
        path = self.dir / name
        path.write_bytes(data)
        return str(path)

    def test_big_endian_64_bit_stack_flags(self):
        ident = b"\x7fELF" + bytes([2, 2, 1]) + b"\x00" * 9
        header = ident + struct.pack(">HHIQQQIHHHHHH", 2, 62, 1, 0, 64, 0, 0, 64, 56, 1, 64, 0, 0)
        rw = header + struct.pack(">IIQQQQQQ", 0x6474E551, 6, 0, 0, 0, 0, 0, 16)
        result = bm.analyse(self.write("be-rw", rw), bm.DEFAULT_MAX_BYTES)
        self.assertEqual((result["class"], result["endianness"], result["machine"]),
                         (64, "BE", "x86-64"))
        self.assertEqual(result["kind"], "executable")
        self.assertEqual(result["mitigations"]["nx"]["status"], "enabled")
        self.assertEqual(result["mitigations"]["pie"]["status"], "no")
        self.assertEqual(result["mitigations"]["relro"]["status"], "none")
        self.assertEqual(result["mitigations"]["canary"]["status"], "unknown")
        self.assertIsNone(result["mitigations"]["fortify"]["count"])
        self.assertTrue(result["symbols"]["stripped"])

        rwx = header + struct.pack(">IIQQQQQQ", 0x6474E551, 7, 0, 0, 0, 0, 0, 16)
        result = bm.analyse(self.write("be-rwx", rwx), bm.DEFAULT_MAX_BYTES)
        self.assertEqual(result["mitigations"]["nx"]["status"], "executable-stack")

    def test_little_endian_32_bit_layout_reads_flags_and_relro(self):
        ident = b"\x7fELF" + bytes([1, 1, 1]) + b"\x00" * 9
        header = ident + struct.pack("<HHIIIIIHHHHHH", 2, 3, 1, 0, 52, 0, 0, 52, 32, 2, 40, 0, 0)
        stack = struct.pack("<IIIIIIII", 0x6474E551, 0, 0, 0, 0, 0, 7, 4)
        relro = struct.pack("<IIIIIIII", 0x6474E552, 0, 0, 0, 0, 0, 4, 4)
        result = bm.analyse(self.write("le32", header + stack + relro), bm.DEFAULT_MAX_BYTES)
        self.assertEqual((result["class"], result["endianness"]), (32, "LE"))
        self.assertEqual(result["mitigations"]["nx"]["status"], "executable-stack")
        self.assertEqual(result["mitigations"]["relro"]["status"], "partial")

    def test_non_elf_file_exits_one_with_status(self):
        path = self.write("text.bin", b"plain text, not an executable\n")
        proc = subprocess.run([sys.executable, str(SCRIPT), path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["status"], "not_elf")

    def test_empty_and_truncated_magic_are_not_elf(self):
        for name, data in (("empty.bin", b""), ("tiny.bin", b"\x7fEL")):
            with self.subTest(name=name):
                path = self.write(name, data)
                proc = subprocess.run([sys.executable, str(SCRIPT), path], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(json.loads(proc.stdout)["status"], "not_elf")

    def test_unreadable_symbol_table_leaves_canary_unknown(self):
        path = self.write("broken-symtab", elf64_le_with_broken_symtab())
        result = bm.analyse(path, bm.DEFAULT_MAX_BYTES)
        self.assertEqual(result["mitigations"]["canary"]["status"], "unknown")
        self.assertEqual(result["mitigations"]["fortify"]["count"], 0)
        self.assertEqual(len(result["symbols"]["errors"]), 1)
        self.assertFalse(result["symbols"]["stripped"])

    def test_os_error_is_a_usage_error(self):
        path = self.write("ok.bin", b"x")
        with mock.patch.object(bm, "analyse", side_effect=OSError("permission denied")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(bm.main([path]), 2)
        self.assertIn("permission denied", err.getvalue())

    def test_truncated_header_is_reported_as_malformed(self):
        ident = b"\x7fELF" + bytes([2, 1, 1]) + b"\x00" * 9
        path = self.write("short.bin", ident + b"\x02\x00")
        proc = subprocess.run([sys.executable, str(SCRIPT), path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["status"], "malformed")

    def test_size_limit_and_missing_file_are_usage_errors(self):
        path = self.write("big.bin", b"\x7fELF" + b"\x00" * 64)
        too_big = subprocess.run([sys.executable, str(SCRIPT), path, "--max-bytes", "8"],
                                 capture_output=True, text=True)
        self.assertEqual(too_big.returncode, 2)
        missing = subprocess.run([sys.executable, str(SCRIPT), str(self.dir / "nope")],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
