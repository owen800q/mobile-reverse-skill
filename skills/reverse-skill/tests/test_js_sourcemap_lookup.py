#!/usr/bin/env python3
"""Tests for scripts/js_sourcemap_lookup.py: VLQ decoding, segment choice, one-field gaps,
column units, the generated and original checks, the verdict, and input errors."""
import json
import subprocess
import sys
import tempfile
import time
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
# Twenty-six letters on line 1, so a one-field gap can sit at generated column 10.
ALPHABET = "abcdefghijklmnopqrstuvwxyz\n"


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


class SegmentTests(unittest.TestCase):
    def test_parse_mappings_yields_one_field_segments_as_gaps(self):
        rows = list(sl.parse_mappings("AAAA,U"))
        self.assertEqual(rows, [(0, 0, 0, 0, 0, None), (0, 10, None, None, None, None)])

    def test_find_segment_uses_the_last_segment_at_or_before_the_column(self):
        self.assertEqual(sl.find_segment("AAAA,IAAIA", 0, 2), (0, 0, 0, 0, None))
        self.assertEqual(sl.find_segment("AAAA,IAAIA", 0, 4), (4, 0, 0, 4, 0))
        self.assertEqual(sl.find_segment("AAAA,IAAIA", 0, 5), (4, 0, 0, 4, 0))

    def test_find_segment_returns_none_for_a_gap_that_is_the_last_segment(self):
        self.assertEqual(sl.find_segment("AAAA,U", 0, 9), (0, 0, 0, 0, None))
        self.assertIsNone(sl.find_segment("AAAA,U", 0, 10))
        self.assertIsNone(sl.find_segment("AAAA,U", 0, 15))

    def test_a_later_segment_ends_a_gap(self):
        self.assertEqual(sl.find_segment("AAAA,U,IAAI", 0, 14), (14, 0, 0, 4, None))

    def test_vlq_value_limit(self):
        self.assertEqual(sl.decode_vlq("g" * 10 + "A"), [0])
        with self.assertRaises(sl.InputError) as ctx:
            sl.decode_vlq("g" * 11 + "A")
        self.assertIn("too large", str(ctx.exception))

    def test_long_run_of_continuation_digits_is_refused_at_once(self):
        started = time.monotonic()
        with self.assertRaises(sl.InputError):
            sl.decode_vlq("w" * 200000)
        self.assertLess(time.monotonic() - started, 1)

    def test_a_position_below_zero_is_refused(self):
        cases = {
            "generated column of a gap": "D",
            "source index": "ADAA",
            "original line": "AADA",
            "original column": "AAAD",
            "name index": "AAAAD",
            "original column reached by a later segment": "AAAA,AAAD",
        }
        for label, mappings in cases.items():
            with self.subTest(label):
                with self.assertRaises(sl.InputError) as ctx:
                    list(sl.parse_mappings(mappings))
                self.assertIn("negative position", str(ctx.exception))

    def test_a_negative_step_that_stays_at_or_above_zero_is_fine(self):
        rows = list(sl.parse_mappings("AAAI,AAAJ"))
        self.assertEqual([(r[1], r[4]) for r in rows], [(0, 4), (0, 0)])


class LookupBase(unittest.TestCase):
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

    def resolve_generated(self, generated, data, line, col):
        self.gen.write_text(generated, encoding="utf-8")
        return self.resolve(data, line, col)

    def run_cli(self, map_path, line="1", col="1"):
        return subprocess.run([sys.executable, str(SCRIPTS / "js_sourcemap_lookup.py"),
                               str(self.gen), map_path, line, col],
                              capture_output=True, text=True)


class LookupTests(LookupBase):
    def test_name_position_resolves_and_both_sides_match(self):
        result, code = self.resolve(GOOD_MAP, 1, 5)
        self.assertEqual(code, 0)
        self.assertTrue(result["resolved"])
        self.assertEqual(result["original"]["source"], "src/app.ts")
        self.assertEqual((result["original"]["line"], result["original"]["column"]), (1, 5))
        self.assertEqual(result["original"]["column_utf16"], 5)
        self.assertEqual(result["original"]["name"], "a")
        self.assertEqual(result["checks"]["generated_name"], "match")
        self.assertEqual(result["checks"]["generated_token"], "a")
        self.assertEqual(result["checks"]["original_text"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_position_before_a_named_segment_uses_the_segment_at_or_before(self):
        result, code = self.resolve(GOOD_MAP, 1, 2)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["column"], 1)
        self.assertEqual(result["checks"]["generated_name"], "no_name")

    def test_last_segment_at_or_before_the_column_is_used(self):
        # Segments at generated columns 0 and 4 (0-based). Column 5 (1-based) is the column-4
        # segment itself, and column 6 comes after it; both use the second segment, not the
        # first, so the original column is 5 (1-based) in each case.
        for col in (5, 6):
            with self.subTest(column=col):
                result, code = self.resolve(GOOD_MAP, 1, col)
                self.assertEqual(code, 0)
                self.assertEqual(result["original"]["segment_generated_column"], 5)
                self.assertEqual(result["original"]["column"], 5)
                self.assertEqual(result["original"]["name"], "a")

    def test_name_that_does_not_fit_the_original_text_is_a_mismatch(self):
        wrong = dict(GOOD_MAP, names=["zzz"])
        result, code = self.resolve(wrong, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["generated_name"], "differs")
        self.assertEqual(result["checks"]["original_text"], "mismatch")
        self.assertEqual(result["checks"]["verdict"], "mismatch")

    def test_minified_name_that_differs_from_generated_text_is_still_consistent(self):
        # The generated text "e" is the minified identifier; the map names the original "a",
        # which the embedded original text has at the same position.
        result, code = self.resolve_generated("var e=1;\n", GOOD_MAP, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["generated_name"], "differs")
        self.assertEqual(result["checks"]["generated_token"], "e")
        self.assertEqual(result["checks"]["original_text"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_generated_name_must_be_the_whole_identifier(self):
        # "abc" is not the name "a". The original-side check is a prefix test, so the original
        # text "a = 1;" still matches; the limitation is recorded in LIMITATIONS.
        result, code = self.resolve_generated("var abc=1;\n", GOOD_MAP, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["generated_token"], "abc")
        self.assertEqual(result["checks"]["generated_name"], "differs")
        self.assertEqual(result["checks"]["original_text"], "match")

    def test_generated_token_is_null_when_no_identifier_is_at_the_segment(self):
        result, code = self.resolve_generated("(a);\n", dict(GOOD_MAP, names=[]), 1, 1)
        self.assertEqual(code, 0)
        self.assertIsNone(result["checks"]["generated_token"])
        self.assertEqual(result["checks"]["generated_name"], "no_name")

    def test_generated_token_is_cut_to_60_characters(self):
        result, code = self.resolve_generated("q" * 70 + "(1);\n", dict(GOOD_MAP, names=[]), 1, 1)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["generated_token"], "q" * 60)

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

    def test_map_without_embedded_sources_is_still_resolved_but_not_checked(self):
        bare = {k: v for k, v in GOOD_MAP.items() if k != "sourcesContent"}
        result, code = self.resolve(bare, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["checks"]["original_text"], "not_embedded")
        self.assertIsNone(result["original"]["column"])
        self.assertEqual(result["original"]["column_utf16"], 5)
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_hashes_are_recorded_for_both_files(self):
        result, _ = self.resolve(GOOD_MAP, 1, 5)
        self.assertEqual(len(result["generated"]["sha256"]), 64)
        self.assertEqual(len(result["map"]["sha256"]), 64)

    def test_astral_character_before_the_original_target_gives_the_code_point_column(self):
        # The original "let 😀a = 1;" has the name 'a' at UTF-16 unit 6 but at code point 5
        # (0-based), because the emoji takes two UTF-16 units.
        original = "let \U0001F600a = 1;\n"
        # "IAAMA": generated column +4, source 0, original line 0, original column +6, name 0.
        astral = dict(GOOD_MAP, sourcesContent=[original], mappings="AAAA,IAAMA;")
        result, code = self.resolve(astral, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["column_utf16"], 7)
        self.assertEqual(result["original"]["column"], 6)
        self.assertEqual(result["checks"]["original_text"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_astral_character_before_the_generated_target_is_counted_in_utf16(self):
        # "😀a=1": the 'a' is at code point 1 (0-based) and UTF-16 unit 2. Column 2 (1-based)
        # is code point 1, which the lookup converts to UTF-16 unit 2 before the search.
        generated = "\U0001F600a=1\n"
        # "EAAAA": generated column +2, source 0, original 0:0, name 0.
        mapped = dict(GOOD_MAP, sourcesContent=["a=1\n"], mappings="AAAA,EAAAA;")
        result, code = self.resolve_generated(generated, mapped, 1, 2)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["segment_generated_column"], 3)
        self.assertEqual(result["checks"]["generated_token"], "a")
        self.assertEqual(result["checks"]["generated_name"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_query_after_a_one_field_gap_has_no_mapping(self):
        # "AAAA" maps column 0; "U" is a one-field gap at generated column 10, with no source.
        gap = dict(GOOD_MAP, mappings="AAAA,U;", names=[])
        result, code = self.resolve_generated(ALPHABET, gap, 1, 16)
        self.assertEqual(code, 1)
        self.assertFalse(result["resolved"])
        self.assertEqual(result["checks"]["mapping"], "no_segment")
        self.assertNotIn("original", result)
        done = self.run_cli(self.write_map(gap), "1", "16")
        self.assertEqual(done.returncode, 1)

    def test_query_at_the_gap_itself_has_no_mapping(self):
        gap = dict(GOOD_MAP, mappings="AAAA,U;", names=[])
        result, code = self.resolve_generated(ALPHABET, gap, 1, 11)
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"]["mapping"], "no_segment")

    def test_query_before_a_gap_still_uses_the_segment_before_it(self):
        gap = dict(GOOD_MAP, mappings="AAAA,U;", names=[])
        result, code = self.resolve_generated(ALPHABET, gap, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["column"], 1)

    def test_segment_after_a_gap_is_found_again(self):
        # "IAAI" is at generated column 14, after the gap, with original column 4 (0-based).
        after = dict(GOOD_MAP, mappings="AAAA,U,IAAI;", names=[])
        result, code = self.resolve_generated(ALPHABET, after, 1, 16)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["segment_generated_column"], 15)
        self.assertEqual(result["original"]["column"], 5)

    def test_non_json_map_is_an_input_error_at_the_cli(self):
        bad = self.dir / "bad.map"
        bad.write_text("not json", encoding="utf-8")
        done = self.run_cli(str(bad))
        self.assertEqual(done.returncode, 2)
        self.assertIn("not JSON", done.stderr)

    def test_non_utf8_generated_file_is_an_input_error(self):
        self.gen.write_bytes(b"var \xff\xfe = 1;\n")
        map_path = self.write_map(GOOD_MAP)
        with self.assertRaises(sl.InputError):
            sl.resolve(str(self.gen), map_path, 1, 1)
        done = self.run_cli(map_path)
        self.assertEqual(done.returncode, 2)
        self.assertIn("not UTF-8", done.stderr)

    def test_non_utf8_map_file_is_an_input_error(self):
        bad = self.dir / "bad-bytes.map"
        bad.write_bytes(b'{"mappings": "AAAA", "x": "\xff"}')
        done = self.run_cli(str(bad))
        self.assertEqual(done.returncode, 2)
        self.assertIn("not UTF-8", done.stderr)

    def test_mappings_that_is_a_number_is_an_input_error(self):
        map_path = self.write_map(dict(GOOD_MAP, mappings=5))
        with self.assertRaises(sl.InputError):
            sl.resolve(str(self.gen), map_path, 1, 1)
        done = self.run_cli(map_path)
        self.assertEqual(done.returncode, 2)
        self.assertIn("'mappings' is not a string", done.stderr)

    def test_other_map_fields_of_the_wrong_type_are_input_errors(self):
        cases = {
            "sourcesContent entry is a number": dict(GOOD_MAP, sourcesContent=[42]),
            "names entry is a number": dict(GOOD_MAP, names=[7]),
            "sources is a string": dict(GOOD_MAP, sources="src/app.ts"),
            "sourcesContent is an object": dict(GOOD_MAP, sourcesContent={"a": "b"}),
        }
        for label, data in cases.items():
            with self.subTest(label):
                done = self.run_cli(self.write_map(data))
                self.assertEqual(done.returncode, 2, done.stderr)

    def test_text_that_is_not_valid_unicode_is_an_input_error(self):
        # json.dumps writes a lone surrogate as an escape, and json.loads reads it back.
        data = dict(GOOD_MAP, sourcesContent=["\ud800 lone"])
        done = self.run_cli(self.write_map(data))
        self.assertEqual(done.returncode, 2)
        self.assertIn("not valid Unicode", done.stderr)

    def test_invalid_vlq_after_the_target_line_is_an_input_error(self):
        done = self.run_cli(self.write_map(dict(GOOD_MAP, mappings="AAAA;!")))
        self.assertEqual(done.returncode, 2)
        self.assertIn("invalid base64 VLQ", done.stderr)

    def test_segment_with_two_fields_is_an_input_error(self):
        done = self.run_cli(self.write_map(dict(GOOD_MAP, mappings="AA")))
        self.assertEqual(done.returncode, 2)
        self.assertIn("2 fields", done.stderr)

    def test_oversized_vlq_and_negative_positions_exit_with_2_not_a_traceback(self):
        bare = {k: v for k, v in GOOD_MAP.items() if k != "sourcesContent"}
        cases = {
            "VLQ value over 55 bits": "AAA" + "w" * 2999 + "AA",
            "position below zero": "AADD",
        }
        for label, mappings in cases.items():
            with self.subTest(label):
                done = self.run_cli(self.write_map(dict(bare, mappings=mappings)))
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertNotIn("Traceback", done.stderr)

    def test_out_of_order_segments_use_the_last_one_in_map_order(self):
        # "QAAA" is generated column 8. "JAAI" then moves back 4, to column 4 (original column 4).
        out_of_order = dict(GOOD_MAP, names=[], mappings="QAAA,JAAI;")
        self.gen.write_text("0123456789abcdef\n", encoding="utf-8")
        only_second_is_before, code = self.resolve(out_of_order, 1, 7)
        self.assertEqual(code, 0)
        self.assertEqual(only_second_is_before["original"]["segment_generated_column"], 5)
        both_are_before, code = self.resolve(out_of_order, 1, 11)
        self.assertEqual(code, 0)
        self.assertEqual(both_are_before["original"]["segment_generated_column"], 5)

    def test_deeply_nested_map_is_an_input_error(self):
        bad = self.dir / "deep.map"
        bad.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
        done = self.run_cli(str(bad))
        self.assertEqual(done.returncode, 2)

    def test_limitations_describe_the_last_segment_rule(self):
        text = " ".join(sl.LIMITATIONS)
        self.assertIn("last", text)
        self.assertNotIn("first", text)

    def test_docstring_states_the_segment_column_and_check_rules(self):
        doc = sl.__doc__
        for term in ("last", "UTF-16", "one-field", "sourcesContent", "not_embedded", "mismatch"):
            self.assertIn(term, doc)
        self.assertNotIn("first matching", doc)


class IndexedAndFramedMapTests(LookupBase):
    """Indexed maps (sections) and maps served with a BOM or the )]}' transport line."""

    def write_raw(self, text):
        path = self.dir / "raw.map"
        path.write_bytes(text.encode("utf-8"))
        return str(path)

    def test_section_offset_shifts_the_first_line_column(self):
        self.gen.write_text("x;var a = 1;\nreturn a;\n", encoding="utf-8")
        indexed = {"version": 3, "sections": [{"offset": {"line": 0, "column": 2}, "map": GOOD_MAP}]}
        result, code = self.resolve(indexed, 1, 7)
        self.assertEqual(code, 0)
        self.assertEqual(result["map"]["section"], "0")
        self.assertEqual(result["original"]["column"], 5)
        self.assertEqual(result["original"]["name"], "a")
        self.assertEqual(result["original"]["segment_generated_column"], 7)
        self.assertEqual(result["checks"]["generated_name"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_position_before_the_first_section_has_no_section(self):
        self.gen.write_text("x;var a = 1;\nreturn a;\n", encoding="utf-8")
        indexed = {"version": 3, "sections": [{"offset": {"line": 0, "column": 2}, "map": GOOD_MAP}]}
        result, code = self.resolve(indexed, 1, 1)
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"]["mapping"], "no_section")

    def test_the_section_that_starts_last_before_the_position_is_used(self):
        second = {"version": 3, "sources": ["b.ts"], "names": [], "mappings": "AAAA"}
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": GOOD_MAP},
            {"offset": {"line": 1, "column": 0}, "map": second},
        ]}
        result, code = self.resolve(indexed, 2, 1)
        self.assertEqual(code, 0)
        self.assertEqual(result["map"]["section"], "1")
        self.assertEqual(result["original"]["source"], "b.ts")
        self.assertTrue(result["map"]["indexed"])

    def test_section_without_an_embedded_map_is_refused_not_fetched(self):
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "url": "https://cdn.example.test/a.map"}]}
        with self.assertRaises(sl.InputError) as ctx:
            self.resolve(indexed, 1, 1)
        self.assertIn("not fetched", str(ctx.exception))

    def test_section_without_a_valid_offset_is_refused(self):
        indexed = {"version": 3, "sections": [{"offset": {"line": -1, "column": 0}, "map": GOOD_MAP}]}
        with self.assertRaises(sl.InputError):
            self.resolve(indexed, 1, 1)

    def test_bom_and_xssi_prefix_are_dropped_before_parsing(self):
        framed = self.write_raw("\ufeff)]}'\n" + json.dumps(GOOD_MAP))
        result, code = sl.resolve(str(self.gen), framed, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["name"], "a")

    def test_prefix_only_map_is_an_input_error(self):
        with self.assertRaises(sl.InputError):
            sl.resolve(str(self.gen), self.write_raw(")]}'"), 1, 1)

    # Indexed maps meet the UTF-16 column rule, the gap rule and the input checks.

    def test_section_offsets_are_utf16_units_after_a_wide_character(self):
        # "😀x;" is 4 UTF-16 units but 3 code points, so the section at unit 4 starts at "var".
        # COLUMN 8 (1-based code points) is the 'a' of "var a", UTF-16 unit 8.
        self.gen.write_text("\U0001F600x;var a = 1;\n", encoding="utf-8")
        indexed = {"version": 3, "sections": [{"offset": {"line": 0, "column": 4}, "map": GOOD_MAP}]}
        result, code = self.resolve(indexed, 1, 8)
        self.assertEqual(code, 0)
        self.assertEqual(result["original"]["name"], "a")
        self.assertEqual(result["original"]["segment_generated_column"], 9)
        self.assertEqual(result["checks"]["generated_name"], "match")
        self.assertEqual(result["checks"]["verdict"], "consistent")

    def test_section_is_chosen_by_the_utf16_column(self):
        # COLUMN 4 is the 'v' of "var", code point 3 but UTF-16 unit 4, where section 1 starts.
        self.gen.write_text("\U0001F600x;var a = 1;\n", encoding="utf-8")
        first = {"version": 3, "sources": ["first.ts"], "names": [], "mappings": "AAAA"}
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": first},
            {"offset": {"line": 0, "column": 4}, "map": GOOD_MAP},
        ]}
        result, code = self.resolve(indexed, 1, 4)
        self.assertEqual(code, 0)
        self.assertEqual(result["map"]["section"], "1")
        self.assertEqual(result["original"]["source"], "src/app.ts")

    def test_section_column_offset_applies_on_its_first_line_only(self):
        self.gen.write_text("x;var a = 1;\nvar a = 2;\n", encoding="utf-8")
        two_lines = dict(GOOD_MAP, sourcesContent=["let a = 1;\nlet a = 2;\n"],
                         mappings="AAAA,IAAIA;AACJ,IAAIA")
        indexed = {"version": 3, "sections": [{"offset": {"line": 0, "column": 2}, "map": two_lines}]}
        first_line, _ = self.resolve(indexed, 1, 7)
        self.assertEqual(first_line["original"]["segment_generated_column"], 7)
        second_line, code = self.resolve(indexed, 2, 5)
        self.assertEqual(code, 0)
        self.assertEqual(second_line["original"]["line"], 2)
        self.assertEqual(second_line["original"]["segment_generated_column"], 5)
        self.assertEqual(second_line["checks"]["generated_name"], "match")
        self.assertEqual(second_line["checks"]["verdict"], "consistent")

    def test_a_gap_inside_a_section_gives_no_mapping(self):
        gap = dict(GOOD_MAP, mappings="AAAA,U;", names=[])
        indexed = {"version": 3, "sections": [{"offset": {"line": 0, "column": 2}, "map": gap}]}
        self.gen.write_text(ALPHABET, encoding="utf-8")
        before, code = self.resolve(indexed, 1, 8)
        self.assertEqual(code, 0)
        self.assertEqual(before["original"]["segment_generated_column"], 3)
        after, code = self.resolve(indexed, 1, 16)
        self.assertEqual(code, 1)
        self.assertEqual(after["checks"]["mapping"], "no_segment")
        self.assertNotIn("original", after)

    def test_only_the_covering_section_is_checked(self):
        broken = dict(GOOD_MAP, mappings="!")
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": GOOD_MAP},
            {"offset": {"line": 1, "column": 0}, "map": broken},
        ]}
        result, code = self.resolve(indexed, 1, 5)
        self.assertEqual(code, 0)
        self.assertEqual(result["map"]["section"], "0")
        with self.assertRaises(sl.InputError) as ctx:
            self.resolve(indexed, 2, 1)
        self.assertIn("invalid base64 VLQ", str(ctx.exception))

    def test_a_field_of_the_wrong_type_inside_the_section_is_an_input_error(self):
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": dict(GOOD_MAP, names=[7])}]}
        with self.assertRaises(sl.InputError):
            self.resolve(indexed, 1, 1)

    def test_section_map_without_mappings_is_an_input_error(self):
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": {"version": 3, "sources": []}}]}
        with self.assertRaises(sl.InputError) as ctx:
            self.resolve(indexed, 1, 1)
        self.assertIn("'mappings'", str(ctx.exception))

    def test_sections_that_is_not_a_list_is_an_input_error(self):
        with self.assertRaises(sl.InputError) as ctx:
            self.resolve({"version": 3, "sections": "nope"}, 1, 1)
        self.assertIn("not a list", str(ctx.exception))

    def test_null_sections_next_to_mappings_is_a_plain_map(self):
        result, code = self.resolve(dict(GOOD_MAP, sections=None), 1, 5)
        self.assertEqual(code, 0)
        self.assertNotIn("indexed", result["map"])

    def test_a_plain_map_is_checked_before_the_position_is(self):
        # The position is outside the file, but the map's own text is invalid, so this is exit 2.
        with self.assertRaises(sl.InputError):
            self.resolve(dict(GOOD_MAP, mappings="AAAA;!"), 9, 1)

    def test_nested_sections_compose_their_offsets(self):
        self.gen.write_text("0123456789\nabcdefghij\n", encoding="utf-8")

        def leaf(source):
            return {"version": 3, "sources": [source], "names": [], "mappings": "AAAA"}

        inner = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": leaf("inner-a.ts")},
            {"offset": {"line": 0, "column": 2}, "map": leaf("inner-b.ts")},
        ]}
        outer = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "map": leaf("outer-a.ts")},
            {"offset": {"line": 1, "column": 3}, "map": inner},
        ]}
        # COLUMN 8 on line 2 is column index 7. The outer section starts at (1, 3), so inside it
        # the second inner section starts at column 3 + 2 = 5 of the same line.
        second, code = self.resolve(outer, 2, 8)
        self.assertEqual(code, 0)
        self.assertEqual(second["map"]["section"], "1-1")
        self.assertEqual(second["original"]["source"], "inner-b.ts")
        self.assertEqual(second["original"]["segment_generated_column"], 6)
        # Column index 4 is before that start, so the first inner section covers it.
        first, code = self.resolve(outer, 2, 5)
        self.assertEqual(code, 0)
        self.assertEqual(first["map"]["section"], "1-0")
        self.assertEqual(first["original"]["source"], "inner-a.ts")
        self.assertEqual(first["original"]["segment_generated_column"], 4)

    def test_section_nesting_is_limited_to_eight_levels(self):
        def nest(levels):
            node = {"version": 3, "sources": ["s.ts"], "names": [], "mappings": "AAAA"}
            for _ in range(levels):
                node = {"version": 3, "sections": [{"offset": {"line": 0, "column": 0}, "map": node}]}
            return node

        result, code = self.resolve(nest(8), 1, 1)
        self.assertEqual(code, 0)
        self.assertEqual(result["map"]["section"], "-".join(["0"] * 8))
        with self.assertRaises(sl.InputError) as ctx:
            self.resolve(nest(9), 1, 1)
        self.assertIn("nested deeper", str(ctx.exception))

    def test_cli_exit_codes_for_an_indexed_map(self):
        before_first = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 2}, "map": GOOD_MAP}]}
        done = self.run_cli(self.write_map(before_first), "1", "1")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(json.loads(done.stdout)["checks"]["mapping"], "no_section")
        by_url = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "url": "https://cdn.example.test/a.map"}]}
        done = self.run_cli(self.write_map(by_url, "url.map"), "1", "1")
        self.assertEqual(done.returncode, 2)
        self.assertIn("not fetched", done.stderr)


if __name__ == "__main__":
    unittest.main()
