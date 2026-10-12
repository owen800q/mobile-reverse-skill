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


DECOMPILE_FAILURE_SRC = '''package com.example;

public class Keys {
    public String broken() {
        throw new UnsupportedOperationException("Method not decompiled: com.example.Keys.broken()");
    }
    public String warned() {
        /* JADX WARN: Code restructure failed */
        return "x";
    }
    public String error() {
        // ERROR: stub from a failed decompile
        return null;
    }
    public String clean() {
        return "ok";
    }
    static {
        KEY = new String[] {"a", "b"};
    }
}
'''

CLINIT_SMALI_SRC = '''.class public Lcom/example/Keys;
.super Ljava/lang/Object;

.method static constructor <clinit>()V
    .locals 1
    const-string v0, "folded"
    sput-object v0, Lcom/example/Keys;->KEY:Ljava/lang/String;
    return-void
.end method

.method public broken()Ljava/lang/String;
    .locals 1
    const-string v0, "from smali"
    return-object v0
.end method
'''

JAVA_WITHOUT_CLINIT = '''package com.example;

public class Keys {
    public String clean() {
        return "ok";
    }
}
'''


class DecompileMarkerAndFallbackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.jadx = base / "sources"
        self.smali = base / "smali"
        (self.jadx / "com" / "example").mkdir(parents=True)
        (self.smali / "com" / "example").mkdir(parents=True)
        (self.jadx / "com" / "example" / "Keys.java").write_text(DECOMPILE_FAILURE_SRC, encoding="utf-8")
        (self.smali / "com" / "example" / "Keys.smali").write_text(CLINIT_SMALI_SRC, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_failure_stub_is_decompile_failed_not_present(self):
        result, code = jm.select(str(self.jadx), "com.example.Keys", "broken", None, 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["body_status"], "decompile_failed")
        self.assertIn("Method not decompiled", result["body_markers"])
        self.assertEqual(result["selected"]["body_status"], "decompile_failed")

    def test_error_prefix_is_a_failure_marker(self):
        result, _ = jm.select(str(self.jadx), "com.example.Keys", "error", None, 400)
        self.assertEqual(result["body_status"], "decompile_failed")
        self.assertIn("// ERROR:", result["body_markers"])

    def test_warning_comment_is_partial(self):
        result, _ = jm.select(str(self.jadx), "com.example.Keys", "warned", None, 400)
        self.assertEqual(result["body_status"], "partial")
        self.assertEqual(result["body_markers"], ["JADX WARN"])

    def test_clean_body_stays_present_with_no_markers(self):
        result, _ = jm.select(str(self.jadx), "com.example.Keys", "clean", None, 400)
        self.assertEqual(result["body_status"], "present")
        self.assertEqual(result["body_markers"], [])
        self.assertIsNone(result["fallback"])

    def test_clinit_without_smali_root_is_a_usage_error(self):
        with self.assertRaises(jm.InputError) as ctx:
            jm.select(str(self.jadx), "com.example.Keys", "<clinit>", None, 400)
        self.assertIn("--smali-root", str(ctx.exception))

    def test_clinit_is_read_from_smali_with_static_initializer_fallback(self):
        result, code = jm.select(str(self.jadx), "com.example.Keys", "<clinit>", None, 400,
                                 smali_root=str(self.smali))
        self.assertEqual(code, 0)
        self.assertEqual(result["source"]["format"], "smali")
        self.assertEqual(result["fallback"], "static_initializer")
        self.assertEqual(result["body_status"], "present")
        self.assertIn("sput-object", result["body"])
        self.assertEqual(result["source"]["path"], "com/example/Keys.smali")

    def test_method_missing_from_java_falls_back_to_smali(self):
        result, code = jm.select(str(self.jadx), "com.example.Keys", "broken", None, 400,
                                 smali_root=str(self.smali))
        # The Java file declares broken(), so it is still the source of record.
        self.assertEqual(result["source"]["format"], "java")
        self.assertIsNone(result["fallback"])

        java_root = Path(self._tmp.name) / "sources_b"
        (java_root / "com" / "example").mkdir(parents=True)
        (java_root / "com" / "example" / "Keys.java").write_text(JAVA_WITHOUT_CLINIT, encoding="utf-8")
        result, code = jm.select(str(java_root), "com.example.Keys", "broken", None, 400,
                                 smali_root=str(self.smali))
        self.assertEqual(code, 0)
        self.assertEqual(result["source"]["format"], "smali")
        self.assertEqual(result["fallback"], "method_not_in_java")
        self.assertEqual(result["body_status"], "present")

    def test_missing_method_without_smali_root_is_still_not_found(self):
        result, code = jm.select(str(self.jadx), "com.example.Keys", "nosuch", None, 400)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["fallback"])

    def test_missing_smali_root_directory_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = subprocess.run(
                [sys.executable, str(SCRIPT), str(self.jadx), "com.example.Keys", "<clinit>",
                 "--smali-root", str(Path(tmp) / "nope")],
                capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2)


NESTED_MESSAGE = (
    "nested classes are not resolved; pass the top-level class and select the method inside it")

CONSTRUCTOR_SRC = '''package com.example;

public class Api {
    private final String user;
    public Api(String user) {
        this.user = user;
    }
    protected Api(int tries, String user) {
        this(user);
    }
    private Api(char c) {
    }
    Api() {
        this("");
    }
    public String login(String user) {
        return user;
    }
}
'''

CALLS_SRC = '''package com.example;

public class Calls {
    public void run(String user) {
        Runnable r = () -> login(user);
        Runnable s = () -> {
            login(user);
        };
        login(user);
    }
    public void login(String user) {
    }
}
'''

CTOR_SMALI_SRC = '''.class public Lcom/example/Api;
.super Ljava/lang/Object;

.method public constructor <init>()V
    .locals 0
    return-void
.end method
'''

OUTER_SRC = '''package com.example;

public class Outer {
    public void run(String s) {
    }
    static class Inner {
        void tick(String s) {
        }
    }
}
'''

GENERIC_SRC = '''package com.example;

public class Generic {
    public void deep(Map<String,Map<String,Map<String,Map>>> m) {
    }
    public void deepest(Map<String,Map<String,Map<String,Map<String,Map>>>> m) {
    }
    public void mixed(Map<String,Map<String,Map<String,Map>>> m, int count) {
    }
    public void bar(List<String> a) {
    }
    public void bar(List<List<List<List<String>>>> a) {
    }
}
'''

MANY_SRC = "package com.example;\n\npublic class Many {\n" + "".join(
    "    public void many(int x%d) {\n    }\n" % i for i in range(101)) + "}\n"

MARKER_SRC = '''package com.example;

public class Marks {
    public String both() {
        // ERROR: stub from a failed decompile
        /* JADX WARN: Code restructure failed */
        return null;
    }
    public String literal() {
        return "Failed to decompile";
    }
    public String warnLiteral() {
        return "JADX WARN is printed by the tool";
    }
}
'''

ANNOTATED_RETURN_SRC = '''package com.example;

public class Ann {
    public @Nullable String foo(int x) {
        return null;
    }
    public String foo(String s) {
        return s;
    }
}
'''

ANNOTATED_PARAM_SRC = '''package com.example;

public class Hidden {
    public void tagged(@Ann(v = f(1)) String s) {
    }
}
'''


def select_java(text, cls, method, params=None, max_lines=400):
    """Write TEXT as the Java file of CLASS in a temporary tree, then select METHOD from it."""
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / (cls.split(".")[-1] + ".java")).write_text(text, encoding="utf-8")
        return jm.select(tmp, cls, method, params, max_lines)


def select_smali(text, cls, method, params=None, max_lines=400):
    """Write TEXT as the smali file of CLASS in a temporary tree, then select METHOD from it."""
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / (cls.split(".")[-1] + ".smali")).write_text(text, encoding="utf-8")
        return jm.select(tmp, cls, method, params, max_lines)


class PackageMatchTests(unittest.TestCase):
    """A file matches only when its directory is the package path, optionally below one container."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_shorter_package_is_not_selected_for_the_file(self):
        self.write("sources/com/example/Api.java", JAVA_SRC)
        with self.assertRaises(jm.InputError) as ctx:
            jm.select(str(self.base / "sources"), "example.Api", "login", None, 400)
        self.assertIn("no Java or smali source for example.Api", str(ctx.exception))

    def test_shorter_package_exits_2_from_the_command_line(self):
        self.write("sources/com/example/Api.java", JAVA_SRC)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.base / "sources"), "example.Api", "login"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def test_sources_directory_is_a_container(self):
        self.write("sources/com/example/Api.java", JAVA_SRC)
        result, code = jm.select(str(self.base), "com.example.Api", "ping", "", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["source"]["path"], "sources/com/example/Api.java")

    def test_secondary_dex_directory_is_a_container(self):
        self.write("smali_classes2/com/example/Api.smali", SMALI_SRC)
        result, code = jm.select(str(self.base), "com.example.Api", "sign", None, 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["source"],
                         {"path": "smali_classes2/com/example/Api.smali", "format": "smali"})

    def test_other_directories_are_not_containers(self):
        cases = {
            "classes/com/example/Api.java": JAVA_SRC,
            "smali_classes/com/example/Api.smali": SMALI_SRC,
            "sources/smali/com/example/Api.java": JAVA_SRC,
            "com/example/extra/Api.java": JAVA_SRC,
        }
        for rel, text in cases.items():
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / rel
                path.parent.mkdir(parents=True)
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(jm.InputError):
                    jm.select(tmp, "com.example.Api", "login", None, 400)

    def test_two_java_files_for_the_class_are_refused(self):
        self.write("com/example/Api.java", JAVA_SRC)
        self.write("sources/com/example/Api.java", JAVA_SRC)
        with self.assertRaises(jm.InputError) as ctx:
            jm.select(str(self.base), "com.example.Api", "login", None, 400)
        self.assertIn("several java files declare Api", str(ctx.exception))


class ConstructorTests(unittest.TestCase):
    def test_constructors_are_not_candidates_for_a_method_named_like_the_class(self):
        result, code = select_java(CONSTRUCTOR_SRC, "com.example.Api", "Api")
        self.assertEqual((result["status"], code), ("not_found", 1))
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["candidates"], [])

    def test_a_real_method_beside_the_constructors_is_still_selected(self):
        result, code = select_java(CONSTRUCTOR_SRC, "com.example.Api", "login", "String")
        self.assertEqual(code, 0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["selected"]["return_type"], "String")

    def test_each_modifier_word_read_as_a_return_type_is_a_constructor(self):
        for word in sorted(jm.MODIFIER_WORDS):
            with self.subTest(modifier=word):
                text = "class Api {\n    %s Api(int x) {\n    }\n}\n" % word
                self.assertEqual(jm.java_candidates(text, "Api"), [])

    def test_declaration_with_no_return_type_is_never_a_candidate(self):
        for decl in ("    Api(int x) {\n    }\n", "    Api(int x);\n", "    Api() {\n    }\n"):
            with self.subTest(decl=decl):
                self.assertEqual(jm.java_candidates("class Api {\n" + decl + "}\n", "Api"), [])


class DeclarationShapeTests(unittest.TestCase):
    def test_calls_in_lambdas_and_statements_are_not_declarations(self):
        result, code = select_java(CALLS_SRC, "com.example.Calls", "login")
        self.assertEqual(code, 0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["line"],
                         line_of(CALLS_SRC, "public void login(String user)"))

    def test_annotation_between_modifier_and_return_type_is_a_candidate(self):
        # Both overloads must be seen: a bare name is ambiguous, not silently the String one.
        result, code = select_java(ANNOTATED_RETURN_SRC, "com.example.Ann", "foo")
        self.assertEqual((result["status"], code), ("ambiguous", 1))
        self.assertEqual(result["candidate_count"], 2)
        result, code = select_java(ANNOTATED_RETURN_SRC, "com.example.Ann", "foo", "int")
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["signature"], "foo(int)")

    def test_parameter_annotation_with_a_call_does_not_hide_the_declaration(self):
        result, code = select_java(ANNOTATED_PARAM_SRC, "com.example.Hidden", "tagged")
        self.assertEqual(code, 0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["selected"]["signature"], "tagged(String)")

    def test_smali_constructor_is_selected_by_its_name_documented_limitation(self):
        result, code = select_smali(CTOR_SMALI_SRC, "com.example.Api", "<init>")
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["signature"], "<init>()")


class NestedClassTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "sources"
        pkg = self.root / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / "Outer.java").write_text(OUTER_SRC, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_nested_class_name_is_refused_with_the_nested_message(self):
        with self.assertRaises(jm.InputError) as ctx:
            jm.select(str(self.root), "com.example.Outer.Inner", "tick", "String", 400)
        self.assertEqual(str(ctx.exception), NESTED_MESSAGE)

    def test_nested_class_request_exits_2_with_the_message_on_stderr(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root), "com.example.Outer.Inner", "tick",
             "--params", "String"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("ERROR: " + NESTED_MESSAGE, proc.stderr)

    def test_nested_name_is_refused_before_the_clinit_usage_check(self):
        with self.assertRaises(jm.InputError) as ctx:
            jm.select(str(self.root), "com.example.Outer.Inner", "<clinit>", None, 400)
        self.assertEqual(str(ctx.exception), NESTED_MESSAGE)

    def test_top_level_name_can_return_a_nested_declaration_documented_limitation(self):
        result, code = jm.select(str(self.root), "com.example.Outer", "tick", "String", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["line"], line_of(OUTER_SRC, "void tick(String s)"))
        self.assertIn("void tick(String s)", result["body"])

    def test_dollar_name_is_looked_up_as_a_file_name(self):
        result, code = select_smali(SMALI_SRC, "com.example.Outer$Inner", "sign")
        self.assertEqual(code, 0)
        self.assertEqual(result["source"],
                         {"path": "com/example/Outer$Inner.smali", "format": "smali"})


class GenericDepthTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        pkg = self.root / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / "Generic.java").write_text(GENERIC_SRC, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_type_arguments_reduce_to_the_raw_type_at_any_depth(self):
        self.assertEqual(jm.simple_type("Map<String,Map<String,Map<String,Map>>>"), "Map")
        self.assertEqual(jm.simple_type("Map<String,Map<String,Map<String,Map<String,Map>>>>"), "Map")
        self.assertEqual(jm.simple_type("java.util.List<java.util.List<String>>[]"), "List[]")

    def test_three_level_parameter_is_selected_by_its_simple_name(self):
        result, code = jm.select(str(self.root), "com.example.Generic", "deep", "Map", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["params"], ["Map"])
        self.assertEqual(result["selected"]["line"], line_of(GENERIC_SRC, "public void deep("))

    def test_four_level_type_arguments_are_reduced_fully_for_selection(self):
        result, code = jm.select(str(self.root), "com.example.Generic", "deepest", "Map", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["params"], ["Map"])
        self.assertEqual(result["selected"]["line"], line_of(GENERIC_SRC, "public void deepest("))

    def test_four_level_parameter_beside_a_second_parameter_is_selected(self):
        result, code = jm.select(str(self.root), "com.example.Generic", "mixed", "Map,int", 400)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected"]["params"], ["Map", "int"])

    def test_overloads_differing_only_by_type_arguments_are_ambiguous(self):
        result, code = jm.select(str(self.root), "com.example.Generic", "bar", None, 400)
        self.assertEqual((result["status"], code), ("ambiguous", 1))
        self.assertEqual([c["params"] for c in result["candidates"]], [["List"], ["List"]])


class CandidateCapTests(unittest.TestCase):
    def test_candidate_list_is_capped_and_candidate_count_is_the_total(self):
        result, code = select_java(MANY_SRC, "com.example.Many", "many")
        self.assertEqual((result["status"], code), ("ambiguous", 1))
        self.assertEqual(result["candidate_count"], 101)
        self.assertEqual(len(result["candidates"]), 100)


class MarkerPrecedenceTests(unittest.TestCase):
    def test_failure_and_warning_markers_together_report_decompile_failed(self):
        result, code = select_java(MARKER_SRC, "com.example.Marks", "both")
        self.assertEqual(code, 0)
        self.assertEqual(result["body_status"], "decompile_failed")
        self.assertEqual(result["body_markers"], ["// ERROR:", "JADX WARN"])
        self.assertEqual(result["selected"]["body_status"], "decompile_failed")

    def test_body_status_for_orders_failure_markers_before_warning_markers(self):
        self.assertEqual(jm.body_status_for("/* JADX WARN */ // ERROR:", "java"),
                         ("decompile_failed", ["// ERROR:", "JADX WARN"]))
        self.assertEqual(jm.body_status_for("/* JADX WARN */", "java"), ("partial", ["JADX WARN"]))
        self.assertEqual(jm.body_status_for("// ERROR:", "smali"), (None, []))

    def test_string_literal_with_a_failure_text_is_decompile_failed_documented_limitation(self):
        result, _ = select_java(MARKER_SRC, "com.example.Marks", "literal")
        self.assertEqual(result["body_status"], "decompile_failed")
        self.assertEqual(result["body_markers"], ["Failed to decompile"])

    def test_string_literal_with_the_warning_text_is_partial_documented_limitation(self):
        result, _ = select_java(MARKER_SRC, "com.example.Marks", "warnLiteral")
        self.assertEqual(result["body_status"], "partial")
        self.assertEqual(result["body_markers"], ["JADX WARN"])


class GeneratedHelpTests(unittest.TestCase):
    def test_help_names_the_statuses_and_the_nested_class_rule(self):
        text = jm.build_parser().format_help()
        self.assertIn("ambiguous", text)
        self.assertIn("no_match_for_params", text)
        self.assertIn("nested", text)


if __name__ == "__main__":
    unittest.main()
