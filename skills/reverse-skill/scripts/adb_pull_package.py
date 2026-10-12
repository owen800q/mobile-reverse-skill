#!/usr/bin/env python3
"""Pull every APK of an installed package from a device, digest each one, and record coverage.

Usage:
    adb_pull_package.py PACKAGE --out DIR --scope "TEXT" [--serial SERIAL] [--adb PATH]

--scope is required. It is one line stating the device and app scope the analyst has
agreed, for example "user's own Pixel 7, com.example.aa, installed copy only". It is
written into the manifest, and the tool refuses to run without it. Possessing a device
or an app does not by itself establish that the pull is in scope.

The tool asks the device for the APK paths of PACKAGE with `pm path`. It pulls the APK
files only: base.apk, split_*.apk and any other APK the package lists. It never pulls
app data directories, shared storage or other packages. Every command runs as an
argument list with no shell, and each device path must be an absolute .apk path whose
file name is simple, so a hostile package listing cannot inject anything.

File roles come from the names the device reports. base.apk is "base" and split_*.apk
is "split". Any other name is "unknown" and is not guessed. Each pulled file is written
into DIR under an index prefix, so two files with the same name cannot overwrite each
other, and is digested with SHA-256. A failed pull is recorded and marks the run
partial. A partial package is still a result, but it must not be described as the
whole app.

DIR must not exist. It is created mode 0700 and manifest.json mode 0600.
Output: manifest.json in DIR, plus a summary on stdout. Exit codes: 0 complete,
1 partial or nothing pulled, 2 usage or input error (including a missing --scope).
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
SAFE_APK_RE = re.compile(r"^[A-Za-z0-9._-]+\.apk$")
TIMEOUT_SECONDS = 120

LIMITATIONS = [
    "Only the APK files the device lists for the package are pulled; the app's private data is not",
    "The APKs are the installed copies; a store copy or an update may differ and is not compared",
    "Digests show the bytes that were pulled, not that the install was unmodified",
    "A partial result lists its failures and must be described as partial",
]


class InputError(Exception):
    """Bad arguments or an unusable device response. Exit code 2."""


def adb_command(adb: str, serial, *args) -> list:
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    return cmd + list(args)


def run_adb(adb: str, serial, *args):
    return subprocess.run(adb_command(adb, serial, *args), capture_output=True, text=True,
                          timeout=TIMEOUT_SECONDS)


def parse_pm_paths(output: str):
    """Return the device paths from `pm path` output, in the order the device gave them."""
    paths = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            paths.append(line[len("package:"):])
    return paths


def role_for(name: str) -> str:
    if name == "base.apk":
        return "base"
    if name.startswith("split_"):
        return "split"
    return "unknown"


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def adb_digest(adb: str):
    resolved = shutil.which(adb) or adb
    return sha256_of(resolved) if os.path.isfile(resolved) else None


def pull_package(package: str, out: str, scope: str, serial, adb: str) -> dict:
    if not PACKAGE_RE.match(package):
        raise InputError("not a valid package name: %r" % package)
    if not scope.strip():
        raise InputError("--scope must state the agreed device and app scope")
    if os.path.lexists(out):
        raise InputError("output directory already exists: %s" % out)
    if shutil.which(adb) is None and not os.path.isfile(adb):
        raise InputError("adb not found: %s" % adb)

    listing = run_adb(adb, serial, "shell", "pm", "path", package)
    if listing.returncode != 0:
        raise InputError("pm path failed: %s" % (listing.stderr.strip() or listing.stdout.strip()))
    device_paths = parse_pm_paths(listing.stdout)

    os.makedirs(out, mode=0o700)
    os.chmod(out, 0o700)
    files, rejected, failures = [], [], []
    for index, device_path in enumerate(device_paths, 1):
        name = device_path.rsplit("/", 1)[-1]
        if not device_path.startswith("/") or not device_path.endswith(".apk") or not SAFE_APK_RE.match(name):
            rejected.append({"device_path": device_path, "reason": "not an absolute .apk path with a simple name"})
            continue
        host_name = "%02d_%s" % (index, name)
        dest = os.path.join(out, host_name)
        entry = {"index": index, "device_path": device_path, "host_name": host_name,
                 "role": role_for(name), "status": "pulled", "sha256": None, "size": None}
        pulled = run_adb(adb, serial, "pull", device_path, dest)
        if pulled.returncode != 0 or not os.path.isfile(dest):
            entry["status"] = "failed"
            entry["error"] = (pulled.stderr or pulled.stdout).strip()[:300]
            failures.append({"device_path": device_path, "error": entry["error"]})
        else:
            entry["size"] = os.path.getsize(dest)
            entry["sha256"] = sha256_of(dest)
            os.chmod(dest, 0o600)
        files.append(entry)

    complete = bool(files) and not failures and not rejected
    manifest = {
        "package": package,
        "serial": serial or "default",
        "scope": scope.strip(),
        "pulled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "adb": {"path": adb, "sha256": adb_digest(adb)},
        "pm_path_count": len(device_paths),
        "files": files,
        "rejected": rejected,
        "failures": failures,
        "coverage": "complete" if complete else "partial",
        "limitations": list(LIMITATIONS),
    }
    manifest_path = os.path.join(out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(manifest_path, 0o600)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pull every APK of a package from a device, with digests and coverage.")
    ap.add_argument("package", help="package name, e.g. com.example.aa")
    ap.add_argument("--out", required=True, help="new directory for the pulled APKs (must not exist)")
    ap.add_argument("--scope", required=True, help="one line stating the agreed device and app scope")
    ap.add_argument("--serial", default=None, help="device serial, when more than one device is attached")
    ap.add_argument("--adb", default=os.environ.get("ADB", "adb"), help="adb executable (default: $ADB or adb)")
    args = ap.parse_args(argv)
    try:
        manifest = pull_package(args.package, args.out, args.scope, args.serial, args.adb)
    except (InputError, OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    summary = {"package": manifest["package"], "coverage": manifest["coverage"],
               "pulled": sum(1 for f in manifest["files"] if f["status"] == "pulled"),
               "failed": len(manifest["failures"]), "rejected": len(manifest["rejected"]),
               "manifest": os.path.join(args.out, "manifest.json")}
    print(json.dumps(summary, indent=2))
    return 0 if manifest["coverage"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
