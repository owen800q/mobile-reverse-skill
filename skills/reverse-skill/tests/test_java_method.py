#!/usr/bin/env python3
"""Tests for scripts/java_method.py: overload refusal, masking, smali, and a real source."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "java_method.py"
FIXTURE = HERE / "fixtures" / "_reference" / "StringUtils.java"
sys.path.insert(0, str(SCRIPT.parent))

import java_method as jm  # noqa: E402

JAVA_SRC = '''package com.example;

// String login(String fake) { return "x"; }
public class Api {
    private static final String LOG = "login(String) {";
    /* login(int x) { } */
    public String login(String user) {
        return helper(user) + "}";
    }
    public String login(String user, int tries) {
        if (tries > 0) {
            return login(user);
        }
        return "";
    }
    public native String sign(String payload);
    public abstract static class Base {
        abstract void login(char c);
    }
    static String helper(String s) {
        return s;
    }
    public void put(java.util.Map<String, Integer> m, final String... keys) {
        m.clear();
    }
    public void ping() {
    }
    public void ping(int x) {
    }
}
'''

SMALI_SRC = '''.class public Lcom/example/Api;
.super Ljava/lang/Object;

.method public login(Ljava/lang/String;)Ljava/lang/String;
    .locals 1
    const-string v0, "a}"
    return-object v0
.end method

.method public login(Ljava/lang/String;I)Ljava/lang/String;
    .locals 1
    const/4 v0, 0x0
    return-object v0
.end method

.method public native sign(Ljava/lang/String;)Ljava/lang/String;
.end method
'''


def line_of(text, needle):
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError("needle not found: %r" % needle)


class JavaSelectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "sources"
        pkg = self.root / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / "Api.java").write_text(JAVA_SRC, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def select(self, method, params=None, cls="com.example.Api", max_lines=400):
        return jm.select(str(self.root), cls, method, params, max_lines)

    def test_overloads_are_refused_without_params(self):
        result, code = self.select("login")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["selected"])
        self.assertIsNone(result["body"])
        self.assertEqual(
            [c["signature"] for c in result["candidates"]],
            ["login(String)", "login(String,int)", "login(char)"],
        )

    def test_comments_literals_and_return_statements_are_not_candidates(self):
        result, _ = self.select("login")
        self.assertEqual(result["candidate_count"], 3)

    def test_one_parameter_overload_is_selected_with_its_full_body(self):
        result, code = self.select("login", "String")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["selected"]["line"], line_of(JAVA_SRC, "login(String user) {"))
        self.assertTrue(result["body"].lstrip().startswith("public String login(String user) {"))
        self.assertTrue(result["body"].endswith("}"))
        self.assertIn('return helper(user) + "}";', result["body"])

    def test_two_parameter_overload_is_selected(self):
        result, code = self.select("login", "String,int")
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["line"], line_of(JAVA_SRC, "login(String user, int tries)"))
        self.assertIn("if (tries > 0)", result["body"])

    def test_abstract_nested_declaration_has_no_body(self):
        result, code = self.select("login", "char")
        self.assertEqual(code, 0)
        self.assertEqual(result["body_status"], "not_available")
        self.assertIsNone(result["body"])
        self.assertIn("abstract void login(char c);", result["declaration"])

    def test_native_declaration_is_not_available_not_empty(self):
        result, code = self.select("sign")
        self.assertEqual(code, 0)
        self.assertEqual(result["body_status"], "not_available")
        self.assertIn("native String sign(String payload);", result["declaration"])

    def test_params_that_match_no_overload_are_reported(self):
        result, code = self.select("login", "long")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "no_match_for_params")
        self.assertEqual(result["candidate_count"], 3)

    def test_empty_params_select_the_no_argument_method(self):
        result, code = self.select("ping", "")
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["signature"], "ping()")

    def test_generic_varargs_and_qualified_types_normalise_to_simple_names(self):
        result, code = self.select("put", "Map,String[]")
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["params"], ["Map", "String[]"])
        result, code = self.select("put", "java.util.Map<String,Integer>,String...")
        self.assertEqual(code, 0)

    def test_missing_method_and_missing_class_are_reported(self):
        result, code = self.select("nosuch")
        self.assertEqual((result["status"], code), ("not_found", 1))
        with self.assertRaises(jm.InputError):
            self.select("login", cls="com.example.Missing")

    def test_body_truncation_is_flagged(self):
        result, code = self.select("login", "String", max_lines=2)
        self.assertEqual(code, 0)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["body"].splitlines()), 2)
        self.assertGreater(result["body_lines"], 2)

    def test_unbalanced_braces_are_an_input_error(self):
        (self.root / "com" / "example" / "Broken.java").write_text(
            "package com.example;\nclass Broken {\n    void go() {\n", encoding="utf-8")
        with self.assertRaises(jm.InputError):
            self.select("go", cls="com.example.Broken")


class SmaliSelectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "smali"
        pkg = self.root / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / "Api.smali").write_text(SMALI_SRC, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_smali_overloads_are_refused_then_selected_by_descriptor_types(self):
        result, code = jm.select(str(self.root), "com.example.Api", "login", None, 400)
        self.assertEqual((result["status"], code), ("ambiguous", 1))
        self.assertEqual(result["source"]["format"], "smali")
        result, code = jm.select(str(self.root), "com.example.Api", "login", "String,int", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["line"], line_of(SMALI_SRC, "login(Ljava/lang/String;I)"))
        self.assertIn("const/4 v0, 0x0", result["body"])

    def test_smali_native_method_has_no_body(self):
        result, code = jm.select(str(self.root), "com.example.Api", "sign", None, 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["body_status"], "not_available")


class RealSourceGoldenTests(unittest.TestCase):
    """Golden values from grep over Apache Commons Lang 3.14.0 StringUtils.java."""

    @classmethod
    def setUpClass(cls):
        if not FIXTURE.is_file():
            raise unittest.SkipTest(
                "fixture missing: run tests/fixtures/fetch_fixtures.py to download StringUtils.java")
        cls._tmp = tempfile.TemporaryDirectory()
        pkg = Path(cls._tmp.name) / "org" / "apache" / "commons" / "lang3"
        pkg.mkdir(parents=True)
        shutil.copy(FIXTURE, pkg / "StringUtils.java")
        cls.root = cls._tmp.name

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_index_of_has_four_overloads_at_known_lines(self):
        result, code = jm.select(self.root, "org.apache.commons.lang3.StringUtils", "indexOf",
                                 None, 400)
        self.assertEqual((result["status"], code), ("ambiguous", 1))
        self.assertEqual([c["line"] for c in result["candidates"]], [2582, 2622, 2666, 2725])

    def test_char_sequence_int_overload_is_selected(self):
        result, code = jm.select(self.root, "org.apache.commons.lang3.StringUtils", "indexOf",
                                 "CharSequence,int", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["line"], 2666)
        self.assertTrue(result["body"].lstrip().startswith(
            "public static int indexOf(final CharSequence seq, final int searchChar) {"))


class CommandLineTests(unittest.TestCase):
    def test_exit_codes_for_ambiguous_and_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "com" / "example"
            pkg.mkdir(parents=True)
            (pkg / "Api.java").write_text(JAVA_SRC, encoding="utf-8")
            ambiguous = subprocess.run(
                [sys.executable, str(SCRIPT), tmp, "com.example.Api", "login"],
                capture_output=True, text=True)
            self.assertEqual(ambiguous.returncode, 1)
            self.assertIn('"status": "ambiguous"', ambiguous.stdout)
            missing = subprocess.run(
                [sys.executable, str(SCRIPT), str(Path(tmp) / "nope"), "com.example.Api", "login"],
                capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
