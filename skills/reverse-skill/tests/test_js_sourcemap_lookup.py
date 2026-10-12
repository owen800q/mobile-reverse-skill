#!/usr/bin/env python3
"""Tests for scripts/js_sourcemap_lookup.py: VLQ decoding, bounds and name checks."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import js_sourcemap_lookup as sl  # noqa: E402

GENERATED = "var a = 1;\nreturn a;\n"
ORIGINAL = "let a = 1;\nreturn a;\n"
# Line 1: col 0 -> src 0, orig 0:0, no name; col 4 -> the name "a" at orig 0:4.
# Line 2 has no segments.
GOOD_MAP = {
    "version": 3,
    "sources": ["src/app.ts"],
    "sourcesContent": [ORIGINAL],
    "names": ["a"],
    "mappings": "AAAA,IAAIA;",
}


class VlqTests(unittest.TestCase):
    def test_small_and_negative_values(self):
        self.assertEqual(sl.decode_vlq("A"), [0])
        self.assertEqual(sl.decode_vlq("D"), [-1])
        self.assertEqual(sl.decode_vlq("IAAIA"), [4, 0, 0, 4, 0])

    def test_continuation_digits(self):
        # 16 needs two base64 digits: 32 (continuation) then 1.
        self.assertEqual(sl.decode_vlq("gB"), [16])

    def test_truncated_and_invalid_input_are_refused(self):
        with self.assertRaises(sl.InputError):
            sl.decode_vlq("g")
        with self.assertRaises(sl.InputError):
            sl.decode_vlq("!")


class LookupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.gen = self.dir / "app.js"
        self.gen.write_text(GENERATED, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def write_map(self, data, name="app.js.map"):
        path = self.dir / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def resolve(self, data, line, col):
        return sl.resolve(str(self.gen), self.write_map(data), line, col)

    def test_name_position_resolves_and_both_sides_match(self):
        result, code = self.resolve(GOOD_MAP, 1, 5)
        self.assertEqual(code, 0)
        self.assertTrue(result["resolved"])
        self.assertEqual(result["original"]["source"], "src/app.ts")
        self.assertEqual((result["original"]["line"], result["original"]["column"]), (1, 5))
        self.assertEqual(result["original"]["name"], "a")
        self.assertEqual(result["checks"]["generated_name"], "match")
        self.assertEqual(result["checks"]["original_text"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_position_before_a_named_segment_uses_the_segment_at_or_before(self):
        result, code = self.resolve(GOOD_MAP, 1, 2)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["column"], 1)
        self.assertEqual(result["checks"]["generated_name"], "no_name")

    def test_name_that_does_not_fit_the_generated_text_is_a_mismatch(self):
        wrong = dict(GOOD_MAP, names=["zzz"])
        result, code = self.resolve(wrong, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["generated_name"], "mismatch")
        self.assertEqual(result["checks"]["verdict"], "mismatch")

    def test_position_outside_the_generated_file_is_reported(self):
        result, code = self.resolve(GOOD_MAP, 9, 1)
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"]["generated_position"], "outside_file")

    def test_line_without_a_segment_is_reported(self):
        result, code = self.resolve(GOOD_MAP, 2, 1)
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"]["mapping"], "no_segment")

    def test_original_position_past_the_source_is_a_mismatch(self):
        short = dict(GOOD_MAP, sourcesContent=["x"])
        result, _ = self.resolve(short, 1, 5)
        self.assertEqual(result["checks"]["original_text"], "outside_source")
        self.assertEqual(result["checks"]["verdict"], "mismatch")

    def test_map_without_embedded_sources_is_still_resolved(self):
        bare = {k: v for k, v in GOOD_MAP.items() if k != "sourcesContent"}
        result, code = self.resolve(bare, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["original_text"], "not_embedded")

    def test_non_json_map_is_an_input_error_at_the_cli(self):
        bad = self.dir / "bad.map"
        bad.write_text("not json", encoding="utf-8")
        done = subprocess.run([sys.executable, str(SCRIPTS / "js_sourcemap_lookup.py"),
                               str(self.gen), str(bad), "1", "1"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("not JSON", done.stderr)

    def test_hashes_are_recorded_for_both_files(self):
        result, _ = self.resolve(GOOD_MAP, 1, 5)
        self.assertEqual(len(result["generated"]["sha256"]), 64)
        self.assertEqual(len(result["map"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
