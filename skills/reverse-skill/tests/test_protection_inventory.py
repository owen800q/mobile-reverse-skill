#!/usr/bin/env python3
"""Tests for scripts/protection_inventory.py: static protection indicators for research."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "protection_inventory.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import protection_inventory as pi  # noqa: E402


def ids(indicators):
    return {(i["id"], i["encoding"]) for i in indicators}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_strong_names_match_exact_case_only(self):
        ind, _ = pi.scan_bytes(b"isdebuggerpresent")
        self.assertFalse([i for i in ind if i["id"] == "win_debugger_api"])
        ind, _ = pi.scan_bytes(b"IsDebuggerPresent")
        self.assertEqual(ids(ind), {("win_debugger_api", "ascii")})

    def test_short_marker_does_not_match_inside_ordinary_words(self):
        # Regression: a case-insensitive "MPRESS" matched inside "compress".
        ind, _ = pi.scan_bytes(b"compress the payload, then decompress it")
        self.assertFalse([i for i in ind if i["category"] == "packer"])

    def test_utf16_names_are_found_with_byte_offsets(self):
        name = "CheckRemoteDebuggerPresent"
        data = b"\x00" * 10 + name.encode("utf-16-le") + b"\x00"
        ind, _ = pi.scan_bytes(data)
        hits = [i for i in ind if i["pattern"] == name]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["encoding"], "utf-16le")
        self.assertEqual(hits[0]["offsets"], [data.index(name.encode("utf-16-le"))])

    def test_weak_terms_ignore_case(self):
        ind, _ = pi.scan_bytes(b"FRIDA-AGENT loaded")
        hit = [i for i in ind if i["id"] == "instrumentation_terms"]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["pattern"], "frida-agent")
        self.assertEqual(hit[0]["strength"], "weak")

    def test_longest_pattern_wins_over_its_prefix(self):
        ind, _ = pi.scan_bytes(b"frida-agent")
        patterns = [i["pattern"] for i in ind]
        self.assertEqual(patterns, ["frida-agent"])

    def test_urls_are_kept_only_with_protection_terms(self):
        _, urls = pi.scan_bytes(b"https://cdn.example.test/logo.png")
        self.assertEqual(urls, [])
        _, urls = pi.scan_bytes(b"https://lic.example.test/activate?x=1")
        self.assertEqual([u["url"] for u in urls], ["https://lic.example.test/activate?x=1"])

    def test_directory_scan_skips_symlinks_and_reports_clean_files(self):
        target = self.write("tree/app.bin", b"IsDebuggerPresent")
        self.write("tree/clean.txt", b"nothing to see")
        os.symlink(target, os.path.join(self.root, "tree", "link.bin"))
        r = subprocess.run([sys.executable, SCRIPT, os.path.join(self.root, "tree")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(report["files_scanned"], 2)
        self.assertEqual(report["files_without_hits"], 1)
        self.assertEqual([f["path"] for f in report["files"]], ["app.bin"])
        self.assertEqual(report["summary"]["anti_debug"]["strong"], 1)

    def test_large_files_are_skipped_and_named(self):
        path = self.write("big.bin", b"IsDebuggerPresent" + b"\x00" * 4096)
        r = subprocess.run([sys.executable, SCRIPT, path, "--max-bytes", "1024"],
                           capture_output=True, text=True)
        report = json.loads(r.stdout)
        self.assertEqual(report["skipped_large"], ["big.bin"])
        self.assertEqual(report["files_scanned"], 0)

    def test_report_states_its_limits(self):
        path = self.write("sample.bin", b"UPX!")
        r = subprocess.run([sys.executable, SCRIPT, path], capture_output=True, text=True)
        report = json.loads(r.stdout)
        self.assertEqual(report["kind"], "file")
        self.assertTrue(any("not that the code runs" in x for x in report["limitations"]))
        self.assertTrue(any("Nothing was executed" in x for x in report["limitations"]))

    def test_missing_path_is_a_usage_error(self):
        r = subprocess.run([sys.executable, SCRIPT, os.path.join(self.root, "nope")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
