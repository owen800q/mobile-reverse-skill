#!/usr/bin/env python3
"""Tests for scripts/flutter_snapshot.py: snapshot hashes, engine facts, AOT sections and URI pools, and refusals."""
import contextlib
import io
import json
import os
import shutil
import stat
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import flutter_snapshot as fs  # noqa: E402

H_A = "65817c30a78bb44c3dc3771876b6010a"
H_B = "0123456789abcdef0123456789abcdef"
BUILD_ID = bytes(range(1, 21))


def snapshot_header(hash_hex, kind=3, length=None, size=None):
    """A Dart data section header: magic, length (excluding the magic), kind, then the 32-byte hash."""
    size = size or 128
    length = size - 4 if length is None else length
    return fs.DART_MAGIC + struct.pack("<QQ", length, kind) + hash_hex.encode("ascii")


def data_section(hash_hex, uris=(), kind=3):
    """A data section that covers its declared length (124 bytes after the magic), then a URI pool."""
    head = snapshot_header(hash_hex, kind=kind, size=128)
    pool = b"".join(u.encode("ascii") + b"\x00" for u in uris)
    return (head + b"\x00" * (128 - len(head)) + pool)


def build_so(payload, symbols, note=b""):
    """ELF64 shared object. One PT_LOAD maps the whole file at its own offsets; PT_NOTE holds `note`.
    payload sits at a 16-byte aligned offset; symbols are (name, offset in payload, size)."""
    note_at = 176
    payload_at = (note_at + len(note) + 15) & ~15
    body = bytearray(payload_at + len(payload))
    body[note_at:note_at + len(note)] = note
    body[payload_at:] = payload
    strtab = bytearray(b"\x00")
    entries = [struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)]
    for name, rel, size in symbols:
        name_off = len(strtab)
        strtab += name.encode("ascii") + b"\x00"
        entries.append(struct.pack("<IBBHQQ", name_off, (1 << 4) | 1, 0, 1, payload_at + rel, size))
    dynsym = b"".join(entries)
    while len(body) % 8:
        body.append(0)
    dynstr_at = len(body)
    body += strtab
    while len(body) % 8:
        body.append(0)
    dynsym_at = len(body)
    body += dynsym
    while len(body) % 8:
        body.append(0)
    shoff = len(body)
    shdrs = struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    shdrs += struct.pack("<IIQQQQIIQQ", 0, 3, 0, 0, dynstr_at, len(strtab), 0, 0, 1, 0)
    shdrs += struct.pack("<IIQQQQIIQQ", 0, 11, 0, 0, dynsym_at, len(dynsym), 1, 1, 8, 24)
    body += shdrs
    load = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, len(body), len(body), 0x1000)
    note_ph = struct.pack("<IIQQQQQQ", 4, 4, note_at, note_at, note_at, len(note), len(note), 4)
    header = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    header += struct.pack("<HHIQQQIHHHHHH", 3, 183, 1, 0, 64, shoff, 0, 64, 56, 2, 64, 3, 0)
    body[0:64] = header
    body[64:120] = load
    body[120:176] = note_ph
    return bytes(body)


def gnu_note(build_id):
    return struct.pack("<III", 4, len(build_id), 3) + b"GNU\x00" + build_id


def libapp(vm_hash, iso_hash, uris=("package:app/main.dart", "package:flutter/widgets.dart", "dart:core"),
           kind=3):
    vm = data_section(vm_hash, kind=kind)
    vm_instr = b"\x90" * 64
    iso = data_section(iso_hash, uris=uris, kind=kind)
    iso_instr = b"\x90" * 64
    payload = vm + vm_instr + iso + iso_instr
    symbols = [
        ("_kDartVmSnapshotData", 0, len(vm)),
        ("_kDartVmSnapshotInstructions", len(vm), len(vm_instr)),
        ("_kDartIsolateSnapshotData", len(vm) + len(vm_instr), len(iso)),
        ("_kDartIsolateSnapshotInstructions", len(vm) + len(vm_instr) + len(iso), len(iso_instr)),
    ]
    return build_so(payload, symbols)


def libflutter(version=b"Dart VM version: 3.0.5 (stable)", toolchain=b"", build_id=BUILD_ID):
    payload = b"Dart_Initialize\x00" + version + b"\x00" + toolchain + b"\x00"
    return build_so(payload, [("Dart_Initialize", 0, 15)], note=gnu_note(build_id))


def write_apk(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def run_main(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fs.main(argv)
    return code, out.getvalue(), err.getvalue()


class FlutterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="flutter-snapshot-test-"))
        self.out = self.tmp / "out" / "flutter.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load(self):
        return json.loads(self.out.read_text(encoding="utf-8"))


class IdentifyTests(FlutterCase):
    def test_apk_reports_agreed_hash_engine_facts_and_aot_pool(self):
        apk = self.tmp / "app.apk"
        write_apk(apk, {
            "lib/arm64-v8a/libapp.so": libapp(H_A, H_A),
            "lib/arm64-v8a/libflutter.so": libflutter(
                toolchain=b"Android (8490178, based on r450784e) clang version 14.0.6"),
        })
        code, out, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        result = self.load()
        self.assertTrue(result["flutter_detected"])
        self.assertEqual(result["snapshot_hash"], H_A)
        self.assertEqual(result["coverage"], "complete")
        engine = result["abis"]["arm64-v8a"]["libflutter"]
        self.assertEqual(engine["build_id"], BUILD_ID.hex())
        self.assertEqual(engine["dart_vm_version"], "Dart VM version: 3.0.5 (stable)")
        self.assertEqual(engine["toolchain_lines"],
                         ["Android (8490178, based on r450784e) clang version 14.0.6"])
        aot = result["aot"]
        self.assertEqual(aot["abi"], "arm64-v8a")
        self.assertEqual(aot["snapshot_hash"], H_A)
        self.assertEqual(aot["coverage"], "complete")
        self.assertEqual(aot["string_pool"]["package_uris"]["retained"],
                         ["package:app/main.dart", "package:flutter/widgets.dart"])
        self.assertEqual(aot["string_pool"]["dart_uris"]["retained"], ["dart:core"])
        self.assertIn("flutter_detected", out)

    def test_sha256_of_the_target_is_recorded(self):
        import hashlib
        apk = self.tmp / "app.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A)})
        run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(self.load()["target"]["sha256"], hashlib.sha256(apk.read_bytes()).hexdigest())

    def test_disagreeing_abis_keep_candidates_and_partial_coverage(self):
        apk = self.tmp / "app.apk"
        write_apk(apk, {
            "lib/arm64-v8a/libapp.so": libapp(H_A, H_A),
            "lib/armeabi-v7a/libapp.so": libapp(H_B, H_B),
        })
        code, _, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        result = self.load()
        self.assertIsNone(result["snapshot_hash"])
        self.assertEqual(result["snapshot_hash_candidates"], sorted([H_A, H_B]))
        self.assertEqual(result["coverage"], "partial")
        self.assertIn("snapshot hash is absent or disagrees across ABIs", result["coverage_gaps"])

    def test_plain_apk_is_a_complete_negative(self):
        apk = self.tmp / "plain.apk"
        write_apk(apk, {"AndroidManifest.xml": b"<manifest/>", "classes.dex": b"dex\n035\x00"})
        code, _, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        result = self.load()
        self.assertFalse(result["flutter_detected"])
        self.assertEqual(result["abis"], {})
        self.assertIsNone(result["aot"])
        self.assertEqual(result["coverage"], "complete")

    def test_libflutter_without_libapp_is_partial(self):
        apk = self.tmp / "engine.apk"
        write_apk(apk, {"lib/arm64-v8a/libflutter.so": libflutter()})
        code, _, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        result = self.load()
        self.assertFalse(result["flutter_detected"])
        self.assertEqual(result["abis"]["arm64-v8a"]["coverage"], "partial")
        self.assertIn("libapp.so absent", result["abis"]["arm64-v8a"]["coverage_gaps"])

    def test_directory_layout_gives_the_same_hash_as_the_apk(self):
        root = self.tmp / "unpacked"
        (root / "lib" / "arm64-v8a").mkdir(parents=True)
        (root / "lib" / "arm64-v8a" / "libapp.so").write_bytes(libapp(H_A, H_A))
        code, _, _ = run_main([str(root), "--out", str(self.out)])
        self.assertEqual(code, 0)
        result = self.load()
        self.assertEqual(result["snapshot_hash"], H_A)
        self.assertIsNone(result["target"]["sha256"])

    def test_requested_abi_must_be_present(self):
        apk = self.tmp / "app.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A)})
        code, _, err = run_main([str(apk), "--out", str(self.out), "--abi", "x86"])
        self.assertEqual(code, 2)
        self.assertIn("ABI x86 has no libapp.so", err)
        self.assertFalse(self.out.exists())

    def test_library_without_snapshot_symbols_is_refused(self):
        apk = self.tmp / "stripped.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": build_so(b"\x00" * 32, [("Other", 0, 8)])})
        code, _, err = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("no exported _kDart*Snapshot* symbols", err)

    def test_duplicate_library_entries_are_refused(self):
        apk = self.tmp / "dup.apk"
        with warnings.catch_warnings(), zipfile.ZipFile(apk, "w") as zf:
            warnings.simplefilter("ignore", UserWarning)  # zipfile warns about the duplicate on purpose
            zf.writestr("lib/arm64-v8a/libapp.so", libapp(H_A, H_A))
            zf.writestr("lib/arm64-v8a/libapp.so", libapp(H_B, H_B))
        code, _, err = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("duplicate library entry", err)

    def test_non_zip_file_is_refused(self):
        plain = self.tmp / "not-a-zip.bin"
        plain.write_bytes(b"\x7fELF but not an archive")
        code, _, err = run_main([str(plain), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("not an APK or zip", err)


class AotTests(FlutterCase):
    def test_header_kind_other_than_full_aot_is_partial(self):
        apk = self.tmp / "kind.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A, kind=2)})
        code, _, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        aot = self.load()["aot"]
        self.assertEqual(aot["sections"]["vm_data"]["header"]["kind"], 2)
        self.assertEqual(aot["coverage"], "partial")
        self.assertIn("_kDartVmSnapshotData header is not a complete FullAOT layout", aot["coverage_gaps"])

    def test_uri_pool_truncation_is_reported(self):
        apk = self.tmp / "pool.apk"
        uris = ("package:a/one.dart", "package:a/two.dart", "package:a/three.dart")
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A, uris=uris)})
        code, _, _ = run_main([str(apk), "--out", str(self.out), "--max-pool", "1"])
        self.assertEqual(code, 0)
        pool = self.load()["aot"]["string_pool"]["package_uris"]
        self.assertEqual(pool["distinct"], 3)
        self.assertEqual(pool["retained"], ["package:a/one.dart"])
        self.assertEqual(pool["coverage"], "partial")

    def test_max_pool_must_be_positive(self):
        apk = self.tmp / "app.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A)})
        code, _, err = run_main([str(apk), "--out", str(self.out), "--max-pool", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--max-pool must be at least 1", err)


def allocate_dynsym(image, addr):
    """Mark the .dynsym section (index 2 of build_so) SHF_ALLOC at `addr`."""
    shoff, = struct.unpack_from("<Q", image, 40)
    buf = bytearray(image)
    struct.pack_into("<Q", buf, shoff + 2 * 64 + 8, 2)
    struct.pack_into("<Q", buf, shoff + 2 * 64 + 16, addr)
    return bytes(buf)


def dynsym_offset(image):
    shoff, = struct.unpack_from("<Q", image, 40)
    return struct.unpack_from("<Q", image, shoff + 2 * 64 + 24)[0]


class AotMappingTests(FlutterCase):
    def test_allocated_symbol_table_agreeing_with_pt_load_keeps_complete_coverage(self):
        base = libapp(H_A, H_A)
        apk = self.tmp / "agree.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": allocate_dynsym(base, dynsym_offset(base))})
        code, _, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        aot = self.load()["aot"]
        self.assertEqual(aot["coverage"], "complete")
        self.assertEqual(aot["snapshot_hash"], H_A)

    def test_allocated_symbol_table_off_its_pt_load_is_partial_and_still_resolved(self):
        base = libapp(H_A, H_A)
        apk = self.tmp / "disagree.apk"
        shifted = dynsym_offset(base) + 0x10
        write_apk(apk, {"lib/arm64-v8a/libapp.so": allocate_dynsym(base, shifted)})
        code, _, _ = run_main([str(apk), "--out", str(self.out)])
        self.assertEqual(code, 0)
        aot = self.load()["aot"]
        self.assertEqual(aot["coverage"], "partial")
        self.assertTrue(any("dynamic symbol table section offset" in g and "disagrees with its PT_LOAD mapping" in g
                            for g in aot["coverage_gaps"]), aot["coverage_gaps"])
        self.assertIsNotNone(aot["sections"]["vm_data"]["offset"])
        self.assertEqual(aot["snapshot_hash"], H_A)


class EngineLabelTests(unittest.TestCase):
    def test_version_label_glued_to_other_text_is_not_a_label(self):
        data = b"junkDart VM version: 9.9.9\x00"
        result = fs.scan_labeled_strings(data)
        self.assertIsNone(result["dart_vm_version"])
        self.assertFalse(result["dart_vm_version_capped"])

    def test_overlong_version_label_is_capped_not_truncated(self):
        data = b"Dart VM version: " + b"9" * 300 + b"\x00"
        result = fs.scan_labeled_strings(data)
        self.assertIsNone(result["dart_vm_version"])
        self.assertTrue(result["dart_vm_version_capped"])

    def test_conflicting_version_labels_are_capped(self):
        data = b"Dart VM version: 3.0.5\x00Dart VM version: 2.19.6\x00"
        result = fs.scan_labeled_strings(data)
        self.assertEqual(result["dart_vm_version"], "Dart VM version: 3.0.5")
        self.assertTrue(result["dart_vm_version_capped"])

    def test_unrecognised_toolchain_grammar_is_capped(self):
        data = b"Android (broken clang\x00"
        result = fs.scan_labeled_strings(data)
        self.assertEqual(result["toolchain_lines"], [])
        self.assertTrue(result["toolchain_capped"])

    def test_llvm_line_is_reported_verbatim(self):
        data = b"based on LLVM 17.0.2\x00"
        self.assertEqual(fs.scan_labeled_strings(data)["toolchain_lines"], ["based on LLVM 17.0.2"])

    def test_snapshot_hash_must_be_lowercase_hex(self):
        bad = fs.DART_MAGIC + b"\x00" * 16 + b"G" * 32
        self.assertEqual(fs.scan_snapshot_hashes(bad), {"sources": 0, "candidates": [], "capped": False})
        good = fs.DART_MAGIC + b"\x00" * 16 + H_A.encode()
        self.assertEqual(fs.scan_snapshot_hashes(good)["candidates"], [H_A])

    def test_build_id_beyond_the_file_is_incomplete(self):
        lib = bytearray(libflutter())
        # Declare a note whose descriptor runs past the end of the file.
        note_at = 176
        struct.pack_into("<III", lib, note_at, 4, 0x10000, 3)
        ids, complete = fs.read_build_ids(bytes(lib))
        self.assertEqual(ids, [])
        self.assertFalse(complete)

    def test_build_id_in_elf32_note_is_read(self):
        note_at = 64 + 32
        note = gnu_note(BUILD_ID)
        image = bytearray(note_at + len(note))
        image[0:4] = b"\x7fELF"
        image[4] = 1  # ELFCLASS32
        image[5] = 1  # little-endian
        struct.pack_into("<I", image, 0x1C, 64)  # e_phoff
        struct.pack_into("<HH", image, 0x2A, 32, 1)  # e_phentsize, e_phnum
        struct.pack_into("<IIIIIIII", image, 64, 4, note_at, note_at, note_at, len(note), len(note), 4, 4)
        image[note_at:] = note
        ids, complete = fs.read_build_ids(bytes(image))
        self.assertEqual(ids, [BUILD_ID.hex()])
        self.assertTrue(complete)


class OutputTests(FlutterCase):
    def test_output_is_private_and_holds_no_absolute_paths(self):
        apk = self.tmp / "app.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A)})
        run_main([str(apk), "--out", str(self.out)])
        mode = stat.S_IMODE(os.stat(self.out).st_mode)
        self.assertEqual(mode, 0o600)
        self.assertNotIn(str(self.tmp), self.out.read_text(encoding="utf-8"))
        self.assertEqual(self.load()["target"]["name"], "app.apk")

    def test_symbolic_link_output_is_refused_and_its_target_is_untouched(self):
        apk = self.tmp / "app.apk"
        write_apk(apk, {"lib/arm64-v8a/libapp.so": libapp(H_A, H_A)})
        victim = self.tmp / "victim.txt"
        victim.write_text("keep", encoding="utf-8")
        link = self.tmp / "link.json"
        os.symlink(victim, link)
        code, _, err = run_main([str(apk), "--out", str(link)])
        self.assertEqual(code, 2)
        self.assertIn("symbolic link", err)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
