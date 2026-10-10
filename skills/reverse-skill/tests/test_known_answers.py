#!/usr/bin/env python3
"""Known-answer checks against the pinned real fixtures in tests/fixtures/manifest.json.

Every check here is skipped until `python3 tests/fixtures/fetch_fixtures.py` has put its
fixture in tests/fixtures/_reference/. The answers were established by hand against those
exact bytes (zipfile listing and target_identify.py), so a parser change that moves one
fails here even when the synthetic tests still pass. The Java selector's golden answers
for StringUtils.java live in test_java_method.py.
"""
import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REFERENCE = FIXTURES / "_reference"
sys.path.insert(0, str(HERE.parent / "scripts"))

import target_identify as ti  # noqa: E402

SKIP_HINT = "fixture missing: run python3 tests/fixtures/fetch_fixtures.py"


def pinned(fixture_id):
    with open(FIXTURES / "manifest.json", encoding="utf-8") as f:
        return next(fx for fx in json.load(f)["fixtures"] if fx["id"] == fixture_id)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ApiDemosApkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pin = pinned("apidemos-apk")
        cls.path = REFERENCE / cls.pin["filename"]
        if not cls.path.is_file():
            raise unittest.SkipTest(SKIP_HINT)

    def test_bytes_match_the_pin(self):
        self.assertEqual(self.path.stat().st_size, self.pin["size"])
        self.assertEqual(sha256_of(self.path), self.pin["sha256"])

    def test_archive_has_869_entries_including_dex_manifest_and_resources(self):
        with zipfile.ZipFile(self.path) as archive:
            names = archive.namelist()
        self.assertEqual(len(names), 869)
        for required in ("classes.dex", "AndroidManifest.xml", "resources.arsc"):
            self.assertIn(required, names)

    def test_archive_has_no_native_libraries(self):
        with zipfile.ZipFile(self.path) as archive:
            names = archive.namelist()
        self.assertEqual([n for n in names if n.startswith("lib/") or n.endswith(".so")], [])

    def test_target_identify_routes_it_to_android(self):
        info = ti.identify_file(str(self.path))
        self.assertEqual(info["format"], "android package (apk)")
        self.assertEqual(info["route"], "android")
        self.assertEqual(info["members"], 869)
        self.assertEqual(info["sha256"], self.pin["sha256"])


class CommonsLangStringUtilsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pin = pinned("commons-lang-stringutils")
        cls.path = REFERENCE / cls.pin["filename"]
        if not cls.path.is_file():
            raise unittest.SkipTest(SKIP_HINT)

    def test_bytes_match_the_pin(self):
        self.assertEqual(self.path.stat().st_size, self.pin["size"])
        self.assertEqual(sha256_of(self.path), self.pin["sha256"])


if __name__ == "__main__":
    unittest.main()
