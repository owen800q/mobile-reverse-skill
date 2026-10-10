#!/usr/bin/env python3
"""Tests for scripts/mobile_inventory.py: APK, AAB, and IPA layouts on synthetic archives.

The archives are built here, so no app is needed. Real-file checks live in
test_known_answers.py. Every test writes into its own temporary directory.
"""
import json
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "mobile_inventory.py"
sys.path.insert(0, str(SCRIPT.parent))

import mobile_inventory as mi  # noqa: E402


# ----------------------------------------------------------- builders ----------
def axml(package, version_code, version_name):
    """Minimal binary XML: a UTF-16 string pool and one <manifest> element."""
    strings = ["manifest", "package", "versionCode", "versionName", package, version_name]
    encoded = []
    for s in strings:
        encoded.append(struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\x00\x00")
    offsets, off = [], 0
    for body in encoded:
        offsets.append(off)
        off += len(body)
    body = b"".join(encoded)
    body += b"\x00" * ((-len(body)) % 4)
    strings_start = 28 + 4 * len(strings)
    pool_size = strings_start + len(body)
    pool = (struct.pack("<HHI", 0x0001, 28, pool_size)
            + struct.pack("<IIIII", len(strings), 0, 0, strings_start, 0)
            + struct.pack("<%dI" % len(strings), *offsets)
            + body)
    attrs = [(1, 4, 3, 4), (2, 0xFFFFFFFF, 0x10, version_code), (3, 5, 3, 5)]
    element_size = 16 + 20 + 20 * len(attrs)
    element = (struct.pack("<HHI", 0x0102, 16, element_size)
               + struct.pack("<II", 1, 0xFFFFFFFF)
               + struct.pack("<IIHHHHHH", 0xFFFFFFFF, 0, 20, 20, len(attrs), 0, 0, 0)
               + b"".join(struct.pack("<IIIHBBI", 0xFFFFFFFF, name, raw, 8, 0, dtype, data)
                          for name, raw, dtype, data in attrs))
    total = 8 + len(pool) + len(element)
    return struct.pack("<HHI", 0x0003, 8, total) + pool + element


def _dylib_command(name):
    raw = name.encode("utf-8") + b"\x00"
    size = 24 + len(raw)
    size += (-size) % 8
    return struct.pack("<IIIIII", 0xC, size, 24, 0, 0, 0) + raw + b"\x00" * (size - 24 - len(raw))


def macho64(cryptid=1, dylibs=(), with_encryption=True, cputype=0x0100000C):
    """Thin 64-bit little-endian Mach-O header with optional encryption and dylib commands."""
    cmds = b""
    ncmds = 0
    if with_encryption:
        cmds += struct.pack("<IIIIII", 0x2C, 24, 0x4000, 0x100, cryptid, 0)
        ncmds += 1
    for name in dylibs:
        cmds += _dylib_command(name)
        ncmds += 1
    return struct.pack("<IIIIIIII", 0xFEEDFACF, cputype, 0, 2, ncmds, len(cmds), 0, 0) + cmds


def macho32_thin():
    return struct.pack("<IIIIIII", 0xFEEDFACE, 0x0C, 0, 2, 0, 0, 0)


def fat(slices):
    """Big-endian fat header with each (cputype, bytes) slice at a page-aligned offset."""
    header_size = 8 + 20 * len(slices)
    offset = (header_size + 0xFFF) & ~0xFFF
    table, body = b"", b""
    for cputype, blob in slices:
        table += struct.pack(">IIIII", cputype, 0, offset, len(blob), 14)
        body += b"\x00" * (offset - header_size - len(body)) + blob
        offset = (offset + len(blob) + 0xFFF) & ~0xFFF
    return struct.pack(">II", 0xCAFEBABE, len(slices)) + table + body


def plist(value, binary=True):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY if binary else plistlib.FMT_XML)


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return str(path)


def app_plist(**overrides):
    base = {
        "CFBundleIdentifier": "com.example.game",
        "CFBundleName": "Game",
        "CFBundleExecutable": "Game",
        "CFBundleVersion": "7",
        "CFBundleShortVersionString": "1.2",
        "MinimumOSVersion": "13.0",
        "CFBundlePackageType": "APPL",
    }
    base.update(overrides)
    return base


def ipa_entries(**overrides):
    entries = {
        "Payload/Game.app/Info.plist": plist(app_plist()),
        "Payload/Game.app/Game": macho64(
            cryptid=1, dylibs=["@rpath/UnityFramework.framework/UnityFramework",
                               "/usr/lib/libSystem.B.dylib"]),
        "Payload/Game.app/Frameworks/UnityFramework.framework/UnityFramework": b"framework",
        "Payload/Game.app/Data/Managed/Metadata/global-metadata.dat": b"metadata",
        "Payload/Game.app/PlugIns/Share.appex/Info.plist": plist({
            "CFBundleIdentifier": "com.example.game.share",
            "NSExtension": {"NSExtensionPointIdentifier": "com.apple.share-services"},
        }),
        "Payload/Game.app/PlugIns/Custom.appex/Info.plist": plist({
            "NSExtension": {"NSExtensionPointIdentifier": "com.example.custom"},
        }),
        "Payload/Game.app/Watch/Companion.app/Info.plist": plist({"WKCompanionAppBundleIdentifier": "x"}),
        "Payload/Game.app/SC_Info/Game.sinf": b"sinf-bytes",
        "iTunesMetadata.plist": b"<plist>appleId test-account-secret</plist>",
    }
    entries.update(overrides)
    return entries


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def inventory_of(path, max_entries=mi.DEFAULT_MAX_ENTRIES):
    return mi.inventory(path, max_entries)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def archive(self, name, entries):
        return write_zip(self.dir / name, entries)


# ----------------------------------------------------------- Android -----------
class AndroidTests(Base):
    def test_apk_reports_modules_libraries_identity_and_flutter_hint(self):
        path = self.archive("app.apk", {
            "AndroidManifest.xml": axml("io.example.app", 7, "1.2.3"),
            "classes.dex": b"dex", "classes2.dex": b"dex",
            "lib/arm64-v8a/libflutter.so": b"so", "lib/arm64-v8a/libapp.so": b"so",
            "lib/armeabi-v7a/libflutter.so": b"so",
            "assets/flutter_assets/AssetManifest.json": b"{}",
            "assets/html/index.html": b"<html>",
        })
        report = inventory_of(path)
        self.assertEqual((report["status"], report["kind"], report["route"]), ("ok", "apk", "android"))
        manifest = report["android"]["manifest"]
        self.assertEqual((manifest["package"], manifest["version_code"], manifest["version_name"]),
                         ("io.example.app", 7, "1.2.3"))
        module = report["android"]["modules"][0]
        self.assertEqual(module["dex_files"], ["classes.dex", "classes2.dex"])
        self.assertEqual(module["native_libs"], {"arm64-v8a": 2, "armeabi-v7a": 1})
        self.assertEqual(module["asset_dirs"], {"flutter_assets": 1, "html": 1})
        hints = {h["family"]: h for h in report["runtime_hints"]}
        self.assertEqual(hints["flutter"]["strength"], "strong")
        self.assertEqual(hints["flutter"]["scope"], "apk")
        self.assertIn("lib/arm64-v8a/libflutter.so", hints["flutter"]["evidence"])
        self.assertEqual(report["notes"], [])

    def test_native_only_apk_is_noted_and_godot_hint_is_strong(self):
        path = self.archive("native.apk", {
            "AndroidManifest.xml": axml("io.example.game", 1, "0.1"),
            "lib/arm64-v8a/libgodot_android.so": b"so",
        })
        report = inventory_of(path)
        self.assertTrue(any("no classes.dex" in note for note in report["notes"]), report["notes"])
        godot = next(h for h in report["runtime_hints"] if h["family"] == "godot")
        self.assertEqual((godot["strength"], godot["see"]), ("strong", None))

    def test_web_shell_markers_are_weak_until_the_strong_file_appears(self):
        weak_path = self.archive("weak.apk", {
            "AndroidManifest.xml": axml("io.example.web", 1, "1"),
            "classes.dex": b"dex", "assets/www/index.html": b"<html>",
        })
        weak = next(h for h in inventory_of(weak_path)["runtime_hints"] if h["family"] == "cordova")
        self.assertEqual(weak["strength"], "weak")
        strong_path = self.archive("strong.apk", {
            "AndroidManifest.xml": axml("io.example.web", 1, "1"),
            "classes.dex": b"dex", "assets/www/index.html": b"<html>",
            "assets/www/cordova.js": b"//",
        })
        strong = next(h for h in inventory_of(strong_path)["runtime_hints"] if h["family"] == "cordova")
        self.assertEqual(strong["strength"], "strong")
        self.assertEqual(strong["see"], "references/web.md")

    def test_dotnet_assemblies_are_counted_and_hinted(self):
        path = self.archive("net.apk", {
            "AndroidManifest.xml": axml("io.example.net", 1, "1"),
            "classes.dex": b"dex", "assemblies/Mono.Android.dll": b"il",
            "assemblies/App.dll": b"il",
        })
        report = inventory_of(path)
        self.assertEqual(report["android"]["modules"][0]["dotnet_assemblies"], 2)
        dotnet = next(h for h in report["runtime_hints"] if h["family"] == "dotnet")
        self.assertEqual(dotnet["strength"], "strong")

    def test_aab_reports_each_module_and_identity_from_base(self):
        path = self.archive("app.aab", {
            "BundleConfig.pb": b"pb",
            "base/manifest/AndroidManifest.xml": axml("io.example.bundle", 9, "2.0"),
            "base/dex/classes.dex": b"dex",
            "base/lib/x86_64/libil2cpp.so": b"so",
            "base/assets/bin/Data/Managed/Metadata/global-metadata.dat": b"meta",
            "feature/manifest/AndroidManifest.xml": axml("io.example.bundle", 9, "2.0"),
            "feature/dex/classes.dex": b"dex",
            "feature/assets/clip.bin": b"x",
        })
        report = inventory_of(path)
        self.assertEqual(report["kind"], "aab")
        self.assertEqual([m["name"] for m in report["android"]["modules"]], ["base", "feature"])
        self.assertEqual(report["android"]["manifest"]["package"], "io.example.bundle")
        self.assertTrue(report["android"]["bundle_config"])
        base_hints = [h for h in report["runtime_hints"] if h["scope"] == "module:base"]
        self.assertEqual([h["family"] for h in base_hints], ["unity"])
        self.assertEqual(base_hints[0]["strength"], "strong")
        self.assertFalse([h for h in report["runtime_hints"] if h["scope"] == "module:feature"])

    def test_oversized_manifest_is_reported_not_read(self):
        path = self.archive("big.apk", {"AndroidManifest.xml": b"x" * 64, "classes.dex": b"dex"})
        with mock.patch.object(mi, "MAX_MANIFEST_BYTES", 8):
            report = inventory_of(path)
        self.assertEqual(report["android"]["manifest"]["status"], "too_large")
        self.assertIn("manifest not decoded: too_large", report["notes"])

    def test_member_with_unsupported_compression_is_unreadable_not_fatal(self):
        path = self.archive("odd.apk", {"AndroidManifest.xml": axml("io.example.odd", 1, "1"),
                                        "classes.dex": b"dex"})
        with mock.patch.object(zipfile.ZipFile, "open", side_effect=NotImplementedError("deflate64")):
            report = inventory_of(path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["android"]["manifest"]["status"], "unreadable")
        self.assertIn("manifest not decoded: unreadable", report["notes"])

    def test_unparseable_manifest_does_not_stop_the_inventory(self):
        path = self.archive("junk.apk", {"AndroidManifest.xml": b"not binary xml at all",
                                         "classes.dex": b"dex"})
        report = inventory_of(path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["android"]["manifest"]["status"], "unparsed")
        self.assertEqual(report["android"]["modules"][0]["dex_count"], 1)


# ----------------------------------------------------------- iOS ---------------
class IosTests(Base):
    def test_ipa_reports_identity_executable_extensions_and_unity_hint(self):
        path = self.archive("game.ipa", ipa_entries())
        report = inventory_of(path)
        self.assertEqual((report["status"], report["kind"], report["route"]), ("ok", "ipa", "ios"))
        ios = report["ios"]
        self.assertEqual(ios["info"]["bundle_id"], "com.example.game")
        self.assertEqual(ios["info"]["short_version"], "1.2")
        self.assertEqual(ios["info"]["version"], "7")
        self.assertEqual(ios["info"]["minimum_os"], "13.0")
        self.assertEqual(ios["info"]["name"], "Game")
        executable = ios["executable"]
        self.assertEqual((executable["status"], executable["archs"]), ("ok", ["arm64"]))
        self.assertEqual((executable["cryptid"], executable["encryption"]), (1, "encrypted"))
        self.assertIn("@rpath/UnityFramework.framework/UnityFramework", executable["linked_dylibs"])
        self.assertEqual(ios["frameworks"], ["UnityFramework.framework"])
        self.assertEqual(ios["watch_apps"], ["Companion.app"])
        self.assertEqual(ios["sc_info"], ["Game.sinf"])
        self.assertEqual(ios["itunes_metadata"], "present")
        extensions = {e["name"]: e for e in ios["extensions"]}
        self.assertEqual(extensions["Share.appex"]["role"], "share")
        self.assertEqual(extensions["Share.appex"]["path_role"], "app-extension")
        self.assertEqual(extensions["Share.appex"]["bundle_id"], "com.example.game.share")
        self.assertEqual(extensions["Custom.appex"]["role"], "unmapped")
        self.assertEqual(extensions["Custom.appex"]["point"], "com.example.custom")
        unity = next(h for h in report["runtime_hints"] if h["family"] == "unity")
        self.assertEqual(unity["strength"], "strong")
        self.assertIn("linked: @rpath/UnityFramework.framework/UnityFramework", unity["evidence"])
        self.assertTrue(any("FairPlay-encrypted" in note for note in report["notes"]))

    def test_account_metadata_content_is_never_echoed(self):
        path = self.archive("game.ipa", ipa_entries())
        proc = run_cli(path)
        self.assertNotIn("test-account-secret", proc.stdout)
        self.assertNotIn("appleId", proc.stdout)

    def test_decrypted_executable_reports_not_encrypted(self):
        path = self.archive("clear.ipa", ipa_entries(**{"Payload/Game.app/Game": macho64(cryptid=0)}))
        report = inventory_of(path)
        self.assertEqual(report["ios"]["executable"]["encryption"], "not-encrypted")
        self.assertFalse(any("FairPlay" in note for note in report["notes"]))

    def test_executable_without_encryption_command(self):
        path = self.archive("plain.ipa", ipa_entries(**{"Payload/Game.app/Game": macho64(with_encryption=False)}))
        self.assertEqual(inventory_of(path)["ios"]["executable"]["encryption"], "no-encryption-command")

    def test_fat_executable_lists_slices_and_reads_the_first(self):
        slices = [(0x0100000C, macho64(cryptid=0)), (0x01000007, macho64(cryptid=1, cputype=0x01000007))]
        path = self.archive("fat.ipa", ipa_entries(**{"Payload/Game.app/Game": fat(slices)}))
        executable = inventory_of(path)["ios"]["executable"]
        self.assertEqual(executable["archs"], ["arm64", "x86_64"])
        self.assertEqual((executable["status"], executable["cryptid"]), ("ok", 0))

    def test_truncated_load_commands_are_malformed_not_fatal(self):
        header = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 1, 4096, 0, 0)
        path = self.archive("cut.ipa", ipa_entries(**{"Payload/Game.app/Game": header}))
        report = inventory_of(path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["ios"]["executable"]["status"], "malformed")

    def test_non_macho_executable_is_reported(self):
        path = self.archive("script.ipa", ipa_entries(**{"Payload/Game.app/Game": b"#!/bin/sh\necho\n"}))
        self.assertEqual(inventory_of(path)["ios"]["executable"]["status"], "not-macho")

    def test_missing_executable_is_reported(self):
        entries = ipa_entries()
        del entries["Payload/Game.app/Game"]
        report = inventory_of(self.archive("missing.ipa", entries))
        self.assertEqual(report["ios"]["executable"]["status"], "missing")

    def test_missing_executable_name_falls_back_with_a_note(self):
        entries = ipa_entries()
        entries["Payload/Game.app/Info.plist"] = plist({k: v for k, v in app_plist().items()
                                                       if k != "CFBundleExecutable"})
        report = inventory_of(self.archive("noexec.ipa", entries))
        self.assertIn("CFBundleExecutable is missing; assumed Game", report["notes"])
        self.assertEqual(report["ios"]["executable"]["status"], "ok")

    def test_unparseable_info_plist_is_reported(self):
        report = inventory_of(self.archive("bad.ipa", ipa_entries(
            **{"Payload/Game.app/Info.plist": b"not a plist"})))
        self.assertEqual(report["ios"]["info"]["status"], "unparsed")

    def test_oversized_info_plist_is_not_parsed(self):
        with mock.patch.object(mi, "MAX_PLIST_BYTES", 16):
            report = inventory_of(self.archive("huge.ipa", ipa_entries()))
        self.assertEqual(report["ios"]["info"]["status"], "too_large")

    def test_extension_without_extension_dictionary_has_unknown_role(self):
        entries = ipa_entries(**{"Payload/Game.app/PlugIns/Bare.appex/Info.plist": plist({"CFBundleIdentifier": "x"})})
        extensions = {e["name"]: e for e in inventory_of(self.archive("bare.ipa", entries))["ios"]["extensions"]}
        self.assertEqual(extensions["Bare.appex"]["role"], "unknown")

    def test_playcover_playtools_shim_is_hinted_from_linked_dylib(self):
        entries = ipa_entries(**{"Payload/Game.app/Game": macho64(
            cryptid=0, dylibs=["@rpath/PlayTools.framework/PlayTools"])})
        hints = inventory_of(self.archive("shim.ipa", entries))["runtime_hints"]
        shim = next(h for h in hints if h["family"] == "playcover-playtools")
        self.assertEqual((shim["strength"], shim["see"]), ("strong", "references/ios-playcover.md"))

    def test_multiple_app_bundles_are_noted_and_the_first_is_inspected(self):
        entries = ipa_entries()
        entries["Payload/Other.app/Info.plist"] = plist(app_plist(CFBundleIdentifier="com.example.other"))
        report = inventory_of(self.archive("two.ipa", entries))
        self.assertEqual(report["ios"]["app_bundles"], 2)
        self.assertEqual(report["ios"]["bundle_path"], "Payload/Game.app")
        self.assertTrue(any("2 app bundles" in note for note in report["notes"]))


# ----------------------------------------------------------- refusals ----------
class RefusalTests(Base):
    def test_non_archive_is_unrecognized_and_exits_one(self):
        path = self.dir / "notes.txt"
        path.write_text("plain text\n", encoding="utf-8")
        report = inventory_of(str(path))
        self.assertEqual((report["status"], report["kind"]), ("unrecognized", "unrecognized"))
        self.assertEqual(run_cli(str(path)).returncode, 1)

    def test_zip_without_a_mobile_layout_is_unrecognized(self):
        path = self.archive("readme.zip", {"README.md": b"hello"})
        self.assertEqual(inventory_of(path)["status"], "unrecognized")

    def test_truncated_zip_is_malformed_and_exits_one(self):
        good = self.archive("good.apk", {"AndroidManifest.xml": axml("io.example", 1, "1"),
                                         "classes.dex": b"dex" * 200})
        data = Path(good).read_bytes()
        cut = self.dir / "cut.apk"
        cut.write_bytes(data[: len(data) // 2])
        self.assertEqual(inventory_of(str(cut))["status"], "malformed")
        self.assertEqual(run_cli(str(cut)).returncode, 1)

    def test_entry_needing_a_newer_zip_version_is_malformed_not_a_crash(self):
        path = self.archive("newer.apk", {"AndroidManifest.xml": axml("io.example", 1, "1"),
                                          "classes.dex": b"dex"})
        data = bytearray(Path(path).read_bytes())
        at = data.find(b"PK\x01\x02")
        self.assertNotEqual(at, -1)
        data[at + 6] = 0xFF  # "version needed to extract": 25.5, beyond what zipfile supports
        Path(path).write_bytes(bytes(data))
        report = inventory_of(path)
        self.assertEqual(report["status"], "malformed")

    def test_entry_cap_refuses_large_archives(self):
        path = self.archive("many.apk", {"AndroidManifest.xml": b"x", "classes.dex": b"dex"})
        self.assertEqual(inventory_of(path, max_entries=1)["status"], "too_many_entries")
        proc = run_cli(path, "--max-entries", "1")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["status"], "too_many_entries")

    def test_missing_path_and_bad_cap_are_usage_errors(self):
        self.assertEqual(run_cli(str(self.dir / "absent.apk")).returncode, 2)
        path = self.archive("ok.apk", {"AndroidManifest.xml": axml("io.example", 1, "1")})
        self.assertEqual(run_cli(path, "--max-entries", "0").returncode, 2)


# ----------------------------------------------------------- parsers -----------
class ParserTests(unittest.TestCase):
    def test_binary_xml_reads_package_and_versions(self):
        attrs = mi.parse_axml(axml("io.example.parse", 42, "9.9"))
        self.assertEqual(attrs, {"package": "io.example.parse", "version_code": 42, "version_name": "9.9"})

    def test_binary_xml_rejects_other_data(self):
        with self.assertRaises(mi.Malformed):
            mi.parse_axml(b"x" * 40)
        with self.assertRaises(mi.Malformed):
            mi.parse_axml(b"tiny")

    def test_fat_and_thin_macho_headers_are_recognised_by_magic(self):
        self.assertEqual(mi.FAT_MAGIC, b"\xca\xfe\xba\xbe")
        self.assertEqual(macho32_thin()[:4], mi.MH_MAGIC_32)
        self.assertEqual(macho64()[:4], mi.MH_MAGIC_64)

    def test_classify_distinguishes_the_three_layouts(self):
        self.assertEqual(mi.classify(["Payload/A.app/Info.plist"])[0], "ipa")
        self.assertEqual(mi.classify(["BundleConfig.pb", "base/manifest/AndroidManifest.xml"])[0], "aab")
        self.assertEqual(mi.classify(["AndroidManifest.xml", "classes.dex"])[0], "apk")
        self.assertEqual(mi.classify(["README"])[0], "unrecognized")


if __name__ == "__main__":
    unittest.main()
