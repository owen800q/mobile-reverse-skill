#!/usr/bin/env python3
"""Remove analyst-declared secret literals from every text file in a capture output directory.

Usage (standalone):
    redact_literals.py OUT_DIR (--literal VALUE | --literal-file FILE) [--literal ...]

Usage (from a parser): add_literal_args(ap) before parse_args(); then call
resolve_literal_args(args) before any output is written, and apply_literals(literals,
out_dir) once every output file has been written.

A literal is a value the analyst already knows is sensitive: a session token, a
password, a device id, an account number. Each literal is removed wherever it
appears in a text output, in its raw form and in the URL-encoded and base64
forms that often carry it in query strings and JSON bodies. Literals shorter
than MIN_LITERAL_LEN are refused, because they would also match ordinary text.

This is a last-resort pass for text that the structural redactors (har_parse
--redact) cannot see: free text, buffer previews and ledger quotes. It does not
change file names, does not touch stderr, and skips binary files and any file it
cannot decode as UTF-8, reporting each skipped file rather than changing it.
Redacted files are rewritten in place, so run it on the output directory only,
never on the raw capture.

Output: a JSON summary on stdout. Exit codes: 0 done, 2 usage or input error.
Standard library only.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse

MIN_LITERAL_LEN = 6
REDACTED = "[REDACTED]"


class LiteralError(Exception):
    """A literal that cannot be used safely. Exit code 2."""


def variants(literal: str) -> list[str]:
    """Forms a literal takes inside captured text, longest first so overlaps resolve safely."""
    raw = literal.encode("utf-8")
    forms = {
        literal,
        urllib.parse.quote(literal, safe=""),
        urllib.parse.quote_plus(literal),
        base64.b64encode(raw).decode("ascii"),
    }
    forms.discard("")
    return sorted(forms, key=len, reverse=True)


def load_literals(values, file_path=None) -> list[str]:
    """Collect literals from --literal values and an optional file (one per line, # comments allowed)."""
    found = []
    for value in values or []:
        found.append(value)
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.rstrip("\r\n")
                    if stripped.strip() and not stripped.lstrip().startswith("#"):
                        found.append(stripped)
        except OSError as exc:
            raise LiteralError("cannot read literal file %s: %s" % (file_path, exc))
    unique = []
    for literal in found:
        if len(literal) < MIN_LITERAL_LEN:
            raise LiteralError(
                "literal shorter than %d characters refused (too likely to match ordinary text)"
                % MIN_LITERAL_LEN)
        if literal not in unique:
            unique.append(literal)
    return unique


def redact_text(text: str, literals) -> tuple[str, int]:
    """Replace every variant of every literal. Returns (text, replacement count)."""
    count = 0
    for literal in literals:
        for form in variants(literal):
            occurrences = text.count(form)
            if occurrences:
                count += occurrences
                text = text.replace(form, REDACTED)
    return text, count


def redact_tree(out_dir: str, literals) -> dict:
    """Redact every decodable text file under out_dir in place. Returns a summary."""
    summary = {
        "literals": len(literals),
        "files_scanned": 0,
        "files_redacted": 0,
        "replacements": 0,
        "skipped": [],
    }
    if not literals:
        return summary
    for dirpath, _dirnames, filenames in os.walk(out_dir, followlinks=False):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            rel = os.path.relpath(path, out_dir).replace(os.sep, "/")
            summary["files_scanned"] += 1
            with open(path, "rb") as fh:
                data = fh.read()
            if b"\x00" in data:
                summary["skipped"].append({"path": rel, "reason": "binary"})
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                summary["skipped"].append({"path": rel, "reason": "not utf-8"})
                continue
            new_text, count = redact_text(text, literals)
            if count:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new_text)
                summary["files_redacted"] += 1
                summary["replacements"] += count
    return summary


def add_literal_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--literal", action="append", default=[], metavar="VALUE",
                    help="secret value to remove from every text output (repeatable, min %d chars)"
                    % MIN_LITERAL_LEN)
    ap.add_argument("--literal-file", default=None, metavar="FILE",
                    help="file with one secret value per line; # starts a comment")


def resolve_literal_args(args) -> list[str]:
    """Load and validate literals from parsed args. Call before any output is written.

    Raises LiteralError for a bad literal, so a parser exits before it writes anything
    that would later need redacting.
    """
    if not getattr(args, "literal", None) and not getattr(args, "literal_file", None):
        return []
    return load_literals(args.literal, args.literal_file)


def apply_literals(literals, out_dir: str) -> dict | None:
    """Run the literal pass on a parser's finished output directory. None if no literals."""
    if not literals:
        return None
    summary = redact_tree(out_dir, literals)
    sys.stderr.write(
        "Literal redaction: %d literal(s), %d replacement(s) in %d file(s)\n"
        % (summary["literals"], summary["replacements"], summary["files_redacted"]))
    for item in summary["skipped"]:
        sys.stderr.write("  not scanned (%s): %s\n" % (item["reason"], item["path"]))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Replace declared secret literals in every text file of a capture output directory.")
    ap.add_argument("out_dir", help="output directory to redact in place (never the raw capture)")
    add_literal_args(ap)
    args = ap.parse_args(argv)
    if not os.path.isdir(args.out_dir):
        sys.stderr.write("ERROR: output directory not found: %s\n" % args.out_dir)
        return 2
    if not args.literal and not args.literal_file:
        sys.stderr.write("ERROR: give --literal or --literal-file\n")
        return 2
    try:
        literals = resolve_literal_args(args)
    except LiteralError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(apply_literals(literals, args.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
