#!/usr/bin/env python3
"""Tests for the source-binary provenance check in scripts/ida_export.py.

The IDA calls themselves need a licensed IDA install and are not exercised here;
these tests use a fake namespace that exposes the same retrieve_input_file_* names.
The run_export tests add no-op stand-ins for the other IDA calls, so the flow
from the pre-open check to the export can run without IDA.
"""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

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


def run_ns(sha256=None):
    """Namespace for run_export: the IDA calls do nothing and the database has no functions."""
    nalt = types.SimpleNamespace(get_import_module_qty=lambda: 0)
    if sha256 is not None:
        nalt.retrieve_input_file_sha256 = lambda: sha256
    return types.SimpleNamespace(
        idapro=types.SimpleNamespace(
            open_database=MagicMock(return_value=0),
            close_database=MagicMock(return_value=None),
            auto_wait=MagicMock(return_value=None),
        ),
        ida_nalt=nalt,
        ida_hexrays=types.SimpleNamespace(init_hexrays_plugin=lambda: False),
        idautils=types.SimpleNamespace(
            Functions=lambda: [], Strings=lambda: [], Entries=lambda: []),
    )


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


class RunExportProvenanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.binary = self.root / "libfoo.so"
        self.binary.write_bytes(PAYLOAD)
        self.sha = hashlib.sha256(PAYLOAD).hexdigest()
        self.out = self.root / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def export(self, ns, source=None):
        args = types.SimpleNamespace(target=str(self.binary), out=str(self.out),
                                     source_binary=source, max=0, funcs=None)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = ie.run_export(ns, args)
        return rc, err.getvalue()

    def check_json(self):
        return json.loads((self.out / "source_check.json").read_text(encoding="utf-8"))

    def test_missing_source_binary_exits_2_before_anything_is_written(self):
        missing = self.root / "nope.so"
        ns = run_ns(sha256=bytes.fromhex(self.sha))
        rc, err = self.export(ns, source=str(missing))
        self.assertEqual(rc, 2)
        self.assertIn(f"ERROR: source binary not found: {missing.resolve()}", err)
        ns.idapro.open_database.assert_not_called()
        self.assertFalse(self.out.exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["libfoo.so"])

    def test_source_binary_that_is_a_directory_exits_2(self):
        ns = run_ns(sha256=bytes.fromhex(self.sha))
        rc, _ = self.export(ns, source=str(self.root))
        self.assertEqual(rc, 2)
        ns.idapro.open_database.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_no_source_binary_flag_exports_as_not_checked_without_warning(self):
        ns = run_ns(sha256=bytes.fromhex(self.sha))
        rc, err = self.export(ns, source=None)
        self.assertEqual(rc, 0)
        check = self.check_json()
        self.assertEqual(check["status"], "not_checked")
        self.assertEqual(check["reason"], "no --source-binary given")
        self.assertTrue((self.out / "functions.txt").is_file())
        self.assertNotIn("NOT checked", err)

    def test_database_without_digest_warns_and_continues(self):
        ns = run_ns(sha256=None)
        rc, err = self.export(ns, source=str(self.binary))
        self.assertEqual(rc, 0)
        check = self.check_json()
        self.assertEqual(check["status"], "not_checked")
        self.assertEqual(check["reason"], "database records no input-file digest")
        self.assertIn("[!] WARNING: export is NOT checked against the binary: "
                      "database records no input-file digest.", err)
        self.assertTrue((self.out / "functions.txt").is_file())

    def test_matching_digest_exports_as_match_without_warning(self):
        ns = run_ns(sha256=bytes.fromhex(self.sha))
        rc, err = self.export(ns, source=str(self.binary))
        self.assertEqual(rc, 0)
        self.assertEqual(self.check_json()["status"], "match")
        self.assertNotIn("NOT checked", err)
        self.assertTrue((self.out / "functions.txt").is_file())

    def test_mismatch_stops_before_any_address_file_is_written(self):
        ns = run_ns(sha256=hashlib.sha256(b"a different database").digest())
        rc, _ = self.export(ns, source=str(self.binary))
        self.assertEqual(rc, 1)
        self.assertEqual(self.check_json()["status"], "mismatch")
        for name in ("functions.txt", "strings.txt", "imports.txt", "exports.txt"):
            self.assertFalse((self.out / name).exists(), name)
        self.assertEqual(list((self.out / "decompile").iterdir()), [])

    def test_source_removed_after_precheck_is_recorded_as_not_checked(self):
        source_copy = self.root / "source.so"
        source_copy.write_bytes(PAYLOAD)
        ns = run_ns(sha256=bytes.fromhex(self.sha))

        def remove_source_then_open(*_args, **_kwargs):
            source_copy.unlink()
            return 0

        ns.idapro.open_database.side_effect = remove_source_then_open
        rc, err = self.export(ns, source=str(source_copy))
        self.assertEqual(rc, 0)
        check = self.check_json()
        self.assertEqual(check["status"], "not_checked")
        self.assertTrue(check["reason"].startswith("source binary not found: "))
        self.assertIn("WARNING: export is NOT checked against the binary", err)
        self.assertTrue((self.out / "functions.txt").is_file())

    def test_help_and_docstring_describe_the_check_without_offsets(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            ie.parse_args(["target.so", "--help"])
        help_text = " ".join(out.getvalue().split())
        doc = " ".join(ie.__doc__.split())
        for text in (help_text, doc):
            self.assertIn("before any address is written to the export", text)
            self.assertNotIn("offset", text.lower())
        self.assertIn("exits 2 before the database is opened", help_text)


if __name__ == "__main__":
    unittest.main()
