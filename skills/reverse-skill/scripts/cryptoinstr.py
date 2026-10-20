#!/usr/bin/env python3
"""
cryptoinstr.py - ARM64 crypto-extension instruction detector (P4).

The hardware counterpart to constscan.py: instead of fingerprinting constants,
it fingerprints the AArch64 cryptographic-extension *instructions* a binary
actually uses (AESE/AESMC, SHA1/SHA256/SHA512, SM3/SM4, PMULL). Their presence
is high-signal evidence of a primitive that constant-scanning can miss when the
algorithm runs entirely on dedicated silicon (no S-box in .rodata).

Disassembler discovery order:
  1. llvm-objdump -d --arch=aarch64
  2. objdump -d
  3. aarch64-linux-gnu-objdump -d
  4. python `capstone` (CS_ARCH_ARM64), disassembling executable ELF sections
If none are available, an install hint is printed and the tool exits non-zero.

Output: <out>/crypto_instr.json
  [{instr, primitive, count, sample_addrs:[...up to 5]}]
A summary is printed to stderr. Exit 0 whether or not instructions are found
(0 only becomes non-zero when NO disassembler is available).

--symbol NAME restricts disassembly to one symbol (GNU objdump --disassemble=NAME,
llvm-objdump --disassemble-symbols=NAME), so a known signer can be checked for crypto
instructions without decoding or buffering the whole binary. It needs a symbol-aware
objdump; the capstone fallback has no symbol selector and is not used. An absent symbol
makes objdump emit only a header, which decodes to zero instructions: that is reported
as a confirmed empty scan of the named symbol (exit 4), never a silent whole-binary
scan. Exit 3 when no symbol-aware objdump is available.

No network.
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys

# mnemonic -> primitive is derived by prefix (see primitive_of); this set gates
# which tokens we care about.
MNEMONICS = {
    # AES
    "aese", "aesd", "aesmc", "aesimc",
    # SHA-1
    "sha1c", "sha1p", "sha1m", "sha1h", "sha1su0", "sha1su1",
    # SHA-256
    "sha256h", "sha256h2", "sha256su0", "sha256su1",
    # SHA-512
    "sha512h", "sha512h2", "sha512su0", "sha512su1",
    # SM3
    "sm3partw1", "sm3partw2", "sm3ss1",
    "sm3tt1a", "sm3tt1b", "sm3tt2a", "sm3tt2b",
    # SM4
    "sm4e", "sm4ekey",
    # GHASH / GCM carryless multiply
    "pmull", "pmull2",
}

# Order matters: check longer / more specific prefixes first.
_PRIM_PREFIXES = [
    ("sha512", "SHA-512"),
    ("sha256", "SHA-256"),
    ("sha1", "SHA-1"),
    ("sm3", "SM3"),
    ("sm4", "SM4"),
    ("aes", "AES"),
    ("pmull", "GHASH/GCM"),
]

# An instruction line: an address, a colon, then at least one hex byte of
# encoding. This distinguishes it from a `<symbol>:` label line.
INSN_LINE_RE = re.compile(r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]{2}")
# Match a known mnemonic as a whole word. No crypto mnemonic is a valid hex
# token (they all contain a non-hex letter), so this never false-matches the
# encoded-byte column, regardless of how objdump spaces it. Longest first so
# e.g. sha256h2 wins over sha256h and pmull2 over pmull.
MNE_RE = re.compile(
    r"\b(" + "|".join(sorted(MNEMONICS, key=len, reverse=True)) + r")\b"
)


def primitive_of(mn):
    for prefix, prim in _PRIM_PREFIXES:
        if mn.startswith(prefix):
            return prim
    return "unknown"


# ---------------------------------------------------------------------------
# objdump path.
# ---------------------------------------------------------------------------

def _run_objdump(cmd, path):
    try:
        proc = subprocess.run(
            cmd + [path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if not proc.stdout:
        return None
    return proc.stdout.decode("utf-8", "replace")


# llvm-objdump decodes the crypto-extension instructions only when the target
# features are enabled; without this it prints "<unknown>". GNU binutils objdump
# decodes them by default and rejects --mattr, so we only add the flag on a retry
# when we actually see undecoded instructions.
MATTR = "--mattr=+crypto,+sha2,+sha3,+aes,+sm4"


def _symbol_selector(tool, symbol):
    """objdump flag that restricts disassembly to one symbol, named per tool."""
    if tool == "llvm-objdump":
        return "--disassemble-symbols=" + symbol
    # GNU binutils objdump (and the cross-prefixed build).
    return "--disassemble=" + symbol


def disasm_with_objdump(path, symbol=None):
    """Return (insns, tool_name), or (None, None) if no objdump is usable.

    With symbol set, only that symbol is disassembled (GNU --disassemble, llvm
    --disassemble-symbols). An absent symbol makes objdump print a header and nothing
    else, which decodes to an empty list: the result is ([], tool_name), a confirmed
    empty scan of that symbol, not (None, None). Callers must not read an empty symbol
    scan as "no tool" and fall back to a whole-binary scan under a false symbol label.
    """
    candidates = [
        ["llvm-objdump", "-d", "--arch=aarch64", MATTR],
        ["objdump", "-d"],
        ["aarch64-linux-gnu-objdump", "-d"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            continue
        cmd = cmd + [_symbol_selector(cmd[0], symbol)] if symbol else cmd
        out = _run_objdump(cmd, path)
        if not out:
            continue
        # A generic objdump that is really llvm-objdump leaves crypto insns as
        # "<unknown>"; retry with the feature flags. If it is GNU objdump the
        # retry errors out (empty) and we keep the original, already-good output.
        if "<unknown>" in out and MATTR not in cmd:
            retry = _run_objdump(cmd + [MATTR], path)
            if retry:
                out = retry
        insns = _parse_objdump(out)
        # Accept the first tool that produced a real disassembly (any addressed
        # line), even if it contained no crypto instructions.
        if insns is not None:
            return insns, cmd[0]
        # The tool ran but decoded no addressed line. With a symbol selector that is a
        # confirmed empty scan of that one symbol; report it rather than trying the next
        # tool, so an absent symbol never falls through to a whole-binary scan.
        if symbol:
            return [], cmd[0]
    return None, None


def _parse_objdump(text):
    found = []
    saw_disasm = False
    for line in text.splitlines():
        m = INSN_LINE_RE.match(line)
        if not m:
            continue
        saw_disasm = True
        # Search the text after the address for a known mnemonic.
        rest = line[m.end(1):].lower()
        mm = MNE_RE.search(rest)
        if mm:
            addr = m.group(1)
            found.append((mm.group(1), "0x" + addr.lstrip("0").rjust(1, "0")))
    return found if saw_disasm else None


# ---------------------------------------------------------------------------
# capstone fallback.
# ---------------------------------------------------------------------------

def _elf_exec_sections(raw):
    """Minimal ELF parse -> list of (vaddr, code_bytes) for executable PROGBITS
    sections. Returns None if not an ELF we can parse (then caller disassembles
    the whole file)."""
    if raw[:4] != b"\x7fELF":
        return None
    ei_class = raw[4]
    ei_data = raw[5]
    endian = "<" if ei_data == 1 else ">"
    is64 = ei_class == 2
    try:
        if is64:
            e_shoff = struct.unpack_from(endian + "Q", raw, 0x28)[0]
            e_shentsize = struct.unpack_from(endian + "H", raw, 0x3A)[0]
            e_shnum = struct.unpack_from(endian + "H", raw, 0x3C)[0]
        else:
            e_shoff = struct.unpack_from(endian + "I", raw, 0x20)[0]
            e_shentsize = struct.unpack_from(endian + "H", raw, 0x2E)[0]
            e_shnum = struct.unpack_from(endian + "H", raw, 0x30)[0]
    except struct.error:
        return None
    if not e_shoff or not e_shnum:
        return None

    SHT_PROGBITS = 1
    SHF_EXECINSTR = 0x4
    out = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        try:
            if is64:
                _, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(
                    endian + "IIQQQQ", raw, off
                )
            else:
                _, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(
                    endian + "IIIIII", raw, off
                )
        except struct.error:
            continue
        if sh_type == SHT_PROGBITS and (sh_flags & SHF_EXECINSTR) and sh_size:
            code = raw[sh_offset : sh_offset + sh_size]
            if code:
                out.append((sh_addr, code))
    return out or None


def disasm_with_capstone(path):
    """Return list of (mnemonic, addr_str) or None if capstone unavailable."""
    try:
        import capstone
    except ImportError:
        return None

    arch = getattr(capstone, "CS_ARCH_ARM64", None)
    if arch is None:  # capstone >= 6 renamed the constant
        arch = getattr(capstone, "CS_ARCH_AARCH64", None)
    if arch is None:
        return None
    md = capstone.Cs(arch, capstone.CS_MODE_LITTLE_ENDIAN)

    with open(path, "rb") as fh:
        raw = fh.read()

    sections = _elf_exec_sections(raw)
    if sections is None:
        sections = [(0, raw)]

    found = []
    for vaddr, code in sections:
        for insn in md.disasm(code, vaddr):
            mn = insn.mnemonic.lower()
            if mn in MNEMONICS:
                found.append((mn, "0x%x" % insn.address))
    return found


# ---------------------------------------------------------------------------
# Aggregation + driver.
# ---------------------------------------------------------------------------

def aggregate(insns):
    agg = {}
    for mn, addr in insns:
        e = agg.get(mn)
        if e is None:
            e = {
                "instr": mn,
                "primitive": primitive_of(mn),
                "count": 0,
                "sample_addrs": [],
            }
            agg[mn] = e
        e["count"] += 1
        if len(e["sample_addrs"]) < 5:
            e["sample_addrs"].append(addr)
    results = list(agg.values())
    results.sort(key=lambda r: (r["primitive"], -r["count"], r["instr"]))
    return results


def _print_hint():
    sys.stderr.write(
        "cryptoinstr: no AArch64 disassembler available.\n"
        "  Install one of:\n"
        "    brew install llvm           # provides llvm-objdump\n"
        "    (or a binutils objdump / aarch64-linux-gnu-objdump)\n"
        "    pip install capstone        # python fallback disassembler\n"
    )


def run(path, out_dir, symbol=None):
    insns, tool = disasm_with_objdump(path, symbol)
    if symbol is None and insns is None:
        # Whole-binary capstone fallback; capstone has no symbol selector, so it is
        # not used when a symbol was requested.
        insns = disasm_with_capstone(path)
        tool = "capstone" if insns is not None else None

    if insns is None:
        if symbol is not None:
            sys.stderr.write(
                "cryptoinstr: --symbol needs a symbol-aware objdump "
                "(llvm-objdump or GNU binutils objdump); none is available\n"
            )
            return 3
        _print_hint()
        return 3

    results = aggregate(insns)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "crypto_instr.json")
    with open(out_path, "w") as fh:
        json.dump(results, fh, indent=2)

    scope = (" symbol %r" % symbol) if symbol else ""
    sys.stderr.write("cryptoinstr: %s%s (disassembler: %s)\n" % (path, scope, tool))
    if symbol is not None and not insns:
        sys.stderr.write(
            "no instructions disassembled for symbol %r: it is absent from this binary, "
            "is not a function, or has no code\n" % symbol
        )
        sys.stderr.write("wrote %s\n" % out_path)
        return 4
    if not results:
        sys.stderr.write("no ARM64 crypto-extension instructions found\n")
    else:
        prims = {}
        for r in results:
            prims[r["primitive"]] = prims.get(r["primitive"], 0) + r["count"]
        sys.stderr.write("crypto-extension instructions detected:\n")
        for r in results:
            sys.stderr.write(
                "  %-10s %-12s x%-6d  e.g. %s\n"
                % (r["instr"], r["primitive"], r["count"], ", ".join(r["sample_addrs"][:3]))
            )
        sys.stderr.write(
            "primitives: "
            + ", ".join("%s(%d)" % (p, c) for p, c in sorted(prims.items()))
            + "\n"
        )
    sys.stderr.write("wrote %s\n" % out_path)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Detect AArch64 crypto-extension instructions (AES/SHA/SM3/"
        "SM4/PMULL) in an ELF .so via objdump or capstone."
    )
    ap.add_argument("binary", help="ARM64 ELF binary (.so) to disassemble")
    ap.add_argument("--out", default=".", help="output directory (default: .)")
    ap.add_argument(
        "--symbol",
        help="disassemble only this symbol (GNU --disassemble / llvm "
        "--disassemble-symbols) instead of the whole binary; needs a symbol-aware "
        "objdump and does not use the capstone fallback. Exit 4 if the symbol decodes "
        "to no instructions (absent, not a function, or no code).",
    )
    args = ap.parse_args(argv)

    if not os.path.isfile(args.binary):
        sys.stderr.write("cryptoinstr: not a file: %s\n" % args.binary)
        return 2
    return run(args.binary, args.out, args.symbol)


if __name__ == "__main__":
    sys.exit(main())
