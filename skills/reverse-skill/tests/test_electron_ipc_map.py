#!/usr/bin/env python3
"""Tests for scripts/electron_ipc_map.py: pairing, dynamic channels, comments, exposure."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_missing_source_directory_is_an_input_error(self):
        with self.assertRaises(em.InputError):
            em.scan(str(Path(self._tmp.name) / "nope"))


if __name__ == "__main__":
    unittest.main()
