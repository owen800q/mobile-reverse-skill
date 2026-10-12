#!/usr/bin/env python3
"""Tests for scripts/android_strings.py: qualifiers, missing translations, entities,
comments, quotes, translatable status and elements that are not read."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "android_strings.py"
sys.path.insert(0, str(SCRIPT.parent))

import android_strings as au  # noqa: E402

DEFAULT_XML = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Demo</string>
    <string name="login_error">Wrong password &amp; try again</string>
    <string name="api_key" translatable="false">k_live_123</string>
    <string name="only_default">Only in default</string>
</resources>
'''
FR_XML = '''<resources>
    <string name="app_name">Démo</string>
    <string name="login_error">Mot de passe &lt;faux&gt;</string>
    <string name="api_key">ignored</string>
</resources>
'''
NIGHT_XML = '''<resources>
    <string name="app_name">Demo (dark)</string>
</resources>
'''


class StringProjectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "apktool_out"
        for folder, text in (("values", DEFAULT_XML), ("values-fr", FR_XML),
                             ("values-night", NIGHT_XML)):
            d = self.root / "res" / folder
            d.mkdir(parents=True)
            (d / "strings.xml").write_text(text, encoding="utf-8")
        (self.root / "res" / "values-v21").mkdir()  # no strings.xml: must be ignored

    def tearDown(self):
        self._tmp.cleanup()

    def test_qualifiers_are_kept_as_declared(self):
        result = au.project(str(self.root))
        self.assertEqual(result["qualifiers"], ["default", "fr", "night"])
        self.assertEqual(result["string_count"], 4)

    def test_entities_are_decoded_once(self):
        result = au.project(str(self.root), names=["login_error"])
        entry = result["strings"]["login_error"]
        self.assertEqual(entry["default"], "Wrong password & try again")
        self.assertEqual(entry["variants"]["fr"], "Mot de passe <faux>")

    def test_missing_translations_are_listed(self):
        result = au.project(str(self.root), names=["only_default"])
        self.assertEqual(result["strings"]["only_default"]["missing_in"], ["fr", "night"])

    def test_untranslatable_strings_report_no_missing_translations(self):
        result = au.project(str(self.root), names=["api_key"])
        entry = result["strings"]["api_key"]
        self.assertFalse(entry["translatable"])
        self.assertEqual(entry["missing_in"], [])

    def test_search_matches_names_and_values(self):
        by_value = au.project(str(self.root), search="dark")
        self.assertEqual(list(by_value["strings"]), ["app_name"])
        by_name = au.project(str(self.root), search="LOGIN")
        self.assertEqual(list(by_name["strings"]), ["login_error"])

    def test_limit_marks_truncation(self):
        result = au.project(str(self.root), limit=2)
        self.assertEqual(result["shown"], 2)
        self.assertTrue(result["truncated"])

    def test_missing_directory_and_empty_tree_exit_codes(self):
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.root / "nope")],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        with tempfile.TemporaryDirectory() as empty:
            done = subprocess.run([sys.executable, str(SCRIPT), empty], capture_output=True, text=True)
            self.assertEqual(done.returncode, 1)

    def test_cli_emits_json(self):
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.root), "--name", "app_name"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["strings"]["app_name"]["variants"]["night"],
                         "Demo (dark)")


COMMENT_XML = '''<resources>
    <!-- <string name="commented">Hidden</string> -->
    <string name="live">Shown<!-- inline note -->!</string>
    <!--
        <string name="multi">Multi-line hidden</string>
    -->
    <string name="after_comments">After</string>
</resources>
'''

# Four names across four qualifiers. Each name pins one rule of the translatable status.
RULE_FILES = {
    "values": '''<resources>
    <string name="flagged">Default flagged</string>
    <string name='locked' translatable='false'>Locked default</string>
</resources>
''',
    "values-de": '''<resources>
    <string name="nodef_locked_first" translatable="false">Gesperrt</string>
</resources>
''',
    "values-fr": '''<resources>
    <string name="flagged" translatable="false">Drapeau</string>
    <string name="locked">Verrouille</string>
    <string name="nodef_locked_first">Verrouille aussi</string>
    <string name="nodef_open_first">Ouvert</string>
</resources>
''',
    "values-night": '''<resources>
    <string name="nodef_open_first" translatable="false">Ouvert sombre</string>
</resources>
''',
}


def write_tree(root: Path, files: dict) -> None:
    """Write {res folder: strings.xml text} under root/res."""
    for folder, text in files.items():
        d = root / "res" / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / "strings.xml").write_text(text, encoding="utf-8")


class CommentTests(unittest.TestCase):
    def test_single_and_multi_line_comments_are_ignored(self):
        self.assertEqual(sorted(au.parse_strings(COMMENT_XML)), ["after_comments", "live"])

    def test_comment_inside_a_value_is_removed_from_the_value(self):
        self.assertEqual(au.parse_strings(COMMENT_XML)["live"]["value"], "Shown!")

    def test_unterminated_comment_runs_to_end_of_file(self):
        text = '<resources><string name="a">A</string><!-- <string name="b">B</string>'
        self.assertEqual(sorted(au.parse_strings(text)), ["a"])

    def test_commented_strings_are_not_counted_in_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "apktool_out"
            write_tree(root, {"values": COMMENT_XML})
            result = au.project(str(root))
        self.assertEqual(result["string_count"], 2)
        self.assertNotIn("commented", result["strings"])


class QuoteTests(unittest.TestCase):
    def test_single_quotes_work_for_name_and_translatable(self):
        text = ("<resources><string name='sq' translatable='false'>Keep</string>"
                "<string translatable=\"false\" name='rev'>Rev</string>"
                "<string name=\"mixed\" translatable='false'>Mix</string></resources>")
        found = au.parse_strings(text)
        self.assertEqual(found["sq"], {"value": "Keep", "translatable": False})
        self.assertEqual(found["rev"], {"value": "Rev", "translatable": False})
        self.assertEqual(found["mixed"], {"value": "Mix", "translatable": False})

    def test_name_must_close_with_the_quote_that_opened_it(self):
        self.assertEqual(au.parse_strings('<resources><string name="bad\'>X</string></resources>'), {})


class TranslatableStatusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "apktool_out"
        write_tree(self.root, RULE_FILES)

    def tearDown(self):
        self._tmp.cleanup()

    def project_one(self, name):
        return au.project(str(self.root), names=[name])["strings"][name]

    def test_default_declaration_decides_even_when_a_qualifier_says_false(self):
        entry = self.project_one("flagged")
        self.assertTrue(entry["translatable"])
        self.assertEqual(entry["missing_in"], ["de", "night"])

    def test_default_false_with_single_quotes_gives_empty_missing_list(self):
        entry = self.project_one("locked")
        self.assertFalse(entry["translatable"])
        self.assertEqual(entry["missing_in"], [])

    def test_without_default_the_first_declaring_qualifier_decides_false(self):
        entry = self.project_one("nodef_locked_first")
        self.assertIsNone(entry["default"])
        self.assertFalse(entry["translatable"])
        self.assertEqual(entry["missing_in"], [])

    def test_without_default_a_later_false_does_not_override_the_first(self):
        entry = self.project_one("nodef_open_first")
        self.assertTrue(entry["translatable"])
        self.assertEqual(entry["missing_in"], ["de"])


class DuplicateNameTests(unittest.TestCase):
    def test_name_declared_twice_in_one_file_keeps_the_last_declaration(self):
        text = '<resources><string name="d">first</string><string name="d">second</string></resources>'
        self.assertEqual(au.parse_strings(text)["d"]["value"], "second")


class UnreadElementTests(unittest.TestCase):
    PLURALS_XML = ('<resources>'
                   '<plurals name="p"><item quantity="one">%d item</item></plurals>'
                   '<string-array name="arr"><item>one</item></string-array>'
                   '<string name="ref">@string/other</string>'
                   '</resources>')

    def test_plurals_and_string_array_are_not_read(self):
        found = au.parse_strings(self.PLURALS_XML)
        self.assertEqual(sorted(found), ["ref"])
        self.assertEqual(found["ref"]["value"], "@string/other")

    def test_plurals_and_string_array_are_absent_from_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "apktool_out"
            write_tree(root, {"values": self.PLURALS_XML})
            named = au.project(str(root), names=["p", "arr"])
            everything = au.project(str(root))
        self.assertEqual(named["matched"], 0)
        self.assertEqual(named["strings"], {})
        self.assertEqual(everything["string_count"], 1)

    def test_self_closing_string_is_empty_and_does_not_swallow_the_next_element(self):
        text = '<resources><string name="empty"/><string name="x">X value</string></resources>'
        found = au.parse_strings(text)
        self.assertEqual(sorted(found), ["empty", "x"])
        self.assertEqual(found["empty"]["value"], "")
        self.assertEqual(found["x"]["value"], "X value")


if __name__ == "__main__":
    unittest.main()
