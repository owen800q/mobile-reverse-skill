#!/usr/bin/env python3
"""Tests for scripts/electron_ipc_map.py: pairing, dynamic channels, comments, exposure, skips."""
import json
import os
import subprocess
import sys
import tempfile
import time
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
                                              "file": "main.js", "line": 1,
                                              "reason": "not a constant reference"}])
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

    # Constants meet the whole-argument rule: a name is resolved only when it is the complete argument.

    def test_constant_with_a_suffix_is_not_resolved(self):
        result = self.scan_files({"main.js": (
            "const IPC = { GET: 'prefix' };\n"
            "ipcMain.handle(IPC.GET + '-suffix', () => 1);\n")})
        self.assertEqual([(d["argument"], d["reason"]) for d in result["dynamic"]],
                         [("IPC.GET + '-suffix'", "not a constant reference")])
        self.assertEqual(result["channels"], [])

    def test_constant_split_from_its_comma_by_a_line_break_is_not_resolved(self):
        result = self.scan_files({"main.js": (
            "const CH = 'split';\n"
            "ipcMain.handle(CH\n"
            "  , () => 1);\n")})
        self.assertEqual([(d["argument"], d["reason"], d["line"]) for d in result["dynamic"]],
                         [("CH", em.REASON_INCOMPLETE, 2)])
        self.assertEqual(result["channels"], [])

    def test_constant_defined_inside_a_block_comment_is_not_collected(self):
        result = self.scan_files({"main.js": (
            "/*\n"
            "const GHOST = 'ghost';\n"
            "*/\n"
            "ipcMain.handle(GHOST, () => 1);\n")})
        self.assertEqual([(d["argument"], d["reason"]) for d in result["dynamic"]],
                         [("GHOST", "no string constant found")])
        self.assertEqual(result["channels"], [])

    def test_literal_with_a_dollar_sign_is_listed_not_dropped(self):
        result = self.scan_files({"main.js": "ipcMain.handle('price$list', () => 1);\n"})
        self.assertEqual([d["argument"] for d in result["dynamic"]], ["'price$list'"])
        self.assertEqual(result["channels"], [])

    def test_every_dynamic_entry_has_a_reason(self):
        result = self.scan_files({"app.js": (
            "ipcMain.handle(a + b, () => 1);\n"
            "ipcRenderer.invoke(\n"
            "  'later');\n"
            "win.webContents.send(`t-${n}`);\n"
            "event.reply(unknown);\n")})
        self.assertEqual(len(result["dynamic"]), 4)
        for entry in result["dynamic"]:
            self.assertTrue(entry["reason"], entry)

    def test_long_argument_is_cut_for_display_but_the_entry_is_kept(self):
        result = self.scan_files({"main.js": "ipcMain.handle('x' + '%s', () => 1);\n" % ("y" * 300)})
        argument = result["dynamic"][0]["argument"]
        self.assertEqual(len(argument), em.ARG_MAX + 3)
        self.assertTrue(argument.endswith("..."))

    def test_once_receivers_keep_their_own_kind(self):
        result = self.scan_files({"main.js": "ipcMain.once('one-shot', () => 1);\n",
                                  "preload.js": ("ipcRenderer.once('from-main', () => 1);\n"
                                                 "ipcRenderer.send('one-shot');\n")})
        channels = self.channel_map(result)
        self.assertEqual(channels["one-shot"]["main"][0]["kind"], "once")
        self.assertEqual(channels["from-main"]["renderer"][0]["kind"], "once")
        self.assertEqual(channels["one-shot"]["status"], "paired")

    # Sends that take a target first: the channel is the second argument.

    def test_send_to_takes_the_channel_after_its_target(self):
        result = self.scan_files({"main.js": "win.webContents.sendTo(7, 'sendto:msg', data);\n"})
        channels = self.channel_map(result)
        self.assertEqual(list(channels), ["sendto:msg"])
        self.assertEqual(channels["sendto:msg"]["main"][0]["kind"], "sendTo")
        self.assertEqual(result["dynamic"], [])

    def test_send_to_frame_target_may_be_an_array_or_a_call(self):
        result = self.scan_files({"main.js": (
            "wc.webContents.sendToFrame([pid, fid], 'arr:msg', 1);\n"
            "wc.webContents.sendToFrame(getFrame(1, 2), 'call:msg', 1);\n")})
        self.assertEqual(sorted(self.channel_map(result)), ["arr:msg", "call:msg"])
        self.assertEqual(result["dynamic"], [])

    def test_send_to_frame_channel_can_come_from_a_constant(self):
        result = self.scan_files({"main.js": (
            "const CH = 'frame:const';\n"
            "wc.webContents.sendToFrame(frame, CH, 1);\n")})
        site = self.channel_map(result)["frame:const"]["main"][0]
        self.assertEqual(site["kind"], "sendToFrame")
        self.assertEqual(site["resolved_from"]["expression"], "CH")

    def test_send_to_with_the_channel_on_a_later_line_is_listed_empty(self):
        result = self.scan_files({"main.js": (
            "wc.webContents.sendTo(id,\n"
            "  'later');\n"
            "wc.webContents.sendTo(id\n"
            "  , 'later2');\n")})
        self.assertEqual([(d["kind"], d["argument"], d["reason"], d["line"]) for d in result["dynamic"]],
                         [("sendTo", "", em.REASON_NOT_ON_LINE, 1),
                          ("sendTo", "", em.REASON_NOT_ON_LINE, 3)])
        self.assertEqual(result["channels"], [])

    def test_send_to_frame_is_paired_only_with_a_renderer_listener(self):
        result = self.scan_files({
            "main.js": ("wc.webContents.sendToFrame(f, 'tf:heard', 1);\n"
                        "wc.webContents.sendToFrame(f, 'tf:lost', 1);\n"),
            "preload.js": "ipcRenderer.on('tf:heard', () => 1);\n"})
        channels = self.channel_map(result)
        self.assertEqual(channels["tf:heard"]["status"], "paired")
        self.assertEqual(channels["tf:lost"]["status"], "unhandled")

    # Event replies follow the same whole-argument rule.

    def test_event_reply_name_must_be_the_whole_argument(self):
        result = self.scan_files({"main.js": (
            "ipcMain.on('ask', (event, id) => {\n"
            "  event.reply('reply:' + id, 1);\n"
            "  event.sender.send(unknown, 2);\n"
            "  event.reply('plain-reply', 3);\n"
            "});\n")})
        channels = self.channel_map(result)
        self.assertEqual(sorted(channels), ["ask", "plain-reply"])
        self.assertEqual(channels["plain-reply"]["main"][0]["kind"], "send")
        self.assertEqual([(d["kind"], d["argument"]) for d in result["dynamic"]],
                         [("send", "'reply:' + id"), ("send", "unknown")])


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
        result = em.scan(str(self.root))
        # The scan ends, keeps what the other files hold, and does not claim to be cut short.
        self.assertIn("user:get", {c["name"] for c in result["channels"]})
        self.assertEqual(result["constants_incomplete"], [])


class HardeningTests(unittest.TestCase):
    """Constant definitions, hostile input and call forms found by the review of the merge."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def scan_files(self, files):
        root = Path(tempfile.mkdtemp(dir=self._tmp.name))
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return em.scan(str(root))

    @staticmethod
    def channel_map(result):
        return {c["name"]: c for c in result["channels"]}

    @staticmethod
    def reasons(result):
        return {d["argument"]: d["reason"] for d in result["dynamic"]}

    # A constant counts only when its initializer is just the string.

    def test_initializer_that_continues_past_its_string_is_not_a_constant(self):
        initializers = [
            "'app:' +\n  suffix",
            "'app:' + suffix",
            "'a' + 'b'",
            "'x'.toUpperCase()",
            "'p' ? q : r",
            "'a'\n  .trim()",
            "'a'\n  + b",
        ]
        for init in initializers:
            with self.subTest(init=init):
                result = self.scan_files({"a.js": "const P = %s;\nipcMain.handle(P, f);\n" % init})
                self.assertEqual(result["channels"], [])
                self.assertEqual(self.reasons(result), {"P": "no string constant found"})

    def test_object_member_that_continues_is_not_collected(self):
        result = self.scan_files({"a.js": (
            "const IPC = { GET: 'user:' + id, OK: 'user:ok' };\n"
            "ipcMain.handle(IPC.GET, f);\n"
            "ipcMain.handle(IPC.OK, f);\n")})
        self.assertEqual(sorted(self.channel_map(result)), ["user:ok"])
        self.assertEqual(self.reasons(result), {"IPC.GET": "no string constant found"})

    def test_plain_string_constants_still_resolve(self):
        result = self.scan_files({"a.js": (
            "const A = 'a1';\n"
            "const B = \"b1\"\n"
            "const C = 'c1' // note\n"
            "export const D = 'd1' as const;\n"
            "const O = { 'GET': 'g1', \"PUT\": 'p1' } as const;\n"
            "ipcMain.on(A, f); ipcMain.on(B, f); ipcMain.on(C, f); ipcMain.on(D, f);\n"
            "ipcMain.on(O.GET, f); ipcMain.on(O.PUT, f);\n")})
        self.assertEqual(sorted(self.channel_map(result)), ["a1", "b1", "c1", "d1", "g1", "p1"])
        self.assertEqual(result["dynamic"], [])

    def test_freeze_nesting_is_bounded(self):
        deep = "const X = " + "Object.freeze(" * 1000 + "'a'" + ")" * 1000 + ";\n"
        result = self.scan_files({"a.js": deep + "ipcMain.on(X, f);\n"})
        self.assertEqual(result["channels"], [])
        self.assertEqual(self.reasons(result), {"X": "no string constant found"})
        shallow = self.scan_files({"a.js": "const Y = Object.freeze(Object.freeze('y1'));\nipcMain.on(Y, f);\n"})
        self.assertEqual(list(self.channel_map(shallow)), ["y1"])

    def test_constant_value_must_be_usable_as_a_channel_name(self):
        result = self.scan_files({"a.js": (
            "const EMPTY = '';\n"
            "const DOLLAR = 'a$b';\n"
            "const QUOTE = \"it's\";\n"
            "const LONG = '%s';\n"
            "const FINE = 'fine';\n"
            "ipcMain.on(EMPTY, f); ipcMain.on(DOLLAR, f); ipcMain.on(QUOTE, f);\n"
            "ipcMain.on(LONG, f); ipcMain.on(FINE, f);\n" % ("x" * 201))})
        self.assertEqual(sorted(self.channel_map(result)), ["fine"])
        self.assertEqual({d["reason"] for d in result["dynamic"]}, {em.REASON_BAD_NAME})
        self.assertEqual(len(result["dynamic"]), 4)

    def test_template_followed_by_an_operator_is_not_called_interpolation(self):
        result = self.scan_files({"a.js": "ipcMain.on(`a` + x, f);\nipcMain.on(`t-${x}`, f);\n"})
        self.assertEqual(self.reasons(result), {"`a` + x": "not a constant reference",
                                                "`t-${x}`": "template literal with interpolation"})

    # The scan stays bounded on hostile input.

    def test_constant_scan_budget_stops_the_scan_and_says_so(self):
        source = ("const EARLY = 'early';\n"
                  "const a = {\nconst b = {\nconst c = {\n"
                  "const LATE = 'late';\n"
                  "ipcMain.on(EARLY, f);\nipcMain.on(LATE, f);\n")
        within = self.scan_files({"a.js": source})
        self.assertEqual(within["constants_incomplete"], [])
        self.assertEqual(sorted(self.channel_map(within)), ["early", "late"])
        with mock.patch.object(em, "MAX_FAILED_SCAN", 10):
            cut = self.scan_files({"a.js": source})
        self.assertEqual(cut["constants_incomplete"],
                         [{"path": "a.js", "reason": "constant scan budget used up"}])
        self.assertEqual(sorted(self.channel_map(cut)), ["early"])
        self.assertEqual(self.reasons(cut), {"LATE": "no string constant found"})

    def test_long_argument_is_listed_with_its_own_reason(self):
        result = self.scan_files({"a.js": (
            "ipcMain.handle(%s, f);\n"
            "wc.webContents.sendTo(%s, 'ch');\n" % ("a" * 1500, "t" * 1500))})
        self.assertEqual([(d["kind"], d["reason"]) for d in result["dynamic"]],
                         [("handle", em.REASON_TOO_LONG), ("sendTo", em.REASON_TOO_LONG)])
        self.assertEqual(result["channels"], [])
        self.assertEqual(len(result["dynamic"][0]["argument"]), em.ARG_MAX + 3)

    def test_many_calls_on_one_line_stay_fast(self):
        started = time.monotonic()
        result = self.scan_files({"a.js": "ipcMain.on(a " * 6000 + "\n"})
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(len(result["dynamic"]), 6000)

    def test_a_named_pipe_is_skipped_and_never_read(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("named pipes are not available here")
        root = Path(tempfile.mkdtemp(dir=self._tmp.name))
        os.mkfifo(str(root / "pipe.js"))
        (root / "real.js").write_text("ipcMain.handle('real', () => 1);\n", encoding="utf-8")
        out = root.parent / "fifo-map.json"
        try:
            done = subprocess.run([sys.executable, str(SCRIPT), str(root), "--out", str(out)],
                                  capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            self.fail("the scan blocked on a named pipe")
        self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(result["skipped"], [{"path": "pipe.js", "reason": "not a regular file"}])
        self.assertEqual([c["name"] for c in result["channels"]], ["real"])

    def test_cli_summary_leaves_out_constants_incomplete(self):
        root = Path(tempfile.mkdtemp(dir=self._tmp.name))
        (root / "a.js").write_text("ipcMain.handle('x', f);\n", encoding="utf-8")
        out = root.parent / "summary-map.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(root), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("constants_incomplete", json.loads(done.stdout))
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["constants_incomplete"], [])

    # Call forms and settings that had no test.

    def test_every_receiver_and_request_form_is_recognised(self):
        result = self.scan_files({
            "main.js": ("ipcMain.handleOnce('h1', f);\n"
                        "ipcMain.on('s1', f);\n"
                        "ipcMain.once('s2', f);\n"
                        "win.webContents.send('push', 1);\n"),
            "preload.js": ("ipcRenderer.invoke('h1');\n"
                           "ipcRenderer.sendSync('s1');\n"
                           "ipcRenderer.send('s2');\n"
                           "ipcRenderer.once('push', f);\n"
                           "ipcRenderer.sendToHost('host-only');\n")})
        channels = self.channel_map(result)
        for name in ("h1", "s1", "s2", "push"):
            self.assertEqual(channels[name]["status"], "paired", name)
        self.assertEqual(channels["host-only"]["status"], "unused")
        self.assertEqual(channels["host-only"]["renderer"][0]["kind"], "sendToHost")

    def test_event_reply_variable_names(self):
        names = ["event", "_event", "evt", "ev", "e"]
        text = "".join("%s.reply('reply-%s', 1);\n" % (n, n) for n in names)
        text += "ctx.reply('not-a-reply', 1);\n"
        result = self.scan_files({"main.js": text})
        self.assertEqual(sorted(self.channel_map(result)), sorted("reply-" + n for n in names))
        self.assertEqual(result["dynamic"], [])

    def test_call_with_a_space_before_the_parenthesis_is_not_matched_or_listed(self):
        result = self.scan_files({"main.js": "ipcMain.handle ('spaced', f);\nipcMain.on (name, f);\n"})
        self.assertEqual(result["channels"], [])
        self.assertEqual(result["dynamic"], [])

    def test_empty_and_overlong_literals_are_dynamic(self):
        too_long = "n" * 201
        result = self.scan_files({"main.js": (
            "ipcMain.on('', f);\nipcMain.on(\"\", f);\n"
            "ipcMain.on('%s', f);\nipcMain.on('%s', f);\n" % (too_long, "m" * 200))})
        self.assertEqual(sorted(self.channel_map(result)), ["m" * 200])
        self.assertEqual([d["argument"] for d in result["dynamic"]],
                         ["''", '""', em._shorten("'" + too_long + "'")])


if __name__ == "__main__":
    unittest.main()
