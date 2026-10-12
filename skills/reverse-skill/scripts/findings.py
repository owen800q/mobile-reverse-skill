#!/usr/bin/env python3
"""
findings.py - the single connective-tissue ledger for /reverse-skill.

One JSON file (findings.json) is the shared blackboard across every phase. It
collapses three ideas from the source skills into something a single session can
actually maintain:

  - Facts    : evidence-graded observations (Fausto's blackboard + Guardian rungs)
  - Intents  : directed cross-phase targeting ("the sign sinks into libsec.so")
  - Hypotheses: named crypto/algorithm guesses gated by fingerprints (algokiller)

It also records provenance: the input's SHA-256 (`init --input`) and each tool
binary's SHA-256 and reported version (`add-tool`), so a later reader can tell
which bytes and which engine produced a result.

The `validate` subcommand mechanically enforces the anti-hallucination rules
that make the ledger worth keeping:

  R1  No fact may sit above rung PATTERN without a verbatim evidence quote.
  R2  No hypothesis may reach confidence >= medium naming a crypto primitive
      without at least one fingerprint (a constscan/cryptoinstr hit). high needs
      two independent signals. This is the "no primitive name without a
      fingerprint" rule - it stops a lone magic number from becoming "AES".
  R3  A VERIFIED fact needs at least two distinct captured samples that reproduce
      and one control case: an input deliberately changed, whose output change the
      reconstruction predicted or correctly rejected. One sample only verifies
      that one test vector.

Dispositions: `blocked` and `out_of_scope` record why a claim is not pursued.
They are never counted as verified.

Coverage: `add-coverage` records how much of an area was examined (for example 40 of
120 smali classes) and what was left out. One record per area, replaced on update.
`validate` reports partial coverage as INFO, so a conclusion drawn from part of a
target stays visibly partial.

Everything is stdlib. Scripts in this skill write their own result JSON; the
model reads those and records durable conclusions here via `add-fact` etc.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

RUNGS = ["PATTERN", "REACHABLE", "CONTROLLABLE", "EXPLOITABLE", "VERIFIED"]
CONFIDENCE = ["low", "medium", "high"]
FACT_STATUS = ["open", "confirmed", "refuted", "blocked", "out_of_scope"]
HYP_STATUS = ["proposed", "confirmed", "refuted", "blocked", "out_of_scope"]
DISPOSITIONS = ("blocked", "out_of_scope")
# Where a fact's evidence came from. Separate from the rung, which grades how strong
# the claim is. A fact above CONTROLLABLE cannot rest on an analyst note alone.
AUTHORITIES = ("source_text", "tool_output", "runtime_capture", "external_record", "analyst_note")
AUTHORITY_CEILING_RUNG = "CONTROLLABLE"
# Artifacts bound to facts are read for verbatim checks up to this size.
MAX_ARTIFACT_TEXT_BYTES = 64 * 1024 * 1024
CITATION_RE = re.compile(r"\[(f\d+|h\d+)\]")
QUOTE_RE = re.compile(r'"([^"\n]{8,})"')
MIN_VERIFIED_SAMPLES = 2
HASH_CHUNK = 1024 * 1024

# Substrings that count as "naming a crypto primitive" for rule R2. If a
# hypothesis claim/primitive hits one of these it must carry a fingerprint
# before its confidence can be raised.
PRIMITIVE_TOKENS = [
    "aes", "des", "3des", "rc4", "chacha", "salsa", "blowfish",
    "sha1", "sha-1", "sha256", "sha-256", "sha512", "sha-512", "sha384",
    "md5", "sm2", "sm3", "sm4", "tea", "xtea", "xxtea",
    "hmac", "rsa", "ecdsa", "ecc", "ed25519", "x25519", "crc32",
    "poly1305", "gcm", "ghash", "base64",  # base64 is encoding, still gated
]


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _path(args):
    if args.file:
        return args.file
    return os.path.join(args.out, "findings.json")


def _load(args):
    p = _path(args)
    if not os.path.exists(p):
        sys.exit("findings.json not found at %s - run `findings.py init` first" % p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(args, data):
    p = _path(args)
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return p


def _next_id(items, prefix):
    n = 1
    existing = {it.get("id") for it in items}
    while "%s%d" % (prefix, n) in existing:
        n += 1
    return "%s%d" % (prefix, n)


def _names_primitive(text):
    t = (text or "").lower()
    return any(tok in t for tok in PRIMITIVE_TOKENS)


def _describe_file(path):
    """Absolute path, size and SHA-256 of a regular file, streamed in chunks."""
    if not os.path.isfile(path):
        sys.exit("not a regular file: %s" % path)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK), b""):
            digest.update(chunk)
    return {"path": os.path.abspath(path), "size": os.path.getsize(path),
            "sha256": digest.hexdigest()}


def _pct(examined, total):
    return "%d%%" % round(100.0 * examined / total) if total else "n/a"


def _unique(values):
    out = []
    for v in values or []:
        if v and v not in out:
            out.append(v)
    return out


def _samples(fact):
    return set(s for s in (fact.get("samples") or []) if s)


def _is_verified(fact):
    """A VERIFIED fact that meets R3 and is neither refuted nor dispositioned."""
    if fact.get("rung") != "VERIFIED" or fact.get("status") == "refuted":
        return False
    if fact.get("status") in DISPOSITIONS:
        return False
    samples = _samples(fact)
    control = fact.get("control") or ""
    return len(samples) >= MIN_VERIFIED_SAMPLES and bool(control) and control not in samples


# ---------------------------------------------------------------- subcommands
def cmd_init(args):
    if os.path.lexists(_path(args)):
        sys.exit("findings.json already exists - use `show` to resume or choose a new --out directory")
    data = {
        "target": args.target,
        "goal": args.goal,
        "phase": 0,
        "created": _now(),
        "updated": _now(),
        "input": _describe_file(args.input) if args.input else None,
        "tools": [],
        "facts": [],
        "intents": [],
        "hypotheses": [],
        "protocol_map": {
            "auth_fields": [],
            "signature_fields": [],
            "endpoint_parameter_map": {},
        },
        "endpoints": [],
        "requests": [],
        "coverage": [],
        "artifacts": {},
    }
    p = _save(args, data)
    print("initialized %s (target=%s)" % (p, args.target))
    if data["input"]:
        print("input sha256=%s size=%d" % (data["input"]["sha256"], data["input"]["size"]))


def cmd_add_tool(args):
    data = _load(args)
    desc = _describe_file(args.path)
    tool = dict(desc, name=args.name, version=args.version, recorded=_now())
    data.setdefault("tools", []).append(tool)
    data["updated"] = _now()
    _save(args, data)
    print("recorded %s %s sha256=%s" % (tool["name"], tool["version"], tool["sha256"]))


def _session_dir(args):
    return os.path.dirname(os.path.abspath(_path(args)))


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _norm(text):
    return " ".join((text or "").split())


def _bind_artifact(args, path_arg):
    """Digest an artifact that must sit inside the session directory. Returns {path, sha256}."""
    session = _session_dir(args)
    root = os.path.realpath(session)
    full = os.path.realpath(path_arg if os.path.isabs(path_arg) else os.path.join(session, path_arg))
    if os.path.commonpath([full, root]) != root:
        sys.exit("artifact must be inside the session directory: %s" % path_arg)
    if not os.path.isfile(full):
        sys.exit("artifact not found: %s" % path_arg)
    return {"path": os.path.relpath(full, root).replace(os.sep, "/"), "sha256": _file_sha256(full)}


def _bind_samples(args, items):
    """Parse repeated SAMPLE=PATH pairs into {sample: {path, sha256}}."""
    bound = {}
    for item in items or []:
        sample, sep, path_arg = item.partition("=")
        if not sep or not sample or not path_arg:
            sys.exit("--sample-artifact expects SAMPLE=PATH, got %r" % item)
        bound[sample] = _bind_artifact(args, path_arg)
    return bound


def _artifact_problems(session, art, verbatim=None):
    """Return a list of problems with one bound artifact: missing, changed, or verbatim absent."""
    full = os.path.join(session, art.get("path", ""))
    if not os.path.isfile(full):
        return ["artifact %s is missing" % art.get("path")]
    if _file_sha256(full) != art.get("sha256"):
        return ["artifact %s changed since it was recorded (sha256 mismatch)" % art.get("path")]
    if verbatim and _norm(verbatim) and not _artifact_contains(session, art, _norm(verbatim)):
        return ["verbatim quote not found in artifact %s" % art.get("path")]
    return []


def _artifact_contains(session, art, needle):
    full = os.path.join(session, art.get("path", ""))
    if not os.path.isfile(full) or os.path.getsize(full) > MAX_ARTIFACT_TEXT_BYTES:
        return False
    try:
        with open(full, "r", encoding="utf-8") as fh:
            return needle in _norm(fh.read())
    except UnicodeDecodeError:
        return False


def cmd_add_fact(args):
    data = _load(args)
    if args.rung not in RUNGS:
        sys.exit("rung must be one of %s" % RUNGS)
    ev = []
    if args.verbatim or args.ref or args.tool or args.artifact:
        entry = {"tool": args.tool or "", "ref": args.ref or "",
                 "verbatim": args.verbatim or ""}
        if args.artifact:
            entry["artifact"] = _bind_artifact(args, args.artifact)
        ev.append(entry)
    fact = {
        "id": _next_id(data["facts"], "f"),
        "phase": args.phase,
        "claim": args.claim,
        "rung": args.rung,
        "evidence": ev,
        "status": args.status,
        "samples": _unique(args.sample),
        "control": args.control or "",
        "authority": args.authority or "",
        "absence": bool(args.absence),
        "coverage_area": args.coverage_area or "",
        "sample_artifacts": _bind_samples(args, args.sample_artifact),
    }
    data["facts"].append(fact)
    data["updated"] = _now()
    _save(args, data)
    print("added %s [%s] %s" % (fact["id"], fact["rung"], fact["claim"]))


def cmd_set_fact(args):
    data = _load(args)
    f = next((x for x in data["facts"] if x["id"] == args.id), None)
    if not f:
        sys.exit("no fact %s" % args.id)
    if args.rung:
        if args.rung not in RUNGS:
            sys.exit("rung must be one of %s" % RUNGS)
        f["rung"] = args.rung
    if args.status:
        f["status"] = args.status
    if args.verbatim or args.ref or args.tool or args.artifact:
        entry = {"tool": args.tool or "", "ref": args.ref or "", "verbatim": args.verbatim or ""}
        if args.artifact:
            entry["artifact"] = _bind_artifact(args, args.artifact)
        f.setdefault("evidence", []).append(entry)
    if args.sample_artifact:
        f.setdefault("sample_artifacts", {}).update(_bind_samples(args, args.sample_artifact))
    if args.sample:
        f["samples"] = _unique((f.get("samples") or []) + args.sample)
    if args.control:
        f["control"] = args.control
    if args.authority:
        f["authority"] = args.authority
    data["updated"] = _now()
    _save(args, data)
    print("updated %s -> rung=%s status=%s samples=%d control=%s"
          % (f["id"], f["rung"], f["status"], len(_samples(f)), f.get("control") or "none"))


def cmd_add_intent(args):
    data = _load(args)
    it = {
        "id": _next_id(data["intents"], "i"),
        "from_phase": args.from_phase,
        "target": args.target_ref,
        "reason": args.reason,
        "status": "open",
    }
    data["intents"].append(it)
    data["updated"] = _now()
    _save(args, data)
    print("added %s -> %s (%s)" % (it["id"], it["target"], it["reason"]))


def cmd_add_hypothesis(args):
    data = _load(args)
    h = {
        "id": _next_id(data["hypotheses"], "h"),
        "phase": args.phase,
        "claim": args.claim,
        "primitive": args.primitive or "",
        "confidence": args.confidence,
        "fingerprints": list(args.fingerprint or []),
        "supports": _unique(args.supports),
        "contradicts": _unique(args.contradicts),
        "status": "proposed",
    }
    data["hypotheses"].append(h)
    data["updated"] = _now()
    _save(args, data)
    print("added %s: %s (confidence=%s, %d fingerprint(s))"
          % (h["id"], h["claim"], h["confidence"], len(h["fingerprints"])))


def cmd_set_hypothesis(args):
    data = _load(args)
    h = next((x for x in data["hypotheses"] if x["id"] == args.id), None)
    if not h:
        sys.exit("no hypothesis %s" % args.id)
    for fp in (args.fingerprint or []):
        if fp not in h["fingerprints"]:
            h["fingerprints"].append(fp)
    h["supports"] = _unique((h.get("supports") or []) + (args.supports or []))
    h["contradicts"] = _unique((h.get("contradicts") or []) + (args.contradicts or []))
    if args.confidence:
        h["confidence"] = args.confidence
    if args.status:
        h["status"] = args.status
    data["updated"] = _now()
    _save(args, data)
    print("updated %s -> confidence=%s status=%s fingerprints=%d"
          % (h["id"], h["confidence"], h["status"], len(h["fingerprints"])))


def cmd_set_phase(args):
    data = _load(args)
    data["phase"] = args.n
    data["updated"] = _now()
    _save(args, data)
    print("phase = %d" % args.n)


def cmd_add_coverage(args):
    if not (0 <= args.examined <= args.total and args.total >= 1):
        sys.exit("coverage needs 0 <= examined <= total and total >= 1 (got %d of %d)"
                 % (args.examined, args.total))
    data = _load(args)
    entry = {"area": args.area, "examined": args.examined, "total": args.total,
             "note": args.note or "", "recorded": _now()}
    items = data.setdefault("coverage", [])
    current = next((c for c in items if c.get("area") == args.area), None)
    if current:
        current.update(entry)
    else:
        items.append(entry)
    data["updated"] = _now()
    _save(args, data)
    print("coverage %s: %d of %d (%s)"
          % (args.area, args.examined, args.total, _pct(args.examined, args.total)))


def cmd_show(args):
    data = _load(args)
    print("target : %s" % data.get("target"))
    print("goal   : %s" % data.get("goal"))
    print("phase  : %s" % data.get("phase"))
    inp = data.get("input")
    if inp:
        print("input  : %s sha256=%s size=%d" % (inp["path"], inp["sha256"], inp["size"]))
    latest = {}
    for t in data.get("tools", []):
        latest[t["name"]] = t
    for t in latest.values():
        print("tool   : %s %s sha256=%s" % (t["name"], t["version"], t["sha256"]))
    print("\nfacts (%d):" % len(data["facts"]))
    for f in data["facts"]:
        print("  %-4s [%-12s] %-12s samples=%d control=%s %s"
              % (f["id"], f["rung"], f["status"], len(_samples(f)),
                 f.get("control") or "-", f["claim"]))
    print("\nintents (%d):" % len(data["intents"]))
    for it in data["intents"]:
        print("  %-4s %-9s %s <- %s" % (it["id"], it["status"], it["target"], it["reason"]))
    print("\nhypotheses (%d):" % len(data["hypotheses"]))
    for h in data["hypotheses"]:
        print("  %-4s %-8s %-12s fp=%d  %s"
              % (h["id"], h["confidence"], h["status"], len(h["fingerprints"]), h["claim"]))
    print("\ncoverage (%d):" % len(data.get("coverage", [])))
    for c in data.get("coverage", []):
        print("  %-24s %d of %d (%s)%s"
              % (c["area"], c["examined"], c["total"], _pct(c["examined"], c["total"]),
                 "  " + c["note"] if c.get("note") else ""))


def cmd_validate(args):
    data = _load(args)
    errors = []
    warns = []
    notes = []

    for f in data["facts"]:
        if f.get("rung") not in RUNGS:
            errors.append("%s: invalid rung %r" % (f.get("id"), f.get("rung")))
        if f.get("status") not in FACT_STATUS:
            errors.append("%s: invalid status %r" % (f.get("id"), f.get("status")))
        # R1: above PATTERN requires a verbatim evidence quote.
        if f.get("rung") in RUNGS and RUNGS.index(f.get("rung", "PATTERN")) > 0:
            has_v = any((e.get("verbatim") or "").strip() for e in f.get("evidence", []))
            if not has_v:
                errors.append("R1 violation: %s is rung %s but has no verbatim evidence"
                              % (f.get("id"), f.get("rung")))
        # R3: VERIFIED needs two distinct samples and one control case.
        if f.get("rung") == "VERIFIED":
            samples = _samples(f)
            control = f.get("control") or ""
            if len(samples) < MIN_VERIFIED_SAMPLES or not control:
                errors.append(
                    "R3 violation: %s is VERIFIED with %d distinct sample(s) and control=%s; "
                    "need >=%d samples and one control case"
                    % (f.get("id"), len(samples), control or "none", MIN_VERIFIED_SAMPLES))
            elif control in samples:
                errors.append("R3 violation: %s control %r is also listed as a sample"
                              % (f.get("id"), control))
        # Authority: an analyst note cannot carry a rung above the ceiling by itself.
        authority = f.get("authority") or ""
        if authority and authority not in AUTHORITIES:
            errors.append("%s: invalid authority %r" % (f.get("id"), authority))
        if authority == "analyst_note" and f.get("rung") in RUNGS and \
                RUNGS.index(f["rung"]) > RUNGS.index(AUTHORITY_CEILING_RUNG):
            errors.append("%s is rung %s but its only authority is analyst_note; needs tool, "
                          "source or runtime evidence" % (f.get("id"), f.get("rung")))
        elif not authority and f.get("rung") in RUNGS and RUNGS.index(f["rung"]) > 0:
            notes.append("%s has no authority recorded (set --authority)" % f.get("id"))
        # Absence: "not found" is only evidence over an area that was fully examined.
        if f.get("absence") and f.get("status") not in DISPOSITIONS:
            area = f.get("coverage_area") or ""
            record = next((c for c in data.get("coverage", []) if c.get("area") == area), None)
            if not area or record is None:
                errors.append("%s is an absence claim with no coverage record for area %r; "
                              "run add-coverage first" % (f.get("id"), area))
            elif record.get("examined", 0) < record.get("total", 0):
                errors.append("%s is an absence claim over partial coverage of %r (%d of %d); "
                              "examine the rest or drop the claim"
                              % (f.get("id"), area, record["examined"], record["total"]))
        # Digests: every bound artifact must still match, and its verbatim quote must be in it.
        session = _session_dir(args)
        for e in f.get("evidence", []):
            if e.get("artifact"):
                for msg in _artifact_problems(session, e["artifact"], e.get("verbatim")):
                    errors.append("%s: %s" % (f.get("id"), msg))
        for sid, art in (f.get("sample_artifacts") or {}).items():
            for msg in _artifact_problems(session, art):
                errors.append("%s sample %s: %s" % (f.get("id"), sid, msg))
        if f.get("rung") == "VERIFIED":
            unbound = [sid for sid in _samples(f) if sid not in (f.get("sample_artifacts") or {})]
            if unbound:
                warns.append("%s VERIFIED with sample(s) not bound to an artifact: %s"
                             % (f.get("id"), ", ".join(unbound)))
        if f.get("status") in DISPOSITIONS:
            notes.append("%s is %s (not counted as verified)" % (f.get("id"), f.get("status")))

    fact_ids = {f.get("id") for f in data["facts"]}
    for h in data["hypotheses"]:
        if h.get("confidence") not in CONFIDENCE:
            errors.append("%s: invalid confidence %r" % (h.get("id"), h.get("confidence")))
        if h.get("status") not in HYP_STATUS:
            errors.append("%s: invalid status %r" % (h.get("id"), h.get("status")))
        names_prim = _names_primitive(h.get("primitive") or h.get("claim"))
        nfp = len(h.get("fingerprints", []))
        conf = h.get("confidence")
        # R2: naming a primitive at medium+ requires a fingerprint.
        if names_prim and conf in ("medium", "high") and nfp < 1:
            errors.append(
                "R2 violation: %s names a primitive at confidence=%s with 0 fingerprints "
                "(run constscan.py / cryptoinstr.py first)" % (h.get("id"), conf))
        # high confidence wants two independent signals.
        if names_prim and conf == "high" and nfp < 2:
            warns.append("%s is high confidence with only %d fingerprint(s); "
                         "want >=2 independent signals or a VERIFIED replay" % (h.get("id"), nfp))
        # Links: every referenced fact must exist; a confirmed hypothesis needs a
        # supporting fact and must not be contradicted by a confirmed one.
        for ref in (h.get("supports") or []) + (h.get("contradicts") or []):
            if ref not in fact_ids:
                errors.append("%s links to unknown fact %s" % (h.get("id"), ref))
        if h.get("status") == "confirmed":
            live_support = [f for f in data["facts"]
                            if f.get("id") in (h.get("supports") or [])
                            and f.get("status") not in DISPOSITIONS + ("refuted",)]
            if not live_support:
                warns.append("%s status=confirmed with no supporting fact linked (--supports)"
                             % h.get("id"))
            confirmed_against = [f.get("id") for f in data["facts"]
                                 if f.get("id") in (h.get("contradicts") or [])
                                 and f.get("status") == "confirmed"]
            if confirmed_against:
                errors.append("%s is confirmed but contradicted by confirmed fact(s) %s"
                              % (h.get("id"), ", ".join(confirmed_against)))
        if h.get("status") == "confirmed":
            if not any(_is_verified(f) for f in data["facts"]):
                warns.append("%s status=confirmed but no VERIFIED fact meets R3; the strongest "
                             "confirmation is recomputing the captured signature" % h.get("id"))
        if h.get("status") in DISPOSITIONS:
            notes.append("%s is %s (not counted as verified)" % (h.get("id"), h.get("status")))

    for c in data.get("coverage", []):
        examined, total = c.get("examined"), c.get("total")
        if not (isinstance(examined, int) and isinstance(total, int)
                and 0 <= examined <= total and total >= 1):
            errors.append("coverage %r: examined=%r total=%r needs 0 <= examined <= total and total >= 1"
                          % (c.get("area"), examined, total))
        elif examined < total:
            notes.append("coverage %r examined %d of %d (%s)%s"
                         % (c.get("area"), examined, total, _pct(examined, total),
                            ": " + c["note"] if c.get("note") else ""))

    for n in notes:
        print("INFO  " + n)
    for w in warns:
        print("WARN  " + w)
    for e in errors:
        print("FAIL  " + e)
    if errors:
        sys.exit("\nvalidate: %d error(s), %d warning(s)" % (len(errors), len(warns)))
    print("validate: OK (%d warning(s))" % len(warns))


def cmd_check_report(args):
    """Check a written report against the ledger: citations, quotes, rung claims, absence."""
    data = _load(args)
    session = _session_dir(args)
    facts = {f["id"]: f for f in data["facts"]}
    hyps = {h["id"]: h for h in data["hypotheses"]}
    coverage = {c.get("area"): c for c in data.get("coverage", [])}
    with open(args.report, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    errors, warns, checked = [], [], 0
    for lineno, line in enumerate(lines, 1):
        cited = CITATION_RE.findall(line)
        quotes = QUOTE_RE.findall(line)
        if not cited:
            if quotes:
                warns.append("line %d quotes text with no fact citation; it cannot be checked" % lineno)
            continue
        checked += 1
        cited_facts = []
        for ident in cited:
            if ident.startswith("h"):
                if ident not in hyps:
                    errors.append("line %d cites unknown hypothesis %s" % (lineno, ident))
                elif hyps[ident].get("status") == "refuted":
                    errors.append("line %d cites refuted hypothesis %s" % (lineno, ident))
                continue
            if ident not in facts:
                errors.append("line %d cites unknown fact %s" % (lineno, ident))
                continue
            f = facts[ident]
            cited_facts.append(f)
            if f.get("status") == "refuted":
                errors.append("line %d cites refuted fact %s" % (lineno, ident))
            elif f.get("status") in ("open",) + DISPOSITIONS:
                warns.append("line %d cites %s fact %s" % (lineno, f.get("status"), ident))
            if f.get("absence") and f.get("status") not in DISPOSITIONS:
                rec = coverage.get(f.get("coverage_area") or "")
                if rec is None or rec.get("examined", 0) < rec.get("total", 0):
                    errors.append("line %d states an absence (%s) without complete coverage of %r"
                                  % (lineno, ident, f.get("coverage_area") or ""))
        if not cited_facts:
            continue
        # A rung word on the line is a claim; it cannot exceed the strongest cited fact.
        strongest = max(RUNGS.index(f.get("rung", "PATTERN")) for f in cited_facts)
        for word in set(re.findall(r"\b(PATTERN|REACHABLE|CONTROLLABLE|EXPLOITABLE|VERIFIED)\b", line)):
            if RUNGS.index(word) > strongest:
                errors.append("line %d claims %s but the cited fact(s) reach at most %s"
                              % (lineno, word, RUNGS[strongest]))
        # Quotes must appear in the cited facts' verbatim evidence or bound artifacts.
        for quote in quotes:
            needle = _norm(quote)
            found = False
            for f in cited_facts:
                for e in f.get("evidence", []):
                    if needle in _norm(e.get("verbatim")):
                        found = True
                    elif e.get("artifact") and _artifact_contains(session, e["artifact"], needle):
                        found = True
            if not found:
                errors.append("line %d quotes %r, which is not in the verbatim evidence of %s"
                              % (lineno, quote[:60], ", ".join(f["id"] for f in cited_facts)))

    for w in warns:
        print("WARN  " + w)
    for e in errors:
        print("FAIL  " + e)
    print("check-report: %d cited line(s), %d error(s), %d warning(s)" % (checked, len(errors), len(warns)))
    if errors:
        sys.exit(1)


def build_parser():
    ap = argparse.ArgumentParser(description="reverse-skill findings ledger")
    ap.add_argument("--out", default="./re_out", help="session dir (holds findings.json)")
    ap.add_argument("--file", help="explicit path to findings.json (overrides --out)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.set_defaults(func=cmd_init)
    p.add_argument("--target", required=True)
    p.add_argument("--goal", default="reverse login API")
    p.add_argument("--input", help="target file; its size and SHA-256 are recorded")

    p = sub.add_parser("add-tool"); p.set_defaults(func=cmd_add_tool)
    p.add_argument("--name", required=True, help="tool name, e.g. unblob, idat, ilspycmd")
    p.add_argument("--path", required=True, help="installed binary; its SHA-256 is recorded")
    p.add_argument("--version", required=True, help="version string as the tool reports it")

    p = sub.add_parser("add-fact"); p.set_defaults(func=cmd_add_fact)
    p.add_argument("--claim", required=True)
    p.add_argument("--phase", type=int, default=0)
    p.add_argument("--rung", default="PATTERN")
    p.add_argument("--tool"); p.add_argument("--ref"); p.add_argument("--verbatim")
    p.add_argument("--status", default="open", choices=FACT_STATUS)
    p.add_argument("--sample", action="append",
                   help="captured sample ID that reproduces the claim (repeat for >=2 with VERIFIED)")
    p.add_argument("--control", help="ID of a deliberately changed input whose output change was predicted or rejected")
    p.add_argument("--authority", choices=AUTHORITIES,
                   help="where the evidence came from (separate from the rung)")
    p.add_argument("--absence", action="store_true",
                   help="the claim is 'not found' or 'does not occur'; needs complete coverage of --coverage-area")
    p.add_argument("--coverage-area", dest="coverage_area", default="",
                   help="the add-coverage area this absence claim covers")
    p.add_argument("--artifact", default=None, metavar="PATH",
                   help="session-local file the verbatim quote came from; its SHA-256 is recorded")
    p.add_argument("--sample-artifact", action="append", default=[], metavar="SAMPLE=PATH",
                   help="bind a sample ID to the artifact that holds it (repeatable)")

    p = sub.add_parser("set-fact"); p.set_defaults(func=cmd_set_fact)
    p.add_argument("--id", required=True)
    p.add_argument("--rung"); p.add_argument("--status", choices=FACT_STATUS)
    p.add_argument("--tool"); p.add_argument("--ref"); p.add_argument("--verbatim")
    p.add_argument("--sample", action="append", help="add a sample ID")
    p.add_argument("--control", help="set the control case ID")
    p.add_argument("--authority", choices=AUTHORITIES, help="set the evidence authority")
    p.add_argument("--artifact", default=None, metavar="PATH")
    p.add_argument("--sample-artifact", action="append", default=[], metavar="SAMPLE=PATH")

    p = sub.add_parser("add-intent"); p.set_defaults(func=cmd_add_intent)
    p.add_argument("--from-phase", type=int, required=True, dest="from_phase")
    p.add_argument("--target", required=True, dest="target_ref")
    p.add_argument("--reason", required=True)

    p = sub.add_parser("add-hypothesis"); p.set_defaults(func=cmd_add_hypothesis)
    p.add_argument("--claim", required=True)
    p.add_argument("--primitive")
    p.add_argument("--phase", type=int, default=4)
    p.add_argument("--confidence", default="low", choices=CONFIDENCE)
    p.add_argument("--fingerprint", action="append")
    p.add_argument("--supports", action="append", metavar="FACT_ID",
                   help="fact ID that supports this hypothesis (repeatable)")
    p.add_argument("--contradicts", action="append", metavar="FACT_ID",
                   help="fact ID that contradicts this hypothesis (repeatable)")

    p = sub.add_parser("set-hypothesis"); p.set_defaults(func=cmd_set_hypothesis)
    p.add_argument("--id", required=True)
    p.add_argument("--confidence", choices=CONFIDENCE)
    p.add_argument("--status", choices=HYP_STATUS)
    p.add_argument("--fingerprint", action="append")
    p.add_argument("--supports", action="append", metavar="FACT_ID")
    p.add_argument("--contradicts", action="append", metavar="FACT_ID")

    p = sub.add_parser("set-phase"); p.set_defaults(func=cmd_set_phase)
    p.add_argument("n", type=int)

    p = sub.add_parser("add-coverage"); p.set_defaults(func=cmd_add_coverage)
    p.add_argument("--area", required=True,
                   help="what was surveyed, e.g. 'smali classes' or 'rootfs ELF binaries'")
    p.add_argument("--examined", type=int, required=True)
    p.add_argument("--total", type=int, required=True)
    p.add_argument("--note", help="what was left out and why; validate prints it for partial coverage")

    p = sub.add_parser("show"); p.set_defaults(func=cmd_show)
    p = sub.add_parser("validate"); p.set_defaults(func=cmd_validate)
    p = sub.add_parser("check-report"); p.set_defaults(func=cmd_check_report)
    p.add_argument("--report", required=True, help="the written report to check (Markdown or text)")
    return ap


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
