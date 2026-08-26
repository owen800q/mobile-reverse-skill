#!/usr/bin/env python3
"""Port the binary-only iOS QBDI tracer to a PlayCover application copy.

The upstream package is a jailbreak Debian package.  MobileSubstrate only
loads TracerEngine.dylib; the engine itself embeds Dobby and QBDI and has no
MobileSubstrate import.  This tool replaces that bootstrap with an
LC_LOAD_DYLIB in a copied PlayCover app and rewrites the two jailbreak-only
configuration roots to a host-visible path (``/tmp/QBDITracer`` by default).

Only thin little-endian 64-bit Mach-O files are modified.  Input files are
never changed in place.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import plistlib
import shutil
import stat
import struct
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path


MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0x0C
MACH_HEADER_64_SIZE = 32
DYLIB_COMMAND_NAME_OFFSET = 24

ENGINE_MEMBER = "Library/MobileSubstrate/DynamicLibraries/TracerEngine.dylib"
OLD_CONFIG_ROOTS = (
    b"/var/jb/var/mobile/Documents/QBDITracer",
    b"/var/mobile/Documents/QBDITracer",
)
DEFAULT_LOAD_PATH = "@executable_path/Frameworks/TracerEngine.dylib"
DEFAULT_CONFIG_ROOT = "/tmp/QBDITracer"


class PortError(RuntimeError):
    """An input failed a porting invariant."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) & ~(boundary - 1)


def read_ar_members(path: Path) -> dict[str, bytes]:
    """Read the simple ar variant used by Debian packages."""
    blob = path.read_bytes()
    if not blob.startswith(b"!<arch>\n"):
        raise PortError(f"not an ar archive: {path}")
    members: dict[str, bytes] = {}
    offset = 8
    while offset < len(blob):
        if offset + 60 > len(blob):
            raise PortError(f"truncated ar header at 0x{offset:x}")
        header = blob[offset : offset + 60]
        if header[58:60] != b"`\n":
            raise PortError(f"invalid ar member header at 0x{offset:x}")
        name = header[:16].decode("ascii", "replace").strip().rstrip("/")
        try:
            size = int(header[48:58].decode("ascii").strip())
        except ValueError as exc:
            raise PortError(f"invalid ar member size at 0x{offset:x}") from exc
        start = offset + 60
        end = start + size
        if end > len(blob):
            raise PortError(f"truncated ar member {name}")
        members[name] = blob[start:end]
        offset = end + (size & 1)
    return members


def extract_engine(deb_path: Path) -> bytes:
    members = read_ar_members(deb_path)
    data_names = [name for name in members if name.startswith("data.tar")]
    if len(data_names) != 1:
        raise PortError(f"expected one data.tar member, found {data_names}")
    try:
        with tarfile.open(fileobj=io.BytesIO(members[data_names[0]]), mode="r:*") as tf:
            matches = [m for m in tf.getmembers() if m.name.lstrip("./") == ENGINE_MEMBER]
            if len(matches) != 1:
                raise PortError(f"expected one {ENGINE_MEMBER}, found {len(matches)}")
            extracted = tf.extractfile(matches[0])
            if extracted is None:
                raise PortError(f"cannot extract {ENGINE_MEMBER}")
            return extracted.read()
    except tarfile.TarError as exc:
        raise PortError(f"cannot read {data_names[0]}: {exc}") from exc


def patch_engine_config_roots(engine: bytes, config_root: str) -> tuple[bytes, list[dict]]:
    replacement = config_root.encode("utf-8")
    if not replacement.startswith(b"/"):
        raise PortError("config root must be an absolute POSIX path")
    changes: list[dict] = []
    patched = bytearray(engine)
    for original in OLD_CONFIG_ROOTS:
        if len(replacement) > len(original):
            raise PortError(
                f"config root is too long ({len(replacement)} > {len(original)}): {config_root}"
            )
        current = bytes(patched)
        offsets: list[int] = []
        cursor = 0
        while True:
            found = current.find(original, cursor)
            if found < 0:
                break
            offsets.append(found)
            cursor = found + 1
        if len(offsets) != 1:
            raise PortError(
                f"expected one occurrence of {original.decode()}, found {len(offsets)}"
            )
        offset = offsets[0]
        value = replacement + b"\0" * (len(original) - len(replacement))
        patched[offset : offset + len(original)] = value
        changes.append(
            {
                "offset": offset,
                "before": original.decode(),
                "after": config_root,
                "width": len(original),
            }
        )
    return bytes(patched), changes


@dataclass(frozen=True)
class MachHeader:
    cputype: int
    cpusubtype: int
    filetype: int
    ncmds: int
    sizeofcmds: int
    flags: int


@dataclass(frozen=True)
class LoadCommand:
    offset: int
    cmd: int
    size: int


def parse_macho(blob: bytes) -> tuple[MachHeader, list[LoadCommand]]:
    if len(blob) < MACH_HEADER_64_SIZE:
        raise PortError("Mach-O is shorter than mach_header_64")
    magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, _ = struct.unpack_from(
        "<IiiIIIII", blob, 0
    )
    if magic != MH_MAGIC_64:
        raise PortError(f"unsupported Mach-O magic 0x{magic:08x}; thin MH_MAGIC_64 required")
    commands: list[LoadCommand] = []
    offset = MACH_HEADER_64_SIZE
    command_end = MACH_HEADER_64_SIZE + sizeofcmds
    if command_end > len(blob):
        raise PortError("load command table extends beyond file")
    for index in range(ncmds):
        if offset + 8 > command_end:
            raise PortError(f"truncated load command {index}")
        cmd, cmdsize = struct.unpack_from("<II", blob, offset)
        if cmdsize < 8 or offset + cmdsize > command_end:
            raise PortError(f"invalid load command {index} size {cmdsize}")
        commands.append(LoadCommand(offset, cmd, cmdsize))
        offset += cmdsize
    if offset != command_end:
        raise PortError(f"load command size mismatch: parsed 0x{offset:x}, header 0x{command_end:x}")
    return MachHeader(cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags), commands


def dylib_paths(blob: bytes) -> list[str]:
    _, commands = parse_macho(blob)
    paths: list[str] = []
    for command in commands:
        if command.cmd != LC_LOAD_DYLIB:
            continue
        if command.size < DYLIB_COMMAND_NAME_OFFSET:
            raise PortError("short LC_LOAD_DYLIB command")
        name_offset = struct.unpack_from("<I", blob, command.offset + 8)[0]
        if name_offset >= command.size:
            raise PortError("LC_LOAD_DYLIB name offset is outside command")
        start = command.offset + name_offset
        end_limit = command.offset + command.size
        end = blob.find(b"\0", start, end_limit)
        if end < 0:
            raise PortError("unterminated LC_LOAD_DYLIB path")
        paths.append(blob[start:end].decode("utf-8", "replace"))
    return paths


def first_section_file_offset(blob: bytes, commands: list[LoadCommand]) -> int:
    offsets: list[int] = []
    for command in commands:
        if command.cmd != LC_SEGMENT_64:
            continue
        if command.size < 72:
            raise PortError("short LC_SEGMENT_64 command")
        fields = struct.unpack_from("<II16sQQQQiiII", blob, command.offset)
        nsects = fields[9]
        expected = 72 + nsects * 80
        if expected > command.size:
            raise PortError("LC_SEGMENT_64 section table exceeds command")
        section_offset = command.offset + 72
        for _ in range(nsects):
            section = struct.unpack_from("<16s16sQQIIIIIIII", blob, section_offset)
            file_offset = section[4]
            if file_offset:
                offsets.append(file_offset)
            section_offset += 80
    if not offsets:
        raise PortError("could not locate a positive section file offset")
    return min(offsets)


def build_dylib_command(path: str) -> bytes:
    encoded = path.encode("utf-8") + b"\0"
    command_size = align(DYLIB_COMMAND_NAME_OFFSET + len(encoded), 8)
    command = bytearray(command_size)
    struct.pack_into(
        "<IIIIII",
        command,
        0,
        LC_LOAD_DYLIB,
        command_size,
        DYLIB_COMMAND_NAME_OFFSET,
        0,
        0,
        0,
    )
    command[DYLIB_COMMAND_NAME_OFFSET : DYLIB_COMMAND_NAME_OFFSET + len(encoded)] = encoded
    return bytes(command)


def inject_load_dylib(blob: bytes, path: str) -> tuple[bytes, dict]:
    header, commands = parse_macho(blob)
    if header.cputype != CPU_TYPE_ARM64:
        raise PortError(f"target CPU type 0x{header.cputype:x} is not ARM64")
    existing = dylib_paths(blob)
    if path in existing:
        return blob, {"changed": False, "path": path, "reason": "already present"}
    command = build_dylib_command(path)
    insert_offset = MACH_HEADER_64_SIZE + header.sizeofcmds
    padding_end = first_section_file_offset(blob, commands)
    if insert_offset + len(command) > padding_end:
        raise PortError(
            f"insufficient Mach-O header padding: need {len(command)} bytes, "
            f"have {padding_end - insert_offset}"
        )
    padding = blob[insert_offset : insert_offset + len(command)]
    if any(padding):
        raise PortError(f"Mach-O load-command padding is not zero at 0x{insert_offset:x}")
    patched = bytearray(blob)
    patched[insert_offset : insert_offset + len(command)] = command
    struct.pack_into("<I", patched, 16, header.ncmds + 1)
    struct.pack_into("<I", patched, 20, header.sizeofcmds + len(command))
    reparsed, _ = parse_macho(patched)
    if reparsed.ncmds != header.ncmds + 1 or path not in dylib_paths(patched):
        raise PortError("post-injection Mach-O verification failed")
    return bytes(patched), {
        "changed": True,
        "path": path,
        "insert_offset": insert_offset,
        "command_size": len(command),
        "header_padding_end": padding_end,
        "ncmds_before": header.ncmds,
        "ncmds_after": reparsed.ncmds,
        "sizeofcmds_before": header.sizeofcmds,
        "sizeofcmds_after": reparsed.sizeofcmds,
    }


def load_app_info(app_path: Path) -> tuple[dict, Path]:
    info_path = app_path / "Info.plist"
    if not info_path.is_file():
        raise PortError(f"missing Info.plist: {info_path}")
    try:
        with info_path.open("rb") as fh:
            info = plistlib.load(fh)
    except Exception as exc:  # noqa: BLE001
        raise PortError(f"cannot parse {info_path}: {exc}") from exc
    executable_name = info.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or not executable_name:
        raise PortError("Info.plist has no CFBundleExecutable")
    executable = app_path / executable_name
    if not executable.is_file():
        raise PortError(f"main executable not found: {executable}")
    return info, executable


def write_file(path: Path, data: bytes, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def port_app(
    deb_path: Path,
    input_app: Path,
    output_app: Path,
    config_root: str,
    load_path: str,
    manifest_path: Path,
) -> dict:
    if output_app.exists():
        raise PortError(f"output already exists: {output_app}")
    info, input_executable = load_app_info(input_app)
    input_exec_hash = sha256_file(input_executable)
    shutil.copytree(input_app, output_app, symlinks=True)
    try:
        _, output_executable = load_app_info(output_app)
        original_engine = extract_engine(deb_path)
        patched_engine, engine_changes = patch_engine_config_roots(original_engine, config_root)
        engine_path = output_app / "Frameworks" / "TracerEngine.dylib"
        write_file(engine_path, patched_engine, executable=True)

        executable_blob = output_executable.read_bytes()
        patched_executable, injection = inject_load_dylib(executable_blob, load_path)
        write_file(output_executable, patched_executable, executable=True)

        manifest = {
            "schema": 1,
            "input": {
                "deb": str(deb_path.resolve()),
                "deb_sha256": sha256_file(deb_path),
                "app": str(input_app.resolve()),
                "bundle_id": info.get("CFBundleIdentifier"),
                "executable": input_executable.name,
                "executable_sha256": input_exec_hash,
                "engine_sha256": sha256_bytes(original_engine),
            },
            "output": {
                "app": str(output_app.resolve()),
                "executable_sha256": sha256_file(output_executable),
                "engine": str(engine_path.resolve()),
                "engine_sha256": sha256_file(engine_path),
                "load_path": load_path,
                "config_root": config_root,
            },
            "engine_changes": engine_changes,
            "macho_injection": injection,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        verify_ported_app(output_app, config_root, load_path)
        return manifest
    except Exception:
        shutil.rmtree(output_app, ignore_errors=True)
        raise


def verify_ported_app(app_path: Path, config_root: str, load_path: str) -> dict:
    info, executable = load_app_info(app_path)
    engine = app_path / "Frameworks" / "TracerEngine.dylib"
    if not engine.is_file():
        raise PortError(f"missing ported engine: {engine}")
    executable_blob = executable.read_bytes()
    header, _ = parse_macho(executable_blob)
    paths = dylib_paths(executable_blob)
    if load_path not in paths:
        raise PortError(f"missing load command: {load_path}")
    engine_blob = engine.read_bytes()
    if engine_blob.count(config_root.encode()) != len(OLD_CONFIG_ROOTS):
        raise PortError("patched configuration root does not occur twice in engine")
    for old in OLD_CONFIG_ROOTS:
        if old in engine_blob:
            raise PortError(f"jailbreak configuration root remains: {old.decode()}")
    return {
        "bundle_id": info.get("CFBundleIdentifier"),
        "executable": str(executable),
        "cputype": header.cputype,
        "ncmds": header.ncmds,
        "load_path": load_path,
        "config_root": config_root,
        "engine_sha256": sha256_file(engine),
        "executable_sha256": sha256_file(executable),
    }


def parse_hex(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {value}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def make_config(args: argparse.Namespace) -> dict:
    if args.end <= args.start:
        raise PortError("end must be greater than start")
    item = {
        "id": args.id,
        "enabled": True,
        "bundleId": args.bundle_id,
        "appName": args.app_name or args.bundle_id,
        "module": args.module,
        "start": args.start,
        "end": args.end,
        "count": args.count,
        "moduleOnly": args.module_only,
        "delaySecs": args.delay,
        "logMask": args.log_mask,
        "watches": [],
    }
    config = {"enabled": True, "items": [item]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract-engine", help="extract TracerEngine.dylib from the Debian package")
    extract.add_argument("--deb", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)

    patch = sub.add_parser("patch-engine", help="rewrite jailbreak configuration roots in an engine copy")
    patch.add_argument("--input", type=Path, required=True)
    patch.add_argument("--output", type=Path, required=True)
    patch.add_argument("--config-root", default=DEFAULT_CONFIG_ROOT)

    port = sub.add_parser("port-app", help="copy an app and inject the patched tracer")
    port.add_argument("--deb", type=Path, required=True)
    port.add_argument("--input-app", type=Path, required=True)
    port.add_argument("--output-app", type=Path, required=True)
    port.add_argument("--manifest", type=Path, required=True)
    port.add_argument("--config-root", default=DEFAULT_CONFIG_ROOT)
    port.add_argument("--load-path", default=DEFAULT_LOAD_PATH)

    verify = sub.add_parser("verify-app", help="verify a ported PlayCover app")
    verify.add_argument("--app", type=Path, required=True)
    verify.add_argument("--config-root", default=DEFAULT_CONFIG_ROOT)
    verify.add_argument("--load-path", default=DEFAULT_LOAD_PATH)

    config = sub.add_parser("make-config", help="write the tracer's config.json schema")
    config.add_argument("--output", type=Path, required=True)
    config.add_argument("--bundle-id", required=True)
    config.add_argument("--app-name")
    config.add_argument("--module", required=True)
    config.add_argument("--start", type=parse_hex, required=True)
    config.add_argument("--end", type=parse_hex, required=True)
    config.add_argument("--count", type=int, default=1)
    config.add_argument("--delay", type=int, default=0)
    config.add_argument("--log-mask", type=parse_hex, default=0x1F)
    config.add_argument("--id", default="ci-trace")
    module_group = config.add_mutually_exclusive_group()
    module_group.add_argument("--module-only", dest="module_only", action="store_true")
    module_group.add_argument("--no-module-only", dest="module_only", action="store_false")
    config.set_defaults(module_only=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "extract-engine":
            data = extract_engine(args.deb)
            write_file(args.output, data, executable=True)
            result = {"output": str(args.output), "sha256": sha256_bytes(data)}
        elif args.command == "patch-engine":
            data, changes = patch_engine_config_roots(args.input.read_bytes(), args.config_root)
            write_file(args.output, data, executable=True)
            result = {"output": str(args.output), "sha256": sha256_bytes(data), "changes": changes}
        elif args.command == "port-app":
            result = port_app(
                args.deb,
                args.input_app,
                args.output_app,
                args.config_root,
                args.load_path,
                args.manifest,
            )
        elif args.command == "verify-app":
            result = verify_ported_app(args.app, args.config_root, args.load_path)
        elif args.command == "make-config":
            result = make_config(args)
        else:  # pragma: no cover
            raise AssertionError(args.command)
    except (OSError, PortError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
