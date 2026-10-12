#!/usr/bin/env python3
"""Tests for scripts/cdp_script_inventory.py using a recorded event log."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

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

    def test_json_array_wrappers_are_unwrapped_like_json_lines(self):
        array = self.dir / "wrapped.json"
        wrapped = [{"message": json.dumps(EVENTS[2])}, {"message": json.dumps(EVENTS[4])},
                   {"message": "not json"}, EVENTS[7]]
        array.write_text(json.dumps(wrapped), encoding="utf-8")
        result = ci.run(str(array), str(self.dir / "wa.json"))
        self.assertEqual(result["scripts_parsed"], 2)
        self.assertEqual(result["by_source"], {"https": 1, "file": 1})

    def test_array_and_lines_layouts_give_the_same_inventory(self):
        lines = self.dir / "same.jsonl"
        lines.write_text("\n".join(json.dumps({"message": json.dumps(m)}) for m in EVENTS) + "\n",
                         encoding="utf-8")
        array = self.dir / "same.json"
        array.write_text(json.dumps([{"message": json.dumps(m)} for m in EVENTS]), encoding="utf-8")
        from_lines = ci.run(str(lines), str(self.dir / "l.json"))
        from_array = ci.run(str(array), str(self.dir / "a2.json"))
        self.assertEqual(from_lines["inventory"], from_array["inventory"])
        self.assertEqual(from_lines["scripts_parsed"], from_array["scripts_parsed"])

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

    def test_run_appends_a_private_entry_without_script_urls(self):
        out = self.dir / "traced" / "inv.json"
        ci.run(str(self.log), str(out))
        log = out.parent / "trace.jsonl"
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        text = log.read_text(encoding="utf-8")
        entry = json.loads(text.splitlines()[-1])
        self.assertEqual(entry["tool"], "cdp_script_inventory")
        self.assertEqual(entry["function"], "run")
        self.assertEqual((entry["status"], entry["exit_code"]), ("ok", 0))
        self.assertEqual(entry["events"], "events.jsonl")
        self.assertEqual(entry["out"], "inv.json")
        self.assertEqual(entry["events_sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())
        self.assertEqual((entry["format"], entry["unwrapped"], entry["unwrap_failed"]), ("lines", 0, 0))
        self.assertEqual((entry["scripts_parsed"], entry["distinct_scripts"]), (5, 4))
        self.assertEqual(datetime.fromisoformat(entry["ts"]).utcoffset(), timedelta(0))
        self.assertNotIn("cdn.example.test", text)
        self.assertNotIn("file:///opt", text)

    def test_wrapper_counts_are_logged(self):
        wrapped = self.dir / "wcase" / "wrapped.json"
        wrapped.parent.mkdir()
        items = [{"message": json.dumps(EVENTS[2])}, {"message": "not json"}]
        wrapped.write_text(json.dumps(items), encoding="utf-8")
        ci.run(str(wrapped), str(wrapped.parent / "w.json"))
        entry = json.loads((wrapped.parent / "trace.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((entry["format"], entry["unwrapped"], entry["unwrap_failed"]), ("array", 2, 1))

    def test_malformed_input_is_logged_as_an_error(self):
        case = self.dir / "bad-case"
        case.mkdir()
        bad = case / "bad.jsonl"
        bad.write_text("{not json\n", encoding="utf-8")
        with self.assertRaises(ci.InputError):
            ci.run(str(bad), str(case / "b.json"))
        entry = json.loads((case / "trace.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((entry["status"], entry["exit_code"]), ("error", 2))
        self.assertIn("line 1 is not valid JSON", entry["error"])
        self.assertEqual(entry["events_sha256"], hashlib.sha256(bad.read_bytes()).hexdigest())
        self.assertFalse((case / "b.json").exists())

    def test_refused_oversize_log_is_logged_with_a_null_hash(self):
        case = self.dir / "big-case"
        case.mkdir()
        with mock.patch.object(ci, "MAX_EVENTS_BYTES", 10):
            with self.assertRaises(ci.InputError):
                ci.run(str(self.log), str(case / "inv.json"))
        entry = json.loads((case / "trace.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((entry["status"], entry["exit_code"]), ("error", 2))
        self.assertIsNone(entry["events_sha256"])
        self.assertIn("exceeds 256 MiB", entry["error"])
        self.assertFalse((case / "inv.json").exists())

    def test_output_cannot_be_the_trace_log(self):
        trace = self.dir / "trace.jsonl"
        with self.assertRaises(ci.InputError):
            ci.run(str(self.log), str(trace))
        for line in trace.read_text(encoding="utf-8").splitlines():
            json.loads(line)
        last = json.loads(trace.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(last["status"], "error")
        self.assertEqual(last["events_sha256"], hashlib.sha256(self.log.read_bytes()).hexdigest())

    def test_cli_logs_the_run_and_the_exit_code(self):
        out = self.dir / "cli-log" / "inv.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.log), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        log = out.parent / "trace.jsonl"
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["function"] for e in entries], ["run", "main"])
        self.assertEqual([e["exit_code"] for e in entries], [0, 0])
        digest = hashlib.sha256(self.log.read_bytes()).hexdigest()
        self.assertEqual([e["events_sha256"] for e in entries], [digest, digest])
        missing = self.dir / "cli-log" / "missing.jsonl"
        done = subprocess.run([sys.executable, str(SCRIPT), str(missing), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((last["function"], last["status"], last["exit_code"]), ("main", "error", 2))
        self.assertEqual(last["events"], "missing.jsonl")


if __name__ == "__main__":
    unittest.main()
