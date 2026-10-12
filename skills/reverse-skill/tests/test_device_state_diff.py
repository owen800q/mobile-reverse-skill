#!/usr/bin/env python3
"""Tests for scripts/device_state_diff.py: classification, scope, path safety, output and trace log."""
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "device_state_diff.py"
sys.path.insert(0, str(SCRIPT.parent))

import device_state_diff as dsd  # noqa: E402

BEFORE = "shared_prefs/app.xml\t120\taaa\nfiles/cache.db\t500\tbbb\nfiles/old.log\t10\tccc\nfiles/same.bin\t7\tddd\n"
AFTER = "shared_prefs/app.xml\t120\taaa\nfiles/cache.db\t640\tbbb2\nfiles/new.token\t32\teee\nfiles/same.bin\t7\tddd\n"
SCOPE = "own device"
TS_RE = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


class DiffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.before = self.dir / "before.tsv"
        self.after = self.dir / "after.tsv"
        self.before.write_text(BEFORE, encoding="utf-8")
        self.after.write_text(AFTER, encoding="utf-8")
        self.out = self.dir / "d.json"
        self.trace = self.dir / "device_state_diff.trace.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def trace_records(self):
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines()]

    def test_added_removed_changed_and_unchanged_are_classified(self):
        result = dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")
        self.assertEqual(result["diff"]["added"], ["files/new.token"])
        self.assertEqual(result["diff"]["removed"], ["files/old.log"])
        self.assertEqual([c["path"] for c in result["diff"]["changed"]], ["files/cache.db"])
        self.assertEqual(result["diff"]["unchanged"], 2)

    def test_output_holds_sizes_and_flags_but_no_hashes_or_contents(self):
        self.before.write_text("files/cache.db\t500\t0123abcd0123abcd\n", encoding="utf-8")
        self.after.write_text("files/cache.db\t640\t9f9f9f9f9f9f9f9f\nfiles/new.token\t32\te3e3e3e3\n",
                              encoding="utf-8")
        dsd.run(str(self.before), str(self.after), str(self.out), "own device")
        text = self.out.read_text(encoding="utf-8")
        result = json.loads(text)
        self.assertEqual(set(result), {"scope", "before", "after", "summary", "diff", "limitations"})
        self.assertEqual(set(result["diff"]["changed"][0]), {"path", "size_before", "size_after", "hash_compared"})
        self.assertEqual(result["diff"]["changed"][0]["size_before"], 500)
        self.assertEqual(result["diff"]["changed"][0]["size_after"], 640)
        self.assertEqual(result["diff"]["changed"][0]["hash_compared"], True)
        self.assertEqual(result["diff"]["added"], ["files/new.token"])
        for digest in ("0123abcd0123abcd", "9f9f9f9f9f9f9f9f", "e3e3e3e3"):
            self.assertNotIn(digest, text)
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)

    def test_missing_hash_marks_the_comparison_as_size_only(self):
        self.after.write_text("files/cache.db\t500\t-\n", encoding="utf-8")
        self.before.write_text("files/cache.db\t500\tbbb\n", encoding="utf-8")
        result = dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")
        self.assertEqual(result["diff"]["changed"], [])
        self.assertEqual(result["diff"]["unchanged"], 1)

    def test_same_size_hash_change_is_detected(self):
        self.before.write_text("files/x\t5\taaa\n", encoding="utf-8")
        self.after.write_text("files/x\t5\tbbb\n", encoding="utf-8")
        result = dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")
        self.assertEqual(result["diff"]["changed"][0]["hash_compared"], True)

    def test_scope_is_required(self):
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "  ")

    def test_absolute_and_parent_components_are_refused(self):
        self.after.write_text("/etc/passwd\t1\taaa\n", encoding="utf-8")
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")
        self.after.write_text("files/../../x\t1\taaa\n", encoding="utf-8")
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")

    def test_dotdot_inside_a_name_is_accepted_and_a_dotdot_component_is_refused(self):
        self.before.write_text("", encoding="utf-8")
        self.after.write_text("a..b.txt\t1\taaa\nfiles/a/..b/c.txt\t2\tbbb\n", encoding="utf-8")
        result = dsd.run(str(self.before), str(self.after), str(self.out), SCOPE)
        self.assertEqual(result["diff"]["added"], ["a..b.txt", "files/a/..b/c.txt"])
        for rel in ("x/../y", "..", "files/../x"):
            self.after.write_text("%s\t1\taaa\n" % rel, encoding="utf-8")
            with self.assertRaises(dsd.InputError):
                dsd.run(str(self.before), str(self.after), str(self.out), SCOPE)

    def test_malformed_line_is_refused(self):
        self.after.write_text("files/x\tnot-a-size\taaa\n", encoding="utf-8")
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")

    def test_cli_summary_and_exit_codes(self):
        out = self.dir / "d.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.before), str(self.after),
                               "--out", str(out), "--scope", "own device"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["added"], 1)
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.before), str(self.after),
                               "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)

    def test_every_call_is_logged_without_listing_paths_or_scope_text(self):
        dsd.run(str(self.before), str(self.after), str(self.out), SCOPE)
        records = self.trace_records()
        self.assertEqual([r["function"] for r in records], ["read_listing", "read_listing", "run"])
        for record in records:
            self.assertRegex(record["ts"], TS_RE)
            self.assertEqual(record["tool"], "device_state_diff.py")
        self.assertEqual(records[0]["listing"], "before.tsv")
        self.assertEqual(records[0]["sha256"], hashlib.sha256(BEFORE.encode("utf-8")).hexdigest())
        self.assertEqual(records[1]["entries"], 4)
        run = records[-1]
        self.assertEqual((run["status"], run["exit_code"]), ("ok", 0))
        self.assertEqual(run["scope_length"], len(SCOPE))
        self.assertEqual(run["scope_sha256"], hashlib.sha256(SCOPE.encode("utf-8")).hexdigest())
        self.assertEqual(run["summary"], {"added": 1, "removed": 1, "changed": 1, "unchanged": 2})
        self.assertEqual(run["output"], "d.json")
        text = self.trace.read_text(encoding="utf-8")
        self.assertNotIn(SCOPE, text)
        self.assertNotIn("files/cache.db", text)
        self.assertEqual(self.trace.stat().st_mode & 0o777, 0o600)

    def test_refused_listing_is_logged_with_exit_code_2(self):
        self.after.write_text("files/x\tnot-a-size\taaa\n", encoding="utf-8")
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.out), SCOPE)
        records = self.trace_records()
        self.assertEqual([r["function"] for r in records], ["read_listing", "read_listing", "run"])
        self.assertEqual(records[1]["status"], "input_error")
        self.assertEqual((records[-1]["status"], records[-1]["exit_code"]), ("input_error", 2))

    def test_missing_listing_is_refused_and_logged(self):
        with redirect_stderr(io.StringIO()) as err:
            code = dsd.main([str(self.dir / "missing.tsv"), str(self.after), "--out", str(self.out),
                             "--scope", SCOPE])
        self.assertEqual(code, 2)
        self.assertIn("listing not found", err.getvalue())
        last = self.trace_records()[-1]
        self.assertEqual((last["function"], last["status"], last["exit_code"]), ("main", "input_error", 2))
        self.assertEqual(last["listing"], ["missing.tsv"])

    def test_trace_log_is_append_only(self):
        dsd.run(str(self.before), str(self.after), str(self.out), SCOPE)
        first = self.trace.read_text(encoding="utf-8")
        dsd.run(str(self.before), str(self.after), str(self.dir / "second.json"), SCOPE)
        self.assertTrue(self.trace.read_text(encoding="utf-8").startswith(first))
        self.assertEqual(sum(1 for r in self.trace_records() if r["function"] == "run"), 2)


if __name__ == "__main__":
    unittest.main()
