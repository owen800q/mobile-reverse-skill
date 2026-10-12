#!/usr/bin/env python3
"""Tests for scripts/endpoint_inventory.py: templating, no raw values, literal redaction."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import endpoint_inventory as ei  # noqa: E402

UUID = "3f2a9c1e-7b4d-4e8a-9f10-2c5d6e7f8a9b"
HEX = "9f86d081884c7d65a5f0c3b1d2e4f5a6"
TOKEN = "Qm9vdHN0cmFwVG9rZW4xMjM0"
SECRET = "sess-ABCD-9999-live"


def send(method, path, host="api.example.test", index=0):
    return {"direction": "send", "method": method, "host": host, "path": path, "entry_index": index}


class TemplateTests(unittest.TestCase):
    def test_numeric_uuid_hex_token_and_timestamp_segments(self):
        self.assertEqual(ei.template_path("/v1/users/12345/orders")[0], "/v1/users/{n}/orders")
        self.assertEqual(ei.template_path("/v1/u/%s" % UUID)[0], "/v1/u/{uuid}")
        self.assertEqual(ei.template_path("/v1/i/%s" % HEX)[0], "/v1/i/{hex}")
        self.assertEqual(ei.template_path("/v1/s/%s" % TOKEN)[0], "/v1/s/{token}")
        self.assertEqual(ei.template_path("/v1/export/1714000000000")[0], "/v1/export/{ts}")

    def test_path_without_a_leading_slash_keeps_its_segments(self):
        self.assertEqual(ei.template_path("users/12345/orders")[0], "/users/{n}/orders")
        self.assertEqual(ei.template_path("?q=1")[0], "/")

    def test_static_words_are_kept(self):
        self.assertEqual(ei.template_path("/api/v2/auth/login")[0], "/api/v2/auth/login")

    def test_query_string_is_dropped_but_parameter_names_are_kept(self):
        template, names = ei.template_path("/search?q=secret-value&page=2")
        self.assertEqual(template, "/search")
        self.assertEqual(names, ["page", "q"])
        self.assertNotIn("secret-value", template)


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

    def test_declared_literal_is_removed_even_from_a_static_segment(self):
        self.requests.write_text(json.dumps([send("GET", "/v1/acct-partner-7741/info", index=1)]),
                                 encoding="utf-8")
        result, out = self.run_inventory("acct-partner-7741")
        self.assertNotIn("acct-partner-7741", out.read_text(encoding="utf-8"))
        self.assertIn("[REDACTED]", result["endpoints"][0]["template"])

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


if __name__ == "__main__":
    unittest.main()
