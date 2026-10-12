#!/usr/bin/env python3
"""Find GraphQL operations and tRPC procedures in JavaScript or TypeScript sources.

Usage:
    js_rpc_inventory.py SOURCE_DIR --out FILE

SOURCE_DIR is an unpacked app, a recovered-source directory (for example
js_sourcemap_extract.py output) or a directory of bundles. Every .js, .mjs, .cjs, .jsx,
.ts, .tsx and .html file under it is scanned as text. Nothing is executed, and symlinks
are not followed.

It reports request-shape leads that a plain URL search misses, because these clients send
every call to one endpoint:

  graphql    operation literals that start with query, mutation or subscription and a
             name; precompiled OperationDefinition objects; persisted-query hashes; and
             operationName values. Each literal keeps its variables and a SHA-256.
  trpc       procedure member paths such as trpc.user.byId.useQuery(...), grouped by
             path and kind, and the literal url of httpLink, httpBatchLink and similar
             links. The member path survives minification because tRPC proxies need it.

A match is a lead, not proof that the call is reachable or that the server accepts it.
Output: JSON in FILE with mode 0600, plus a summary on stdout. Exit codes: 0 done,
2 usage or input error. Standard library only.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import sys

MAX_FILE_BYTES = 16 * 1024 * 1024
SCAN_EXTS = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".html")
MAX_LITERAL_CHARS = 20_000
MAX_TEXT_CHARS = 4_000
MAX_USES_PER_PROCEDURE = 20
MAX_ITEMS = 5_000

IDENT = r"[A-Za-z_$][\w$]*"
OPERATIONS = ("query", "mutation", "subscription")

# A literal that opens with an operation header: query Name, mutation Name($x: T) { ...
GQL_LITERAL_RE = re.compile(
    r"(?P<quote>[\"'`])\s*(?:#[^\n]*\n\s*|\\n\s*)*"
    r"(?P<op>query|mutation|subscription)\s+(?P<name>[A-Za-z_]\w*)\s*"
    r"(?P<vars>\([^)]{0,1000}\))?\s*(?:@\w+(?:\([^)]*\))?\s*)*[{\\]"
)
GQL_VAR_RE = re.compile(r"\$([A-Za-z_]\w*)\s*:\s*([^,)=$]+)")
GQL_AST_RE = re.compile(
    r"[\"']?kind[\"']?\s*:\s*[\"']OperationDefinition[\"']\s*,\s*[\"']?operation[\"']?\s*:\s*"
    r"[\"'](?P<op>query|mutation|subscription)[\"']\s*,\s*(?:[\"']?(?:variableDefinitions|directives)[\"']?\s*:\s*\[[^\]]{0,2000}\]\s*,\s*)*"
    r"[\"']?name[\"']?\s*:\s*\{\s*[\"']?kind[\"']?\s*:\s*[\"']Name[\"']\s*,\s*[\"']?value[\"']?\s*:\s*"
    r"[\"'](?P<name>[A-Za-z_]\w*)[\"']"
)
GQL_OPNAME_RE = re.compile(r"[\"']?operationName[\"']?\s*[:=]\s*[\"'](?P<name>[A-Za-z_]\w*)[\"']")
GQL_PERSISTED_RE = re.compile(r"[\"']?sha256Hash[\"']?\s*:\s*[\"'](?P<hash>[0-9a-fA-F]{64})[\"']")

TRPC_METHODS = {
    "useQuery": "query", "useSuspenseQuery": "query", "useInfiniteQuery": "query",
    "queryOptions": "query", "infiniteQueryOptions": "query", "query": "query",
    "useMutation": "mutation", "mutationOptions": "mutation", "mutate": "mutation",
    "useSubscription": "subscription", "subscribe": "subscription",
}
TRPC_VANILLA = {"query", "mutate", "subscribe"}
# A file with none of these cannot hold a hook or options-factory call, so skip the regex pass.
TRPC_CHEAP_WORDS = tuple(sorted(set(TRPC_METHODS) - TRPC_VANILLA))
TRPC_CALL_RE = re.compile(
    r"(?<![\w$.])(?P<root>" + IDENT + r")(?P<path>(?:\." + IDENT + r"){1,8})\."
    r"(?P<method>" + "|".join(sorted(TRPC_METHODS, key=len, reverse=True)) + r")\s*\("
)
TRPC_MARKER_RE = re.compile(
    r"@trpc/|createTRPC(?:Client|ProxyClient|React|Next|Untyped\w*)|httpBatchLink|httpBatchStreamLink")
TRPC_BOUND_RE = re.compile(
    r"\b(?P<root>" + IDENT + r")\s*=\s*(?:\w+\.)?createTRPC(?:Client|ProxyClient|React|Next)\w*\s*[(<]")
TRPC_LINK_RE = re.compile(
    r"\b(?P<link>httpBatchLink|httpBatchStreamLink|httpLink|httpSubscriptionLink|wsLink|"
    r"unstable_httpBatchStreamLink|unstable_httpSubscriptionLink|createWSClient)\s*\(\s*\{[^{}]{0,400}?"
    r"\burl\s*:\s*(?P<url>(?P<q>[\"'`])[^\"'`\n$]{1,300}(?P=q))"
)
# Roots and path segments that are never tRPC procedures.
NOT_ROOTS = {"this", "window", "document", "globalThis", "self", "global", "process",
             "console", "Promise", "Object", "Array", "JSON", "Math"}
NOT_SEGMENTS = {"endpoints", "prototype", "constructor"}

LIMITATIONS = [
    "Static text only: a match is a lead, not proof that the call is reachable or accepted by a server",
    "GraphQL literals are found only when the literal opens with the operation keyword; a literal that starts with a fragment is missed",
    "Interpolated template literals keep their ${...} holes as written; the operation text is not evaluated",
    "tRPC vanilla calls (query, mutate, subscribe) need a tRPC marker in the file, and the root bound to a tRPC client or a path of two segments or more",
    "A minifier that renames a link or helper hides it; procedure member paths survive minification",
    "Carrier segments before a router path (a context or utils object) become part of the reported path",
]


class InputError(Exception):
    """Bad input directory. Exit code 2."""


def iter_sources(root):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames
                             if d != "node_modules" and not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            if not name.lower().endswith(SCAN_EXTS):
                continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or os.path.getsize(path) > MAX_FILE_BYTES:
                continue
            yield path


def _literal_end(text, start, quote):
    """Index just past the closing quote of the literal opened at text[start], or None."""
    depth = 0
    i = start + 1
    limit = min(len(text), start + MAX_LITERAL_CHARS)
    while i < limit:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if quote == "`" and ch == "$" and text.startswith("${", i):
            depth += 1
            i += 2
            continue
        if quote == "`" and depth and ch == "}":
            depth -= 1
        elif ch == quote and depth == 0:
            return i + 1
        elif ch == "\n" and quote != "`":
            return None
        i += 1
    return None


def _clean(body):
    return body.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")


def _graphql(text, line_of, rel, out):
    for m in GQL_LITERAL_RE.finditer(text):
        end = _literal_end(text, m.start(), m.group("quote"))
        if end is None:
            continue
        body = _clean(text[m.start() + 1:end - 1])
        variables = [{"name": v.group(1), "type": v.group(2).strip()}
                     for v in GQL_VAR_RE.finditer(m.group("vars") or "")]
        out.append({"kind": m.group("op"), "mechanism": "literal", "name": m.group("name"),
                    "variables": variables, "text_length": len(body),
                    "text_sha256": hashlib.sha256(body.encode("utf-8", "replace")).hexdigest(),
                    "text": body[:MAX_TEXT_CHARS], "truncated": len(body) > MAX_TEXT_CHARS,
                    "file": rel, "line": line_of(m.start())})
    for m in GQL_AST_RE.finditer(text):
        out.append({"kind": m.group("op"), "mechanism": "precompiled", "name": m.group("name"),
                    "variables": [], "file": rel, "line": line_of(m.start())})
    for m in GQL_OPNAME_RE.finditer(text):
        out.append({"kind": "operation-name", "mechanism": "operationName", "name": m.group("name"),
                    "file": rel, "line": line_of(m.start())})
    for m in GQL_PERSISTED_RE.finditer(text):
        out.append({"kind": "persisted-query", "mechanism": "sha256Hash",
                    "sha256": m.group("hash").lower(), "file": rel, "line": line_of(m.start())})


def _trpc(text, line_of, rel, procedures, links):
    for m in TRPC_LINK_RE.finditer(text):
        links.append({"link": m.group("link"), "url": m.group("url")[1:-1],
                      "file": rel, "line": line_of(m.start())})
    marker = bool(TRPC_MARKER_RE.search(text))
    if not marker and not any(word in text for word in TRPC_CHEAP_WORDS):
        return
    bound = {b.group("root") for b in TRPC_BOUND_RE.finditer(text)}
    for m in TRPC_CALL_RE.finditer(text):
        root, method = m.group("root"), m.group("method")
        segments = m.group("path")[1:].split(".")
        if root in NOT_ROOTS or any(s in NOT_SEGMENTS for s in segments):
            continue
        if method in TRPC_VANILLA and not (
                marker and (root in bound or len(segments) >= 2)):
            continue
        procedures.append({"path": ".".join(segments), "kind": TRPC_METHODS[method],
                           "method": method, "root": root, "file": rel, "line": line_of(m.start())})


def _group_procedures(items):
    grouped = {}
    for p in items:
        entry = grouped.setdefault((p["path"], p["kind"]),
                                   {"path": p["path"], "kind": p["kind"], "use_count": 0, "uses": []})
        entry["use_count"] += 1
        if len(entry["uses"]) < MAX_USES_PER_PROCEDURE:
            entry["uses"].append({k: p[k] for k in ("method", "root", "file", "line")})
    return [grouped[k] for k in sorted(grouped)]


def scan(root):
    if not os.path.isdir(root):
        raise InputError("source directory not found: %s" % root)
    rel = lambda p: os.path.relpath(p, root).replace(os.sep, "/")  # noqa: E731
    graphql, procedures, links = [], [], []
    files = 0
    for path in iter_sources(root):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        files += 1
        newlines = [m.start() for m in re.finditer("\n", text)]

        def line_of(pos, newlines=newlines):
            return bisect.bisect_left(newlines, pos) + 1

        _graphql(text, line_of, rel(path), graphql)
        _trpc(text, line_of, rel(path), procedures, links)
    seen, unique = set(), []
    for item in graphql:
        key = (item["kind"], item["mechanism"], item.get("name"), item.get("sha256"),
               item.get("text_sha256"), item["file"], item["line"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    graphql = sorted(unique, key=lambda i: (i["file"], i["line"], i["kind"]))[:MAX_ITEMS]
    grouped = _group_procedures(procedures)[:MAX_ITEMS]
    links = links[:MAX_ITEMS]
    return {
        "source_root": os.path.basename(os.path.abspath(root)),
        "files_scanned": files,
        "graphql": graphql,
        "trpc": {"procedures": grouped, "links": links},
        "counts": {
            "graphql_operations": sum(1 for g in graphql if g["kind"] in OPERATIONS),
            "graphql_operation_names": sum(1 for g in graphql if g["kind"] == "operation-name"),
            "graphql_persisted_hashes": sum(1 for g in graphql if g["kind"] == "persisted-query"),
            "trpc_procedures": len(grouped),
            "trpc_links": len(links),
        },
        "limitations": list(LIMITATIONS),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find GraphQL operations and tRPC procedures statically.")
    ap.add_argument("source", help="unpacked app, recovered sources or bundle directory")
    ap.add_argument("--out", required=True, help="output JSON file")
    args = ap.parse_args(argv)
    try:
        result = scan(args.source)
    except InputError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(args.out, 0o600)
    print(json.dumps({k: v for k, v in result.items() if k not in ("graphql", "trpc", "limitations")},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
