#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import sys
from pathlib import Path

libc = ctypes.CDLL(None, use_errno=True)
PTRACE_TRACEME = 0
PTRACE_CONT = 7
PTRACE_ATTACH = 16
PTRACE_DETACH = 17


def ptrace(request: int, pid: int, addr: int = 0, data: int = 0) -> None:
    result = libc.ptrace(request, pid, ctypes.c_void_p(addr), ctypes.c_void_p(data))
    if result == -1:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


def wait_stopped(pid: int) -> int:
    waited, status = os.waitpid(pid, 0)
    if waited != pid or not os.WIFSTOPPED(status):
        raise RuntimeError(
            f"process {pid} did not stop as expected: status={status}"
        )
    return os.WSTOPSIG(status)


def maps_for(pid: int) -> list[tuple[int, int, int, str]]:
    result = []
    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) < 5:
            continue
        start_s, end_s = fields[0].split("-")
        path = fields[5] if len(fields) == 6 else ""
        result.append(
            (int(start_s, 16), int(end_s, 16), int(fields[2], 16), path)
        )
    return result


def runtime_address(pid: int, executable: Path, file_offset: int) -> int:
    real = str(executable.resolve())
    for start, end, map_offset, path in maps_for(pid):
        cleaned = path.removesuffix(" (deleted)")
        if cleaned != real:
            continue
        span = end - start
        if map_offset <= file_offset < map_offset + span:
            return start + file_offset - map_offset
    raise RuntimeError(f"no mapping for {real} file offset 0x{file_offset:x}")


def apply_spec(pid: int, executable: Path, spec_path: Path) -> None:
    spec = json.loads(spec_path.read_text())
    expected_sha = spec.get("sha256")
    if expected_sha:
        actual = hashlib.sha256(executable.read_bytes()).hexdigest()
        if actual != expected_sha:
            raise RuntimeError(f"binary hash mismatch: {actual} != {expected_sha}")

    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        for patch in spec["patches"]:
            raw_offset = patch["file_offset"]
            offset = int(raw_offset, 0) if isinstance(raw_offset, str) else int(raw_offset)
            expected = bytes.fromhex(patch["expected"])
            replacement = bytes.fromhex(patch["replacement"])
            if len(expected) != len(replacement):
                raise RuntimeError("expected and replacement byte lengths differ")
            address = runtime_address(pid, executable, offset)
            mem.seek(address)
            observed = mem.read(len(expected))
            if observed != expected:
                raise RuntimeError(
                    f"byte mismatch at 0x{address:x}: "
                    f"observed={observed.hex()} expected={expected.hex()}"
                )
            mem.seek(address)
            mem.write(replacement)
            print(
                f"patched {patch.get('name', 'site')} pid={pid} "
                f"addr=0x{address:x} {expected.hex()}->{replacement.hex()}"
            )


def attach_mode(pid: int, executable: Path, spec: Path) -> int:
    ptrace(PTRACE_ATTACH, pid)
    wait_stopped(pid)
    try:
        apply_spec(pid, executable, spec)
    finally:
        ptrace(PTRACE_DETACH, pid)
    return 0


def exec_mode(executable: Path, spec: Path, argv: list[str]) -> int:
    pid = os.fork()
    if pid == 0:
        try:
            ptrace(PTRACE_TRACEME, 0)
            os.kill(os.getpid(), signal.SIGSTOP)
            os.execvpe(str(executable), [str(executable), *argv], os.environ)
        except BaseException as exc:
            print(f"child setup failed: {exc}", file=sys.stderr)
            os._exit(127)

    wait_stopped(pid)
    ptrace(PTRACE_CONT, pid)
    wait_stopped(pid)
    try:
        apply_spec(pid, executable, spec)
    except BaseException:
        os.kill(pid, signal.SIGKILL)
        raise
    ptrace(PTRACE_DETACH, pid)
    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hash- and byte-guarded in-memory ELF patcher"
    )
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pid", type=int)
    mode.add_argument("--exec", action="store_true", dest="do_exec")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.pid is not None:
        return attach_mode(args.pid, args.binary, args.spec)
    child_args = args.args[1:] if args.args[:1] == ["--"] else args.args
    return exec_mode(args.binary, args.spec, child_args)


if __name__ == "__main__":
    raise SystemExit(main())
