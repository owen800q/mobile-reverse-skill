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


SHARED_JS = """const IPC = Object.freeze({
  GET_USER: 'user:get',
  NEST: { PING: 'nest:ping' },
});
const LOCAL = 'shared-local';
const CLASH = 'clash:a';
module.exports = { IPC };
"""
MAIN2_JS = """const { IPC } = require('./shared');
const CLASH = 'clash:b';
const TPL = `tpl:plain`;
ipcMain.handle(IPC.GET_USER, () => 1);
ipcMain.on(IPC['NEST'].PING, () => 1);
ipcMain.on(IPC.NEST.PING, () => 1);
ipcMain.handle(CLASH, () => 2);
ipcMain.handle(LOCAL, () => 3);
ipcMain.handle(`tpl:plain`, () => 4);
ipcMain.handle(`tpl:${id}`, () => 5);
win.webContents.send('app:update', 'payload-not-a-channel');
win.webContents.sendToFrame(frame, 'frame:msg', data);
ipcMain.on('ask', (event, arg) => { event.reply('answer', 1); event.sender.send('answer2', 2); });
win.webContents.send(IPC.UNKNOWN, 1);
"""
PRELOAD2_JS = """const { IPC } = require('./shared');
const CLASH = 'clash:c';
const api = {
  user: () => ipcRenderer.invoke(IPC.GET_USER),
  ping: () => ipcRenderer.send(IPC.NEST.PING),
  clash: () => ipcRenderer.invoke(CLASH),
  local: () => ipcRenderer.invoke(LOCAL),
  param: (channel) => ipcRenderer.invoke(channel),
};
ipcRenderer.on('app:update', () => 1);
ipcRenderer.on('answer', () => 1);
ipcRenderer.send('ask');
"""


class ConstantResolutionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "app"
        self.root.mkdir()
        (self.root / "shared.js").write_text(SHARED_JS, encoding="utf-8")
        (self.root / "main.js").write_text(MAIN2_JS, encoding="utf-8")
        (self.root / "preload.js").write_text(PRELOAD2_JS, encoding="utf-8")
        self.result = em.scan(str(self.root))
        self.channels = {c["name"]: c for c in self.result["channels"]}
        self.dynamic = {(d["file"], d["argument"]): d["reason"] for d in self.result["dynamic"]}

    def tearDown(self):
        self._tmp.cleanup()

    def test_shared_object_constant_pairs_main_and_renderer(self):
        self.assertEqual(self.channels["user:get"]["status"], "paired")
        site = self.channels["user:get"]["renderer"][0]
        self.assertEqual(site["resolved_from"]["expression"], "IPC.GET_USER")
        self.assertIn("shared.js:1", site["resolved_from"]["how"])

    def test_nested_and_bracket_forms_resolve_to_the_same_channel(self):
        self.assertEqual(self.channels["nest:ping"]["status"], "paired")
        self.assertEqual(len(self.channels["nest:ping"]["main"]), 2)

    def test_template_literal_without_interpolation_is_a_literal(self):
        self.assertEqual(self.channels["tpl:plain"]["status"], "unused")
        self.assertEqual(self.dynamic[("main.js", "`tpl:${id}`")], "template literal with interpolation")

    def test_bare_name_resolves_only_in_its_own_file(self):
        # LOCAL is defined in shared.js, so the uses in main.js and preload.js stay dynamic.
        self.assertEqual(self.dynamic[("main.js", "LOCAL")], "no string constant found")
        self.assertEqual(self.dynamic[("preload.js", "LOCAL")], "no string constant found")
        self.assertNotIn("shared-local", self.channels)

    def test_same_bare_name_in_different_files_resolves_per_file(self):
        # Each file defines CLASH once, so each use resolves to its own file's value.
        self.assertIn("clash:b", self.channels)
        self.assertIn("clash:c", self.channels)
        self.assertNotIn("clash:a", self.channels)

    def test_ambiguous_dotted_path_is_reported_not_guessed(self):
        extra = self.root / "other.js"
        extra.write_text("const IPC = { GET_USER: 'user:other' };\n", encoding="utf-8")
        result = em.scan(str(self.root))
        reasons = {d["reason"] for d in result["dynamic"] if d["argument"] == "IPC.GET_USER"}
        self.assertEqual(reasons, {"ambiguous: 2 different definitions"})
        self.assertNotIn("user:get", {c["name"] for c in result["channels"]})

    def test_parameter_stays_dynamic_with_a_reason(self):
        self.assertEqual(self.dynamic[("preload.js", "channel")], "no string constant found")

    def test_send_records_the_first_argument_not_the_payload(self):
        self.assertIn("app:update", self.channels)
        self.assertNotIn("payload-not-a-channel", self.channels)
        self.assertEqual(self.channels["app:update"]["status"], "paired")

    def test_send_to_frame_skips_the_target_argument(self):
        self.assertEqual(self.channels["frame:msg"]["main"][0]["kind"], "sendToFrame")

    def test_event_replies_are_main_sends(self):
        self.assertEqual(self.channels["answer"]["status"], "paired")
        self.assertEqual(self.channels["answer2"]["main"][0]["kind"], "send")

    def test_unresolved_webcontents_send_is_dynamic(self):
        self.assertEqual(self.dynamic[("main.js", "IPC.UNKNOWN")], "no string constant found")

    def test_resolved_uses_are_counted(self):
        self.assertEqual(self.result["resolved_uses"], sum(
            1 for c in self.result["channels"] for side in ("main", "renderer")
            for u in c[side] if "resolved_from" in u))
        self.assertGreaterEqual(self.result["resolved_uses"], 6)

    def test_pathological_object_literals_terminate(self):
        (self.root / "bad.js").write_text(
            "const A = { x: ), y: ] , 'k': 'v' };\nconst B = Object.freeze({ z: 1 ;\nconst C = {", encoding="utf-8")
        em.scan(str(self.root))


if __name__ == "__main__":
    unittest.main()
