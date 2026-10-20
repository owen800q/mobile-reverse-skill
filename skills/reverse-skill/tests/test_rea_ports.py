#!/usr/bin/env python3
"""Tests for the ports taken from the morluto/rea review: trigger name case, AppleDouble
sidecars, the Mach-O build-version record, SAZ archives, wrapped Electron IPC calls,
asset directory-entry counting, and DEX-member routing precision."""
import io
import json
import os
import shutil
import sqlite3
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import electron_ipc_map as em  # noqa: E402
import js_rpc_inventory as rpc  # noqa: E402
import js_sourcemap_extract as sm  # noqa: E402
import har_parse  # noqa: E402
import mobile_inventory as mi  # noqa: E402
import sqlite_inspect as si  # noqa: E402
import smali_callers as sc  # noqa: E402
import target_identify as ti  # noqa: E402


class SqliteTriggerCaseTests(unittest.TestCase):
    def test_trigger_declared_with_other_case_is_listed(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "app.db")
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE Users (id INTEGER PRIMARY KEY, name TEXT);"
            "CREATE TABLE audit (id INTEGER);"
            "CREATE TRIGGER log_users AFTER INSERT ON users BEGIN "
            "INSERT INTO audit VALUES (new.id); END;")
        conn.commit()
        conn.close()
        result = si.inspect_database(path, table="Users")
        self.assertIn("log_users", json.dumps(result))
        shutil.rmtree(tmp)


class SidecarTests(unittest.TestCase):
    def test_appledouble_and_macosx_copies_are_sidecars(self):
        self.assertTrue(mi.is_sidecar("Payload/X.app/Frameworks/._libfoo.dylib"))
        self.assertTrue(mi.is_sidecar("__MACOSX/Payload/X.app/Info.plist"))
        self.assertFalse(mi.is_sidecar("Payload/X.app/Frameworks/libfoo.framework/libfoo"))


def macho_with_build(platform, minos, sdk, tools):
    """A thin little-endian 64-bit Mach-O header with one LC_BUILD_VERSION command."""
    tool_bytes = b"".join(struct.pack("<II", t, v) for t, v in tools)
    cmdsize = 24 + len(tool_bytes)
    cmd = struct.pack("<IIIIII", 0x32, cmdsize, platform, minos, sdk, len(tools)) + tool_bytes
    header = struct.pack("<IIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 1, len(cmd), 0)
    header += b"\x00" * 4  # reserved word of the 64-bit header
    return header + cmd + b"\x00" * 64


class BuildVersionTests(unittest.TestCase):
    def test_macho_build_reads_platform_minos_sdk_and_tools(self):
        raw = macho_with_build(2, (16 << 16), (17 << 16) | (2 << 8), [(3, (1 << 16))])
        build = ti.macho_build(raw[32:], 1)
        self.assertEqual(build["platform"], "iOS")
        self.assertEqual(build["minos"], "16.0.0")
        self.assertEqual(build["sdk"], "17.2.0")
        self.assertEqual(build["tools"], [{"tool": "ld", "version": "1.0.0"}])

    def test_identify_names_ios_slice_instead_of_macos(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "App")
        with open(path, "wb") as fh:
            fh.write(macho_with_build(2, 16 << 16, 17 << 16, [(3, 1 << 16)]))
        info = ti.identify_file(path)
        shutil.rmtree(tmp)
        self.assertEqual(info["build"]["platform"], "iOS")
        self.assertTrue(any("iOS binary" in n or "iOS-family" in n for n in info["notes"]))
        self.assertFalse(any("macOS binary" in n for n in info["notes"]))

    def test_truncated_table_yields_no_build(self):
        raw = macho_with_build(2, 16 << 16, 17 << 16, [])
        self.assertIsNone(ti.macho_build(raw[32:40], 1))


def _saz(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class SazTests(unittest.TestCase):
    def test_session_becomes_send_and_recv_entries(self):
        raw = _saz({
            "raw/1_c.txt": b"POST https://api.example.com/v1/login HTTP/1.1\r\nHost: api.example.com\r\n"
                           b"Content-Type: application/json\r\n\r\n{\"user\":\"u\"}",
            "raw/1_s.txt": b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":true}",
            "raw/1_m.xml": b'<Session><SessionTimers ClientConnected="10/13/2026 5:51:14 AM"/></Session>',
        })
        log, notes = har_parse.saz_to_har(raw)
        self.assertEqual(notes, [])
        entry = log["entries"][0]
        self.assertEqual(entry["request"]["method"], "POST")
        self.assertEqual(entry["response"]["status"], 200)
        self.assertEqual(entry["startedDateTime"], "10/13/2026 5:51:14 AM")
        self.assertEqual(entry["response"]["content"]["encoding"], "base64")

    def test_websocket_members_are_listed_not_decoded(self):
        raw = _saz({"raw/1_c.txt": b"GET / HTTP/1.1\r\nHost: h\r\n\r\n",
                    "raw/1_s.txt": b"HTTP/1.1 101 Switching\r\n\r\n",
                    "raw/1_w.txt": b"frames"})
        _log, notes = har_parse.saz_to_har(raw)
        self.assertTrue(any("raw/1_w.txt" in n for n in notes))

    def test_encrypted_member_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("raw/1_c.txt", b"x")
        data = bytearray(buf.getvalue())
        # Set the encryption flag in the local and central headers.
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            pos = data.find(sig)
            data[pos + off] |= 0x1
        with self.assertRaises(har_parse.SazError) as ctx:
            har_parse.saz_to_har(bytes(data))
        self.assertIn("encrypted", str(ctx.exception))

    def test_archive_without_sessions_is_refused(self):
        with self.assertRaises(har_parse.SazError):
            har_parse.saz_to_har(_saz({"other.txt": b"x"}))


class ElectronWrapperTests(unittest.TestCase):
    def scan_files(self, files):
        root = tempfile.mkdtemp()
        for name, text in files.items():
            p = os.path.join(root, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
        result = em.scan(root)
        shutil.rmtree(root)
        return result

    def test_wrapped_calls_pair_with_their_handlers(self):
        result = self.scan_files({
            "preload.js": 'const { contextBridge, ipcRenderer } = require("electron");\n'
                          'contextBridge.exposeInMainWorld("api", {\n'
                          '  invoke: (channel, ...a) => ipcRenderer.invoke(channel, ...a),\n'
                          '});\n',
            "main.js": 'const register = (ch, h) => ipcMain.handle(ch, h);\n'
                       'register("data:get", () => 1);\n',
            "renderer.js": 'window.api.invoke("data:get");\n',
        })
        channels = {c["name"]: c for c in result["channels"]}
        self.assertEqual(channels["data:get"]["status"], "paired")
        main_use = channels["data:get"]["main"][0]
        renderer_use = channels["data:get"]["renderer"][0]
        self.assertEqual(main_use["via_wrapper"], "register")
        self.assertEqual(renderer_use["via_wrapper"], "api.invoke")

    def test_optional_calls_and_listener_forms_are_read(self):
        result = self.scan_files({
            "main.js": 'ipcMain?.handle("opt:chain", () => 2);\n'
                       'ipcMain.handle?.("opt:call", () => 3);\n'
                       'ipcMain.addListener("doc:save", () => 4);\n'
                       'webContents.postMessage("push:tick", {});\n',
        })
        channels = {c["name"]: c for c in result["channels"]}
        self.assertEqual(channels["opt:chain"]["main"][0]["kind"], "handle")
        self.assertEqual(channels["opt:call"]["main"][0]["kind"], "handle")
        self.assertEqual(channels["doc:save"]["main"][0]["kind"], "addListener")
        self.assertEqual(channels["push:tick"]["main"][0]["kind"], "postMessage")

    def test_dynamic_wrapped_argument_is_listed_as_dynamic(self):
        result = self.scan_files({
            "preload.js": 'contextBridge.exposeInMainWorld("api", {\n'
                          '  invoke: (channel) => ipcRenderer.invoke(channel),\n});\n',
            "renderer.js": 'window.api.invoke(nameVar);\n',
        })
        self.assertTrue(any(d["argument"] == "nameVar" and d.get("via_wrapper") == "api.invoke"
                            for d in result["dynamic"]))


class SmaliCallerTests(unittest.TestCase):
    def tree(self, files):
        root = tempfile.mkdtemp()
        for name, text in files.items():
            p = os.path.join(root, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
        return root

    def test_callers_name_class_method_kind_and_overload(self):
        root = self.tree({
            "smali/com/example/Caller.smali":
                ".class public Lcom/example/Caller;\n"
                ".method public run()V\n"
                "    invoke-static {v0, v1}, Lcom/example/Api;->send(Ljava/lang/String;I)V\n"
                "    invoke-virtual {v0}, Lcom/example/Api;->send(Ljava/lang/String;)V\n"
                ".end method\n"
                ".method private other()V\n"
                "    invoke-virtual/range {v0 .. v3}, Lcom/example/Api;->send(Ljava/lang/String;I)V\n"
                ".end method\n",
        })
        report = sc.build_report(root, "com.example.Api", "send")
        self.assertEqual(report["total"], 3)
        kinds = sorted(c["invoke"] for c in report["callers"])
        self.assertEqual(kinds, ["invoke-static", "invoke-virtual", "invoke-virtual/range"])
        first = report["callers"][0]
        self.assertEqual(first["caller_class"], "Lcom/example/Caller;")
        self.assertEqual(first["caller_method"], "run()V")
        self.assertEqual(first["line"], 3)

        narrowed = sc.build_report(root, "com.example.Api", "send", params="Ljava/lang/String;I")
        self.assertEqual(narrowed["total"], 2)
        self.assertEqual(narrowed["target"]["smali_class"], "Lcom/example/Api;")

    def test_no_callers_is_reported_with_zero_total(self):
        root = self.tree({"smali/A.smali": ".class public LA;\n.method m()V\n    return-void\n.end method\n"})
        self.assertEqual(sc.build_report(root, "com.example.Api", "send")["total"], 0)

    def test_missing_root_is_refused(self):
        with self.assertRaises(sc.InputError):
            sc.build_report("/nonexistent/smali", "com.example.Api", "send")


class FatSliceTests(unittest.TestCase):
    def test_each_slice_carries_its_own_width_and_byte_order(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "Universal")
        fat = (b"\xca\xfe\xba\xbe" + struct.pack(">I", 3)
               + struct.pack(">IIIII", 0x01000007, 3, 0x1000, 0x100, 12)
               + struct.pack(">IIIII", 0x0100000C, 0, 0x2000, 0x100, 14)
               + struct.pack(">IIIII", 0x00000012, 0, 0x3000, 0x100, 12))
        with open(path, "wb") as fh:
            fh.write(fat.ljust(0x4000, b"\x00"))
        info = ti.identify_file(path)
        shutil.rmtree(tmp)
        got = [(s["arch"], s["bits"], s["endian"]) for s in info["slices"]]
        self.assertEqual(got, [("x86-64", 64, "LE"), ("AArch64", 64, "LE"), ("PowerPC", 32, "BE")])
        self.assertEqual(info["endian"], "BE")  # the fat table's order, kept for old callers

    def test_arm64_32_slice_is_named_with_a_32_bit_width(self):
        self.assertEqual(ti._macho_arch(0x0200000C, 1), "arm64_32")
        self.assertEqual(ti.MACHO_CPU[0x0200000C], "arm64_32")


class GraphqlIgnoredTokenTests(unittest.TestCase):
    def names(self, text):
        out = []
        rpc._graphql(text, lambda i: 1, "x.js", out)
        return [(o["kind"], o["name"]) for o in out if o["mechanism"] == "literal"]

    def test_comments_commas_and_escapes_between_tokens_are_ignored(self):
        text = (r'const a = "query # c\nGetUser { user { id } }";'
                '\nconst b = "mutation, Save($x: T) { save(x: $x) { ok } }";'
                '\nconst c = `query GetUser # keep\n{ user { id } }`;'
                '\nconst d = "query GetUser( # c\\n$id: ID!) { user(id: $id) { name } }";'
                '\nconst e = "query Named @cached # c\\n{ me }";')
        self.assertEqual(self.names(text), [("query", "GetUser"), ("mutation", "Save"),
                                            ("query", "GetUser"), ("query", "GetUser"),
                                            ("query", "Named")])

    def test_a_comment_cannot_hide_the_operation_it_precedes_or_contains(self):
        self.assertEqual(self.names(r'const a = "query # GetUser { user }";'), [])
        self.assertEqual(self.names(r'const b = "query # anonymous\n{ user }";'), [])

    def test_long_comment_runs_stay_linear(self):
        text = '"query ' + "# x\\n" * 20000 + '"'
        self.assertEqual(self.names(text), [])


class DuplicateMemberTests(unittest.TestCase):
    def test_repeated_member_names_are_reported_with_copy_counts(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "app.apk")
        with zipfile.ZipFile(path, "w") as zf, warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # zipfile warns about the repeat on purpose
            zf.writestr("AndroidManifest.xml", b"x")
            zf.writestr("classes.dex", b"first")
            zf.writestr("classes.dex", b"second")
        report = mi.inventory(path)
        shutil.rmtree(tmp)
        self.assertEqual(report["duplicate_members"], [{"name": "classes.dex", "copies": 2}])
        self.assertTrue(any("more than once" in n for n in report["notes"]))


class CurrentDirectoryPrefixTests(unittest.TestCase):
    def zip_with(self, name, members):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, name)
        with zipfile.ZipFile(path, "w") as zf:
            for member, data in members:
                zf.writestr(member, data)
        return path

    def test_apk_written_with_dot_slash_members_is_classified_as_apk(self):
        path = self.zip_with("app.apk", [("./AndroidManifest.xml", b"x"), ("./classes.dex", b"dex")])
        report = mi.inventory(path)
        self.assertEqual(report["kind"], "apk")
        self.assertEqual(report["route"], "android")

    def test_ipa_written_with_dot_slash_members_lists_its_app(self):
        plist = b"<?xml version='1.0'?><plist version='1.0'><dict><key>CFBundleIdentifier</key><string>x.y</string></dict></plist>"
        path = self.zip_with("app.ipa", [("./Payload/Demo.app/Info.plist", plist)])
        report = mi.inventory(path)
        self.assertEqual(report["kind"], "ipa")
        self.assertEqual(report["route"], "ios")

    def test_logical_view_reads_the_member_under_its_archive_spelling(self):
        path = self.zip_with("view.zip", [("./a/b.txt", b"hello")])
        with zipfile.ZipFile(path) as zf:
            view = mi.LogicalView(zf, zf.namelist())
            with view.open(view.getinfo("a/b.txt")) as fh:
                self.assertEqual(fh.read(), b"hello")
            with self.assertRaises(KeyError):
                view.getinfo("missing")

    def test_identify_routes_dot_slash_ipa_to_ios(self):
        path = self.zip_with("app.ipa", [("./Payload/Demo.app/Info.plist", b"x")])
        info = {"notes": []}
        ti._zip(path, info)
        self.assertEqual(info["route"], "ios")


class SourceMapDotSegmentTests(unittest.TestCase):
    def test_empty_segment_is_cancelled_by_a_following_parent_reference(self):
        self.assertEqual(sm._url_path("assets//../app.js"), "assets/app.js")

    def test_plain_and_current_directory_references_are_unchanged(self):
        self.assertEqual(sm._url_path("./maps/app.js.map"), "maps/app.js.map")
        self.assertEqual(sm._url_path("a//b.map"), "a//b.map")

    def test_references_above_the_start_and_absolute_paths_are_kept(self):
        self.assertEqual(sm._url_path("../../x.map"), "../../x.map")
        self.assertEqual(sm._url_path("/x.map"), "/x.map")


class HexagonElfTests(unittest.TestCase):
    def test_hexagon_elf_is_named_not_unknown(self):
        ident = b"\x7fELF" + bytes([2, 1, 1]) + b"\x00" * 9
        hdr = ident + struct.pack("<HHI", 3, 164, 1) + b"\x00" * 40
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "libadsprpc.so")
            with open(path, "wb") as fh:
                fh.write(hdr)
            info = ti.identify_file(path)
        self.assertEqual((info["format"], info["arch"]), ("ELF", "Hexagon"))


class AssetDirectoryCountTests(unittest.TestCase):
    """A ZIP directory entry under assets/ is not an asset file, so it must not be counted."""

    def test_directory_entries_do_not_inflate_asset_counts(self):
        rels = ["assets/", "assets/foo/", "assets/foo/data.bin", "assets/top.json"]
        record = mi.module_record("base", rels)
        # one file directly under assets/ ("(files)"), one under foo/; the bare
        # directory entries assets/ and assets/foo/ are not counted.
        self.assertEqual(record["asset_dirs"], {"(files)": 1, "foo": 1})


class UrlAuthorityBoundaryTests(unittest.TestCase):
    """A backslash ends the authority of a special-scheme URL, and an @ in the path is
    not userinfo, so a crafted URL cannot hide its real host or lose its path."""

    def test_crafted_backslash_url_resolves_the_real_host_and_path(self):
        host, path, query = har_parse._host_path_query(
            "https://user:pass@app.example.test\\path@tail/../keep?x=1")
        self.assertEqual(host, "app.example.test")
        self.assertEqual(path, "\\path@tail/../keep")
        self.assertEqual(query, "x=1")

    def test_redaction_keeps_the_real_host(self):
        red, count = har_parse._redact_url(
            "https://user:secret@app.example.test\\x@fake/p?token=abc")
        self.assertIn("app.example.test", red)
        self.assertNotIn("secret", red)
        self.assertGreaterEqual(count, 1)

    def test_well_formed_url_is_bounded_exactly_as_before(self):
        host, path, query = har_parse._host_path_query("https://u:p@ex.com:8443/a/b?q=1#f")
        self.assertEqual((host, path, query), ("ex.com:8443", "/a/b", "q=1"))


class DexRoutingPrecisionTests(unittest.TestCase):
    def zip_with(self, name, members):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, name)
        with zipfile.ZipFile(path, "w") as zf:
            for member in members:
                zf.writestr(member, b"x")
        return path

    def test_asset_named_classes_dex_does_not_route_to_android(self):
        path = self.zip_with("mystery.zip", ["assets/myclasses.dex", "readme.txt"])
        info = {"notes": []}
        ti._zip(path, info)
        self.assertNotEqual(info.get("route"), "android")

    def test_root_and_multidex_and_dex_dir_still_route_to_android(self):
        for member in ("classes.dex", "classes2.dex", "dex/classes.dex"):
            path = self.zip_with("app.apk", [member])
            info = {"notes": []}
            ti._zip(path, info)
            self.assertEqual(info.get("route"), "android", member)


def _make_pe(machine, magic, clr=False):
    buf = bytearray(0x400)
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", buf, 0x84, machine, 1)
    opt_size = 240 if magic == 0x20B else 224
    struct.pack_into("<H", buf, 0x84 + 16, opt_size)
    struct.pack_into("<H", buf, 0x84 + 18, 0x0002)
    opt = 0x84 + 20
    struct.pack_into("<H", buf, opt, magic)
    if clr:
        dd_off = 112 if magic == 0x20B else 96
        struct.pack_into("<II", buf, opt + dd_off + 14 * 8, 0x2000, 0x48)
    return bytes(buf)


class PeArchitectureTests(unittest.TestCase):
    def _info(self, data):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "a.bin")
        with open(path, "wb") as fh:
            fh.write(data)
        return ti.identify_file(path)

    def test_thumb_machine_is_named(self):
        info = self._info(_make_pe(0x01C2, 0x10B))
        self.assertEqual(info["arch"], "Thumb")

    def test_magic_contradicting_machine_reports_no_arch(self):
        info = self._info(_make_pe(0x8664, 0x10B))  # AMD64 machine, PE32 (32-bit) magic
        self.assertIsNone(info["arch"])
        self.assertTrue(any("contradicts" in n for n in info["notes"]))

    def test_readytorun_linux_override_is_arch_only_when_managed(self):
        linux_amd64 = 0x8664 ^ 0x7B79
        native = self._info(_make_pe(linux_amd64, 0x20B))
        self.assertTrue(str(native["arch"]).startswith("unknown("))
        self.assertTrue(any("override" in n for n in native["notes"]))
        managed = self._info(_make_pe(linux_amd64, 0x20B, clr=True))
        self.assertEqual(managed["arch"], "x86-64")
        self.assertTrue(managed["managed"])


class DesktopSignatureTests(unittest.TestCase):
    def _info(self, name, data):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return ti.identify_file(path)

    def test_il2cpp_metadata_magic_routes_to_unity(self):
        info = self._info("global-metadata.dat", b"\xaf\x1b\xb1\xfa\x1f\x00\x00\x00" + b"\x00" * 64)
        self.assertEqual(info["route"], "unity")
        self.assertIn("il2cpp_metadata.py", info["reference"])

    def test_godot_pck_header(self):
        info = self._info("game.pck", b"GDPC" + b"\x00" * 60)
        self.assertEqual((info["format"], info["route"]), ("godot pck", "godot"))

    def test_unreal_iostore_marker(self):
        info = self._info("game.utoc", b"-==--==--==--==-" + b"\x00" * 48)
        self.assertEqual(info["route"], "unreal")

    def test_gamemaker_needs_gen8_after_form(self):
        gm = self._info("data.win", b"FORM" + struct.pack("<I", 100) + b"GEN8" + b"\x00" * 64)
        self.assertEqual(gm["route"], "gamemaker")
        # A bare FORM container (AIFF/IFF) without GEN8 is not GameMaker.
        other = self._info("sound.aiff", b"FORM" + struct.pack("<I", 100) + b"AIFF" + b"\x00" * 64)
        self.assertNotEqual(other.get("route"), "gamemaker")

    def test_unity_player_directory_mono_and_il2cpp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        mono = os.path.join(tmp, "mono")
        os.makedirs(os.path.join(mono, "Game_Data", "Managed"))
        self.assertEqual(ti.identify_dir(mono)["route"], "unity")
        il2 = os.path.join(tmp, "il2")
        meta_dir = os.path.join(il2, "Game_Data", "il2cpp_data", "Metadata")
        os.makedirs(meta_dir)
        open(os.path.join(meta_dir, "global-metadata.dat"), "wb").close()
        info = ti.identify_dir(il2)
        self.assertEqual(info["format"], "unity player directory (il2cpp)")


if __name__ == "__main__":
    unittest.main()
