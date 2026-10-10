#!/usr/bin/env python3
"""Extract a firmware image with unblob and write a verification manifest.

Usage:
    firmware_unpack.py FIRMWARE --out DIR [--unblob PATH] [--timeout SECONDS] [--max-depth N]

The unblob executable comes from --unblob or the UNBLOB_COMMAND environment
variable. It must be an absolute path to an existing executable. This tool never
installs unblob. DIR must not exist; the tool creates it mode 0700, because the
extracted tree can hold password hashes and private keys. Layout:

    DIR/extracted/           unblob output (unblob nests each input under
                             <name>_extract/, so a rootfs sits one level down)
    DIR/logs/                unblob-stdout.log and unblob-stderr.log (1 MiB cap
                             each, exact byte counts kept), unblob.log
    DIR/unblob-report.json   unblob's JSON report (--report)
    DIR/manifest.json        input and tool hashes, argv, exit code, status and
                             its reasons, report summary, extracted inventory

Status:
    complete  exit 0, the report has no unknown, encrypted or unextracted chunks,
              and at least one entry was extracted
    partial   exit 0 but the report flags chunks or cannot be read, or the run
              failed after producing entries
    failed    nothing extracted, or the input or input directory changed

Exit codes: 0 complete or partial, 1 failed, 2 usage or input error.

unblob runs with its default Landlock sandbox. --no-sandbox is never passed, and
a failed run is never retried. Extracted content is never executed. No network
access. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import signal
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

try:  # POSIX only; without it the child runs without rlimits.
    import resource
except ImportError:  # pragma: no cover - non-POSIX platforms
    resource = None


UNBLOB_ENV = "UNBLOB_COMMAND"
UNBLOB_HINT = "set UNBLOB_COMMAND to an absolute path; this tool does not install unblob"
MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_HASH_BYTES = 64 * 1024 * 1024
LOG_CAP_BYTES = 1024 * 1024
DEFAULT_TIMEOUT = 900.0
VERSION_TIMEOUT = 30.0
DEFAULT_MAX_DEPTH = 10
AS_LIMIT_BYTES = 1024 * 1024 * 1024
PIPE_JOIN_SECONDS = 30.0
SANDBOX_LOG_CAP_BYTES = 8 * 1024 * 1024
SANDBOX_UNAVAILABLE_TEXT = "Sandboxing FS access is unavailable"
SANDBOX_ERROR_WORDS = ("fail", "error", "cannot", "could not", "unable", "denied")
ERROR_LIST_CAP = 200
CANDIDATE_CAP = 50
ROOTFS_MARKERS = ("bin", "sbin", "usr", "lib")
MISSING_DEPENDENCY_TYPE = "ExtractorDependencyNotFoundReport"
REPORT_SEVERITIES = ("ERROR", "WARNING")

LIMITATION_EXTRACTION_ONLY = "Extraction only; no extracted program was executed"
LIMITATION_SANDBOX_ENABLED = "Unblob's default sandbox remained enabled"
LIMITATION_SANDBOX_UNAVAILABLE = (
    "Unblob reported its filesystem sandbox unavailable on this system, so unblob did not "
    "enforce it for this run (see logs); this tool did not disable it"
)
LIMITATION_FORMAT_COVERAGE = (
    "Format coverage is unblob's; unknown or encrypted regions are not reconstructed"
)
LIMITATION_NOT_RECONSTRUCTION = (
    "Successful extraction does not establish complete firmware reconstruction or runtime behavior"
)
LIMITATION_SYMLINKS = "Symlinks in the extracted tree were recorded by target text and never followed"
LIMITATION_HASH_CAP = (
    "Files above 64 MiB are not hashed; their sha256 is null in the inventory"
)
LIMITATION_VERSION = (
    "The tool version is the first line printed by 'unblob --version'; the tool binary is "
    "identified by sha256 only, not by signature"
)


class UsageError(Exception):
    """Bad arguments, bad input, or an unusable unblob. Exit code 2."""


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _show(text):
    """Escape text for the terminal: firmware-derived names may contain control characters."""
    return ascii(str(text))[1:-1]


def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an integer, got %r" % text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _positive_seconds(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a number of seconds, got %r" % text)
    if not value > 0 or math.isinf(value):
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return value


def sha256_and_size(path):
    """Stream a file through sha256. Returns (hexdigest, bytes_read)."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def resolve_tool(cli_value, environ):
    """Return the absolute unblob path from --unblob or UNBLOB_COMMAND, or raise UsageError."""
    if cli_value is not None:
        value, source = cli_value, "--unblob"
    else:
        value, source = environ.get(UNBLOB_ENV), UNBLOB_ENV
    if not value:
        raise UsageError("no unblob executable configured; %s (or pass --unblob)" % UNBLOB_HINT)
    if not os.path.isabs(value):
        raise UsageError("%s must be an absolute path, got %r; %s" % (source, value, UNBLOB_HINT))
    if not os.path.isfile(value):
        raise UsageError("unblob not found at %r; %s" % (value, UNBLOB_HINT))
    if not os.access(value, os.X_OK):
        raise UsageError("unblob at %r is not executable; %s" % (value, UNBLOB_HINT))
    return value


def probe_version(tool):
    """Run `<tool> --version` with a 30-second timeout and return the first line printed."""
    try:
        proc = subprocess.run(
            [tool, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=VERSION_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise UsageError("'%s --version' did not finish within %d seconds" % (tool, VERSION_TIMEOUT))
    except OSError as exc:
        raise UsageError("cannot run '%s --version': %s" % (tool, exc.strerror or exc))
    if proc.returncode != 0:
        raise UsageError("'%s --version' exited with code %d" % (tool, proc.returncode))
    lines = [line.strip() for line in proc.stdout.decode("utf-8", "replace").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise UsageError("'%s --version' printed no version string" % tool)
    return lines[0][:200]


def check_input(path):
    """Require a regular, non-empty file of at most 128 MiB."""
    try:
        st = os.stat(path)
    except OSError as exc:
        raise UsageError("cannot read input %r: %s" % (path, exc.strerror or exc))
    if not stat.S_ISREG(st.st_mode):
        raise UsageError("input is not a regular file: %s" % path)
    if st.st_size == 0:
        raise UsageError("input is empty: %s" % path)
    if st.st_size > MAX_INPUT_BYTES:
        raise UsageError(
            "input is %d bytes; the limit is %d bytes (128 MiB)" % (st.st_size, MAX_INPUT_BYTES)
        )


def create_output(out):
    """Create DIR, DIR/extracted and DIR/logs. DIR must not already exist."""
    if os.path.lexists(out):
        raise UsageError("output directory already exists, refusing to write into it: %s" % out)
    try:
        os.makedirs(out, mode=0o700)
        os.mkdir(os.path.join(out, "extracted"))
        os.mkdir(os.path.join(out, "logs"))
    except FileExistsError:
        raise UsageError("output directory appeared while starting, refusing to write into it: %s" % out)


def _kill_group(pid):
    """SIGKILL the child's process group (the child was started in its own session)."""
    kill = getattr(os, "killpg", None)
    if kill is None:
        return
    try:
        kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    except OSError:
        pass


def _cap_rlimit(which, value):
    _soft, hard = resource.getrlimit(which)
    if hard != resource.RLIM_INFINITY and value > hard:
        value = hard
    resource.setrlimit(which, (value, value))


def _child_limits(timeout_seconds):
    """Return a preexec_fn applying RLIMIT_AS 1 GiB, RLIMIT_CPU = timeout, RLIMIT_CORE 0."""
    if resource is None:
        return None
    cpu_seconds = max(1, int(math.ceil(timeout_seconds)))

    def apply_limits():
        _cap_rlimit(resource.RLIMIT_AS, AS_LIMIT_BYTES)
        _cap_rlimit(resource.RLIMIT_CPU, cpu_seconds)
        _cap_rlimit(resource.RLIMIT_CORE, 0)

    return apply_limits


class _Drain(threading.Thread):
    """Drain a child pipe to a log file. Keeps at most LOG_CAP_BYTES, counts every byte."""

    def __init__(self, stream, path):
        threading.Thread.__init__(self)
        self.daemon = True
        self._stream = stream
        self._path = path
        self.total = 0
        self.kept = 0
        self.error = None

    def run(self):
        out = None
        try:
            out = open(self._path, "wb")
        except OSError as exc:
            self.error = "cannot open log: %s" % (exc.strerror or exc)
        read = getattr(self._stream, "read1", self._stream.read)
        try:
            while True:
                chunk = read(65536)
                if not chunk:
                    break
                self.total += len(chunk)
                room = LOG_CAP_BYTES - self.kept
                if out is not None and room > 0:
                    piece = chunk[:room]
                    try:
                        out.write(piece)
                        self.kept += len(piece)
                    except OSError as exc:
                        self.error = "cannot write log: %s" % (exc.strerror or exc)
                        out.close()
                        out = None
        except (OSError, ValueError) as exc:
            self.error = "cannot read pipe: %s" % type(exc).__name__
        finally:
            if out is not None:
                try:
                    out.close()
                except OSError:
                    pass
            try:
                self._stream.close()
            except OSError:
                pass

    def describe(self, relpath):
        return {
            "path": relpath,
            "bytes_total": self.total,
            "bytes_kept": self.kept,
            "truncated": self.total > self.kept,
            "capture_incomplete": self.is_alive(),
            "error": self.error,
        }


def run_unblob(argv, workdir, logs_dir, timeout_seconds):
    """Run unblob with resource limits and bounded log capture. Never retries."""
    stdout_path = os.path.join(logs_dir, "unblob-stdout.log")
    stderr_path = os.path.join(logs_dir, "unblob-stderr.log")
    result = {
        "exit_code": None,
        "timed_out": False,
        "launch_error": None,
        "duration_seconds": None,
    }
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv,
            cwd=workdir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=_child_limits(timeout_seconds),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result["launch_error"] = "%s: %s" % (type(exc).__name__, exc)
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        for path in (stdout_path, stderr_path):
            open(path, "wb").close()
        return result, None, None

    drains = (_Drain(proc.stdout, stdout_path), _Drain(proc.stderr, stderr_path))
    for drain in drains:
        drain.start()
    try:
        try:
            result["exit_code"] = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            result["timed_out"] = True
            _kill_group(proc.pid)
            result["exit_code"] = proc.wait()
    finally:
        if proc.poll() is None:  # interrupted: do not leave extraction running
            _kill_group(proc.pid)
            proc.wait()
    for drain in drains:
        drain.join(PIPE_JOIN_SECONDS)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result, drains[0], drains[1]


def _empty_capture(relpath):
    """Log descriptor for a stream that unblob never produced (launch failure)."""
    return {
        "path": relpath,
        "bytes_total": 0,
        "bytes_kept": 0,
        "truncated": False,
        "capture_incomplete": False,
        "error": "unblob was not started",
    }


def _is_error_report(report):
    return isinstance(report, dict) and report.get("severity") in REPORT_SEVERITIES


def _collect_missing(report, missing):
    if isinstance(report, dict) and report.get("__typename__") == MISSING_DEPENDENCY_TYPE:
        deps = report.get("dependencies")
        if isinstance(deps, list):
            missing.update(str(dep) for dep in deps)


def analyze_report(path, max_depth):
    """Summarise unblob's JSON report. Unrecognised structure yields parse 'unrecognized'."""
    info = {
        "present": os.path.isfile(path),
        "parse": "absent",
        "parse_error": None,
        "task_results": 0,
        "chunks": 0,
        "unknown_chunks": 0,
        "encrypted_chunks": 0,
        "unextracted_chunks": 0,
        "unprocessed_subtasks": 0,
        "depth_limited_tasks": 0,
        "unextracted_total": 0,
        "error_reports": 0,
        "warning_reports": 0,
        "report_types": {},
        "missing_dependencies": [],
    }
    if not info["present"]:
        return info

    def unrecognized(reason):
        info["parse"] = "unrecognized"
        info["parse_error"] = reason
        return info

    try:
        with open(path, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        return unrecognized("cannot parse JSON (%s)" % type(exc).__name__)
    if not isinstance(data, list):
        return unrecognized("top level is not a list")

    processed = set()
    subtasks = []
    types = {}
    missing = set()
    unextracted_chunks = depth_limited = unknown = encrypted = chunks = 0
    errors = warnings = 0

    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("task"), dict):
            return unrecognized("task result without a task object")
        if not isinstance(item.get("reports"), list):
            return unrecognized("task result without a reports list")
        task = item["task"]
        depth = task.get("depth")
        task_path = task.get("path")
        if not isinstance(depth, int) or isinstance(depth, bool) or not isinstance(task_path, str):
            return unrecognized("task without integer depth and string path")
        processed.add(task_path)
        info["task_results"] += 1
        if depth >= max_depth:
            depth_limited += 1
        sub_list = item.get("subtasks", [])
        if not isinstance(sub_list, list):
            return unrecognized("subtasks is not a list")
        for sub in sub_list:
            if isinstance(sub, dict) and isinstance(sub.get("path"), str):
                subtasks.append(sub["path"])

        for report in item["reports"]:
            if not isinstance(report, dict):
                return unrecognized("report entry is not an object")
            typename = report.get("__typename__")
            typename = typename if isinstance(typename, str) else "unknown"
            types[typename] = types.get(typename, 0) + 1
            if report.get("severity") == "ERROR":
                errors += 1
            elif report.get("severity") == "WARNING":
                warnings += 1
            _collect_missing(report, missing)

            if typename == "UnknownChunkReport":
                unknown += 1
            elif typename == "ChunkReport":
                chunks += 1
                if report.get("is_encrypted") is True:
                    encrypted += 1
                extraction = report.get("extraction_reports", [])
                if not isinstance(extraction, list):
                    return unrecognized("extraction_reports is not a list")
                flagged = False
                for sub_report in extraction:
                    if not isinstance(sub_report, dict):
                        return unrecognized("extraction report entry is not an object")
                    if sub_report.get("severity") == "ERROR":
                        errors += 1
                    elif sub_report.get("severity") == "WARNING":
                        warnings += 1
                    _collect_missing(sub_report, missing)
                    if _is_error_report(sub_report):
                        flagged = True
                if flagged and report.get("handler_name") != "padding":
                    unextracted_chunks += 1

    unprocessed = sum(1 for sub_path in subtasks if sub_path not in processed)
    info.update({
        "parse": "ok",
        "parse_error": None,
        "chunks": chunks,
        "unknown_chunks": unknown,
        "encrypted_chunks": encrypted,
        "unextracted_chunks": unextracted_chunks,
        "unprocessed_subtasks": unprocessed,
        "depth_limited_tasks": depth_limited,
        "unextracted_total": unextracted_chunks + unprocessed + depth_limited,
        "error_reports": errors,
        "warning_reports": warnings,
        "report_types": dict(sorted(types.items())),
        "missing_dependencies": sorted(missing),
    })
    return info


def scan_sandbox(paths):
    """Look for unblob sandbox messages in the captured output and its own log."""
    unavailable = False
    error_reported = False
    matched = []
    for path in paths:
        try:
            with open(path, "rb") as fh:
                text = fh.read(SANDBOX_LOG_CAP_BYTES).decode("utf-8", "replace")
        except OSError:
            continue
        for line in text.splitlines():
            lowered = line.lower()
            if "sandbox" not in lowered:
                continue
            if SANDBOX_UNAVAILABLE_TEXT.lower() in lowered:
                unavailable = True
            elif any(word in lowered for word in SANDBOX_ERROR_WORDS):
                error_reported = True
            if len(matched) < 10:
                matched.append(line.strip()[:300])
    return {
        "unavailable_warning": unavailable,
        "error_reported": error_reported,
        "matched_lines": matched,
    }


def _sha256_nofollow(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        digest = hashlib.sha256()
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _special_kind(mode):
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "chardev"
    if stat.S_ISBLK(mode):
        return "blockdev"
    return "unknown"


def build_inventory(root):
    """Inventory a tree without following symlinks. Hashes regular files up to 64 MiB."""
    entries = []
    counts = {
        "entries": 0,
        "files": 0,
        "dirs": 0,
        "symlinks": 0,
        "other": 0,
        "hashed_files": 0,
        "hash_skipped_large": 0,
        "regular_bytes": 0,
        "errors": 0,
    }
    errors = []

    def note_error(where, exc):
        counts["errors"] += 1
        if len(errors) < ERROR_LIST_CAP:
            errors.append({
                "path": os.path.relpath(where, root).replace(os.sep, "/"),
                "error": type(exc).__name__,
            })

    def on_walk_error(exc):
        note_error(exc.filename or root, exc)

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=on_walk_error):
        for name in sorted(dirnames) + sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                st = os.lstat(full)
            except OSError as exc:
                note_error(full, exc)
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                target = None
                try:
                    target = os.readlink(full)
                except OSError as exc:
                    note_error(full, exc)
                entries.append({"path": rel, "type": "symlink", "size": None, "sha256": None,
                                "target": target})
                counts["symlinks"] += 1
            elif stat.S_ISDIR(mode):
                entries.append({"path": rel, "type": "dir", "size": None, "sha256": None})
                counts["dirs"] += 1
            elif stat.S_ISREG(mode):
                size = st.st_size
                digest = None
                if size <= MAX_HASH_BYTES:
                    try:
                        digest = _sha256_nofollow(full)
                    except OSError as exc:
                        note_error(full, exc)
                    if digest is not None:
                        counts["hashed_files"] += 1
                else:
                    counts["hash_skipped_large"] += 1
                entries.append({"path": rel, "type": "file", "size": size, "sha256": digest})
                counts["files"] += 1
                counts["regular_bytes"] += size
            else:
                entries.append({"path": rel, "type": "other", "size": None, "sha256": None,
                                "detail": _special_kind(mode)})
                counts["other"] += 1

    counts["entries"] = len(entries)
    entries.sort(key=lambda entry: entry["path"])
    return entries, counts, errors


def rootfs_candidates(entries):
    """Directories (relative to extracted/) that look like a root filesystem: etc plus a usr-like dir."""
    dirs = set(entry["path"] for entry in entries if entry["type"] == "dir")
    found = []
    for base in [""] + sorted(dirs):
        prefix = "" if base == "" else base + "/"
        has_etc = (prefix + "etc") in dirs
        has_marker = any((prefix + marker) in dirs for marker in ROOTFS_MARKERS)
        if has_etc and has_marker:
            found.append(base or ".")
    return found[:CANDIDATE_CAP], len(found)


def decide_status(run, entry_count, report, input_changed, input_dir_changed):
    """Return (status, reasons) following the documented status rules.

    entry_count counts extracted content: files, symlinks and special files. Directories
    alone do not count, so an output tree with only empty directories is not complete.
    """
    if input_changed:
        return "failed", ["input file changed during extraction"]
    if input_dir_changed:
        return "failed", ["entries appeared or vanished in the input directory during the run"]

    run_ok = run["exit_code"] == 0 and not run["timed_out"] and run["launch_error"] is None
    if not run_ok:
        if run["launch_error"] is not None:
            reason = "unblob could not be started (%s)" % run["launch_error"]
        elif run["timed_out"]:
            reason = "unblob was killed after the %g-second timeout" % run["timeout_seconds"]
        else:
            reason = "unblob exited with code %s" % run["exit_code"]
        if entry_count > 0:
            return "partial", [reason, "%d entr%s extracted despite the failure"
                               % (entry_count, "y" if entry_count == 1 else "ies")]
        return "failed", [reason, "no entries were extracted"]

    problems = []
    if not report["present"]:
        problems.append("unblob did not write the requested report")
    elif report["parse"] != "ok":
        problems.append("report structure not recognised (%s)" % report["parse_error"])
    else:
        if report["unknown_chunks"]:
            problems.append("%d unknown chunk(s) in report" % report["unknown_chunks"])
        if report["encrypted_chunks"]:
            problems.append("%d encrypted chunk(s) in report" % report["encrypted_chunks"])
        if report["unextracted_total"]:
            problems.append("%d unextracted chunk/task(s) in report" % report["unextracted_total"])
    if entry_count == 0:
        problems.append("no entries were extracted")
    if problems:
        return "partial", problems
    return "complete", [
        "exit code 0; report has no unknown, encrypted or unextracted chunks; entries extracted"
    ]


def build_limitations(sandbox):
    lines = [LIMITATION_EXTRACTION_ONLY]
    if sandbox["unavailable_warning"]:
        lines.append(LIMITATION_SANDBOX_UNAVAILABLE)
    else:
        lines.append(LIMITATION_SANDBOX_ENABLED)
    lines.append(LIMITATION_FORMAT_COVERAGE)
    lines.append(LIMITATION_NOT_RECONSTRUCTION)
    lines.append(LIMITATION_SYMLINKS)
    lines.append(LIMITATION_HASH_CAP)
    lines.append(LIMITATION_VERSION)
    return lines


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def _listdir_or_none(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return None


def _run(args):
    tool = resolve_tool(args.unblob, os.environ)
    check_input(args.firmware)
    input_path = os.path.abspath(args.firmware)
    out_dir = os.path.abspath(args.out)
    if os.path.lexists(out_dir):
        raise UsageError("output directory already exists, refusing to write into it: %s" % out_dir)

    tool_version = probe_version(tool)
    try:
        tool_sha256, _ = sha256_and_size(tool)
        input_sha256, input_size = sha256_and_size(input_path)
    except OSError as exc:
        raise UsageError("cannot read tool or input for hashing: %s" % (exc.strerror or exc))
    started_utc = _utc_now()

    create_output(out_dir)
    extracted_dir = os.path.join(out_dir, "extracted")
    logs_dir = os.path.join(out_dir, "logs")
    report_path = os.path.join(out_dir, "unblob-report.json")
    unblob_log = os.path.join(logs_dir, "unblob.log")
    input_dir = os.path.dirname(input_path)
    input_dir_before = _listdir_or_none(input_dir)

    argv = [
        tool,
        "--extract-dir", extracted_dir,
        "--depth", str(args.max_depth),
        "--report", report_path,
        "--log", unblob_log,
        input_path,
    ]
    run, stdout_drain, stderr_drain = run_unblob(argv, out_dir, logs_dir, args.timeout)
    run["timeout_seconds"] = args.timeout

    try:
        after_sha256, after_size = sha256_and_size(input_path)
        input_changed = after_sha256 != input_sha256 or after_size != input_size
    except OSError:
        after_sha256, after_size = None, None
        input_changed = True
    input_dir_after = _listdir_or_none(input_dir)
    if input_dir_before is None or input_dir_after is None:
        input_dir_changed = False
        added, removed = [], []
    else:
        added = sorted(set(input_dir_after) - set(input_dir_before))
        removed = sorted(set(input_dir_before) - set(input_dir_after))
        input_dir_changed = bool(added or removed)

    entries, counts, inventory_errors = build_inventory(extracted_dir)
    candidates, candidate_total = rootfs_candidates(entries)
    report = analyze_report(report_path, args.max_depth)
    sandbox = scan_sandbox([
        os.path.join(logs_dir, "unblob-stdout.log"),
        os.path.join(logs_dir, "unblob-stderr.log"),
        unblob_log,
    ])

    content_count = counts["files"] + counts["symlinks"] + counts["other"]
    status, reasons = decide_status(run, content_count, report, input_changed, input_dir_changed)
    if report["parse"] == "ok" and report["missing_dependencies"]:
        reasons.append("missing extractor dependencies reported: %s"
                       % ", ".join(report["missing_dependencies"]))
    if report["depth_limited_tasks"]:
        reasons.append("depth limit %d reached for %d task(s)"
                       % (args.max_depth, report["depth_limited_tasks"]))
    if sandbox["unavailable_warning"]:
        reasons.append("unblob reported its sandbox unavailable (not enforced for this run)")
    if sandbox["error_reported"] and not run["timed_out"] and run["exit_code"] != 0:
        reasons.append("unblob reported a sandbox error; it was not retried")

    limitations = build_limitations(sandbox)
    if report["parse"] != "ok" and report["present"]:
        limitations.append("Unblob's report structure was not recognised; chunk status is unverified")
    if report["missing_dependencies"]:
        limitations.append(
            "Missing external extractors reduced format coverage: %s"
            % ", ".join(report["missing_dependencies"])
        )
    if report["depth_limited_tasks"]:
        limitations.append(
            "Depth limit %d reached; deeper content was not extracted" % args.max_depth
        )
    if input_dir_before is None or input_dir_after is None:
        limitations.append("The input directory listing was unavailable; its changes were not checked")

    manifest = {
        "schema": 1,
        "tool": "firmware_unpack.py",
        "status": status,
        "status_reasons": reasons,
        "started_utc": started_utc,
        "finished_utc": _utc_now(),
        "input": {
            "path": input_path,
            "realpath": os.path.realpath(input_path),
            "sha256": input_sha256,
            "size_bytes": input_size,
            "sha256_after": after_sha256,
            "size_bytes_after": after_size,
            "unchanged": not input_changed,
        },
        "unblob": {
            "path": tool,
            "sha256": tool_sha256,
            "version": tool_version,
        },
        "run": {
            "argv": argv,
            "exit_code": run["exit_code"],
            "timed_out": run["timed_out"],
            "launch_error": run["launch_error"],
            "duration_seconds": run["duration_seconds"],
            "timeout_seconds": args.timeout,
            "max_depth": args.max_depth,
            "resource_limits": (
                None if resource is None else {
                    "RLIMIT_AS_bytes": AS_LIMIT_BYTES,
                    "RLIMIT_CPU_seconds": max(1, int(math.ceil(args.timeout))),
                    "RLIMIT_CORE": 0,
                }
            ),
        },
        "sandbox": sandbox,
        "logs": {
            "stdout": (stdout_drain.describe("logs/unblob-stdout.log") if stdout_drain
                       else _empty_capture("logs/unblob-stdout.log")),
            "stderr": (stderr_drain.describe("logs/unblob-stderr.log") if stderr_drain
                       else _empty_capture("logs/unblob-stderr.log")),
            "unblob_log": {
                "path": "logs/unblob.log",
                "exists": os.path.isfile(unblob_log),
                "bytes": os.path.getsize(unblob_log) if os.path.isfile(unblob_log) else None,
            },
        },
        "report": {"path": "unblob-report.json", **report},
        "counts": counts,
        "inventory": {
            "root": "extracted",
            "rootfs_candidates": candidates,
            "rootfs_candidates_total": candidate_total,
            "errors": inventory_errors,
            "entries": entries,
        },
        "input_directory": {
            "path": input_dir,
            "changed": input_dir_changed,
            "added": added,
            "removed": removed,
        },
        "limitations": limitations,
    }
    manifest_path = os.path.join(out_dir, "manifest.json")
    _write_json(manifest_path, manifest)

    summary = "firmware_unpack: status=%s unblob_exit=%s entries=%d (files=%d dirs=%d symlinks=%d)" % (
        status, run["exit_code"], counts["entries"], counts["files"], counts["dirs"],
        counts["symlinks"],
    )
    sys.stdout.write(summary + "\n")
    sys.stdout.write("manifest: %s\n" % _show(manifest_path))
    if candidates:
        sys.stdout.write("rootfs candidates (under extracted/): %s\n"
                         % ", ".join(_show(name) for name in candidates))
    else:
        sys.stdout.write("rootfs candidates: none found; inspect extracted/ manually\n")
    if status != "complete":
        for reason in reasons:
            sys.stderr.write("  reason: %s\n" % _show(reason))
    if sandbox["unavailable_warning"]:
        sys.stderr.write("WARNING: unblob reported its sandbox unavailable; see the manifest\n")
    if sandbox["error_reported"]:
        sys.stderr.write("WARNING: unblob reported a sandbox error; it was not retried\n")
    return 1 if status == "failed" else 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Extract a firmware image with unblob and write manifest.json.",
    )
    parser.add_argument("firmware", help="firmware image file (regular, non-empty, at most 128 MiB)")
    parser.add_argument("--out", required=True, help="output directory; must not exist")
    parser.add_argument(
        "--unblob",
        default=None,
        help="absolute path to the unblob executable (default: $UNBLOB_COMMAND)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_seconds,
        default=DEFAULT_TIMEOUT,
        help="seconds before unblob is killed (default %d)" % int(DEFAULT_TIMEOUT),
    )
    parser.add_argument(
        "--max-depth",
        type=_positive_int,
        default=DEFAULT_MAX_DEPTH,
        help="unblob recursion depth, passed as --depth (default %d)" % DEFAULT_MAX_DEPTH,
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except UsageError as exc:
        sys.stderr.write("ERROR: %s\n" % _show(exc))
        return 2
    except OSError as exc:
        sys.stderr.write("ERROR: %s\n" % _show(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
