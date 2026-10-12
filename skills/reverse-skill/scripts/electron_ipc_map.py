#!/usr/bin/env python3
"""Map Electron IPC channels and the contextBridge surface from static JavaScript.

Usage:
    electron_ipc_map.py SOURCE_DIR --out FILE

SOURCE_DIR is an unpacked app (for example asar_extract.py output) or a directory of
bundled JavaScript. Every .js, .mjs, .cjs and .html file under it is scanned. Nothing
is executed, and symlinks are not followed.

The map records three things, each with file and line:

  exposed    contextBridge.exposeInMainWorld("name", ...): the API the page can call.
  channels   IPC names, one entry per name, with the main-side and renderer-side
             uses found. Main side is ipcMain.handle/on and webContents.send. Renderer
             side is ipcRenderer.invoke/send/sendSync and ipcRenderer.on.
  dynamic    uses whose channel name is not a string literal and could not be
             resolved. They are listed with a reason, never guessed.

A channel name held in a string constant is resolved when the definition is unique:
a bare name needs a `const NAME = "x"` in the same file; `OBJ.KEY` needs one
`const OBJ = { KEY: "x" }` (also under Object.freeze, nested objects included) in the
scanned tree, or an interpolation-free template literal. A resolved use carries
`resolved_from` with the expression and the definition site. A name with two different
definitions stays dynamic and is reported as ambiguous.

Each channel gets a status. "paired" means a request side and a handler side both
exist, for example invoke with handle, or main webContents.send with renderer on.
"unhandled" means a sender with no receiver. "unused" means a receiver with no
sender. These are static leads: a channel may be reached through a path the scan
cannot see, such as a helper that builds the name at runtime.

Output: the map as JSON in FILE, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import bisect
import os
import re
import sys

MAX_FILE_BYTES = 16 * 1024 * 1024
SCAN_EXTS = (".js", ".mjs", ".cjs", ".html")

# A string literal channel name, not a template with interpolation.
LITERAL = r"""(?P<quote>['"])(?P<name>[^'"`\n$]{1,200})(?P=quote)"""
MAIN_RECEIVE_RE = re.compile(r"\bipcMain\.(?P<kind>handle|handleOnce|on|once)\(\s*" + LITERAL)
RENDERER_SEND_RE = re.compile(r"\bipcRenderer\.(?P<kind>invoke|send|sendSync|sendToHost)\(\s*" + LITERAL)
RENDERER_RECEIVE_RE = re.compile(r"\bipcRenderer\.(?P<kind>on|once)\(\s*" + LITERAL)
# webContents.send takes the channel first. sendToFrame (and sendTo) take a target first.
MAIN_SEND_RE = re.compile(r"\bwebContents\.(?P<kind>send)\(\s*" + LITERAL)
MAIN_SEND_TARGET_RE = re.compile(r"\bwebContents\.(?P<kind>sendTo|sendToFrame)\(\s*[^,()]+,\s*" + LITERAL)
# Replies on the event object: event.reply(ch, ...) and event.sender.send(ch, ...).
EVENT_REPLY_RE = re.compile(r"\b(?:_?event|evt|ev|e)\.(?:reply|sender\.send)\(\s*" + LITERAL)
EXPOSE_RE = re.compile(r"\bcontextBridge\.exposeInMainWorld\(\s*" + LITERAL)
# Any call of these names whose first argument is not a plain literal is dynamic.
DYNAMIC_RE = re.compile(
    r"\b(?P<obj>ipcMain|ipcRenderer)\."
    r"(?P<kind>handle|handleOnce|on|once|invoke|send|sendSync|sendToHost)\(\s*(?![\"'])"
    r"(?P<arg>[^,)\n]{0,80})")
WEB_SEND_DYNAMIC_RE = re.compile(r"\bwebContents\.send\(\s*(?![\"'])(?P<arg>[^,)\n]{0,80})")
EVENT_REPLY_DYNAMIC_RE = re.compile(
    r"\b(?:_?event|evt|ev|e)\.(?:reply|sender\.send)\(\s*(?![\"'])(?P<arg>[^,)\n]{0,80})")

IDENT = r"[A-Za-z_$][\w$]*"
CONST_DECL_RE = re.compile(r"\bconst\s+(?P<name>" + IDENT + r")\s*=\s*")
PATH_RE = re.compile(r"^" + IDENT + r"(?:\." + IDENT + r")*$")
BRACKET_KEY_RE = re.compile(r"\[\s*(['\"])(" + IDENT + r")\1\s*\]")
PLAIN_TEMPLATE_RE = re.compile(r"^`([^`$\\]{1,200})`$")
MAX_OBJECT_CHARS = 200_000
MAX_OBJECT_DEPTH = 6

LIMITATIONS = [
    "Static text only: channel names built at runtime appear under dynamic, not in the pairing",
    "Lines that start with a comment marker are skipped; a comment on the same line as code is not",
    "A channel reached through a helper that takes the name as an argument is seen only at the literal call site",
    "A resolved constant is matched by spelling, not by scope: check the definition site named in resolved_from",
    "Event replies are matched on the variable names event, _event, evt, ev and e",
    "A pairing means both sides exist in the source. It does not show that the handler validates its input",
]


class InputError(Exception):
    """Bad input directory. Exit code 2."""


def iter_sources(root: str):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            if not name.lower().endswith(SCAN_EXTS):
                continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or os.path.getsize(path) > MAX_FILE_BYTES:
                continue
            yield path


def _code_lines(text: str):
    """Yield (line_number, line) for lines that are not a whole-line comment."""
    in_block = False
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
            in_block = True
            continue
        yield number, line


def _code_text(text: str) -> str:
    """The source with whole-line comments blanked, so line numbers are unchanged."""
    keep = dict(_code_lines(text))
    return "\n".join(keep.get(n, "") for n in range(1, len(text.splitlines()) + 1))


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


def _parse_value(text, i, end, depth=0):
    """Parse a string or an object of strings. Return (value, next_index) or None."""
    i = _skip_space(text, i, end)
    if text.startswith("Object.freeze(", i):
        parsed = _parse_value(text, i + len("Object.freeze("), end, depth)
        if parsed is None:
            return None
        close = _skip_space(text, parsed[1], end)
        return parsed[0], close + 1 if close < end and text[close] == ")" else close
    got = _string_at(text, i, end)
    if got:
        return got
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


def collect_constants(code: str):
    """Return [(dotted_path, string_value, line)] for const strings and const objects of strings."""
    found = []
    newlines = [m.start() for m in re.finditer("\n", code)]
    for m in CONST_DECL_RE.finditer(code):
        end = min(len(code), m.end() + MAX_OBJECT_CHARS)
        parsed = _parse_value(code, m.end(), end)
        if parsed is None:
            continue
        line = bisect.bisect_left(newlines, m.start()) + 1
        flat = []
        _flatten(m.group("name"), parsed[0], flat)
        found.extend((path, value, line) for path, value in flat)
    return found


def _resolve(arg, rel_file, constants):
    """Return (value, how, why_not). Exactly one of value or why_not is set."""
    arg = arg.strip()
    plain = PLAIN_TEMPLATE_RE.match(arg)
    if plain:
        return plain.group(1), "template literal without interpolation", None
    if arg.startswith("`"):
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


def scan(root: str) -> dict:
    if not os.path.isdir(root):
        raise InputError("source directory not found: %s" % root)
    rel = lambda p: os.path.relpath(p, root).replace(os.sep, "/")  # noqa: E731

    sources = []
    for path in iter_sources(root):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            sources.append((path, fh.read()))

    constants = {}
    for path, text in sources:
        for name, value, line in collect_constants(_code_text(text)):
            constants.setdefault(name, []).append((value, rel(path), line))

    exposed, dynamic = [], []
    channels = {}

    def site(side, kind, name, path, number, resolved=None):
        entry = channels.setdefault(name, {"main": [], "renderer": []})
        record = {"kind": kind, "file": rel(path), "line": number}
        if resolved:
            record["resolved_from"] = resolved
        entry[side].append(record)

    def dynamic_use(side, kind, obj, arg, path, number):
        arg = arg.strip()
        if not arg:
            return
        value, how, why_not = _resolve(arg, rel(path), constants)
        if value is None:
            dynamic.append({"kind": kind, "argument": arg, "file": rel(path), "line": number,
                            "reason": why_not})
        else:
            site(side, kind, value, path, number, {"expression": arg, "how": how})

    files = 0
    for path, text in sources:
        files += 1
        for number, line in _code_lines(text):
            for m in EXPOSE_RE.finditer(line):
                exposed.append({"name": m.group("name"), "file": rel(path), "line": number})
            for m in MAIN_RECEIVE_RE.finditer(line):
                site("main", m.group("kind"), m.group("name"), path, number)
            for m in RENDERER_SEND_RE.finditer(line):
                site("renderer", m.group("kind"), m.group("name"), path, number)
            for m in RENDERER_RECEIVE_RE.finditer(line):
                site("renderer", "on", m.group("name"), path, number)
            for m in MAIN_SEND_RE.finditer(line):
                site("main", m.group("kind"), m.group("name"), path, number)
            for m in MAIN_SEND_TARGET_RE.finditer(line):
                site("main", m.group("kind"), m.group("name"), path, number)
            for m in EVENT_REPLY_RE.finditer(line):
                site("main", "send", m.group("name"), path, number)
            for m in DYNAMIC_RE.finditer(line):
                kind = m.group("kind")
                if m.group("obj") == "ipcMain":
                    dynamic_use("main", kind, "ipcMain", m.group("arg"), path, number)
                else:
                    dynamic_use("renderer", "on" if kind in ("on", "once") else kind,
                                "ipcRenderer", m.group("arg"), path, number)
            for m in WEB_SEND_DYNAMIC_RE.finditer(line):
                dynamic_use("main", "send", "webContents", m.group("arg"), path, number)
            for m in EVENT_REPLY_DYNAMIC_RE.finditer(line):
                dynamic_use("main", "send", "event", m.group("arg"), path, number)

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
        "limitations": list(LIMITATIONS),
    }


def _status(entry) -> str:
    """paired: every request has a handler on the other side. unhandled: one does not. unused: no requests."""
    main_kinds = {x["kind"] for x in entry["main"]}
    renderer_kinds = {x["kind"] for x in entry["renderer"]}
    renderer_requests = renderer_kinds & {"invoke", "send", "sendSync"}
    main_sends = main_kinds & {"send", "sendTo"}
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
                      if k not in ("exposed", "channels", "dynamic", "limitations")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
