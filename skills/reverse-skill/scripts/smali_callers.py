#!/usr/bin/env python3
"""List the call sites of one Java or Android method in an apktool smali tree.

Usage:
    smali_callers.py SMALI_ROOT CLASS METHOD [--params DESC] [--out FILE]

SMALI_ROOT is an apktool output directory (smali/, smali_classes2/, and so on). CLASS is a
dotted class name such as com.example.Api, and METHOD is the simple method name. --params
takes the JVM parameter descriptors without parentheses, for example "Ljava/lang/String;I",
and narrows the match to one overload. Without it, every overload is listed and each one is
named by its full descriptor.

Each invoke-* instruction in the tree whose method reference names CLASS and METHOD is
recorded with the file, the line, the invoke kind (invoke-virtual, invoke-static and so
on), the calling class and the calling method's full descriptor. The caller is the nearest
.method above the instruction in the same file. Nothing is executed. Matching is on the
descriptor text, so a call through a subclass or an interface is found only when the
instruction names that class.

Output is JSON on stdout, or to --out (mode 0600). The output lists at most MAX_CALLERS
call sites; the total is reported, and truncated is true when the list was cut.

Limitations: only instructions in .smali files are read. Calls made by reflection,
method handles, invoke-custom, or string-built names are not seen. A caller in a file the
tree does not hold is not reported, and a symlinked file is not followed. Lines longer
than MAX_LINE_CHARS are skipped and counted in the output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

MAX_CALLERS = 2000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_LINE_CHARS = 4000
MAX_FILES = 200_000

CLASS_RE = re.compile(r"^\.class\b[^\n]*?\s(L[^\s;]+;)\s*$")
METHOD_RE = re.compile(r"^\.method\b.*?\s([^\s(]+)(\([^)]*\)\S+)\s*$")
END_METHOD_RE = re.compile(r"^\.end method\b")
INVOKE_RE = re.compile(
    r"^\s*(invoke-[a-z/]+)\s+\{[^}]*\},\s*(L[^;\s]+;)->([^(\s]+)(\([^)]*\)\S+)")

LIMITATIONS = [
    "Only .smali files are read; a method called only through reflection, a method handle, invoke-custom or a string-built name is not found",
    "Matching is on the class named in the instruction. A call made through a subclass or an interface that does not name the class is not reported",
    "The caller is the nearest .method above the instruction in the same file; an instruction outside any method is reported with caller null",
    "Symlinked files and directories are not followed, and files over 16 MiB are skipped",
]


class InputError(Exception):
    """Bad input. Exit code 2."""


def smali_class(dotted: str) -> str:
    return "L" + dotted.replace(".", "/") + ";"


def iter_smali(root: str, skipped: list):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if not name.endswith(".smali"):
                continue
            if os.path.islink(path):
                skipped.append({"path": os.path.relpath(path, root), "reason": "symlink"})
                continue
            if os.path.getsize(path) > MAX_FILE_BYTES:
                skipped.append({"path": os.path.relpath(path, root), "reason": "over 16 MiB"})
                continue
            count += 1
            if count > MAX_FILES:
                raise InputError("more than %d smali files; narrow SMALI_ROOT" % MAX_FILES)
            yield path


def find_callers(root: str, cls: str, method: str, params=None):
    """Return (callers, total, skipped, files_read). Each caller is a dict."""
    target = smali_class(cls)
    wanted = "(" + (params or "") + ")"
    callers, total, skipped = [], 0, []
    files_read = 0
    for path in iter_smali(root, skipped):
        files_read += 1
        rel = os.path.relpath(path, root)
        caller_class, caller_method = None, None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for number, line in enumerate(fh, 1):
                if len(line) > MAX_LINE_CHARS:
                    skipped.append({"path": rel, "line": number, "reason": "line over 4000 characters"})
                    continue
                m = CLASS_RE.match(line)
                if m:
                    caller_class, caller_method = m.group(1), None
                    continue
                m = METHOD_RE.match(line)
                if m:
                    caller_method = m.group(1) + m.group(2)
                    continue
                if END_METHOD_RE.match(line):
                    caller_method = None
                    continue
                m = INVOKE_RE.match(line)
                if not m or m.group(2) != target or m.group(3) != method:
                    continue
                if params is not None and not m.group(4).startswith(wanted):
                    continue
                total += 1
                if len(callers) < MAX_CALLERS:
                    callers.append({
                        "file": rel, "line": number, "invoke": m.group(1),
                        "caller_class": caller_class, "caller_method": caller_method,
                        "descriptor": m.group(4),
                    })
    return callers, total, skipped, files_read


def build_report(root: str, cls: str, method: str, params=None) -> dict:
    if not os.path.isdir(root):
        raise InputError("smali root is not a directory: %s" % root)
    callers, total, skipped, files_read = find_callers(root, cls, method, params)
    return {
        "target": {"class": cls, "smali_class": smali_class(cls), "method": method,
                   "params": params},
        "files_read": files_read,
        "total": total,
        "truncated": total > len(callers),
        "callers": callers,
        "skipped": skipped,
        "limitations": list(LIMITATIONS),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="List call sites of a method in an apktool smali tree.")
    ap.add_argument("root", help="apktool smali directory (smali/, smali_classes2/, ...)")
    ap.add_argument("class_name", metavar="CLASS", help="dotted class name, for example com.example.Api")
    ap.add_argument("method", help="simple method name")
    ap.add_argument("--params", default=None,
                    help="JVM parameter descriptors without parentheses, for example Ljava/lang/String;I")
    ap.add_argument("--out", default=None, help="write JSON to FILE instead of stdout")
    args = ap.parse_args(argv)
    try:
        report = build_report(args.root, args.class_name, args.method, args.params)
    except (InputError, OSError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        os.chmod(args.out, 0o600)
    else:
        print(text)
    return 0 if report["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
