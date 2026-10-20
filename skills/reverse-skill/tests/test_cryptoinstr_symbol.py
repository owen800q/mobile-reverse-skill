#!/usr/bin/env python3
"""Tests for cryptoinstr.py --symbol selection (ported from morluto/rea).

The disassembler is stubbed, so these run without a real AArch64 binary or toolchain.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location("cryptoinstr", SCRIPTS / "cryptoinstr.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

AESE = "0000000000001000 <foo>:\n    1000: 4e284800 \taese v0.16b, v0.16b\n"
HEADER_ONLY = "x.so: file format elf64-littleaarch64\n"


class SymbolSelectorTests(unittest.TestCase):
    def test_gnu_and_llvm_use_their_own_flags(self):
        self.assertEqual(c._symbol_selector("objdump", "sign"), "--disassemble=sign")
        self.assertEqual(c._symbol_selector("aarch64-linux-gnu-objdump", "sign"),
                         "--disassemble=sign")
        self.assertEqual(c._symbol_selector("llvm-objdump", "sign"),
                         "--disassemble-symbols=sign")

    def test_absent_symbol_is_empty_scan_not_no_tool(self):
        # The tool runs but decodes nothing: ([], tool), never (None, None), so the
        # caller does not fall through to a whole-binary scan.
        self.set_tool(lambda cmd, path: HEADER_ONLY)
        insns, tool = c.disasm_with_objdump("x.so", symbol="missing")
        self.assertEqual(insns, [])
        self.assertIsNotNone(tool)

    def test_found_symbol_returns_instructions(self):
        self.set_tool(lambda cmd, path: AESE if "--disassemble=foo" in cmd else None)
        insns, tool = c.disasm_with_objdump("x.so", symbol="foo")
        self.assertEqual(insns, [("aese", "0x1000")])

    def test_run_exit_4_on_empty_symbol_scan(self):
        self.set_tool(lambda cmd, path: HEADER_ONLY)
        with tempfile.TemporaryDirectory() as d:
            binary = os.path.join(d, "lib.so")
            open(binary, "wb").close()
            self.assertEqual(c.run(binary, d, symbol="missing"), 4)

    def test_run_no_symbol_aware_tool_exits_3(self):
        self._which = c.shutil.which
        self._run = c._run_objdump
        self.addCleanup(self._restore)
        c.shutil.which = lambda n: None
        with tempfile.TemporaryDirectory() as d:
            binary = os.path.join(d, "lib.so")
            open(binary, "wb").close()
            self.assertEqual(c.run(binary, d, symbol="foo"), 3)

    def set_tool(self, run_objdump):
        self._which = c.shutil.which
        self._run = c._run_objdump
        self.addCleanup(self._restore)
        c.shutil.which = lambda n: "/usr/bin/" + n if n == "objdump" else None
        c._run_objdump = run_objdump

    def _restore(self):
        c.shutil.which = self._which
        c._run_objdump = self._run


if __name__ == "__main__":
    unittest.main()
