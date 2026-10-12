#!/usr/bin/env python3
"""Parse gojue/ecapture output into structured HTTP requests.

Usage:
    ecapture_parse.py <ecapture_text.log | file.pcapng> [--out DIR] [--literal VALUE | --literal-file FILE]

Text-mode logs from `ecapture tls -m text` contain blocks of metadata
(PID/Comm/TID and a "Send/Recv Data" marker) followed by a hexdump or ascii
payload. This script reassembles the plaintext, extracts HTTP messages
(request line, Host, headers, body), and flags likely auth/signature material.

For .pcapng input it uses scapy or pyshark when importable, otherwise prints a
`tshark` hint and exits gracefully.

Writes <out>/requests.json and prints login-looking requests to stderr: the host, the
path and the signature key names, with declared literals removed from each. --literal
and --literal-file rewrite only requests.json, so a raw capture placed in <out> is left
unchanged; redact_literals.py lists the encodings searched.
No network calls; stdlib-first (scapy/pyshark optional).
"""
import argparse
import json
import os
import re
import sys

from redact_literals import (  # noqa: E402
    LiteralError, add_literal_args, apply_literals, redact_text, resolve_literal_args,
)


# --- patterns for auth/signature material ---------------------------------
SIG_KEY_RE = re.compile(
    r"(?i)^(authorization|x-?sign(ature)?|sign|signature|token|"
    r"access[-_]?token|refresh[-_]?token|nonce|timestamp|ts)$"
)
# For substring matching against header names / json keys.
SIG_SUBSTR_RE = re.compile(
    r"(?i)(authorization|x-?sign|sign|signature|token|nonce|timestamp|(^|[-_])ts($|[-_]))"
)
LOGIN_PATH_RE = re.compile(r"(?i)(login|auth|token|signin|sign-in|oauth|session)")

HTTP_METHODS = (
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT",
)
REQUEST_LINE_RE = re.compile(
    r"^(" + "|".join(HTTP_METHODS) + r")\s+(\S+)\s+(HTTP/\d(?:\.\d)?)\s*$"
)
STATUS_LINE_RE = re.compile(r"^(HTTP/\d(?:\.\d)?)\s+(\d{3})\s*(.*)$")


# --- hexdump / payload reassembly -----------------------------------------
# ecapture text mode typically emits canonical hexdump lines like:
#   00000000  47 45 54 20 2f ...   GET /...
# i.e. offset, hex bytes, then an ascii gutter. We prefer decoding the hex
# bytes (lossless) and fall back to raw ascii lines.
HEXDUMP_LINE_RE = re.compile(
    r"^\s*[0-9a-fA-F]{4,8}\s+((?:[0-9a-fA-F]{2}\s+){1,16})\s*(?:\|.*\|)?\s*$"
)
# A looser variant: offset then hex, ascii gutter separated by 2+ spaces.
HEXDUMP_LINE_RE2 = re.compile(
    r"^\s*[0-9a-fA-F]{4,8}[:\s]\s*"
    r"((?:[0-9a-fA-F]{2}[ ]?){1,16}(?:\s+(?:[0-9a-fA-F]{2}[ ]?){1,16})?)"
    r"\s{2,}(.*)$"
)

# Metadata / boundary markers that separate ecapture event blocks.
META_RE = re.compile(
    r"(?i)\b(PID|Comm|TID|UID|Version|Pid|Tid)\s*[:=]"
)
DIRECTION_RE = re.compile(r"(?i)(Send|Recv|Sent|Received|Write|Read)\s+Data")


def _hex_from_line(line):
    """Return decoded bytes from a hexdump line, or None if not a hexdump."""
    m = HEXDUMP_LINE_RE.match(line)
    hexpart = None
    if m:
        hexpart = m.group(1)
    else:
        m2 = HEXDUMP_LINE_RE2.match(line)
        if m2:
            hexpart = m2.group(1)
    if hexpart is None:
        return None
    tokens = re.findall(r"[0-9a-fA-F]{2}", hexpart)
    if not tokens:
        return None
    try:
        return bytes(int(t, 16) for t in tokens)
    except ValueError:
        return None


def parse_text_log(path):
    """Split an ecapture text log into (direction, payload_bytes) blocks."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    blocks = []
    cur_dir = None
    cur_hex = bytearray()
    cur_ascii = []
    have_hex = False

    def flush():
        nonlocal cur_hex, cur_ascii, have_hex, cur_dir
        payload = b""
        if have_hex and cur_hex:
            payload = bytes(cur_hex)
        elif cur_ascii:
            payload = "\n".join(cur_ascii).encode("utf-8", "replace")
        if payload.strip():
            blocks.append((cur_dir or "unknown", payload))
        cur_hex = bytearray()
        cur_ascii = []
        have_hex = False

    for line in lines:
        dm = DIRECTION_RE.search(line)
        if dm:
            # New event block begins; flush the previous one.
            flush()
            token = dm.group(1).lower()
            cur_dir = "recv" if token in ("recv", "received", "read") else "send"
            continue
        if META_RE.search(line) and _hex_from_line(line) is None:
            # Metadata boundary between blocks (not itself payload).
            # If it clearly starts a new record, flush.
            if re.search(r"(?i)\b(PID|Pid)\s*[:=]", line):
                flush()
            continue

        decoded = _hex_from_line(line)
        if decoded is not None:
            cur_hex.extend(decoded)
            have_hex = True
        else:
            # Plain ascii payload line (some builds print raw text).
            if line.strip() == "" and not (cur_hex or cur_ascii):
                continue
            cur_ascii.append(line)

    flush()
    return blocks


# --- HTTP extraction -------------------------------------------------------
def _split_head_body(payload):
    """Split raw bytes into (head_text, body_bytes) on CRLF CRLF or LF LF."""
    idx = payload.find(b"\r\n\r\n")
    sep = 4
    if idx == -1:
        idx = payload.find(b"\n\n")
        sep = 2
    if idx == -1:
        return payload.decode("utf-8", "replace"), b""
    head = payload[:idx].decode("utf-8", "replace")
    body = payload[idx + sep:]
    return head, body


def _looks_binary(data):
    if not data:
        return False
    sample = data[:512]
    nontext = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return nontext > len(sample) * 0.10


def _find_sig_candidates(headers, body_obj):
    found = {}
    for k, v in headers.items():
        if SIG_KEY_RE.match(k) or SIG_SUBSTR_RE.search(k):
            found[k] = v

    def walk(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                if SIG_SUBSTR_RE.search(key):
                    label = (prefix + "." + key) if prefix else key
                    if isinstance(v, (dict, list)):
                        found[label] = json.dumps(v)[:200]
                    else:
                        found[label] = v
                walk(v, (prefix + "." + key) if prefix else key)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, "%s[%d]" % (prefix, i))

    if isinstance(body_obj, (dict, list)):
        walk(body_obj)
    return found


def extract_http(direction, payload):
    """Return an HTTP record dict from a payload, or None if not HTTP."""
    head, body = _split_head_body(payload)
    head_lines = head.split("\n")
    if not head_lines:
        return None
    first = head_lines[0].rstrip("\r")

    req = REQUEST_LINE_RE.match(first)
    sts = STATUS_LINE_RE.match(first)
    if not req and not sts:
        return None

    method = path = version = None
    status = None
    if req:
        method, path, version = req.group(1), req.group(2), req.group(3)
    else:
        version, status = sts.group(1), int(sts.group(2))

    headers = {}
    for hl in head_lines[1:]:
        hl = hl.rstrip("\r")
        if not hl:
            continue
        if ":" not in hl:
            continue
        name, _, val = hl.partition(":")
        headers[name.strip()] = val.strip()

    host = headers.get("Host") or headers.get("host")

    # HTTP/2 or binary payloads: note rather than mis-decode.
    is_http2 = bool(version and version.startswith("HTTP/2"))
    body_text = None
    body_obj = None
    body_note = None
    if is_http2:
        body_note = "HTTP/2 or binary framing; body not reassembled as text."
    elif _looks_binary(body):
        body_note = "binary/compressed body (%d bytes) not decoded." % len(body)
    else:
        body_text = body.decode("utf-8", "replace")
        ctype = (headers.get("Content-Type") or headers.get("content-type") or "")
        stripped = body_text.strip()
        if stripped and (
            "json" in ctype.lower()
            or stripped[0] in "{["
        ):
            try:
                body_obj = json.loads(stripped)
            except ValueError:
                body_obj = None

    record = {
        "direction": direction,
        "host": host,
        "method": method,
        "path": path,
        "version": version,
        "status": status,
        "headers": headers,
        "body": body_text if body_text is not None else body_note,
        "sig_candidates": _find_sig_candidates(headers, body_obj),
    }
    return record


# --- pcapng handling -------------------------------------------------------
def parse_pcapng(path):
    """Best-effort pcapng parse via scapy/pyshark; else return None + hint."""
    records = []

    # Try pyshark first (understands HTTP layers directly).
    try:
        import pyshark  # type: ignore

        cap = pyshark.FileCapture(path, display_filter="http")
        try:
            for pkt in cap:
                try:
                    http = pkt.http
                except AttributeError:
                    continue
                headers = {}
                for field in getattr(http, "field_names", []):
                    try:
                        headers[field] = getattr(http, field)
                    except Exception:  # noqa: BLE001
                        pass
                method = getattr(http, "request_method", None)
                path_v = getattr(http, "request_uri", None)
                host = getattr(http, "host", None)
                direction = "send" if method else "recv"
                records.append({
                    "direction": direction,
                    "host": host,
                    "method": method,
                    "path": path_v,
                    "version": None,
                    "status": getattr(http, "response_code", None),
                    "headers": headers,
                    "body": getattr(http, "file_data", None),
                    "sig_candidates": _find_sig_candidates(headers, None),
                })
        finally:
            cap.close()
        return records
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("pyshark parse failed (%s); trying scapy.\n" % exc)

    # Fall back to scapy: reassemble TCP payloads crudely per (src,dst,sport,dport).
    try:
        from scapy.all import PcapReader, Raw  # type: ignore
        from scapy.layers.inet import IP, TCP  # type: ignore

        streams = {}
        with PcapReader(path) as pr:
            for pkt in pr:
                if not (pkt.haslayer(TCP) and pkt.haslayer(Raw)):
                    continue
                ip = pkt.getlayer(IP)
                tcp = pkt.getlayer(TCP)
                if ip is None:
                    continue
                key = (ip.src, ip.dst, tcp.sport, tcp.dport)
                streams.setdefault(key, bytearray()).extend(bytes(pkt[Raw].load))

        for key, data in streams.items():
            direction = "send" if key[3] in (80, 443, 8080, 8443) else "recv"
            rec = extract_http(direction, bytes(data))
            if rec:
                records.append(rec)
        return records
    except ImportError:
        return None
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("scapy parse failed: %s\n" % exc)
        return None


def tshark_hint(path):
    sys.stderr.write(
        "\nNo scapy/pyshark available to parse pcapng.\n"
        "Install one (`pip install pyshark` or `pip install scapy`), or use tshark:\n"
        "  tshark -r %s -Y http -T fields -e http.request.method "
        "-e http.host -e http.request.uri\n"
        "  tshark -r %s -Y http --export-objects http,./http_objects\n\n"
        % (path, path)
    )


# --- driver ----------------------------------------------------------------
def is_pcap(path):
    lower = path.lower()
    if lower.endswith((".pcapng", ".pcap", ".cap")):
        return True
    try:
        with open(path, "rb") as fh:
            magic = fh.read(4)
        # pcapng: 0x0A0D0D0A ; pcap: 0xA1B2C3D4 / 0xD4C3B2A1
        return magic in (
            b"\x0a\x0d\x0d\x0a",
            b"\xa1\xb2\xc3\xd4",
            b"\xd4\xc3\xb2\xa1",
            b"\x4d\x3c\xb2\xa1",
        )
    except OSError:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Parse ecapture text log or pcapng into structured HTTP requests."
    )
    ap.add_argument("input", help="ecapture_text.log or file.pcapng")
    ap.add_argument("--out", default="./re_out", help="output directory (default ./re_out)")
    add_literal_args(ap)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        sys.stderr.write("ERROR: input not found: %s\n" % args.input)
        return 2
    try:
        literals = resolve_literal_args(args)
    except LiteralError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    os.makedirs(args.out, exist_ok=True)

    if is_pcap(args.input):
        records = parse_pcapng(args.input)
        if records is None:
            tshark_hint(args.input)
            return 0
    else:
        records = []
        for direction, payload in parse_text_log(args.input):
            rec = extract_http(direction, payload)
            if rec:
                records.append(rec)

    out_path = os.path.join(args.out, "requests.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False, default=str)
    sys.stderr.write("Wrote %d HTTP record(s) -> %s\n" % (len(records), out_path))
    apply_literals(literals, args.out, files=[out_path])

    # Login-looking requests to stderr.
    login = [
        r for r in records
        if r.get("path") and LOGIN_PATH_RE.search(str(r["path"]))
    ]
    if login:
        sys.stderr.write("\nLogin-looking requests:\n")
        for r in login:
            # Signature key names come from the captured headers and body, so each is redacted too.
            sigs = ",".join(sorted(redact_text(k, literals)[0] for k in r.get("sig_candidates", {}))) or "-"
            sys.stderr.write(
                "  [%s] %s %s%s  sig:{%s}\n" % (
                    r.get("direction", "?"),
                    r.get("method") or "",
                    redact_text(r.get("host") or "", literals)[0],
                    redact_text(r.get("path") or "", literals)[0],
                    sigs,
                )
            )
    else:
        sys.stderr.write("\nNo obvious login/auth/token paths found.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
