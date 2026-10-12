#!/usr/bin/env python3
"""Tests for scripts/android_strings.py: qualifiers, missing translations, entities."""
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


if __name__ == "__main__":
    unittest.main()
