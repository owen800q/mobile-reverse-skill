#!/usr/bin/env python3
"""Tests for scripts/ios_container.py: bounded NSKeyedArchiver decoding."""
import plistlib
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import ios_container as ios  # noqa: E402


def keyed_archive(pairs, extra_strings=()):
    """A minimal NSKeyedArchiver-shaped binary plist holding one NS.keys/NS.objects dictionary."""
    objects = ["$null"]
    keys, values = [], []
    for key, value in pairs:
        objects.append(key)
        keys.append(plistlib.UID(len(objects) - 1))
        objects.append(value)
        values.append(plistlib.UID(len(objects) - 1))
    objects.extend(extra_strings)
    objects.append({"NS.keys": keys, "NS.objects": values})
    root = plistlib.UID(len(objects) - 1)
    return plistlib.dumps(
        {"$archiver": "NSKeyedArchiver", "$top": {"root": root},
         "$objects": objects, "$version": 100000},
        fmt=plistlib.FMT_BINARY,
    )


class ArchiveDecodingTests(unittest.TestCase):
    def test_header_map_is_decoded(self):
        blob = keyed_archive([("Content-Type", "application/json"), ("Accept", "*/*")])
        self.assertEqual(ios.archive_headers(blob),
                         {"Content-Type": "application/json", "Accept": "*/*"})

    def test_http_method_token_is_found(self):
        blob = keyed_archive([("Accept", "*/*")], extra_strings=("POST",))
        self.assertEqual(ios.archive_method(blob), "POST")

    def test_malformed_input_returns_empty_results(self):
        self.assertEqual(ios.archive_headers(b"not a plist"), {})
        self.assertIsNone(ios.archive_method(b"not a plist"))

    def test_oversized_blob_is_refused_before_parsing(self):
        blob = b"\x00" * (ios.MAX_ARCHIVE_BYTES + 1)
        with mock.patch.object(ios.plistlib, "loads") as loads:
            self.assertEqual(ios.archive_headers(blob), {})
            self.assertIsNone(ios.archive_method(blob))
        loads.assert_not_called()

    def test_object_count_cap_applies(self):
        blob = keyed_archive([("Accept", "*/*"), ("Host", "example.test")])
        with mock.patch.object(ios, "MAX_ARCHIVE_OBJECTS", 3):
            self.assertEqual(ios.archive_headers(blob), {})
            self.assertIsNone(ios.archive_method(blob))

    def test_pair_cap_limits_each_dictionary(self):
        blob = keyed_archive([("Accept", "*/*"), ("Host", "example.test")])
        with mock.patch.object(ios, "MAX_PAIRS_PER_DICT", 1):
            headers = ios.archive_headers(blob)
        self.assertEqual(headers, {"Accept": "*/*"})


if __name__ == "__main__":
    unittest.main()
