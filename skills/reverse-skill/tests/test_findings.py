#!/usr/bin/env python3
"""Tests for scripts/findings.py: R3 verification rule, dispositions, provenance."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FINDINGS = os.path.join(HERE, "..", "scripts", "findings.py")


def run(out, *args):
    cmd = [sys.executable, FINDINGS, "--out", out] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


class FindingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "session")

    def tearDown(self):
        self.tmp.cleanup()

    def init(self, *extra):
        r = run(self.out, "init", "--target", "com.example.aa", *extra)
        self.assertEqual(r.returncode, 0, r.stderr)

    def load(self):
        with open(os.path.join(self.out, "findings.json"), encoding="utf-8") as f:
            return json.load(f)

    # --- provenance -------------------------------------------------------
    def test_init_records_input_hash(self):
        inp = os.path.join(self.tmp.name, "app.bin")
        with open(inp, "wb") as f:
            f.write(b"mobile app bytes")
        self.init("--input", inp)
        data = self.load()
        self.assertEqual(data["input"]["sha256"], hashlib.sha256(b"mobile app bytes").hexdigest())
        self.assertEqual(data["input"]["size"], len(b"mobile app bytes"))

    def test_init_refuses_existing_ledger(self):
        self.init()
        r = run(self.out, "init", "--target", "again")
        self.assertNotEqual(r.returncode, 0)

    def test_add_tool_records_sha256_and_version(self):
        self.init()
        tool = os.path.join(self.tmp.name, "unblob-stub")
        with open(tool, "wb") as f:
            f.write(b"#!/bin/sh\n")
        r = run(self.out, "add-tool", "--name", "unblob", "--path", tool, "--version", "26.6.4")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load()
        self.assertEqual(data["tools"][0]["version"], "26.6.4")
        self.assertEqual(data["tools"][0]["sha256"], hashlib.sha256(b"#!/bin/sh\n").hexdigest())
        self.assertIn("tool   : unblob 26.6.4", run(self.out, "show").stdout)

    def test_add_tool_rejects_missing_binary(self):
        self.init()
        r = run(self.out, "add-tool", "--name", "x",
                "--path", os.path.join(self.tmp.name, "nope"), "--version", "1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not a regular file", r.stderr)

    def test_legacy_ledger_without_provenance_keys_still_validates(self):
        os.makedirs(self.out)
        legacy = {"target": "t", "goal": "g", "phase": 0, "facts": [],
                  "intents": [], "hypotheses": [], "artifacts": {}}
        with open(os.path.join(self.out, "findings.json"), "w", encoding="utf-8") as f:
            json.dump(legacy, f)
        self.assertEqual(run(self.out, "show").returncode, 0)
        self.assertEqual(run(self.out, "validate").returncode, 0)

    # --- R3 verification strength ----------------------------------------
    def test_verified_needs_two_samples_and_control(self):
        self.init()
        r = run(self.out, "add-fact", "--claim", "X-Sign reproduces", "--rung", "VERIFIED",
                "--verbatim", "sign = hmac(...)", "--sample", "cap1", "--sample", "cap2")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("R3 violation: f1", v.stdout)
        s = run(self.out, "set-fact", "--id", "f1", "--control", "cap3-perturbed")
        self.assertEqual(s.returncode, 0, s.stderr)
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_one_sample_is_not_enough(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "VERIFIED", "--verbatim", "q",
            "--sample", "cap1", "--control", "cap2-perturbed")
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("1 distinct sample(s)", v.stdout)

    def test_duplicate_samples_count_once(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "VERIFIED", "--verbatim", "q",
            "--sample", "cap1", "--sample", "cap1", "--control", "cap2-perturbed")
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("1 distinct sample(s)", v.stdout)

    def test_control_must_differ_from_samples(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "VERIFIED", "--verbatim", "q",
            "--sample", "cap1", "--sample", "cap2", "--control", "cap1")
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("also listed as a sample", v.stdout)

    def test_confirmed_hypothesis_warns_without_r3_fact(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "VERIFIED", "--verbatim", "q",
            "--sample", "cap1")
        run(self.out, "add-hypothesis", "--claim", "x", "--confidence", "low")
        run(self.out, "set-hypothesis", "--id", "h1", "--status", "confirmed")
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("no VERIFIED fact meets R3", v.stdout)

    # --- dispositions -----------------------------------------------------
    def test_dispositions_are_accepted_and_reported_not_verified(self):
        self.init()
        run(self.out, "add-fact", "--claim", "live replay", "--status", "out_of_scope")
        run(self.out, "add-hypothesis", "--claim", "X-Sign = HMAC-SHA256",
            "--primitive", "HMAC-SHA256", "--confidence", "medium",
            "--fingerprint", "constscan:sha256_k@0x10")
        run(self.out, "set-hypothesis", "--id", "h1", "--status", "blocked")
        v = run(self.out, "validate")
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertIn("f1 is out_of_scope", v.stdout)
        self.assertIn("h1 is blocked", v.stdout)

    def test_blocked_fact_status_is_accepted(self):
        self.init()
        r = run(self.out, "add-fact", "--claim", "c", "--status", "blocked")
        self.assertEqual(r.returncode, 0, r.stderr)

    # --- R1 / R2 still enforced ------------------------------------------
    def test_r2_still_blocks_unfingerprinted_primitive(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "X-Sign = AES-CBC", "--confidence", "medium")
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("R2 violation: h1", v.stdout)

    def test_r1_still_requires_verbatim_quote(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "REACHABLE")
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("R1 violation: f1", v.stdout)


if __name__ == "__main__":
    unittest.main()
