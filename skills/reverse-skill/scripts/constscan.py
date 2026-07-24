#!/usr/bin/env python3
"""
constscan.py - crypto-constant fingerprint scanner (P4 / crypto-algorithm-id).

Reimplements the icloudza/algokiller idea in lightweight stdlib Python: identify
a crypto/signing primitive by fingerprinting its well-known constants, and grade
every hit with an *evidence taxonomy* so a lone magic number is never promoted to
"cipher".

Input may be a binary (.so) OR a text file (IDA / Hex-Rays pseudocode); the type
is auto-detected from content.

Verdict taxonomy (per fingerprint hit):
  real      - a full / near-full table matched (e.g. >=4 consecutive SHA-256 K
              words, or a full S-box). Strong: names the primitive.
  real_simd - matched, but in a form that suggests a SIMD / T-table layout
              (e.g. the AES Te0 first word 0xc66363a5).
  weak      - short / ambiguous evidence (base64 alphabet alone, a single HMAC
              pad, a marker word). Suggestive, not proof.
  alu_only  - a lone magic that ALSO appears in non-crypto / ALU contexts:
              specifically the 0x9e3779b9 golden ratio and single CRC polynomials
              found in isolation. constscan FLAGS these; it must never assert
              "TEA cipher" from 0x9e3779b9 alone.

Output: <out>/const_fingerprints.json
  [{name, primitive, verdict, hits:[{offset_or_line, endianness}], count}]
A ranked summary (real first) is printed to stderr. Exit code is always 0.

No network. Stdlib only.
"""
import argparse
import bisect
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Fingerprint table.
#
# type:
#   table       list of 32-bit words expected CONTIGUOUS in .rodata (SHA/MD5 K
#               tables, IVs, Blowfish P-array). Graded by longest matched run.
#   wordset     list of 32-bit words used as independent immediates (SM3 T
#               constants, SM4 FK). Graded by count of distinct words matched.
#   bytes       a literal byte table / S-box. Graded full vs half.
#   simd_word   one distinctive 32-bit T-table word -> real_simd.
#   single_word one lone magic shared with ALU/non-crypto code -> alu_only.
#   marker      one distinctive-but-short crypto marker word -> weak.
#   string      an ASCII alphabet / literal -> weak.
#   repbyte     a repeated-byte run (HMAC ipad/opad) -> weak.
# ---------------------------------------------------------------------------
FINGERPRINTS = [
    {
        "name": "SHA-256 K",
        "primitive": "SHA-256",
        "type": "table",
        "min_real": 4,
        "words": [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
            0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
            0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        ],
    },
    {
        "name": "SHA-256 IV (H0)",
        "primitive": "SHA-256",
        "type": "table",
        "min_real": 4,
        "words": [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
            0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
        ],
    },
    {
        "name": "SHA-1 IV",
        "primitive": "SHA-1",
        "type": "table",
        "min_real": 4,
        "words": [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0],
    },
    {
        "name": "MD5 sine T-table",
        "primitive": "MD5",
        "type": "table",
        "min_real": 4,
        "words": [
            0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
            0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
            0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
        ],
    },
    {
        "name": "AES S-box",
        "primitive": "AES",
        "type": "bytes",
        "table": [
            0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5,
            0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
            0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0,
            0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        ],
    },
    {
        "name": "AES Inv S-box",
        "primitive": "AES",
        "type": "bytes",
        "table": [
            0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38,
            0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
            0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87,
            0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
        ],
    },
    {
        "name": "AES Te0 (T-table)",
        "primitive": "AES",
        "type": "simd_word",
        "word": 0xc66363a5,
    },
    {
        "name": "SM3 IV",
        "primitive": "SM3",
        "type": "table",
        "min_real": 4,
        "words": [
            0x7380166f, 0x4914b2b9, 0x172442d7, 0xda8a0600,
            0xa96f30bc, 0x163138aa, 0xe38dee4d, 0xb0fb0e4e,
        ],
    },
    {
        "name": "SM3 T constants (Tj)",
        "primitive": "SM3",
        "type": "wordset",
        "min_real": 2,
        "words": [0x79cc4519, 0x7a879d8a],
    },
    {
        "name": "SM4 S-box",
        "primitive": "SM4",
        "type": "bytes",
        "table": [
            0xd6, 0x90, 0xe9, 0xfe, 0xcc, 0xe1, 0x3d, 0xb7,
            0x16, 0xb6, 0x14, 0xc2, 0x28, 0xfb, 0x2c, 0x05,
            0x2b, 0x67, 0x9a, 0x76, 0x2a, 0xbe, 0x04, 0xc3,
            0xaa, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
        ],
    },
    {
        "name": "SM4 FK",
        "primitive": "SM4",
        "type": "wordset",
        "min_real": 3,
        "words": [0xa3b1bac6, 0x56aa3350, 0x677d9197, 0xb27022dc],
    },
    {
        "name": "SM4 CK",
        "primitive": "SM4",
        "type": "table",
        "min_real": 4,
        "words": [
            0x00070e15, 0x1c232a31, 0x383f464d, 0x545b6269,
            0x70777e85, 0x8c939aa1, 0xa8afb6bd, 0xc4cbd2d9,
        ],
    },
    {
        "name": "TEA/XTEA/XXTEA delta (golden ratio)",
        "primitive": "TEA/XTEA/XXTEA",
        "type": "single_word",
        "word": 0x9e3779b9,
        "note": "0x9e3779b9 = 2^32/phi; also a common hash/PRNG mixer. Lone hit "
                "is ALU-only evidence, NOT proof of a TEA cipher.",
    },
    {
        "name": "CRC32 reflected polynomial",
        "primitive": "CRC32",
        "type": "single_word",
        "word": 0xEDB88320,
        "note": "Lone CRC polynomial appears in non-crypto integrity code.",
    },
    {
        "name": "CRC32 normal polynomial",
        "primitive": "CRC32",
        "type": "single_word",
        "word": 0x04C11DB7,
        "note": "Lone CRC polynomial appears in non-crypto integrity code.",
    },
    {
        "name": "Base64 std alphabet",
        "primitive": "Base64",
        "type": "string",
        "string": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    },
    {
        "name": "HMAC ipad",
        "primitive": "HMAC",
        "type": "repbyte",
        "byte": 0x36,
        "minrun": 16,
    },
    {
        "name": "HMAC opad",
        "primitive": "HMAC",
        "type": "repbyte",
        "byte": 0x5c,
        "minrun": 16,
    },
    {
        "name": "GHASH R constant",
        "primitive": "GHASH/GCM",
        "type": "marker",
        "word": 0xE1000000,
    },
    {
        "name": "Poly1305 clamp mask",
        "primitive": "Poly1305",
        "type": "marker",
        "word": 0x0ffffffc,
    },
    {
        "name": "Blowfish P-array (pi digits)",
        "primitive": "Blowfish",
        "type": "table",
        "min_real": 4,
        "words": [
            0x243f6a88, 0x85a308d3, 0x13198a2e, 0x03707344,
            0xa4093822, 0x299f31d0, 0x082efa98, 0xec4e6c89,
        ],
    },
]

VERDICT_ORDER = {"real": 0, "real_simd": 1, "weak": 2, "alu_only": 3}
HEXD = set("0123456789abcdef")
HIT_CAP = 100

# ---------------------------------------------------------------------------
# Detection helpers.
# ---------------------------------------------------------------------------

def looks_like_text(raw):
    """Heuristic: content is text pseudocode rather than a binary."""
    chunk = raw[:8192]
    if not chunk:
        return True
    if b"\x00" in chunk:
        return False
    printable = set(range(0x20, 0x7f)) | {0x09, 0x0a, 0x0d, 0x0c}
    nonprint = sum(1 for b in chunk if b not in printable)
    return (nonprint / len(chunk)) < 0.10


def word_bytes(w, endian):
    return w.to_bytes(4, "little" if endian == "le" else "big")


def find_all_bytes(data, pat, cap=HIT_CAP):
    offs = []
    start = 0
    n = len(pat)
    if n == 0:
        return offs
    while True:
        i = data.find(pat, start)
        if i < 0:
            break
        offs.append(i)
        start = i + 1
        if len(offs) >= cap:
            break
    return offs


# ---------------------------------------------------------------------------
# Binary scanners.
# ---------------------------------------------------------------------------

def scan_table_binary(data, words):
    """Return (longest_run, hits). Searches contiguous prefixes LE and BE."""
    hits = []
    best_run = 0
    for endian in ("le", "be"):
        L = len(words)
        while L >= 2:
            pat = b"".join(word_bytes(w, endian) for w in words[:L])
            offs = find_all_bytes(data, pat)
            if offs:
                best_run = max(best_run, L)
                for o in offs:
                    hits.append({"offset_or_line": o, "endianness": endian})
                break
            L -= 1
    return best_run, hits


def scan_wordset_binary(data, words):
    """Return (distinct_matched, hits). Each word searched independently."""
    hits = []
    matched = 0
    for w in words:
        found = False
        for endian in ("le", "be"):
            offs = find_all_bytes(data, word_bytes(w, endian))
            if offs:
                found = True
                for o in offs:
                    hits.append({"offset_or_line": o, "endianness": endian})
        if found:
            matched += 1
    return matched, hits


def scan_bytes_binary(data, table):
    hits = []
    full = bytes(table)
    offs = find_all_bytes(data, full)
    if offs:
        for o in offs:
            hits.append({"offset_or_line": o, "endianness": "bytes"})
        return "full", hits
    half = bytes(table[: max(8, len(table) // 2)])
    offs = find_all_bytes(data, half)
    if offs:
        for o in offs:
            hits.append({"offset_or_line": o, "endianness": "bytes"})
        return "half", hits
    return None, hits


def scan_word_binary(data, w):
    hits = []
    for endian in ("le", "be"):
        for o in find_all_bytes(data, word_bytes(w, endian)):
            hits.append({"offset_or_line": o, "endianness": endian})
    return hits


def scan_repbyte_binary(data, b, minrun):
    hits = []
    pat = bytes([b]) * minrun
    for o in find_all_bytes(data, pat):
        hits.append({"offset_or_line": o, "endianness": "run"})
    return hits


def scan_string_binary(data, s):
    hits = []
    for o in find_all_bytes(data, s.encode("latin-1")):
        hits.append({"offset_or_line": o, "endianness": "string"})
    return hits


# ---------------------------------------------------------------------------
# Text scanners.
# ---------------------------------------------------------------------------

def make_line_of(text):
    nl = [i for i, c in enumerate(text) if c == "\n"]

    def line_of(pos):
        return bisect.bisect_right(nl, pos) + 1

    return line_of


def _hex_boundary_ok(tl, i, ln):
    before = tl[i - 1] if i > 0 else " "
    after = tl[i + ln] if i + ln < len(tl) else " "
    return (before not in HEXD) and (after not in HEXD)


def text_find_word(tl, w, line_of, cap=HIT_CAP):
    """Find a 32-bit word by its 8-digit hex token (with/without 0x, any case)."""
    hexstr = "%08x" % w
    ln = len(hexstr)
    lines = []
    start = 0
    while True:
        i = tl.find(hexstr, start)
        if i < 0:
            break
        start = i + 1
        if _hex_boundary_ok(tl, i, ln):
            lines.append(line_of(i))
            if len(lines) >= cap:
                break
    return lines


def scan_words_text(tl, words, line_of):
    """Distinct-word count + line hits (used for both table & wordset in text)."""
    hits = []
    matched = 0
    for w in words:
        lines = text_find_word(tl, w, line_of)
        if lines:
            matched += 1
            for ln in lines:
                hits.append({"offset_or_line": ln, "endianness": "text"})
    return matched, hits


def _byte_regex(table, n):
    sep = r"[^0-9a-fx]{1,6}"
    parts = [r"(?:0x)?%02x" % b for b in table[:n]]
    return re.compile(sep.join(parts))


def scan_bytes_text(tl, table, line_of):
    # Contiguous hex-string form (S-box embedded as a hex literal).
    contig = "".join("%02x" % b for b in table[:16])
    i = tl.find(contig)
    if i >= 0:
        return "full", [{"offset_or_line": line_of(i), "endianness": "text"}]
    m = _byte_regex(table, 16).search(tl)
    if m:
        return "full", [{"offset_or_line": line_of(m.start()), "endianness": "text"}]
    m = _byte_regex(table, 8).search(tl)
    if m:
        return "half", [{"offset_or_line": line_of(m.start()), "endianness": "text"}]
    return None, []


def scan_string_text(text, s, line_of):
    hits = []
    start = 0
    while True:
        i = text.find(s, start)
        if i < 0:
            break
        hits.append({"offset_or_line": line_of(i), "endianness": "text"})
        start = i + 1
        if len(hits) >= HIT_CAP:
            break
    return hits


# ---------------------------------------------------------------------------
# Per-fingerprint dispatch + verdict grading.
# ---------------------------------------------------------------------------

def grade_binary(fp, data):
    t = fp["type"]
    if t == "table":
        run, hits = scan_table_binary(data, fp["words"])
        if not hits:
            return None
        verdict = "real" if run >= fp["min_real"] else "weak"
        return verdict, hits
    if t == "wordset":
        matched, hits = scan_wordset_binary(data, fp["words"])
        if not hits:
            return None
        verdict = "real" if matched >= fp["min_real"] else "weak"
        return verdict, hits
    if t == "bytes":
        level, hits = scan_bytes_binary(data, fp["table"])
        if not hits:
            return None
        return ("real" if level == "full" else "weak"), hits
    if t == "simd_word":
        hits = scan_word_binary(data, fp["word"])
        return ("real_simd", hits) if hits else None
    if t == "single_word":
        hits = scan_word_binary(data, fp["word"])
        return ("alu_only", hits) if hits else None
    if t == "marker":
        hits = scan_word_binary(data, fp["word"])
        return ("weak", hits) if hits else None
    if t == "repbyte":
        hits = scan_repbyte_binary(data, fp["byte"], fp["minrun"])
        return ("weak", hits) if hits else None
    if t == "string":
        hits = scan_string_binary(data, fp["string"])
        return ("weak", hits) if hits else None
    return None


def grade_text(fp, text, tl, line_of):
    t = fp["type"]
    if t in ("table", "wordset"):
        matched, hits = scan_words_text(tl, fp["words"], line_of)
        if not hits:
            return None
        verdict = "real" if matched >= fp["min_real"] else "weak"
        return verdict, hits
    if t == "bytes":
        level, hits = scan_bytes_text(tl, fp["table"], line_of)
        if not hits:
            return None
        return ("real" if level == "full" else "weak"), hits
    if t == "simd_word":
        lines = text_find_word(tl, fp["word"], line_of)
        if not lines:
            return None
        return "real_simd", [{"offset_or_line": ln, "endianness": "text"} for ln in lines]
    if t == "single_word":
        lines = text_find_word(tl, fp["word"], line_of)
        if not lines:
            return None
        return "alu_only", [{"offset_or_line": ln, "endianness": "text"} for ln in lines]
    if t == "marker":
        lines = text_find_word(tl, fp["word"], line_of)
        if not lines:
            return None
        return "weak", [{"offset_or_line": ln, "endianness": "text"} for ln in lines]
    if t == "string":
        hits = scan_string_text(text, fp["string"], line_of)
        return ("weak", hits) if hits else None
    if t == "repbyte":
        # A literal repeated-byte run is not meaningfully expressed in pseudocode.
        return None
    return None


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------

def run(path, out_dir):
    with open(path, "rb") as fh:
        raw = fh.read()

    is_text = looks_like_text(raw)
    results = []

    if is_text:
        text = raw.decode("latin-1")
        tl = text.lower()
        line_of = make_line_of(text)
        for fp in FINGERPRINTS:
            graded = grade_text(fp, text, tl, line_of)
            if graded is None:
                continue
            verdict, hits = graded
            results.append(_result(fp, verdict, hits))
    else:
        for fp in FINGERPRINTS:
            graded = grade_binary(fp, raw)
            if graded is None:
                continue
            verdict, hits = graded
            results.append(_result(fp, verdict, hits))

    results.sort(key=lambda r: (VERDICT_ORDER.get(r["verdict"], 9), -r["count"], r["name"]))

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "const_fingerprints.json")
    with open(out_path, "w") as fh:
        json.dump(results, fh, indent=2)

    _print_summary(results, path, is_text, out_path)
    return 0


def _result(fp, verdict, hits):
    r = {
        "name": fp["name"],
        "primitive": fp["primitive"],
        "verdict": verdict,
        "hits": hits[:HIT_CAP],
        "count": len(hits),
    }
    if "note" in fp:
        r["note"] = fp["note"]
    return r


def _print_summary(results, path, is_text, out_path):
    mode = "text/pseudocode" if is_text else "binary"
    sys.stderr.write("constscan: %s (%s)\n" % (path, mode))
    if not results:
        sys.stderr.write("no strong crypto constants found\n")
        sys.stderr.write("wrote %s\n" % out_path)
        return
    label = {
        "real": "REAL",
        "real_simd": "REAL(simd)",
        "weak": "weak",
        "alu_only": "ALU-ONLY",
    }
    sys.stderr.write("ranked fingerprints (strongest first):\n")
    for r in results:
        sys.stderr.write(
            "  [%-10s] %-8s %-32s x%d\n"
            % (label.get(r["verdict"], r["verdict"]), r["primitive"], r["name"], r["count"])
        )
    if any(r["verdict"] == "alu_only" for r in results):
        sys.stderr.write(
            "  note: alu_only hits (e.g. 0x9e3779b9) are NOT proof of a cipher; "
            "corroborate before naming a primitive.\n"
        )
    sys.stderr.write("wrote %s\n" % out_path)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fingerprint well-known crypto constants in a binary (.so) or "
        "IDA/Hex-Rays pseudocode text, with an evidence-graded verdict."
    )
    ap.add_argument("path", help="binary (.so) or text pseudocode file to scan")
    ap.add_argument("--out", default=".", help="output directory (default: .)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.path):
        sys.stderr.write("constscan: not a file: %s\n" % args.path)
        return 2
    return run(args.path, args.out)


if __name__ == "__main__":
    sys.exit(main())
