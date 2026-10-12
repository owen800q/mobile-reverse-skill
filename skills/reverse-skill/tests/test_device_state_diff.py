#!/usr/bin/env python3
"""Tests for scripts/device_state_diff.py: added, removed, changed, scope and path safety."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "device_state_diff.py"
sys.path.insert(0, str(SCRIPT.parent))

import device_state_diff as dsd  # noqa: E402

BEFORE = "shared_prefs/app.xml\t120\taaa\nfiles/cache.db\t500\tbbb\nfiles/old.log\t10\tccc\nfiles/same.bin\t7\tddd\n"
AFTER = "shared_prefs/app.xml\t120\taaa\nfiles/cache.db\t640\tbbb2\nfiles/new.token\t32\teee\nfiles/same.bin\t7\tddd\n"


class DiffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.before = self.dir / "before.tsv"
        self.after = self.dir / "after.tsv"
        self.before.write_text(BEFORE, encoding="utf-8")
        self.after.write_text(AFTER, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_added_removed_changed_and_unchanged_are_classified(self):
        result = dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")
        self.assertEqual(result["diff"]["added"], ["files/new.token"])
        self.assertEqual(result["diff"]["removed"], ["files/old.log"])
        self.assertEqual([c["path"] for c in result["diff"]["changed"]], ["files/cache.db"])
        self.assertEqual(result["diff"]["unchanged"], 2)

    def test_output_holds_paths_and_hashes_but_no_contents(self):
        out = self.dir / "d.json"
        dsd.run(str(self.before), str(self.after), str(out), "own device")
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(set(result), {"scope", "before", "after", "summary", "diff", "limitations"})
        self.assertEqual(set(result["diff"]["changed"][0]), {"path", "size_before", "size_after", "hash_compared"})
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)

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

    def test_absolute_and_parent_paths_are_refused(self):
        self.after.write_text("/etc/passwd\t1\taaa\n", encoding="utf-8")
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")
        self.after.write_text("files/../../x\t1\taaa\n", encoding="utf-8")
        with self.assertRaises(dsd.InputError):
            dsd.run(str(self.before), str(self.after), str(self.dir / "d.json"), "own device")

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


if __name__ == "__main__":
    unittest.main()
