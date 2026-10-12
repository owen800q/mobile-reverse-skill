#!/usr/bin/env python3
"""Select one method body from decompiled Java or smali, refusing ambiguous overloads.

Usage:
    java_method.py SRC_ROOT CLASS METHOD [--params "T1,T2"] [--max-body-lines N]
                   [--smali-root APKTOOL_OUT]

CLASS is a fully qualified top-level class name such as com.example.Api. METHOD is a
simple name. SRC_ROOT is a source tree: jadx output (sources/) or apktool output (smali*/),
or the directory that holds one of them.

File lookup: Java files are searched first, then smali. A file is chosen by the top-level
simple name of CLASS, the first segment that starts with an uppercase letter. Its directory
below SRC_ROOT must equal the package path of CLASS, or be one container directory (sources,
smali or smali_classes<N>) followed by the package path. So com/example/Api.java matches
com.example.Api and does not match example.Api, and smali_classes2/com/example/Api.smali
matches com.example.Api. A nested class name, such as com.example.Outer.Inner, is refused
with exit 2: pass the top-level class and select the method inside it. A name containing $,
such as com.example.Outer$Inner, is looked up as a file name.

Rule: a bare method name is never resolved to its first overload. If the file declares
several methods with that name and --params does not select exactly one, the tool exits 1.
The status is "ambiguous" when several declarations match (a bare name matches all of them)
and "no_match_for_params" when none does. Each candidate is listed with its simple parameter
types and line number, up to 100 candidates; candidate_count gives the total. A declaration
without a body (abstract, native, or interface) reports body_status "not_available" rather
than an empty body. Java constructors are not candidates: a declaration whose return type is
a modifier word or missing is skipped. In smali the constructor is the method <init>, which
is selected when it is asked for by that name.

Decompiler output is checked before a body is trusted. A selected Java body that contains a
decompiler failure marker reports body_status "decompile_failed"; one that contains a
decompiler warning and no failure marker reports "partial". When a body contains both kinds,
the status is "decompile_failed" and body_markers lists the failure markers and then the
warning markers that were found. Markers are plain text matches, so a string literal or a
comment that contains a marker text is reported too. The body is still returned so the
analyst can see it, but it must not be cited as recovered source.

Static initializers (<clinit>) are read only from smali, by design, and --smali-root is
required for them. The reason given is that jadx can fold their instructions into field
declarations; that jadx behaviour was not checked against jadx output. A method that the
Java source does not declare is read from --smali-root when given, and the result records
the fallback in "fallback".

Parameter types are compared by simple name: package prefixes and final are dropped, generics
are dropped at any nesting depth, simple annotations are dropped, and varargs are read as
arrays. A parameter annotation whose argument contains a parenthesised call, such as
@Ann(v = f(1)), hides its declaration. Java parsing is heuristic: comments and string or char
literals are masked first, then declarations are matched by shape. Check a selected body
against the file before citing it.

Output: one JSON object on stdout. Exit codes: 0 selected or not available, 1 ambiguous,
no_match_for_params or not_found, 2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

DEFAULT_MAX_BODY_LINES = 400
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_CANDIDATES_SHOWN = 100

# Text jadx writes into a body when it could not decompile the method. The first
# marker is the one REA checks for; the others are our assumption about jadx output
# and must be confirmed against a real failing method before the skill pins a jadx.
DECOMPILE_FAILURE_MARKERS = (
    "// ERROR:",
    "Method not decompiled",
    "Method dump skipped",
    "Failed to decompile",
)
DECOMPILE_WARNING_MARKERS = ("JADX WARN",)

# A word before a method name that makes the match a statement, not a declaration.
NOT_RETURN_TYPES = {
    "return", "new", "throw", "yield", "else", "case", "assert", "do", "if", "while",
    "for", "switch", "catch", "try", "throws",
}
MODIFIERS = (
    "public|private|protected|static|final|synchronized|native|abstract|default|strictfp"
)
# A declaration whose return type is one of these words has no return type: the word is a
# modifier, so the declaration is a constructor such as "public Api(String s) {".
MODIFIER_WORDS = frozenset(MODIFIERS.split("|"))
COMMENT_OR_LITERAL_RE = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"""[\s\S]*?"""|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'',
)
ANNOTATION_RE = re.compile(r"@[\w.]+(?:\s*\([^()]*(?:\([^()]*\)[^()]*)*\))?")
# One innermost type-argument group. strip_type_args() applies it until none remains.
TYPE_ARGS_RE = re.compile(r"<[^<>]*>")
# Directory names that may sit between the source root and the package path.
CONTAINER_DIR_RE = re.compile(r"smali|smali_classes\d+|sources")
PRIMITIVES = {
    "Z": "boolean", "B": "byte", "S": "short", "C": "char", "I": "int",
    "J": "long", "F": "float", "D": "double", "V": "void",
}
NESTED_CLASS_MESSAGE = (
    "nested classes are not resolved; pass the top-level class and select the method inside it"
)
LIMITATIONS = [
    "Selection uses declared simple parameter types. Generics are removed at any nesting depth, so overloads that differ only by type arguments are reported as ambiguous",
    "A parameter annotation whose argument contains a parenthesised call, such as @Ann(v = f(1)), hides its declaration; the method is then not_found, or another overload is selected",
    "A declaration with an annotation between its modifiers and its return type, such as public @Nullable String foo(int x), is not detected; another overload can then be selected",
    "Java parsing is heuristic: comments and literals are masked, then declarations are matched by shape. Verify each selected body against the file before citing it",
    "Declarations are matched across the whole file, including nested and anonymous classes. The requested CLASS is not checked against the class that declares the body. An uppercase segment after the top-level class exits 2; a trailing lowercase segment is ignored",
    "Java constructors are not candidates. In smali the constructor is the method <init>, which is selected when asked for by that name. Methods inherited from other files are not selected, and calls inside lambda bodies are not matched as declarations",
    "A decompiled body is a derived rendering; a complete body does not establish identical semantics",
    "Smali bodies are shown as instructions; register values and types are not interpreted",
    "Decompiler markers are plain text matches over the selected source, comments and string literals included. A body without a marker is not proof that jadx recovered it correctly",
    "Static initializers come from smali only, by design; the claim that jadx folds <clinit> instructions into field declarations was not checked against jadx output",
    "Candidate lists are capped at 100 entries; candidate_count gives the total",
]


class InputError(Exception):
    """Bad arguments or unreadable input. Exit code 2."""


def strip_type_args(text):
    """Remove type arguments at any nesting depth, innermost group first."""
    while True:
        reduced = TYPE_ARGS_RE.sub("", text)
        if reduced == text:
            return text
        text = reduced


def simple_type(text):
    """Reduce a Java type to its simple name with array dimensions, e.g. java.util.List<T>[] -> List[]."""
    t = strip_type_args(text)
    t = re.sub(r"\s+", "", t).replace("...", "[]")
    dims = t.count("[]")
    base = t.replace("[]", "").split(".")[-1]
    return base + "[]" * dims


def split_top(text):
    """Split on commas that are not nested inside <>, () or []."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def java_param_type(decl):
    """Simple type of one Java parameter declaration, dropping annotations, final and the name."""
    s = ANNOTATION_RE.sub(" ", decl)
    s = re.sub(r"\bfinal\b", " ", s).strip()
    m = re.match(r"^(?P<type>.+?)\s*(?P<name>[A-Za-z_$][\w$]*)\s*(?P<dims>(?:\[\s*\]\s*)*)$",
                 s, re.S)
    if not m:
        return simple_type(s)
    return simple_type(m.group("type") + m.group("dims"))


def mask_java(text):
    """Blank comments and literals to spaces, keeping offsets and newlines."""
    return COMMENT_OR_LITERAL_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def declaration_pattern(name):
    # The return type is required, so a declaration with no return type (a constructor with
    # no modifier) is not matched at all.
    head = (
        r"(?:(?<=[;{}])|^)[ \t]*"
        r"(?:@[\w.]+(?:\([^()]*(?:\([^()]*\)[^()]*)*\))?\s+)*"
        r"(?:(?:" + MODIFIERS + r"|@[\w.]+(?:\s*\([^()]*(?:\([^()]*\)[^()]*)*\))?)\s+)*"
        r"(?:<[^;{}()]*>\s*)?"
        r"(?P<rtype>[A-Za-z_][\w.]*(?:\s*<[^;{}()=]*>)?(?:\s*\[\s*\])*)\s+"
    )
    tail = (
        r"(?P<name>" + re.escape(name) + r")\s*\((?P<params>(?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)"
        r"(?P<tail>\s*(?:throws\s+[\w.,\s]+?)?)\s*(?P<end>[{;])"
    )
    return re.compile(head + tail, re.M)


def match_brace(masked, open_index):
    depth = 0
    for i in range(open_index, len(masked)):
        ch = masked[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def java_candidates(text, method):
    masked = mask_java(text)
    found = []
    for m in declaration_pattern(method).finditer(masked):
        rtype = m.group("rtype").strip()
        if rtype.split("<")[0].split()[0] in NOT_RETURN_TYPES:
            continue
        if rtype in MODIFIER_WORDS:
            # "public Api(String s) {": the word read as the return type is a modifier, so this
            # is a constructor. Constructors are never candidates.
            continue
        params = [java_param_type(p) for p in split_top(m.group("params"))]
        has_body = m.group("end") == "{"
        close = match_brace(masked, m.end("end") - 1) if has_body else None
        if has_body and close is None:
            raise InputError("unbalanced braces after line %d" % (masked.count("\n", 0, m.start()) + 1))
        end_pos = close + 1 if close is not None else m.end("end")
        found.append({
            "signature": "%s(%s)" % (method, ",".join(params)),
            "params": params,
            "return_type": rtype.strip(),
            "line": masked.count("\n", 0, m.start("name")) + 1,
            "body_status": "present" if has_body else "not_available",
            "_span": (m.start(), end_pos),
        })
    return found


def smali_type(desc):
    """Simple names for a smali parameter descriptor string such as 'Ljava/lang/String;I[B'."""
    types, i = [], 0
    while i < len(desc):
        dims = 0
        while i < len(desc) and desc[i] == "[":
            dims += 1
            i += 1
        if i >= len(desc):
            raise ValueError("truncated descriptor")
        if desc[i] == "L":
            end = desc.find(";", i)
            if end == -1:
                raise ValueError("unterminated class descriptor")
            name = desc[i + 1:end].split("/")[-1].split("$")[-1]
            i = end + 1
        elif desc[i] in PRIMITIVES:
            name = PRIMITIVES[desc[i]]
            i += 1
        else:
            raise ValueError("unknown descriptor character %r" % desc[i])
        types.append(name + "[]" * dims)
    return types


def smali_candidates(text, method):
    found = []
    lines = text.splitlines(keepends=True)
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)
    for idx, line in enumerate(lines):
        m = re.match(r"^\.method[ \t]+(.*?)\s*$", line)
        if not m:
            continue
        words = m.group(1).split()
        header = m.group(1)
        mm = re.match(r"^(?:[\w-]+\s+)*?([^\s(]+)\(([^)]*)\)(\S*)", header)
        if not mm or mm.group(1) != method:
            continue
        try:
            params = smali_type(mm.group(2))
        except ValueError:
            continue
        flags = set(words)
        end_idx = next((j for j in range(idx + 1, len(lines))
                        if lines[j].strip() == ".end method"), None)
        if end_idx is None:
            raise InputError("smali method without .end method at line %d" % (idx + 1))
        instructions = [
            ln for ln in lines[idx + 1:end_idx]
            if ln.strip() and not ln.strip().startswith((".", "#"))
        ]
        abstract = bool(flags & {"abstract", "native"})
        has_body = bool(instructions) and not abstract
        start = offsets[idx]
        end = offsets[end_idx] + len(lines[end_idx])
        found.append({
            "signature": "%s(%s)" % (method, ",".join(params)),
            "params": params,
            "return_type": smali_type(mm.group(3) or "V")[0],
            "line": idx + 1,
            "body_status": "present" if has_body else "not_available",
            "_span": (start, end),
        })
    return found


def split_class(cls):
    """Return (package, top) for a dotted CLASS name, or raise InputError for a nested class name.

    The top-level class is the first segment that starts with an uppercase letter. A name with no
    uppercase segment names its last segment.
    """
    parts = cls.split(".")
    top_index = next((i for i, p in enumerate(parts) if p[:1].isupper()), len(parts) - 1)
    if any(p[:1].isupper() for p in parts[top_index + 1:]):
        raise InputError(NESTED_CLASS_MESSAGE)
    return parts[:top_index], parts[top_index]


def package_dir_matches(segs, package):
    """True when a directory path below the source root is the package path, or one container
    directory (smali, smali_classes<N> or sources) followed by the package path."""
    if segs == package:
        return True
    return (len(segs) == len(package) + 1 and CONTAINER_DIR_RE.fullmatch(segs[0]) is not None
            and segs[1:] == package)


def locate(root, cls):
    """Return (path, format) for the file declaring the top-level class, or raise InputError."""
    package, top = split_class(cls)
    hits = {"java": [], "smali": []}
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        rel = os.path.relpath(dirpath, root)
        segs = [] if rel == "." else rel.replace(os.sep, "/").split("/")
        if not package_dir_matches(segs, package):
            continue
        for fmt, ext in (("java", ".java"), ("smali", ".smali")):
            name = top + ext
            if name in filenames:
                full = os.path.join(dirpath, name)
                if not os.path.islink(full):
                    hits[fmt].append(full)
    for fmt in ("java", "smali"):
        if len(hits[fmt]) == 1:
            return hits[fmt][0], fmt
        if len(hits[fmt]) > 1:
            raise InputError("several %s files declare %s: %s" % (
                fmt, top, ", ".join(sorted(os.path.relpath(p, root) for p in hits[fmt]))))
    raise InputError("no Java or smali source for %s under %s" % (cls, root))


def pick_source(root, cls, method, smali_root):
    """Return (path, format, base, fallback) for the file that should answer this lookup."""
    if method == "<clinit>":
        if smali_root is None:
            raise InputError("static initializers are read from smali; pass --smali-root with the apktool output")
        path, fmt = locate(smali_root, cls)
        return path, fmt, smali_root, "static_initializer"
    try:
        path, fmt = locate(root, cls)
    except InputError:
        if smali_root is None:
            raise
        path, fmt = locate(smali_root, cls)
        return path, fmt, smali_root, "no_java_source"
    return path, fmt, root, None


def read_source(path, base):
    if os.path.getsize(path) > MAX_FILE_BYTES:
        raise InputError("source file exceeds 16 MiB: %s" % os.path.relpath(path, base))
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def body_status_for(declaration, fmt):
    """Classify a selected body by decompiler markers. Smali bodies carry no jadx markers.

    A body with a failure marker is "decompile_failed". A body with only warning markers is
    "partial". A body with both is "decompile_failed", and body_markers lists the failure
    markers first and then the warning markers.
    """
    if fmt != "java":
        return None, []
    failures = [m for m in DECOMPILE_FAILURE_MARKERS if m in declaration]
    warnings = [m for m in DECOMPILE_WARNING_MARKERS if m in declaration]
    if failures:
        return "decompile_failed", failures + warnings
    if warnings:
        return "partial", warnings
    return None, []


def select(root, cls, method, params_spec, max_lines, smali_root=None):
    split_class(cls)  # refuses a nested class name before any file is read
    path, fmt, base, fallback = pick_source(root, cls, method, smali_root)
    text = read_source(path, base)
    candidates = java_candidates(text, method) if fmt == "java" else smali_candidates(text, method)
    if not candidates and fmt == "java" and smali_root is not None and fallback is None:
        # The Java source does not declare the method. Try the compiled form before giving up.
        try:
            spath, sfmt = locate(smali_root, cls)
        except InputError:
            spath = None
        if spath is not None:
            path, fmt, base, fallback = spath, sfmt, smali_root, "method_not_in_java"
            text = read_source(path, base)
            candidates = smali_candidates(text, method)

    wanted = None
    if params_spec is not None:
        wanted = [simple_type(p) for p in split_top(params_spec)]
    matching = [c for c in candidates if wanted is None or c["params"] == wanted]

    if not candidates:
        status = "not_found"
    elif not matching:
        status = "no_match_for_params"
    elif len(matching) > 1:
        status = "ambiguous"
    else:
        status = "selected"

    result = {
        "source": {"path": os.path.relpath(path, base).replace(os.sep, "/"), "format": fmt},
        "class": cls,
        "method": method,
        "params_requested": wanted,
        "status": status,
        "fallback": fallback,
        "candidates": [
            {k: v for k, v in c.items() if not k.startswith("_")}
            for c in candidates[:MAX_CANDIDATES_SHOWN]
        ],
        "candidate_count": len(candidates),
        "selected": None,
        "body": None,
        "body_status": None,
        "body_markers": [],
        "body_lines": 0,
        "truncated": False,
        "limitations": list(LIMITATIONS),
    }
    if status != "selected":
        return result, 1

    chosen = matching[0]
    start, end = chosen["_span"]
    declaration = text[start:end]
    if chosen["body_status"] == "present":
        status_override, markers = body_status_for(declaration, fmt)
        if status_override is not None:
            chosen["body_status"] = status_override
            result["body_markers"] = markers
    result["selected"] = {k: v for k, v in chosen.items() if not k.startswith("_")}
    result["body_status"] = chosen["body_status"]
    if chosen["body_status"] == "not_available":
        # Abstract, native or interface declaration: there is no body to return.
        result["declaration"] = declaration.strip()
        return result, 0
    lines = declaration.splitlines()
    result["body_lines"] = len(lines)
    if len(lines) > max_lines:
        result["body"] = "\n".join(lines[:max_lines])
        result["truncated"] = True
    else:
        result["body"] = declaration
    return result, 0


def build_parser():
    ap = argparse.ArgumentParser(
        description="Select one method body from decompiled Java or smali; refuse ambiguous overloads.")
    ap.add_argument("root", help="source tree (jadx sources/ or apktool smali*/)")
    ap.add_argument("class_name", metavar="CLASS",
                    help="fully qualified top-level class, e.g. com.example.Api; a nested class name exits 2")
    ap.add_argument("method", help="simple method name")
    ap.add_argument("--params", default=None,
                    help='comma-separated simple parameter types, e.g. "String,int"; "" selects a no-argument '
                         'method. Several matches exit 1 with status "ambiguous"; none exits 1 with '
                         'status "no_match_for_params"')
    ap.add_argument("--max-body-lines", type=int, default=DEFAULT_MAX_BODY_LINES,
                    help="truncate the returned body after N lines (default %d)" % DEFAULT_MAX_BODY_LINES)
    ap.add_argument("--smali-root", default=None,
                    help="apktool output (smali*/); required for <clinit>, used when the Java source lacks the method")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not os.path.isdir(args.root):
        sys.stderr.write("ERROR: source root is not a directory: %s\n" % args.root)
        return 2
    if args.max_body_lines < 1:
        sys.stderr.write("ERROR: --max-body-lines must be at least 1\n")
        return 2
    if args.smali_root is not None and not os.path.isdir(args.smali_root):
        sys.stderr.write("ERROR: smali root is not a directory: %s\n" % args.smali_root)
        return 2
    try:
        result, code = select(args.root, args.class_name, args.method, args.params,
                              args.max_body_lines, smali_root=args.smali_root)
    except InputError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
