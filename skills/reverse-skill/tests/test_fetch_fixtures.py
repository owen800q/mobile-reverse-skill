#!/usr/bin/env python3
"""Tests for tests/fixtures/fetch_fixtures.py: pin checks, atomic fetch, no clobbering.

Nothing here touches the network. Downloads go through an injected opener, and the
main() paths patch urlopen so that any unexpected fetch fails the test.
"""
import contextlib
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "fixtures"))

import fetch_fixtures as ff  # noqa: E402

PAYLOAD = b"pinned fixture bytes\n"
PIN = {
    "id": "sample",
    "filename": "sample.bin",
    "url": "https://example.test/sample.bin",
    "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
    "size": len(PAYLOAD),
}


def opener_returning(data):
    def opener(url, timeout=None):
        return io.BytesIO(data)
    return opener


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return ff.main(argv)


def write_manifest(directory, fixtures):
    path = Path(directory) / "manifest.json"
    path.write_text(json.dumps({"fixtures": fixtures}), encoding="utf-8")
    return str(path)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_checked_in_manifest_pins_both_fixtures(self):
        ids = [fx["id"] for fx in ff.load_manifest(ff.MANIFEST)]
        self.assertEqual(ids, ["apidemos-apk", "commons-lang-stringutils"])

    def test_refuses_http_path_names_and_malformed_pins(self):
        bad = (
            {**PIN, "url": "http://example.test/sample.bin"},
            {**PIN, "filename": "../escape.bin"},
            {**PIN, "filename": "."},
            {**PIN, "sha256": "ABC"},
            {**PIN, "sha256": "F" * 64},
            {**PIN, "size": 0},
        )
        for fx in bad:
            with self.subTest(fx=fx):
                with self.assertRaises(ValueError):
                    ff.load_manifest(write_manifest(self.dir, [fx]))

    def test_duplicate_ids_are_refused(self):
        with self.assertRaises(ValueError):
            ff.load_manifest(write_manifest(self.dir, [PIN, dict(PIN, filename="other.bin")]))

    def test_malformed_manifest_shapes_are_usage_errors(self):
        path = self.dir / "manifest.json"
        for body in ("[]", '{"fixtures": ["not an object"]}'):
            with self.subTest(body=body):
                path.write_text(body, encoding="utf-8")
                self.assertEqual(quiet_main(["--manifest", str(path), "--dest", str(self.dir)]), 2)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.final = self.dir / PIN["filename"]

    def tearDown(self):
        self._tmp.cleanup()

    def leftovers(self):
        return sorted(p.name for p in self.dir.iterdir() if p.name.startswith(".partial-"))

    def test_verified_download_is_renamed_into_place_with_mode_0644(self):
        path = ff.fetch(PIN, str(self.dir), opener=opener_returning(PAYLOAD))
        self.assertEqual(Path(path).read_bytes(), PAYLOAD)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644)
        self.assertEqual(self.leftovers(), [])

    def test_wrong_hash_is_never_renamed_into_place(self):
        with self.assertRaises(ValueError) as cm:
            ff.fetch(PIN, str(self.dir), opener=opener_returning(b"X" * PIN["size"]))
        self.assertIn("does not match the pin", str(cm.exception))
        self.assertFalse(self.final.exists())
        self.assertEqual(self.leftovers(), [])

    def test_short_download_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            ff.fetch(PIN, str(self.dir), opener=opener_returning(b"short"))
        self.assertIn("pinned", str(cm.exception))
        self.assertFalse(self.final.exists())
        self.assertEqual(self.leftovers(), [])

    def test_oversized_stream_is_cut_off_before_it_is_written_out(self):
        with self.assertRaises(ValueError) as cm:
            ff.fetch(PIN, str(self.dir), opener=opener_returning(PAYLOAD + b"more bytes"))
        self.assertIn("more than the pinned", str(cm.exception))
        self.assertFalse(self.final.exists())
        self.assertEqual(self.leftovers(), [])

    def test_existing_matching_file_is_not_fetched_again(self):
        self.final.write_bytes(PAYLOAD)
        manifest = write_manifest(self.dir, [PIN])
        with mock.patch.object(ff.urllib.request, "urlopen",
                               side_effect=AssertionError("network used")):
            status = quiet_main(["--manifest", manifest, "--dest", str(self.dir)])
        self.assertEqual(status, 0)
        self.assertEqual(self.final.read_bytes(), PAYLOAD)

    def test_mismatched_existing_file_is_refused_and_kept(self):
        self.final.write_bytes(b"someone else's file")
        manifest = write_manifest(self.dir, [PIN])
        with mock.patch.object(ff.urllib.request, "urlopen",
                               side_effect=AssertionError("network used")):
            status = quiet_main(["--manifest", manifest, "--dest", str(self.dir)])
        self.assertEqual(status, 1)
        self.assertEqual(self.final.read_bytes(), b"someone else's file")

    def test_symlink_at_destination_is_refused_and_not_followed(self):
        target = self.dir / "elsewhere.bin"
        target.write_bytes(PAYLOAD)
        os.symlink(str(target), str(self.final))
        manifest = write_manifest(self.dir, [PIN])
        with mock.patch.object(ff.urllib.request, "urlopen",
                               side_effect=AssertionError("network used")):
            status = quiet_main(["--manifest", manifest, "--dest", str(self.dir)])
        self.assertEqual(status, 1)
        self.assertTrue(os.path.islink(str(self.final)))
        self.assertEqual(target.read_bytes(), PAYLOAD)

    def test_unknown_only_id_is_a_usage_error(self):
        manifest = write_manifest(self.dir, [PIN])
        status = quiet_main(["--manifest", manifest, "--dest", str(self.dir), "--only", "nope"])
        self.assertEqual(status, 2)
        self.assertFalse(self.final.exists())


if __name__ == "__main__":
    unittest.main()
