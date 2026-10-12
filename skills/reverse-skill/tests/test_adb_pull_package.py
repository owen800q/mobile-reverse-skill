#!/usr/bin/env python3
"""Tests for scripts/adb_pull_package.py using a fake adb that serves a fixture device tree."""
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "adb_pull_package.py"
sys.path.insert(0, str(SCRIPT.parent))

import adb_pull_package as ap  # noqa: E402

FAKE_ADB = r'''#!/usr/bin/env python3
import json, os, shutil, sys, time
root = os.environ["FAKE_ADB_ROOT"]
args = sys.argv[1:]
if args[:1] == ["-s"]:
    args = args[2:]
calls = os.environ.get("FAKE_ADB_CALLS")
if calls:
    with open(calls, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(args) + "\n")
if args[:4] == ["shell", "pm", "path", "com.example.aa"]:
    if os.environ.get("FAKE_ADB_SLOW_PM"):
        time.sleep(5)
    sys.stdout.write(open(os.path.join(root, "pm_path.txt")).read())
    sys.exit(0)
if args[:1] == ["pull"]:
    src, dst = args[1], args[2]
    name = os.path.join(root, "files", src.lstrip("/").replace("/", "__"))
    slow = os.environ.get("FAKE_ADB_SLOW_PULL")
    if slow and slow in src and os.path.isfile(name):
        with open(dst, "wb") as fh:  # a pull that is killed leaves a partial file behind
            fh.write(open(name, "rb").read()[:4])
        time.sleep(5)
    if not os.path.isfile(name):
        sys.stderr.write("remote object '%s' does not exist\n" % src)
        sys.exit(1)
    shutil.copy(name, dst)
    sys.exit(0)
sys.exit(2)
'''

BASE = b"base apk bytes"
SPLIT = b"split apk bytes"
FEATURE = b"feature bytes"
SCOPE = "user's own test device, com.example.aa, installed copy only"
TS_RE = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


class PullTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "device"
        (self.root / "files").mkdir(parents=True)
        self.adb = self.tmp / "adb"
        self.adb.write_text(FAKE_ADB, encoding="utf-8")
        self.adb.chmod(self.adb.stat().st_mode | stat.S_IEXEC)
        self.calls = self.tmp / "adb_calls.jsonl"
        self.trace = self.tmp / "adb_pull_package.trace.jsonl"
        self.put_file("/data/app/aa/base.apk", BASE)
        self.put_file("/data/app/aa/split_config.arm64.apk", SPLIT)
        self.put_file("/data/app/aa/feature_x.apk", FEATURE)
        self.set_pm_paths([
            "/data/app/aa/base.apk",
            "/data/app/aa/split_config.arm64.apk",
            "/data/app/aa/feature_x.apk",
        ])
        os.environ["FAKE_ADB_ROOT"] = str(self.root)
        os.environ["FAKE_ADB_CALLS"] = str(self.calls)
        self.out = self.tmp / "pulled"

    def tearDown(self):
        for name in ("FAKE_ADB_ROOT", "FAKE_ADB_CALLS", "FAKE_ADB_SLOW_PULL", "FAKE_ADB_SLOW_PM"):
            os.environ.pop(name, None)
        self._tmp.cleanup()

    def put_file(self, device_path, data):
        (self.root / "files" / device_path.lstrip("/").replace("/", "__")).write_bytes(data)

    def set_pm_paths(self, paths):
        (self.root / "pm_path.txt").write_text("".join("package:%s\n" % p for p in paths), encoding="utf-8")

    def short_timeout(self):
        """Set the module timeout to one second for one test."""
        saved = ap.TIMEOUT_SECONDS
        ap.TIMEOUT_SECONDS = 1
        self.addCleanup(setattr, ap, "TIMEOUT_SECONDS", saved)

    def pull(self, scope=SCOPE, out=None):
        return ap.pull_package("com.example.aa", str(out or self.out), scope, None, str(self.adb))

    def adb_calls(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()]

    def trace_records(self):
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines()]

    def test_complete_pull_digests_every_apk_and_assigns_roles(self):
        manifest = self.pull()
        self.assertEqual(manifest["coverage"], "complete")
        roles = {f["host_name"]: f["role"] for f in manifest["files"]}
        self.assertEqual(roles["01_base.apk"], "base")
        self.assertEqual(roles["02_split_config.arm64.apk"], "split")
        self.assertEqual(roles["03_feature_x.apk"], "unknown")
        digest = hashlib.sha256(BASE).hexdigest()
        self.assertEqual(manifest["files"][0]["sha256"], digest)
        self.assertEqual((self.out / "01_base.apk").read_bytes(), BASE)

    def test_scope_is_recorded_in_the_manifest(self):
        manifest = self.pull(scope="  agreed scope text  ")
        self.assertEqual(manifest["scope"], "agreed scope text")
        on_disk = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["package"], "com.example.aa")

    def test_private_permissions_on_directory_and_manifest(self):
        self.pull()
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.out / "manifest.json").stat().st_mode & 0o777, 0o600)

    def test_missing_scope_is_refused(self):
        with self.assertRaises(ap.InputError):
            self.pull(scope="   ")
        self.assertFalse(self.out.exists())

    def test_invalid_package_name_is_refused(self):
        with self.assertRaises(ap.InputError):
            ap.pull_package("com.example.aa; rm -rf /", str(self.out), "scope", None, str(self.adb))

    def test_existing_output_directory_is_refused(self):
        self.out.mkdir()
        with self.assertRaises(ap.InputError):
            self.pull()

    def test_failed_pull_marks_the_run_partial(self):
        (self.root / "files" / "data__app__aa__split_config.arm64.apk").unlink()
        manifest = self.pull()
        self.assertEqual(manifest["coverage"], "partial")
        self.assertEqual(len(manifest["failures"]), 1)
        failed = [f for f in manifest["files"] if f["status"] == "failed"]
        self.assertEqual(failed[0]["host_name"], "02_split_config.arm64.apk")

    def test_names_that_are_not_simple_apk_names_are_rejected_not_pulled(self):
        self.set_pm_paths(["/data/app/aa/base.apk", "/data/app/aa/bad name.apk", "relative.apk"])
        manifest = self.pull()
        self.assertEqual(manifest["coverage"], "partial")
        self.assertEqual(len(manifest["rejected"]), 2)
        self.assertEqual(len(manifest["files"]), 1)

    def test_paths_outside_the_allowed_directories_are_rejected_and_never_pulled(self):
        bad = {
            "/sdcard/Download/x.apk": b"shared storage",
            "/data/app/../data/com.other.app/files/x.apk": b"other package",
            "/data/app/aa/../../../sdcard/y.apk": b"traversal",
            "/data/data/com.example.aa/files/x.apk": b"app data",
            "/data/app/aa/base.odex": b"odex",
        }
        for path, data in bad.items():
            self.put_file(path, data)
        self.set_pm_paths(["/data/app/aa/base.apk"] + list(bad))
        manifest = self.pull()
        self.assertEqual(manifest["coverage"], "partial")
        rejected = {r["device_path"]: r["reason"] for r in manifest["rejected"]}
        self.assertEqual(set(rejected), set(bad))
        self.assertIn("'..'", rejected["/data/app/../data/com.other.app/files/x.apk"])
        self.assertIn("'..'", rejected["/data/app/aa/../../../sdcard/y.apk"])
        self.assertIn("outside", rejected["/sdcard/Download/x.apk"])
        pulled = [c[1] for c in self.adb_calls() if c[:1] == ["pull"]]
        self.assertEqual(pulled, ["/data/app/aa/base.apk"])
        self.assertEqual([p.name for p in self.out.iterdir() if p.name != "manifest.json"], ["01_base.apk"])

    def test_system_product_and_normalized_paths_are_pulled(self):
        self.put_file("/system/app/Foo/Foo.apk", b"system app")
        self.put_file("/product/app/Bar/Bar.apk", b"product app")
        self.set_pm_paths(["/data/app/aa/./base.apk", "/system/app/Foo/Foo.apk", "/product/app/Bar/Bar.apk"])
        manifest = self.pull()
        self.assertEqual(manifest["coverage"], "complete")
        self.assertEqual(manifest["rejected"], [])
        pulled = [c[1] for c in self.adb_calls() if c[:1] == ["pull"]]
        self.assertEqual(pulled, ["/data/app/aa/base.apk", "/system/app/Foo/Foo.apk", "/product/app/Bar/Bar.apk"])
        self.assertEqual(manifest["files"][0]["device_path"], "/data/app/aa/./base.apk")

    def test_cli_exit_codes_follow_coverage(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "com.example.aa", "--out", str(self.out),
                               "--scope", "own device", "--adb", str(self.adb)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["coverage"], "complete")

        done = subprocess.run([sys.executable, str(SCRIPT), "com.example.aa",
                               "--out", str(self.tmp / "second"),
                               "--adb", str(self.adb)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--scope", done.stderr)

    def test_adb_command_is_an_argument_list_without_a_shell(self):
        cmd = ap.adb_command("adb", "SER1", "shell", "pm", "path", "com.example.aa")
        self.assertEqual(cmd, ["adb", "-s", "SER1", "shell", "pm", "path", "com.example.aa"])

    def test_pull_timeout_is_recorded_and_the_run_continues(self):
        self.short_timeout()
        os.environ["FAKE_ADB_SLOW_PULL"] = "split_config"
        with redirect_stdout(io.StringIO()) as printed:
            code = ap.main(["com.example.aa", "--out", str(self.out), "--scope", SCOPE,
                            "--adb", str(self.adb)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(printed.getvalue())["failed"], 1)
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["coverage"], "partial")
        self.assertEqual(manifest["failures"],
                         [{"device_path": "/data/app/aa/split_config.arm64.apk", "error": "timeout"}])
        status = {f["host_name"]: f["status"] for f in manifest["files"]}
        self.assertEqual(status, {"01_base.apk": "pulled", "02_split_config.arm64.apk": "failed",
                                  "03_feature_x.apk": "pulled"})
        self.assertFalse((self.out / "02_split_config.arm64.apk").exists())
        self.assertEqual((self.out / "03_feature_x.apk").read_bytes(), FEATURE)
        timed_out = [r for r in self.trace_records() if r["function"] == "run_adb" and r["status"] == "timeout"]
        self.assertEqual(len(timed_out), 1)

    def test_pm_path_timeout_is_an_input_error_before_the_output_directory(self):
        self.short_timeout()
        os.environ["FAKE_ADB_SLOW_PM"] = "1"
        with redirect_stderr(io.StringIO()) as err:
            code = ap.main(["com.example.aa", "--out", str(self.out), "--scope", SCOPE,
                            "--adb", str(self.adb)])
        self.assertEqual(code, 2)
        self.assertIn("timed out", err.getvalue())
        self.assertFalse(self.out.exists())
        last = self.trace_records()[-1]
        self.assertEqual((last["function"], last["status"], last["exit_code"]), ("pull_package", "input_error", 2))

    def test_every_call_is_logged_with_utc_time_digests_and_outcome(self):
        manifest = self.pull()
        records = self.trace_records()
        self.assertEqual(sum(1 for r in records if r["function"] == "run_adb"), 4)  # pm path and three pulls
        for record in records:
            self.assertRegex(record["ts"], TS_RE)
            self.assertEqual(record["tool"], "adb_pull_package.py")
        summary = records[-1]
        self.assertEqual(summary["function"], "pull_package")
        self.assertEqual((summary["status"], summary["exit_code"]), ("complete", 0))
        self.assertEqual(summary["adb_sha256"], ap.adb_digest(str(self.adb)))
        self.assertEqual(summary["scope_sha256"], hashlib.sha256(SCOPE.encode("utf-8")).hexdigest())
        self.assertEqual(summary["scope_length"], len(SCOPE))
        self.assertEqual(summary["files"][0]["sha256"], hashlib.sha256(BASE).hexdigest())
        self.assertEqual(summary["out"], "pulled")
        self.assertNotIn(SCOPE, self.trace.read_text(encoding="utf-8"))
        self.assertEqual(self.trace.stat().st_mode & 0o777, 0o600)
        self.assertEqual(manifest["coverage"], "complete")

    def test_input_error_is_logged(self):
        with self.assertRaises(ap.InputError):
            self.pull(scope="   ")
        last = self.trace_records()[-1]
        self.assertEqual((last["function"], last["status"], last["exit_code"]), ("pull_package", "input_error", 2))
        self.assertEqual(last["scope_length"], 0)

    def test_trace_log_is_append_only(self):
        self.pull()
        first = self.trace.read_text(encoding="utf-8")
        self.pull(out=self.tmp / "second")
        second = self.trace.read_text(encoding="utf-8")
        self.assertTrue(second.startswith(first))
        self.assertEqual(sum(1 for r in self.trace_records() if r["function"] == "pull_package"), 2)


if __name__ == "__main__":
    unittest.main()
