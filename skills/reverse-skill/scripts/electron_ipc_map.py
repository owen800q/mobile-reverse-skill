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
  dynamic    uses whose channel name is not a string literal, so they cannot be
             paired. They are listed, never guessed.

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
MAIN_SEND_RE = re.compile(r"\bwebContents\.(?P<kind>send|sendTo)\(\s*(?:[^,()]+,\s*)?" + LITERAL)
EXPOSE_RE = re.compile(r"\bcontextBridge\.exposeInMainWorld\(\s*" + LITERAL)
# Any call of these names whose first argument is not a plain literal is dynamic.
DYNAMIC_RE = re.compile(
    r"\bipc(?:Main|Renderer)\.(?P<kind>handle|handleOnce|on|once|invoke|send|sendSync|sendToHost)\(\s*(?![\"'])"
    r"(?P<arg>[^,)\n]{0,80})")

LIMITATIONS = [
    "Static text only: channel names built at runtime appear under dynamic, not in the pairing",
    "Lines that start with a comment marker are skipped; a comment on the same line as code is not",
    "A channel reached through a helper that takes the name as an argument is seen only at the literal call site",
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


def scan(root: str) -> dict:
    if not os.path.isdir(root):
        raise InputError("source directory not found: %s" % root)
    rel = lambda p: os.path.relpath(p, root).replace(os.sep, "/")  # noqa: E731

    exposed, dynamic = [], []
    channels = {}

    def site(side, kind, name, path, number):
        entry = channels.setdefault(name, {"main": [], "renderer": []})
        entry[side].append({"kind": kind, "file": rel(path), "line": number})

    files = 0
    for path in iter_sources(root):
        files += 1
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
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
            for m in DYNAMIC_RE.finditer(line):
                dynamic.append({"kind": m.group("kind"), "argument": m.group("arg").strip(),
                                "file": rel(path), "line": number})

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
