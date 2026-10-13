#!/usr/bin/env python3
"""Map Electron IPC channels and the contextBridge surface from static JavaScript.

Usage:
    electron_ipc_map.py SOURCE_DIR --out FILE

SOURCE_DIR is an unpacked app (for example asar_extract.py output) or a directory of
bundled JavaScript. Each .js, .mjs, .cjs or .html file under it is read and scanned,
unless it is larger than 16 MiB, is a symlink, or is not a regular file (a FIFO or a
socket, which would block a read). A file larger than 16 MiB is listed under skipped with
the reason "too large"; a symlink with a scanned extension, and a symlinked directory below
SOURCE_DIR, with the reason "symlink"; any other file that is not regular, with the reason
"not a regular file". None of them is read or followed. If SOURCE_DIR itself is a symlink,
it is followed. Nothing is executed. Each scanned file is read twice, once to collect
string constants and once to scan the calls.

The map records these, each with file and line:

  exposed          contextBridge.exposeInMainWorld("name", ...): the API the page can call.
                   contextBridge.exposeInIsolatedWorld(worldId, "name", ...) is listed here
                   too, with world "isolated" and world_id (the literal, or "dynamic").
  channels         IPC names, one entry per name, with the main-side and renderer-side
                   uses found. Main side is ipcMain.handle/handleOnce/on/once, the sends
                   webContents.send/sendTo/sendToFrame, and the replies event.reply and
                   event.sender.send (recorded as kind send). Renderer side is
                   ipcRenderer.invoke/send/sendSync/sendToHost/on/once. A use whose name
                   came from a constant carries resolved_from, with the expression and
                   the definition site.
  dynamic          IPC calls whose channel argument is not one string literal followed by
                   "," or ")" on the same line and did not resolve to a string constant.
                   Each has the argument's text (cut to 200 characters and suffixed with
                   "..." when longer) and a reason. A literal with a quote character, a
                   backtick or "$" inside, an empty one, or one over 200 characters is
                   listed here too. A name built at runtime, such as 'app:' + name, or a
                   variable with no constant behind it is listed here and is never paired.
  dynamic_exposed  exposeInMainWorld calls whose name is not such a literal, with the
                   argument's text. Constants are not resolved here.
  skipped          files that were not read, with the reason: "too large" for a file over
                   16 MiB, "symlink" for a symlink with a scanned extension or a symlinked
                   directory, or "not a regular file".
  constants_incomplete
                   files whose string constants were not all collected, because the scan
                   budget below ran out, each with a reason.

A channel name held in a string constant is resolved when the definition is unique and the
constant is just that string. A bare name needs one `const NAME = "x"` in the same file. A
dotted path such as `OBJ.KEY` needs one `const OBJ = { KEY: "x" }` (also under
Object.freeze, with nested objects included) in the scanned tree, and `OBJ['KEY']` is read
as `OBJ.KEY`. A template literal without interpolation is read as its text. A string
counts only when nothing continues it: `'a' + b`, `'x'.toUpperCase()` and `'p' ? q : r`
are not the string they start with, and a TypeScript `as const` after the string is
allowed. Only const declarations are read. An object is read only if it closes within
200,000 characters and nests at most 6 levels, and Object.freeze( may wrap a value at
most 6 times. The value must be usable as a channel name, like a literal: 1 to 200
characters, none of a quote, a backtick, "$" or a newline. A name with two different
definitions stays dynamic and its reason says ambiguous. A constant is resolved only
when the channel argument is complete on its line.

Object initializers that never close are scanned up to 200,000 characters each. When they
use up 4,000,000 characters in one file, the scan of that file's constants stops, the file
is listed under constants_incomplete, and constants defined later in it stay dynamic. The
reasons under dynamic are "template literal with interpolation", "not a constant
reference", "no string constant found", "ambiguous: N different definitions", "constant
value cannot be a channel name ...", "channel argument is not on this line", "channel
argument is not complete on this line" and "channel argument is longer than 1000
characters" (the end of an argument is looked for within 1000 characters).

Matching is line by line. A call is matched only when its name is immediately followed by
its opening parenthesis on one line; a call with a space between them is not matched and
is not listed under dynamic. webContents.sendTo and webContents.sendToFrame take a target
first, so their channel is the second argument. When the channel argument is not complete
on the line, the call is listed under dynamic with the text found there, which is empty
when the line ends before the argument starts. Other calls split across lines are not
matched. Whole lines that start with // or * are skipped, and so are the lines of a
/* block comment up to its closing */. Code after a closing */ is scanned.

Each channel gets a status. "paired" means every request or send found for the channel
has a receiver of the matching kind on the other side: invoke with handle or handleOnce,
renderer send or sendSync with main on or once, and a main-side send (webContents send,
sendTo or sendToFrame, or an event reply) with renderer on or once. "unhandled" means a
request or send with no such receiver; a receiver of another kind does not count.
"unused" means no request or send was found for the channel. ipcRenderer.sendToHost is
recorded but is not treated as a request. These are static leads: a channel may be
reached through a path the scan cannot see, such as a helper that builds the name at
runtime.

Output: the map as JSON in FILE, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Any other exception, such as an OSError while reading a scanned
file or writing FILE, is not caught: the run ends with a traceback and exit code 1.
Standard library only.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys

MAX_FILE_BYTES = 16 * 1024 * 1024
SCAN_EXTS = (".js", ".mjs", ".cjs", ".html")
ARG_MAX = 200

# A string literal channel name, not a template with interpolation.
LITERAL = r"""(?P<quote>['"])(?P<name>[^'"`\n$]{1,200})(?P=quote)"""
# That literal as the whole channel argument: followed by "," or ")", spaces allowed.
LITERAL_ARG_RE = re.compile(LITERAL + r"\s*(?=[,)])")
# The start of each call. Its channel argument begins where the match ends, or, for the
# target-first sends, after the first argument.
MAIN_RECEIVE_CALL = re.compile(r"\bipcMain\.(?P<kind>handle|handleOnce|on|once)\(\s*")
RENDERER_SEND_CALL = re.compile(r"\bipcRenderer\.(?P<kind>invoke|send|sendSync|sendToHost)\(\s*")
RENDERER_RECEIVE_CALL = re.compile(r"\bipcRenderer\.(?P<kind>on|once)\(\s*")
MAIN_SEND_CALL = re.compile(r"\bwebContents\.(?P<kind>send)\(\s*")
# sendTo and sendToFrame take a target first and the channel second.
MAIN_SEND_TARGET_CALL = re.compile(r"\bwebContents\.(?P<kind>sendTo|sendToFrame)\(\s*")
# Replies on the event object: event.reply(ch, ...) and event.sender.send(ch, ...).
EVENT_REPLY_CALL = re.compile(r"\b(?:_?event|evt|ev|e)\.(?:reply|sender\.send)\(\s*")
EXPOSE_CALL = re.compile(r"\bcontextBridge\.exposeInMainWorld\(\s*")
# exposeInIsolatedWorld(worldId, key, api): the world ID comes first, then the key.
EXPOSE_ISOLATED_CALL = re.compile(r"\bcontextBridge\.exposeInIsolatedWorld\(\s*")
WORLD_ID_RE = re.compile(r"[0-9]{1,6}")
# (pattern, side of the channel, kind to record or None for the pattern's kind group,
# whether a target argument comes before the channel).
CHANNEL_CALLS = (
    (MAIN_RECEIVE_CALL, "main", None, False),
    (RENDERER_SEND_CALL, "renderer", None, False),
    (RENDERER_RECEIVE_CALL, "renderer", None, False),
    (MAIN_SEND_CALL, "main", None, False),
    (MAIN_SEND_TARGET_CALL, "main", None, True),
    (EVENT_REPLY_CALL, "main", "send", False),
)

# Characters scanned for the end of one argument. A longer one is listed as dynamic.
ARG_SCAN_MAX = 1000

REASON_NOT_ON_LINE = "channel argument is not on this line"
REASON_INCOMPLETE = "channel argument is not complete on this line"
REASON_TOO_LONG = "channel argument is longer than %d characters" % ARG_SCAN_MAX
REASON_BAD_NAME = ("constant value cannot be a channel name (empty, over 200 characters, or "
                   "contains a quote, backtick, $ or newline)")

IDENT = r"[A-Za-z_$][\w$]*"
CONST_DECL_RE = re.compile(r"\bconst\s+(?P<name>" + IDENT + r")\s*=\s*")
PATH_RE = re.compile(r"^" + IDENT + r"(?:\." + IDENT + r")*$")
BRACKET_KEY_RE = re.compile(r"\[\s*(['\"])(" + IDENT + r")\1\s*\]")
PLAIN_TEMPLATE_RE = re.compile(r"^`([^`$\\]{1,200})`$")
WHOLE_TEMPLATE_RE = re.compile(r"`[^`]*`")
# A channel name, from a literal or from a constant's value: 1 to 200 characters, none of
# a quote, a backtick, "$" or a newline.
NAME_RE = re.compile(r"[^'\"`\n$]{1,200}\Z")
# TypeScript "as const" after a string constant does not change its value.
AS_CONST_RE = re.compile(r"as\s+const\b")
# After a string, a new line starting with one of these continues the expression.
CONTINUATION = "+-*/%&|^<>=!?:.([`"
MAX_OBJECT_CHARS = 200_000
MAX_OBJECT_DEPTH = 6
# Characters one file may spend on object initializers that never close, before the scan of
# its constants stops. Each such initializer scans up to MAX_OBJECT_CHARS.
MAX_FAILED_SCAN = 20 * MAX_OBJECT_CHARS

LIMITATIONS = [
    "Static text only: a channel name is read from a string literal that is the whole channel argument on its line, or from a string constant that resolves uniquely; any other argument is listed under dynamic with a reason and never paired",
    "Matching is line by line: a channel argument that is not complete on its line is listed under dynamic with the text found there, and other calls split across lines are not matched",
    "Whole lines that start with // or * are skipped, and so are lines inside a block comment up to its closing */; code after a closing */ is scanned",
    "A comment after code on the same line is scanned as code, and so is a complete /* */ comment at the start of a line; a block comment opened after code is not tracked",
    "ipcRenderer.sendToHost is recorded as a renderer use but is not treated as a request, so it is not paired with a main-process receiver",
    "Files over 16 MiB, symlinks with a scanned extension, symlinked directories and files that are not regular are not read and are listed under skipped",
    "A channel reached through a helper that takes the name as an argument is seen only at the literal call site",
    "A resolved constant is matched by spelling, not by scope: check the definition site named in resolved_from. Only const declarations are read, and a constant counts only when its initializer is just the string",
    "An object constant is read only if it closes within 200,000 characters and nests at most 6 levels. When the unclosed initializers of a file use up the scan budget, the later constants of that file are not collected and the file is listed under constants_incomplete",
    "Event replies are matched on the variable names event, _event, evt, ev and e",
    "A pairing means both sides exist in the source. It does not show that the handler validates its input",
]


class InputError(Exception):
    """Bad input directory. Exit code 2."""


def _rel(path: str, root: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def iter_sources(root: str, skipped: list):
    """Yield the files to scan. Symlinks, oversized files and files that are not regular files
    (a FIFO or a socket, which would block a read) are appended to skipped instead."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept = []
        for name in sorted(dirnames):
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                skipped.append({"path": _rel(path, root), "reason": "symlink"})
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            if not name.lower().endswith(SCAN_EXTS):
                continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                skipped.append({"path": _rel(path, root), "reason": "symlink"})
            elif not os.path.isfile(path):
                skipped.append({"path": _rel(path, root), "reason": "not a regular file"})
            elif os.path.getsize(path) > MAX_FILE_BYTES:
                skipped.append({"path": _rel(path, root), "reason": "too large"})
            else:
                yield path


def _code_lines(text: str, lines=None):
    """Yield (line_number, text) for the code on each line. Whole-line comments are dropped;
    the code after the closing */ of a block comment is kept. lines is text.splitlines() when
    the caller already has it."""
    in_block = False
    for number, line in enumerate(text.splitlines() if lines is None else lines, 1):
        if in_block:
            end = line.find("*/")
            if end == -1:
                continue
            in_block = False
            line = line[end + 2:]
            if line.strip():
                yield number, line
            continue
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
            in_block = True
            continue
        yield number, line


def _code_text(text: str) -> str:
    """The source with whole-line comments blanked, so line numbers are unchanged."""
    lines = text.splitlines()
    code = [""] * len(lines)
    for number, line in _code_lines(text, lines):
        code[number - 1] = line
    return "\n".join(code)


# --- string constants ---------------------------------------------------------
def _skip_space(text, i, end):
    while i < end:
        if text[i].isspace():
            i += 1
        elif text.startswith("//", i):
            nl = text.find("\n", i)
            i = end if nl < 0 else nl
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = end if close < 0 else close + 2
        else:
            break
    return i


def _string_at(text, i, end):
    """Return (value, next_index) for a quoted string with no escapes, else None."""
    if i >= end or text[i] not in "'\"":
        return None
    quote = text[i]
    j = i + 1
    while j < end and text[j] not in (quote, "\\", "\n"):
        j += 1
    if j >= end or text[j] != quote:
        return None
    return text[i + 1:j], j + 1


def _skip_expression(text, i, end):
    """Advance past one expression to the top-level comma or closing brace."""
    depth = 0
    while i < end:
        ch = text[i]
        if ch in "'\"`":
            j = i + 1
            while j < end and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif ch == "," and depth == 0:
            return i
        i += 1
    return end


def _value_ends(text, i, end):
    """True when the expression that began with a string literal stops right after the literal.

    That holds before , ; } ) or the end of the text, and at a new line whose first token
    cannot continue the expression. A TypeScript "as const" after the literal is allowed. So
    'app:' + suffix, 'x'.toUpperCase() and 'p' ? q : r are not the string they start with.
    """
    j = _skip_space(text, i, end)
    m = AS_CONST_RE.match(text, j, end)
    if m:
        i = m.end()
        j = _skip_space(text, i, end)
    if j >= end or text[j] in ",;})":
        return True
    return "\n" in text[i:j] and text[j] not in CONTINUATION


def _parse_value(text, i, end, depth=0, wrapped=0):
    """Parse a string or an object of strings. Return (value, next_index) or None.

    A string counts only when nothing continues it (see _value_ends). Object.freeze( may wrap
    a value at most MAX_OBJECT_DEPTH times.
    """
    i = _skip_space(text, i, end)
    if text.startswith("Object.freeze(", i):
        if wrapped >= MAX_OBJECT_DEPTH:
            return None
        parsed = _parse_value(text, i + len("Object.freeze("), end, depth, wrapped + 1)
        if parsed is None:
            return None
        close = _skip_space(text, parsed[1], end)
        return parsed[0], close + 1 if close < end and text[close] == ")" else close
    got = _string_at(text, i, end)
    if got:
        return got if _value_ends(text, got[1], end) else None
    if i < end and text[i] == "{" and depth < MAX_OBJECT_DEPTH:
        return _parse_object(text, i + 1, end, depth + 1)
    return None


def _parse_object(text, i, end, depth):
    members = {}
    while True:
        i = _skip_space(text, i, end)
        while i < end and text[i] == ",":
            i = _skip_space(text, i + 1, end)
        if i >= end:
            return None
        if text[i] == "}":
            return members, i + 1
        key = None
        got = _string_at(text, i, end)
        if got:
            key, i = got
        else:
            m = re.compile(IDENT).match(text, i)
            if m:
                key, i = m.group(0), m.end()
        j = _skip_space(text, i, end)
        value = None
        if key is not None and j < end and text[j] == ":":
            value = _parse_value(text, j + 1, end, depth)
            if value is not None:
                i = value[1]
                members[key] = value[0]
        if value is None:
            i = _skip_expression(text, i if key is None else j, end)
            if i < end and text[i] == "}":
                return members, i + 1
            if i < end and text[i] != ",":
                i += 1  # a stray closer: step over it so the loop always advances


def _flatten(prefix, value, out):
    if isinstance(value, dict):
        for key, inner in value.items():
            _flatten(prefix + "." + key, inner, out)
    else:
        out.append((prefix, value))


def _opens_object(code, i, end):
    """True when the initializer at i is an object literal, possibly inside Object.freeze(."""
    i = _skip_space(code, i, end)
    while code.startswith("Object.freeze(", i):
        i = _skip_space(code, i + len("Object.freeze("), end)
    return code.startswith("{", i)


def collect_constants(code: str):
    """Return ([(dotted_path, string_value, line)], complete) for const strings and const objects of strings.

    An object initializer that never closes scans up to MAX_OBJECT_CHARS. When those scans in
    one file add up to more than MAX_FAILED_SCAN, the scan stops and complete is False: later
    constants in that file are not collected.
    """
    found, wasted, newlines = [], 0, None
    for m in CONST_DECL_RE.finditer(code):
        end = min(len(code), m.end() + MAX_OBJECT_CHARS)
        parsed = _parse_value(code, m.end(), end)
        if parsed is None:
            if _opens_object(code, m.end(), end):
                wasted += end - m.end()
                if wasted > MAX_FAILED_SCAN:
                    return found, False
            continue
        if newlines is None:  # built on the first constant, so a file without one skips it
            newlines = [n.start() for n in re.finditer("\n", code)]
        line = bisect.bisect_left(newlines, m.start()) + 1
        flat = []
        _flatten(m.group("name"), parsed[0], flat)
        found.extend((path, value, line) for path, value in flat)
    return found, True


def _resolve(arg, rel_file, constants):
    """Return (value, how, why_not). Exactly one of value or why_not is set."""
    arg = arg.strip()
    plain = PLAIN_TEMPLATE_RE.match(arg)
    if plain:
        return plain.group(1), "template literal without interpolation", None
    if WHOLE_TEMPLATE_RE.fullmatch(arg):
        return None, None, "template literal with interpolation"
    path = BRACKET_KEY_RE.sub(lambda m: "." + m.group(2), arg)
    if not PATH_RE.match(path):
        return None, None, "not a constant reference"
    # A bare name is only trusted in the file that defines it; a dotted path may be shared.
    defs = [d for d in constants.get(path, []) if "." in path or d[1] == rel_file]
    if not defs:
        return None, None, "no string constant found"
    values = {d[0] for d in defs}
    if len(values) > 1:
        return None, None, "ambiguous: %d different definitions" % len(values)
    value, def_file, def_line = defs[0]
    return value, "constant %s defined at %s:%d" % (path, def_file, def_line), None


# --- call arguments -----------------------------------------------------------
def _literal_at(line: str, pos: int):
    """The channel name when a string literal that is the whole argument starts at pos."""
    m = LITERAL_ARG_RE.match(line, pos)
    return m.group("name") if m else None


def _argument_end(line: str, pos: int):
    """Return (end, stop): where the argument that starts at pos ends, and the character that
    ended it. That is the first "," or ")" outside brackets and quotes. stop is "" when the
    line ended first, or when no end was found within ARG_SCAN_MAX characters."""
    depth, quote, i, n = 0, None, pos, min(len(line), pos + ARG_SCAN_MAX)
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}," and depth == 0:
            return i, ch
        elif ch in ")]}":
            depth -= 1
        i += 1
    return n, ""


def _argument(line: str, pos: int):
    """Return (text, state) for the argument that starts at pos. state is "complete" when a ","
    or ")" ended it, "long" when no end was found within ARG_SCAN_MAX characters, and "open"
    when the line ended first or a stray "]" or "}" did."""
    end, stop = _argument_end(line, pos)
    text = line[pos:end].strip()
    if stop in (",", ")"):
        return text, "complete"
    return text, "long" if stop == "" and end < len(line) else "open"


def _shorten(text: str) -> str:
    return text if len(text) <= ARG_MAX else text[:ARG_MAX] + "..."


def _channel_start(line: str, pos: int, target_first: bool) -> int:
    """Where the channel argument starts. After a target argument that is past its comma; when
    the line has no such comma it is the end of the line, so the channel is not on the line.
    -1 means the target argument is longer than ARG_SCAN_MAX."""
    if not target_first:
        return pos
    end, stop = _argument_end(line, pos)
    if stop != ",":
        return -1 if stop == "" and end < len(line) else len(line)
    rest = line[end + 1:]
    return end + 1 + len(rest) - len(rest.lstrip())


def scan(root: str) -> dict:
    if not os.path.isdir(root):
        raise InputError("source directory not found: %s" % root)
    rel = lambda p: _rel(p, root)  # noqa: E731

    skipped = []
    paths = list(iter_sources(root, skipped))

    constants, constants_incomplete = {}, []
    for path in paths:
        found, complete = collect_constants(_code_text(_read(path)))
        for name, value, line in found:
            constants.setdefault(name, []).append((value, rel(path), line))
        if not complete:
            constants_incomplete.append({"path": rel(path), "reason": "constant scan budget used up"})

    exposed, dynamic, dynamic_exposed = [], [], []
    channels = {}

    def site(side, kind, name, path, number, resolved=None):
        entry = channels.setdefault(name, {"main": [], "renderer": []})
        record = {"kind": kind, "file": rel(path), "line": number}
        if resolved:
            record["resolved_from"] = resolved
        entry[side].append(record)

    def channel_use(side, kind, line, pos, path, number):
        """Record the channel argument at pos: a literal, a resolved constant, or a dynamic entry."""
        if pos < 0:
            dynamic.append({"kind": kind, "argument": "", "file": rel(path), "line": number,
                            "reason": REASON_TOO_LONG})
            return
        name = _literal_at(line, pos)
        if name is not None:
            site(side, kind, name, path, number)
            return
        text, state = _argument(line, pos)
        if not text:
            reason = REASON_NOT_ON_LINE
        elif state == "long":
            reason = REASON_TOO_LONG
        elif state == "open":
            reason = REASON_INCOMPLETE
        else:
            value, how, reason = _resolve(text, rel(path), constants)
            if value is not None and not NAME_RE.match(value):
                value, reason = None, REASON_BAD_NAME
            if value is not None:
                site(side, kind, value, path, number, {"expression": text, "how": how})
                return
        dynamic.append({"kind": kind, "argument": _shorten(text), "file": rel(path),
                        "line": number, "reason": reason})

    files = 0
    for path in paths:
        files += 1
        for number, line in _code_lines(_read(path)):
            if "(" not in line:  # every call form needs its opening parenthesis
                continue
            for m in EXPOSE_CALL.finditer(line):
                name = _literal_at(line, m.end())
                if name is None:
                    dynamic_exposed.append({"argument": _shorten(_argument(line, m.end())[0]),
                                            "file": rel(path), "line": number})
                else:
                    exposed.append({"name": name, "file": rel(path), "line": number})
            for m in EXPOSE_ISOLATED_CALL.finditer(line):
                world_text, _state = _argument(line, m.end())
                world_end = _argument_end(line, m.end())[0]
                world = world_text if WORLD_ID_RE.fullmatch(world_text) else "dynamic"
                if line[world_end:world_end + 1] != ",":
                    dynamic_exposed.append({"argument": _shorten(world_text), "world": world,
                                            "file": rel(path), "line": number})
                    continue
                key_pos = world_end + 1
                while line[key_pos:key_pos + 1] == " ":
                    key_pos += 1
                name = _literal_at(line, key_pos)
                if name is None:
                    dynamic_exposed.append({"argument": _shorten(_argument(line, key_pos)[0]),
                                            "world": world, "file": rel(path), "line": number})
                else:
                    exposed.append({"name": name, "file": rel(path), "line": number,
                                    "world": "isolated", "world_id": world})
            for pattern, side, fixed_kind, target_first in CHANNEL_CALLS:
                for m in pattern.finditer(line):
                    kind = fixed_kind or m.group("kind")
                    channel_use(side, kind, line, _channel_start(line, m.end(), target_first),
                                path, number)

    out_channels = []
    for name in sorted(channels):
        entry = channels[name]
        status = _status(entry)
        out_channels.append({"name": name, "status": status,
                             "main": entry["main"], "renderer": entry["renderer"]})
    return {
        "source_root": os.path.basename(os.path.abspath(root)),
        "files_scanned": files,
        "exposed": exposed,
        "channels": out_channels,
        "channel_count": len(out_channels),
        "paired": sum(1 for c in out_channels if c["status"] == "paired"),
        "resolved_uses": sum(1 for c in out_channels for side in ("main", "renderer")
                             for u in c[side] if "resolved_from" in u),
        "dynamic": dynamic,
        "dynamic_exposed": dynamic_exposed,
        "skipped": skipped,
        "constants_incomplete": constants_incomplete,
        "limitations": list(LIMITATIONS),
    }


def _status(entry) -> str:
    """paired: every request or send has a receiver of the matching kind. unhandled: one does not. unused: no request or send was found."""
    main_kinds = {x["kind"] for x in entry["main"]}
    renderer_kinds = {x["kind"] for x in entry["renderer"]}
    renderer_requests = renderer_kinds & {"invoke", "send", "sendSync"}
    main_sends = main_kinds & {"send", "sendTo", "sendToFrame"}
    if not renderer_requests and not main_sends:
        return "unused"
    invoke_ok = "invoke" not in renderer_kinds or bool(main_kinds & {"handle", "handleOnce"})
    send_ok = not (renderer_kinds & {"send", "sendSync"}) or bool(main_kinds & {"on", "once"})
    main_send_ok = not main_sends or bool(renderer_kinds & {"on", "once"})
    return "paired" if (invoke_ok and send_ok and main_send_ok) else "unhandled"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Map Electron IPC channels and contextBridge exposure statically.")
    ap.add_argument("source", help="unpacked app or bundle directory")
    ap.add_argument("--out", required=True, help="output JSON file")
    args = ap.parse_args(argv)
    try:
        result = scan(args.source)
    except InputError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(args.out, 0o600)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("exposed", "channels", "dynamic", "dynamic_exposed", "skipped",
                                   "constants_incomplete", "limitations")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
