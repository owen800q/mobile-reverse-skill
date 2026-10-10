#!/usr/bin/env python3
"""Tests for scripts/firmware_survey.py and scripts/firmware_unpack.py.

Standard library only. Fixtures are built in temporary directories at test time;
no binary fixtures are committed. unpack tests use a stub unblob written by the
test. The real-unblob test runs only when REVERSE_SKILL_TEST_UNBLOB is set to an
absolute path to unblob, and skips otherwise.

Run: python3 -m unittest discover -s skills/reverse-skill/tests -v
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import platform
import shutil
import struct
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import firmware_survey as survey  # noqa: E402
import firmware_unpack as unpack  # noqa: E402


REAL_UNBLOB = os.environ.get("REVERSE_SKILL_TEST_UNBLOB", "")
FAKE_HASH = "$6$fakesalt$FAKEHASHFAKEHASHFAKEHASHFAKEHASH"
FAKE_KEY_BODY = "KEYBODY-SECRET-0123456789"


def build_elf32_be_mips(phdr_types=(), total_size=None):
    """Header-only big-endian MIPS ELF32 file. It is never executed."""
    phnum = len(phdr_types)
    header = bytearray(52)
    header[0:4] = b"\x7fELF"
    header[4] = 1  # ELFCLASS32
    header[5] = 2  # ELFDATA2MSB
    header[6] = 1  # EV_CURRENT
    struct.pack_into(
        ">HHIIIIIHHHHHH", header, 16,
        2,                       # e_type ET_EXEC
        8,                       # e_machine EM_MIPS
        1,                       # e_version
        0x400000,                # e_entry
        52 if phnum else 0,      # e_phoff
        0,                       # e_shoff
        0,                       # e_flags
        52,                      # e_ehsize
        32 if phnum else 0,      # e_phentsize
        phnum,                   # e_phnum
        0, 0, 0,
    )
    table = b"".join(struct.pack(">8I", ptype, 0, 0, 0, 0, 0, 0, 0) for ptype in phdr_types)
    blob = bytes(header) + table
    if total_size is not None and total_size > len(blob):
        blob += b"\0" * (total_size - len(blob))
    return blob


def make_rootfs(root: Path, outside: Path) -> dict:
    """Build a synthetic root filesystem. Returns offsets the assertions need."""
    def write(rel, data, mode=0o644):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)

    write("bin/mipsbe", build_elf32_be_mips(phdr_types=(3, 1)), 0o755)   # PT_INTERP present
    write("usr/lib/static.bin", build_elf32_be_mips(phdr_types=(1,)), 0o755)
    write("usr/lib/broken.so", b"\x7fELF\x01\x02\x01")                 # truncated ident
    write("etc/passwd",
          b"root:x:0:0:root:/root:/bin/sh\n"
          b"toor:x:0:0:alt root:/root:/bin/bash\n"
          b"ghost::1001:1001::/:/bin/false\n"
          b"daemon:x:1:1:daemon:/:/bin/false\n")
    write("etc/shadow",
          ("root:%s:19000:0:99999:7:::\n" % FAKE_HASH).encode()
          + b"toor:*:19000:0:99999:7:::\n"
          + b"ghost::19000:0:99999:7:::\n"
          + b"admin:$1$abcdefgh$FAKEMD5FAKEMD5FAKEMD5FAK:19000:0:99999:7:::\n", 0o600)
    write("etc/init.d/rcS", b"#!/bin/sh\nmount -a\n", 0o755)
    write("etc/inittab", b"::sysinit:/etc/init.d/rcS\n")
    write("etc/rc2.d/S20telnet", b"#!/bin/sh\n", 0o755)
    write("etc/ssl/private/device.key",
          ("-----BEGIN RSA PRIVATE KEY-----\n%s\n-----END RSA PRIVATE KEY-----\n" % FAKE_KEY_BODY)
          .encode(), 0o600)
    write("etc/ssl/certs/ca.crt",
          b"-----BEGIN CERTIFICATE-----\nFAKECERTFAKECERT\n-----END CERTIFICATE-----\n")
    write("var/www/cgi-bin/login.cgi", b"#!/bin/sh\necho ok\n", 0o755)
    write("var/www/index.asp", b"<form action=\"/goform/setWifi\"></form>\n")

    goform = b"/goform/setWifi"
    binary = (
        build_elf32_be_mips(phdr_types=(1,))
        + b"\0" * 64
        + b"\0/cgi-bin/login.cgi\0"
        + goform + b"\0"
        + b"BusyBox v1.22.1 (2016-01-01)\0OpenSSL 1.0.2k  26 Jan 2017\0"
        + b"OpenSSL 1.0.2k  26 Jan 2017\0dropbear_2019.78\0"
    )
    write("usr/sbin/httpd", binary, 0o755)
    goform_offset = binary.index(goform)

    # Larger than the max-file-bytes used by the tests: header read only, no content scan.
    write("usr/lib/big.so", build_elf32_be_mips(phdr_types=(3,), total_size=8192)
          + b"BusyBox v9.9.9-HIDDEN")

    # Symlinks: relative inside the root, absolute outside, and a directory outside.
    (root / "etc/rc.d").mkdir(parents=True, exist_ok=True)
    os.symlink("../init.d/rcS", root / "etc/rc.d/S10network")
    os.symlink("/etc/shadow", root / "etc/host-shadow")
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "evil.cgi").write_text("#!/bin/sh\n")
    os.symlink(str(outside), root / "var/www/outside-link")

    if hasattr(os, "mkfifo"):
        os.mkfifo(root / "dev_fifo")
    return {"goform_offset": goform_offset}


class ElfParsingTests(unittest.TestCase):
    def parse(self, data):
        return survey.parse_elf(survey._bytes_reader(data), len(data))

    def test_big_endian_mips_header(self):
        rec = self.parse(build_elf32_be_mips(phdr_types=(1,)))
        self.assertEqual(rec["class"], 32)
        self.assertEqual(rec["endianness"], "BE")
        self.assertEqual(rec["e_machine"], "MIPS")
        self.assertEqual(rec["e_type"], "EXEC")
        self.assertFalse(rec["pt_interp"])
        self.assertIsNone(rec["malformed"])

    def test_pt_interp_detected(self):
        self.assertTrue(self.parse(build_elf32_be_mips(phdr_types=(3,)))["pt_interp"])

    def test_not_elf_returns_none(self):
        self.assertIsNone(self.parse(b"MZ\x90\x00" + b"\0" * 60))

    def test_malformed_cases_are_reported_not_raised(self):
        self.assertEqual(self.parse(b"\x7fELF\x01\x02\x01")["malformed"], "truncated e_ident")
        bad_class = bytearray(build_elf32_be_mips())
        bad_class[4] = 3
        self.assertIn("EI_CLASS", self.parse(bytes(bad_class))["malformed"])
        self.assertEqual(self.parse(b"\x7fELF\x01\x02\x01" + b"\0" * 9)["malformed"],
                         "truncated ELF header")
        cut = build_elf32_be_mips(phdr_types=(3,))[:52]
        self.assertIn("outside the file", self.parse(cut)["malformed"])
        small_entries = bytearray(build_elf32_be_mips(phdr_types=(3,)))
        small_entries[42:44] = struct.pack(">H", 16)  # e_phentsize at offset 42 (ELF32)
        self.assertIn("below 32", self.parse(bytes(small_entries))["malformed"])

    def test_host_binary_is_x86_64_dynamic(self):
        ls = Path("/bin/ls")
        if not (platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")
                and ls.exists()):
            self.skipTest("needs a Linux x86-64 host with /bin/ls")
        with open(ls, "rb") as fh:
            data = fh.read()
        rec = self.parse(data)
        self.assertEqual(rec["e_machine"], "x86-64")
        self.assertEqual(rec["class"], 64)
        self.assertEqual(rec["endianness"], "LE")
        self.assertTrue(rec["pt_interp"], "expected /bin/ls to be dynamically linked")


class SurveyTests(unittest.TestCase):
    MAX_FILE = 4096

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.root = base / "rootfs"
        cls.root.mkdir()
        cls.outside = base / "outside-dir"
        cls.info = make_rootfs(cls.root, cls.outside)
        cls.survey = survey.Survey(str(cls.root), cls.MAX_FILE, 500)
        cls.survey.scan()
        cls.doc = cls.survey.document()
        cls.text = json.dumps(cls.doc)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def elf_by_path(self, path):
        return next(item for item in self.doc["elf"]["items"] if item["path"] == path)

    def test_counts(self):
        counts = self.doc["counts"]
        self.assertEqual(counts["skipped_large"], 1)
        self.assertEqual(counts["elf"], 5)  # mipsbe, static.bin, broken.so, httpd, big.so
        self.assertEqual(counts["symlinks"], 3)
        self.assertEqual(counts["other_special"], 1 if hasattr(os, "mkfifo") else 0)
        self.assertEqual(counts["unreadable"], 0)
        self.assertEqual(self.doc["errors"]["count"], 0)

    def test_elf_records(self):
        mips = self.elf_by_path("bin/mipsbe")
        self.assertEqual((mips["class"], mips["endianness"], mips["e_machine"]), (32, "BE", "MIPS"))
        self.assertTrue(mips["pt_interp"])
        self.assertEqual(len(mips["sha256"]), 64)
        self.assertFalse(self.elf_by_path("usr/lib/static.bin")["pt_interp"])
        self.assertIsNotNone(self.elf_by_path("usr/lib/broken.so")["malformed"])
        big = self.elf_by_path("usr/lib/big.so")
        self.assertIsNone(big["sha256"])
        self.assertGreater(big["size"], self.MAX_FILE)

    def test_init_scripts(self):
        paths = {item["path"] for item in self.doc["init_scripts"]["items"]}
        self.assertEqual(paths, {
            "etc/init.d/rcS", "etc/inittab", "etc/rc.d/S10network", "etc/rc2.d/S20telnet",
        })

    def test_accounts_flags_and_no_hash_output(self):
        accounts = {item["name"]: item for item in self.doc["accounts"]["accounts"]["items"]}
        self.assertIn("uid0_nonroot", accounts["toor"]["flags"])
        self.assertIn("interactive_shell", accounts["toor"]["flags"])
        self.assertIn("empty_passwd_field", accounts["ghost"]["flags"])
        self.assertIn("empty_shadow_hash", accounts["ghost"]["flags"])
        self.assertEqual(accounts["root"]["shadow"]["scheme"], "$6$")
        self.assertTrue(accounts["root"]["shadow"]["has_hash"])
        self.assertEqual(accounts["daemon"]["flags"], [])
        shadow_only = {item["name"]: item for item in self.doc["accounts"]["shadow_only"]["items"]}
        self.assertEqual(shadow_only["admin"]["shadow"]["scheme"], "$1$")
        self.assertNotIn("FAKEHASH", self.text)
        self.assertNotIn("FAKEMD5", self.text)
        self.assertNotIn("abcdefgh", self.text)

    def test_keys_kinds_without_key_contents(self):
        keys = {item["path"]: item for item in self.doc["keys_and_certs"]["items"]}
        key = keys["etc/ssl/private/device.key"]
        self.assertEqual(key["kind"], "RSA PRIVATE KEY")
        self.assertIs(key["private_key_material"], True)
        cert = keys["etc/ssl/certs/ca.crt"]
        self.assertEqual(cert["kind"], "CERTIFICATE")
        self.assertIs(cert["private_key_material"], False)
        self.assertNotIn(FAKE_KEY_BODY, self.text)

    def test_web_listing_does_not_follow_symlinks(self):
        self.assertIn("var/www/cgi-bin", self.doc["web"]["dirs"]["items"])
        files = {item["path"] for item in self.doc["web"]["files"]["items"]}
        self.assertIn("var/www/cgi-bin/login.cgi", files)
        self.assertIn("var/www/index.asp", files)
        self.assertFalse(any("outside-link" in path for path in files),
                         "a symlinked directory outside ROOT must not be walked")

    def test_symlinks_recorded_not_followed(self):
        items = {item["path"]: item for item in self.doc["symlinks"]["items"]}
        self.assertEqual(items["etc/host-shadow"]["target"], "/etc/shadow")
        self.assertTrue(items["etc/host-shadow"]["absolute"])
        self.assertTrue(items["etc/host-shadow"]["escapes_root"])
        self.assertFalse(items["etc/rc.d/S10network"]["escapes_root"])
        self.assertEqual(items["var/www/outside-link"]["target"], str(self.outside))

    def test_route_candidates_with_offsets(self):
        matches = [item for item in self.doc["route_candidates"]["items"]
                   if item["file"] == "usr/sbin/httpd" and "/goform/setWifi" in item["string"]]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["offset"], self.info["goform_offset"])
        self.assertTrue(any(item["file"] == "var/www/index.asp"
                            for item in self.doc["route_candidates"]["items"]))

    def test_version_banners_counted(self):
        banners = {(item["file"], item["match"]): item["count"]
                   for item in self.doc["version_banners"]["items"]}
        self.assertEqual(banners[("usr/sbin/httpd", "BusyBox v1.22.1")], 1)
        self.assertEqual(banners[("usr/sbin/httpd", "OpenSSL 1.0.2k")], 2)
        self.assertEqual(banners[("usr/sbin/httpd", "dropbear_2019.78")], 1)
        self.assertFalse(any("v9.9.9" in item["match"] for item in self.doc["version_banners"]["items"]),
                         "files above max-file-bytes must not be content-scanned")

    def test_limitations_present(self):
        self.assertIn("Static strings and headers only; nothing was executed", self.doc["limitations"])
        self.assertTrue(any("unverified" in item for item in self.doc["limitations"]))
        self.assertTrue(any("does not prove" in item for item in self.doc["limitations"]))

    def test_lists_bounded_by_max_items(self):
        bounded = survey.Survey(str(self.root), self.MAX_FILE, 2)
        bounded.scan()
        doc = bounded.document()
        self.assertEqual(len(doc["elf"]["items"]), 2)
        self.assertTrue(doc["elf"]["truncated"])
        self.assertEqual(doc["elf"]["count"], 5)
        self.assertEqual(doc["counts"]["elf"], 5)

    def test_real_ls_copy_is_x86_64_dynamic(self):
        ls = Path("/bin/ls")
        if not (platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")
                and ls.exists()):
            self.skipTest("needs a Linux x86-64 host with /bin/ls")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bin").mkdir()
            shutil.copy2(str(ls), str(Path(tmp) / "bin" / "ls"))
            scan = survey.Survey(tmp, 32 * 1024 * 1024, 500)
            scan.scan()
            doc = scan.document()
        record = doc["elf"]["items"][0]
        self.assertEqual(record["path"], "bin/ls")
        self.assertEqual(record["e_machine"], "x86-64")
        self.assertTrue(record["pt_interp"])

    def test_main_writes_survey_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "survey-out"
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = survey.main([str(self.root), "--out", str(out), "--max-file-bytes", "4096"])
            self.assertEqual(code, 0, stderr.getvalue())
            written = json.loads((out / "survey.json").read_text(encoding="utf-8"))
            self.assertEqual(written["counts"]["elf"], 5)
            summary = stdout.getvalue()
            self.assertIn("firmware_survey:", summary)
            self.assertNotIn(FAKE_HASH, summary)
            self.assertNotIn(FAKE_KEY_BODY, summary)
            self.assertNotIn("FAKEHASH", (out / "survey.json").read_text(encoding="utf-8"))

    def test_refuses_existing_output_and_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "exists"
            existing.mkdir()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(survey.main([str(self.root), "--out", str(existing)]), 2)
                self.assertEqual(survey.main([str(Path(tmp) / "missing"), "--out",
                                              str(Path(tmp) / "new")]), 2)
            self.assertFalse((existing / "survey.json").exists())
            self.assertIn("already exists", stderr.getvalue())


def write_stub(directory: Path) -> str:
    path = directory / "fake-unblob"
    path.write_text("#!%s\n%s" % (sys.executable, STUB_SOURCE), encoding="utf-8")
    path.chmod(0o755)
    return str(path)


STUB_SOURCE = r'''
import argparse
import json
import os
import sys
import time

ap = argparse.ArgumentParser(add_help=False)
ap.add_argument("--version", action="store_true")
ap.add_argument("--extract-dir")
ap.add_argument("--depth", type=int)
ap.add_argument("--report")
ap.add_argument("--log")
ap.add_argument("input", nargs="?")
args = ap.parse_args()

if args.version:
    sys.stdout.write(os.environ.get("STUB_VERSION", "9.9.9") + "\n")
    sys.exit(0)

if os.environ.get("STUB_ARGV_LOG"):
    with open(os.environ["STUB_ARGV_LOG"], "a") as fh:
        fh.write(json.dumps(sys.argv) + "\n")
if os.environ.get("STUB_COUNT_FILE"):
    with open(os.environ["STUB_COUNT_FILE"], "a") as fh:
        fh.write("x")

mode = os.environ.get("STUB_MODE", "ok")
if mode == "sleep":
    time.sleep(60)
if mode == "fail":
    sys.stderr.write("stub: failing on purpose\n")
    sys.exit(1)
if mode == "sandbox_error":
    sys.stderr.write("stub: sandbox failed to start: operation not permitted\n")
    sys.exit(1)
if mode == "mutate":
    with open(args.input, "ab") as fh:
        fh.write(b"!")
if mode == "spam":
    sys.stdout.write("o" * (3 * 1024 * 1024))
    sys.stderr.write("e" * (2 * 1024 * 1024))
    sys.stdout.flush()
    sys.stderr.flush()
if mode == "sandbox_warn":
    sys.stderr.write("Sandboxing FS access is unavailable on this system, skipping.\n")

base = os.path.join(args.extract_dir, os.path.basename(args.input) + "_extract")
if mode == "dirs_only":
    os.makedirs(os.path.join(base, "etc"), exist_ok=True)
    os.makedirs(os.path.join(base, "usr", "bin"), exist_ok=True)
elif mode != "fail":
    for rel, data in (
        ("etc/passwd", b"root:x:0:0:root:/root:/bin/sh\n"),
        ("etc/init.d/rcS", b"#!/bin/sh\n"),
        ("usr/bin/app", b"\x7fELF-not-really"),
    ):
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    if mode == "symlink":
        os.symlink(os.environ["STUB_SYMLINK_TARGET"], os.path.join(base, "escape"))

size = os.path.getsize(args.input)
extract_path = base
task0 = {"path": os.path.abspath(args.input), "depth": 0, "blob_id": "", "is_multi_file": False}
chunk_reports = [
    {"__typename__": "StatReport", "path": task0["path"], "size": size, "is_dir": False,
     "is_file": True, "is_link": False, "link_target": None},
    {"__typename__": "ChunkReport", "id": "1:1", "handler_name": "tar", "start_offset": 0,
     "end_offset": size, "size": size, "is_encrypted": mode == "encrypted",
     "extraction_reports": []},
]
if mode == "unknown":
    chunk_reports.append({"__typename__": "UnknownChunkReport", "id": "1:2", "start_offset": 0,
                          "end_offset": 4, "size": 4, "randomness": None})
if mode == "unextracted":
    chunk_reports[1]["extraction_reports"] = [{
        "__typename__": "ExtractorDependencyNotFoundReport", "severity": "ERROR",
        "dependencies": ["7z"]}]
report = [
    {"task": task0, "reports": chunk_reports,
     "subtasks": [{"path": extract_path, "depth": 1, "blob_id": "1:1", "is_multi_file": False}]},
    {"task": {"path": extract_path, "depth": 1, "blob_id": "1:1", "is_multi_file": False},
     "reports": [{"__typename__": "StatReport", "path": extract_path, "size": 4096,
                  "is_dir": True, "is_file": False, "is_link": False, "link_target": None}],
     "subtasks": []},
]
if args.report and mode not in ("missing_report", "fail"):
    if mode == "badreport":
        with open(args.report, "w") as fh:
            fh.write("{not json")
    else:
        with open(args.report, "w") as fh:
            json.dump(report, fh)
sys.exit(1 if mode == "fail_partial" else 0)
'''


def run_main(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = unpack.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class UnpackTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.firmware = self.work / "firmware.bin"
        self.firmware.write_bytes(b"FIRMWARE-IMAGE-" * 512)
        self.tool = write_stub(self.tmp)
        self.argv_log = self.tmp / "argv.log"
        self.count_file = self.tmp / "count.txt"
        self.env = {
            "UNBLOB_COMMAND": self.tool,
            "STUB_ARGV_LOG": str(self.argv_log),
            "STUB_COUNT_FILE": str(self.count_file),
        }
        self.out = self.tmp / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def run_stub(self, mode, extra_argv=(), extra_env=None):
        env = dict(self.env)
        env["STUB_MODE"] = mode
        env.update(extra_env or {})
        with mock.patch.dict(os.environ, env, clear=False):
            return run_main([str(self.firmware), "--out", str(self.out), *extra_argv])

    def manifest(self):
        return json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))


class UnpackArgumentTests(UnpackTestBase):
    def test_relative_tool_path_rejected_before_anything_is_created(self):
        code, _, stderr = run_main([str(self.firmware), "--out", str(self.out),
                                    "--unblob", "fake-unblob"])
        self.assertEqual(code, 2)
        self.assertIn("absolute", stderr)
        self.assertFalse(self.out.exists())

    def test_missing_tool_gives_hint(self):
        code, _, stderr = run_main([str(self.firmware), "--out", str(self.out),
                                    "--unblob", str(self.tmp / "no-such-unblob")])
        self.assertEqual(code, 2)
        self.assertIn("UNBLOB_COMMAND", stderr)
        self.assertIn("does not install unblob", stderr)
        self.assertFalse(self.out.exists())

    def test_no_tool_configured_gives_hint(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _, stderr = run_main([str(self.firmware), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("does not install unblob", stderr)

    def test_non_executable_tool_rejected(self):
        plain = self.tmp / "not-exec"
        plain.write_text("#!/bin/sh\n")
        plain.chmod(0o644)
        code, _, stderr = run_main([str(self.firmware), "--out", str(self.out),
                                    "--unblob", str(plain)])
        self.assertEqual(code, 2)
        self.assertIn("not executable", stderr)

    def test_environment_variable_supplies_the_tool(self):
        code, stdout, stderr = self.run_stub("ok")
        self.assertEqual(code, 0, stderr)
        self.assertIn("status=complete", stdout)

    def test_refuses_existing_output_directory(self):
        self.out.mkdir()
        sentinel = self.out / "keep.txt"
        sentinel.write_text("do not touch")
        code, _, stderr = self.run_stub("ok")
        self.assertEqual(code, 2)
        self.assertIn("already exists", stderr)
        self.assertEqual(sentinel.read_text(), "do not touch")
        self.assertFalse(self.argv_log.exists(), "unblob must not run when DIR exists")

    def test_input_checks(self):
        missing = self.work / "absent.bin"
        empty = self.work / "empty.bin"
        empty.write_bytes(b"")
        huge = self.work / "huge.bin"
        with open(huge, "wb") as fh:
            fh.truncate(128 * 1024 * 1024 + 1)
        for path in (missing, empty, huge, self.work):
            code, _, stderr = run_main([str(path), "--out", str(self.out),
                                        "--unblob", self.tool])
            self.assertEqual(code, 2, path)
            self.assertFalse(self.out.exists())
            if path == huge:
                self.assertIn("128 MiB", stderr)


class UnpackRunTests(UnpackTestBase):
    def test_complete_manifest_hashes_argv_and_limitations(self):
        code, stdout, stderr = self.run_stub("ok")
        self.assertEqual(code, 0, stderr)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["input"]["sha256"], sha256_of(self.firmware))
        self.assertEqual(manifest["input"]["size_bytes"], self.firmware.stat().st_size)
        self.assertTrue(manifest["input"]["unchanged"])
        self.assertEqual(manifest["unblob"]["sha256"], sha256_of(self.tool))
        self.assertEqual(manifest["unblob"]["version"], "9.9.9")
        argv = manifest["run"]["argv"]
        self.assertNotIn("--no-sandbox", argv)
        self.assertEqual(argv[argv.index("--depth") + 1], "10")
        self.assertIn("--report", argv)
        self.assertIn("--extract-dir", argv)
        self.assertEqual(manifest["run"]["exit_code"], 0)
        for line in (
            "Extraction only; no extracted program was executed",
            "Unblob's default sandbox remained enabled",
            "Format coverage is unblob's; unknown or encrypted regions are not reconstructed",
            "Successful extraction does not establish complete firmware reconstruction or runtime behavior",
        ):
            self.assertIn(line, manifest["limitations"])
        self.assertEqual(manifest["inventory"]["rootfs_candidates"], ["firmware.bin_extract"])
        self.assertTrue((self.out / "extracted").is_dir())
        self.assertTrue((self.out / "logs").is_dir())
        self.assertNotIn("FIRMWARE-IMAGE", stdout)

    def test_input_directory_untouched(self):
        before = sorted(os.listdir(self.work))
        code, _, _ = self.run_stub("ok")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(self.work)), before)
        self.assertFalse(self.manifest()["input_directory"]["changed"])

    def test_unknown_chunk_gives_partial(self):
        code, _, _ = self.run_stub("unknown")
        self.assertEqual(code, 0)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["report"]["unknown_chunks"], 1)

    def test_encrypted_chunk_gives_partial(self):
        self.run_stub("encrypted")
        self.assertEqual(self.manifest()["status"], "partial")

    def test_unextracted_chunk_names_missing_dependency(self):
        code, _, _ = self.run_stub("unextracted")
        self.assertEqual(code, 0)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["report"]["missing_dependencies"], ["7z"])
        self.assertGreaterEqual(manifest["report"]["unextracted_total"], 1)

    def test_failed_run_without_output_is_failed(self):
        code, _, _ = self.run_stub("fail")
        self.assertEqual(code, 1)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["run"]["exit_code"], 1)
        self.assertEqual(manifest["counts"]["entries"], 0)

    def test_directories_only_is_not_complete(self):
        code, _, _ = self.run_stub("dirs_only")
        self.assertEqual(code, 0)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["counts"]["files"], 0)
        self.assertGreater(manifest["counts"]["dirs"], 0)

    def test_failed_run_with_output_is_partial(self):
        code, _, _ = self.run_stub("fail_partial")
        self.assertEqual(code, 0)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["run"]["exit_code"], 1)

    def test_input_changed_during_run_fails(self):
        code, _, stderr = self.run_stub("mutate")
        self.assertEqual(code, 1)
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "failed")
        self.assertFalse(manifest["input"]["unchanged"])
        self.assertIn("input file changed", " ".join(manifest["status_reasons"]))

    def test_timeout_kills_unblob(self):
        started = time.monotonic()
        code, _, _ = self.run_stub("sleep", extra_argv=["--timeout", "1"])
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(code, 1)
        manifest = self.manifest()
        self.assertTrue(manifest["run"]["timed_out"])
        self.assertEqual(manifest["status"], "failed")

    def test_log_capture_is_bounded_with_exact_counts(self):
        code, _, _ = self.run_stub("spam")
        self.assertEqual(code, 0)
        logs = self.manifest()["logs"]
        self.assertEqual(logs["stdout"]["bytes_total"], 3 * 1024 * 1024)
        self.assertEqual(logs["stdout"]["bytes_kept"], unpack.LOG_CAP_BYTES)
        self.assertTrue(logs["stdout"]["truncated"])
        self.assertEqual(logs["stderr"]["bytes_total"], 2 * 1024 * 1024)
        self.assertEqual((self.out / "logs" / "unblob-stdout.log").stat().st_size,
                         unpack.LOG_CAP_BYTES)

    def test_sandbox_unavailable_warning_is_recorded(self):
        code, _, stderr = self.run_stub("sandbox_warn")
        self.assertEqual(code, 0)
        manifest = self.manifest()
        self.assertTrue(manifest["sandbox"]["unavailable_warning"])
        self.assertNotIn("Unblob's default sandbox remained enabled", manifest["limitations"])
        self.assertIn("sandbox", stderr.lower())

    def test_sandbox_startup_error_is_reported_and_not_retried(self):
        code, _, stderr = self.run_stub("sandbox_error")
        self.assertEqual(code, 1)
        self.assertEqual(self.count_file.read_text(), "x", "unblob must run exactly once")
        manifest = self.manifest()
        self.assertTrue(manifest["sandbox"]["error_reported"])
        self.assertIn("not retried", stderr)

    def test_symlinks_recorded_and_never_followed(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("OUTSIDE-SECRET-CONTENT")
        code, _, _ = self.run_stub("symlink", extra_env={"STUB_SYMLINK_TARGET": str(outside)})
        self.assertEqual(code, 0)
        entries = {entry["path"]: entry for entry in self.manifest()["inventory"]["entries"]}
        link = entries["firmware.bin_extract/escape"]
        self.assertEqual(link["type"], "symlink")
        self.assertEqual(link["target"], str(outside))
        self.assertIsNone(link["sha256"])
        self.assertFalse(any(path.startswith("firmware.bin_extract/escape/") for path in entries))
        self.assertNotIn(hashlib.sha256(secret.read_bytes()).hexdigest(),
                         (self.out / "manifest.json").read_text())

    def test_hash_cap_leaves_large_files_unhashed(self):
        with mock.patch.object(unpack, "MAX_HASH_BYTES", 4):
            self.run_stub("ok")
        counts = self.manifest()["counts"]
        self.assertGreater(counts["hash_skipped_large"], 0)
        big = [e for e in self.manifest()["inventory"]["entries"]
               if e["type"] == "file" and e["size"] > 4]
        self.assertTrue(big and all(e["sha256"] is None for e in big))

    def test_missing_report_is_partial(self):
        self.run_stub("missing_report")
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "partial")
        self.assertFalse(manifest["report"]["present"])

    def test_unrecognised_report_is_partial_with_note(self):
        self.run_stub("badreport")
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["report"]["parse"], "unrecognized")
        self.assertTrue(any("not recognised" in line for line in manifest["limitations"]))

    def test_depth_limit_reached_is_partial(self):
        self.run_stub("ok", extra_argv=["--max-depth", "1"])
        manifest = self.manifest()
        self.assertEqual(manifest["report"]["depth_limited_tasks"], 1)
        self.assertEqual(manifest["status"], "partial")
        self.assertIn("1", " ".join(manifest["status_reasons"]))

    def test_nothing_passes_no_sandbox_flag(self):
        self.run_stub("ok")
        for line in self.argv_log.read_text().splitlines():
            self.assertNotIn("--no-sandbox", json.loads(line))


class UnpackHelperTests(unittest.TestCase):
    def test_report_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            task = {"path": "/x/input", "depth": 0, "blob_id": "", "is_multi_file": False}
            data = [{
                "task": task,
                "reports": [
                    {"__typename__": "ChunkReport", "id": "a", "handler_name": "zip",
                     "start_offset": 0, "end_offset": 9, "size": 9, "is_encrypted": False,
                     "extraction_reports": [{"__typename__": "ExtractorDependencyNotFoundReport",
                                             "severity": "ERROR", "dependencies": ["7z"]}]},
                    {"__typename__": "ChunkReport", "id": "b", "handler_name": "padding",
                     "start_offset": 9, "end_offset": 20, "size": 11, "is_encrypted": False,
                     "extraction_reports": []},
                    {"__typename__": "ChunkReport", "id": "c", "handler_name": "luks",
                     "start_offset": 20, "end_offset": 30, "size": 10, "is_encrypted": True,
                     "extraction_reports": []},
                    {"__typename__": "UnknownChunkReport", "id": "d", "start_offset": 30,
                     "end_offset": 31, "size": 1, "randomness": None},
                ],
                "subtasks": [{"path": "/x/out", "depth": 1, "blob_id": "a", "is_multi_file": False}],
            }, {
                "task": {"path": "/x/out", "depth": 1, "blob_id": "a", "is_multi_file": False},
                "reports": [{"__typename__": "StatReport", "path": "/x/out", "size": 1,
                             "is_dir": True, "is_file": False, "is_link": False,
                             "link_target": None}],
                "subtasks": [],
            }]
            path.write_text(json.dumps(data))
            summary = unpack.analyze_report(str(path), max_depth=1)
        self.assertEqual(summary["parse"], "ok")
        self.assertEqual(summary["chunks"], 3)
        self.assertEqual(summary["unknown_chunks"], 1)
        self.assertEqual(summary["encrypted_chunks"], 1)
        self.assertEqual(summary["unextracted_chunks"], 1)
        self.assertEqual(summary["depth_limited_tasks"], 1)
        self.assertEqual(summary["missing_dependencies"], ["7z"])
        self.assertEqual(summary["error_reports"], 1)

    def test_report_parse_failures_are_unrecognized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            for payload in ("{}", "[1, 2]", "not json", "[{\"task\": 5, \"reports\": []}]"):
                path.write_text(payload)
                self.assertEqual(unpack.analyze_report(str(path), 10)["parse"], "unrecognized",
                                 payload)
            self.assertEqual(unpack.analyze_report(str(Path(tmp) / "absent.json"), 10)["parse"],
                             "absent")

    def test_status_rules(self):
        ok_run = {"exit_code": 0, "timed_out": False, "launch_error": None,
                  "timeout_seconds": 900.0}
        bad_run = dict(ok_run, exit_code=1)
        clean = {"present": True, "parse": "ok", "unknown_chunks": 0, "encrypted_chunks": 0,
                 "unextracted_total": 0}
        self.assertEqual(unpack.decide_status(ok_run, 3, clean, False, False)[0], "complete")
        self.assertEqual(unpack.decide_status(ok_run, 0, clean, False, False)[0], "partial")
        self.assertEqual(unpack.decide_status(ok_run, 3, dict(clean, unknown_chunks=1),
                                              False, False)[0], "partial")
        self.assertEqual(unpack.decide_status(ok_run, 3, dict(clean, present=False, parse="absent"),
                                              False, False)[0], "partial")
        self.assertEqual(unpack.decide_status(bad_run, 0, clean, False, False)[0], "failed")
        self.assertEqual(unpack.decide_status(bad_run, 2, clean, False, False)[0], "partial")
        self.assertEqual(unpack.decide_status(ok_run, 3, clean, True, False)[0], "failed")
        self.assertEqual(unpack.decide_status(ok_run, 3, clean, False, True)[0], "failed")

    def test_rootfs_candidates(self):
        entries = [
            {"path": "fw_extract", "type": "dir"},
            {"path": "fw_extract/etc", "type": "dir"},
            {"path": "fw_extract/usr", "type": "dir"},
            {"path": "other", "type": "dir"},
            {"path": "other/etc", "type": "dir"},
        ]
        self.assertEqual(unpack.rootfs_candidates(entries)[0], ["fw_extract"])


@unittest.skipUnless(os.path.isabs(REAL_UNBLOB) and os.path.isfile(REAL_UNBLOB),
                     "set REVERSE_SKILL_TEST_UNBLOB to an absolute unblob path to run")
class RealUnblobTests(unittest.TestCase):
    def test_real_unblob_extracts_plain_tar(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "src"
            (src / "etc" / "init.d").mkdir(parents=True)
            (src / "etc" / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\n")
            (src / "etc" / "init.d" / "rcS").write_text("#!/bin/sh\n")
            firmware = base / "fw.tar"
            with tarfile.open(firmware, "w") as tf:
                tf.add(src / "etc", arcname="etc")
            out = base / "out"
            with mock.patch.dict(os.environ, {"UNBLOB_COMMAND": REAL_UNBLOB}):
                code, _, stderr = run_main([str(firmware), "--out", str(out)])
            self.assertEqual(code, 0, stderr)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn(manifest["status"], ("complete", "partial"))
            self.assertEqual(manifest["run"]["exit_code"], 0)
            self.assertNotIn("--no-sandbox", manifest["run"]["argv"])
            self.assertEqual(manifest["unblob"]["sha256"], sha256_of(REAL_UNBLOB))
            self.assertTrue(list((out / "extracted").rglob("passwd")))
            self.assertFalse(manifest["input_directory"]["changed"])


class OutputPermissionTests(UnpackTestBase):
    """Extracted trees and surveys name credentials and keys, so their directories are 0700."""

    def test_unpack_output_directory_is_private(self):
        code, _, _ = self.run_stub("ok")
        self.assertEqual(code, 0)
        self.assertEqual(os.stat(self.out).st_mode & 0o777, 0o700)

    def test_survey_output_directory_is_private(self):
        root = self.tmp / "rootfs"
        (root / "etc").mkdir(parents=True)
        (root / "etc" / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\n")
        out = self.tmp / "survey"
        with contextlib.redirect_stdout(io.StringIO()):
            code = survey.main([str(root), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
