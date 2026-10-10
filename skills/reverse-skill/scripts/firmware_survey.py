#!/usr/bin/env python3
"""Survey an extracted root filesystem with static, read-only checks.

Usage:
    firmware_survey.py ROOT --out DIR [--max-file-bytes N] [--max-items N]

ROOT is an extracted root filesystem directory, for example the <name>_extract
directory that firmware_unpack.py creates under DIR/extracted. The output
directory DIR must not exist; it is created and receives survey.json, and a
one-screen summary is printed to stdout.

Read-only and static. Nothing is executed. os.walk runs with followlinks=False,
symlinks are recorded by target text and never followed, and every file is
opened with O_NOFOLLOW. Files above --max-file-bytes (default 32 MiB) are not
hashed or scanned for strings, keys, banners or routes; for those only the ELF
header and program header table are read. Every list is capped at --max-items
(default 500) with a truncated flag. Hashes, salts and key bodies are never
printed or written. Standard library only.

Sections: counts, elf, symlinks, init_scripts, accounts, keys_and_certs, web,
route_candidates, version_banners, errors, limitations.

Exit codes: 0 success, 1 analysis or output failure, 2 usage or input error.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import stat
import struct
import sys
from datetime import datetime, timezone


DEFAULT_MAX_FILE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_ITEMS = 500
PEM_SCAN_BYTES = 64 * 1024
TEXT_SNIFF_BYTES = 8192
MAX_PHDR_TABLE_BYTES = 1024 * 1024
SUMMARY_SAMPLE = 5
ELF_MAGIC = b"\x7fELF"
PT_INTERP = 3
E_TYPE_NAMES = {1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
E_MACHINE_NAMES = {
    3: "x86",
    8: "MIPS",
    20: "PowerPC",
    21: "PowerPC64",
    40: "ARM",
    62: "x86-64",
    94: "Xtensa",
    183: "AArch64",
    243: "RISC-V",
}
KEY_SUFFIXES = (".pem", ".crt", ".cer", ".key", ".p12", ".pfx", ".der", ".jks")
WEB_SUFFIXES = (".cgi", ".asp", ".php", ".jsp")
WEB_DIR_NAMES = frozenset(("cgi-bin", "www", "htdocs", "web", "webroot", "goform", "api"))
INTERACTIVE_SHELLS = frozenset(("sh", "bash", "ash"))
SHADOW_SCHEMES = ("$1$", "$5$", "$6$", "$y$")
PEM_KINDS = {
    "CERTIFICATE": "CERTIFICATE",
    "PRIVATE KEY": "PRIVATE KEY",
    "RSA PRIVATE KEY": "RSA PRIVATE KEY",
    "EC PRIVATE KEY": "EC PRIVATE KEY",
    "PUBLIC KEY": "PUBLIC KEY",
    "ENCRYPTED PRIVATE KEY": "ENCRYPTED PRIVATE KEY",
}
CONTAINER_NOTES = {
    ".p12": "binary PKCS#12 container; contents not parsed",
    ".pfx": "binary PKCS#12 container; contents not parsed",
    ".jks": "binary Java keystore; contents not parsed",
    ".der": "binary DER; contents not parsed",
}
PEM_LABEL_RE = re.compile(rb"-----BEGIN ([A-Z0-9 ]+)-----")
PRINTABLE_RUN_RE = re.compile(rb"[\x20-\x7e]{6,}")
ROUTE_RE = re.compile(rb"(?i)(/cgi-bin/|/goform/|/api/|\.cgi|\.asp|\.php|\.jsp|/rpc)")
BANNER_RE = re.compile(
    rb"(BusyBox v\d+\.\d+(?:\.\d+)?"
    rb"|OpenSSL \d+\.\d+\.\d+[a-z]?"
    rb"|U-Boot \d{4}\.\d{2}"
    rb"|dropbear_\d+\.\d+"
    rb"|lighttpd/\d+\.\d+"
    rb"|Linux version \d+\.\d+[\x21-\x7e]*"
    rb"|GoAhead \d+)"
)
LIMITATIONS = [
    "Static strings and headers only; nothing was executed",
    "Route candidates are unverified strings; each must be confirmed by reading its handler",
    "A version banner does not prove a build is vulnerable",
    "Files above max-file-bytes were not hashed or scanned; only their ELF headers were read",
    "Symlinks were recorded by target text and never followed; escapes_root is a lexical check",
    "Key kinds come from PEM labels only; binary containers (.p12, .pfx, .jks, .der) were not parsed",
]


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an integer, got %r" % text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _show(text):
    """Escape text for the terminal: firmware-derived names and strings may hold control bytes."""
    return ascii(str(text))[1:-1]


def _bounded(items, cap):
    return {"count": len(items), "truncated": len(items) > cap, "items": items[:cap]}


def _open_nofollow(path):
    """Open a regular file without following a symlink. Returns None for non-regular files."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    fh = os.fdopen(fd, "rb")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            fh.close()
            return None
    except OSError:
        fh.close()
        raise
    return fh


def _reader(fh):
    def read_at(offset, length):
        fh.seek(offset)
        return fh.read(length)

    return read_at


def _bytes_reader(data):
    def read_at(offset, length):
        return data[offset:offset + length]

    return read_at


def parse_elf(read_at, file_size):
    """Parse an ELF header and its program header table with bounds checks.

    read_at(offset, length) returns at most `length` bytes. Returns None when the data
    does not start with the ELF magic. Otherwise returns a dict whose 'malformed' is
    None for a clean parse, or a reason string. Nothing beyond the returned bytes is trusted.
    """
    ident = read_at(0, 16)
    if ident[:4] != ELF_MAGIC:
        return None
    rec = {
        "class": None,
        "endianness": None,
        "e_machine": None,
        "e_type": None,
        "pt_interp": False,
        "malformed": None,
    }
    if len(ident) < 16:
        rec["malformed"] = "truncated e_ident"
        return rec
    ei_class, ei_data = ident[4], ident[5]
    if ei_class not in (1, 2):
        rec["malformed"] = "invalid EI_CLASS %d" % ei_class
        return rec
    rec["class"] = 32 if ei_class == 1 else 64
    if ei_data not in (1, 2):
        rec["malformed"] = "invalid EI_DATA %d" % ei_data
        return rec
    endian = "<" if ei_data == 1 else ">"
    rec["endianness"] = "LE" if ei_data == 1 else "BE"

    header_len = 52 if ei_class == 1 else 64
    head = read_at(0, header_len)
    if len(head) < header_len:
        rec["malformed"] = "truncated ELF header"
        return rec
    fmt = endian + ("HHIIIIIHHHHHH" if ei_class == 1 else "HHIQQQIHHHHHH")
    fields = struct.unpack_from(fmt, head, 16)
    e_type, e_machine = fields[0], fields[1]
    e_phoff, e_phentsize, e_phnum = fields[4], fields[8], fields[9]
    rec["e_type"] = E_TYPE_NAMES.get(e_type, "unknown(%d)" % e_type)
    rec["e_machine"] = E_MACHINE_NAMES.get(e_machine, "unknown(%d)" % e_machine)
    if e_phnum == 0:
        return rec

    min_entsize = 32 if ei_class == 1 else 56
    if e_phentsize < min_entsize:
        rec["malformed"] = "program header entry size %d is below %d" % (e_phentsize, min_entsize)
        return rec
    table_len = e_phnum * e_phentsize
    if table_len > MAX_PHDR_TABLE_BYTES:
        rec["malformed"] = "program header table of %d bytes exceeds the read limit" % table_len
        return rec
    if e_phoff == 0 or e_phoff + table_len > file_size:
        rec["malformed"] = "program header table lies outside the file"
        return rec
    table = read_at(e_phoff, table_len)
    if len(table) < table_len:
        rec["malformed"] = "truncated program header table"
        return rec
    for index in range(e_phnum):
        (p_type,) = struct.unpack_from(endian + "I", table, index * e_phentsize)
        if p_type == PT_INTERP:
            rec["pt_interp"] = True
            break
    return rec


def parse_passwd(data):
    """Return (entries, malformed_lines). Password fields are inspected, never returned."""
    entries = []
    malformed = 0
    for raw in data.decode("utf-8", "replace").splitlines():
        line = raw.strip()
        if not line or line[0] in "#+-":
            continue
        fields = line.split(":")
        if len(fields) < 4:
            malformed += 1
            continue
        name, password = fields[0], fields[1]
        try:
            uid, gid = int(fields[2]), int(fields[3])
        except ValueError:
            malformed += 1
            continue
        shell = fields[6] if len(fields) > 6 else ""
        flags = []
        if uid == 0 and name != "root":
            flags.append("uid0_nonroot")
        if password == "":
            flags.append("empty_passwd_field")
        if posixpath.basename(shell) in INTERACTIVE_SHELLS:
            flags.append("interactive_shell")
        entries.append({"name": name, "uid": uid, "gid": gid, "shell": shell, "flags": flags})
    return entries, malformed


def parse_shadow(data):
    """Return ({name: info}, malformed_lines). Hash text is classified and never returned."""
    accounts = {}
    malformed = 0
    for raw in data.decode("utf-8", "replace").splitlines():
        line = raw.strip()
        if not line or line[0] == "#":
            continue
        fields = line.split(":")
        if len(fields) < 2 or not fields[0]:
            malformed += 1
            continue
        name, field = fields[0], fields[1]
        stripped = field.lstrip("!")
        has_hash = stripped not in ("", "*")
        scheme = None
        if has_hash:
            scheme = next(
                (prefix for prefix in SHADOW_SCHEMES if stripped.startswith(prefix)),
                "traditional-or-other",
            )
        accounts[name] = {
            "has_hash": has_hash,
            "scheme": scheme,
            "locked": field.startswith("!") or field == "*",
            "empty": field == "",
        }
    return accounts, malformed


def _is_init_script(rel):
    if rel == "etc/inittab":
        return True
    parts = rel.split("/")
    if len(parts) < 3 or parts[0] != "etc":
        return False
    return parts[1] in ("init.d", "init") or fnmatch.fnmatchcase(parts[1], "rc*.d")


def _escapes_root(rel, target):
    """Lexical check only: does a relative target climb out of ROOT from the link's directory?"""
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
    return joined == ".." or joined.startswith("../")


def _looks_text(data):
    return bool(data) and b"\x00" not in data[:TEXT_SNIFF_BYTES]


class Survey:
    """Walks ROOT once and collects every section. All reads are read-only."""

    def __init__(self, root, max_file_bytes, max_items):
        self.root = os.path.abspath(root)
        self.max_file_bytes = max_file_bytes
        self.max_items = max_items
        self.counts = {
            "files": 0,
            "dirs": 0,
            "symlinks": 0,
            "skipped_large": 0,
            "other_special": 0,
            "unreadable": 0,
        }
        self.elf = []
        self.symlinks = []
        self.init_scripts = []
        self.keys = []
        self.web_dirs = []
        self.web_files = []
        self.routes = []
        self.banners = {}
        self.errors = []
        self.account_files = {}
        self.account_state = {"etc/passwd": "absent", "etc/shadow": "absent"}

    def _rel(self, full):
        return os.path.relpath(full, self.root).replace(os.sep, "/")

    def _error(self, rel, exc):
        self.counts["unreadable"] += 1
        self.errors.append({"path": rel, "error": type(exc).__name__})

    def _walk_error(self, exc):
        self._error(self._rel(exc.filename or self.root), exc)

    def scan(self):
        for dirpath, dirnames, filenames in os.walk(
            self.root, followlinks=False, onerror=self._walk_error
        ):
            dirnames.sort()
            filenames.sort()
            for dname in dirnames:
                full = os.path.join(dirpath, dname)
                rel = self._rel(full)
                if os.path.islink(full):
                    self._add_symlink(full, rel)
                    continue
                self.counts["dirs"] += 1
                if dname in WEB_DIR_NAMES:
                    self.web_dirs.append(rel)
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = self._rel(full)
                try:
                    st = os.lstat(full)
                except OSError as exc:
                    self._error(rel, exc)
                    continue
                mode = st.st_mode
                if stat.S_ISLNK(mode):
                    self._add_symlink(full, rel)
                    self._name_checks(rel, fname, "symlink")
                elif stat.S_ISREG(mode):
                    try:
                        self._regular_file(rel, full, fname, st.st_size)
                    except Exception as exc:  # one bad file must not stop the survey
                        self._error(rel, exc)
                else:
                    self.counts["other_special"] += 1

    def _add_symlink(self, full, rel):
        self.counts["symlinks"] += 1
        try:
            target = os.readlink(full)
        except OSError as exc:
            self._error(rel, exc)
            target = None
        absolute = target is not None and target.startswith("/")
        escapes = absolute or (target is not None and _escapes_root(rel, target))
        self.symlinks.append({
            "path": rel,
            "target": target,
            "absolute": absolute,
            "escapes_root": escapes,
        })
        if rel in self.account_state:
            self.account_state[rel] = "symlink-not-followed"

    def _name_checks(self, rel, name, kind):
        if _is_init_script(rel):
            self.init_scripts.append({"path": rel, "type": kind})
        if name.lower().endswith(WEB_SUFFIXES):
            self.web_files.append({"path": rel, "type": kind})

    def _regular_file(self, rel, full, name, size):
        self.counts["files"] += 1
        self._name_checks(rel, name, "file")
        key_name = name.lower().endswith(KEY_SUFFIXES)
        if size > self.max_file_bytes:
            self._large_file(rel, full, name, size, key_name)
            return
        fh = _open_nofollow(full)
        if fh is None:
            self._error(rel, OSError("not a regular file when opened"))
            return
        with fh:
            data = fh.read(self.max_file_bytes + 1)
        if len(data) > self.max_file_bytes:
            self._large_file(rel, full, name, size, key_name)
            return
        self._scan_content(rel, name, data, size, key_name)

    def _large_file(self, rel, full, name, size, key_name):
        self.counts["skipped_large"] += 1
        if rel in self.account_state:
            self.account_state[rel] = "skipped-large"
        fh = _open_nofollow(full)
        if fh is not None:
            with fh:
                if fh.read(4) == ELF_MAGIC:
                    elf = parse_elf(_reader(fh), size)
                    if elf is not None:
                        self._add_elf(rel, size, None, elf)
        if key_name:
            self.keys.append({
                "path": rel,
                "size": size,
                "sha256": None,
                "kind": "other",
                "private_key_material": None,
                "pem_labels": [],
                "scanned": False,
                "note": "not scanned: exceeds max-file-bytes",
            })

    def _scan_content(self, rel, name, data, size, key_name):
        sha256 = hashlib.sha256(data).hexdigest()
        is_elf = data[:4] == ELF_MAGIC
        if is_elf:
            elf = parse_elf(_bytes_reader(data), len(data))
            if elf is not None:
                self._add_elf(rel, size, sha256, elf)
        head = data[:PEM_SCAN_BYTES]
        if key_name or b"-----BEGIN" in head:
            self._add_key(rel, name, head, size, sha256)
        if is_elf or _looks_text(data):
            self._scan_routes(rel, data)
        self._scan_banners(rel, data)
        if rel in self.account_state:
            self.account_files[rel] = data
            self.account_state[rel] = "parsed"

    def _add_elf(self, rel, size, sha256, elf):
        self.elf.append(dict({"path": rel, "size": size, "sha256": sha256}, **elf))

    def _add_key(self, rel, name, head, size, sha256):
        labels = []
        for match in PEM_LABEL_RE.finditer(head):
            label = match.group(1).decode("ascii")
            if label not in labels:
                labels.append(label)
        if labels:
            kind = PEM_KINDS.get(labels[0], "other")
            private = any(label.endswith("PRIVATE KEY") for label in labels)
            note = None
        else:
            kind = "other"
            private = None
            suffix = posixpath.splitext(name.lower())[1]
            note = CONTAINER_NOTES.get(suffix, "no PEM label found; contents not classified")
        self.keys.append({
            "path": rel,
            "size": size,
            "sha256": sha256,
            "kind": kind,
            "private_key_material": private,
            "pem_labels": labels[:10],
            "scanned": True,
            "note": note,
        })

    def _scan_routes(self, rel, data):
        for match in PRINTABLE_RUN_RE.finditer(data):
            run = match.group(0)
            hit = ROUTE_RE.search(run)
            if hit is None:
                continue
            start = max(0, hit.start() - 80)
            end = min(len(run), hit.end() + 160)
            text = run[start:end].decode("ascii")
            if start > 0:
                text = "..." + text
            if end < len(run):
                text = text + "..."
            self.routes.append({
                "file": rel,
                "string": text,
                "offset": match.start() + hit.start(),
            })

    def _scan_banners(self, rel, data):
        for match in BANNER_RE.finditer(data):
            text = match.group(1)[:120].decode("ascii")
            key = (rel, text)
            self.banners[key] = self.banners.get(key, 0) + 1

    def _accounts(self):
        cap = self.max_items
        passwd_entries, passwd_bad = ([], 0)
        if "etc/passwd" in self.account_files:
            passwd_entries, passwd_bad = parse_passwd(self.account_files["etc/passwd"])
        shadow_map, shadow_bad = ({}, 0)
        if "etc/shadow" in self.account_files:
            shadow_map, shadow_bad = parse_shadow(self.account_files["etc/shadow"])

        def shadow_view(info):
            if info is None:
                return None
            return {"has_hash": info["has_hash"], "scheme": info["scheme"], "locked": info["locked"]}

        accounts = []
        seen = set()
        for entry in passwd_entries:
            seen.add(entry["name"])
            info = shadow_map.get(entry["name"])
            flags = list(entry["flags"])
            if info is not None and info["empty"]:
                flags.append("empty_shadow_hash")
            accounts.append({
                "name": entry["name"],
                "uid": entry["uid"],
                "gid": entry["gid"],
                "shell": entry["shell"],
                "flags": flags,
                "shadow": shadow_view(info),
            })
        shadow_only = []
        for name, info in shadow_map.items():
            if name in seen:
                continue
            shadow_only.append({
                "name": name,
                "uid": None,
                "gid": None,
                "shell": None,
                "flags": ["empty_shadow_hash"] if info["empty"] else [],
                "shadow": shadow_view(info),
            })

        flag_counts = {}
        for record in accounts + shadow_only:
            for flag in record["flags"]:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
        return {
            "passwd_state": self.account_state["etc/passwd"],
            "shadow_state": self.account_state["etc/shadow"],
            "passwd_malformed_lines": passwd_bad,
            "shadow_malformed_lines": shadow_bad,
            "flag_counts": dict(sorted(flag_counts.items())),
            "flagged": sum(1 for record in accounts + shadow_only if record["flags"]),
            "accounts": _bounded(accounts, cap),
            "shadow_only": _bounded(shadow_only, cap),
        }

    def document(self):
        cap = self.max_items
        self.elf.sort(key=lambda item: item["path"])
        self.symlinks.sort(key=lambda item: item["path"])
        self.init_scripts.sort(key=lambda item: item["path"])
        self.keys.sort(key=lambda item: item["path"])
        self.web_files.sort(key=lambda item: item["path"])
        self.routes.sort(key=lambda item: (item["file"], item["offset"]))
        self.errors.sort(key=lambda item: item["path"])
        banners = [
            {"file": rel, "match": text, "count": count}
            for (rel, text), count in sorted(self.banners.items())
        ]
        counts = dict(self.counts)
        counts["elf"] = len(self.elf)
        return {
            "schema": 1,
            "tool": "firmware_survey.py",
            "generated_utc": _utc_now(),
            "root": self.root,
            "parameters": {"max_file_bytes": self.max_file_bytes, "max_items": cap},
            "counts": counts,
            "elf": _bounded(self.elf, cap),
            "symlinks": _bounded(self.symlinks, cap),
            "init_scripts": _bounded(self.init_scripts, cap),
            "accounts": self._accounts(),
            "keys_and_certs": _bounded(self.keys, cap),
            "web": {
                "dirs": _bounded(sorted(self.web_dirs), cap),
                "files": _bounded(self.web_files, cap),
            },
            "route_candidates": _bounded(self.routes, cap),
            "version_banners": _bounded(banners, cap),
            "errors": _bounded(self.errors, cap),
            "limitations": list(LIMITATIONS),
        }


def _arch_summary(elf_items):
    groups = {}
    for item in elf_items:
        if item.get("malformed"):
            key = "malformed"
        else:
            key = "%s %s %s-bit %s" % (
                item["e_machine"], item["endianness"], item["class"], item["e_type"]
            )
        groups[key] = groups.get(key, 0) + 1
    return ", ".join("%s x%d" % (key, groups[key]) for key in sorted(groups)) or "none"


def summary_lines(survey, doc, out_path):
    counts = doc["counts"]
    accounts = doc["accounts"]
    keys = survey.keys
    private = sum(1 for item in keys if item["private_key_material"] is True)
    lines = [
        "firmware_survey: %s" % _show(doc["root"]),
        "  files=%d dirs=%d symlinks=%d elf=%d skipped_large=%d unreadable=%d" % (
            counts["files"], counts["dirs"], counts["symlinks"], counts["elf"],
            counts["skipped_large"], counts["unreadable"],
        ),
        "  elf: %s" % _show(_arch_summary(survey.elf)),
        "  dynamically linked (PT_INTERP): %d" % sum(1 for item in survey.elf if item["pt_interp"]),
        "  init scripts: %d   web dirs: %d   web files: %d" % (
            doc["init_scripts"]["count"], doc["web"]["dirs"]["count"], doc["web"]["files"]["count"],
        ),
        "  keys/certs: %d (private key material: %d)" % (len(keys), private),
        "  accounts: %d (flagged %d) %s" % (
            accounts["accounts"]["count"], accounts["flagged"],
            _show(json.dumps(accounts["flag_counts"], sort_keys=True)),
        ),
        "  route candidates: %d%s" % (
            doc["route_candidates"]["count"],
            " (truncated)" if doc["route_candidates"]["truncated"] else "",
        ),
    ]
    for item in doc["route_candidates"]["items"][:SUMMARY_SAMPLE]:
        lines.append("    %s @%d: %s" % (
            _show(item["file"]), item["offset"], _show(item["string"][:100])))
    lines.append("  version banners: %d" % doc["version_banners"]["count"])
    for item in doc["version_banners"]["items"][:SUMMARY_SAMPLE]:
        lines.append("    %s: %s (x%d)" % (_show(item["file"]), _show(item["match"]), item["count"]))
    lines.append("  output: %s" % _show(out_path))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Static, read-only survey of an extracted root filesystem."
    )
    parser.add_argument("root", help="extracted root filesystem directory")
    parser.add_argument("--out", required=True,
                        help="output directory; must not exist (survey.json is written here)")
    parser.add_argument("--max-file-bytes", type=_positive_int, default=DEFAULT_MAX_FILE_BYTES,
                        help="files above this size are not hashed or scanned (default 32 MiB)")
    parser.add_argument("--max-items", type=_positive_int, default=DEFAULT_MAX_ITEMS,
                        help="cap for every list in the output (default 500)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.root):
        sys.stderr.write("ERROR: ROOT is not a directory: %s\n" % _show(args.root))
        return 2
    out_dir = os.path.abspath(args.out)
    if os.path.lexists(out_dir):
        sys.stderr.write("ERROR: output directory already exists, refusing to write into it: %s\n"
                         % _show(out_dir))
        return 2

    survey = Survey(args.root, args.max_file_bytes, args.max_items)
    try:
        survey.scan()
        doc = survey.document()
    except Exception as exc:  # analysis failure, reported with exit code 1
        sys.stderr.write("ERROR: survey failed: %s: %s\n" % (type(exc).__name__, _show(exc)))
        return 1

    out_path = os.path.join(out_dir, "survey.json")
    try:
        os.makedirs(out_dir)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
    except FileExistsError:
        sys.stderr.write("ERROR: output directory appeared while running, refusing to write: %s\n"
                         % _show(out_dir))
        return 2
    except OSError as exc:
        sys.stderr.write("ERROR: cannot write %s: %s\n" % (_show(out_path), exc.strerror or exc))
        return 1

    sys.stdout.write("\n".join(summary_lines(survey, doc, out_path)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
