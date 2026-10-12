#!/usr/bin/env python3
"""Inventory the scripts a page or Node/Electron process loaded, from a recorded CDP event log.

Usage:
    cdp_script_inventory.py EVENTS --out FILE

EVENTS is a file of Chrome DevTools Protocol messages: JSON lines, or a JSON array.
Each message is a {"method": ..., "params": ...} object, or a wrapper with the same
object as a JSON string under "message". Wrappers are unwrapped in both layouts, and a
wrapper whose string does not parse is skipped. This tool reads two methods only:

  Debugger.scriptParsed           one entry per script in the log (one per event). A
                                  script the log reports more than once, for example after
                                  a second Debugger.enable, has one entry per report; the
                                  inventory groups them under one URL. Each entry carries
                                  the URL, length, source-map reference and execution
                                  context.
  Runtime.executionContextCreated the context's name and origin, to label each script.

scripts_parsed counts the Debugger.scriptParsed events in the log. distinct_scripts
counts the URL groups. The inventory groups scripts by URL and classifies each source as
file, http, https, node-internal, inline or other. It records a script's content hash
only when the event itself carries one. Nothing is sent to the target and nothing is
evaluated.

This reads a log that someone else recorded, so it does not attach to a process.
Recording the log is a live step, and it needs the same scope as any other device
or desktop instrumentation (see references/operating-scope.md). Use it only on
pages and processes you own or are authorized to examine. Remote scripts are listed
with their URLs; this tool never fetches them.

Each call to run() and each call to main() appends one JSON line to trace.jsonl, in the
directory of --out (the session directory), mode 0600. Every entry holds the UTC
timestamp, the tool and function, the status and the exit code. The run entry also holds
the events and output paths relative to the session directory, the events file's SHA-256
(null only when the file was refused before it was read), the input layout, unwrap and
script counts, and any error text. The main entry holds the paths and the events file's
SHA-256. Script URLs and script content are never logged.

Output: the inventory as JSON in FILE, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error, or a trace entry that could not be written. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

MAX_EVENTS_BYTES = 256 * 1024 * 1024
HASH_CHUNK = 1024 * 1024
TRACE_FILE = "trace.jsonl"
TRACE_TOOL = "cdp_script_inventory"

LIMITATIONS = [
    "Reads a recorded log only; no live attach, no evaluation, no pause or breakpoint",
    "Only scripts the engine reported in the log appear; lazily loaded or cached scripts may be absent",
    "A content hash is shown only when the event carried one; this tool never hashes the script body",
    "Script URLs are as reported. Remote URLs are recorded, never fetched",
]


class InputError(Exception):
    """Unreadable or malformed event log. Exit code 2."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def trace_path(out_path: str) -> str:
    """The session trace log: trace.jsonl in the directory of the output file."""
    return os.path.join(os.path.dirname(os.path.abspath(out_path)), TRACE_FILE)


def session_path(path: str, session_dir: str) -> str:
    """An identifier for the log: the path relative to the session directory, else the file name."""
    full = os.path.abspath(path)
    base = os.path.abspath(session_dir)
    try:
        inside = os.path.commonpath([full, base]) == base
    except ValueError:  # paths on different drives
        inside = False
    if inside:
        return os.path.relpath(full, base).replace(os.sep, "/")
    return os.path.basename(full)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def log_entry(log_path: str, function: str, **fields) -> None:
    """Append one JSON line for a call. Raises OSError when the line cannot be written."""
    entry = {"ts": utc_now(), "tool": TRACE_TOOL, "function": function}
    entry.update(fields)
    data = (json.dumps(entry, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), mode=0o700, exist_ok=True)
    fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "ab") as fh:
        fh.write(data)
    os.chmod(log_path, 0o600)


def _line_items(text: str):
    """Yield the parsed JSON value of each non-blank line."""
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            raise InputError("line %d is not valid JSON" % number)


def _unwrap(items, stats: dict):
    """Yield each message. A wrapper's "message" string is parsed; one that does not parse is skipped."""
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("message"), str):
            stats["unwrapped"] += 1
            try:
                item = json.loads(item["message"])
            except json.JSONDecodeError:
                stats["unwrap_failed"] += 1
                continue
        yield item


def iter_messages(path: str, stats: dict):
    """Yield the messages in the log, from a JSON array or JSON lines. stats records the layout and unwrap counts."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if text.lstrip().startswith("["):
        stats["format"] = "array"
        try:
            items = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError("event array is not valid JSON: %s" % exc)
        yield from _unwrap(items, stats)
        return
    stats["format"] = "lines"
    yield from _unwrap(_line_items(text), stats)


def classify(url: str) -> str:
    if not url:
        return "inline"
    lowered = url.lower()
    if lowered.startswith("file:"):
        return "file"
    if lowered.startswith("http://"):
        return "http"
    if lowered.startswith("https://"):
        return "https"
    if lowered.startswith("node:"):
        return "node-internal"
    return "other"


def build_inventory(messages) -> dict:
    contexts = {}
    scripts = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        method = msg.get("method")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            continue
        if method == "Runtime.executionContextCreated":
            ctx = params.get("context") or {}
            contexts[ctx.get("id")] = {"name": ctx.get("name") or "", "origin": ctx.get("origin") or ""}
        elif method == "Debugger.scriptParsed":
            scripts.append(params)

    groups = {}
    for params in scripts:
        url = params.get("url") or ""
        ctx_id = params.get("executionContextId")
        ctx = contexts.get(ctx_id, {})
        key = url if url else "(inline script %s)" % params.get("scriptId", "?")
        group = groups.setdefault(key, {
            "url": url,
            "source": classify(url),
            "script_ids": [],
            "lengths": [],
            "hashes": [],
            "source_maps": [],
            "is_module": False,
            "contexts": [],
        })
        group["script_ids"].append(str(params.get("scriptId", "")))
        if isinstance(params.get("length"), int):
            group["lengths"].append(params["length"])
        if params.get("hash"):
            group["hashes"].append(str(params["hash"]))
        if params.get("sourceMapURL"):
            group["source_maps"].append(str(params["sourceMapURL"])[:300])
        group["is_module"] = group["is_module"] or bool(params.get("isModule"))
        label = ctx.get("name") or ctx.get("origin") or ("context %s" % ctx_id if ctx_id is not None else "")
        if label and label not in group["contexts"]:
            group["contexts"].append(label)

    inventory = []
    for key in sorted(groups):
        g = groups[key]
        g["count"] = len(g["script_ids"])
        g["hashes"] = sorted(set(g["hashes"]))
        g["source_maps"] = sorted(set(g["source_maps"]))
        inventory.append(g)

    by_source = {}
    for g in inventory:
        by_source[g["source"]] = by_source.get(g["source"], 0) + 1
    return {
        "scripts_parsed": len(scripts),
        "distinct_scripts": len(inventory),
        "by_source": by_source,
        "with_source_maps": sum(1 for g in inventory if g["source_maps"]),
        "inventory": inventory,
        "limitations": list(LIMITATIONS),
    }


def run(events_path: str, out_path: str, log_path: str = None) -> dict:
    """Read the event log and write its inventory to out_path. Appends one entry to the trace log."""
    log_path = log_path or trace_path(out_path)
    session = os.path.dirname(os.path.abspath(out_path))
    fields = {"events": session_path(events_path, session), "out": session_path(out_path, session)}
    stats = {"format": None, "unwrapped": 0, "unwrap_failed": 0}
    digest = None
    try:
        if os.path.getsize(events_path) > MAX_EVENTS_BYTES:
            raise InputError("event log exceeds 256 MiB: %s" % fields["events"])
        digest = sha256_file(events_path)
        if os.path.abspath(out_path) == os.path.abspath(log_path):
            raise InputError("output file is the trace log: %s" % fields["out"])
        result = build_inventory(iter_messages(events_path, stats))
        out_dir = os.path.dirname(os.path.abspath(out_path))
        os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.chmod(out_path, 0o600)
    except Exception as exc:
        log_entry(log_path, "run", status="error", exit_code=2, error=str(exc)[:300],
                  events_sha256=digest, **fields, **stats)
        raise
    log_entry(log_path, "run", status="ok", exit_code=0, events_sha256=digest,
              scripts_parsed=result["scripts_parsed"], distinct_scripts=result["distinct_scripts"],
              **fields, **stats)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Inventory loaded scripts from a recorded CDP event log.")
    ap.add_argument("events", help="recorded CDP messages (JSON lines or a JSON array)")
    ap.add_argument("--out", required=True, help="output JSON file")
    args = ap.parse_args(argv)
    log_path = trace_path(args.out)
    session = os.path.dirname(os.path.abspath(args.out))
    summary, digest = None, None
    if not os.path.isfile(args.events):
        sys.stderr.write("ERROR: event log not found: %s\n" % args.events)
        code = 2
    else:
        try:
            if os.path.getsize(args.events) <= MAX_EVENTS_BYTES:
                digest = sha256_file(args.events)
            result = run(args.events, args.out, log_path=log_path)
            summary = {k: v for k, v in result.items() if k not in ("inventory", "limitations")}
            code = 0
        except Exception as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            code = 2
    try:
        log_entry(log_path, "main", status="ok" if code == 0 else "error", exit_code=code,
                  events=session_path(args.events, session), out=session_path(args.out, session),
                  events_sha256=digest)
    except OSError as exc:
        sys.stderr.write("ERROR: trace log could not be written: %s\n" % exc)
        return 2
    if summary is not None:
        print(json.dumps(summary, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
