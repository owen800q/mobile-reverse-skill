#!/usr/bin/env python3
"""Tests for scripts/findings.py: R3 verification rule, dispositions, provenance."""
import copy
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
        r = run(self.out, "add-coverage", "--area", "smali", "--examined", "40", "--total", "120",
                "--note", "smali classes after the first 40 were not read")
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
        run(self.out, "add-coverage", "--area", "smali", "--examined", "1", "--total", "9",
            "--note", "only the login package was read")
        run(self.out, "add-fact", "--claim", "no pinning", "--absence", "--coverage-area", "smali")
        report = self.write_report("No pinning in the login path [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("without complete coverage", r.stdout)

    # --- helpers for the tests below --------------------------------------
    def fresh(self, name):
        out = os.path.join(self.tmp.name, name)
        r = run(out, "init", "--target", "t")
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def save(self, data):
        with open(os.path.join(self.out, "findings.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)

    # --- provenance: what is recorded, and what is not checked ------------
    def test_init_without_input_records_no_input_hash(self):
        self.init()
        self.assertIsNone(self.load()["input"])

    def test_add_tool_records_the_version_as_passed_and_does_not_run_the_binary(self):
        self.init()
        marker = os.path.join(self.tmp.name, "ran.marker")
        tool = os.path.join(self.tmp.name, "stub-tool")
        with open(tool, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n: > '%s'\necho 1.0\n" % marker)
        os.chmod(tool, 0o755)
        r = run(self.out, "add-tool", "--name", "stub", "--path", tool, "--version", "99.9.9")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load()["tools"][0]["version"], "99.9.9")
        self.assertFalse(os.path.exists(marker), "add-tool must not run the binary")

    def test_fact_tool_is_free_text_and_not_checked_against_tools(self):
        self.init()
        r = run(self.out, "add-fact", "--claim", "c", "--rung", "REACHABLE",
                "--verbatim", "POST /api/v2/auth/login", "--tool", "no-such-tool")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_init_leaves_endpoints_requests_protocol_map_and_artifacts_empty(self):
        self.init()
        data = self.load()
        self.assertEqual(data["endpoints"], [])
        self.assertEqual(data["requests"], [])
        self.assertEqual(data["protocol_map"],
                         {"auth_fields": [], "signature_fields": [], "endpoint_parameter_map": {}})
        self.assertEqual(data["artifacts"], {})

    def test_no_findings_command_writes_endpoints_requests_protocol_map_or_artifacts(self):
        self.init()
        tool = os.path.join(self.tmp.name, "tool-bin")
        with open(tool, "wb") as f:
            f.write(b"bin")
        art = self.write_artifact("ida/sign.c", "int sign(void) { return 42; }\n")
        self.assertEqual(run(self.out, "add-tool", "--name", "idat", "--path", tool,
                             "--version", "8.3").returncode, 0)
        self.assertEqual(run(self.out, "set-phase", "2").returncode, 0)
        self.assertEqual(run(self.out, "add-fact", "--claim", "sign returns 42", "--rung", "REACHABLE",
                             "--artifact", art, "--verbatim", "return 42;").returncode, 0)
        self.assertEqual(run(self.out, "add-coverage", "--area", "dex", "--examined", "1",
                             "--total", "2", "--note", "one of two").returncode, 0)
        self.assertEqual(run(self.out, "add-intent", "--from-phase", "3", "--target",
                             "libsec.so:sign", "--reason", "native").returncode, 0)
        self.assertEqual(run(self.out, "add-hypothesis", "--claim", "X-Sign").returncode, 0)
        self.assertEqual(run(self.out, "set-hypothesis", "--id", "h1", "--status", "proposed").returncode, 0)
        data = self.load()
        self.assertEqual(data["endpoints"], [])
        self.assertEqual(data["requests"], [])
        self.assertEqual(data["protocol_map"]["auth_fields"], [])
        self.assertEqual(data["artifacts"], {})
        # The bound artifact is stored inside the fact that cites it.
        self.assertEqual(data["facts"][0]["evidence"][0]["artifact"]["path"], "ida/sign.c")

    def test_write_commands_refuse_unknown_ids_and_store_an_unchecked_coverage_area(self):
        self.init()
        r = run(self.out, "set-fact", "--id", "f9", "--status", "open")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no fact f9", r.stderr)
        r = run(self.out, "set-hypothesis", "--id", "h9", "--confidence", "high")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no hypothesis h9", r.stderr)
        # --coverage-area is stored on a non-absence fact and not checked against coverage.
        r = run(self.out, "add-fact", "--claim", "login", "--rung", "REACHABLE",
                "--verbatim", "POST /api/v2/auth/login", "--coverage-area", "no such area")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load()["facts"][0]["coverage_area"], "no such area")
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_facts_have_a_rung_and_status_but_no_confidence_field(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "REACHABLE", "--verbatim", "quoted text here")
        fact = self.load()["facts"][0]
        self.assertNotIn("confidence", fact)
        self.assertIn("rung", fact)
        self.assertIn("status", fact)

    # --- R1 as documented: a non-blank verbatim string, nothing more -------
    def test_r1_accepts_a_paraphrase_when_no_artifact_is_bound(self):
        self.init()
        run(self.out, "add-fact", "--claim", "flow", "--rung", "REACHABLE",
            "--verbatim", "I'm confident the flow goes A to B to C")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_r1_rejects_a_blank_verbatim_string(self):
        self.init()
        run(self.out, "add-fact", "--claim", "flow", "--rung", "REACHABLE", "--verbatim", "   ")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("R1 violation: f1", r.stdout)

    def test_pattern_fact_may_have_no_evidence(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c")
        self.assertEqual(run(self.out, "validate").returncode, 0)

    # --- R2 as documented: substring names, counted entries ----------------
    def test_r2_does_not_read_fingerprint_labels_or_text(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "X-Sign = AES-128", "--confidence", "medium",
            "--fingerprint", "constscan:alu_only:0x9e3779b9")
        run(self.out, "add-hypothesis", "--claim", "Y-Sign = AES-128", "--confidence", "medium",
            "--fingerprint", "trust me")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_r2_warns_for_high_with_one_entry_and_counts_a_repeated_entry_twice(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "X-Sign = SHA-256", "--primitive", "sha256",
            "--confidence", "high", "--fingerprint", "constscan:sha256_k@0x10")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN  h1 is high confidence with only 1 fingerprint(s)", r.stdout)
        run(self.out, "add-hypothesis", "--claim", "Y-Sign = SHA-256", "--primitive", "sha256",
            "--confidence", "high", "--fingerprint", "cryptoinstr:sha256h",
            "--fingerprint", "cryptoinstr:sha256h")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("WARN  h2", r.stdout)

    def test_r2_matches_names_by_substring_only(self):
        # 'ecc' is inside 'keccak', so it is caught. PBKDF2, SHA-384 and Curve25519
        # contain none of the PRIMITIVE_TOKENS substrings, so they are not checked.
        cases = (("Keccak-256 signer", 1), ("PBKDF2 key derivation", 0),
                 ("SHA-384 digest", 0), ("Curve25519 ECDH", 0))
        for i, (claim, rc) in enumerate(cases):
            with self.subTest(claim=claim):
                out = self.fresh("case%d" % i)
                run(out, "add-hypothesis", "--claim", claim, "--confidence", "medium")
                self.assertEqual(run(out, "validate").returncode, rc)

    def test_r2_tests_the_primitive_field_when_given_and_not_the_claim(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "X-Sign = AES-128-CBC(key, body)",
            "--primitive", "block cipher", "--confidence", "medium")
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_write_commands_accept_medium_without_fingerprint_and_validate_reports_it(self):
        self.init()
        r = run(self.out, "add-hypothesis", "--claim", "X-Sign = HMAC-SHA256", "--confidence", "high")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run(self.out, "add-hypothesis", "--claim", "Y-Sign = AES", "--confidence", "low")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run(self.out, "set-hypothesis", "--id", "h2", "--confidence", "medium")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run(self.out, "validate")
        self.assertEqual(v.returncode, 1)
        self.assertIn("R2 violation: h1", v.stdout)
        self.assertIn("R2 violation: h2", v.stdout)

    # --- R3 as documented: distinct labels and a control label -------------
    def test_add_fact_stores_a_verified_fact_without_samples_and_validate_fails(self):
        self.init()
        r = run(self.out, "add-fact", "--claim", "sign", "--rung", "VERIFIED", "--verbatim", "sign(body)")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(run(self.out, "validate").returncode, 1)

    def test_r3_counts_labels_so_two_samples_bound_to_one_file_pass(self):
        self.init()
        art = self.write_artifact("captures/one.txt", "request body")
        run(self.out, "add-fact", "--claim", "sig", "--rung", "VERIFIED", "--verbatim", "request body",
            "--sample", "s1", "--sample", "s2", "--control", "c1",
            "--sample-artifact", "s1=" + art, "--sample-artifact", "s2=" + art)
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("validate: OK (0 warning(s))", r.stdout)

    # --- dispositions -------------------------------------------------------
    def test_dispositions_are_info_in_validate_and_store_no_reason(self):
        self.init()
        r = run(self.out, "add-fact", "--claim", "c", "--status", "blocked", "--reason", "no device")
        self.assertEqual(r.returncode, 2)
        run(self.out, "add-fact", "--claim", "c", "--status", "blocked")
        fact = self.load()["facts"][0]
        self.assertEqual(fact["status"], "blocked")
        self.assertNotIn("reason", fact)
        v = run(self.out, "validate")
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertIn("INFO  f1 is blocked (not counted as verified)", v.stdout)

    def test_a_blocked_verified_fact_does_not_satisfy_a_confirmed_hypothesis(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign", "--rung", "VERIFIED", "--verbatim", "sign(body)",
            "--sample", "cap1", "--sample", "cap2", "--control", "cap3-perturbed", "--status", "blocked")
        run(self.out, "add-hypothesis", "--claim", "custom signer", "--confidence", "low")
        run(self.out, "set-hypothesis", "--id", "h1", "--status", "confirmed")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no VERIFIED fact meets R3", r.stdout)

    def test_a_blocked_fact_does_not_support_a_confirmed_hypothesis(self):
        self.init()
        run(self.out, "add-fact", "--claim", "login path", "--rung", "REACHABLE",
            "--verbatim", "POST /login/x", "--status", "blocked")
        run(self.out, "add-hypothesis", "--claim", "custom signer", "--supports", "f1")
        run(self.out, "set-hypothesis", "--id", "h1", "--status", "confirmed")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no supporting fact linked", r.stdout)

    def test_a_blocked_absence_claim_needs_no_coverage(self):
        self.init()
        run(self.out, "add-fact", "--claim", "no pinning", "--absence", "--coverage-area", "smali",
            "--status", "out_of_scope")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("f1 is out_of_scope", r.stdout)

    # --- coverage -----------------------------------------------------------
    def test_partial_coverage_without_a_note_exits_2_and_writes_nothing(self):
        self.init()
        for extra in ([], ["--note", ""], ["--note", "   "]):
            with self.subTest(extra=extra):
                r = run(self.out, "add-coverage", "--area", "smali classes", "--examined", "40",
                        "--total", "120", *extra)
                self.assertEqual(r.returncode, 2)
                self.assertIn("partial coverage needs --note saying what was left out", r.stderr)
        self.assertEqual(self.load()["coverage"], [])

    def test_a_partial_update_without_a_note_is_refused_and_keeps_the_old_record(self):
        self.init()
        run(self.out, "add-coverage", "--area", "smali", "--examined", "40", "--total", "120",
            "--note", "excludes generated R classes")
        r = run(self.out, "add-coverage", "--area", "smali", "--examined", "60", "--total", "120")
        self.assertEqual(r.returncode, 2)
        cov = self.load()["coverage"]
        self.assertEqual((cov[0]["examined"], cov[0]["note"]), (40, "excludes generated R classes"))

    def test_complete_coverage_needs_no_note(self):
        self.init()
        r = run(self.out, "add-coverage", "--area", "rootfs ELF binaries", "--examined", "7", "--total", "7")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_non_absence_finding_gets_no_partial_coverage_notice_from_check_report(self):
        self.init()
        run(self.out, "add-coverage", "--area", "smali", "--examined", "1", "--total", "9",
            "--note", "only the login package")
        run(self.out, "add-fact", "--claim", "login path", "--rung", "REACHABLE",
            "--verbatim", "POST /api/v2/auth/login")
        report = self.write_report('Login is "POST /api/v2/auth/login" [f1].\n')
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("coverage", r.stdout)

    def test_validate_fails_impossible_coverage_counts_in_a_hand_edited_ledger(self):
        self.init()
        for examined, total in ((-1, 3), (0, 0)):
            with self.subTest(examined=examined, total=total):
                data = self.load()
                data["coverage"] = [{"area": "x", "examined": examined, "total": total, "note": ""}]
                self.save(data)
                r = run(self.out, "validate")
                self.assertEqual(r.returncode, 1)
                self.assertIn("FAIL  coverage 'x'", r.stdout)

    # --- citations and quotes in check-report -------------------------------
    def test_check_report_reads_a_bracketed_list_as_two_citations(self):
        self.init()
        run(self.out, "add-fact", "--claim", "login path", "--rung", "REACHABLE",
            "--verbatim", "POST /api/v2/auth/login")
        run(self.out, "add-fact", "--claim", "old path", "--verbatim", "GET /v1/x", "--status", "refuted")
        report = self.write_report('Login is "POST /api/v2/auth/login" [f1, f9].\n'
                                   "Old path [f1,f2].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("line 1 cites unknown fact f9", r.stdout)
        self.assertNotIn("line 1 cites unknown fact f1", r.stdout)
        self.assertIn("line 2 cites refuted fact f2", r.stdout)
        self.assertIn("check-report: 2 cited line(s), 2 error(s)", r.stdout)

    def test_check_report_checks_rung_and_quotes_against_every_id_in_a_list(self):
        self.init()
        run(self.out, "add-fact", "--claim", "login path", "--rung", "PATTERN",
            "--verbatim", "POST /api/v2/auth/login")
        run(self.out, "add-fact", "--claim", "sign", "--rung", "REACHABLE", "--verbatim", "sign(body)")
        report = self.write_report("The sign is VERIFIED [f1, f2].\n"
                                   'Login is "sign(body)" [f1, f2].\n')
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("line 1 claims VERIFIED but the cited fact(s) reach at most REACHABLE", r.stdout)
        self.assertNotIn("FAIL  line 2", r.stdout)
        self.assertIn("check-report: 2 cited line(s), 1 error(s)", r.stdout)

    def test_curly_quoted_phrase_on_a_cited_line_is_checked(self):
        self.init()
        run(self.out, "add-fact", "--claim", "login path", "--rung", "REACHABLE",
            "--verbatim", "POST /api/v2/auth/login")
        report = self.write_report("Login is “POST /api/v2/auth/login” [f1].\n")
        self.assertEqual(run(self.out, "check-report", "--report", report).returncode, 0)
        report = self.write_report("Login is “POST /api/v1/auth/login” [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not in the verbatim evidence", r.stdout)

    def test_curly_quoted_phrase_on_an_uncited_line_is_warned(self):
        self.init()
        report = self.write_report("The flow is “POST /api/v2/auth/login” in the app.\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN  line 1 quotes text with no fact citation", r.stdout)

    def test_quotes_under_eight_characters_are_not_checked(self):
        self.init()
        run(self.out, "add-fact", "--claim", "login", "--rung", "REACHABLE", "--verbatim", "POST /login")
        report = self.write_report('Short “abc” and "xyz" [f1].\n')
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("not in the verbatim", r.stdout)

    def test_hypothesis_only_line_gets_no_rung_or_quote_check(self):
        self.init()
        run(self.out, "add-hypothesis", "--claim", "custom signer", "--confidence", "low")
        report = self.write_report('The signer is VERIFIED, per "an invented quote here" [h1].\n')
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("check-report: 1 cited line(s), 0 error(s), 0 warning(s)", r.stdout)

    def test_rung_words_are_matched_only_in_capitals(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign exists", "--rung", "PATTERN", "--verbatim", "sign(")
        report = self.write_report("The sign routine is verified [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_report_uses_a_blocked_facts_rung_and_warns_about_the_status(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign", "--rung", "VERIFIED", "--verbatim", "sign(body)",
            "--sample", "cap1", "--sample", "cap2", "--control", "cap3-perturbed", "--status", "blocked")
        report = self.write_report("The sign is VERIFIED [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN  line 1 cites blocked fact f1", r.stdout)

    # --- authority ----------------------------------------------------------
    def test_authority_label_is_not_checked_against_the_evidence(self):
        self.init()
        run(self.out, "add-fact", "--claim", "sign is exploitable", "--rung", "EXPLOITABLE",
            "--authority", "tool_output", "--verbatim", "the analyst believes the sign is exploitable")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_fact_above_pattern_without_authority_gets_an_info_line(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "REACHABLE", "--verbatim", "some quoted text")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("INFO  f1 has no authority recorded", r.stdout)

    def test_pattern_fact_without_authority_gets_no_info_line(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("no authority recorded", r.stdout)

    # --- artifacts ----------------------------------------------------------
    def test_quote_in_a_non_utf8_artifact_is_reported_as_not_found(self):
        self.init()
        with open(os.path.join(self.out, "dump.bin"), "wb") as f:
            f.write(b"POST /api/v2/auth/login\xff\xfe")
        run(self.out, "add-fact", "--claim", "login", "--rung", "REACHABLE", "--artifact", "dump.bin",
            "--verbatim", "POST /api/v2/auth/login")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("verbatim quote not found in artifact dump.bin", r.stdout)

    def test_quote_match_ignores_whitespace_differences_in_an_artifact(self):
        self.init()
        art = self.write_artifact("dump.txt", "POST   /api/v2/auth/login\n")
        run(self.out, "add-fact", "--claim", "login", "--rung", "REACHABLE", "--artifact", art,
            "--verbatim", "POST /api/v2/auth/login")
        self.assertEqual(run(self.out, "validate").returncode, 0)

    def test_missing_bound_artifact_fails_validate(self):
        self.init()
        art = self.write_artifact("ida/sign.c", "int sign(void) { return 42; }\n")
        run(self.out, "add-fact", "--claim", "sign", "--rung", "REACHABLE", "--artifact", art,
            "--verbatim", "return 42;")
        os.remove(os.path.join(self.out, art))
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("artifact ida/sign.c is missing", r.stdout)

    def test_sample_artifact_digest_change_fails_validate(self):
        self.init()
        art = self.write_artifact("captures/s1.txt", "request body")
        run(self.out, "add-fact", "--claim", "sig", "--rung", "VERIFIED", "--verbatim", "request body",
            "--sample", "s1", "--sample", "s2", "--control", "c1", "--sample-artifact", "s1=" + art)
        self.assertEqual(run(self.out, "validate").returncode, 0)
        self.write_artifact("captures/s1.txt", "request body changed")
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sample s1: artifact captures/s1.txt changed since it was recorded", r.stdout)

    # --- hand-edited ledgers: the enumerations validate checks -------------
    def test_validate_fails_invalid_enumerations_in_a_hand_edited_ledger(self):
        self.init()
        run(self.out, "add-fact", "--claim", "c", "--rung", "REACHABLE", "--verbatim", "quoted text here")
        run(self.out, "add-hypothesis", "--claim", "h")
        base = self.load()
        cases = (
            ("facts", "rung", "CERTAIN", "invalid rung 'CERTAIN'"),
            ("facts", "status", "maybe", "invalid status 'maybe'"),
            ("facts", "authority", "hearsay", "invalid authority 'hearsay'"),
            ("hypotheses", "confidence", "certain", "invalid confidence 'certain'"),
            ("hypotheses", "status", "maybe", "invalid status 'maybe'"),
        )
        for section, key, value, message in cases:
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(base)
                data[section][0][key] = value
                self.save(data)
                r = run(self.out, "validate")
                self.assertEqual(r.returncode, 1)
                self.assertIn(message, r.stdout)

    def test_non_integer_coverage_counts_fail_validate_instead_of_crashing(self):
        self.init()
        run(self.out, "add-coverage", "--area", "smali", "--examined", "1", "--total", "9", "--note", "partial")
        run(self.out, "add-fact", "--claim", "no pinning", "--absence", "--coverage-area", "smali")
        data = self.load()
        data["coverage"][0]["examined"] = "5"
        with open(os.path.join(self.out, "findings.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        r = run(self.out, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("non-integer or out-of-range counts", r.stdout)

    def test_check_report_with_malformed_coverage_fails_cleanly(self):
        self.init()
        run(self.out, "add-coverage", "--area", "smali", "--examined", "1", "--total", "9", "--note", "partial")
        run(self.out, "add-fact", "--claim", "no pinning", "--absence", "--coverage-area", "smali")
        data = self.load()
        data["coverage"][0]["total"] = None
        with open(os.path.join(self.out, "findings.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        report = self.write_report("No pinning in the login path [f1].\n")
        r = run(self.out, "check-report", "--report", report)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("without complete coverage", r.stdout)


if __name__ == "__main__":
    unittest.main()
