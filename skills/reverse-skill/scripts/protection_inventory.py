#!/usr/bin/env python3
"""
protection_inventory.py - static inventory of protection indicators for research.

Usage:
    protection_inventory.py PATH [--max-bytes N]

Scans a file, or every regular file under a directory, for names and markers that
protection schemes commonly use: anti-debugging APIs, code-signing checks, licensing
and activation terms, license-server URLs, certificate pinning, packer and protector
markers, anti-VM and root or emulator checks, and instrumentation-detection strings.
Prints one JSON object.

What a hit means: the name or marker is present in the bytes, at the listed offsets.
It does not show that the code runs, that a check is enforced, or where the check
lives. Use the offsets to find the code in a disassembler, and describe the mechanism
from that code with its evidence. Weak indicators are generic words: read them in
context before citing them.

Nothing is executed, no check is evaluated or changed, and symlinks are not followed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from target_identify import identify_file  # noqa: E402

DEFAULT_MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 2000
MAX_OFFSETS = 5
MAX_URLS = 20

# (indicator id, category, strength, patterns). Matching is case-insensitive and
# runs over both ASCII and UTF-16LE encodings. "strong" names a specific API, product
# or marker; "weak" is a generic word that needs context before it is cited.
CATALOG = [
    ("win_debugger_api", "anti_debug", "strong", [
        "IsDebuggerPresent", "CheckRemoteDebuggerPresent", "NtQueryInformationProcess",
        "NtSetInformationThread", "DebugActiveProcess"]),
    ("posix_tracer_check", "anti_debug", "strong", [
        "PTRACE_TRACEME", "TracerPid"]),
    ("proc_status_read", "anti_debug", "weak", [
        "/proc/self/status"]),
    ("macos_debugger_check", "anti_debug", "strong", [
        "P_TRACED", "kinfo_proc"]),
    ("timing_api", "anti_debug", "weak", [
        "GetTickCount", "QueryPerformanceCounter", "clock_gettime"]),
    ("code_signing_windows", "code_signing", "strong", [
        "WinVerifyTrust", "CryptQueryObject", "CertGetCertificateChain"]),
    ("code_signing_apple", "code_signing", "strong", [
        "SecStaticCodeCheckValidity", "SecCodeCheckValidity", "SecRequirementCreateWithString"]),
    ("android_signature_check", "code_signing", "strong", [
        "GET_SIGNATURES", "GET_SIGNING_CERTIFICATES"]),
    ("integrity_terms", "integrity", "weak", [
        "integrity check", "tamper", "checksum mismatch", "signature mismatch"]),
    ("licensing_terms", "licensing", "weak", [
        "license key", "licence key", "product key", "serial number", "activation",
        "trial period", "hardware id", "machine id", "hwid"]),
    ("tls_pinning_api", "tls_pinning", "strong", [
        "CertificatePinner", "TrustKit", "SSLPinningMode", "AFSecurityPolicy",
        "NSPinnedDomains", "pinnedCertificates"]),
    ("tls_pinning_terms", "tls_pinning", "weak", [
        "certificate pinning", "public key pin", "sha256/"]),
    ("packer_markers", "packer", "strong", [
        "UPX!", "UPX0", "UPX1", ".themida", "Themida", ".vmp0", ".vmp1", "VMProtect",
        ".enigma1", "Enigma Protector", "ASPack", ".aspack", "MPRESS", "Obsidium",
        "PECompact", "Armadillo"]),
    ("android_protector_markers", "packer", "strong", [
        "DexProtector", "DexGuard", "Bangcle", "ijiami", "libjiagu", "libdexprotect"]),
    ("anti_vm_terms", "anti_vm", "weak", [
        "VMware", "VirtualBox", "VBOX", "vmtoolsd", "qemu", "Hyper-V"]),
    ("android_root_emulator_checks", "anti_root", "weak", [
        "/system/xbin/su", "magisk", "test-keys", "ro.debuggable", "goldfish", "ranchu"]),
    ("instrumentation_terms", "instrumentation_detection", "weak", [
        "frida-agent", "gum-js-loop", "linjector", "frida"]),
]

# Network endpoints are kept only when the URL itself suggests a protection role.
URL_RE = re.compile(rb"https?://[A-Za-z0-9.-]{3,253}(?::\d{1,5})?/[\x21-\x7e]{0,160}",
                    re.IGNORECASE)
URL_TERMS_RE = re.compile(rb"licen[cs]e|activat|entitle|register|drm|check-?in|serial|verif|auth",
                          re.IGNORECASE)


def _entries():
    entries = []
    for ind_id, category, strength, patterns in CATALOG:
        for text in patterns:
            entries.append((ind_id, category, strength, text))
    return entries


_META = _entries()


def _build(encoding, strength):
    # Strong names match exactly: case-insensitive "MPRESS" would match inside "compress".
    # Weak words match in any case. Longest first, so "frida-agent" wins over "frida".
    flags = re.IGNORECASE if strength == "weak" else 0
    chosen = [i for i in range(len(_META)) if _META[i][2] == strength]
    order = sorted(chosen, key=lambda i: -len(_META[i][3]))
    alts = []
    for idx in order:
        text = _META[idx][3]
        raw = text.encode("ascii") if encoding == "ascii" else text.encode("utf-16-le")
        alts.append(b"(?P<p%d>" % idx + re.escape(raw) + b")")
    return re.compile(b"|".join(alts), flags)


_MATCHERS = [(_build(enc, strength), enc)
             for enc in ("ascii", "utf-16le")
             for strength in ("strong", "weak")]


def scan_bytes(data):
    """Return (indicator records, URL records) for one file's bytes."""
    found = {}
    for regex, encoding in _MATCHERS:
        for m in regex.finditer(data):
            idx = int(m.lastgroup[1:])
            rec = found.setdefault((idx, encoding), {"count": 0, "offsets": []})
            rec["count"] += 1
            if len(rec["offsets"]) < MAX_OFFSETS:
                rec["offsets"].append(m.start())
    indicators = []
    for (idx, encoding), rec in sorted(found.items()):
        ind_id, category, strength, text = _META[idx]
        indicators.append({"id": ind_id, "category": category, "strength": strength,
                           "pattern": text, "encoding": encoding,
                           "count": rec["count"], "offsets": rec["offsets"]})
    urls = []
    seen = set()
    for m in URL_RE.finditer(data):
        raw = m.group(0)
        if not URL_TERMS_RE.search(raw):
            continue
        text = raw.decode("ascii", "replace")[:200]
        if text in seen:
            continue
        seen.add(text)
        urls.append({"url": text, "offset": m.start()})
        if len(urls) >= MAX_URLS:
            break
    return indicators, urls


def scan_file(path, rel):
    size = os.path.getsize(path)
    try:
        ident = identify_file(path)
        fmt, arch, sha256 = ident["format"], ident["arch"], ident["sha256"]
    except (OSError, ValueError, struct.error):
        fmt, arch, sha256 = "unknown (identification failed)", None, None
    with open(path, "rb") as f:
        data = f.read()
    indicators, urls = scan_bytes(data)
    return {"path": rel, "size": size, "sha256": sha256, "format": fmt, "arch": arch,
            "indicators": indicators, "urls": urls}


def collect(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            out.append(p)
            if len(out) >= MAX_FILES:
                return out, True
    return out, False


def summarize(files):
    summary = {}
    for f in files:
        for ind in f["indicators"]:
            kinds = summary.setdefault(ind["category"], {"strong": 0, "weak": 0})
            kinds[ind["strength"]] += 1
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Static inventory of protection indicators for research (JSON to stdout).")
    ap.add_argument("path", help="file or directory to scan")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                    help="skip files larger than this many bytes (default 256 MiB)")
    args = ap.parse_args(argv)

    truncated = False
    if os.path.isfile(args.path):
        kind = "file"
        base = os.path.dirname(os.path.abspath(args.path))
        paths = [args.path]
    elif os.path.isdir(args.path):
        kind = "directory"
        base = os.path.abspath(args.path)
        paths, truncated = collect(args.path)
    else:
        sys.stderr.write("ERROR: not a regular file or directory: %s\n" % args.path)
        return 2

    scanned, skipped = [], []
    for p in paths:
        rel = os.path.relpath(p, base)
        if os.path.getsize(p) > args.max_bytes:
            skipped.append(rel)
            continue
        scanned.append(scan_file(p, rel))

    with_hits = [f for f in scanned if f["indicators"] or f["urls"]]
    report = {
        "target": os.path.abspath(args.path),
        "kind": kind,
        "files_scanned": len(scanned),
        "files_without_hits": len(scanned) - len(with_hits),
        "skipped_large": skipped,
        "truncated": truncated,
        "summary": summarize(scanned),
        "files": with_hits,
        "limitations": [
            "A hit means the name or marker is present in the bytes, not that the code runs",
            "A check's presence is not evidence that it is enforced or where it lives",
            "Encrypted, split, or runtime-built strings are missed; absence is not evidence",
            "Weak indicators are generic words and need context before they are cited",
            "Nothing was executed and no check was evaluated or changed",
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
