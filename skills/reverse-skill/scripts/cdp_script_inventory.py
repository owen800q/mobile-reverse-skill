#!/usr/bin/env python3
"""Inventory the scripts a page or Node/Electron process loaded, from a recorded CDP event log.

Usage:
    cdp_script_inventory.py EVENTS --out FILE

EVENTS is a file of Chrome DevTools Protocol messages: JSON lines, or a JSON array.
Each message is a {"method": ..., "params": ...} object, or a wrapper with the same
object as a JSON string under "message". This tool reads two methods only:

  Debugger.scriptParsed           one entry per script the engine parsed, with its URL,
                                  length, source-map reference and execution context.
  Runtime.executionContextCreated the context's name and origin, to label each script.

The inventory groups scripts by URL and classifies each source as file, http, https,
node-internal, inline or other. It records a script's content hash only when the
event itself carries one. Nothing is sent to the target and nothing is evaluated.

This reads a log that someone else recorded, so it does not attach to a process.
Recording the log is a live step, and it needs the same scope as any other device
or desktop instrumentation (see references/operating-scope.md). Use it only on
pages and processes you own or are authorized to examine. Remote scripts are listed
with their URLs; this tool never fetches them.

Output: the inventory as JSON in FILE, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MAX_EVENTS_BYTES = 256 * 1024 * 1024

LIMITATIONS = [
    "Reads a recorded log only; no live attach, no evaluation, no pause or breakpoint",
    "Only scripts the engine reported in the log appear; lazily loaded or cached scripts may be absent",
    "A content hash is shown only when the event carried one; this tool never hashes the script body",
    "Script URLs are as reported. Remote URLs are recorded, never fetched",
]


class InputError(Exception):
    """Unreadable or malformed event log. Exit code 2."""


def iter_messages(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            items = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError("event array is not valid JSON: %s" % exc)
        for item in items:
            yield item
        return
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            raise InputError("line %d is not valid JSON" % number)
        if isinstance(item, dict) and isinstance(item.get("message"), str):
            try:
                item = json.loads(item["message"])
            except json.JSONDecodeError:
                continue
        yield item


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


def run(events_path: str, out_path: str) -> dict:
    if os.path.getsize(events_path) > MAX_EVENTS_BYTES:
        raise InputError("event log exceeds 256 MiB: %s" % events_path)
    result = build_inventory(iter_messages(events_path))
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(out_path, 0o600)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Inventory loaded scripts from a recorded CDP event log.")
    ap.add_argument("events", help="recorded CDP messages (JSON lines or a JSON array)")
    ap.add_argument("--out", required=True, help="output JSON file")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.events):
        sys.stderr.write("ERROR: event log not found: %s\n" % args.events)
        return 2
    try:
        result = run(args.events, args.out)
    except (InputError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps({k: v for k, v in result.items() if k not in ("inventory", "limitations")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
