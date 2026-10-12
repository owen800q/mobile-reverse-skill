#!/usr/bin/env python3
"""Tests for scripts/redact_literals.py and its wiring into har_parse.py."""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import redact_literals as rl  # noqa: E402

TOKEN = "s3cr3t-token-value"
# Standard base64 of this 15-byte literal contains + and /, and URL-safe base64 contains
# - and _, in the groups that the byte-offset forms keep, so the URL-encoded cases are real.
OFFSET_LITERAL = "s3cr3t>>??~~val"


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "redact_literals.py"), *args],
                          capture_output=True, text=True)


class RedactionTests(unittest.TestCase):
    def test_variants_cover_raw_url_encoded_and_base64_forms(self):
        literal = "a b&c=d/e"
        forms = rl.variants(literal)
        self.assertIn(literal, forms)
        self.assertIn(urllib.parse.quote(literal, safe=""), forms)
        self.assertIn(urllib.parse.quote_plus(literal), forms)
        self.assertIn(base64.b64encode(literal.encode()).decode(), forms)
        self.assertEqual(forms, sorted(forms, key=len, reverse=True))

    def test_redact_text_counts_every_form(self):
        text = "raw %s, query %s, body %s" % (
            TOKEN, urllib.parse.quote(TOKEN, safe=""),
            base64.b64encode(TOKEN.encode()).decode())
        out, count = rl.redact_text(text, [TOKEN])
        self.assertNotIn(TOKEN, out)
        self.assertEqual(count, 3)
        self.assertEqual(out.count(rl.REDACTED), 3)

    def test_short_literal_is_refused(self):
        with self.assertRaises(rl.LiteralError):
            rl.load_literals(["abc"], None)

    def test_literal_file_skips_comments_blanks_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lits.txt"
            path.write_text("# session token\n%s\n\n%s\n" % (TOKEN, TOKEN), encoding="utf-8")
            self.assertEqual(rl.load_literals([], str(path)), [TOKEN])

    def test_tree_pass_rewrites_text_and_skips_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "requests.json").write_text('{"token": "%s"}' % TOKEN, encoding="utf-8")
            (root / "sub" / "note.txt").write_text("leak %s" % TOKEN, encoding="utf-8")
            (root / "blob.bin").write_bytes(b"\x00\x01" + TOKEN.encode())
            summary = rl.redact_tree(str(root), [TOKEN])
            self.assertNotIn(TOKEN, (root / "requests.json").read_text(encoding="utf-8"))
            self.assertNotIn(TOKEN, (root / "sub" / "note.txt").read_text(encoding="utf-8"))
            self.assertIn(TOKEN.encode(), (root / "blob.bin").read_bytes())
            self.assertEqual(summary["files_redacted"], 2)
            self.assertEqual(summary["replacements"], 2)
            self.assertEqual(summary["skipped"], [{"path": "blob.bin", "reason": "binary"}])

    def test_standalone_cli_needs_a_literal_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = run_cli(tmp)
            self.assertEqual(done.returncode, 2)

    def test_shorter_literal_inside_longer_one_does_not_break_it(self):
        text = "token=secretpassword&x=1"
        for literals in (["secret", "secretpassword"], ["secretpassword", "secret"]):
            with self.subTest(literals=literals):
                out, count = rl.redact_text(text, literals)
                self.assertEqual(out, "token=[REDACTED]&x=1")
                self.assertEqual(count, 1)

    def test_crlf_line_endings_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_bytes(("a: 1\r\nkey=" + TOKEN + "\r\n").encode("utf-8"))
            rl.redact_tree(tmp, [TOKEN])
            self.assertEqual(path.read_bytes(), b"a: 1\r\nkey=[REDACTED]\r\n")

    def test_unreadable_directory_ends_the_walk_with_an_error(self):
        def walk_with_failure(top, followlinks=False, onerror=None):
            onerror(PermissionError(13, "Permission denied", top))
            return iter(())

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(rl.os, "walk", walk_with_failure):
                with self.assertRaises(PermissionError):
                    rl.redact_tree(tmp, [TOKEN])


class ParserWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.har = self.base / "capture.har"
        self.har.write_text(json.dumps(har_with_token()), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_har(self, out, *extra):
        return subprocess.run([sys.executable, str(SCRIPTS / "har_parse.py"), str(self.har),
                               "--out", str(out), *extra], capture_output=True, text=True)

    def test_short_literal_is_refused_before_any_output_is_written(self):
        out = self.base / "out"
        done = self.run_har(out, "--literal", "abc")
        self.assertEqual(done.returncode, 2)
        self.assertFalse(out.exists())

    def test_declared_literal_never_reaches_har_output(self):
        out = self.base / "out"
        done = self.run_har(out, "--redact", "--literal", TOKEN)
        self.assertIn("Literal redaction", done.stderr)
        for path in out.rglob("*"):
            if path.is_file():
                self.assertNotIn(TOKEN, path.read_text(encoding="utf-8", errors="replace"), path)

    def test_without_literal_flags_output_is_unchanged(self):
        out = self.base / "plain"
        done = self.run_har(out)
        self.assertNotIn("Literal redaction", done.stderr)
        self.assertTrue(any(TOKEN in p.read_text(encoding="utf-8", errors="replace")
                            for p in out.rglob("*") if p.is_file()))


def har_with_token():
    return {
        "log": {"version": "1.2", "creator": {"name": "t", "version": "1"}, "entries": [{
            "startedDateTime": "2026-01-01T00:00:00.000Z", "time": 1,
            "request": {"method": "POST", "url": "https://api.example.test/v1/login",
                        "httpVersion": "HTTP/1.1", "headers": [], "queryString": [],
                        "cookies": [], "headersSize": -1, "bodySize": 0},
            "response": {"status": 200, "statusText": "OK", "httpVersion": "HTTP/1.1",
                         "headers": [], "cookies": [], "headersSize": -1, "bodySize": -1,
                         "content": {"size": 0, "mimeType": "text/plain",
                                     "text": "token=%s" % TOKEN}},
            "cache": {}, "timings": {"send": 0, "wait": 0, "receive": 0},
        }]},
    }


class EncodedFormTests(unittest.TestCase):
    """Forms that real captures contain and that an earlier version did not cover."""

    def test_variants_include_json_escaped_and_nested_forms(self):
        lit = 'pa"ss-word-9'
        forms = rl.variants(lit)
        self.assertIn('pa\\"ss-word-9', forms)               # one JSON escape
        self.assertIn('pa\\\\\\"ss-word-9', forms)          # escaped again, as in JSON-in-JSON

    def test_variants_include_base64url_and_hex(self):
        lit = "??>>token~~value"
        self.assertIn(base64.urlsafe_b64encode(lit.encode()).decode(), rl.variants(lit))
        self.assertIn(lit.encode().hex(), rl.variants(lit))
        self.assertIn(lit.encode().hex().upper(), rl.variants(lit))

    def test_variants_include_url_encoded_base64(self):
        for lit in (OFFSET_LITERAL, "pa>>ss?word~9"):
            with self.subTest(literal=lit):
                forms = rl.variants(lit)
                standard = base64.b64encode(lit.encode()).decode()
                urlsafe = base64.urlsafe_b64encode(lit.encode()).decode()
                self.assertIn(urllib.parse.quote(standard, safe=""), forms)
                self.assertIn(urllib.parse.quote(urlsafe, safe=""), forms)

    def test_non_ascii_is_matched_in_both_json_escaping_modes(self):
        lit = "pässwörd-密码-42"
        for ensure_ascii in (True, False):
            text = json.dumps({"v": lit}, ensure_ascii=ensure_ascii)
            out, count = rl.redact_text(text, [lit])
            self.assertGreaterEqual(count, 1, ensure_ascii)
            # Redacting inside the string keeps the JSON valid, and the value becomes the marker.
            self.assertEqual(json.loads(out)["v"], rl.REDACTED, ensure_ascii)

    def test_nested_json_file_has_no_secret_left(self):
        lit = 'pa"ss-word-9'
        body = json.dumps({"password_hint": lit})            # a JSON body...
        record = json.dumps({"body": body}, indent=2)        # ...stored inside a JSON record
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.json"
            path.write_text(record, encoding="utf-8")
            rl.redact_tree(tmp, [lit])
            self.assertNotIn("ss-word-9", path.read_text(encoding="utf-8"))


class Base64OffsetTests(unittest.TestCase):
    """The literal can start at byte offset 0, 1 or 2 of a 3-byte group (see variants)."""

    def test_literal_base64_has_plus_slash_and_minus_underscore(self):
        standard = base64.b64encode(OFFSET_LITERAL.encode()).decode()
        urlsafe = base64.urlsafe_b64encode(OFFSET_LITERAL.encode()).decode()
        self.assertTrue({"+", "/"} <= set(standard))
        self.assertTrue({"-", "_"} <= set(urlsafe))

    def test_a_form_is_found_at_every_prefix_and_suffix_length(self):
        forms = rl.variants(OFFSET_LITERAL)
        literal = OFFSET_LITERAL.encode("utf-8")
        for prefix_len in range(6):
            for suffix_len in range(6):
                body = bytes(range(prefix_len)) + literal + bytes(range(200, 200 + suffix_len))
                for encode in (base64.b64encode, base64.urlsafe_b64encode):
                    with self.subTest(prefix=prefix_len, suffix=suffix_len,
                                      alphabet=encode.__name__):
                        encoded = encode(body).decode("ascii")
                        found = [form for form in forms if form in encoded]
                        self.assertTrue(found)
                        out, count = rl.redact_text(encoded, [OFFSET_LITERAL])
                        self.assertGreaterEqual(count, 1)
                        for form in found:
                            self.assertNotIn(form, out)

    def test_plus_and_slash_base64_is_found_url_encoded(self):
        forms = rl.variants(OFFSET_LITERAL)
        literal = OFFSET_LITERAL.encode("utf-8")
        url_encoded_match = False
        for prefix_len in range(6):
            for suffix_len in range(6):
                body = bytes(range(prefix_len)) + literal + bytes(range(200, 200 + suffix_len))
                encoded = base64.b64encode(body).decode("ascii")
                text = "token=" + urllib.parse.quote(encoded, safe="")
                with self.subTest(prefix=prefix_len, suffix=suffix_len):
                    matches = [form for form in forms if form in text]
                    self.assertTrue(matches)
                    url_encoded_match = url_encoded_match or any(
                        "%2B" in form or "%2F" in form for form in matches)
                    out, count = rl.redact_text(text, [OFFSET_LITERAL])
                    self.assertGreaterEqual(count, 1)
                    for form in matches:
                        self.assertNotIn(form, out)
        self.assertTrue(url_encoded_match)


class LiteralValidityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_non_utf8_literal_file_raises(self):
        path = self.base / "lits.bin"
        path.write_bytes(b"hunter2hunter2\n\xff\xfe\n")
        with self.assertRaises(rl.LiteralError):
            rl.load_literals([], str(path))

    def test_lone_surrogate_literal_raises(self):
        bad = "abcdef\udcff"  # what Python gives for a raw 0xff byte on the command line
        with self.assertRaises(rl.LiteralError):
            rl.load_literals([bad], None)
        with self.assertRaises(rl.LiteralError):
            rl.resolve_literal_args(argparse.Namespace(literal=[bad], literal_file=None))
        with self.assertRaises(rl.LiteralError):
            rl.variants(bad)

    def test_comment_only_literal_file_raises(self):
        path = self.base / "lits.txt"
        path.write_text("# nothing here\n\n   \n# still nothing\n", encoding="utf-8")
        with self.assertRaisesRegex(rl.LiteralError, "no literals in"):
            rl.load_literals([], str(path))

    def test_utf8_byte_order_mark_is_not_part_of_the_first_literal(self):
        path = self.base / "lits.txt"
        path.write_bytes(b"\xef\xbb\xbf" + TOKEN.encode("utf-8") + b"\n")
        self.assertEqual(rl.load_literals([], str(path)), [TOKEN])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.out = self.base / "out"
        self.out.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_cli_exits_2_for_each_bad_literal_and_writes_nothing(self):
        (self.out / "a.txt").write_text("pw=hunter2hunter2", encoding="utf-8")
        non_utf8 = self.base / "bad.txt"
        non_utf8.write_bytes(b"hunter2hunter2\n\xff\xfe\n")
        comments = self.base / "comments.txt"
        comments.write_text("# only a comment\n\n   \n", encoding="utf-8")
        cases = [
            ("short literal", ["--literal", "abc"]),
            ("non-UTF-8 literal file", ["--literal-file", str(non_utf8)]),
            ("literal file with no literals", ["--literal-file", str(comments)]),
            ("literal that is not UTF-8", ["--literal", "abcdef\udcff"]),
        ]
        for name, extra in cases:
            with self.subTest(name):
                done = run_cli(str(self.out), *extra)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertNotIn("Traceback", done.stderr)
                self.assertEqual(done.stdout, "")
                self.assertEqual((self.out / "a.txt").read_text(encoding="utf-8"),
                                 "pw=hunter2hunter2")

    def test_cli_prints_a_json_summary_on_success(self):
        (self.out / "a.txt").write_text("pw=" + TOKEN, encoding="utf-8")
        done = run_cli(str(self.out), "--literal", TOKEN)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotEqual(done.stdout.strip(), "null")
        summary = json.loads(done.stdout)
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["files_redacted"], 1)
        self.assertEqual(summary["replacements"], 1)


class LiteralFileRuleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def load(self, text):
        path = self.base / "lits.txt"
        path.write_text(text, encoding="utf-8")
        return rl.load_literals([], str(path))

    def test_hash_after_the_value_is_part_of_the_value(self):
        literals = self.load("hunter2hunter2  # note\n")
        self.assertEqual(literals, ["hunter2hunter2  # note"])
        self.assertEqual(rl.redact_text("pw=hunter2hunter2  # note", literals),
                         ("pw=[REDACTED]", 1))
        self.assertEqual(rl.redact_text("pw=hunter2hunter2", literals), ("pw=hunter2hunter2", 0))

    def test_comment_lines_are_skipped(self):
        self.assertEqual(self.load("# note\n   # indented note\nhunter2hunter2\n"),
                         ["hunter2hunter2"])

    def test_leading_and_trailing_spaces_are_part_of_the_value(self):
        self.assertEqual(self.load("  hunter2hunter2  \n"), ["  hunter2hunter2  "])


class FilesArgumentTests(unittest.TestCase):
    """redact_tree(files=...): only the listed files are rewritten, and links are not followed."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.out = self.base / "out"
        self.out.mkdir()
        self.outside = self.base / "outside"
        self.outside.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

    def text(self, path):
        return path.read_text(encoding="utf-8")

    def link(self, target, name):
        try:
            os.symlink(str(target), str(name))
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symbolic links are not available: %s" % exc)

    def test_only_listed_files_are_rewritten(self):
        self.write(self.out / "a.txt", "a=" + TOKEN)
        self.write(self.out / "b.txt", "b=" + TOKEN)
        summary = rl.redact_tree(str(self.out), [TOKEN], files=[str(self.out / "a.txt")])
        self.assertNotIn(TOKEN, self.text(self.out / "a.txt"))
        self.assertIn(TOKEN, self.text(self.out / "b.txt"))
        self.assertEqual((summary["files_scanned"], summary["files_redacted"]), (1, 1))

    def test_paths_are_read_as_open_reads_them_relative_to_the_current_directory(self):
        self.write(self.out / "sub" / "a.txt", "a=" + TOKEN)
        relative = os.path.relpath(self.out / "sub" / "a.txt")
        summary = rl.redact_tree(str(self.out), [TOKEN], files=[relative])
        self.assertEqual(summary["files_redacted"], 1)
        self.assertNotIn(TOKEN, self.text(self.out / "sub" / "a.txt"))

    def test_listed_file_outside_the_directory_raises_before_any_rewrite(self):
        self.write(self.out / "a.txt", "a=" + TOKEN)
        self.write(self.outside / "o.txt", "o=" + TOKEN)
        outside_file = self.outside / "o.txt"
        for bad in (str(outside_file), os.path.relpath(outside_file)):
            with self.subTest(bad=bad):
                with self.assertRaises(rl.LiteralError):
                    rl.redact_tree(str(self.out), [TOKEN],
                                   files=[str(self.out / "a.txt"), bad])
                self.assertIn(TOKEN, self.text(self.out / "a.txt"))
                self.assertIn(TOKEN, self.text(self.outside / "o.txt"))

    def test_symbolic_link_to_a_file_outside_is_not_followed(self):
        self.write(self.outside / "o.txt", "o=" + TOKEN)
        self.link(self.outside / "o.txt", self.out / "link.txt")
        with self.assertRaises(rl.LiteralError):
            rl.redact_tree(str(self.out), [TOKEN], files=[str(self.out / "link.txt")])
        self.assertIn(TOKEN, self.text(self.outside / "o.txt"))

    def test_symbolic_links_inside_the_directory_are_skipped(self):
        self.write(self.out / "a.txt", "a=" + TOKEN)
        self.write(self.out / "sub" / "b.txt", "b=" + TOKEN)
        self.link(self.out / "a.txt", self.out / "alias.txt")
        self.link(self.out / "sub", self.out / "sublink")
        listed = [str(self.out / "alias.txt"), str(self.out / "sublink" / "b.txt")]
        summary = rl.redact_tree(str(self.out), [TOKEN], files=listed)
        self.assertEqual(summary["files_scanned"], 0)
        self.assertEqual(summary["skipped"], [])
        self.assertIn(TOKEN, self.text(self.out / "a.txt"))
        self.assertIn(TOKEN, self.text(self.out / "sub" / "b.txt"))

    def test_directory_walk_does_not_follow_symbolic_links(self):
        self.write(self.outside / "o.txt", "o=" + TOKEN)
        self.link(self.outside / "o.txt", self.out / "link.txt")
        self.link(self.outside, self.out / "linkdir")
        self.write(self.out / "a.txt", "a=" + TOKEN)
        summary = rl.redact_tree(str(self.out), [TOKEN])
        self.assertIn(TOKEN, self.text(self.outside / "o.txt"))
        self.assertNotIn(TOKEN, self.text(self.out / "a.txt"))
        self.assertEqual(summary["files_redacted"], 1)

    def test_binary_and_non_utf8_listed_files_are_reported_not_changed(self):
        self.write(self.out / "blob.bin", b"\x00\x01" + TOKEN.encode("utf-8"))
        self.write(self.out / "latin.txt", b"\xff" + TOKEN.encode("utf-8"))
        listed = [str(self.out / "blob.bin"), str(self.out / "latin.txt")]
        summary = rl.redact_tree(str(self.out), [TOKEN], files=listed)
        self.assertEqual(summary["skipped"], [{"path": "blob.bin", "reason": "binary"},
                                              {"path": "latin.txt", "reason": "not utf-8"}])
        self.assertEqual(summary["files_redacted"], 0)
        self.assertEqual((self.out / "blob.bin").read_bytes(), b"\x00\x01" + TOKEN.encode("utf-8"))
        self.assertEqual((self.out / "latin.txt").read_bytes(), b"\xff" + TOKEN.encode("utf-8"))

    def test_named_pipe_in_the_walk_is_listed_and_never_opened(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("named pipes are not available")
        self.write(self.out / "a.txt", "a=" + TOKEN)
        os.mkfifo(str(self.out / "pipe"))
        # A child process with a timeout: opening a FIFO that has no writer blocks forever.
        code = ("import sys; sys.path.insert(0, %r); import json, redact_literals as rl; "
                "print(json.dumps(rl.redact_tree(%r, [%r])))"
                % (str(SCRIPTS), str(self.out), TOKEN))
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        summary = json.loads(done.stdout)
        self.assertIn({"path": "pipe", "reason": "not a regular file"}, summary["skipped"])
        self.assertEqual(summary["files_redacted"], 1)

    def test_a_file_listed_twice_is_processed_once(self):
        self.write(self.out / "a.txt", TOKEN)
        listed = [str(self.out / "a.txt"), os.path.join(str(self.out), ".", "a.txt"),
                  str(self.out / "a.txt")]
        summary = rl.redact_tree(str(self.out), [TOKEN], files=listed)
        self.assertEqual(summary["files_scanned"], 1)
        self.assertEqual(summary["replacements"], 1)

    def test_listed_directory_or_missing_file_raises(self):
        (self.out / "sub").mkdir()
        for bad in (self.out / "sub", self.out / "missing.txt", self.out):
            with self.subTest(bad=str(bad)):
                with self.assertRaises(rl.LiteralError):
                    rl.redact_tree(str(self.out), [TOKEN], files=[str(bad)])

    def test_apply_literals_passes_files_through(self):
        self.write(self.out / "a.txt", "a=" + TOKEN)
        self.write(self.out / "b.txt", "b=" + TOKEN)
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            summary = rl.apply_literals([TOKEN], str(self.out), files=[str(self.out / "b.txt")])
            self.assertIsNone(rl.apply_literals([], str(self.out)))
        self.assertEqual(summary["files_redacted"], 1)
        self.assertIn(TOKEN, self.text(self.out / "a.txt"))
        self.assertNotIn(TOKEN, self.text(self.out / "b.txt"))


class ConsoleAndNestedLeakTests(unittest.TestCase):
    """End-to-end regressions: the literal must not reach stderr or the output files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_har(self, name, url, body_text):
        har = har_with_token()
        har["log"]["entries"][0]["request"]["url"] = url
        har["log"]["entries"][0]["response"]["content"]["text"] = body_text
        path = self.base / name
        path.write_text(json.dumps(har), encoding="utf-8")
        return path

    def test_login_path_on_stderr_is_redacted(self):
        lit = "sess-ABCD-9999-live"
        har = self.write_har("login.har", "https://api.example.test/api/login/" + lit, "ok")
        done = subprocess.run([sys.executable, str(SCRIPTS / "har_parse.py"), str(har),
                               "--out", str(self.base / "out"), "--literal", lit],
                              capture_output=True, text=True)
        self.assertNotIn(lit, done.stderr)
        self.assertIn("[REDACTED]", done.stderr)

    def test_json_escaped_secret_in_a_stored_body_is_not_on_disk(self):
        lit = 'pa"ss-word-9'
        har = self.write_har("quote.har", "https://api.example.test/v1/profile",
                             json.dumps({"password_hint": lit}))
        lit_file = self.base / "lit.txt"
        lit_file.write_text(lit + "\n", encoding="utf-8")
        out = self.base / "out"
        done = subprocess.run([sys.executable, str(SCRIPTS / "har_parse.py"), str(har),
                               "--out", str(out), "--literal-file", str(lit_file)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        for path in out.rglob("*"):
            if path.is_file():
                self.assertNotIn("ss-word-9", path.read_text(encoding="utf-8"), path)
        self.assertNotIn("ss-word-9", done.stderr)

    def test_stackplz_buffer_with_escaped_secret_is_not_on_disk(self):
        lit = 'pa"ss-word-9'
        event = {"name": "SSL_write", "comm": "app", "pid": 1234, "tid": 1234,
                 "buf": json.dumps({"password": lit, "user": "alice"})}
        events = self.base / "stack.json"
        events.write_text(json.dumps([event]), encoding="utf-8")
        lit_file = self.base / "lit.txt"
        lit_file.write_text(lit + "\n", encoding="utf-8")
        out = self.base / "out"
        done = subprocess.run([sys.executable, str(SCRIPTS / "stackplz_parse.py"), str(events),
                               "--out", str(out), "--literal-file", str(lit_file)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        for path in out.rglob("*"):
            if path.is_file():
                self.assertNotIn("ss-word-9", path.read_text(encoding="utf-8"), path)
        self.assertNotIn("ss-word-9", done.stderr)


if __name__ == "__main__":
    unittest.main()
