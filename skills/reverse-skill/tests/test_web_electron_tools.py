#!/usr/bin/env python3

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import asar_extract as asar  # noqa: E402
import ecapture_parse  # noqa: E402
import har_parse as har  # noqa: E402
import js_sourcemap_extract as sourcemap  # noqa: E402

ECAP_KEYS = set(ecapture_parse.extract_http("send", b"GET / HTTP/1.1\r\nHost: h\r\n\r\n"))
HAR_EXTRA_KEYS = {"url", "source", "entry_index", "started", "redactions", "form_params",
                  "body_sha256"}
BIN = bytes(range(256))
HOST = "https://api.example.test"


def run_main(module, argv):
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def _entry(method, url, status, req_headers=(), post=None, resp_headers=(), content=None):
    req = {"method": method, "url": url, "httpVersion": "HTTP/1.1",
           "headers": [{"name": n, "value": v} for n, v in req_headers]}
    if post is not None:
        req["postData"] = post
    res = {"status": status, "httpVersion": "HTTP/1.1",
           "headers": [{"name": n, "value": v} for n, v in resp_headers], "content": content or {}}
    return {"startedDateTime": "2026-01-01T00:00:00.000Z", "request": req, "response": res}


def _har_doc():
    text_b64 = base64.b64encode(b"hello text body").decode()
    entries = [
        _entry("GET", HOST + "/api/data?page=2&access_token=tok-live-AAA111", 200,
               req_headers=[("Cookie", "session=cookie-sess-BBB222; theme=dark"),
                            ("Authorization", "Bearer bearer-EEE555")],
               resp_headers=[("content-type", "application/json")],
               content={"mimeType": "application/json",
                        "text": '{"access_token":"refresh-DDD444","items":[1]}'}),
        _entry("POST", HOST + "/api/login", 200,
               req_headers=[("content-type", "application/json")],
               post={"mimeType": "application/json", "params": [],
                     "text": '{"user":"u","ts":123,"sign":"abc","password":"pw-hunter2-CCC333"}'},
               resp_headers=[("Set-Cookie", "a=1; Path=/"), ("set-cookie", "b=2; Path=/")],
               content={"mimeType": "application/octet-stream", "encoding": "base64",
                        "text": base64.b64encode(BIN).decode()}),
        _entry("POST", HOST + "/api/noop", 204, post={"mimeType": "text/plain", "text": None}),
        _entry("POST", HOST + "/api/form", 200,
               req_headers=[("Content-Type", "application/x-www-form-urlencoded")],
               post={"mimeType": "application/x-www-form-urlencoded",
                     "text": "user=u&password=pw-hunter2-CCC333&sign=zz",
                     "params": [{"name": "user", "value": "u"},
                                {"name": "password", "value": "pw-hunter2-CCC333"},
                                {"name": "sign", "value": "zz"}]},
               content={"mimeType": "text/plain", "encoding": "base64", "text": text_b64}),
        "not-an-object",
        {"request": {"method": "GET"}, "response": {"status": 200}},
        {"request": {"method": "GET", "url": HOST + "/x"}, "response": {}},
    ]
    return {"log": {"version": "1.2", "creator": {"name": "fixture", "version": "0.1"},
                    "entries": entries}}


class HarParseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.capture = self.root / "capture.har"
        self.capture.write_text(json.dumps(_har_doc()), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, name, *extra):
        out = self.root / name
        code, _, err = run_main(har, [str(self.capture), "--out", str(out), *extra])
        self.assertEqual(code, 0, err)
        records = json.loads((out / "requests.json").read_text(encoding="utf-8"))
        manifest = json.loads((out / "har_manifest.json").read_text(encoding="utf-8"))
        return records, manifest, err

    def test_record_shape_matches_ecapture(self):
        records, manifest, _ = self._run("raw")
        self.assertEqual(len(records), 8)
        for rec in records:
            self.assertTrue(ECAP_KEYS <= set(rec), set(rec))
            self.assertLessEqual(set(rec) - ECAP_KEYS, HAR_EXTRA_KEYS)
        send, recv = records[0], records[1]
        self.assertEqual((send["direction"], send["host"], send["version"]),
                         ("send", "api.example.test", "HTTP/1.1"))
        self.assertEqual(send["path"], "/api/data?page=2&access_token=tok-live-AAA111")
        self.assertEqual((recv["direction"], recv["method"], recv["path"], recv["host"], recv["status"]),
                         ("recv", None, None, None, 200))
        self.assertEqual(records[3]["headers"]["Set-Cookie"], "a=1; Path=/, b=2; Path=/")
        self.assertTrue(records[3]["body"].startswith("binary body (256 bytes, sha256="))
        self.assertEqual(records[3]["body_sha256"], hashlib.sha256(BIN).hexdigest())
        self.assertEqual(records[4]["body"], "postData.text absent")
        self.assertEqual(records[5]["body"], "content.text absent")
        self.assertEqual(records[7]["body"], "hello text body")
        self.assertEqual(records[7]["body_sha256"], hashlib.sha256(b"hello text body").hexdigest())
        self.assertNotIn("form_params", records[2])  # params: [] does not create form_params
        self.assertEqual(records[6]["form_params"],
                         {"user": "u", "password": "pw-hunter2-CCC333", "sign": "zz"})
        self.assertEqual(records[2]["sig_candidates"]["sign"], "abc")
        self.assertEqual(records[2]["sig_candidates"]["ts"], 123)
        self.assertEqual(records[6]["sig_candidates"]["form.sign"], "zz")
        self.assertEqual(sorted(manifest["skipped_entries"], key=lambda s: s["entry_index"]),
                         [{"entry_index": 4, "reason": "entry is not an object"},
                          {"entry_index": 5, "reason": "request url missing"},
                          {"entry_index": 6, "reason": "response status missing"}])
        self.assertEqual(manifest["entry_count"], 7)
        self.assertEqual(manifest["record_count"], 8)
        self.assertEqual(manifest["host_counts"], {"api.example.test": 4})
        self.assertFalse(manifest["redaction"]["enabled"])
        self.assertIn("No redaction applied", manifest["redaction"]["notice"])

    def test_redaction_masks_secrets_and_keeps_signature_fields(self):
        records, manifest, _ = self._run("red", "--redact")
        blob = json.dumps(records) + json.dumps(manifest)
        for secret in ("tok-live-AAA111", "cookie-sess-BBB222", "bearer-EEE555",
                       "refresh-DDD444", "pw-hunter2-CCC333"):
            self.assertNotIn(secret, blob)
        self.assertEqual(records[0]["headers"]["Cookie"], "[REDACTED]")
        self.assertEqual(records[0]["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(records[0]["path"], "/api/data?page=2&access_token=[REDACTED]")
        self.assertEqual(records[3]["headers"]["Set-Cookie"], "[REDACTED]")
        self.assertIn('"access_token":"[REDACTED]"', records[1]["body"])
        self.assertIn('"sign":"abc"', records[2]["body"])
        self.assertIn('"ts":123', records[2]["body"])
        self.assertIn('"password":"[REDACTED]"', records[2]["body"])
        self.assertEqual(records[6]["body"], "user=u&password=[REDACTED]&sign=zz")
        self.assertEqual(records[6]["form_params"]["password"], "[REDACTED]")
        self.assertEqual(records[6]["form_params"]["sign"], "zz")
        self.assertEqual(records[6]["sig_candidates"]["form.sign"], "zz")
        self.assertEqual([r["redactions"] for r in records], [3, 2, 1, 1, 0, 0, 2, 0])
        self.assertEqual(manifest["redaction"], {"enabled": True, "total_redactions": 9,
                                                 "notice": None})

    def test_bad_capture_is_refused_and_existing_output_is_kept(self):
        bad = self.root / "bad.har"
        bad.write_text(json.dumps({"log": {"entries": {"not": "a list"}}}), encoding="utf-8")
        code, _, err = run_main(har, [str(bad), "--out", str(self.root / "o1")])
        self.assertEqual(code, 2)
        self.assertIn("log.entries is not a list", err)
        existing = self.root / "exists"
        existing.mkdir()
        code, _, err = run_main(har, [str(self.capture), "--out", str(existing)])
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)
        self.assertEqual(list(existing.iterdir()), [])


# --- source maps ---------------------------------------------------------------
def _map_bytes(sources, contents):
    return json.dumps({"version": 3, "sources": sources, "names": [], "mappings": "",
                       "sourcesContent": contents}).encode("utf-8")


class SourceMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.inp = self.root / "in"
        self.inp.mkdir()
        self.out = self.root / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_traversal_names_stay_inside_output(self):
        (self.inp / "bundle.js.map").write_bytes(
            _map_bytes(["../../x", "/abs", "webpack:///../../y", "C:\\z"], ["X", "A", "Y", "Z"]))
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        slug = self.out / "bundle.js.map"
        self.assertEqual(sorted(p.name for p in slug.iterdir()), ["abs", "x", "y", "z"])
        self.assertEqual((slug / "y").read_text(encoding="utf-8"), "Y")
        self.assertFalse(any((self.root / n).exists() for n in ("x", "abs", "y", "z")))
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        changed = {m["original"]: m["output"] for m in manifest["maps"][0]["sanitized_mappings"]}
        self.assertEqual(changed, {"../../x": "x", "/abs": "abs",
                                   "webpack:///../../y": "y", "C:\\z": "z"})

    def test_data_uri_map_is_decoded(self):
        inline = base64.b64encode(_map_bytes(["src/a.js"], ["A"])).decode()
        (self.inp / "app.js").write_bytes(
            b"console.log(1);\n//# sourceMappingURL=data:application/json;base64," +
            inline.encode() + b"\n")
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        self.assertEqual((self.out / "app.js_inline" / "src" / "a.js").read_text(encoding="utf-8"), "A")
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["maps"][0]["kind"], "inline")

    def test_missing_content_and_collisions_are_recorded(self):
        (self.inp / "m.map").write_bytes(_map_bytes(["a.js", "b.js"], [None, "B"]))
        (self.inp / "c.map").write_bytes(
            _map_bytes(["a/b.js", "a", "a/b.js/c.js", "a/b.js"], ["1", "2", "3", "4"]))
        (self.inp / "r.js").write_text("//# sourceMappingURL=https://cdn.example.test/r.js.map\n")
        (self.inp / "o.js").write_text("//# sourceMappingURL=../../outside.map\n")
        try:
            os.symlink(str(self.inp / "m.map"), str(self.inp / "alias.map"))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        by_path = {m["path"]: m for m in manifest["maps"]}
        self.assertEqual(by_path["m.map"]["missing_content"][0]["index"], 0)
        self.assertFalse((self.out / "m.map" / "a.js").exists())
        self.assertEqual((self.out / "m.map" / "b.js").read_text(encoding="utf-8"), "B")
        written = sorted(p.read_text(encoding="utf-8")
                         for p in (self.out / "c.map").rglob("*") if p.is_file())
        self.assertEqual(written, ["1", "2", "3", "4"])
        reasons = {r["js"]: r["reason"] for r in manifest["missing_map_refs"]}
        self.assertEqual(reasons["r.js"], "remote or scheme URL; not fetched")
        self.assertEqual(reasons["o.js"], "resolves outside INPUT")
        self.assertIn("alias.map", [s["path"] for s in manifest["skipped"]])

    def test_indexed_map_is_flattened_in_declared_order(self):
        indexed = {"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0},
             "map": json.loads(_map_bytes(["a.js", "shared.js"], ["A0", "S0"]))},
            {"offset": {"line": 10, "column": 0},
             "map": json.loads(_map_bytes(["b.js", "shared.js"], [None, "S1"]))},
            {"offset": {"line": 20, "column": 0}, "url": "https://cdn.example.test/c.map"},
        ]}
        (self.inp / "idx.map").write_bytes(json.dumps(indexed).encode("utf-8"))
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        entry = manifest["maps"][0]
        self.assertTrue(entry["indexed"])
        self.assertEqual(entry["sections"], 2)
        self.assertEqual(entry["sources_count"], 4)
        self.assertEqual(entry["written_count"], 3)
        self.assertEqual(entry["unresolved_sections"],
                         [{"section": "2", "reason": "section references a url; not fetched"}])
        self.assertEqual([(m["section"], m["index"]) for m in entry["missing_content"]], [("1", 0)])
        slug = self.out / entry["slug"]
        self.assertEqual((slug / "section-0" / "shared.js").read_text(encoding="utf-8"), "S0")
        self.assertEqual((slug / "section-1" / "shared.js").read_text(encoding="utf-8"), "S1")
        self.assertEqual((slug / "section-0" / "a.js").read_text(encoding="utf-8"), "A0")

    def test_indexed_map_without_embedded_sections_is_an_error_entry(self):
        (self.inp / "idx.map").write_bytes(json.dumps({"version": 3, "sections": [
            {"offset": {"line": 0, "column": 0}, "url": "x.map"}]}).encode("utf-8"))
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 1, err)
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["maps"][0]["error"], "indexed map has no embedded section maps")

    def test_bom_and_xssi_prefix_are_dropped(self):
        body = b"\xef\xbb\xbf)]}'\n" + _map_bytes(["src/a.js"], ["A"])
        (self.inp / "framed.map").write_bytes(body)
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        self.assertEqual((self.out / "framed.map" / "src" / "a.js").read_text(encoding="utf-8"), "A")

    def test_existing_output_is_refused(self):
        (self.inp / "x.map").write_bytes(_map_bytes(["a.js"], ["A"]))
        self.out.mkdir()
        (self.out / "keep.txt").write_text("keep", encoding="utf-8")
        code, _, err = run_main(sourcemap, [str(self.inp), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)
        self.assertEqual((self.out / "keep.txt").read_text(encoding="utf-8"), "keep")


# --- ASAR ----------------------------------------------------------------------
def write_asar(path, tree, unpacked=(), block_size=16, flip=None):
    """Write an archive in the verified layout: 16-byte prefix, JSON, padding, data."""
    data = bytearray()

    def build(node, prefix):
        files = {}
        for name, value in node.items():
            rel = prefix + name
            if isinstance(value, dict):
                files[name] = {"files": build(value, rel + "/")}
            elif isinstance(value, tuple):
                files[name] = {"link": value[1]}
            else:
                blocks = [hashlib.sha256(value[i:i + block_size]).hexdigest()
                          for i in range(0, max(len(value), 1), block_size)]
                entry = {"size": len(value), "integrity": {
                    "algorithm": "SHA256", "hash": hashlib.sha256(value).hexdigest(),
                    "blockSize": block_size, "blocks": blocks}}
                if rel in unpacked:
                    entry["unpacked"] = True
                else:
                    entry["offset"] = str(len(data))
                    data.extend(value)
                files[name] = entry
        return files

    raw = json.dumps({"files": build(tree, "")}, separators=(",", ":")).encode("utf-8")
    payload = 4 + ((len(raw) + 3) & ~3)
    head = struct.pack("<4I", 4, payload + 4, payload, len(raw)) + raw
    head += b"\0" * (12 + payload - len(head))
    if flip is not None:
        data[flip] ^= 0xFF
    Path(path).write_bytes(bytes(head) + bytes(data))


class AsarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.arc = self.root / "app.asar"
        self.out = self.root / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def _manifest(self):
        return json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))

    def test_extracts_tree_and_verifies_blocks(self):
        tree = {"app.js": b"console.log('x')\n" * 3,
                "lib": {"util.js": b"module.exports = 1;\n", "deep": {"big.bin": BIN}},
                "empty": {}, "empty.txt": b""}
        write_asar(self.arc, tree)
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        self.assertEqual((self.out / "app.js").read_bytes(), tree["app.js"])
        self.assertEqual((self.out / "lib" / "deep" / "big.bin").read_bytes(), BIN)
        self.assertEqual((self.out / "empty.txt").read_bytes(), b"")
        self.assertTrue((self.out / "empty").is_dir())
        counts = self._manifest()["counts"]
        self.assertEqual(counts["integrity"]["verified"], 4)
        self.assertEqual(counts["integrity_mismatches"], 0)

    def test_traversal_names_are_rejected(self):
        tree = {"ok.txt": b"ok", "../evil.txt": b"evil", "/abs.txt": b"abs",
                "a\\b.txt": b"bs", "..": b"dots"}
        write_asar(self.arc, tree)
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["manifest.json", "ok.txt"])
        self.assertFalse((self.root / "evil.txt").exists())
        rejected = [e for e in self._manifest()["entries"] if e["kind"] == "rejected"]
        self.assertEqual(len(rejected), 4)
        self.assertTrue(all(e["skip_reason"] for e in rejected))

    def test_integrity_mismatch_is_recorded_and_file_still_written(self):
        tree = {"a.js": b"A" * 40, "b.js": b"B" * 40}
        write_asar(self.arc, tree, flip=5)
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 0)
        self.assertIn("integrity mismatch", err)
        tampered = b"A" * 5 + bytes([ord("A") ^ 0xFF]) + b"A" * 34
        self.assertEqual((self.out / "a.js").read_bytes(), tampered)
        manifest = self._manifest()
        self.assertEqual(manifest["integrity_mismatches"], ["a.js"])
        self.assertIn("block(s) 0 differ", [e for e in manifest["entries"]
                                             if e["path"] == "a.js"][0]["integrity_reason"])

    def test_unpacked_entry_is_unavailable_without_companion(self):
        tree = {"app.js": b"js", "native.node": b"NATIVE-BYTES"}
        write_asar(self.arc, tree, unpacked={"native.node"})
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        self.assertFalse((self.out / "native.node").exists())
        entry = [e for e in self._manifest()["entries"] if e["path"] == "native.node"][0]
        self.assertTrue(entry["unpacked"])
        self.assertFalse(entry["extracted"])
        self.assertIn("no companion directory", entry["skip_reason"])
        self.assertEqual(entry["integrity"], "unavailable")

        # With the default companion directory beside the archive, the bytes are used and verified.
        second = self.root / "out2"
        companion = self.root / "app.asar.unpacked"
        companion.mkdir()
        (companion / "native.node").write_bytes(b"NATIVE-BYTES")
        code, _, err = run_main(asar, [str(self.arc), "--out", str(second)])
        self.assertEqual(code, 0, err)
        self.assertEqual((second / "native.node").read_bytes(), b"NATIVE-BYTES")
        entry = [e for e in json.loads((second / "manifest.json").read_text(encoding="utf-8"))["entries"]
                 if e["path"] == "native.node"][0]
        self.assertEqual(entry["integrity"], "verified")

    def test_links_are_recorded_not_created(self):
        write_asar(self.arc, {"real.js": b"r", "alias.js": ("link", "real.js")})
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.lexists(self.out / "alias.js"))
        link = [e for e in self._manifest()["entries"] if e["kind"] == "link"][0]
        self.assertEqual(link["link_target"], "real.js")

    def test_header_layout_violation_fails_without_writing(self):
        write_asar(self.arc, {"a.js": b"A"})
        raw = bytearray(self.arc.read_bytes())
        raw[0:4] = struct.pack("<I", 5)
        self.arc.write_bytes(bytes(raw))
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 1)
        self.assertIn("layout check failed", err)
        self.assertFalse(self.out.exists())

    def test_existing_output_is_refused(self):
        write_asar(self.arc, {"a.js": b"A"})
        self.out.mkdir()
        code, _, err = run_main(asar, [str(self.arc), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)


if __name__ == "__main__":
    unittest.main()
