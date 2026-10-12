#!/usr/bin/env python3
"""Tests for scripts/redact_literals.py and its wiring into har_parse.py."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import redact_literals as rl  # noqa: E402

TOKEN = "s3cr3t-token-value"


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
            done = subprocess.run([sys.executable, str(SCRIPTS / "redact_literals.py"), tmp],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 2)


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
