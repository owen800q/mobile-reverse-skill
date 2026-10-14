#!/usr/bin/env python3
"""Tests for the ports taken from the morluto/rea review: trigger name case, AppleDouble
sidecars, the Mach-O build-version record, SAZ archives, and wrapped Electron IPC calls."""
import io
import json
import os
import shutil
import sqlite3
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import electron_ipc_map as em  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
