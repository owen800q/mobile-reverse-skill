#!/usr/bin/env python3
"""Tests for literal and redaction handling in har_parse.py, ecapture_parse.py and stackplz_parse.py."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import har_parse as hp  # noqa: E402

LITERAL = "hunter2hunter2"
HOST = "https://api.example.test"
# 24 characters of letters and digits that are not all hex, so template_path gives {token}.
# (A purely hex segment such as a1b2c3d4e5f6a7b8c9d0e1f2 gives {hex}.)
LOGIN_SEGMENT = "k1m2n3p4q5r6s7t8u9v0w1x2"


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args],
                          capture_output=True, text=True)


def nested_json(depth):
    """A JSON object nested depth levels deep with a password key at the bottom.

    Built as text, because json.dumps itself recurses and fails before the parser does.
    """
    return '{"a":' * depth + '{"password": "%s"}' % LITERAL + "}" * depth


def har_entry(url, method="POST", post=None):
    request = {"method": method, "url": url, "httpVersion": "HTTP/1.1", "headers": [],
               "queryString": [], "cookies": [], "headersSize": -1, "bodySize": -1}
    if post is not None:
        request["postData"] = post
    return {
        "startedDateTime": "2026-01-01T00:00:00.000Z", "time": 1, "request": request,
        "response": {"status": 200, "statusText": "OK", "httpVersion": "HTTP/1.1", "headers": [],
                     "cookies": [], "headersSize": -1, "bodySize": -1,
                     "content": {"size": 2, "mimeType": "text/plain", "text": "ok"}},
        "cache": {}, "timings": {"send": 0, "wait": 0, "receive": 0},
    }


def har_doc(*entries):
    return {"log": {"version": "1.2", "creator": {"name": "test", "version": "1"},
                    "entries": list(entries)}}


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_har(self, name, entries, *extra):
        """Run har_parse.py on a HAR built from entries; return (records, stderr, out_dir)."""
        har = self.base / (name + ".har")
        har.write_text(json.dumps(har_doc(*entries)), encoding="utf-8")
        out = self.base / name
        done = run_script("har_parse.py", str(har), "--out", str(out), *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        records = json.loads((out / "requests.json").read_text(encoding="utf-8"))
        return records, done.stderr, out


class HarDeepBodyTests(TempDirTestCase):
    def test_deep_body_with_password_is_withheld_under_redact(self):
        body = nested_json(1500)
        text, obj, count = hp._process_body(body, True)
        self.assertEqual(text, hp._withheld())
        self.assertIsNone(obj)
        self.assertEqual(count, 0)
        self.assertNotIn(LITERAL, text)

    def test_body_past_json_max_depth_is_withheld_under_redact(self):
        text, _, _ = hp._process_body(nested_json(hp.JSON_MAX_DEPTH + 50), True)
        self.assertEqual(text, hp._withheld())

    def test_redaction_walk_recursion_error_withholds_the_body(self):
        with mock.patch.object(hp, "_redact_json", side_effect=RecursionError):
            text, _, _ = hp._process_body('{"password": "%s"}' % LITERAL, True)
        self.assertEqual(text, hp._withheld())

    def test_deep_body_is_kept_when_not_redacting(self):
        body = nested_json(1500)
        text, obj, _ = hp._process_body(body, False)
        self.assertEqual(text, body)
        self.assertIsNone(obj)

    def test_cli_withholds_1500_level_body_in_requests_json(self):
        entry = har_entry(HOST + "/v1/session", post={"mimeType": "application/json",
                                                      "text": nested_json(1500)})
        records, _, out = self.run_har("deep", [entry], "--redact")
        self.assertEqual(records[0]["body"], hp._withheld())
        self.assertNotIn(LITERAL, (out / "requests.json").read_text(encoding="utf-8"))


class HarTextBodyTests(TempDirTestCase):
    def test_form_text_body_is_redacted_under_redact(self):
        entry = har_entry(HOST + "/api/form", post={
            "mimeType": "application/x-www-form-urlencoded",
            "text": "user=alice&password=" + LITERAL})
        records, _, out = self.run_har("form", [entry], "--redact")
        self.assertEqual(records[0]["body"], "user=alice&password=[REDACTED]")
        self.assertEqual(records[0]["redactions"], 1)
        self.assertNotIn(LITERAL, (out / "requests.json").read_text(encoding="utf-8"))

    def test_form_text_body_is_kept_without_redact(self):
        entry = har_entry(HOST + "/api/form", post={
            "mimeType": "application/x-www-form-urlencoded",
            "text": "user=alice&password=" + LITERAL})
        records, _, _ = self.run_har("form_plain", [entry])
        self.assertEqual(records[0]["body"], "user=alice&password=" + LITERAL)

    def test_plain_text_body_without_equals_is_unchanged(self):
        text = "Hello there, nothing to see; no key pairs at all"
        entry = har_entry(HOST + "/api/note", post={"mimeType": "text/plain", "text": text})
        records, _, _ = self.run_har("plain", [entry], "--redact")
        self.assertEqual(records[0]["body"], text)
        self.assertEqual(records[0]["redactions"], 0)


class HarLoginListingTests(TempDirTestCase):
    def test_login_path_prints_templated_segments_without_the_query(self):
        url = "%s/v1/auth/%s/verify?sid=abc" % (HOST, LOGIN_SEGMENT)
        _, err, _ = self.run_har("login", [har_entry(url)])
        self.assertIn("\nLogin-looking send requests (templated path, query omitted):\n", err)
        self.assertIn("  [entry 0] POST /v1/auth/{token}/verify (query omitted)\n", err)
        self.assertNotIn(LOGIN_SEGMENT, err)
        self.assertNotIn("sid=abc", err)

    def test_path_that_urlsplit_rejects_is_not_printed_and_does_not_abort(self):
        url = HOST + "//[a://b/login"
        records, err, _ = self.run_har("bracket", [har_entry(url)])
        self.assertEqual(len(records), 2)
        self.assertIn("  [entry 0] POST (path not templated)\n", err)
        self.assertIn("har_parse:", err)

    def test_declared_literal_in_login_path_never_reaches_stderr(self):
        literal = "abcdefgh/12345678"
        url = "%s/v1/auth/%s/verify?token=%s" % (HOST, literal, LITERAL)
        records, err, out = self.run_har("lit", [har_entry(url)], "--literal", literal)
        self.assertIn("  [entry 0] POST /v1/auth/[REDACTED]/verify (query omitted)\n", err)
        self.assertNotIn("abcdefgh", err)
        self.assertNotIn("12345678", err)
        for path in out.rglob("*"):
            if path.is_file():
                self.assertNotIn(literal, path.read_text(encoding="utf-8", errors="replace"), path)


class EcaptureLiteralTests(TempDirTestCase):
    FORM_LOG = [
        "PID: 1234 Comm: app TID: 1234",
        "Send Data:",
        "POST /v1/login HTTP/1.1",
        "Host: api.example.test",
        "Content-Type: application/x-www-form-urlencoded",
        "",
        "user=alice&password=" + LITERAL,
    ]
    SIGN_HEADER_LOG = [
        "PID: 1234 Comm: app TID: 1234",
        "Send Data:",
        "GET /login HTTP/1.1",
        "Host: api.example.test",
        "X-Sign-" + LITERAL + ": abc",
    ]

    def test_raw_capture_inside_out_dir_is_byte_identical(self):
        out = self.base / "re_out"
        out.mkdir()
        raw = out / "ecapture_text.log"
        raw.write_text("\n".join(self.FORM_LOG) + "\n", encoding="utf-8")
        before = raw.read_bytes()
        done = run_script("ecapture_parse.py", str(raw), "--out", str(out), "--literal", LITERAL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(raw.read_bytes(), before)
        requests = (out / "requests.json").read_text(encoding="utf-8")
        self.assertNotIn(LITERAL, requests)
        self.assertIn("[REDACTED]", requests)

    def test_other_files_in_out_dir_are_not_rewritten(self):
        out = self.base / "re_out"
        out.mkdir()
        notes = out / "notes.txt"
        notes.write_text("kept " + LITERAL, encoding="utf-8")
        log = self.base / "capture.log"
        log.write_text("\n".join(self.FORM_LOG) + "\n", encoding="utf-8")
        done = run_script("ecapture_parse.py", str(log), "--out", str(out), "--literal", LITERAL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(notes.read_text(encoding="utf-8"), "kept " + LITERAL)

    def test_signature_key_containing_literal_is_redacted_on_stderr(self):
        log = self.base / "sign.log"
        log.write_text("\n".join(self.SIGN_HEADER_LOG) + "\n", encoding="utf-8")
        out = self.base / "sign_out"
        done = run_script("ecapture_parse.py", str(log), "--out", str(out), "--literal", LITERAL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("X-Sign-[REDACTED]", done.stderr)
        self.assertNotIn(LITERAL, done.stderr)
        self.assertNotIn(LITERAL, (out / "requests.json").read_text(encoding="utf-8"))


class StackplzLiteralTests(TempDirTestCase):
    def write_events(self, name, events):
        path = self.base / name
        path.write_text(json.dumps(events), encoding="utf-8")
        return path

    def test_literal_across_the_400_character_cut_leaves_no_prefix(self):
        text = "login=" + "x" * (395 - len("login=")) + LITERAL + "y" * 30
        self.assertEqual(text.index(LITERAL), 395)
        events = self.write_events("cut.json", [
            {"name": "SSL_write", "comm": "app", "pid": 1, "tid": 1, "buf": text}])
        out = self.base / "cut_out"
        done = run_script("stackplz_parse.py", str(events), "--out", str(out), "--literal", LITERAL)
        self.assertEqual(done.returncode, 0, done.stderr)
        written = (out / "stackplz_events.json").read_text(encoding="utf-8")
        for k in range(4, len(LITERAL) + 1):
            self.assertNotIn(LITERAL[:k], written)
            self.assertNotIn(LITERAL[:k], done.stderr)
        # The marker is written before the cut, so the 400-character cut ends inside it.
        self.assertIn("x" * 389 + "[REDA\"", written)

    def test_literal_in_comm_and_name_stays_off_stderr(self):
        events = self.write_events("names.json", [{
            "name": "SSL_write_" + LITERAL + "_token", "comm": "app-" + LITERAL,
            "pid": 1, "tid": 1, "buf": "login=alice"}])
        done = run_script("stackplz_parse.py", str(events), "--out", str(self.base / "names_out"),
                          "--literal", LITERAL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(LITERAL, done.stderr)
        self.assertIn("[REDACTED]", done.stderr)

    def test_raw_events_inside_out_dir_are_byte_identical(self):
        out = self.base / "re_out"
        out.mkdir()
        raw = out / "stackplz_events.json"
        raw.write_text(json.dumps([{"name": "SSL_write", "comm": "app", "pid": 1, "tid": 1,
                                    "buf": "login=alice&password=" + LITERAL}]), encoding="utf-8")
        before = raw.read_bytes()
        done = run_script("stackplz_parse.py", str(raw), "--out", str(out), "--literal", LITERAL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(raw.read_bytes(), before)
        normalized = (out / "stackplz_events.normalized.json").read_text(encoding="utf-8")
        self.assertNotIn(LITERAL, normalized)
        self.assertNotIn(LITERAL, done.stderr)


if __name__ == "__main__":
    unittest.main()
