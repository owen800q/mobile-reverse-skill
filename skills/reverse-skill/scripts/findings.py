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

Everything is stdlib. Scripts in this skill write their own result JSON; the
model reads those and records durable conclusions here via `add-fact` etc.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

RUNGS = ["PATTERN", "REACHABLE", "CONTROLLABLE", "EXPLOITABLE", "VERIFIED"]
CONFIDENCE = ["low", "medium", "high"]
FACT_STATUS = ["open", "confirmed", "refuted", "blocked", "out_of_scope"]
HYP_STATUS = ["proposed", "confirmed", "refuted", "blocked", "out_of_scope"]
DISPOSITIONS = ("blocked", "out_of_scope")
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


def cmd_add_fact(args):
    data = _load(args)
    if args.rung not in RUNGS:
        sys.exit("rung must be one of %s" % RUNGS)
    ev = []
    if args.verbatim or args.ref or args.tool:
        ev.append({"tool": args.tool or "", "ref": args.ref or "",
                   "verbatim": args.verbatim or ""})
    fact = {
        "id": _next_id(data["facts"], "f"),
        "phase": args.phase,
        "claim": args.claim,
        "rung": args.rung,
        "evidence": ev,
        "status": args.status,
        "samples": _unique(args.sample),
        "control": args.control or "",
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
    if args.verbatim or args.ref or args.tool:
        f.setdefault("evidence", []).append(
            {"tool": args.tool or "", "ref": args.ref or "", "verbatim": args.verbatim or ""})
    if args.sample:
        f["samples"] = _unique((f.get("samples") or []) + args.sample)
    if args.control:
        f["control"] = args.control
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
        if f.get("status") in DISPOSITIONS:
            notes.append("%s is %s (not counted as verified)" % (f.get("id"), f.get("status")))

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
        if h.get("status") == "confirmed":
            if not any(_is_verified(f) for f in data["facts"]):
                warns.append("%s status=confirmed but no VERIFIED fact meets R3; the strongest "
                             "confirmation is recomputing the captured signature" % h.get("id"))
        if h.get("status") in DISPOSITIONS:
            notes.append("%s is %s (not counted as verified)" % (h.get("id"), h.get("status")))

    for n in notes:
        print("INFO  " + n)
    for w in warns:
        print("WARN  " + w)
    for e in errors:
        print("FAIL  " + e)
    if errors:
        sys.exit("\nvalidate: %d error(s), %d warning(s)" % (len(errors), len(warns)))
    print("validate: OK (%d warning(s))" % len(warns))


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

    p = sub.add_parser("set-fact"); p.set_defaults(func=cmd_set_fact)
    p.add_argument("--id", required=True)
    p.add_argument("--rung"); p.add_argument("--status", choices=FACT_STATUS)
    p.add_argument("--tool"); p.add_argument("--ref"); p.add_argument("--verbatim")
    p.add_argument("--sample", action="append", help="add a sample ID")
    p.add_argument("--control", help="set the control case ID")

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

    p = sub.add_parser("set-hypothesis"); p.set_defaults(func=cmd_set_hypothesis)
    p.add_argument("--id", required=True)
    p.add_argument("--confidence", choices=CONFIDENCE)
    p.add_argument("--status", choices=HYP_STATUS)
    p.add_argument("--fingerprint", action="append")

    p = sub.add_parser("set-phase"); p.set_defaults(func=cmd_set_phase)
    p.add_argument("n", type=int)

    p = sub.add_parser("show"); p.set_defaults(func=cmd_show)
    p = sub.add_parser("validate"); p.set_defaults(func=cmd_validate)
    return ap


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
