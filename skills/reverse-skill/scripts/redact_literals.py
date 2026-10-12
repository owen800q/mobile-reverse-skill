#!/usr/bin/env python3
"""Remove analyst-declared secret literals from the text files of a capture output directory.

Usage (standalone):
    redact_literals.py OUT_DIR (--literal VALUE | --literal-file FILE) [--literal ...]

Usage (from a parser): add_literal_args(ap) before parse_args(); then call
resolve_literal_args(args) before any output is written, and apply_literals(literals,
out_dir, files) once the run has written its output files, passing files as the list of
those files. Without files the whole directory is walked.

A literal is a value the analyst already knows is sensitive: a session token, a
password, a device id, an account number. Literals shorter than MIN_LITERAL_LEN
characters are refused, because they would also match ordinary text.

Forms searched for each literal (its UTF-8 bytes; the list is built by variants):
  - the raw value;
  - URL-encoded (quote) and form-encoded (quote_plus);
  - base64 of the whole literal, padded, in the standard and URL-safe alphabets, and
    the URL-encoded forms of those;
  - base64 of the literal at byte offset 0, 1 or 2 within a 3-byte group (every
    alignment): the base64 characters of the groups that lie wholly inside the literal,
    when there are at least 8 of them, and the URL-encoded forms of those;
  - hex, in lower and upper case;
  - JSON string escapes as json.dumps writes them, applied up to three times (a JSON
    body stored inside a JSON record is escaped twice), with and without \\uXXXX
    escapes for non-ASCII characters.
The forms of all literals are sorted together, longest first, and replaced in that
order, so a shorter literal inside a longer one cannot stop the longer one from being
replaced.

Not covered: other encodings and escape styles, including JSON escapes such as \\= and
\\/, \\uXXXX escapes of printable ASCII characters (for example \\u003d for =), uppercase
hex inside \\uXXXX escapes, and percent-encoding mixed with raw characters; the base64
characters of the partly covered 3-byte groups at each end of the literal; a value split
across fields;
compressed or re-encoded content; file names; the raw capture when it is not one of the
written files; console output, except lines a parser redacts itself; binary and non-UTF-8
files, which are listed as not scanned.

Scope: a parser rewrites only the files its run wrote. The standalone CLI rewrites
every UTF-8 text file directly or indirectly under the directory it is given, including
a raw capture placed there. Rewrites happen in place, so run the CLI on the output
directory only, never on the raw capture. Symbolic links are skipped and not listed.
A file in files (read as open() reads it: relative to the current directory, or
absolute) that resolves outside the directory raises LiteralError before any file is
rewritten. An unreadable directory or file ends the run with an error.

Literal file: one value per line, read as UTF-8 (a byte order mark is ignored). A line
whose first non-blank character is '#' is skipped silently. Any other '#' is part of
the value, and so are leading and trailing spaces. A file with no literals is an error.

Output: the CLI prints a JSON summary on stdout. Exit codes: 0 done; 2 usage or input
error: a missing output directory or no literal source, a literal shorter than
MIN_LITERAL_LEN characters, an unreadable or non-UTF-8 literal file, a file with no
literals, or a literal that is not valid UTF-8. Any other failure ends with an uncaught
exception and exit code 1.
Standard library only.
"""
from __future__ import annotations

import argparse
import base64
import functools
import json
import os
import sys
import urllib.parse

MIN_LITERAL_LEN = 6
REDACTED = "[REDACTED]"
JSON_ESCAPE_LEVELS = 3


class LiteralError(Exception):
    """A literal, literal file or listed output file that cannot be used. The CLI exits 2.

    Raised for a literal shorter than MIN_LITERAL_LEN characters, a literal that is not
    valid UTF-8, a literal file that cannot be read, is not UTF-8 or has no literals, and,
    in redact_tree, a listed file that resolves outside the output directory or is not a
    regular file. Literals are checked before any output is written, and listed files
    are checked before any file is rewritten.
    """


def _utf8_bytes(literal: str) -> bytes:
    """The UTF-8 bytes of a literal. Raises LiteralError for a lone surrogate."""
    try:
        return literal.encode("utf-8")
    except UnicodeEncodeError:
        raise LiteralError(
            "literal is not valid UTF-8 (it has a lone surrogate, as a non-UTF-8 byte "
            "on the command line gives)") from None


def variants(literal: str) -> list[str]:
    """Encoded forms of one literal that this module searches for, longest first.

    This is a fixed list of forms, not an enumeration of every form a literal can take on
    disk. The forms are: the raw value; URL-encoded (quote) and form-encoded (quote_plus);
    base64 of the whole literal, padded, in the standard and URL-safe alphabets, with
    URL-encoded copies; base64 of the literal at byte offset 0, 1 or 2 within a 3-byte
    group, using the characters of the groups that lie wholly inside the literal when there
    are at least 8 of them, with URL-encoded copies; hex in lower and upper case; and JSON
    string escapes as json.dumps writes them, applied one to JSON_ESCAPE_LEVELS times, with
    and without \\uXXXX escapes for non-ASCII characters. The repeated JSON escaping is
    needed because a JSON body stored inside a JSON record is escaped twice. Forms not
    listed here, such as the \\= and \\/ JSON escapes, are not searched.
    """
    raw = _utf8_bytes(literal)
    found = [literal, urllib.parse.quote(literal, safe=""), urllib.parse.quote_plus(literal),
             raw.hex(), raw.hex().upper()]
    for encode in (base64.b64encode, base64.urlsafe_b64encode):
        full = encode(raw).decode("ascii")
        found += [full, urllib.parse.quote(full, safe="")]
        for lead in range(3):
            # The literal starts at byte `lead` of a 3-byte group. Groups first..last of this
            # encoding hold only literal bytes, so their characters do not depend on the
            # bytes around the literal.
            encoded = encode(bytes(lead) + raw).decode("ascii")
            first = 1 if lead else 0
            last = (lead + len(raw)) // 3 - 1
            determined = encoded[4 * first:4 * (last + 1)] if last >= first else ""
            if len(determined) >= 8:
                found += [determined, urllib.parse.quote(determined, safe="")]
    for ensure_ascii in (False, True):
        current = literal
        for _ in range(JSON_ESCAPE_LEVELS):
            current = json.dumps(current, ensure_ascii=ensure_ascii)[1:-1]
            found.append(current)
    unique = [form for form in dict.fromkeys(found) if form]
    return sorted(unique, key=len, reverse=True)


def load_literals(values, file_path=None) -> list[str]:
    """Collect literals from --literal values and an optional literal file.

    The file has one value per line, read as UTF-8 (a byte order mark is ignored). A line
    whose first non-blank character is '#' is skipped; any other '#' is part of the value,
    and so are leading and trailing spaces. Raises LiteralError for a literal shorter than
    MIN_LITERAL_LEN characters, a literal that is not valid UTF-8, a file that cannot be
    read or is not UTF-8, and a file with no literals.
    """
    found = list(values or [])
    if file_path:
        from_file = []
        try:
            with open(file_path, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    stripped = line.rstrip("\r\n")
                    if stripped.strip() and not stripped.lstrip().startswith("#"):
                        from_file.append(stripped)
        except OSError as exc:
            raise LiteralError("cannot read literal file %s: %s" % (file_path, exc)) from None
        except UnicodeDecodeError:
            raise LiteralError("literal file %s is not valid UTF-8" % file_path) from None
        if not from_file:
            raise LiteralError("no literals in %s" % file_path)
        found.extend(from_file)
    unique = []
    for literal in found:
        if len(literal) < MIN_LITERAL_LEN:
            raise LiteralError(
                "literal shorter than %d characters refused (too likely to match ordinary text)"
                % MIN_LITERAL_LEN)
        _utf8_bytes(literal)  # raises LiteralError for a lone surrogate
        if literal not in unique:
            unique.append(literal)
    return unique


@functools.lru_cache(maxsize=64)
def _forms_longest_first(literals: tuple) -> tuple:
    """Every form of every literal, longest first. Forms of equal length keep the order given."""
    ordered = dict.fromkeys(form for literal in literals for form in variants(literal))
    return tuple(sorted(ordered, key=len, reverse=True))


def redact_text(text: str, literals) -> tuple[str, int]:
    """Replace every form of every literal, longest form first. Returns (text, replacement count).

    All forms of all literals go into one ordered list, so a shorter literal inside a
    longer one cannot stop the longer one from being replaced.
    """
    count = 0
    for form in _forms_longest_first(tuple(literals)):
        occurrences = text.count(form)
        if occurrences:
            count += occurrences
            text = text.replace(form, REDACTED)
    return text, count


def _is_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives
        return False


def _has_link_below(base: str, path: str) -> bool:
    """True when path, or a directory between base and path, is a symbolic link."""
    current = base
    for part in os.path.relpath(path, base).split(os.sep):
        if part == os.curdir:
            continue
        current = os.path.join(current, part)
        if os.path.islink(current):
            return True
    return False


def _raise_walk_error(exc: OSError) -> None:
    raise exc


def _walked_targets(out_dir: str):
    """(path, relative path) for every file under out_dir, without following symbolic links."""
    for dirpath, _dirnames, filenames in os.walk(out_dir, followlinks=False,
                                                 onerror=_raise_walk_error):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if not os.path.islink(path):
                yield path, os.path.relpath(path, out_dir).replace(os.sep, "/")


def _listed_targets(out_dir: str, files) -> list[tuple[str, str]]:
    """Check every listed file before any is rewritten. Returns (path, relative path) pairs.

    A listed path is read as open() reads it: relative to the current directory, or absolute.
    """
    base = os.path.abspath(out_dir)
    real_base = os.path.realpath(base)
    targets, seen = [], set()
    for item in files:
        path = os.path.abspath(item)
        real = os.path.realpath(path)
        if not (_is_inside(path, base) and _is_inside(real, real_base)):
            raise LiteralError("file outside the output directory refused: %s" % item)
        if _has_link_below(base, path):
            continue
        if not os.path.isfile(path):
            raise LiteralError("not a regular file under the output directory: %s" % item)
        if real not in seen:
            seen.add(real)
            targets.append((path, os.path.relpath(path, base).replace(os.sep, "/")))
    return targets


def _redact_file(path: str, rel: str, literals, summary: dict) -> None:
    if not os.path.isfile(path):  # a named pipe or socket: opening it could block, so never open it
        summary["skipped"].append({"path": rel, "reason": "not a regular file"})
        return
    summary["files_scanned"] += 1
    with open(path, "rb") as fh:
        data = fh.read()
    if b"\x00" in data:
        summary["skipped"].append({"path": rel, "reason": "binary"})
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        summary["skipped"].append({"path": rel, "reason": "not utf-8"})
        return
    new_text, count = redact_text(text, literals)
    if count:
        with open(path, "wb") as fh:
            fh.write(new_text.encode("utf-8"))
        summary["files_redacted"] += 1
        summary["replacements"] += count


def redact_tree(out_dir: str, literals, files=None) -> dict:
    """Redact literals in place in the text files of out_dir. Returns a summary.

    files=None walks the whole directory (the standalone CLI path). With files, only the
    listed files are processed. Each is read as open() reads it (relative to the current
    directory, or absolute) and must lie inside out_dir. A file that resolves outside
    out_dir, or that is not a regular file, raises
    LiteralError before any file is rewritten. Symbolic links, and files reached through
    one, are skipped and not listed. Binary and non-UTF-8 files are listed under "skipped"
    and not changed; in a walk, so are other non-regular files such as named pipes.
    """
    summary = {
        "literals": len(literals),
        "files_scanned": 0,
        "files_redacted": 0,
        "replacements": 0,
        "skipped": [],
    }
    targets = _listed_targets(out_dir, files) if files is not None else _walked_targets(out_dir)
    if not literals:
        return summary
    for path, rel in targets:
        _redact_file(path, rel, literals, summary)
    return summary


def add_literal_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--literal", action="append", default=[], metavar="VALUE",
                    help="secret value to remove from the output's text files "
                         "(repeatable, at least %d characters)" % MIN_LITERAL_LEN)
    ap.add_argument("--literal-file", default=None, metavar="FILE",
                    help="file with one secret value per line; a line whose first non-blank "
                         "character is # is a comment, and any other # is part of the value")


def resolve_literal_args(args) -> list[str]:
    """Load and validate literals from parsed args. Call before any output is written.

    Raises LiteralError for a literal shorter than MIN_LITERAL_LEN characters, a literal
    that is not valid UTF-8, or a literal file that cannot be read, is not UTF-8 or has no
    literals. A parser exits before it writes anything that would later need redacting.
    """
    if not getattr(args, "literal", None) and not getattr(args, "literal_file", None):
        return []
    return load_literals(args.literal, args.literal_file)


def apply_literals(literals, out_dir: str, files=None) -> dict | None:
    """Run the literal pass on a parser's output directory. None if there are no literals.

    files: the paths the run wrote, as it opened them (relative to the current directory, or
    absolute), so that only those files are rewritten. None walks the whole directory.
    See redact_tree.
    """
    if not literals:
        return None
    summary = redact_tree(out_dir, literals, files)
    sys.stderr.write(
        "Literal redaction: %d literal(s), %d replacement(s) in %d file(s)\n"
        % (summary["literals"], summary["replacements"], summary["files_redacted"]))
    for item in summary["skipped"]:
        sys.stderr.write("  not scanned (%s): %s\n" % (item["reason"], item["path"]))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Replace declared secret literals in every UTF-8 text file under a capture "
                    "output directory, in place.")
    ap.add_argument("out_dir", help="output directory to redact in place; every UTF-8 text file "
                                    "under it is rewritten, so never pass the raw capture")
    add_literal_args(ap)
    args = ap.parse_args(argv)
    if not os.path.isdir(args.out_dir):
        sys.stderr.write("ERROR: output directory not found: %s\n" % args.out_dir)
        return 2
    try:
        literals = resolve_literal_args(args)
    except LiteralError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    if not literals:
        sys.stderr.write("ERROR: give --literal or --literal-file\n")
        return 2
    print(json.dumps(apply_literals(literals, args.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
