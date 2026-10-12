#!/usr/bin/env python3
"""Tests for scripts/jni_map.py: ELF symbol reading, JNI name rules, Java declarations and matching."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
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
            "java_natives_registered_candidate": 0,
            "register_tables": 0,
            "register_entries": 0,
            "register_entries_with_java": 0,
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
        self.assertEqual(result["summary"], {"jni_exports": 4, "register_tables": 0, "register_entries": 0})
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


REG_JAVA = '''package com.example;

public class Api {
    public native String login(String user);
    public native void sign(int a);
    public native void sign(String a);
    public native int gone(long x);
}
'''

OTHER_JAVA = '''package com.example;

public class Other {
    public native String login(String user);
}
'''

GCC_TABLE_SRC = r'''
struct method { const char *name; const char *sig; void *fn; };
static int login_impl(void) { return 1; }
static void sign_impl(int a) { (void)a; }
__attribute__((used)) static const struct method methods[] = {
    { "login", "(Ljava/lang/String;)Ljava/lang/String;", (void *)login_impl },
    { "sign", "(I)V", (void *)sign_impl },
};
int jni_probe(void) { return (int)(sizeof methods / sizeof methods[0]); }
'''


def build_table_library(entries, machine=183, extra_strings=()):
    """A little-endian ELF64 shared object with one JNINativeMethod table in a writable segment.

    entries are (name, signature, use_symbol). A true use_symbol gives the function slot an absolute
    relocation against the defined symbol native_fn. Otherwise it is a RELATIVE relocation to the
    same address, which is the code address 0x100. extra_strings are stored as NUL-terminated strings.
    """
    relative, absolute = {183: (1027, 257), 62: (8, 1)}[machine]
    image = bytearray(0x100)

    def place(blob, align=8):
        image.extend(b"\x00" * (-len(image) % align))
        at = len(image)
        image.extend(blob)
        return at

    code = place(b"\x00" * 16, 16)
    assert code == 0x100
    names = [place(name.encode() + b"\x00", 1) for name, _, _ in entries]
    sigs = [place(sig.encode() + b"\x00", 1) for _, sig, _ in entries]
    for text in extra_strings:
        place(text.encode() + b"\x00", 1)
    dynstr = b"\x00native_fn\x00"
    strtab = place(dynstr, 1)
    dynsym = struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0) + struct.pack("<IBBHQQ", 1, 0x12, 0, 1, code, 4)
    symtab = place(dynsym, 8)
    rela_at = place(b"\x00" * (72 * len(entries)), 8)  # three relocations of 24 bytes per entry
    shstrtab = b"\x00.dynstr\x00.dynsym\x00.rela.dyn\x00.shstrtab\x00"
    shstr = place(shstrtab, 1)
    shdr_at = place(b"\x00" * (64 * 5), 8)
    ro_end = len(image)
    data_at = ro_end + (-ro_end % 0x1000)
    image.extend(b"\x00" * (data_at - ro_end + 24 * len(entries)))
    rela = bytearray()
    for i, (_, _, use_symbol) in enumerate(entries):
        slot = data_at + 24 * i
        rela += struct.pack("<QQq", slot, relative, names[i])
        rela += struct.pack("<QQq", slot + 8, relative, sigs[i])
        if use_symbol:
            rela += struct.pack("<QQq", slot + 16, (1 << 32) | absolute, 0)
        else:
            rela += struct.pack("<QQq", slot + 16, relative, code)
    image[rela_at:rela_at + len(rela)] = rela
    sh = struct.Struct("<IIQQQQIIQQ")
    headers = [
        sh.pack(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        sh.pack(1, 3, 0, 0, strtab, len(dynstr), 0, 0, 1, 0),
        sh.pack(9, 11, 0, 0, symtab, len(dynsym), 1, 1, 8, 24),
        sh.pack(17, 4, 0, 0, rela_at, len(rela), 2, 0, 8, 24),
        sh.pack(27, 3, 0, 0, shstr, len(shstrtab), 0, 0, 1, 0),
    ]
    image[shdr_at:shdr_at + 64 * 5] = b"".join(headers)
    table_bytes = 24 * len(entries)
    phdrs = (struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, ro_end, ro_end, 0x1000)
             + struct.pack("<IIQQQQQQ", 1, 6, data_at, data_at, data_at, table_bytes, table_bytes, 0x1000))
    ident = b"\x7fELF" + bytes([2, 1, 1]) + b"\x00" * 9
    image[0:64] = struct.pack("<16sHHIQQQIHHHHHH", ident, 3, machine, 1, 0, 64, shdr_at, 0, 64, 56, 2, 64, 5, 4)
    image[64:64 + len(phdrs)] = phdrs
    return bytes(image)


def build_table_library32(entries, machine=40):
    """A little-endian ELF32 shared object with one JNINativeMethod table, using REL relocations.

    A REL slot has no addend in its relocation entry. The loader takes the implicit addend from the
    file at the slot, so the table bytes hold the name, signature and function addresses.
    """
    image = bytearray(0x100)

    def place(blob, align=4):
        image.extend(b"\x00" * (-len(image) % align))
        at = len(image)
        image.extend(blob)
        return at

    code = place(b"\x00" * 16, 16)
    assert code == 0x100
    names = [place(name.encode() + b"\x00", 1) for name, _ in entries]
    sigs = [place(sig.encode() + b"\x00", 1) for _, sig in entries]
    dynstr = b"\x00native_fn\x00"
    strtab = place(dynstr, 1)
    dynsym = struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0) + struct.pack("<IIIBBH", 1, code, 4, 0x12, 0, 1)
    symtab = place(dynsym, 4)
    rel_at = place(b"\x00" * (8 * 3 * len(entries)), 4)
    shstrtab = b"\x00.dynstr\x00.dynsym\x00.rel.dyn\x00.shstrtab\x00"
    shstr = place(shstrtab, 1)
    shdr_at = place(b"\x00" * (40 * 5), 4)
    ro_end = len(image)
    data_at = ro_end + (-ro_end % 0x1000)
    image.extend(b"\x00" * (data_at - ro_end))
    for i in range(len(entries)):
        image.extend(struct.pack("<III", names[i], sigs[i], code))
    rel = b"".join(struct.pack("<II", data_at + 12 * i + k, 23)  # R_ARM_RELATIVE
                   for i in range(len(entries)) for k in (0, 4, 8))
    image[rel_at:rel_at + len(rel)] = rel
    sh = struct.Struct("<IIIIIIIIII")
    headers = [
        sh.pack(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        sh.pack(1, 3, 0, 0, strtab, len(dynstr), 0, 0, 1, 0),
        sh.pack(9, 11, 0, 0, symtab, len(dynsym), 1, 1, 4, 16),
        sh.pack(17, 9, 0, 0, rel_at, len(rel), 2, 0, 4, 8),
        sh.pack(26, 3, 0, 0, shstr, len(shstrtab), 0, 0, 1, 0),
    ]
    image[shdr_at:shdr_at + 40 * 5] = b"".join(headers)
    table_bytes = 12 * len(entries)
    phdrs = (struct.pack("<IIIIIIII", 1, 0, 0, 0, ro_end, ro_end, 5, 0x1000)
             + struct.pack("<IIIIIIII", 1, data_at, data_at, data_at, table_bytes, table_bytes, 6, 0x1000))
    ident = b"\x7fELF" + bytes([1, 1, 1]) + b"\x00" * 9
    image[0:52] = struct.pack("<16sHHIIIIIHHHHHH", ident, 3, machine, 1, 0, 52, shdr_at, 0, 52, 32, 2, 40, 5, 4)
    image[52:52 + len(phdrs)] = phdrs
    return bytes(image)


class Elf32RelTests(unittest.TestCase):
    def test_arm32_table_takes_its_addends_from_the_file(self):
        entries = [("login", "(Ljava/lang/String;)Ljava/lang/String;"), ("sign", "(I)V")]
        data = build_table_library32(entries)
        elf = jm.read_dynamic_symbols(data)
        self.assertEqual(elf["elf_class"], "ELF32")
        targets, supported = jm.relocated_targets(data, elf)
        self.assertTrue(supported)
        tables = jm.find_register_tables(data, elf, targets)
        self.assertEqual(
            [(e["name"], e["signature"], e["function"]) for t in tables for e in t["entries"]],
            [("login", "(Ljava/lang/String;)Ljava/lang/String;", "0x100"), ("sign", "(I)V", "0x100")],
        )


class DescriptorTests(unittest.TestCase):
    def test_descriptor_type_names(self):
        self.assertEqual(jm.descriptor_type_names("(ILjava/lang/String;[[JLcom/example/Outer$Inner;)Z"),
                         (["int", "String", "long[][]", "Inner"], "boolean"))

    def test_java_parameter_and_return_names(self):
        self.assertEqual(jm.java_param_names("final Map<String, List<Integer>> m, int a[], String... rest"),
                         ["Map", "int[]", "String[]"])
        self.assertEqual(jm.java_param_names(""), [])
        self.assertEqual(jm.java_return_name(" static <T> java.util.List<T> "), "List")


class RegisterTableTests(unittest.TestCase):
    ENTRIES = [
        ("login", "(Ljava/lang/String;)Ljava/lang/String;", False),
        ("sign", "(I)V", True),
    ]

    def load(self, extra_strings=()):
        data = build_table_library(self.ENTRIES, extra_strings=extra_strings)
        elf = jm.read_dynamic_symbols(data)
        targets, supported = jm.relocated_targets(data, elf)
        return data, elf, targets, supported

    def test_table_entries_come_from_relocations_in_both_forms(self):
        data, elf, targets, supported = self.load()
        self.assertTrue(supported)
        tables = jm.find_register_tables(data, elf, targets)
        self.assertEqual(len(tables), 1)
        self.assertEqual(
            [(e["name"], e["signature"], e["function"]) for e in tables[0]["entries"]],
            [("login", "(Ljava/lang/String;)Ljava/lang/String;", "0x100"), ("sign", "(I)V", "0x100")],
        )

    def test_a_function_slot_outside_executable_memory_ends_the_entry(self):
        data, elf, targets, _ = self.load()
        data_vaddr = elf["loads"][1]["vaddr"]
        targets[data_vaddr + 16] = data_vaddr  # the first entry's function now points at data
        tables = jm.find_register_tables(data, elf, targets)
        self.assertEqual([e["name"] for t in tables for e in t["entries"]], ["sign"])

    def test_an_unrelocated_signature_slot_ends_the_entry(self):
        data, elf, targets, _ = self.load()
        del targets[elf["loads"][1]["vaddr"] + 8]
        tables = jm.find_register_tables(data, elf, targets)
        self.assertEqual([e["name"] for t in tables for e in t["entries"]], ["sign"])

    def test_unknown_machine_reads_no_relocations(self):
        data = bytearray(build_table_library(self.ENTRIES))
        data[18:20] = struct.pack("<H", 0x1234)
        frozen = bytes(data)
        self.assertEqual(jm.relocated_targets(frozen, jm.read_dynamic_symbols(frozen)), ({}, False))

    def test_matching_uses_names_arity_and_simple_types(self):
        data, elf, targets, _ = self.load()
        tables = jm.find_register_tables(data, elf, targets)
        natives = jm.natives_in_source(REG_JAVA, "Api.java")
        jm.match_exports([], natives)
        jm.match_register_tables(tables, natives, data)
        by_name = {e["name"]: e for e in tables[0]["entries"]}
        self.assertEqual([h["signature_match"] for h in by_name["login"]["java"]], [True])
        self.assertEqual([h["signature_match"] for h in by_name["sign"]["java"]], [True, False])
        self.assertFalse(by_name["sign"]["ambiguous"])
        status = {(d["method"], tuple(d["params"])): d["status"] for d in natives}
        self.assertEqual(status[("login", ("String",))], "registered_candidate")
        self.assertEqual(status[("sign", ("int",))], "registered_candidate")
        self.assertEqual(status[("sign", ("String",))], "no_export")
        self.assertEqual(status[("gone", ("long",))], "no_export")

    def test_class_string_is_a_hint_that_separates_candidate_classes(self):
        data, elf, targets, _ = self.load(extra_strings=("com/example/Api",))
        tables = jm.find_register_tables(data, elf, targets)
        natives = jm.natives_in_source(REG_JAVA, "Api.java") + jm.natives_in_source(OTHER_JAVA, "Other.java")
        jm.match_register_tables(tables, natives, data)
        login = [e for t in tables for e in t["entries"] if e["name"] == "login"][0]
        self.assertEqual([(h["class"], h["class_string_present"]) for h in login["java"]],
                         [("com.example.Api", True), ("com.example.Other", False)])
        self.assertTrue(login["ambiguous"])

    def test_command_line_reports_tables_and_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources" / "com" / "example").mkdir(parents=True)
            (root / "sources" / "com" / "example" / "Api.java").write_text(REG_JAVA, encoding="utf-8")
            lib = root / "libtable.so"
            lib.write_bytes(build_table_library(self.ENTRIES))
            out = root / "out.json"
            self.assertEqual(run_main([str(lib), "--out", str(out), "--java-root", str(root / "sources")]), 0)
            result = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(result["register_natives"]["relocations_read"])
        self.assertEqual(result["summary"], {
            "jni_exports": 0,
            "register_tables": 1,
            "register_entries": 2,
            "java_natives": 4,
            "exports_matched": 0,
            "exports_without_java": 0,
            "ambiguous_exports": 0,
            "java_natives_registered_candidate": 2,
            "java_natives_without_export": 2,
            "register_entries_with_java": 2,
        })


@unittest.skipUnless(shutil.which("gcc"), "gcc is not installed")
class CompilerTableTests(unittest.TestCase):
    def test_table_built_by_gcc_is_found_with_its_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "table.c"
            src.write_text(GCC_TABLE_SRC, encoding="utf-8")
            lib = Path(tmp) / "libtable.so"
            proc = subprocess.run(["gcc", "-shared", "-fPIC", "-O1", "-o", str(lib), str(src)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = lib.read_bytes()
        elf = jm.read_dynamic_symbols(data)
        targets, supported = jm.relocated_targets(data, elf)
        self.assertTrue(supported)
        tables = jm.find_register_tables(data, elf, targets)
        self.assertEqual([(e["name"], e["signature"]) for t in tables for e in t["entries"]],
                         [("login", "(Ljava/lang/String;)Ljava/lang/String;"), ("sign", "(I)V")])


if __name__ == "__main__":
    unittest.main()
