#!/usr/bin/env python3
"""Tests for scripts/adb_pull_package.py using a fake adb that serves a fixture device tree."""
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "adb_pull_package.py"
sys.path.insert(0, str(SCRIPT.parent))

import adb_pull_package as ap  # noqa: E402

FAKE_ADB = r'''#!/usr/bin/env python3
import os, shutil, sys
root = os.environ["FAKE_ADB_ROOT"]
args = sys.argv[1:]
if args[:1] == ["-s"]:
    args = args[2:]
if args[:4] == ["shell", "pm", "path", "com.example.aa"]:
    sys.stdout.write(open(os.path.join(root, "pm_path.txt")).read())
    sys.exit(0)
if args[:1] == ["pull"]:
    src, dst = args[1], args[2]
    name = os.path.join(root, "files", src.lstrip("/").replace("/", "__"))
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


class PullTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "device"
        (self.root / "files" / "data__app__aa").mkdir(parents=True)
        self.adb = Path(self._tmp.name) / "adb"
        self.adb.write_text(FAKE_ADB, encoding="utf-8")
        self.adb.chmod(self.adb.stat().st_mode | stat.S_IEXEC)
        (self.root / "files" / "data__app__aa__base.apk").write_bytes(BASE)
        (self.root / "files" / "data__app__aa__split_config.arm64.apk").write_bytes(SPLIT)
        (self.root / "files" / "data__app__aa__feature_x.apk").write_bytes(FEATURE)
        self.set_pm_paths([
            "/data/app/aa/base.apk",
            "/data/app/aa/split_config.arm64.apk",
            "/data/app/aa/feature_x.apk",
        ])
        os.environ["FAKE_ADB_ROOT"] = str(self.root)
        self.out = Path(self._tmp.name) / "pulled"

    def tearDown(self):
        os.environ.pop("FAKE_ADB_ROOT", None)
        self._tmp.cleanup()

    def set_pm_paths(self, paths):
        (self.root / "pm_path.txt").write_text("".join("package:%s\n" % p for p in paths), encoding="utf-8")

    def pull(self, scope="user's own test device, com.example.aa, installed copy only", out=None):
        return ap.pull_package("com.example.aa", str(out or self.out), scope, None, str(self.adb))

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

    def test_cli_exit_codes_follow_coverage(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "com.example.aa", "--out", str(self.out),
                               "--scope", "own device", "--adb", str(self.adb)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["coverage"], "complete")

        done = subprocess.run([sys.executable, str(SCRIPT), "com.example.aa",
                               "--out", str(Path(self._tmp.name) / "second"),
                               "--adb", str(self.adb)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--scope", done.stderr)

    def test_adb_command_is_an_argument_list_without_a_shell(self):
        cmd = ap.adb_command("adb", "SER1", "shell", "pm", "path", "com.example.aa")
        self.assertEqual(cmd, ["adb", "-s", "SER1", "shell", "pm", "path", "com.example.aa"])


if __name__ == "__main__":
    unittest.main()
