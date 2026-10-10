#!/usr/bin/env python3
"""Download the pinned known-answer fixtures listed in manifest.json.

Usage:
    fetch_fixtures.py [--only ID ...] [--dest DIR] [--manifest PATH] [--timeout SECONDS]

Each fixture is streamed over HTTPS into a temporary file in the destination directory.
Its size and SHA-256 are checked against the pin before the file is renamed into place,
so a partial or substituted download never appears under its real name. A file that is
already present and matches is left alone. A file that is present and does not match is
refused and never overwritten: move it aside, then re-run.

The destination defaults to _reference/ beside this script, which is gitignored. Nothing
downloaded is executed.

Exit codes: 0 every requested fixture is present and verified, 1 a fixture was refused or
failed, 2 usage or manifest error.
"""
import argparse
import hashlib
import http.client
import json
import os
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "manifest.json")
DEFAULT_DEST = os.path.join(HERE, "_reference")
CHUNK = 1024 * 1024
REQUIRED_KEYS = ("id", "filename", "url", "sha256", "size")


def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        fixtures = json.load(f).get("fixtures") or []
    seen = set()
    for fx in fixtures:
        missing = [k for k in REQUIRED_KEYS if k not in fx]
        if missing:
            raise ValueError("fixture %r lacks %s" % (fx.get("id"), ", ".join(missing)))
        if fx["id"] in seen:
            raise ValueError("duplicate fixture id %r" % fx["id"])
        seen.add(fx["id"])
        if not fx["url"].startswith("https://"):
            raise ValueError("fixture %r must be fetched over https" % fx["id"])
        if fx["filename"] in ("", ".", "..") or fx["filename"] != os.path.basename(fx["filename"]):
            raise ValueError("fixture %r filename must be a bare name" % fx["id"])
        if len(fx["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in fx["sha256"]):
            raise ValueError("fixture %r sha256 must be 64 lowercase hex digits" % fx["id"])
        if not isinstance(fx["size"], int) or fx["size"] <= 0:
            raise ValueError("fixture %r size must be a positive integer" % fx["id"])
    return fixtures


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_state(path, fx):
    """'absent', 'verified', or 'mismatch'. A symlink or non-file at the path is a mismatch."""
    if not os.path.lexists(path):
        return "absent"
    if os.path.islink(path) or not os.path.isfile(path):
        return "mismatch"
    if os.path.getsize(path) == fx["size"] and sha256_of(path) == fx["sha256"]:
        return "verified"
    return "mismatch"


def fetch(fx, dest_dir, timeout=60, opener=None):
    """Download one fixture and rename it into place only after it verifies."""
    opener = opener or urllib.request.urlopen
    final = os.path.join(dest_dir, fx["filename"])
    fd, partial = tempfile.mkstemp(prefix=".partial-", dir=dest_dir)
    digest = hashlib.sha256()
    received = 0
    try:
        with os.fdopen(fd, "wb") as out, opener(fx["url"], timeout=timeout) as resp:
            for chunk in iter(lambda: resp.read(CHUNK), b""):
                received += len(chunk)
                if received > fx["size"]:
                    raise ValueError("more than the pinned %d bytes" % fx["size"])
                digest.update(chunk)
                out.write(chunk)
        if received != fx["size"]:
            raise ValueError("received %d bytes, pinned %d" % (received, fx["size"]))
        if digest.hexdigest() != fx["sha256"]:
            raise ValueError("sha256 %s does not match the pin" % digest.hexdigest())
        os.chmod(partial, 0o644)
        os.replace(partial, final)
    except BaseException:
        if os.path.lexists(partial):
            os.unlink(partial)
        raise
    return final


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download and verify the pinned known-answer fixtures.")
    ap.add_argument("--only", action="append", metavar="ID",
                    help="fetch only this fixture id (repeatable)")
    ap.add_argument("--dest", default=DEFAULT_DEST,
                    help="download directory (default: _reference/ beside this script)")
    ap.add_argument("--manifest", default=MANIFEST, help="pin list to read (default: manifest.json)")
    ap.add_argument("--timeout", type=float, default=60, help="socket timeout in seconds")
    args = ap.parse_args(argv)

    try:
        fixtures = load_manifest(args.manifest)
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        sys.stderr.write("ERROR: manifest: %s\n" % exc)
        return 2
    if args.only:
        wanted = set(args.only)
        unknown = sorted(wanted - {fx["id"] for fx in fixtures})
        if unknown:
            sys.stderr.write("ERROR: unknown fixture id(s): %s\n" % ", ".join(unknown))
            return 2
        fixtures = [fx for fx in fixtures if fx["id"] in wanted]

    os.makedirs(args.dest, exist_ok=True)
    status = 0
    for fx in fixtures:
        path = os.path.join(args.dest, fx["filename"])
        state = existing_state(path, fx)
        if state == "verified":
            print("present  %s  %s" % (fx["id"], path))
            continue
        if state == "mismatch":
            print("REFUSED  %s  %s exists but does not match the pin; move it aside and re-run"
                  % (fx["id"], path))
            status = 1
            continue
        try:
            fetch(fx, args.dest, args.timeout)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            print("FAILED   %s  %s" % (fx["id"], exc))
            status = 1
            continue
        print("fetched  %s  %s (size and sha256 verified)" % (fx["id"], path))
    return status


if __name__ == "__main__":
    sys.exit(main())
