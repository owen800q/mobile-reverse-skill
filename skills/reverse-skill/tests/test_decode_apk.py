#!/usr/bin/env python3
"""Tests for scripts/decode_apk.sh with stub jadx and apktool on PATH.

The stubs write the output directory the script expects and exit 0, so these
tests check what the script records (digests, the input/ copy, tool exit codes)
and not what a real decompiler produces. Skipped when bash, zip, unzip or a
SHA-256 tool is not on PATH.
"""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "decode_apk.sh"
BASH = shutil.which("bash")

MISSING = [name for name in ("bash", "zip", "unzip") if shutil.which(name) is None]
if shutil.which("sha256sum") is None and shutil.which("shasum") is None:
    MISSING.append("sha256sum or shasum")
SKIP_REASON = "decode_apk.sh tests need on PATH: " + ", ".join(MISSING)

# Names the "no decompiler" test hides from PATH.
DECOMPILERS = ("jadx", "apktool", "d2j-dex2jar", "dex2jar", "d2j-dex2jar.sh")

JADX_STUB = r'''#!/bin/sh
# Stub jadx: "jadx -d DIR [--show-bad-code] [--deobf] APK" writes one Java file under DIR.
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    -d) out="$2"; shift 2;;
    *) shift;;
  esac
done
mkdir -p "$out/sources/stub"
printf '%s\n' 'package stub; class Stub {}' > "$out/sources/stub/Stub.java"
exit 0
'''

APKTOOL_STUB = r'''#!/bin/sh
# Stub apktool: "apktool d -f -o DIR APK" writes DIR/AndroidManifest.xml and exits 0.
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2;;
    *) shift;;
  esac
done
mkdir -p "$out"
printf '%s\n' '<manifest package="com.example.stub"/>' > "$out/AndroidManifest.xml"
exit 0
'''


def unzip_swap_stub(real_unzip, replacement):
    """An unzip stub that swaps REPLACEMENT in for any .apks it is asked to read.

    The swap happens before the real unzip reads the bundle.
    """
    return (
        "#!/bin/sh\n"
        "# Stub unzip: before the real unzip reads a .apks bundle, replace the bundle.\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in\n"
        f"    *.apks) cp {shlex.quote(str(replacement))} \"$arg\";;\n"
        "  esac\n"
        "done\n"
        f"exec {shlex.quote(real_unzip)} \"$@\"\n"
    )


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_zip(archive, members):
    """Write a zip archive holding each member under its base name (zip -j)."""
    subprocess.run(["zip", "-q", "-j", str(archive), *map(str, members)],
                   check=True, capture_output=True)


def path_without(dest, hidden_names):
    """Fill DEST with symlinks to each executable on PATH, except HIDDEN_NAMES."""
    dest.mkdir()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not os.path.isabs(directory) or not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            link = dest / name
            if name in hidden_names or os.path.lexists(link):
                continue
            target = os.path.join(directory, name)
            if os.path.isfile(target) and os.access(target, os.X_OK):
                os.symlink(target, link)


@unittest.skipIf(bool(MISSING), SKIP_REASON)
class DecodeApkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="decode_apk_test_")
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name)
        self.src = self.work / "src"
        self.src.mkdir()
        self.tmpdir = self.work / "tmp"      # TMPDIR for the script's mktemp directories
        self.tmpdir.mkdir()
        self.stubs = self.work / "stubs"     # first on PATH: stub jadx and apktool
        self.stubs.mkdir()
        self._write_stub("jadx", JADX_STUB)
        self._write_stub("apktool", APKTOOL_STUB)

    def _write_stub(self, name, text):
        path = self.stubs / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)

    def run_decode(self, inputs, out, path_dirs=None):
        """Run decode_apk.sh on INPUTS with OUT as the output root."""
        if path_dirs is None:
            system = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
            path_dirs = [self.stubs] + system
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(str(p) for p in path_dirs)
        env["TMPDIR"] = str(self.tmpdir)
        return subprocess.run(
            [BASH, str(SCRIPT), *map(str, inputs), "--out", str(out)],
            env=env, capture_output=True, text=True, timeout=120,
        )

    def load_summary(self, out):
        with open(out / "decode_summary.json", encoding="utf-8") as fh:
            return json.load(fh)

    def test_plain_apk_records_input_and_target_digests(self):
        apk = self.src / "app-release.apk"
        apk.write_bytes(b"plain apk bytes\n" * 64)
        out = self.work / "out-plain"
        result = self.run_decode([apk], out)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.load_summary(out)
        self.assertEqual(summary["input_sha256"], sha256_of(apk))
        self.assertEqual(summary["target_apk"], "app-release.apk")
        self.assertEqual(summary["target_apk_sha256"], sha256_of(apk))
        self.assertEqual(summary["tools"]["jadx"], 0)
        self.assertEqual(summary["tools"]["apktool"], 0)
        self.assertEqual(summary["package"], "com.example.stub")
        snapshot = out / "input" / "app-release.apk"
        self.assertTrue(snapshot.is_file())
        self.assertEqual(sha256_of(snapshot), sha256_of(apk))
        self.assertTrue(os.path.samefile(summary["input_snapshot"], snapshot))
        self.assertEqual(json.loads(result.stdout), summary)

    def test_bundle_records_bundle_digest_and_base_apk_digest(self):
        base = self.src / "base.apk"
        base.write_bytes(b"base apk bytes\n" * 64)
        split = self.src / "config.arm64_v8a.apk"
        split.write_bytes(b"split apk bytes\n" * 32)
        bundle = self.src / "com.example.app.apks"
        make_zip(bundle, [base, split])
        bundle_digest = sha256_of(bundle)
        out = self.work / "out-bundle"
        result = self.run_decode([bundle], out)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.load_summary(out)
        # input_sha256 is the digest of the .apks file; target_apk_sha256 is the base APK.
        self.assertEqual(summary["input_sha256"], bundle_digest)
        self.assertEqual(summary["target_apk"], "base.apk")
        self.assertEqual(summary["target_apk_sha256"], sha256_of(base))
        self.assertEqual(summary["splits"], ["config.arm64_v8a.apk"])
        snapshot = out / "input" / "com.example.app.apks"
        self.assertTrue(snapshot.is_file())
        self.assertEqual(sha256_of(snapshot), bundle_digest)
        self.assertTrue(os.path.samefile(summary["input_snapshot"], snapshot))

    def test_input_digest_is_taken_before_bundle_extraction(self):
        # The unzip stub swaps the bundle for another archive before the real unzip
        # reads it. input_sha256 must still be the digest of the original bundle,
        # because the digest is taken before extraction. The target digest is of
        # the base APK that was actually extracted.
        original_base = self.src / "base.apk"
        original_base.write_bytes(b"original base apk\n" * 32)
        bundle = self.src / "com.example.app.apks"
        make_zip(bundle, [original_base])
        original_digest = sha256_of(bundle)

        replacement_src = self.work / "replacement"
        replacement_src.mkdir()
        replaced_base = replacement_src / "base.apk"
        replaced_base.write_bytes(b"replaced base apk\n" * 32)
        replacement = self.work / "replacement.apks"
        make_zip(replacement, [replaced_base])
        self.assertNotEqual(sha256_of(replacement), original_digest)

        self._write_stub("unzip", unzip_swap_stub(shutil.which("unzip"), replacement))
        out = self.work / "out-swap"
        result = self.run_decode([bundle], out)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.load_summary(out)
        self.assertEqual(summary["input_sha256"], original_digest)
        self.assertEqual(summary["target_apk_sha256"], sha256_of(replaced_base))

    def test_exits_1_when_neither_jadx_nor_apktool_is_on_path(self):
        apk = self.src / "app-release.apk"
        apk.write_bytes(b"plain apk bytes\n")
        hidden = self.work / "path-without-decompilers"
        path_without(hidden, DECOMPILERS)
        out = self.work / "out-none"
        result = self.run_decode([apk], out, path_dirs=[hidden])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("neither jadx nor apktool found on PATH", result.stderr)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
