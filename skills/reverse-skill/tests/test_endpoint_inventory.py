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


def send_body(body=None, form=None, index=0, method="POST", path="/v1/submit", host="api.example.test"):
    """A send record with an optional body string and form_params, as har_parse writes them."""
    record = send(method, path, host=host, index=index)
    if body is not None:
        record["body"] = body
    if form is not None:
        record["form_params"] = form
    return record


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


class BodyFieldTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def fields_by_endpoint(self, records, literals=()):
        endpoints, _ = ei.build_inventory(list(records), list(literals))
        return {(e["method"], e["template"]): e["body_fields"] for e in endpoints}

    def body_fields(self, record, literals=()):
        """The body_fields of the one endpoint that a single record makes."""
        (fields,) = self.fields_by_endpoint([record], literals).values()
        return fields

    def run_file(self, records, *literals):
        requests = self.dir / "requests.json"
        requests.write_text(json.dumps(records), encoding="utf-8")
        out = self.dir / "endpoints.json"
        ei.run(str(requests), str(out), literals=list(literals))
        return out.read_text(encoding="utf-8")

    def test_json_object_body_lists_its_keys_sorted(self):
        body = json.dumps({"username": "alice", "password": VALUE, "remember": True})
        self.assertEqual(self.body_fields(send_body(body)), ["password", "remember", "username"])

    def test_nested_objects_and_arrays_of_objects_contribute_their_keys(self):
        body = json.dumps({"device": {"model": "X1", "os": {"name": "android"}},
                           "items": [{"sku": "A1", "qty": 2}, [{"note": "n"}]],
                           "flag": 7})
        self.assertEqual(self.body_fields(send_body(body)),
                         sorted(["device", "flag", "items", "model", "name", "note", "os", "qty", "sku"]))

    def test_map_style_identifier_keys_are_templated_and_never_appear_raw(self):
        upper = UUID.upper()
        body = json.dumps({
            UUID: {"count": 1},
            upper: {"count": 2},
            TOKEN: {"count": 3},
            HEX: {"count": 4},
            "1714000000000": {"count": 5},
            "1714000000": 6,
            "1234567890123456": 7,
            "user@example.com": {"count": 8},
            "alice%40example.test": 9,
        })
        text = self.run_file([send_body(body)])
        fields = json.loads(text)["endpoints"][0]["body_fields"]
        self.assertEqual(fields, sorted(["count", "{uuid}", "{token}", "{hex}", "{ts}", "{n}", "{email}"]))
        for raw in (UUID, upper, TOKEN, HEX, "1714000000000", "1714000000", "1234567890123456",
                    "user@example.com", "alice%40example.test", "alice@example.test"):
            self.assertNotIn(raw, text)

    def test_distinct_identifier_keys_collapse_into_one_placeholder(self):
        body = json.dumps({"%08x-0000-4000-8000-000000000000" % i: 0 for i in range(300)})
        self.assertEqual(self.body_fields(send_body(body)), ["{uuid}"])

    def test_form_params_keys_are_listed_with_body_keys_and_their_values_are_not(self):
        form = {"username": VALUE, "pin": "1234", UUID: "x"}
        fields = self.body_fields(send_body(json.dumps({"remember": True}), form=form))
        self.assertEqual(fields, sorted(["{uuid}", "pin", "remember", "username"]))

    def test_bodies_that_are_not_json_objects_contribute_nothing(self):
        bodies = [
            "just some plain text",
            "username=alice&password=%s" % VALUE,
            json.dumps([{"id": 1}, {"name": "x"}]),
            json.dumps([1, 2, 3]),
            json.dumps('a string that holds {"k": 1}'),
            "42",
            "null",
            '{"unterminated": ',
            "postData.text absent",
            "binary/compressed body (120 bytes) not decoded.",
            "HTTP/2 or binary framing; body not reassembled as text.",
            "JSON body nested deeper than 200 levels; withheld (cannot be redacted).",
        ]
        for body in bodies:
            with self.subTest(body=body[:40]):
                self.assertEqual(self.body_fields(send_body(body)), [])
        with self.subTest(case="no body"):
            self.assertEqual(self.body_fields(send_body()), [])
        with self.subTest(case="body is not a string"):
            record = send_body()
            record["body"] = {"hidden": VALUE}
            self.assertEqual(self.body_fields(record), [])

    def test_nesting_is_bounded_by_max_nesting(self):
        depth = ei.MAX_NESTING
        inner = '{"deepest_key": 1}'
        at_limit = '{"wrap": ' * (depth - 1) + inner + "}" * (depth - 1)
        past_limit = '{"wrap": ' * depth + inner + "}" * depth
        self.assertEqual(self.body_fields(send_body(at_limit)), sorted(["deepest_key", "wrap"]))
        self.assertEqual(self.body_fields(send_body(past_limit)), [])
        endpoint = json.loads(self.run_file([send_body(past_limit)]))["endpoints"][0]
        self.assertEqual(endpoint["body_fields"], [])

    def test_declared_literal_in_a_body_key_is_redacted(self):
        body = json.dumps({LITERAL: 1, "ok": 2})
        self.assertEqual(self.body_fields(send_body(body), literals=[LITERAL]),
                         sorted(["[REDACTED]", "ok"]))
        text = self.run_file([send_body(body)], LITERAL)
        self.assertNotIn(LITERAL, text)
        self.assertEqual(json.loads(text)["endpoints"][0]["body_fields"], sorted(["[REDACTED]", "ok"]))

    def test_names_that_differ_only_in_a_literal_encoded_form_are_merged_after_redaction(self):
        literal = "partner x 7741"
        body = json.dumps({"k partner x 7741": 1, "k partner+x+7741": 2})
        self.assertEqual(self.body_fields(send_body(body), literals=[literal]), ["k [REDACTED]"])

    def test_values_are_never_listed(self):
        body = json.dumps({"amount": 99999, "memo": VALUE,
                           "nested": {"inner": [VALUE, {"secret_value": VALUE}]}, "flag": None})
        text = self.run_file([send_body(body, form={"comment": VALUE})])
        fields = json.loads(text)["endpoints"][0]["body_fields"]
        self.assertEqual(fields, sorted(["amount", "comment", "flag", "inner", "memo", "nested",
                                         "secret_value"]))
        self.assertNotIn(VALUE, text)
        self.assertNotIn("99999", text)

    def test_body_fields_come_from_send_records_of_their_own_endpoint_only(self):
        records = [
            send_body(json.dumps({"alpha": 1}), index=1, method="POST", path="/v1/a"),
            send_body(json.dumps({"beta": 1}), index=2, method="POST", path="/v1/b"),
            send_body(json.dumps({"delta": 1}), index=3, method="GET", path="/v1/a"),
            {"direction": "recv", "method": None, "path": None, "host": None, "entry_index": 4,
             "body": json.dumps({"gamma": 1})},
        ]
        self.assertEqual(self.fields_by_endpoint(records), {
            ("POST", "/v1/a"): ["alpha"],
            ("POST", "/v1/b"): ["beta"],
            ("GET", "/v1/a"): ["delta"],
        })

    def test_at_most_max_body_fields_names_are_kept_and_they_are_the_first_met(self):
        keys = ["k%03d" % i for i in range(ei.MAX_BODY_FIELDS + 50)]
        body = json.dumps({key: 0 for key in keys})
        self.assertEqual(self.body_fields(send_body(body)), sorted(keys[:ei.MAX_BODY_FIELDS]))

    def test_body_fields_sit_after_query_params_and_are_empty_without_a_body(self):
        text = self.run_file([send_body(json.dumps({"b": 1})),
                              send_body(None, index=2, path="/v1/other")])
        by_template = {e["template"]: e for e in json.loads(text)["endpoints"]}
        self.assertEqual(by_template["/v1/submit"]["body_fields"], ["b"])
        self.assertEqual(by_template["/v1/other"]["body_fields"], [])
        keys = list(by_template["/v1/submit"])
        self.assertEqual(keys[keys.index("query_params") + 1], "body_fields")

    def test_lone_surrogate_key_is_shown_escaped_so_the_file_can_still_be_written(self):
        text = self.run_file([send_body('{"\\ud800": 1}')])
        self.assertEqual(json.loads(text)["endpoints"][0]["body_fields"], ["\\ud800"])

    def test_json_ld_keywords_and_other_at_signs_are_not_mistaken_for_addresses(self):
        body = json.dumps({"@type": "Thing", "@context": "https://schema.example.test", "icon@2x": 1})
        self.assertEqual(self.body_fields(send_body(body)), ["@context", "@type", "icon@2x"])


class LimitationsTests(unittest.TestCase):
    def test_limitations_state_the_rules_the_entry_cap_and_the_redaction_scope(self):
        text = " ".join(ei.LIMITATIONS)
        for placeholder in ("{uuid}", "{ts}", "{n}", "{hex}", "{token}"):
            self.assertIn(placeholder, text)
        self.assertIn("first 50 distinct entry indices", text)
        self.assertIn("Query values are never kept", text)
        self.assertIn("redact_literals.variants()", text)

    def test_limitations_and_docstring_describe_body_fields_as_keys_only_and_capped(self):
        text = " ".join(ei.LIMITATIONS)
        self.assertNotIn("body fields are not listed", text)
        for phrase in ("body_fields", "never values", "form_params", "{email}", "MAX_BODY_FIELDS",
                       "MAX_NESTING"):
            self.assertIn(phrase, text)
        self.assertIn("body_fields", ei.__doc__)


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
