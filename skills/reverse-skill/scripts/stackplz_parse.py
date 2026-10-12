#!/usr/bin/env python3
"""Normalize SeeFlowerX/stackplz output into structured events + ledger hints.

Usage:
    stackplz_parse.py <stackplz_events.json | stackplz_stdout.log> [--out DIR] [--literal VALUE | --literal-file FILE]

stackplz emits one event per hook hit (a syscall, a uprobe, or a hardware
breakpoint), each carrying some subset of: process (comm/pid/tid), the probe
name/symbol/syscall, typed arguments, a hexdump of a buffer, and a call stack.
The exact JSON field names vary across stackplz versions, so this parser is
deliberately tolerant: it accepts a JSON array, JSON-lines, or a raw text log,
walks whatever structure it finds, and pulls out the RE-relevant material
(printable buffers, backtraces, symbol names).

It writes <out>/stackplz_events.json, or <out>/stackplz_events.normalized.json when the
input is already <out>/stackplz_events.json, and prints to stderr the events that look
crypto- or auth-relevant, with up to two buffer previews per event (declared literals
removed, then newlines escaped and the text cut to 160 characters), plus copy-paste
`findings.py` hints, so you can promote the durable ones into findings.json with
evidence. Apart from newlines, buffer text is printed unescaped, so an undeclared secret
in a buffer appears on the console. Like ecapture_parse.py, it does NOT touch the ledger
itself — a script observes; you decide what becomes a Fact.
--literal and --literal-file rewrite only the file this run wrote, and remove declared
literals from buffer previews before they are cut to 400 characters; redact_literals.py
lists the encodings searched.

No network calls; stdlib only.
"""
import argparse
import json
import os
import re
import sys

from redact_literals import (  # noqa: E402
    LiteralError, add_literal_args, apply_literals, redact_text, resolve_literal_args,
)


# --- what makes an event worth surfacing ----------------------------------
# Symbol / probe names that suggest signing or crypto.
CRYPTO_NAME_RE = re.compile(
    r"(?i)(sign|hmac|\baes\b|\bdes\b|\bsm[234]\b|md5|sha\d?|encrypt|decrypt|"
    r"digest|cipher|crypto|token|secret|kdf|pbkdf|scrypt|nonce)"
)
# Plaintext field names that suggest we caught data before encryption.
PLAINTEXT_HINT_RE = re.compile(
    r"(?i)(user(name)?|pass(word|wd)?|login|mobile|phone|email|account|"
    r"timestamp|\bts\b|device|imei|uuid|appkey|apikey)"
)
# Network syscalls whose buffers carry the actual request/response bytes.
NET_SYSCALLS = {
    "connect", "sendto", "recvfrom", "sendmsg", "recvmsg", "write", "read",
    "sendmmsg", "recvmmsg",
}

# Keys that plausibly hold a buffer / hexdump, a backtrace, or a name.
BUF_KEYS = ("hexdump", "hex", "buf", "buffer", "data", "payload", "content", "bytes")
STACK_KEYS = ("stack", "backtrace", "stacktrace", "bt", "unwind", "callstack")
NAME_KEYS = ("name", "symbol", "sym", "syscall", "func", "function", "probe", "point", "event")


def _iter_events(raw_text):
    """Yield event dicts from JSON-array, JSON-lines, or (as a last resort) None."""
    stripped = raw_text.strip()
    if not stripped:
        return
    # Whole-file JSON (array or single object).
    try:
        doc = json.loads(stripped)
        if isinstance(doc, list):
            for e in doc:
                yield e if isinstance(e, dict) else {"value": e}
            return
        if isinstance(doc, dict):
            # Some builds wrap events under a top-level key.
            for k in ("events", "records", "data", "items"):
                if isinstance(doc.get(k), list):
                    for e in doc[k]:
                        yield e if isinstance(e, dict) else {"value": e}
                    return
            yield doc
            return
    except ValueError:
        pass
    # JSON-lines.
    any_line = False
    for line in stripped.splitlines():
        line = line.strip().rstrip(",")
        if not line or line in "[]":
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            any_line = True
            yield obj
    if not any_line:
        # Not JSON at all — signal caller to fall back to text scraping.
        yield {"__nonjson__": True, "raw": raw_text}


PREVIEW_CHARS = 400


def _cut_preview(text, redact=None):
    """Redact the full buffer text, then cut it to PREVIEW_CHARS characters."""
    if redact is not None:
        text = redact(text)
    return text[:PREVIEW_CHARS]


def _printable_preview(data, redact=None):
    """Return a readable preview of bytes/str, or None if mostly binary.

    redact, if given, is applied to the full text before the cut, so a declared literal
    that crosses the PREVIEW_CHARS boundary cannot leave a prefix behind.
    """
    if isinstance(data, list):
        try:
            data = bytes(int(x) & 0xFF for x in data)
        except (ValueError, TypeError):
            data = None
    if isinstance(data, str):
        # Maybe it's a hex string like "47 45 54 ..." or "474554...".
        hexonly = re.sub(r"[^0-9a-fA-F]", "", data)
        if len(hexonly) >= 8 and len(hexonly) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", hexonly):
            try:
                b = bytes.fromhex(hexonly)
                txt = b.decode("utf-8", "replace")
                if _ratio_printable(txt) > 0.8:
                    return _cut_preview(txt, redact)
            except ValueError:
                pass
        return _cut_preview(data, redact) if _ratio_printable(data) > 0.8 else None
    if isinstance(data, (bytes, bytearray)):
        txt = bytes(data).decode("utf-8", "replace")
        return _cut_preview(txt, redact) if _ratio_printable(txt) > 0.8 else None
    return None


def _ratio_printable(s):
    if not s:
        return 0.0
    ok = sum(1 for c in s if c == "\n" or c == "\t" or 32 <= ord(c) < 127)
    return ok / len(s)


def _collect(obj, buf_keys, out):
    """Recursively gather values under key-name hints into out[list]."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(h in kl for h in buf_keys) and not isinstance(v, (dict, list)):
                out.append((k, v))
            elif any(h in kl for h in buf_keys) and isinstance(v, list):
                out.append((k, v))
            _collect(v, buf_keys, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, buf_keys, out)


def _first_name(ev):
    for k in NAME_KEYS:
        for kk in (k, k.upper(), k.capitalize()):
            if isinstance(ev.get(kk), str) and ev[kk].strip():
                return ev[kk].strip()
    # nested search
    found = []
    _collect(ev, NAME_KEYS, found)
    for _, v in found:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def normalize(ev, redact=None):
    """Turn a raw stackplz event into a compact, uniform record.

    redact, if given, removes declared literals from each buffer before it is cut.
    """
    name = _first_name(ev) or "?"

    bufs = []
    _collect(ev, BUF_KEYS, bufs)
    previews = []
    for k, v in bufs:
        p = _printable_preview(v, redact)
        if p is not None:
            previews.append({"field": k, "text": p})

    stacks = []
    _collect(ev, STACK_KEYS, stacks)
    frames = []
    for _, v in stacks:
        if isinstance(v, list):
            for fr in v[:24]:
                frames.append(fr if isinstance(fr, str) else json.dumps(fr))
        elif isinstance(v, str):
            frames.extend(v.splitlines()[:24])

    comm = ev.get("comm") or ev.get("Comm") or ev.get("process")
    pid = ev.get("pid") or ev.get("Pid") or ev.get("PID")
    tid = ev.get("tid") or ev.get("Tid") or ev.get("TID")

    # Relevance scoring.
    reasons = []
    if name and CRYPTO_NAME_RE.search(name):
        reasons.append("crypto/sign symbol")
    base = os.path.basename(str(name)).lower()
    if base in NET_SYSCALLS or name in NET_SYSCALLS:
        reasons.append("network syscall (request bytes)")
    for pv in previews:
        if PLAINTEXT_HINT_RE.search(pv["text"]):
            reasons.append("plaintext auth-looking buffer")
            break
    if any(CRYPTO_NAME_RE.search(f) for f in frames):
        reasons.append("crypto frame in backtrace")

    return {
        "name": name,
        "comm": comm,
        "pid": pid,
        "tid": tid,
        "buffers": previews,
        "stack": frames[:24],
        "relevance": sorted(set(reasons)),
    }


def scrape_text(raw_text, redact=None):
    """Fallback for non-JSON logs: keep lines that mention a probe or buffer."""
    recs = []
    for line in raw_text.splitlines():
        if CRYPTO_NAME_RE.search(line) or PLAINTEXT_HINT_RE.search(line):
            recs.append({"name": "(text)", "comm": None, "pid": None, "tid": None,
                         "buffers": [{"field": "line", "text": _cut_preview(line.strip(), redact)}],
                         "stack": [], "relevance": ["text-match"]})
    return recs


def _redactor(literals):
    """Return a function that removes the declared literals from one string."""
    def redact(text):
        return redact_text(text, literals)[0]
    return redact


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Normalize stackplz JSON/text output into structured events + ledger hints."
    )
    ap.add_argument("input", help="stackplz_events.json or stackplz_stdout.log")
    ap.add_argument("--out", default="./re_out", help="output directory (default ./re_out)")
    add_literal_args(ap)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        sys.stderr.write("ERROR: input not found: %s\n" % args.input)
        return 2
    try:
        literals = resolve_literal_args(args)
    except LiteralError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    with open(args.input, "r", encoding="utf-8", errors="replace") as fh:
        raw_text = fh.read()

    redact = _redactor(literals)
    events = []
    nonjson = False
    for ev in _iter_events(raw_text):
        if ev.get("__nonjson__"):
            nonjson = True
            break
        events.append(normalize(ev, redact))

    if nonjson:
        sys.stderr.write(
            "Input is not stackplz JSON (run with --json, or point me at the -o file); "
            "scraping the text log for leads instead.\n"
        )
        events = scrape_text(raw_text, redact)

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "stackplz_events.json")
    # Avoid clobbering the input if it is already named that.
    if os.path.abspath(out_path) == os.path.abspath(args.input):
        out_path = os.path.join(args.out, "stackplz_events.normalized.json")
    if os.path.islink(out_path):
        sys.stderr.write("ERROR: output path is a symbolic link; refusing to write through it: %s\n" % out_path)
        return 2
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2, ensure_ascii=False, default=str)
    sys.stderr.write("Wrote %d event(s) -> %s\n" % (len(events), out_path))
    apply_literals(literals, args.out, files=[out_path])

    interesting = [e for e in events if e.get("relevance")]
    if not interesting:
        sys.stderr.write(
            "\nNo crypto/auth-looking events surfaced. If you expected a hit, widen "
            "the trace (e.g. --syscalls %net,%file), confirm the --point/--brk offset, "
            "or read the raw log directly.\n"
        )
        return 0

    sys.stderr.write("\nRelevant events (candidate evidence):\n")
    for e in interesting:
        why = ", ".join(e["relevance"])
        # Comm, name and field come from the raw event, so they pass through the literal pass too.
        head = "  [%s] %s" % (redact(str(e.get("comm") or "?")), redact(str(e.get("name"))))
        sys.stderr.write("%s  <%s>\n" % (head, why))
        for pv in e["buffers"][:2]:
            preview = redact(pv["text"]).replace("\n", "\\n")
            sys.stderr.write("      %s: %s\n" % (redact(str(pv["field"])), preview[:160]))

    # Ledger hints — the model promotes the durable ones with a verbatim quote.
    sys.stderr.write(
        "\nLedger hints (promote with a verbatim quote from the buffer above):\n"
        "  # a native sign symbol actually executed on this request path:\n"
        "  findings.py --out %s add-fact --phase 4 --rung REACHABLE \\\n"
        "    --claim \"<symbol> runs during login\" --tool stackplz --ref \"%s\" \\\n"
        "    --verbatim \"<paste the buffer/frame line>\"\n"
        "  # pre-encryption plaintext captured at a uprobe/brk (Gate A blob defeated):\n"
        "  findings.py --out %s add-fact --phase 3 --rung CONTROLLABLE \\\n"
        "    --claim \"plaintext body before app-layer crypto\" --tool stackplz \\\n"
        "    --ref \"%s\" --verbatim \"<paste plaintext>\"\n"
        % (args.out, out_path, args.out, out_path)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
