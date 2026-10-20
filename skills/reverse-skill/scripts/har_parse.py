#!/usr/bin/env python3
"""Parse a HAR 1.2 capture or a native Fiddler SAZ archive into ecapture-shaped records.

Usage:
    har_parse.py CAPTURE.har|CAPTURE.saz --out DIR [--redact] [--literal VALUE | --literal-file FILE]

A file that starts with the ZIP signature is read as a Fiddler SAZ archive. Each session
number NN gives one HAR-shaped entry from raw/NN_c.txt (the request, raw HTTP/1.x) and
raw/NN_s.txt (the response). The stored bytes are kept: the response body is base64 in the
HAR content, and a request body that is not UTF-8 is recorded by its size and sha256 only.
The start time is the ClientConnected attribute of raw/NN_m.xml, as Fiddler wrote it. The
archive is refused when a member is encrypted, is a link, repeats a name, or expands past
256 MiB. raw/NN_w.txt (WebSocket) and raw/NN_g.txt (gRPC) members are not decoded and are
listed in the manifest. Encrypted, linked and oversized archives are refused with exit 2.

Each HAR entry with a request method, a request URL that parses and an integer response
status yields a "send" record (the request) and a "recv" record (the response) with the
keys ecapture_parse.py writes, plus url, source, entry_index, started and redactions;

Each HAR entry with a request method, a request URL that parses and an integer response
status yields a "send" record (the request) and a "recv" record (the response) with the
keys ecapture_parse.py writes, plus url, source, entry_index, started and redactions;
send records whose postData.params is a non-empty list also have form_params, and recv
records with base64 content that decodes also have body_sha256. Other entries are skipped and listed under
skipped_entries in har_manifest.json. sig_candidates reuse ecapture_parse's heuristics
over headers, JSON bodies, query parameters and form parameters.

Writes DIR/requests.json and DIR/har_manifest.json. DIR must not exist. It is
created mode 0700 with 0600 files, because the raw output holds credentials.
--redact replaces the following with "[REDACTED]": the values of the headers in
REDACT_HEADERS (Cookie, Set-Cookie, Authorization and Proxy-Authorization); the values
of JSON object keys whose names match REDACT_KEY_RE; the values of query parameters
and form fields whose names match REDACT_KEY_RE (and name=value pairs in other header
values); and the password in the request URL's userinfo.
Form fields come from a postData.params list, and a body that is not JSON and contains
"=" is checked as name=value pairs separated by "&". A body nested deeper than
JSON_MAX_DEPTH levels, or too deep for json.loads, is withheld instead of redacted.
Signature fields, timestamps and nonces are kept on purpose.
--literal and --literal-file rewrite only requests.json and har_manifest.json, the files
this run wrote; redact_literals.py lists the encodings searched.
Prints counts to stderr and, for login-looking POST, PUT or PATCH send requests, the
method and the templated path without the query. Path segments that match no templating
rule are printed as they are, apart from declared literals. No network calls; stdlib only.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecapture_parse import _find_sig_candidates, _looks_binary  # noqa: E402
from endpoint_inventory import template_path  # noqa: E402
from redact_literals import (  # noqa: E402
    LiteralError, add_literal_args, apply_literals, redact_text, resolve_literal_args,
)

MAX_HAR_BYTES = 256 * 1024 * 1024
REDACTED = "[REDACTED]"
REDACT_HEADERS = ("cookie", "set-cookie", "authorization", "proxy-authorization")
REDACT_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|refresh[-_]?token|access[-_]?token|session)"
)
LOGIN_PATH_RE = re.compile(r"(?i)(login|auth|token|sign)")
LOGIN_METHODS = ("POST", "PUT", "PATCH")
JSON_MAX_DEPTH = 200


def _show(text, limit=160):
    """Escape untrusted text before it reaches the terminal."""
    s = str(text).encode("unicode_escape").decode("ascii")
    return s if len(s) <= limit else s[:limit] + "..."


def _norm_version(value):
    """Map HAR httpVersion ("http/1.1", "h2") to ecapture style ("HTTP/1.1")."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    low = text.lower()
    if low in ("h2", "h2c"):
        return "HTTP/2"
    if low == "h3":
        return "HTTP/3"
    if low.startswith("http/"):
        return "HTTP/" + text[5:]
    return text


def _add_pair(target, name, value):
    """Store name=value; repeated names become lists, in order."""
    if name not in target:
        target[name] = value
    elif isinstance(target[name], list):
        target[name].append(value)
    else:
        target[name] = [target[name], value]


def _headers_dict(items):
    """HAR header list to dict. Names match case-insensitively; repeats join with ", "."""
    out = {}
    spelled = {}
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        name = item["name"]
        if not name:
            continue
        value = item.get("value")
        value = "" if value is None else str(value)
        key = spelled.setdefault(name.lower(), name)
        if key in out:
            out[key] = out[key] + ", " + value
        else:
            out[key] = value
    return out


def _redact_headers(headers):
    """Redact listed headers whole, and secret-looking name=value pairs in any other header value.

    A Referer or Location header can carry a query string, so its value is searched the same way
    as a URL query. A value with no "=" cannot hold a name=value pair and is left unchanged.
    """
    count = 0
    for key in headers:
        if key.lower() in REDACT_HEADERS:
            headers[key] = REDACTED
            count += 1
        elif isinstance(headers[key], str) and "=" in headers[key]:
            headers[key], n = _redact_query(headers[key])
            count += n
    return count


def _redact_json(obj):
    """Replace whole values under secret-looking keys, in place. Returns the count."""
    count = 0
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if REDACT_KEY_RE.search(str(key)):
                obj[key] = REDACTED
                count += 1
            else:
                count += _redact_json(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            count += _redact_json(item)
    return count


def _redact_query(text):
    """Redact secret-looking name=value pairs in a query or urlencoded string."""
    if not text:
        return text, 0
    count = 0
    parts = []
    for part in text.split("&"):
        name, eq, value = part.partition("=")
        if eq and value and REDACT_KEY_RE.search(urllib.parse.unquote_plus(name)):
            parts.append(name + "=" + REDACTED)
            count += 1
        else:
            parts.append(part)
    return "&".join(parts), count


# The WHATWG URL parser ends a special scheme's authority at the first of / ? # \, and
# any other scheme's at / ? #. urllib.parse.urlsplit does not stop at a backslash, so a
# crafted URL such as https://user:pass@real.host\x@fake/p hides its real host
# (real.host) inside what urlsplit reports as userinfo and names "fake" as the host.
# These helpers bound the authority and path the way a browser would, so a captured
# endpoint is reported correctly and redaction does not corrupt the rest of the URL. A
# well-formed URL has no backslash in its authority, so its host, path and query are
# bounded exactly as urlsplit bounds them and the output is unchanged.
_SCHEME_AUTHORITY_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_SPECIAL_SCHEME_RE = re.compile(r"(?i)^(?:https?|wss?|ftp)://")


def _authority_span(url):
    """(start, end) offsets of url's authority, or None if it has no // authority."""
    m = _SCHEME_AUTHORITY_RE.match(url)
    if not m:
        return None
    start = m.end()
    terminators = "/?#\\" if _SPECIAL_SCHEME_RE.match(url) else "/?#"
    end = len(url)
    for i in range(start, len(url)):
        if url[i] in terminators:
            end = i
            break
    return start, end


def _host_path_query(url):
    """Host (with any port), path and query of url, bounded as a browser bounds them."""
    span = _authority_span(url)
    if span is None:
        parts = urllib.parse.urlsplit(url)
        return (parts.netloc.rpartition("@")[2] or None, parts.path, parts.query)
    start, end = span
    host = url[start:end].rpartition("@")[2] or None
    rest = url[end:]
    frag = rest.find("#")
    if frag != -1:
        rest = rest[:frag]
    q = rest.find("?")
    if q == -1:
        return host, rest, ""
    return host, rest[:q], rest[q + 1:]


def _redact_url(url):
    """Redact a URL's userinfo password and secret-looking query values."""
    parts = urllib.parse.urlsplit(url)
    count = 0
    span = _authority_span(url)
    authority = url[span[0]:span[1]] if span is not None else parts.netloc
    userinfo, at, hostport = authority.rpartition("@")
    if at and ":" in userinfo:
        authority = userinfo.split(":", 1)[0] + ":" + REDACTED + "@" + hostport
        count += 1
    _, path, raw_query = _host_path_query(url)
    query, n = _redact_query(raw_query)
    count += n
    if count == 0:
        return url, 0
    rebuilt = urllib.parse.urlunsplit((parts.scheme, authority, path, query, parts.fragment))
    return rebuilt, count


def _too_deep(obj, limit=JSON_MAX_DEPTH):
    """Iterative nesting check, so recursive walkers below never hit the recursion limit."""
    stack = [(obj, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > limit:
            return True
        if isinstance(node, dict):
            stack.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            stack.extend((v, depth + 1) for v in node)
    return False


def _withheld():
    """The note that replaces a body that cannot be checked for secrets."""
    return "JSON body nested deeper than %d levels; withheld (cannot be redacted)." % JSON_MAX_DEPTH


def _process_text(text, redact):
    """A body that is not JSON. With redaction, text that holds '=' is checked as name=value pairs."""
    if not redact or "=" not in text:
        return text, None, 0
    body, count = _redact_query(text)
    return body, None, count


def _process_body(text, redact):
    """Parse a body. Returns (body_text, parsed_or_None, redactions).

    A body that starts with "{" or "[" and parses as JSON is checked as JSON. With
    redaction, a changed body is re-serialized: compact input stays compact; anything
    else is re-dumped with default separators. With redaction, a body nested deeper
    than JSON_MAX_DEPTH is withheld, and so is one that json.loads or the redaction
    walk cannot finish because of the recursion limit, since it cannot be checked
    safely. Any other body goes to _process_text.
    """
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return _process_text(text, redact)
    try:
        obj = json.loads(stripped)
    except RecursionError:
        return (_withheld(), None, 0) if redact else (text, None, 0)
    except ValueError:
        return _process_text(text, redact)
    if _too_deep(obj):
        return (_withheld(), None, 0) if redact else (text, None, 0)
    if not redact:
        return text, obj, 0
    try:
        compact = stripped == json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        count = _redact_json(obj)
        if count == 0:
            return text, obj, 0
        separators = (",", ":") if compact else None
        return json.dumps(obj, ensure_ascii=False, separators=separators), obj, count
    except RecursionError:
        return _withheld(), None, 0


def _form_params(params):
    out = {}
    for item in params:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        value = item.get("value")
        if not isinstance(value, str):
            file_name = item.get("fileName")
            value = "[file %s]" % file_name if isinstance(file_name, str) else ""
        _add_pair(out, item["name"], value)
    return out


def _query_dict(query):
    out = {}
    for name, value in urllib.parse.parse_qsl(query, keep_blank_values=True):
        _add_pair(out, name, value)
    return out


def _prefixed_candidates(mapping, prefix):
    return {prefix + k: v for k, v in _find_sig_candidates({}, mapping).items()}


def _response_body(content, redact):
    """Return (body, body_sha256 or None, redactions) for a HAR content object."""
    if not isinstance(content, dict):
        return "content absent", None, 0
    text = content.get("text")
    if not isinstance(text, str):
        return "content.text absent", None, 0
    encoding = content.get("encoding")
    if not encoding:
        body, _, count = _process_body(text, redact)
        return body, None, count
    if encoding != "base64":
        return "content.encoding %s not decoded" % encoding, None, 0
    try:
        raw = base64.b64decode("".join(text.split()), validate=True)
    except ValueError:
        return "base64 content.text could not be decoded", None, 0
    digest = hashlib.sha256(raw).hexdigest()
    if _looks_binary(raw):
        note = "binary body (%d bytes, sha256=%s) not decoded." % (len(raw), digest)
        return note, digest, 0
    body, _, count = _process_body(raw.decode("utf-8", "replace"), redact)
    return body, digest, count


def _build_records(index, entry, redact):
    """Return ((send, recv, host), None), or (None, skip_reason) for an unusable entry."""
    if not isinstance(entry, dict):
        return None, "entry is not an object"
    req = entry.get("request")
    res = entry.get("response")
    if not isinstance(req, dict) or not isinstance(req.get("method"), str) or not req["method"]:
        return None, "request method missing"
    if not isinstance(req.get("url"), str) or not req["url"]:
        return None, "request url missing"
    status = res.get("status") if isinstance(res, dict) else None
    if isinstance(status, bool) or not isinstance(status, int):
        return None, "response status missing"
    try:
        # Structure comes from the original URL; the redacted string is only for output.
        parts = urllib.parse.urlsplit(req["url"])
        url, url_red = _redact_url(req["url"]) if redact else (req["url"], 0)
    except ValueError:
        return None, "url not parseable"

    host, raw_path, raw_query = _host_path_query(req["url"])
    query, _ = _redact_query(raw_query) if redact else (raw_query, 0)
    path = (raw_path or "/") + ("?" + query if query else "")
    started = entry.get("startedDateTime")
    started = started if isinstance(started, str) else None

    # Send record: the request.
    send_headers = _headers_dict(req.get("headers"))
    send_red = url_red + (_redact_headers(send_headers) if redact else 0)
    body, obj, form = None, None, None
    post = req.get("postData")
    if isinstance(post, dict):
        params = post.get("params")
        if isinstance(params, list) and params:
            form = _form_params(params)
        raw_text = post.get("text")
        if isinstance(raw_text, str):
            body, obj, n = _process_body(raw_text, redact)
            send_red += n
    if body is None:
        body = "postData.text absent"
    if form is not None and redact:
        send_red += _redact_json(form)

    query_params = _query_dict(query)
    sig = _find_sig_candidates(send_headers, obj)
    sig.update(_prefixed_candidates(query_params, "query."))
    if form is not None:
        sig.update(_prefixed_candidates(form, "form."))

    send = {
        "direction": "send",
        "host": host,
        "method": req["method"],
        "path": path,
        "version": _norm_version(req.get("httpVersion")),
        "status": None,
        "headers": send_headers,
        "body": body,
        "sig_candidates": sig,
        "url": url,
        "source": "har",
        "entry_index": index,
        "started": started,
        "redactions": send_red,
    }
    if form is not None:
        send["form_params"] = form

    # Recv record: the response. Its sig_candidates come from headers only.
    recv_headers = _headers_dict(res.get("headers"))
    recv_red = url_red + (_redact_headers(recv_headers) if redact else 0)
    recv_body, digest, n = _response_body(res.get("content"), redact)
    recv_red += n
    recv = {
        "direction": "recv",
        "host": None,
        "method": None,
        "path": None,
        "version": _norm_version(res.get("httpVersion")),
        "status": status,
        "headers": recv_headers,
        "body": recv_body,
        "sig_candidates": _find_sig_candidates(recv_headers, None),
        "url": url,
        "source": "har",
        "entry_index": index,
        "started": started,
        "redactions": recv_red,
    }
    if digest is not None:
        recv["body_sha256"] = digest
    return (send, recv, host), None


def _process_entries(entries, redact):
    records, skipped, hosts = [], [], {}
    for index, entry in enumerate(entries):
        built, reason = _build_records(index, entry, redact)
        if built is None:
            skipped.append({"entry_index": index, "reason": reason})
            continue
        send, recv, host = built
        records.extend((send, recv))
        key = host or "(no host)"
        hosts[key] = hosts.get(key, 0) + 1
    return records, skipped, dict(sorted(hosts.items()))


class SazError(Exception):
    """A SAZ archive that cannot be decoded. The message names the member or the limit."""


SAZ_SESSION_RE = re.compile(r"^raw/(\d+)_(c\.txt|s\.txt|m\.xml|w\.txt|g\.txt)$")
SAZ_CLIENT_CONNECTED_RE = re.compile(rb'ClientConnected="([^"]{1,64})"')


def _split_http(blob):
    """(start line, [(name, value)], body bytes) of a raw HTTP/1.x message as Fiddler stores it."""
    head, sep, body = blob.partition(b"\r\n\r\n")
    if not sep:
        head, sep, body = blob.partition(b"\n\n")
    lines = head.decode("latin-1").splitlines()
    start = lines[0] if lines else ""
    headers = []
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        if colon and name.strip():
            headers.append((name.strip(), value.strip()))
    return start, headers, body


def _saz_header_list(headers):
    return [{"name": n, "value": v} for n, v in headers]


def _saz_entry(request_bytes, response_bytes, started):
    """One HAR-shaped entry from the raw request and response of a SAZ session."""
    start, req_headers, body = _split_http(request_bytes)
    parts = start.split(" ", 2)
    method = parts[0] if parts else ""
    target = parts[1] if len(parts) > 1 else ""
    host = next((v for n, v in req_headers if n.lower() == "host"), None)
    if target.startswith(("http://", "https://")):
        url = target
    elif method == "CONNECT":
        url = "https://" + target
    else:
        url = "http://%s%s" % (host or "unknown-host", target or "/")
    content_type = next((v for n, v in req_headers if n.lower() == "content-type"), None)
    post = None
    if body:
        try:
            post = {"mimeType": content_type or "", "text": body.decode("utf-8")}
        except UnicodeDecodeError:
            digest = hashlib.sha256(body).hexdigest()
            post = {"mimeType": content_type or "",
                    "text": "binary request body (%d bytes, sha256=%s) not decoded." % (len(body), digest)}
    request = {"method": method, "url": url, "httpVersion": parts[2] if len(parts) > 2 else "",
               "headers": _saz_header_list(req_headers)}
    if post is not None:
        request["postData"] = post

    response = None
    if response_bytes is not None:
        rstart, rheaders, rbody = _split_http(response_bytes)
        rparts = rstart.split(" ", 2)
        status = int(rparts[1]) if len(rparts) > 1 and rparts[1].isdigit() else None
        rtype = next((v for n, v in rheaders if n.lower() == "content-type"), "")
        response = {"status": status, "httpVersion": rparts[0] if rparts else "",
                    "headers": _saz_header_list(rheaders),
                    "content": {"size": len(rbody), "mimeType": rtype,
                                "encoding": "base64",
                                "text": base64.b64encode(rbody).decode("ascii")}}
    return {"startedDateTime": started, "request": request, "response": response or {}}


def saz_to_har(raw):
    """Convert SAZ bytes to a HAR 1.2 log dict, one entry per session. Returns (log, notes)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise SazError("SAZ archive is not a valid ZIP file")
    sessions, unrecognized, skipped_members = {}, [], []
    seen, total = set(), 0
    with zf:
        for info in zf.infolist():
            if info.filename in seen:
                raise SazError("SAZ archive repeats the member name %r" % info.filename)
            seen.add(info.filename)
            if info.flag_bits & 0x1:
                raise SazError("SAZ member %r is encrypted; export an unencrypted copy from Fiddler"
                               % info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise SazError("SAZ member %r is a link, which is not read" % info.filename)
            if info.is_dir():
                continue
            total += info.file_size
            if total > MAX_HAR_BYTES:
                raise SazError("SAZ expanded members exceed the 256 MiB limit")
            m = SAZ_SESSION_RE.match(info.filename)
            if not m:
                if info.filename.startswith("raw/"):
                    unrecognized.append(info.filename)
                continue
            if m.group(2) in ("w.txt", "g.txt"):
                skipped_members.append(info.filename)
                continue
            with zf.open(info) as fh:
                data = fh.read(info.file_size + 1)
            if len(data) != info.file_size:
                raise SazError("SAZ member %r does not match its declared size" % info.filename)
            sessions.setdefault(int(m.group(1)), {})[m.group(2)] = data
    if not sessions:
        raise SazError("SAZ archive has no raw/NN_c.txt or raw/NN_s.txt session members")
    entries = []
    for number in sorted(sessions):
        members = sessions[number]
        started = None
        if "m.xml" in members:
            found = SAZ_CLIENT_CONNECTED_RE.search(members["m.xml"])
            started = found.group(1).decode("utf-8", "replace") if found else None
        if "c.txt" not in members:
            entries.append({"startedDateTime": started, "request": {}, "response": {}})
            continue
        entries.append(_saz_entry(members["c.txt"], members.get("s.txt"), started))
    notes = []
    if unrecognized:
        notes.append("unrecognized raw members were not read: %s" % ", ".join(sorted(unrecognized)))
    if skipped_members:
        notes.append("WebSocket or gRPC members were not decoded: %s" % ", ".join(sorted(skipped_members)))
    log = {"version": "1.2", "creator": {"name": "Fiddler SAZ", "version": None}, "entries": entries}
    return log, notes


def _limitations(redact):
    items = [
        "No TLS or connection attribution: the HAR does not tie requests to processes, sockets or certificates.",
        "Response text is producer-decoded: Chromium and Playwright store decompressed text for compressed responses, so it may differ from the wire bytes.",
        "HTTP/2 framing is not represented; httpVersion is copied from the HAR, not checked against the wire.",
        "No live attribution: this is the recorder's snapshot, not a runtime observation of the app.",
        "Nothing was re-sent: no request was replayed, so signatures and tokens are not proven valid.",
        "Multipart bodies are not reconstructed, and their parts are not checked for secrets. Other bodies "
        "that are not valid JSON are checked only under --redact, and only as name=value pairs separated by '&'.",
        "sig_candidates are key-name heuristics (ecapture_parse rules) over headers, JSON bodies, query and form parameters; they are candidates, not proof of signing.",
        "Set-Cookie duplicates are joined with ', ' as specified; cookie attributes such as Expires can contain commas.",
    ]
    if redact:
        items.append(
            "Redaction replaces the values of the listed header names (Cookie, Set-Cookie, "
            "Authorization, Proxy-Authorization) in both records. Elsewhere it replaces the value of "
            "each name=value pair or JSON key whose name contains password, passwd, pwd, secret, "
            "refresh/access token or session: in other header values, the request URL's query, form "
            "fields, and bodies that parse as JSON (request and response); other non-JSON bodies are "
            "checked only for such pairs separated by '&'. It also replaces the password in the request "
            "URL's userinfo. URL fragments, path segments and query parts with no '=' are not redacted; "
            "names without these words (such as token, sign, nonce or timestamp) are kept by design, so "
            "a shared file may still contain bearer tokens."
        )
        items.append(
            "Redacted JSON bodies are re-serialized; byte-exact formatting is kept only for compact JSON "
            "and default-separator JSON is used otherwise. JSON nested deeper than %d levels, or too deep "
            "for the JSON parser, is withheld rather than redacted." % JSON_MAX_DEPTH
        )
    else:
        items.append(
            "No redaction was applied: cookies, Authorization headers, tokens and passwords are stored "
            "in clear text. This output must not be shared; rerun with --redact first."
        )
    return items


def _write_private_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


def _login_display(path, literals):
    """Templated request path for the console, without the query, with declared literals removed.

    Literals are removed before templating, so a literal that spans a segment boundary
    cannot be split into a templated part and a printed part. They are removed again
    after templating, because template_path decodes percent-encoding.
    """
    bare = redact_text(path.partition("?")[0], literals)[0]
    try:
        template, _names = template_path(bare)
    except ValueError:
        # urlsplit rejects some paths, for example an unclosed "[" after "//". Show no path.
        return "(path not templated)"
    return redact_text(template, literals)[0]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Parse a HAR 1.2 capture or a Fiddler SAZ archive into ecapture-shaped "
                    "request and response records."
    )
    ap.add_argument("capture", help="HAR 1.2 file or SAZ archive (max 256 MiB)")
    ap.add_argument("--out", required=True, help="output directory (must not exist)")
    ap.add_argument("--redact", action="store_true",
                    help="redact cookies, authorization and secret-looking values")
    add_literal_args(ap)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.capture):
        sys.stderr.write("ERROR: HAR file not found: %s\n" % _show(args.capture))
        return 2
    if os.path.getsize(args.capture) > MAX_HAR_BYTES:
        sys.stderr.write("ERROR: HAR file exceeds the 256 MiB limit: %s\n" % _show(args.capture))
        return 2
    try:
        literals = resolve_literal_args(args)
    except LiteralError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    if os.path.lexists(args.out):
        sys.stderr.write("ERROR: output directory already exists; refusing to write into it: %s\n"
                         % _show(args.out))
        return 2

    with open(args.capture, "rb") as fh:
        raw = fh.read()
    saz_notes = []
    if raw[:4] == b"PK\x03\x04":
        try:
            log, saz_notes = saz_to_har(raw)
        except SazError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 2
        input_format = "saz"
    else:
        input_format = "har"
        try:
            har = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, RecursionError):
            sys.stderr.write("ERROR: input is not valid JSON (HAR 1.2 or SAZ expected)\n")
            return 2
        log = har.get("log") if isinstance(har, dict) else None
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list):
        sys.stderr.write("ERROR: log.entries is not a list; not a HAR 1.2 file\n")
        return 2

    records, skipped, hosts = _process_entries(entries, args.redact)
    total_red = sum(r["redactions"] for r in records)
    creator = log.get("creator") if isinstance(log.get("creator"), dict) else None
    manifest = {
        "source_path": os.path.abspath(args.capture),
        "input_format": input_format,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "creator": {"name": creator.get("name"), "version": creator.get("version")}
        if creator else None,
        "har_version": log.get("version"),
        "entry_count": len(entries),
        "record_count": len(records),
        "skipped_entries": skipped,
        "host_counts": hosts,
        "redaction": {
            "enabled": bool(args.redact),
            "total_redactions": total_red,
            "notice": None if args.redact else (
                "No redaction applied. The session directory is restricted (0700) and "
                "redaction is required before sharing: rerun with --redact."
            ),
        },
        "permissions": "output directory 0700, files 0600",
        "limitations": _limitations(args.redact),
        "notes": saz_notes,
    }

    try:
        os.makedirs(args.out, mode=0o700)
    except FileExistsError:
        sys.stderr.write("ERROR: output directory already exists; refusing to write into it\n")
        return 2
    os.chmod(args.out, 0o700)
    requests_path = os.path.join(args.out, "requests.json")
    manifest_path = os.path.join(args.out, "har_manifest.json")
    _write_private_json(requests_path, records)
    _write_private_json(manifest_path, manifest)
    written = [requests_path, manifest_path]

    sys.stderr.write("har_parse: %d entries, %d skipped, %d records -> %s\n"
                     % (len(entries), len(skipped), len(records), _show(args.out)))
    if args.redact:
        sys.stderr.write("redaction on: %d redaction(s) counted across the output records; "
                         "a redacted URL is counted in both its send and recv record\n" % total_red)
    else:
        sys.stderr.write("WARNING: redaction off. Output holds raw cookies, tokens and passwords "
                         "(directory is 0700). Redact before sharing.\n")

    login = [
        r for r in records
        if r["direction"] == "send" and str(r["method"]).upper() in LOGIN_METHODS
        and LOGIN_PATH_RE.search(r["path"] or "")
    ]
    if login:
        sys.stderr.write("\nLogin-looking send requests (templated path, query omitted):\n")
        for r in login:
            _, _, query = r["path"].partition("?")
            sys.stderr.write("  [entry %d] %s %s%s\n" % (
                r["entry_index"], r["method"], _show(_login_display(r["path"], literals)),
                " (query omitted)" if query else ""))
    else:
        sys.stderr.write("\nNo login/auth/token/sign POST, PUT or PATCH paths found.\n")

    apply_literals(literals, args.out, files=written)
    if entries and not records:
        sys.stderr.write("ERROR: no usable entries; see skipped_entries in har_manifest.json\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
