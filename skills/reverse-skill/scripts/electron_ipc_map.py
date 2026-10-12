#!/usr/bin/env python3
"""Map Electron IPC channels and the contextBridge surface from static JavaScript.

Usage:
    electron_ipc_map.py SOURCE_DIR --out FILE

SOURCE_DIR is an unpacked app (for example asar_extract.py output) or a directory of
bundled JavaScript. Each .js, .mjs, .cjs or .html file under it is read and scanned,
unless it is larger than 16 MiB or is a symlink. A file larger than 16 MiB is listed
under skipped with the reason "too large" and is not read. A symlink with a scanned
extension, and a symlinked directory below SOURCE_DIR, are listed under skipped with the
reason "symlink" and are not followed. If SOURCE_DIR itself is a symlink, it is followed.
Nothing is executed.

The map records these, each with file and line:

  exposed          contextBridge.exposeInMainWorld("name", ...): the API the page can call.
  channels         IPC names, one entry per name, with the main-side and renderer-side
                   uses found. Main side is ipcMain.handle/handleOnce/on/once and
                   webContents.send/sendTo. Renderer side is ipcRenderer.invoke/send/
                   sendSync/sendToHost/on/once.
  dynamic          IPC calls whose first argument is not one string literal followed by
                   "," or ")" on the same line, with that argument's text. A name built at
                   runtime, such as 'app:' + name, or a variable is listed here and is
                   never paired.
  dynamic_exposed  exposeInMainWorld calls whose name is not such a literal, with the
                   argument's text.
  skipped          files that were not read, with the reason: "too large" for a file over
                   16 MiB, or "symlink" for a symlink with a scanned extension or a
                   symlinked directory.

Matching is line by line. A call is matched when its name and opening parenthesis are
on one line. When its first argument is not complete on that line, the call is listed
under dynamic with the text found there, which is empty when the line ends after the
parenthesis. Other calls split across lines are not matched. Whole lines that start with
// or * are skipped, and so are the lines of a /* block comment up to its closing */.
Code after a closing */ is scanned.

Each channel gets a status. "paired" means every request or send found for the channel
has a receiver of the matching kind on the other side: invoke with handle or handleOnce,
renderer send or sendSync with main on or once, and main webContents send or sendTo with
renderer on or once. "unhandled" means a request or send with no such receiver; a
receiver of another kind does not count. "unused" means no request or send was found for
the channel. ipcRenderer.sendToHost is recorded but is not treated as a request. These
are static leads: a channel may be reached through a path the scan cannot see, such as a
helper that builds the name at runtime.

Output: the map as JSON in FILE, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

MAX_FILE_BYTES = 16 * 1024 * 1024
SCAN_EXTS = (".js", ".mjs", ".cjs", ".html")
ARG_MAX = 200

# A string literal channel name, not a template with interpolation.
LITERAL = r"""(?P<quote>['"])(?P<name>[^'"`\n$]{1,200})(?P=quote)"""
# That literal as the whole first argument: followed by "," or ")", spaces allowed.
LITERAL_ARG_RE = re.compile(LITERAL + r"\s*(?=[,)])")
# The start of each call. Its first argument begins where the match ends.
MAIN_RECEIVE_CALL = re.compile(r"\bipcMain\.(?P<kind>handle|handleOnce|on|once)\(\s*")
RENDERER_SEND_CALL = re.compile(r"\bipcRenderer\.(?P<kind>invoke|send|sendSync|sendToHost)\(\s*")
RENDERER_RECEIVE_CALL = re.compile(r"\bipcRenderer\.(?P<kind>on|once)\(\s*")
MAIN_SEND_CALL = re.compile(r"\bwebContents\.(?P<kind>send|sendTo)\(\s*")
EXPOSE_CALL = re.compile(r"\bcontextBridge\.exposeInMainWorld\(\s*")
# (pattern, side of the channel). The first argument of each call is the channel name.
CHANNEL_CALLS = (
    (MAIN_RECEIVE_CALL, "main"),
    (RENDERER_SEND_CALL, "renderer"),
    (RENDERER_RECEIVE_CALL, "renderer"),
    (MAIN_SEND_CALL, "main"),
)

LIMITATIONS = [
    "Static text only: a channel name is read only from a string literal that is the whole first argument on its line; any other first argument is listed under dynamic and never paired",
    "Matching is line by line: a first argument that is not complete on its line is listed under dynamic with the text found there, and other calls split across lines are not matched",
    "Whole lines that start with // or * are skipped, and so are lines inside a block comment up to its closing */; code after a closing */ is scanned",
    "A comment after code on the same line is scanned as code, and so is a complete /* */ comment at the start of a line; a block comment opened after code is not tracked",
    "ipcRenderer.sendToHost is recorded as a renderer use but is not treated as a request, so it is not paired with a main-process receiver",
    "Files over 16 MiB, symlinks with a scanned extension and symlinked directories are not read and are listed under skipped",
    "A channel reached through a helper that takes the name as an argument is seen only at the literal call site",
    "A pairing means both sides exist in the source. It does not show that the handler validates its input",
]


class InputError(Exception):
    """Bad input directory. Exit code 2."""


def _rel(path: str, root: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def iter_sources(root: str, skipped: list):
    """Yield the files to scan. Symlinks and oversized files are appended to skipped instead."""
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
            elif os.path.getsize(path) > MAX_FILE_BYTES:
                skipped.append({"path": _rel(path, root), "reason": "too large"})
            else:
                yield path


def _code_lines(text: str):
    """Yield (line_number, text) for the code on each line. Whole-line comments are dropped;
    the code after the closing */ of a block comment is kept."""
    in_block = False
    for number, line in enumerate(text.splitlines(), 1):
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


def _literal_at(line: str, pos: int):
    """The channel name when a string literal that is the whole first argument starts at pos."""
    m = LITERAL_ARG_RE.match(line, pos)
    return m.group("name") if m else None


def _argument_text(line: str, pos: int) -> str:
    """The first argument's text: from pos to the first "," or ")" outside brackets and quotes."""
    depth, quote, i, end = 0, None, pos, len(line)
    while i < end:
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
            end = i
            break
        elif ch in ")]}":
            depth -= 1
        i += 1
    text = line[pos:end].strip()
    return text if len(text) <= ARG_MAX else text[:ARG_MAX] + "..."


def scan(root: str) -> dict:
    if not os.path.isdir(root):
        raise InputError("source directory not found: %s" % root)
    rel = lambda p: _rel(p, root)  # noqa: E731

    exposed, dynamic, dynamic_exposed, skipped = [], [], [], []
    channels = {}

    def site(side, kind, name, path, number):
        entry = channels.setdefault(name, {"main": [], "renderer": []})
        entry[side].append({"kind": kind, "file": rel(path), "line": number})

    files = 0
    for path in iter_sources(root, skipped):
        files += 1
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for number, line in _code_lines(text):
            for m in EXPOSE_CALL.finditer(line):
                name = _literal_at(line, m.end())
                if name is None:
                    dynamic_exposed.append({"argument": _argument_text(line, m.end()),
                                            "file": rel(path), "line": number})
                else:
                    exposed.append({"name": name, "file": rel(path), "line": number})
            for pattern, side in CHANNEL_CALLS:
                for m in pattern.finditer(line):
                    kind = m.group("kind")
                    name = _literal_at(line, m.end())
                    if name is None:
                        dynamic.append({"kind": kind, "argument": _argument_text(line, m.end()),
                                        "file": rel(path), "line": number})
                    else:
                        site(side, kind, name, path, number)

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
        "dynamic": dynamic,
        "dynamic_exposed": dynamic_exposed,
        "skipped": skipped,
        "limitations": list(LIMITATIONS),
    }


def _status(entry) -> str:
    """paired: every request or send has a receiver of the matching kind. unhandled: one does not. unused: no request or send was found."""
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
                      if k not in ("exposed", "channels", "dynamic", "dynamic_exposed", "skipped",
                                   "limitations")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
