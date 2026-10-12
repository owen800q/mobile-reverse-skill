#!/usr/bin/env python3
"""Every call of the trace-logging tools leaves a log line, even when it fails on odd input."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import adb_pull_package as ap  # noqa: E402
import cdp_script_inventory as ci  # noqa: E402
import device_state_diff as dsd  # noqa: E402

BAD_BYTES_ADB = r'''#!/usr/bin/env python3
import sys
if sys.argv[1:4] == ["shell", "pm", "path"]:
    sys.stdout.buffer.write(b"package:/data/app/aa/base.apk\xff\n")
    sys.exit(0)
sys.exit(2)
'''


def read_log(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    raw.decode("ascii")  # every byte must be ASCII
    return [json.loads(line) for line in raw.decode("ascii").splitlines() if line]


class TraceRobustnessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_device_diff_non_utf8_scope_still_writes_a_run_line(self):
        before = self.dir / "before.tsv"
        after = self.dir / "after.tsv"
        before.write_text("a.txt\t1\tabc\n", encoding="utf-8")
        after.write_text("a.txt\t1\tabc\n", encoding="utf-8")
        out = self.dir / "session" / "diff.json"
        log = self.dir / "session" / "device_state_diff.trace.jsonl"
        with self.assertRaises(ValueError):
            dsd.run(str(before), str(after), str(out), "bad \udcff scope", log_path=str(log))
        entries = read_log(log)
        self.assertEqual(entries[-1]["function"], "run")
        self.assertEqual(entries[-1]["status"], "input_error")
        self.assertIn("scope_sha256", entries[-1])

    def test_cdp_log_line_is_ascii_for_undecodable_text(self):
        log = self.dir / "trace.jsonl"
        ci.log_entry(str(log), "run", status="error", error="bad \udcff name")
        entries = read_log(log)
        self.assertEqual(entries[0]["status"], "error")
        self.assertEqual(entries[0]["error"], "bad \udcff name")  # escaped on disk, restored on read

    def test_adb_non_utf8_pm_output_exits_2_and_logs_the_call(self):
        fake = self.dir / "adb"
        fake.write_text(BAD_BYTES_ADB, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        out = self.dir / "pulled"
        done = subprocess.run([sys.executable, str(SCRIPTS / "adb_pull_package.py"), "com.example.aa",
                               "--out", str(out), "--scope", "own test device", "--adb", str(fake)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2, done.stderr)
        log = self.dir / "adb_pull_package.trace.jsonl"
        functions = [e["function"] for e in read_log(log)]
        self.assertIn("pull_package", functions)
        self.assertEqual(read_log(log)[-1]["status"], "input_error")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
