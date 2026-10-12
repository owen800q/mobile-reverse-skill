#!/usr/bin/env python3
"""Pull every APK of an installed package from a device, digest each one, and record coverage.

Usage:
    adb_pull_package.py PACKAGE --out DIR --scope "TEXT" [--serial SERIAL] [--adb PATH] [--log FILE]

--scope is required and must not be empty. It is one line stating the device and app
scope the analyst has agreed, for example "user's own Pixel 7, com.example.aa, installed
copy only". The tool checks only that it is not empty; it does not check what it says.
It is written into the manifest. Possessing a device or an app does not by itself
establish that the pull is in scope.

The tool asks the device for the APK paths of PACKAGE with `pm path`, and it trusts that
listing for which APKs belong to the package. It pulls a listed path only when the path
text passes all three checks below. Any other listed path goes to "rejected" with a
reason and is not pulled.
  - The path has no ".." path component (the check splits the path on "/").
  - posixpath.normpath(path) starts with one of ALLOWED_PREFIXES: /data/app/, /system/,
    /system_ext/, /product/, /vendor/ or /apex/.
  - The path ends in .apk and its file name is simple (letters, digits, ".", "_", "-").
So the tool pulls .apk files under those install and system directories. It does not
pull app data directories such as /data/data/PACKAGE, or shared storage such as /sdcard,
because those paths are outside the allowed prefixes. Inside the allowed directories the
device listing decides which APKs are pulled. The checks read the path text only; the tool
does not check whether a listed path is a symbolic link on the device. Every command runs
as an argument list with no shell.

File roles come from the names the device reports. base.apk is "base" and split_*.apk
is "split". Any other name is "unknown" and is not guessed. Each pulled file is written
into DIR under an index prefix, so two files with the same name cannot overwrite each
other, and is digested with SHA-256. A pull that returns an error is recorded as a failed
file and marks the run partial. A pull that runs longer than TIMEOUT_SECONDS (120 seconds)
is recorded as a failed file with the error "timeout"; its partial file is removed, the
other pulls continue, and the run is partial. A timeout on `pm path` is an input error:
nothing is pulled and DIR is not created. A partial package is still a result, but it
must not be described as the whole app.

DIR must not exist. It is created mode 0700 and manifest.json mode 0600.
Output: manifest.json in DIR, plus a summary on stdout, once the pull loop finishes. An
adb command that raises an OSError or a ValueError (for example, output that is not
UTF-8) ends the run with no manifest.json; files already pulled stay in DIR. Exit codes:
0 complete, 1 partial or nothing pulled, 2 usage, input or adb error (including a missing
--scope).

Trace log: every call to pull_package, and every adb command that run_adb runs, appends
one JSON line to --log. The default is adb_pull_package.trace.jsonl in the directory that
holds DIR, created mode 0600. Each line has a UTC timestamp, the tool and function, and the
outcome. A pull_package line also holds the package, the serial, the scope length and
SHA-256, and the status and exit code. A line for a call that returned also holds the
SHA-256 of the adb executable and each file's host name, status and SHA-256; a line for a
call that raised an exception holds the error text instead, which can repeat a path as
typed on the command line. A run_adb line holds the purpose (pm path or pull), the device
path and host name of a pull, and the return code, the timeout, or the error text when
the command raised an exception. The scope text is not logged. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time

PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
SAFE_APK_RE = re.compile(r"^[A-Za-z0-9._-]+\.apk$")
ALLOWED_PREFIXES = ("/data/app/", "/system/", "/system_ext/", "/product/", "/vendor/", "/apex/")
TIMEOUT_SECONDS = 120
TOOL = "adb_pull_package.py"
TRACE_NAME = "adb_pull_package.trace.jsonl"

LIMITATIONS = [
    "Only .apk files that the device lists for the package, under an allowed install or system directory, are pulled; app data directories are not",
    "The APKs are the installed copies; a store copy or an update may differ and is not compared",
    "Digests show the bytes that were pulled, not that the install was unmodified",
    "A partial result lists its failures and must be described as partial",
]


class InputError(Exception):
    """Bad arguments or an unusable device response. Exit code 2."""


class Trace:
    """Append-only JSON-lines log for this tool's calls. The file is mode 0600."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)

    def rel(self, path: str) -> str:
        """Path relative to the log's directory, so the out field holds no absolute path."""
        return os.path.relpath(os.path.abspath(path), os.path.dirname(self.path))

    def write(self, function: str, **fields) -> None:
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": TOOL,
                  "function": function}
        record.update(fields)
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        os.chmod(self.path, 0o600)


def default_trace_path(out: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(out)), TRACE_NAME)


def describe(exc: Exception) -> str:
    """Error text for the log: an OSError's strerror, so no absolute path is logged."""
    return exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)


def adb_command(adb: str, serial, *args) -> list:
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    return cmd + list(args)


def run_adb(adb: str, serial, *args, trace: Trace, purpose: str, device_path=None, host_name=None):
    """Run one adb command with the timeout, and log the call. A timeout is logged, then re-raised."""
    fields = {"purpose": purpose, "serial": serial or "default", "timeout_seconds": TIMEOUT_SECONDS,
              "device_path": device_path, "host_name": host_name}
    try:
        done = subprocess.run(adb_command(adb, serial, *args), capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        trace.write("run_adb", status="timeout", returncode=None, **fields)
        raise
    except Exception as exc:  # a missing interpreter, or output that is not UTF-8
        trace.write("run_adb", status="error", returncode=None, error=describe(exc), **fields)
        raise
    trace.write("run_adb", status="completed", returncode=done.returncode, **fields)
    return done


def parse_pm_paths(output: str):
    """Return the device paths from `pm path` output, in the order the device gave them."""
    paths = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            paths.append(line[len("package:"):])
    return paths


def device_path_problem(device_path: str):
    """Return why a device path from `pm path` must not be pulled, or None when it may be pulled."""
    if ".." in device_path.split("/"):
        return "path has a '..' component"
    normalized = posixpath.normpath(device_path)
    if not normalized.startswith(ALLOWED_PREFIXES):
        return "path is outside the allowed install and system directories"
    if not normalized.endswith(".apk"):
        return "path does not end in .apk"
    if not SAFE_APK_RE.match(normalized.rsplit("/", 1)[-1]):
        return "file name is not simple"
    return None


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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def adb_digest(adb: str):
    resolved = shutil.which(adb) or adb
    return sha256_of(resolved) if os.path.isfile(resolved) else None


def remove_partial(path: str) -> None:
    if os.path.lexists(path):
        os.remove(path)


def exit_code(manifest: dict) -> int:
    return 0 if manifest["coverage"] == "complete" else 1


def pull_package(package: str, out: str, scope: str, serial, adb: str, log_path=None) -> dict:
    """Pull the package's APKs. Logs one pull_package line for the call, with its outcome."""
    trace = Trace(log_path or default_trace_path(out))
    stated = scope.strip()
    facts = {"package": package, "out": trace.rel(out), "serial": serial or "default",
             "timeout_seconds": TIMEOUT_SECONDS, "scope_length": len(stated),
             "scope_sha256": sha256_text(stated)}
    try:
        manifest = _pull_package(package, out, stated, serial, adb, trace)
    except Exception as exc:
        status = "input_error" if isinstance(exc, (InputError, OSError, subprocess.SubprocessError, ValueError)) else "error"
        trace.write("pull_package", status=status, exit_code=2, error=describe(exc), **facts)
        raise
    trace.write("pull_package", status=manifest["coverage"], exit_code=exit_code(manifest),
                adb_sha256=manifest["adb"]["sha256"], pm_path_count=manifest["pm_path_count"],
                files=[{"host_name": f["host_name"], "status": f["status"], "sha256": f["sha256"],
                        "size": f["size"]} for f in manifest["files"]],
                failures=len(manifest["failures"]), rejected=len(manifest["rejected"]), **facts)
    return manifest


def _pull_package(package: str, out: str, scope: str, serial, adb: str, trace: Trace) -> dict:
    if not PACKAGE_RE.match(package):
        raise InputError("not a valid package name: %r" % package)
    if not scope:
        raise InputError("--scope must state the agreed device and app scope")
    if os.path.lexists(out):
        raise InputError("output directory already exists: %s" % out)
    if shutil.which(adb) is None and not os.path.isfile(adb):
        raise InputError("adb not found: %s" % adb)
    adb_sha256 = adb_digest(adb)

    try:
        listing = run_adb(adb, serial, "shell", "pm", "path", package, trace=trace, purpose="pm path")
    except subprocess.TimeoutExpired:
        raise InputError("pm path timed out after %d seconds" % TIMEOUT_SECONDS)
    if listing.returncode != 0:
        raise InputError("pm path failed: %s" % (listing.stderr.strip() or listing.stdout.strip()))
    device_paths = parse_pm_paths(listing.stdout)

    os.makedirs(out, mode=0o700)
    os.chmod(out, 0o700)
    files, rejected, failures = [], [], []
    for index, device_path in enumerate(device_paths, 1):
        problem = device_path_problem(device_path)
        if problem:
            rejected.append({"device_path": device_path, "reason": problem})
            continue
        source = posixpath.normpath(device_path)
        name = source.rsplit("/", 1)[-1]
        host_name = "%02d_%s" % (index, name)
        dest = os.path.join(out, host_name)
        entry = {"index": index, "device_path": device_path, "host_name": host_name,
                 "role": role_for(name), "status": "pulled", "sha256": None, "size": None}
        try:
            pulled = run_adb(adb, serial, "pull", source, dest, trace=trace, purpose="pull",
                             device_path=device_path, host_name=host_name)
        except subprocess.TimeoutExpired:
            remove_partial(dest)
            entry["status"] = "failed"
            entry["error"] = "timeout"
            failures.append({"device_path": device_path, "error": "timeout"})
        else:
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
        "scope": scope,
        "pulled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "adb": {"path": adb, "sha256": adb_sha256},
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
    ap.add_argument("--log", default=None, help="append-only trace log (default: %s beside --out)" % TRACE_NAME)
    args = ap.parse_args(argv)
    try:
        manifest = pull_package(args.package, args.out, args.scope, args.serial, args.adb, args.log)
    except (InputError, OSError, subprocess.SubprocessError, ValueError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    summary = {"package": manifest["package"], "coverage": manifest["coverage"],
               "pulled": sum(1 for f in manifest["files"] if f["status"] == "pulled"),
               "failed": len(manifest["failures"]), "rejected": len(manifest["rejected"]),
               "manifest": os.path.join(args.out, "manifest.json")}
    print(json.dumps(summary, indent=2))
    return exit_code(manifest)


if __name__ == "__main__":
    sys.exit(main())
