#!/usr/bin/env python3
"""Tests for scripts/cdp_script_inventory.py using a recorded event log."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "cdp_script_inventory.py"
sys.path.insert(0, str(SCRIPT.parent))

import cdp_script_inventory as ci  # noqa: E402


def msg(method, **params):
    return {"method": method, "params": params}


EVENTS = [
    msg("Runtime.executionContextCreated", context={"id": 1, "name": "main", "origin": "app://x"}),
    msg("Runtime.executionContextCreated", context={"id": 2, "name": "preload", "origin": "file://"}),
    msg("Debugger.scriptParsed", scriptId="10", url="https://cdn.example.test/app.js",
        executionContextId=1, length=5120, sourceMapURL="app.js.map", hash="abc123"),
    msg("Debugger.scriptParsed", scriptId="11", url="https://cdn.example.test/app.js",
        executionContextId=1, length=5120),
    msg("Debugger.scriptParsed", scriptId="12", url="file:///opt/app/preload.js",
        executionContextId=2, length=300),
    msg("Debugger.scriptParsed", scriptId="13", url="", executionContextId=1, length=40),
    msg("Debugger.scriptParsed", scriptId="14", url="node:internal/fs", executionContextId=1),
    msg("Network.requestWillBeSent", requestId="r1"),
]


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.log = self.dir / "events.jsonl"
        self.log.write_text("\n".join(json.dumps(m) for m in EVENTS) + "\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_scripts_are_grouped_by_url_with_counts_and_contexts(self):
        result = ci.run(str(self.log), str(self.dir / "inv.json"))
        by_url = {g["url"]: g for g in result["inventory"]}
        app = by_url["https://cdn.example.test/app.js"]
        self.assertEqual(app["count"], 2)
        self.assertEqual(app["script_ids"], ["10", "11"])
        self.assertEqual(app["contexts"], ["main"])
        self.assertEqual(app["hashes"], ["abc123"])
        self.assertEqual(app["source_maps"], ["app.js.map"])

    def test_sources_are_classified(self):
        result = ci.run(str(self.log), str(self.dir / "inv.json"))
        self.assertEqual(result["by_source"], {"https": 1, "file": 1, "inline": 1, "node-internal": 1})
        self.assertEqual(result["with_source_maps"], 1)

    def test_inline_scripts_get_a_stable_label(self):
        result = ci.run(str(self.log), str(self.dir / "inv.json"))
        inline = [g for g in result["inventory"] if g["source"] == "inline"]
        self.assertEqual(inline[0]["url"], "")
        self.assertTrue(inline[0]["script_ids"] == ["13"])

    def test_wrapped_messages_are_unwrapped(self):
        wrapped = self.dir / "wrapped.jsonl"
        lines = [json.dumps({"message": json.dumps(EVENTS[2])}), json.dumps({"message": "not json"})]
        wrapped.write_text("\n".join(lines), encoding="utf-8")
        result = ci.run(str(wrapped), str(self.dir / "w.json"))
        self.assertEqual(result["scripts_parsed"], 1)

    def test_json_array_input_is_accepted(self):
        array = self.dir / "events.json"
        array.write_text(json.dumps(EVENTS), encoding="utf-8")
        result = ci.run(str(array), str(self.dir / "a.json"))
        self.assertEqual(result["scripts_parsed"], 5)

    def test_malformed_line_is_an_input_error(self):
        bad = self.dir / "bad.jsonl"
        bad.write_text("{not json\n", encoding="utf-8")
        with self.assertRaises(ci.InputError):
            ci.run(str(bad), str(self.dir / "b.json"))

    def test_cli_writes_a_private_inventory(self):
        out = self.dir / "out" / "inv.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.log), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["distinct_scripts"], 4)
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
