#!/usr/bin/env python3
"""
target_identify.py - classify an input and suggest a reverse-skill route.

Usage:
    target_identify.py PATH

Prints one JSON object. It reads headers and, for archives, member names only.
It never executes the target, never extracts anything, and never follows
symlinks inside a directory. The route is a routing hint: confirm it with the
route's own tools before relying on it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import zipfile

HASH_LIMIT = 2 * 1024 ** 3
MAX_MEMBERS = 200000
TAIL_BYTES = 64 * 1024
PYI_COOKIE = b"MEI\x0c\x0b\x0a\x0b\x06"  # PyInstaller archive cookie

ELF_MACHINE = {3: "x86", 8: "MIPS", 20: "PowerPC", 21: "PowerPC64", 40: "ARM",
               62: "x86-64", 94: "Xtensa", 183: "AArch64", 243: "RISC-V"}
ELF_TYPE = {1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
PE_MACHINE = {0x014C: "x86", 0x8664: "x86-64", 0x01C0: "ARM", 0x01C4: "ARMv7",
              0xAA64: "AArch64", 0x0200: "IA64"}
MACHO_CPU = {7: "x86", 0x01000007: "x86-64", 12: "ARM", 0x0100000C: "AArch64",
             0x0200000C: "arm64_32", 18: "PowerPC", 0x01000012: "PowerPC64"}
# arm64 subtypes that change a slice's name. The lipo name is what `lipo -thin` takes.
# Subtype 12 is CPU_SUBTYPE_ARM64E_X1; lipo calls it arm64e.x1 (rea 5c29565, macOS 27 /bin/ls).
MACHO_ARM64_LIPO = {2: "arm64e", 12: "arm64e.x1"}
MACHO_FILETYPE = {2: "EXECUTE", 6: "DYLIB", 8: "BUNDLE"}
MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce": (32, ">"), b"\xce\xfa\xed\xfe": (32, "<"),
    b"\xfe\xed\xfa\xcf": (64, ">"), b"\xcf\xfa\xed\xfe": (64, "<"),
}

# Plain signatures at offset 0: (magic, format, route, note)
SIGNATURES = [
    (b"hsqs", "squashfs (little-endian)", "firmware", "SquashFS image"),
    (b"sqsh", "squashfs (big-endian)", "firmware", "SquashFS image"),
    (b"UBI#", "ubi image", "firmware", "UBI erase-counter header"),
    (b"\x27\x05\x19\x56", "u-boot uimage", "firmware", "legacy U-Boot image header"),
    (b"\xd0\x0d\xfe\xed", "device tree blob", "firmware",
     "flattened device tree (FIT images use this header)"),
    (b"\x1f\x8b", "gzip", "archive", "gzip stream"),
    (b"\xfd7zXZ\x00", "xz", "archive", "xz stream"),
    (b"\x28\xb5\x2f\xfd", "zstd", "archive", "zstd frame"),
    (b"BZh", "bzip2", "archive", "bzip2 stream"),
    (b"7z\xbc\xaf\x27\x1c", "7z", "archive", "7z archive"),
    (b"\x00asm", "wasm module", "web", "WebAssembly module"),
    (b"dex\n", "dex", "android", "Dalvik executable"),
    (b"bplist00", "binary plist", "ios",
     "bplist00 magic; keyed archives and other property lists often use a non-.plist name, "
     "and plistlib reads them"),
]

# Route key -> where the reverse-skill guidance for it lives.
ROUTES = {
    "android": "SKILL.md Android phases P0-P6; references/android-triage.md",
    "ios": "SKILL.md iOS mode; references/ios-playcover.md",
    "harmony": "references/optional-platforms.md section 5 (HarmonyOS packages)",
    "web": "references/web.md",
    "desktop-electron": "references/desktop.md (Electron section), then references/web.md",
    "desktop-native": "references/desktop.md (native section)",
    "desktop-managed": "references/desktop.md (.NET section)",
    "desktop-java": "references/desktop.md (Java section)",
    "desktop-packed-python": "references/desktop.md (PyInstaller section)",
    "native-elf": "ambiguous: Android .so -> SKILL.md P4; desktop -> references/desktop.md; "
                  "firmware -> references/firmware.md",
    "firmware": "references/firmware.md",
    "archive": "identify the extracted contents, then route again",
    "unknown": "no route matched; inspect the header and container listing manually",
}

LIMITATIONS = [
    "Header and container-listing identification only; formats can be nested",
    "Nothing was extracted, executed, or followed",
    "The route is a hint: confirm it with the route's own tools",
]


def _new_info(path, kind, size):
    return {
        "path": os.path.abspath(path),
        "kind": kind,
        "size": size,
        "sha256": None,
        "format": "unknown",
        "route": "unknown",
        "arch": None,
        "bits": None,
        "endian": None,
        "managed": False,
        "pyinstaller_candidate": False,
        "members": None,
        "notes": [],
        "limitations": list(LIMITATIONS),
    }


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _elf(head, info):
    if len(head) < 20 or head[4] not in (1, 2) or head[5] not in (1, 2):
        info.update(format="ELF (malformed header)", route="native-elf")
        return
    order = "<" if head[5] == 1 else ">"
    e_type, e_machine = struct.unpack_from(order + "HH", head, 16)
    info.update(format="ELF", bits=32 if head[4] == 1 else 64,
                endian="LE" if head[5] == 1 else "BE",
                arch=ELF_MACHINE.get(e_machine, "unknown(%d)" % e_machine),
                route="native-elf")
    info["notes"].append("ELF type %s" % ELF_TYPE.get(e_type, str(e_type)))


def _pe(f, size, info):
    f.seek(0)
    hdr = f.read(64)
    if len(hdr) < 64:
        info.update(format="MZ (truncated)")
        return
    e_lfanew = struct.unpack_from("<I", hdr, 0x3C)[0]
    f.seek(e_lfanew)
    if e_lfanew + 24 > size:
        info.update(format="MZ (no PE header)")
        info["notes"].append("DOS header without a PE signature")
        return
    new_header = f.read(4)
    if new_header[:2] in (b"NE", b"LE", b"LX"):
        # 16-bit NE and OS/2 LE/LX images are Windows-family, not PE: name them, do not call them DOS.
        info.update(format="MZ (%s, not PE)" % new_header[:2].decode("ascii"))
        info["notes"].append("unsupported %s executable behind the MZ stub" % new_header[:2].decode("ascii"))
        return
    if new_header != b"PE\0\0":
        info.update(format="MZ (no PE header)")
        info["notes"].append("DOS header without a PE signature")
        return
    coff = f.read(20)
    if len(coff) < 20:
        info.update(format="PE (truncated)")
        return
    machine = struct.unpack_from("<H", coff, 0)[0]
    size_opt, characteristics = struct.unpack_from("<HH", coff, 16)
    opt = f.read(min(size_opt, 512))
    magic = struct.unpack_from("<H", opt, 0)[0] if len(opt) >= 2 else 0
    bits = {0x10B: 32, 0x20B: 64}.get(magic)
    dd_off = {0x10B: 96, 0x20B: 112}.get(magic)
    managed = False
    if dd_off and len(opt) >= dd_off + 15 * 8 + 8:
        # Data directory 14 is the CLI (CLR) header; a non-zero RVA marks .NET.
        managed = struct.unpack_from("<I", opt, dd_off + 14 * 8)[0] != 0
    info.update(format="PE", arch=PE_MACHINE.get(machine, "unknown(0x%x)" % machine),
                bits=bits, endian="LE", managed=managed,
                route="desktop-managed" if managed else "desktop-native")
    info["notes"].append("PE %s" % ("DLL" if characteristics & 0x2000 else "EXE"))
    if managed:
        info["notes"].append("CLI header present (.NET managed image)")


def _macho_arch(cputype, subtype):
    """Architecture name for a Mach-O slice, with the lipo name when it is an arm64e variant."""
    name = MACHO_CPU.get(cputype, "unknown(0x%x)" % cputype)
    lipo = MACHO_ARM64_LIPO.get(subtype & 0x00FFFFFF) if cputype == 0x0100000C else None
    return "%s %s" % (name, lipo) if lipo else name


# Mach-O platform and build tools (mach-o/loader.h). LC_BUILD_VERSION names a platform and
# its build tools; LC_VERSION_MIN_* names only a platform.
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN = {0x24: 1, 0x25: 2, 0x2F: 3, 0x30: 4}  # MACOSX, IPHONEOS, TVOS, WATCHOS
MACHO_PLATFORM = {1: "macOS", 2: "iOS", 3: "tvOS", 4: "watchOS", 5: "bridgeOS", 6: "Mac Catalyst",
                  7: "iOS simulator", 8: "tvOS simulator", 9: "watchOS simulator", 10: "DriverKit",
                  11: "visionOS", 12: "visionOS simulator"}
MACHO_TOOL = {1: "clang", 2: "swift", 3: "ld", 4: "lld"}


def _macho_version(value):
    return "%d.%d.%d" % (value >> 16, (value >> 8) & 0xFF, value & 0xFF)


def macho_build(cmds, ncmds, order="<"):
    """Platform, minimum OS, SDK and build tools from the first build-version load command.

    Reads only the bytes it is given; a command that runs past them ends the walk, so a
    truncated table yields None rather than a guess.
    """
    off = 0
    for _ in range(ncmds):
        if off + 8 > len(cmds):
            break
        cmd, cmdsize = struct.unpack_from(order + "II", cmds, off)
        if cmdsize < 8 or off + cmdsize > len(cmds):
            break
        if cmd == LC_BUILD_VERSION and cmdsize >= 24:
            plat, minos, sdk, ntools = struct.unpack_from(order + "IIII", cmds, off + 8)
            tools = []
            for i in range(min(ntools, (cmdsize - 24) // 8)):
                tool, version = struct.unpack_from(order + "II", cmds, off + 24 + 8 * i)
                tools.append({"tool": MACHO_TOOL.get(tool, "tool-%d" % tool),
                              "version": _macho_version(version)})
            return {"platform": MACHO_PLATFORM.get(plat, "platform-%d" % plat),
                    "minos": _macho_version(minos), "sdk": _macho_version(sdk), "tools": tools}
        if cmd in LC_VERSION_MIN and cmdsize >= 16:
            minos, sdk = struct.unpack_from(order + "II", cmds, off + 8)
            return {"platform": MACHO_PLATFORM[LC_VERSION_MIN[cmd]], "minos": _macho_version(minos),
                    "sdk": _macho_version(sdk), "tools": []}
        off += cmdsize
    return None


def _macho(head, info):
    bits, order = MACHO_MAGIC[head[:4]]
    cputype, subtype, filetype = struct.unpack_from(order + "III", head, 4)
    info.update(format="Mach-O", bits=bits, endian="LE" if order == "<" else "BE",
                arch=_macho_arch(cputype, subtype), route="desktop-native")
    info["notes"].append(MACHO_FILETYPE.get(filetype, "filetype %d" % filetype))
    build = None
    if len(head) >= 24:
        ncmds, sizeofcmds = struct.unpack_from(order + "II", head, 16)
        header = 32 if bits == 64 else 28
        build = macho_build(head[header:header + sizeofcmds], ncmds, order)
    if build is None:
        info["notes"].append("macOS binary: iOS-mode mechanics (local Frida, codesign) apply; "
                             "see references/ios-playcover.md")
        return
    info["build"] = build
    tools = ", ".join("%s %s" % (t["tool"], t["version"]) for t in build["tools"]) or "no tool records"
    info["notes"].append("%s binary: minos %s, sdk %s, built with %s"
                         % (build["platform"], build["minos"], build["sdk"], tools))
    if build["platform"] in ("iOS", "iOS simulator"):
        info["notes"].append("iOS-family slice: see references/ios-playcover.md")


# Universal (fat) Mach-O headers. The 32-bit table has 20-byte entries; FAT64 has 32-byte
# entries with 64-bit offset and size. The swapped magics are little-endian tables.
FAT_MAGIC = {
    b"\xca\xfe\xba\xbe": (">", 20, "fat"),
    b"\xca\xfe\xba\xbf": (">", 32, "fat64"),
    b"\xbe\xba\xfe\xca": ("<", 20, "fat"),
    b"\xbf\xba\xfe\xca": ("<", 32, "fat64"),
}
MACHO_HEADER_MIN = 28  # a 32-bit Mach-O header; a slice shorter than this cannot be one


def _fat_or_java(head, info, size=None):
    if len(head) < 8:
        return
    order, entry, kind = FAT_MAGIC[head[:4]]
    second = struct.unpack_from(order + "I", head, 4)[0]
    if kind == "fat" and order == ">" and not 1 <= second <= 20:
        info.update(format="java class", route="desktop-java")
        info["notes"].append("class file major version %d"
                             % struct.unpack_from(">H", head, 6)[0])
        return
    if not 1 <= second <= 64:
        info.update(format="unknown")
        info["notes"].append("%s header with an implausible architecture count (%d); "
                             "not classified as Mach-O" % (kind, second))
        return
    cpus, slices, table_end = [], [], 8 + second * entry
    for i in range(second):
        off = 8 + i * entry
        if off + entry > len(head):
            break
        cpu, subtype = struct.unpack_from(order + "II", head, off)
        cpus.append(_macho_arch(cpu, subtype))
        if kind == "fat":
            s_off, s_len = struct.unpack_from(order + "II", head, off + 8)
        else:
            s_off, s_len = struct.unpack_from(order + "QQ", head, off + 8)
        # A slice's width and byte order come from its own CPU type. The table's byte order
        # only says how the table itself is written, so it does not describe the code.
        family = cpu & 0x00FFFFFF
        slices.append({"index": i, "arch": cpus[-1], "offset": s_off, "size": s_len,
                       "bits": 64 if cpu & 0x01000000 else 32,
                       "endian": {7: "LE", 12: "LE", 18: "BE"}.get(family)})
        if s_off < table_end:
            info["notes"].append("slice %d (%s) overlaps the architecture table" % (i, cpus[-1]))
        elif s_len < MACHO_HEADER_MIN:
            info["notes"].append("slice %d (%s) is shorter than a Mach-O header" % (i, cpus[-1]))
        elif size is not None and s_off + s_len > size:
            info["notes"].append("slice %d (%s) runs past the end of the file" % (i, cpus[-1]))
    shown = ", ".join(cpus) or None
    info.update(format="Mach-O (universal)" if kind == "fat" else "Mach-O (universal, FAT64)",
                endian="LE" if order == "<" else "BE", arch=shown, route="desktop-native",
                slices=slices)
    info["notes"].append("top-level endian is the fat table's byte order; read each slice's "
                         "own endian and bits")
    info["notes"].append("%s header lists %d architecture(s)%s"
                         % (kind, second, "; table read only partly from the first 4 KiB"
                            if len(cpus) < second else ""))
    info["notes"].append("the container is a fat file, not a slice: choose a slice before "
                         "per-architecture work (lipo -thin, or the tool's slice option)")


def _harmony(path, names, members, info):
    """Recognise HarmonyOS packages by name suffix plus root layout. Path presence only.

    Stage-model modules carry module.json at the root and FA-model modules carry config.json.
    A .app root that lists .hap/.hsp members (or pack.info) is a distribution App Pack. A
    nested .app inside another package is not classified here, because an IPA's Payload/X.app
    is a directory of the iOS archive and never a root input.
    """
    low = path.lower()
    if low.endswith((".hap", ".hsp")):
        model = ("stage" if "module.json" in members
                 else "fa" if "config.json" in members else None)
        if model is None:
            return False
        kind = "hsp" if low.endswith(".hsp") else "hap"
        info.update(format="harmonyos package (%s)" % kind, route="harmony")
        info["notes"].append("%s model (root %s)" % (model, "module.json" if model == "stage" else "config.json"))
    elif low.endswith(".app") and (
            "pack.info" in members or any(n.lower().endswith((".hap", ".hsp")) for n in names)):
        children = sorted(n for n in names if n.lower().endswith((".hap", ".hsp")))
        info.update(format="harmonyos app pack", route="harmony")
        info["notes"].append("%d child package(s) listed by path, not opened" % len(children))
        return True
    else:
        return False
    abc = sorted(n for n in names if n.lower().endswith(".abc"))
    if abc:
        info["notes"].append("Ark bytecode (not DEX): %s" % ", ".join(abc[:5]))
    abis = sorted({n.split("/")[1] for n in names
                   if n.startswith("libs/") and n.count("/") >= 2 and n.endswith(".so")})
    if abis:
        info["notes"].append("native libraries (ELF) for: %s" % ", ".join(abis))
    if any(n.startswith("META-INF/") for n in names):
        info["notes"].append("META-INF entries present; signing was not verified")
    info["notes"].append("identified from paths only; manifest content and bytecode were not read")
    return True


def _zip(path, info):
    try:
        with zipfile.ZipFile(path) as z:
            # ./Payload/... names one member of the archive, so classify the name the installer sees.
            names = []
            for raw in z.namelist()[:MAX_MEMBERS]:
                while raw.startswith("./"):
                    raw = raw[2:]
                names.append(raw)
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        info.update(format="zip (directory unreadable)")
        info["notes"].append("zip signature but the directory could not be read: %s"
                             % exc.__class__.__name__)
        return
    members = set(names)
    info["members"] = len(names)
    if _harmony(path, names, members, info):
        return
    if "AndroidManifest.xml" in members or any(n.endswith("classes.dex") for n in names):
        info.update(format="android package (apk)", route="android")
    elif "BundleConfig.pb" in members or any(n.startswith("base/manifest/") for n in names):
        info.update(format="android bundle (aab)", route="android")
        info["notes"].append("convert the AAB to an APK set before APK routes")
    elif any(n.startswith("Payload/") and ".app/" in n for n in names):
        info.update(format="ios app archive (ipa)", route="ios")
    elif "payload.bin" in members or "META-INF/com/android/otacert" in members:
        info.update(format="android ota package", route="firmware")
    elif "META-INF/MANIFEST.MF" in members:
        info.update(format="java archive (jar)", route="desktop-java")
    else:
        info.update(format="zip", route="archive")


def _asar(f, size, info):
    f.seek(0)
    hdr = f.read(16)
    if len(hdr) < 16 or struct.unpack_from("<I", hdr, 0)[0] != 4:
        return False
    header_size = struct.unpack_from("<I", hdr, 4)[0]
    json_len = struct.unpack_from("<I", hdr, 12)[0]
    if not (8 < header_size <= 64 * 1024 * 1024) or not (0 < json_len <= header_size - 4):
        return False
    if 16 + json_len > size:
        return False
    f.seek(16)
    try:
        obj = json.loads(f.read(json_len).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False
    if not isinstance(obj, dict) or not isinstance(obj.get("files"), dict):
        return False
    info.update(format="asar archive", route="desktop-electron", members=len(obj["files"]))
    info["notes"].append("top-level entries: %d" % len(obj["files"]))
    return True


def _signature(head, info):
    for magic, fmt, route, note in SIGNATURES:
        if head.startswith(magic):
            info.update(format=fmt, route=route)
            info["notes"].append(note)
            return True
    if len(head) >= 262 and head[257:262] == b"ustar":
        info.update(format="tar", route="archive")
        return True
    return False


def _text(path, head, info):
    if b"\x00" in head:
        return
    text = head.decode("utf-8", "replace").lstrip().lower()
    name = path.lower()
    if text.startswith("<!doctype html") or text.startswith("<html"):
        info.update(format="html document", route="web")
    elif name.endswith(".map"):
        info.update(format="source map", route="web")
        info["notes"].append("identified by extension; the JSON body was not parsed")
    elif name.endswith((".js", ".mjs", ".cjs", ".jsbundle")):
        info.update(format="javascript", route="web")
        info["notes"].append("React Native bundles: also see references/hermes-react-native.md")


def _pyinstaller_check(f, size, info):
    start = max(0, size - TAIL_BYTES)
    f.seek(start)
    if PYI_COOKIE in f.read(size - start):
        info["pyinstaller_candidate"] = True
        if info["route"] in ("desktop-native", "native-elf"):
            info["route"] = "desktop-packed-python"
        info["notes"].append("PyInstaller archive cookie in the last 64 KiB (candidate)")


def identify_file(path):
    size = os.path.getsize(path)
    info = _new_info(path, "file", size)
    if size <= HASH_LIMIT:
        info["sha256"] = _sha256(path)
    with open(path, "rb") as f:
        head = f.read(4096)
        if head[:4] == b"\x7fELF":
            _elf(head, info)
        elif head[:2] == b"MZ":
            _pe(f, size, info)
        elif head[:4] == b"PK\x03\x04":
            _zip(path, info)
        elif len(head) >= 16 and head[:4] in MACHO_MAGIC:
            _macho(head, info)
        elif head[:4] in FAT_MAGIC:
            _fat_or_java(head, info, size)
        elif _asar(f, size, info):
            pass
        elif not _signature(head, info):
            _text(path, head, info)
        if info["format"] in ("ELF", "PE", "Mach-O", "unknown") or info["route"] in (
                "desktop-native", "native-elf"):
            _pyinstaller_check(f, size, info)
    info["reference"] = ROUTES.get(info["route"], ROUTES["unknown"])
    return info


def identify_dir(path):
    info = _new_info(path, "directory", None)
    info["members"] = len(os.listdir(path))

    def under(*parts):
        return os.path.join(path, *parts)

    if path.rstrip(os.sep).endswith(".app") and os.path.isfile(under("Contents", "Info.plist")):
        info.update(format="macOS app bundle", route="desktop-native")
    elif (os.path.isfile(under("resources", "app.asar")) or os.path.isfile(under("app.asar"))
          or os.path.isdir(under("resources", "app"))):
        info.update(format="electron app directory", route="desktop-electron")
    elif os.path.isfile(under("AndroidManifest.xml")):
        info.update(format="decoded android package", route="android")
    elif os.path.isdir(under("etc")) and (os.path.isdir(under("bin"))
                                          or os.path.isdir(under("sbin"))):
        info.update(format="root filesystem directory", route="firmware")
    info["reference"] = ROUTES.get(info["route"], ROUTES["unknown"])
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description="Classify an input and suggest a reverse-skill route.")
    ap.add_argument("path", help="file or directory to classify")
    args = ap.parse_args(argv)
    if os.path.isdir(args.path):
        info = identify_dir(args.path)
    elif os.path.isfile(args.path):
        info = identify_file(args.path)
    else:
        sys.stderr.write("ERROR: not a regular file or directory: %s\n" % args.path)
        return 2
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
