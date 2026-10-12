#!/usr/bin/env python3
"""Tests for scripts/endpoint_inventory.py: templating, output, literal redaction and exit codes."""
import contextlib
import io
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

import endpoint_inventory as ei  # noqa: E402
import redact_literals  # noqa: E402

UUID = "3f2a9c1e-7b4d-4e8a-9f10-2c5d6e7f8a9b"
HEX = "9f86d081884c7d65a5f0c3b1d2e4f5a6"
TOKEN = "Qm9vdHN0cmFwVG9rZW4xMjM0"
SECRET = "sess-ABCD-9999-live"
TOKEN20 = "Qm9vdHN0cmFwVG9rZW4x"  # 20 characters, letters and digits
TOKEN19 = "Qm9vdHN0cmFwVG9rZW4"  # the same string without its last character
VALUE = "VALUE-XYZ-987654"
LITERAL = "acct-partner-7741"


def send(method, path, host="api.example.test", index=0):
    return {"direction": "send", "method": method, "host": host, "path": path, "entry_index": index}


class TemplateTests(unittest.TestCase):
    def test_numeric_uuid_hex_token_and_timestamp_segments(self):
        self.assertEqual(ei.template_path("/v1/users/12345/orders")[0], "/v1/users/{n}/orders")
        self.assertEqual(ei.template_path("/v1/u/%s" % UUID)[0], "/v1/u/{uuid}")
        self.assertEqual(ei.template_path("/v1/i/%s" % HEX)[0], "/v1/i/{hex}")
        self.assertEqual(ei.template_path("/v1/s/%s" % TOKEN)[0], "/v1/s/{token}")
        self.assertEqual(ei.template_path("/v1/export/1714000000000")[0], "/v1/export/{ts}")

    def test_twenty_character_mixed_segment_is_a_token_and_nineteen_is_kept(self):
        self.assertEqual(len(TOKEN20), 20)
        self.assertEqual(ei.template_segment(TOKEN20), "{token}")
        self.assertEqual(ei.template_path("/v1/sessions/%s" % TOKEN20)[0], "/v1/sessions/{token}")
        self.assertEqual(len(TOKEN19), 19)
        self.assertEqual(ei.template_segment(TOKEN19), TOKEN19)

    def test_sixteen_digit_numeric_segment_is_n_not_hex(self):
        self.assertEqual(ei.template_segment("1234567890123456"), "{n}")
        self.assertEqual(ei.template_segment("12345678901234567890"), "{n}")
        self.assertEqual(ei.template_segment("0123456789abcdef"), "{hex}")

    def test_ten_and_thirteen_digits_are_timestamps_other_lengths_are_n(self):
        self.assertEqual(ei.template_segment("1714000000"), "{ts}")
        self.assertEqual(ei.template_segment("1714000000000"), "{ts}")
        self.assertEqual(ei.template_segment("17140000000"), "{n}")

    def test_path_without_a_leading_slash_keeps_its_segments(self):
        self.assertEqual(ei.template_path("users/12345/orders")[0], "/users/{n}/orders")
        self.assertEqual(ei.template_path("?q=1")[0], "/")

    def test_static_words_are_kept(self):
        self.assertEqual(ei.template_path("/api/v2/auth/login")[0], "/api/v2/auth/login")

    def test_segments_that_match_no_rule_are_kept_as_decoded_text(self):
        self.assertEqual(ei.template_path("/v1/users/alice/orders")[0], "/v1/users/alice/orders")
        self.assertEqual(ei.template_segment("0123456789abcde"), "0123456789abcde")
        self.assertEqual(ei.template_segment("abcdefghijklmnopqrstuvwxy"),
                         "abcdefghijklmnopqrstuvwxy")

    def test_segments_are_templated_after_percent_decoding(self):
        self.assertEqual(ei.template_path("/v1/%31%32%33%34%35")[0], "/v1/{n}")

    def test_query_string_is_dropped_but_parameter_names_are_kept(self):
        template, names = ei.template_path("/search?q=secret-value&page=2")
        self.assertEqual(template, "/search")
        self.assertEqual(names, ["page", "q"])
        self.assertNotIn("secret-value", template)

    def test_fragment_is_dropped(self):
        template, names = ei.template_path("/v1/a/12345?x=1#frag")
        self.assertEqual(template, "/v1/a/{n}")
        self.assertEqual(names, ["x"])

    def test_bare_query_token_is_a_parameter_name_and_its_value_is_never_kept(self):
        template, names = ei.template_path("/v1/session?sessiontoken123456789")
        self.assertEqual(template, "/v1/session")
        self.assertEqual(names, ["sessiontoken123456789"])
        template, names = ei.template_path("/v1/session?sessiontoken123456789&auth=%s" % VALUE)
        self.assertEqual(names, ["auth", "sessiontoken123456789"])
        self.assertFalse(any(VALUE in text for text in [template] + names))


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.requests = self.dir / "requests.json"
        records = [
            send("GET", "/v1/users/111/orders?page=1", index=1),
            send("GET", "/v1/users/222/orders?page=2", index=2),
            send("POST", "/api/v2/auth/login", index=3),
            send("GET", "/v1/sessions/%s?token=%s" % (TOKEN, SECRET), index=4),
            {"direction": "recv", "method": None, "path": None, "host": None, "entry_index": 1},
        ]
        self.requests.write_text(json.dumps(records), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_inventory(self, *extra):
        out = self.dir / "endpoints.json"
        result = ei.run(str(self.requests), str(out), literals=list(extra))
        return result, out

    def write_records(self, records):
        self.requests.write_text(json.dumps(records), encoding="utf-8")

    def test_requests_group_by_template_and_count(self):
        result, _ = self.run_inventory()
        groups = {(e["method"], e["template"]): e for e in result["endpoints"]}
        users = groups[("GET", "/v1/users/{n}/orders")]
        self.assertEqual(users["count"], 2)
        self.assertEqual(users["entry_indices"], [1, 2])
        self.assertEqual(users["query_params"], ["page"])
        self.assertEqual(result["send_records"], 4)

    def test_output_never_contains_raw_ids_or_query_values(self):
        _, out = self.run_inventory()
        text = out.read_text(encoding="utf-8")
        for raw in ("111", "222", TOKEN, SECRET, "page=1"):
            self.assertNotIn(raw, text)

    def test_more_than_fifty_send_records_keep_exactly_fifty_entry_indices(self):
        self.write_records([send("GET", "/v1/items/%d" % i, index=i) for i in range(60)])
        result, _ = self.run_inventory()
        (group,) = [e for e in result["endpoints"] if e["template"] == "/v1/items/{n}"]
        self.assertEqual(group["count"], 60)
        self.assertEqual(group["entry_indices"], list(range(50)))

    def test_entry_indices_are_distinct(self):
        self.write_records([send("GET", "/v1/items/%d" % i, index=7) for i in range(3)])
        result, _ = self.run_inventory()
        (group,) = result["endpoints"]
        self.assertEqual(group["count"], 3)
        self.assertEqual(group["entry_indices"], [7])

    def test_method_is_upper_cased_and_host_is_kept_as_recorded(self):
        self.write_records([send("get", "/v1/x", host="API.Example.Test", index=1)])
        result, _ = self.run_inventory()
        endpoint = result["endpoints"][0]
        self.assertEqual(endpoint["method"], "GET")
        self.assertEqual(endpoint["host"], "API.Example.Test")

    def test_declared_literal_is_removed_even_from_a_static_segment(self):
        self.write_records([send("GET", "/v1/%s/info" % LITERAL, index=1)])
        result, out = self.run_inventory(LITERAL)
        self.assertNotIn(LITERAL, out.read_text(encoding="utf-8"))
        self.assertIn("[REDACTED]", result["endpoints"][0]["template"])

    def test_declared_literal_is_removed_from_host_and_parameter_names(self):
        self.write_records([send("GET", "/v1/info?%s=1" % LITERAL,
                                 host="%s.example.test" % LITERAL, index=1)])
        result, out = self.run_inventory(LITERAL)
        endpoint = result["endpoints"][0]
        self.assertEqual(endpoint["host"], "[REDACTED].example.test")
        self.assertEqual(endpoint["query_params"], ["[REDACTED]"])
        self.assertNotIn(LITERAL, out.read_text(encoding="utf-8"))

    def test_every_encoding_in_variants_is_removed_from_the_host(self):
        for form in redact_literals.variants(LITERAL):
            with self.subTest(form=form):
                host = "h-%s-h.example.test" % form
                self.write_records([send("GET", "/v1/x", host=host, index=1)])
                result, _ = self.run_inventory(LITERAL)
                self.assertNotIn(form, result["endpoints"][0]["host"])

    def test_base64_literal_at_a_non_zero_byte_alignment_is_removed(self):
        # base64 of b"Apassword" is QXBhc3N3b3Jk: "password" starts at byte 1 of that value, and
        # the alignment forms in redact_literals.variants() cover that position.
        self.write_records([send("GET", "/v1/QXBhc3N3b3Jk", index=1)])
        result, out = self.run_inventory("password")
        self.assertEqual(result["endpoints"][0]["template"], "/v1/QXBh[REDACTED]")
        self.assertNotIn("c3N3b3Jk", out.read_text(encoding="utf-8"))

    def test_output_file_is_private(self):
        _, out = self.run_inventory()
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)

    def test_cli_rejects_non_list_input(self):
        bad = self.dir / "bad.json"
        bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        done = subprocess.run([sys.executable, str(SCRIPTS / "endpoint_inventory.py"), str(bad),
                               "--out", str(self.dir / "o.json")], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("list of records", done.stderr)


class LimitationsTests(unittest.TestCase):
    def test_limitations_state_the_rules_the_entry_cap_and_the_redaction_scope(self):
        text = " ".join(ei.LIMITATIONS)
        for placeholder in ("{uuid}", "{ts}", "{n}", "{hex}", "{token}"):
            self.assertIn(placeholder, text)
        self.assertIn("first 50 distinct entry indices", text)
        self.assertIn("Query values are never kept", text)
        self.assertIn("redact_literals.variants()", text)


class ExitCodeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.requests = self.dir / "requests.json"
        self.out = self.dir / "endpoints.json"

    def tearDown(self):
        self._tmp.cleanup()

    def run_main(self, payload: bytes, *extra):
        self.requests.write_bytes(payload)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = ei.main([str(self.requests), "--out", str(self.out), *extra])
        return code, err.getvalue()

    def test_non_utf8_requests_file_exits_2(self):
        code, err = self.run_main(b'[{"direction": "send", "method": "GET", "path": "/v1/\xff"}]')
        self.assertEqual(code, 2)
        self.assertIn("cannot read requests JSON", err)
        self.assertFalse(self.out.exists())

    def test_requests_nested_1500_levels_exits_2(self):
        code, err = self.run_main(b"[" * 1500 + b"]" * 1500)
        self.assertEqual(code, 2)
        self.assertIn("nested too deeply", err)
        self.assertFalse(self.out.exists())

    @unittest.skipUnless(hasattr(sys, "get_int_max_str_digits"),
                         "the int string-length limit needs Python 3.11 or later")
    def test_value_error_from_the_parser_exits_2(self):
        code, err = self.run_main(b"[" + b"1" * 5000 + b"]")
        self.assertEqual(code, 2)
        self.assertIn("cannot read requests JSON", err)

    def test_invalid_json_exits_2(self):
        code, err = self.run_main(b"[{")
        self.assertEqual(code, 2)
        self.assertIn("cannot read requests JSON", err)

    def test_refused_literal_exits_2(self):
        code, err = self.run_main(b"[]", "--literal", "short")
        self.assertEqual(code, 2)
        self.assertIn("shorter than", err)

    def test_file_over_the_size_limit_exits_2(self):
        with mock.patch.object(ei, "MAX_REQUESTS_BYTES", 4):
            code, err = self.run_main(b"[]" * 10)
        self.assertEqual(code, 2)
        self.assertIn("exceeds 256 MiB", err)

    def test_missing_requests_file_exits_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = ei.main([str(self.dir / "absent.json"), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
