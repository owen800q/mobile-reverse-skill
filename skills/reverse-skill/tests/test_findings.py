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
            f.write(b"firmware bytes")
        self.init("--input", inp)
        data = self.load()
        self.assertEqual(data["input"]["sha256"], hashlib.sha256(b"firmware bytes").hexdigest())
        self.assertEqual(data["input"]["size"], len(b"firmware bytes"))

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

    # --- coverage ---------------------------------------------------------
    def test_coverage_is_one_record_per_area_and_updates_in_place(self):
        self.init()
        r = run(self.out, "add-coverage", "--area", "smali classes", "--examined", "40",
                "--total", "120", "--note", "excludes generated R classes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("coverage smali classes: 40 of 120 (33%)", r.stdout)
        run(self.out, "add-coverage", "--area", "smali classes", "--examined", "120", "--total", "120")
        cov = self.load()["coverage"]
        self.assertEqual(len(cov), 1)
        self.assertEqual((cov[0]["examined"], cov[0]["total"]), (120, 120))
        self.assertEqual(cov[0]["note"], "")

    def test_partial_coverage_is_info_and_keeps_the_note(self):
        self.init()
        run(self.out, "add-coverage", "--area", "smali classes", "--examined", "40",
            "--total", "120", "--note", "excludes generated R classes")
        v = run(self.out, "validate")
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertIn("INFO  coverage 'smali classes' examined 40 of 120 (33%): "
                      "excludes generated R classes", v.stdout)
        self.assertIn("coverage (1):", run(self.out, "show").stdout)

    def test_complete_coverage_adds_no_coverage_note(self):
        self.init()
        run(self.out, "add-coverage", "--area", "rootfs ELF binaries", "--examined", "7", "--total", "7")
        v = run(self.out, "validate")
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertNotIn("coverage", v.stdout)

    def test_coverage_rejects_impossible_counts(self):
        self.init()
        for examined, total in (("5", "3"), ("-1", "3"), ("0", "0")):
            with self.subTest(examined=examined, total=total):
                r = run(self.out, "add-coverage", "--area", "x", "--examined", examined,
                        "--total", total)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("needs 0 <= examined <= total", r.stderr)
        self.assertEqual(self.load()["coverage"], [])

    def test_validate_flags_hand_edited_impossible_coverage(self):
        self.init()
        data = self.load()
        data["coverage"] = [{"area": "x", "examined": 5, "total": 3, "note": ""}]
        with open(os.path.join(self.out, "findings.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        v = run(self.out, "validate")
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("FAIL  coverage 'x': examined=5 total=3", v.stdout)

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

    # --- absence, authority and hypothesis links --------------------------
    def test_absence_claim_needs_complete_coverage(self):
        self.init()
        r = run(self.out, "add-coverage", "--area", "smali", "--examined", "40", "--total", "120")
        self.assertEqual(r.returncode, 0, r.stderr)
        run(self.out, "add-fact", "--claim", "no pinning", "--rung", "PATTERN", "--absence",
            "--coverage-area", "smali", "--authority", "tool_output")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("absence claim over partial coverage", r.stdout)

        run(self.out, "add-coverage", "--area", "smali", "--examined", "120", "--total", "120")
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_absence_claim_without_coverage_record_fails(self):
        self.init()
        run(self.out, "add-fact", "--claim", "no root check", "--absence", "--coverage-area", "dex")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no coverage record", r.stdout)

    def test_analyst_note_cannot_carry_a_rung_above_controllable(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign is exploitable", "--rung", "EXPLOITABLE",
            "--authority", "analyst_note", "--verbatim", "x", "--tool", "t")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("only authority is analyst_note", r.stdout)

    def test_analyst_note_at_controllable_is_allowed(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign runs", "--rung", "CONTROLLABLE",
            "--authority", "analyst_note", "--verbatim", "x", "--tool", "t")
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_hypothesis_links_must_name_existing_facts(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "AES key schedule", "--primitive", "AES",
            "--supports", "f9")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("links to unknown fact f9", r.stdout)

    def test_confirmed_hypothesis_contradicted_by_confirmed_fact_fails(self):
        self.init()
        run(self.out, "add-fact", "--claim", "block size is 16", "--rung", "REACHABLE",
            "--verbatim", "16", "--status", "confirmed")
        run(self.out, "add-hypothesis", "--claim", "AES-256 cipher", "--contradicts", "f1")
        run(self.out, "set-hypothesis", "--id", "h1", "--status", "confirmed")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("contradicted by confirmed fact", r.stdout)

    def test_confirmed_hypothesis_without_support_warns(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "custom signer")
        run(self.out, "set-hypothesis", "--id", "h1", "--status", "confirmed")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no supporting fact linked", r.stdout)

    def test_unknown_authority_is_rejected_by_the_parser(self):
        self.init()
        r = run(self.out, "add-fact", "--claim", "x", "--authority", "hearsay")
        self.assertNotEqual(r.returncode, 0)

    # --- artifact binding and report checks -------------------------------
    def write_artifact(self, name, text):
        path = os.path.join(self.out, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return name

    def test_artifact_digest_is_recorded_and_detects_tampering(self):
        self.init()
        art = self.write_artifact("ida/sign.c", "int sign(void) { return 42; }\n")
        r = run(self.out, "add-fact", "--claim", "sign returns 42", "--rung", "REACHABLE",
                "--artifact", art, "--verbatim", "return 42;")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(run(self.out, "validate").returncode, 0)
        self.write_artifact("ida/sign.c", "int sign(void) { return 7; }\n")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed since it was recorded", r.stdout)

    def test_verbatim_must_appear_in_its_artifact(self):
        self.init()
        art = self.write_artifact("dump.txt", "POST /login\n")
        run(self.out, "add-fact", "--claim", "login", "--rung", "REACHABLE",
            "--artifact", art, "--verbatim", "POST /logout")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("verbatim quote not found", r.stdout)

    def test_artifact_outside_the_session_is_refused(self):
        self.init()
        outside = os.path.join(self.tmp.name, "elsewhere.txt")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("x")
        r = run(self.out, "add-fact", "--claim", "x", "--artifact", outside)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("inside the session directory", r.stderr)

    def test_sample_artifact_binding_is_digested_and_unbound_samples_warn(self):
        self.init()
        art = self.write_artifact("captures/s1.txt", "request body")
        run(self.out, "add-fact", "--claim", "sig", "--rung", "VERIFIED",
            "--verbatim", "request body", "--tool", "ecapture",
            "--sample", "s1", "--sample", "s2", "--sample-artifact", "s1=" + art,
            "--control", "c1")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("not bound to an artifact: s2", r.stdout)

    def write_report(self, text):
        path = os.path.join(self.tmp.name, "report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_check_report_accepts_a_faithful_citation(self):
        self.init()
        run(self.out, "add-fact", "--claim", "login path", "--rung", "REACHABLE",
            "--verbatim", "POST /api/v2/auth/login")
        report = self.write_report('Login is "POST /api/v2/auth/login" [f1].\n')
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_report_rejects_unknown_refuted_and_misquoted_citations(self):
        self.init()
        run(self.out, "add-fact", "--claim", "old path", "--verbatim", "GET /v1/x", "--status", "refuted")
        run(self.out, "add-fact", "--claim", "login", "--verbatim", "POST /api/v2/auth/login")
        report = self.write_report(
            "Unknown [f9].\n"
            "Refuted [f1].\n"
            'Misquoted "POST /api/v1/auth/login" [f2].\n')
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown fact f9", r.stdout)
        self.assertIn("refuted fact f1", r.stdout)
        self.assertIn("not in the verbatim evidence", r.stdout)

    def test_check_report_rejects_a_rung_claim_above_the_cited_fact(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign exists", "--rung", "PATTERN", "--verbatim", "sign(")
        report = self.write_report("The sign routine is VERIFIED [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("claims VERIFIED", r.stdout)

    def test_check_report_refuses_an_absence_without_complete_coverage(self):
        self.init()
        run(self.out, "add-coverage", "--area", "smali", "--examined", "1", "--total", "9")
        run(self.out, "add-fact", "--claim", "no pinning", "--absence", "--coverage-area", "smali")
        report = self.write_report("No pinning in the login path [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("without complete coverage", r.stdout)


if __name__ == "__main__":
    unittest.main()
