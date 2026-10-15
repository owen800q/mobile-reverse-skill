#!/usr/bin/env python3
"""Tests for scripts/target_identify.py: header and container routing hints."""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "target_identify.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import target_identify as ti  # noqa: E402


def make_pe(machine, magic, clr=False, dll=False):
    buf = bytearray(0x400)
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", buf, 0x84, machine, 1)
    opt_size = 240 if magic == 0x20B else 224
    struct.pack_into("<H", buf, 0x84 + 16, opt_size)
    struct.pack_into("<H", buf, 0x84 + 18, 0x2000 if dll else 0x0002)
    opt = 0x84 + 20
    struct.pack_into("<H", buf, opt, magic)
    if clr:
        dd_off = 112 if magic == 0x20B else 96
        struct.pack_into("<II", buf, opt + dd_off + 14 * 8, 0x2000, 0x48)
    return bytes(buf)


def build_asar(files):
    """Write the ASAR layout: [4][header size][pickle(JSON)][file data]."""
    data = b""
    entries = {}
    for name, content in files.items():
        entries[name] = {"size": len(content), "offset": str(len(data))}
        data += content
    header_json = json.dumps({"files": entries}, separators=(",", ":")).encode("utf-8")
    payload = struct.pack("<I", len(header_json)) + header_json
    payload += b"\0" * ((4 - len(payload) % 4) % 4)
    header_pickle = struct.pack("<I", len(payload)) + payload
    return struct.pack("<II", 4, len(header_pickle)) + header_pickle + data


class IdentifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(path, mode) as f:
            f.write(content)
        return path

    def zip_with(self, name, members):
        path = os.path.join(self.root, name)
        with zipfile.ZipFile(path, "w") as z:
            for member in members:
                z.writestr(member, b"x")
        return path

    # --- native binaries --------------------------------------------------
    def test_real_system_binary_is_elf(self):
        path = shutil.which("ls") or "/bin/ls"
        if not os.path.isfile(path):
            self.skipTest("no system ls binary")
        info = ti.identify_file(path)
        self.assertEqual(info["format"], "ELF")
        self.assertEqual(info["route"], "native-elf")
        self.assertIn(info["arch"], ti.ELF_MACHINE.values())
        self.assertIsNotNone(info["sha256"])

    def test_big_endian_mips_elf(self):
        ident = b"\x7fELF" + bytes([1, 2, 1]) + b"\x00" * 9
        hdr = ident + struct.pack(">HH", 2, 8) + b"\x00" * 44
        info = ti.identify_file(self.write("httpd", hdr))
        self.assertEqual((info["format"], info["arch"], info["bits"], info["endian"]),
                         ("ELF", "MIPS", 32, "BE"))

    def test_ne_le_lx_behind_an_mz_stub_are_named_not_called_dos(self):
        for sig in (b"NE", b"LE", b"LX"):
            blob = bytearray(0x200)
            blob[0:2] = b"MZ"
            struct.pack_into("<I", blob, 0x3C, 0x80)
            blob[0x80:0x82] = sig
            info = ti.identify_file(self.write("legacy-" + sig.decode() + ".exe", bytes(blob)))
            self.assertEqual(info["format"], "MZ (%s, not PE)" % sig.decode())
            self.assertNotEqual(info["format"], "MZ (no PE header)")

    def test_pe_managed_and_native(self):
        managed = ti.identify_file(self.write("app.dll", make_pe(0x8664, 0x20B, clr=True, dll=True)))
        self.assertTrue(managed["managed"])
        self.assertEqual(managed["route"], "desktop-managed")
        native = ti.identify_file(self.write("tool.exe", make_pe(0x8664, 0x20B)))
        self.assertFalse(native["managed"])
        self.assertEqual(native["route"], "desktop-native")
        self.assertEqual((native["format"], native["arch"], native["bits"]),
                         ("PE", "x86-64", 64))

    def test_macho_arm64(self):
        hdr = b"\xcf\xfa\xed\xfe" + struct.pack("<IIII", 0x0100000C, 0, 2, 0)
        info = ti.identify_file(self.write("App", hdr))
        self.assertEqual((info["format"], info["arch"], info["bits"], info["route"]),
                         ("Mach-O", "AArch64", 64, "desktop-native"))

    def test_fat_macho_and_java_class_are_not_confused(self):
        fat = (b"\xca\xfe\xba\xbe" + struct.pack(">I", 2)
               + struct.pack(">IIIII", 0x01000007, 3, 0x1000, 0x100, 12)
               + struct.pack(">IIIII", 0x0100000C, 0, 0x2000, 0x100, 12))
        self.assertEqual(ti.identify_file(self.write("fat", fat))["format"], "Mach-O (universal)")
        java = b"\xca\xfe\xba\xbe" + struct.pack(">HH", 0, 52) + b"\x00" * 8
        info = ti.identify_file(self.write("Main.class", java))
        self.assertEqual((info["format"], info["route"]), ("java class", "desktop-java"))

    def test_fat64_and_swapped_fat_headers_are_universal_not_unknown(self):
        slice_hdr = b"\xcf\xfa\xed\xfe" + struct.pack("<IIII", 0x0100000C, 0, 2, 0) + b"\x00" * 16
        fat64 = (b"\xca\xfe\xba\xbf" + struct.pack(">I", 1)
                 + struct.pack(">IIQQII", 0x0100000C, 0, 0x30, len(slice_hdr), 4, 0)
                 + b"\x00" * 8 + slice_hdr)
        info = ti.identify_file(self.write("fat64", fat64))
        self.assertEqual((info["format"], info["arch"], info["route"]),
                         ("Mach-O (universal, FAT64)", "AArch64", "desktop-native"))
        self.assertEqual(info["endian"], "BE")
        self.assertFalse([n for n in info["notes"] if n.startswith("slice ")])
        swapped = (b"\xbe\xba\xfe\xca" + struct.pack("<I", 1)
                   + struct.pack("<IIIII", 0x0100000C, 0, 0x20, len(slice_hdr), 4)
                   + b"\x00" * 4 + slice_hdr)
        info = ti.identify_file(self.write("swapped", swapped))
        self.assertEqual((info["format"], info["arch"], info["endian"]),
                         ("Mach-O (universal)", "AArch64", "LE"))
        self.assertFalse([n for n in info["notes"] if n.startswith("slice ")])

    def test_arm64e_slices_carry_the_lipo_name_and_byte_range(self):
        thin = b"\xcf\xfa\xed\xfe" + struct.pack("<IIII", 0x0100000C, 2, 2, 0)
        info = ti.identify_file(self.write("thin_arm64e", thin))
        self.assertEqual((info["arch"], info["notes"][0]), ("AArch64 arm64e", "EXECUTE"))
        fat = (b"\xca\xfe\xba\xbe" + struct.pack(">I", 2)
               + struct.pack(">IIIII", 0x0100000C, 12, 0x1000, 0x100, 12)
               + struct.pack(">IIIII", 0x0100000C, 0, 0x2000, 0x100, 12))
        info = ti.identify_file(self.write("fat_arm64e", fat))
        self.assertEqual(info["arch"], "AArch64 arm64e.x1, AArch64")
        self.assertEqual(info["slices"], [
            {"index": 0, "arch": "AArch64 arm64e.x1", "offset": 0x1000, "size": 0x100,
             "bits": 64, "endian": "LE"},
            {"index": 1, "arch": "AArch64", "offset": 0x2000, "size": 0x100,
             "bits": 64, "endian": "LE"}])

    def test_fat_slice_ranges_that_cannot_be_a_slice_are_noted(self):
        table = struct.pack(">IIIII", 0x0100000C, 0, 0x10, 0x100, 12)          # overlaps the table
        table += struct.pack(">IIIII", 0x01000007, 3, 0x50, 4, 12)             # shorter than a header
        table += struct.pack(">IIIII", 0x01000012, 0, 0x1000, 0x100, 12)       # past the end of the file
        fat = b"\xca\xfe\xba\xbe" + struct.pack(">I", 3) + table + b"\x00" * 0x80
        notes = " | ".join(ti.identify_file(self.write("bad_fat", fat))["notes"])
        self.assertIn("slice 0 (AArch64) overlaps the architecture table", notes)
        self.assertIn("slice 1 (x86-64) is shorter than a Mach-O header", notes)
        self.assertIn("slice 2 (PowerPC64) runs past the end of the file", notes)

    def test_binary_plist_is_recognised_by_magic_under_any_name(self):
        info = ti.identify_file(self.write("session.archive", b"bplist00" + b"\x00" * 32))
        self.assertEqual((info["format"], info["route"]), ("binary plist", "ios"))

    def test_pyinstaller_cookie_marks_packed_python(self):
        data = make_pe(0x14C, 0x10B) + b"\x00" * 100 + ti.PYI_COOKIE + b"\x00" * 40
        info = ti.identify_file(self.write("packed.exe", data))
        self.assertTrue(info["pyinstaller_candidate"])
        self.assertEqual(info["route"], "desktop-packed-python")

    # --- archives ---------------------------------------------------------
    def test_zip_identities(self):
        cases = {
            "app.apk": (["AndroidManifest.xml", "classes.dex"], "android package (apk)", "android"),
            "app.aab": (["base/manifest/AndroidManifest.xml", "BundleConfig.pb"],
                        "android bundle (aab)", "android"),
            "app.ipa": (["Payload/App.app/Info.plist"], "ios app archive (ipa)", "ios"),
            "tool.jar": (["META-INF/MANIFEST.MF", "a/B.class"], "java archive (jar)", "desktop-java"),
            "update.zip": (["payload.bin"], "android ota package", "firmware"),
        }
        for name, (members, fmt, route) in cases.items():
            info = ti.identify_file(self.zip_with(name, members))
            self.assertEqual((info["format"], info["route"]), (fmt, route), name)

    def test_harmonyos_packages_are_recognised_by_suffix_and_root_layout(self):
        stage = ti.identify_file(self.zip_with(
            "entry.hap", ["module.json", "ets/modules.abc", "libs/arm64-v8a/libx.so", "META-INF/CERT.SF"]))
        self.assertEqual((stage["format"], stage["route"]), ("harmonyos package (hap)", "harmony"))
        notes = " | ".join(stage["notes"])
        self.assertIn("stage model", notes)
        self.assertIn("Ark bytecode (not DEX): ets/modules.abc", notes)
        self.assertIn("arm64-v8a", notes)
        self.assertIn("signing was not verified", notes)
        fa = ti.identify_file(self.zip_with("lib.hsp", ["config.json"]))
        self.assertEqual(fa["format"], "harmonyos package (hsp)")
        self.assertIn("fa model", " ".join(fa["notes"]))
        pack = ti.identify_file(self.zip_with("App.app", ["entry.hap", "pack.info"]))
        self.assertEqual((pack["format"], pack["route"]), ("harmonyos app pack", "harmony"))

    def test_hap_name_without_a_harmony_root_layout_stays_generic(self):
        info = ti.identify_file(self.zip_with("odd.hap", ["readme.txt"]))
        self.assertEqual((info["format"], info["route"]), ("zip", "archive"))
        self.assertEqual(ti.identify_file(self.zip_with("a.zip", ["module.json"]))["route"], "archive")

    def test_asar_header_is_electron(self):
        archive = build_asar({"main.js": b"console.log(1)\n", "package.json": b"{}"})
        info = ti.identify_file(self.write("app.asar", archive))
        self.assertEqual((info["format"], info["route"], info["members"]),
                         ("asar archive", "desktop-electron", 2))

    def test_firmware_and_archive_signatures(self):
        self.assertEqual(ti.identify_file(self.write("rootfs.sqsh", b"hsqs" + b"\x00" * 60))["route"],
                         "firmware")
        self.assertEqual(ti.identify_file(self.write("kernel.uimage", b"\x27\x05\x19\x56" + b"\x00" * 60))["route"],
                         "firmware")
        gz = ti.identify_file(self.write("fw.gz", b"\x1f\x8b\x08" + b"\x00" * 60))
        self.assertEqual((gz["format"], gz["route"]), ("gzip", "archive"))

    # --- web --------------------------------------------------------------
    def test_web_inputs(self):
        html = ti.identify_file(self.write("index.html", "<!doctype html><html></html>"))
        self.assertEqual((html["format"], html["route"]), ("html document", "web"))
        js = ti.identify_file(self.write("main.js", "const a = 1;\n"))
        self.assertEqual((js["format"], js["route"]), ("javascript", "web"))
        mp = ti.identify_file(self.write("main.js.map", '{"version":3,"sources":[]}'))
        self.assertEqual((mp["format"], mp["route"]), ("source map", "web"))
        wasm = ti.identify_file(self.write("mod.wasm", b"\x00asm\x01\x00\x00\x00"))
        self.assertEqual((wasm["format"], wasm["route"]), ("wasm module", "web"))

    def test_unknown_bytes_have_unknown_route(self):
        info = ti.identify_file(self.write("blob.bin", os.urandom(64) + b"\x00" * 8))
        self.assertEqual(info["route"], "unknown")

    # --- directories ------------------------------------------------------
    def test_directory_routes(self):
        electron = os.path.join(self.root, "Electron App")
        os.makedirs(os.path.join(electron, "resources"))
        with open(os.path.join(electron, "resources", "app.asar"), "wb") as f:
            f.write(build_asar({"main.js": b""}))
        self.assertEqual(ti.identify_dir(electron)["route"], "desktop-electron")

        rootfs = os.path.join(self.root, "rootfs")
        os.makedirs(os.path.join(rootfs, "etc"))
        os.makedirs(os.path.join(rootfs, "bin"))
        self.assertEqual(ti.identify_dir(rootfs)["route"], "firmware")

        bundle = os.path.join(self.root, "Tool.app")
        os.makedirs(os.path.join(bundle, "Contents"))
        with open(os.path.join(bundle, "Contents", "Info.plist"), "w") as f:
            f.write("<plist/>")
        self.assertEqual(ti.identify_dir(bundle)["route"], "desktop-native")

    # --- CLI --------------------------------------------------------------
    def test_cli_prints_json_and_rejects_missing_path(self):
        path = self.write("main.js", "const a = 1;\n")
        r = subprocess.run([sys.executable, SCRIPT, path], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["route"], "web")
        missing = subprocess.run([sys.executable, SCRIPT, os.path.join(self.root, "nope")],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
