#!/usr/bin/env python3
"""Tests for scripts/jni_map.py: ELF symbol reading, JNI name rules, Java declarations and matching."""
import contextlib
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import jni_map as jm  # noqa: E402

API_JAVA = '''package com.example;

import java.util.List;

public class Api {
    // public native void commented(); is a comment, not a declaration
    private static final String S = "native void inString(); {";
    public native String login(String user);
    public native void sign(String a);
    public native void sign(int a);
    public native void gone();
    static class Inner {
        protected native int run(long x);
    }
    public String plain() { return "native"; }
    /* native void blocked(); */
}
'''


def build_elf(symbols, bits=64, machine=183):
    """A minimal little-endian shared object: header, .dynstr, .dynsym, .shstrtab and section headers.
    Each symbol is (name, value, size, type, bind, shndx). An undefined symbol has shndx 0."""
    strtab = bytearray(b"\x00")
    if bits == 64:
        entries = [struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)]
    else:
        entries = [struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0)]
    for name, value, size, stype, bind, shndx in symbols:
        name_off = len(strtab)
        strtab += name.encode("ascii") + b"\x00"
        info = (bind << 4) | stype
        if bits == 64:
            entries.append(struct.pack("<IBBHQQ", name_off, info, 0, shndx, value, size))
        else:
            entries.append(struct.pack("<IIIBBH", name_off, value, size, info, 0, shndx))
    dynsym = b"".join(entries)
    shstrtab = b"\x00.dynstr\x00.dynsym\x00.shstrtab\x00"

    image = bytearray(64)

    def place(blob, align):
        image.extend(b"\x00" * (-len(image) % align))
        offset = len(image)
        image.extend(blob)
        return offset

    off_str = place(bytes(strtab), 1)
    off_sym = place(dynsym, 8)
    off_shs = place(shstrtab, 1)
    image.extend(b"\x00" * (-len(image) % 8))
    shoff = len(image)
    if bits == 64:
        sh = struct.Struct("<IIQQQQIIQQ")
        headers = [
            sh.pack(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            sh.pack(0, 3, 0, 0, off_str, len(strtab), 0, 0, 1, 0),
            sh.pack(0, 11, 0, 0, off_sym, len(dynsym), 1, 1, 8, 24),
            sh.pack(0, 3, 0, 0, off_shs, len(shstrtab), 0, 0, 1, 0),
        ]
        ident = b"\x7fELF" + bytes([2, 1, 1]) + b"\x00" * 9
        ehdr = struct.pack("<16sHHIQQQIHHHHHH", ident, 3, machine, 1, 0, 0, shoff, 0, 64, 0, 0, 64, 4, 3)
    else:
        sh = struct.Struct("<IIIIIIIIII")
        headers = [
            sh.pack(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            sh.pack(0, 3, 0, 0, off_str, len(strtab), 0, 0, 1, 0),
            sh.pack(0, 11, 0, 0, off_sym, len(dynsym), 1, 1, 4, 16),
            sh.pack(0, 3, 0, 0, off_shs, len(shstrtab), 0, 0, 1, 0),
        ]
        ident = b"\x7fELF" + bytes([1, 1, 1]) + b"\x00" * 9
        ehdr = struct.pack("<16sHHIIIIIHHHHHH", ident, 3, machine, 1, 0, 0, shoff, 0, 52, 0, 0, 40, 4, 3)
    image[:len(ehdr)] = ehdr
    image.extend(b"".join(headers))
    return bytes(image)


def run_main(argv):
    """Run the CLI with its output captured, so the test log stays readable."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return jm.main(argv)


class ElfReadTests(unittest.TestCase):
    def test_static_exports_and_registration_signs_in_elf64(self):
        data = build_elf([
            ("Java_com_example_Api_login", 0x1000, 0x40, 2, 1, 5),
            ("Java_com_example_Api_sign__ILjava_lang_String_2", 0x1100, 0x20, 2, 1, 5),
            ("JNI_OnLoad", 0x2000, 0x10, 2, 1, 5),
            ("helper", 0x3000, 0x10, 2, 1, 5),
            ("RegisterNatives", 0, 0, 2, 1, 0),
        ])
        elf = jm.read_dynamic_symbols(data)
        exports, jni_onload, register_natives = jm.classify_symbols(elf["symbols"])
        self.assertEqual([e["symbol"] for e in exports],
                         ["Java_com_example_Api_login", "Java_com_example_Api_sign__ILjava_lang_String_2"])
        self.assertEqual(exports[0]["address"], "0x1000")
        self.assertTrue(jni_onload)
        self.assertTrue(register_natives)
        self.assertEqual((elf["elf_class"], elf["machine"]), ("ELF64", 183))

    def test_elf32_is_read(self):
        data = build_elf([("Java_com_example_Api_login", 0x80, 0x10, 2, 1, 3)], bits=32, machine=40)
        elf = jm.read_dynamic_symbols(data)
        exports, jni_onload, register_natives = jm.classify_symbols(elf["symbols"])
        self.assertEqual([e["symbol"] for e in exports], ["Java_com_example_Api_login"])
        self.assertEqual((jni_onload, register_natives, elf["elf_class"]), (False, False, "ELF32"))

    def test_non_elf_big_endian_and_truncated_inputs_are_refused(self):
        good = build_elf([("Java_com_example_Api_login", 0x80, 0x10, 2, 1, 3)])
        big_endian = bytearray(good)
        big_endian[5] = 2
        for blob in (b"MZ" + b"\x00" * 100, bytes(big_endian), good[:200], good[:40]):
            with self.subTest(length=len(blob)):
                with self.assertRaises(jm.InputError):
                    jm.read_dynamic_symbols(blob)


class NameTests(unittest.TestCase):
    def test_mangle_follows_the_jni_rules(self):
        self.assertEqual(jm.mangle("login"), "login")
        self.assertEqual(jm.mangle("my_var"), "my_1var")
        self.assertEqual(jm.mangle("Outer$Inner"), "Outer_00024Inner")
        self.assertEqual(jm.mangle("com/example/Api", path=True), "com_example_Api")
        self.assertEqual(jm.mangle("a;b[c"), "a_2b_3c")
        self.assertEqual(jm.mangle("é"), "_000e9")

    def test_jni_base_names(self):
        self.assertEqual(jm.jni_base("com.example.Api", "login"), "Java_com_example_Api_login")
        self.assertEqual(jm.jni_base("com.example.Api$Inner", "run"), "Java_com_example_Api_00024Inner_run")
        self.assertEqual(jm.jni_base("com.example.Api", "_hidden"), "Java_com_example_Api__1hidden")

    def test_signature_decoding(self):
        self.assertEqual(jm.demangle_signature("ILjava_lang_String_2"), "ILjava/lang/String;")
        self.assertEqual(jm.demangle_signature("_3BI"), "[BI")
        self.assertEqual(jm.demangle_signature("_1"), "_")

    def test_every_double_underscore_is_a_candidate_split(self):
        self.assertEqual(list(jm.candidate_bases("Java_C__1x__Lfoo_2")),
                         ["Java_C__1x__Lfoo_2", "Java_C", "Java_C__1x"])


class JavaDeclarationTests(unittest.TestCase):
    def test_native_declarations_with_binary_class_names(self):
        found = jm.natives_in_source(API_JAVA, "com/example/Api.java")
        self.assertEqual(
            [(d["class"], d["method"]) for d in found],
            [("com.example.Api", "login"), ("com.example.Api", "sign"), ("com.example.Api", "sign"),
             ("com.example.Api", "gone"), ("com.example.Api$Inner", "run")],
        )
        self.assertEqual(found[0]["line"], 8)
        self.assertEqual(found[0]["file"], "com/example/Api.java")

    def test_comments_and_strings_are_not_declarations(self):
        found = jm.natives_in_source(API_JAVA, "Api.java")
        names = {d["method"] for d in found}
        self.assertFalse({"commented", "inString", "blocked", "plain"} & names)


class MatchingCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.src = self.dir / "sources" / "com" / "example"
        self.src.mkdir(parents=True)
        (self.src / "Api.java").write_text(API_JAVA, encoding="utf-8")
        self.lib = self.dir / "libdemo.so"
        self.lib.write_bytes(build_elf([
            ("Java_com_example_Api_login", 0x1000, 0x40, 2, 1, 5),
            ("Java_com_example_Api_sign__Ljava_lang_String_2", 0x1100, 0x20, 2, 1, 5),
            ("Java_com_example_Api_00024Inner_run", 0x1200, 0x20, 2, 1, 5),
            ("Java_com_example_Other_init", 0x1300, 0x20, 2, 1, 5),
            ("JNI_OnLoad", 0x2000, 0x10, 2, 1, 5),
        ]))
        self.out = self.dir / "out" / "jni.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_matches_declarations_and_reports_the_gaps(self):
        code = run_main([str(self.lib), "--out", str(self.out), "--java-root", str(self.dir / "sources")])
        self.assertEqual(code, 0)
        result = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(result["summary"], {
            "jni_exports": 4,
            "java_natives": 5,
            "exports_matched": 3,
            "exports_without_java": 1,
            "ambiguous_exports": 1,
            "java_natives_without_export": 1,
        })
        by_symbol = {e["symbol"]: e for e in result["exports"]}
        self.assertEqual(by_symbol["Java_com_example_Api_login"]["status"], "matched")
        self.assertEqual(by_symbol["Java_com_example_Api_login"]["java"][0]["line"], 8)
        self.assertEqual(by_symbol["Java_com_example_Other_init"]["status"], "no_java_declaration")
        sign = by_symbol["Java_com_example_Api_sign__Ljava_lang_String_2"]
        self.assertTrue(sign["ambiguous"])
        self.assertTrue(all(hit["overloaded"] for hit in sign["java"]))
        self.assertEqual(sign["java"][0]["signature_jni"], "Ljava/lang/String;")
        gone = [d for d in result["java_natives"] if d["method"] == "gone"][0]
        self.assertEqual(gone["status"], "no_export")

    def test_output_is_private_and_holds_no_absolute_paths(self):
        code = run_main([str(self.lib), "--out", str(self.out), "--java-root", str(self.dir / "sources")])
        self.assertEqual(code, 0)
        self.assertEqual(os.stat(self.out).st_mode & 0o777, 0o600)
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn(str(self.dir), text)
        result = json.loads(text)
        self.assertEqual(result["library_sha256"], hashlib.sha256(self.lib.read_bytes()).hexdigest())
        self.assertEqual(result["library"], "libdemo.so")
        self.assertEqual(result["java"]["root"], "sources")

    def test_without_a_java_root_only_the_exports_are_reported(self):
        out = self.dir / "plain.json"
        self.assertEqual(run_main([str(self.lib), "--out", str(out)]), 0)
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertNotIn("java", result)
        self.assertEqual(result["summary"], {"jni_exports": 4})
        self.assertEqual(result["dynamic_registration"],
                         {"jni_onload_exported": True, "register_natives_imported": False})

    def test_max_java_files_truncates_the_scan(self):
        (self.src / "Second.java").write_text("package com.example;\nclass Second {}\n", encoding="utf-8")
        (self.src / "Third.java").write_text("package com.example;\nclass Third {}\n", encoding="utf-8")
        out = self.dir / "small.json"
        code = run_main([str(self.lib), "--out", str(out), "--java-root", str(self.dir / "sources"),
                         "--max-java-files", "2"])
        self.assertEqual(code, 0)
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(result["java"]["truncated"])
        self.assertEqual(result["java"]["files_scanned"], 2)

    def test_refusals_exit_2(self):
        bad = self.dir / "bad.so"
        bad.write_bytes(b"not elf" * 20)
        self.assertEqual(run_main([str(bad), "--out", str(self.out)]), 2)
        self.assertEqual(run_main([str(self.lib), "--out", str(self.out),
                                   "--java-root", str(self.dir / "missing")]), 2)
        self.assertEqual(run_main([str(self.lib), "--out", str(self.out), "--max-java-files", "0"]), 2)

    def test_symbolic_link_output_is_refused_and_its_target_is_untouched(self):
        target = self.dir / "target.txt"
        target.write_text("keep", encoding="utf-8")
        self.out.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, self.out)
        self.assertEqual(run_main([str(self.lib), "--out", str(self.out)]), 2)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
