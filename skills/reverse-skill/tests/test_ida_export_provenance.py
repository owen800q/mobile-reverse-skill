#!/usr/bin/env python3
"""Tests for the source-binary provenance check in scripts/ida_export.py.

The IDA calls themselves need a licensed IDA install and are not exercised here;
these tests use a fake namespace that exposes the same retrieve_input_file_* names.
"""
import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import ida_export as ie  # noqa: E402

PAYLOAD = b"\x7fELF fake shared object bytes"


def fake_ns(sha256=None, md5=None):
    nalt = types.SimpleNamespace()
    if sha256 is not None:
        nalt.retrieve_input_file_sha256 = lambda: sha256
    if md5 is not None:
        nalt.retrieve_input_file_md5 = lambda: md5
    return types.SimpleNamespace(ida_nalt=nalt)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.binary = Path(self._tmp.name) / "libfoo.so"
        self.binary.write_bytes(PAYLOAD)
        self.sha = hashlib.sha256(PAYLOAD).hexdigest()
        self.md5 = hashlib.md5(PAYLOAD).hexdigest()

    def tearDown(self):
        self._tmp.cleanup()

    def test_file_digest_matches_hashlib(self):
        self.assertEqual(ie.file_digest(str(self.binary), "sha256"), self.sha)
        self.assertEqual(ie.file_digest(str(self.binary), "md5"), self.md5)

    def test_database_digest_accepts_raw_bytes_and_hex_strings(self):
        self.assertEqual(ie.database_input_digest(fake_ns(sha256=bytes.fromhex(self.sha))),
                         ("sha256", self.sha))
        self.assertEqual(ie.database_input_digest(fake_ns(sha256=self.sha.upper())),
                         ("sha256", self.sha))

    def test_database_digest_falls_back_to_md5_then_gives_up(self):
        self.assertEqual(ie.database_input_digest(fake_ns(md5=bytes.fromhex(self.md5))),
                         ("md5", self.md5))
        self.assertEqual(ie.database_input_digest(fake_ns()), (None, None))
        self.assertEqual(ie.database_input_digest(types.SimpleNamespace()), (None, None))

    def test_all_zero_digest_is_treated_as_absent(self):
        self.assertEqual(ie.database_input_digest(fake_ns(sha256=bytes(32))), (None, None))

    def test_no_source_or_missing_source_is_not_checked(self):
        self.assertEqual(ie.check_source_binary(fake_ns(sha256=bytes.fromhex(self.sha)), None)["status"],
                         "not_checked")
        missing = str(Path(self._tmp.name) / "nope.so")
        self.assertEqual(ie.check_source_binary(fake_ns(sha256=bytes.fromhex(self.sha)), missing)["status"],
                         "not_checked")

    def test_database_without_digest_is_not_checked(self):
        result = ie.check_source_binary(fake_ns(), str(self.binary))
        self.assertEqual(result["status"], "not_checked")

    def test_matching_binary_is_a_match(self):
        result = ie.check_source_binary(fake_ns(sha256=bytes.fromhex(self.sha)), str(self.binary))
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["algorithm"], "sha256")

    def test_different_binary_is_a_mismatch(self):
        other = Path(self._tmp.name) / "other.so"
        other.write_bytes(b"different bytes")
        result = ie.check_source_binary(fake_ns(sha256=bytes.fromhex(self.sha)), str(other))
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["recorded"], self.sha)
        self.assertNotEqual(result["actual"], self.sha)


if __name__ == "__main__":
    unittest.main()
