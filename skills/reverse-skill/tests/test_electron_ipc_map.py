#!/usr/bin/env python3
"""Tests for scripts/electron_ipc_map.py: pairing, dynamic channels, comments, exposure, skips."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "electron_ipc_map.py"
sys.path.insert(0, str(SCRIPT.parent))

import electron_ipc_map as em  # noqa: E402

MAIN_JS = """const { ipcMain } = require('electron');
ipcMain.handle('get-config', async () => ({ theme: 'dark' }));
ipcMain.on('log-event', (event, msg) => console.log(msg));
ipcMain.handle('orphan', () => 1);
// ipcMain.handle('commented-out', () => 2);
win.webContents.send('state-changed', { ok: true });
"""
PRELOAD_JS = """const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('api', {
  getConfig: () => ipcRenderer.invoke('get-config'),
  missing: () => ipcRenderer.invoke('missing-handler'),
  log: (m) => ipcRenderer.send('log-event', m),
  dynamic: (name) => ipcRenderer.invoke(name),
});
ipcRenderer.on('state-changed', (e, s) => render(s));
"""


class IpcMapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "app"
        (self.root / "main").mkdir(parents=True)
        (self.root / "preload").mkdir(parents=True)
        (self.root / "main" / "index.js").write_text(MAIN_JS, encoding="utf-8")
        (self.root / "preload" / "index.js").write_text(PRELOAD_JS, encoding="utf-8")
        self.result = em.scan(str(self.root))
        self.channels = {c["name"]: c for c in self.result["channels"]}

    def tearDown(self):
        self._tmp.cleanup()

    def scan_files(self, files):
        """Scan a fresh source tree holding the given {relative path: text} files."""
        root = Path(tempfile.mkdtemp(dir=self._tmp.name))
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return em.scan(str(root))

    def make_root(self):
        return Path(tempfile.mkdtemp(dir=self._tmp.name))

    @staticmethod
    def channel_map(result):
        return {c["name"]: c for c in result["channels"]}

    def test_invoke_paired_with_handle(self):
        self.assertEqual(self.channels["get-config"]["status"], "paired")

    def test_renderer_send_paired_with_main_on(self):
        self.assertEqual(self.channels["log-event"]["status"], "paired")

    def test_main_send_paired_with_renderer_on(self):
        self.assertEqual(self.channels["state-changed"]["status"], "paired")

    def test_invoke_without_handler_is_unhandled(self):
        self.assertEqual(self.channels["missing-handler"]["status"], "unhandled")

    def test_handler_without_sender_is_unused(self):
        self.assertEqual(self.channels["orphan"]["status"], "unused")

    def test_commented_out_channel_is_not_mapped(self):
        self.assertNotIn("commented-out", self.channels)

    def test_dynamic_channel_is_listed_not_guessed(self):
        self.assertEqual([d["argument"] for d in self.result["dynamic"]], ["name"])
        self.assertNotIn("name", self.channels)

    def test_contextbridge_surface_is_recorded_with_location(self):
        exposed = self.result["exposed"]
        self.assertEqual([e["name"] for e in exposed], ["api"])
        self.assertEqual(exposed[0]["file"], "preload/index.js")
        self.assertEqual(exposed[0]["line"], 2)

    def test_locations_point_at_the_call_sites(self):
        get_config = self.channels["get-config"]
        self.assertEqual(get_config["main"][0]["file"], "main/index.js")
        self.assertEqual(get_config["main"][0]["line"], 2)
        self.assertEqual(get_config["renderer"][0]["kind"], "invoke")

    def test_cli_writes_a_private_map(self):
        out = Path(self._tmp.name) / "map" / "ipc.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.root), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["channel_count"],
                         self.result["channel_count"])
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)

    def test_cli_summary_leaves_out_the_lists(self):
        out = Path(self._tmp.name) / "cli-lists" / "ipc.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.root), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        summary = json.loads(done.stdout)
        for key in ("dynamic", "dynamic_exposed", "skipped", "channels"):
            self.assertNotIn(key, summary)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["skipped"], [])

    def test_missing_source_directory_is_an_input_error(self):
        with self.assertRaises(em.InputError):
            em.scan(str(Path(self._tmp.name) / "nope"))

    # Dynamic names: a first argument that is not one string literal followed by "," or ")".

    def test_concatenated_name_is_dynamic_and_never_a_channel(self):
        result = self.scan_files({"main.js": "ipcMain.handle('app:' + name, () => 1);\n"})
        self.assertEqual(result["dynamic"], [{"kind": "handle", "argument": "'app:' + name",
                                              "file": "main.js", "line": 1}])
        self.assertEqual(result["channels"], [])

    def test_renderer_concatenated_name_is_dynamic(self):
        result = self.scan_files({"preload.js": "ipcRenderer.invoke('get-' + key);\n"})
        self.assertEqual([(d["kind"], d["argument"]) for d in result["dynamic"]],
                         [("invoke", "'get-' + key")])
        self.assertEqual(result["channels"], [])

    def test_template_name_is_dynamic(self):
        result = self.scan_files({"main.js": "ipcMain.handle(`tpl-${x}`, () => 1);\n"})
        self.assertEqual([d["argument"] for d in result["dynamic"]], ["`tpl-${x}`"])
        self.assertEqual(result["channels"], [])

    def test_identifier_channels_are_dynamic_for_each_ipc_side(self):
        result = self.scan_files({"app.js": (
            "ipcRenderer.invoke(CHANNEL);\n"
            "win.webContents.send(STATE_CHANNEL, state);\n"
            "webContents.send(CH, 'literal-payload');\n")})
        self.assertEqual([(d["kind"], d["argument"]) for d in result["dynamic"]],
                         [("invoke", "CHANNEL"), ("send", "STATE_CHANNEL"), ("send", "CH")])
        self.assertEqual(result["channels"], [])

    def test_argument_text_keeps_a_nested_call_whole(self):
        result = self.scan_files({"preload.js": "ipcRenderer.invoke(getName(), 1);\n"})
        self.assertEqual([d["argument"] for d in result["dynamic"]], ["getName()"])

    def test_identifier_exposure_is_listed_as_dynamic_exposed(self):
        result = self.scan_files({"preload.js": "contextBridge.exposeInMainWorld(API_NAME, { ok: true });\n"})
        self.assertEqual(result["exposed"], [])
        self.assertEqual(result["dynamic_exposed"], [{"argument": "API_NAME", "file": "preload.js", "line": 1}])

    def test_literal_with_spaces_before_the_comma_is_a_channel(self):
        result = self.scan_files({"main.js": "ipcMain.handle('spaced' , () => 1);\n"})
        self.assertEqual([c["name"] for c in result["channels"]], ["spaced"])
        self.assertEqual(result["dynamic"], [])

    def test_call_whose_first_argument_is_on_a_later_line_is_listed_empty(self):
        result = self.scan_files({"main.js": "ipcMain.handle(\n  'multi-line', () => 1);\n"})
        self.assertEqual([(d["kind"], d["argument"], d["line"]) for d in result["dynamic"]],
                         [("handle", "", 1)])
        self.assertEqual(result["channels"], [])

    def test_exposure_name_on_a_later_line_is_listed_empty(self):
        result = self.scan_files({"preload.js": "contextBridge.exposeInMainWorld(\n  'api', {});\n"})
        self.assertEqual(result["dynamic_exposed"], [{"argument": "", "file": "preload.js", "line": 1}])
        self.assertEqual(result["exposed"], [])

    def test_request_with_a_receiver_of_another_kind_is_unhandled(self):
        result = self.scan_files({"main.js": "ipcMain.on('kind-mismatch', () => 1);\n",
                                  "preload.js": "ipcRenderer.invoke('kind-mismatch');\n"})
        self.assertEqual(self.channel_map(result)["kind-mismatch"]["status"], "unhandled")

    # Comments: whole-line comments are skipped; code after a closing */ is scanned.

    def test_code_after_a_closing_comment_marker_is_scanned(self):
        result = self.scan_files({
            "main.js": (
                "/*\n"
                " * block note\n"
                " */ ipcMain.handle('after-comment', () => 1);\n"
                "/*\n"
                " ipcMain.handle('inside-block', () => 2);\n"
                "*/\n"),
            "preload.js": "ipcRenderer.invoke('after-comment');\n"})
        channels = self.channel_map(result)
        self.assertEqual(channels["after-comment"]["status"], "paired")
        self.assertEqual(channels["after-comment"]["main"][0]["line"], 3)
        self.assertNotIn("inside-block", channels)

    def test_block_comment_lines_and_a_bare_closing_marker_add_nothing(self):
        result = self.scan_files({"main.js": "/*\n ipcMain.handle('inside', () => 1);\n */\n"})
        self.assertEqual(result["channels"], [])
        self.assertEqual(result["dynamic"], [])

    # Skipped files and symlinks are recorded, not scanned.

    def test_file_over_the_limit_is_skipped_and_recorded(self):
        big = "ipcMain.handle('big-channel', () => 1);\n"
        small = "ipcMain.handle('ok', () => 1);\n"
        limit = len(big.encode("utf-8")) - 1
        self.assertLessEqual(len(small.encode("utf-8")), limit)
        with mock.patch.object(em, "MAX_FILE_BYTES", limit):
            result = self.scan_files({"big.js": big, "small.js": small})
        self.assertEqual(result["skipped"], [{"path": "big.js", "reason": "too large"}])
        self.assertEqual(result["files_scanned"], 1)
        self.assertEqual(sorted(self.channel_map(result)), ["ok"])
        self.assertNotIn("big-channel", self.channel_map(result))

    def test_file_of_exactly_the_limit_is_scanned(self):
        text = "ipcMain.handle('edge', () => 1);\n"
        with mock.patch.object(em, "MAX_FILE_BYTES", len(text.encode("utf-8"))):
            result = self.scan_files({"edge.js": text})
        self.assertEqual(result["skipped"], [])
        self.assertEqual(sorted(self.channel_map(result)), ["edge"])

    def test_default_limit_is_16_mib(self):
        self.assertEqual(em.MAX_FILE_BYTES, 16 * 1024 * 1024)

    def test_symlinked_file_is_skipped_and_recorded(self):
        outside = self.make_root()
        target = outside / "real.js"
        target.write_text("ipcMain.handle('linked-channel', () => 1);\n", encoding="utf-8")
        root = self.make_root()
        (root / "main").mkdir()
        try:
            os.symlink(target, root / "main" / "link.js")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        result = em.scan(str(root))
        self.assertEqual(result["skipped"], [{"path": "main/link.js", "reason": "symlink"}])
        self.assertEqual(result["channels"], [])

    def test_symlink_without_a_scanned_extension_is_not_listed(self):
        outside = self.make_root()
        (outside / "real.js").write_text("ipcMain.handle('ignored-link', () => 1);\n", encoding="utf-8")
        root = self.make_root()
        try:
            os.symlink(outside / "real.js", root / "notes.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        result = em.scan(str(root))
        self.assertEqual(result["skipped"], [])
        self.assertEqual(result["files_scanned"], 0)

    def test_symlinked_directory_is_recorded_and_not_followed(self):
        outside = self.make_root()
        (outside / "inner.js").write_text("ipcMain.handle('inner-channel', () => 1);\n", encoding="utf-8")
        root = self.make_root()
        try:
            os.symlink(outside, root / "linked-dir")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        result = em.scan(str(root))
        self.assertEqual(result["skipped"], [{"path": "linked-dir", "reason": "symlink"}])
        self.assertEqual(result["files_scanned"], 0)
        self.assertEqual(result["channels"], [])

    def test_symlinked_source_root_is_followed(self):
        real = self.make_root()
        (real / "main.js").write_text("ipcMain.handle('root-channel', () => 1);\n", encoding="utf-8")
        link = self.make_root() / "app-link"
        try:
            os.symlink(real, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        result = em.scan(str(link))
        self.assertEqual(sorted(self.channel_map(result)), ["root-channel"])


if __name__ == "__main__":
    unittest.main()
