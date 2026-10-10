#!/usr/bin/env python3
"""Inventory an APK, AAB, or IPA without extracting, executing, or decrypting it.

Usage:
    mobile_inventory.py PATH [--max-entries N]

The archive is listed, and only the members the inventory needs are read, each under
a size cap. Nothing is written to disk. Output is one JSON object on stdout:

  Android (APK, AAB)  per-module DEX files, native libraries by ABI, asset directories,
                      and the base manifest's package and version. APK manifests are
                      binary XML; AAB manifests are protobuf (aapt2 --proto-format). Only
                      those three attributes are read from either.
  iOS (IPA)           app identity from Info.plist, frameworks and embedded dylibs,
                      app extensions (a path role and an NSExtensionPointIdentifier
                      role), watch apps, and the FairPlay cryptid, architectures, and
                      linked dylibs of the arm64 slice (or the only slice).
  runtime_hints       marker matches for engines and runtimes. Each hint is strong or
                      weak and lists its evidence. A hint is a lead to check, not a verdict.

Exit codes: 0 inventory produced; 1 not an APK, AAB, or IPA, malformed, or over the entry
limit; 2 usage error. Standard library only.
"""
import argparse
import hashlib
import json
import lzma
import os
import plistlib
import re
import struct
import sys
import zipfile
import zlib

DEFAULT_MAX_ENTRIES = 200_000
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_PLIST_BYTES = 8 * 1024 * 1024
MAX_MACHO_HEADER_BYTES = 16 * 1024 * 1024
MAX_SLICE_SKIP = 16 * 1024 * 1024
MAX_AXML_STRINGS = 200_000
MAX_POOL_DECODED_BYTES = 4 * 1024 * 1024
MAX_EXAMPLES = 20
MAX_DYLIBS = 64
MAX_EVIDENCE = 10
HASH_CHUNK = 1024 * 1024

# Errors that a damaged or unsupported archive member can raise while it is read.
DECODE_ERRORS = (zipfile.BadZipFile, zlib.error, lzma.LZMAError, NotImplementedError,
                 RuntimeError, OSError, ValueError, EOFError)

RES_STRING_POOL = 0x0001
RES_XML = 0x0003
RES_XML_START_ELEMENT = 0x0102
UTF8_FLAG = 0x0100
ATTR_TYPE_STRING = 0x03
ATTR_TYPE_INT_DEC = 0x10
ATTR_TYPE_INT_HEX = 0x11

PROTO_VARINT = 0
PROTO_FIXED64 = 1
PROTO_LENGTH = 2
PROTO_FIXED32 = 5
# Field numbers from aapt2's Resources.proto: XmlNode.element, XmlElement.name and
# .attribute, XmlAttribute.name and .value.
PB_XMLNODE_ELEMENT = 1
PB_XMLELEMENT_NAME = 3
PB_XMLELEMENT_ATTRIBUTE = 4
PB_XMLATTRIBUTE_NAME = 2
PB_XMLATTRIBUTE_VALUE = 3

MH_MAGIC_32 = b"\xce\xfa\xed\xfe"
MH_MAGIC_64 = b"\xcf\xfa\xed\xfe"
FAT_MAGIC = b"\xca\xfe\xba\xbe"
CPU_ARM64 = 0x0100000C
CPU_NAMES = {0x0100000C: "arm64", 0x0C: "arm", 0x01000007: "x86_64", 0x07: "i386"}
LC_LOAD_DYLIBS = {0x0C, 0x20, 0x80000018, 0x8000001F, 0x80000023}  # 0x80000023: LC_LOAD_UPWARD_DYLIB
LC_ENCRYPTION = {0x21, 0x2C}

# Extension points confirmed in OWASP MASTG and in a published list of Apple extension
# targets. Other identifiers are reported raw as "unmapped" rather than given a guessed role.
EXTENSION_POINT_ROLES = {
    "com.apple.share-services": "share",
    "com.apple.keyboard-service": "keyboard",
    "com.apple.widgetkit-extension": "widget",
    "com.apple.photo-editing": "photo-editing",
    "com.apple.fileprovider-nonui": "file-provider",
    "com.apple.quicklook.preview": "quicklook-preview",
}

# Runtime-family markers. Patterns are regular expressions searched in module-relative
# (Android) or app-relative (iOS) member names; iOS also searches linked dylib names.
# Source notes for the less common names:
#   flutter:      libapp.so is a generic name, so on its own it is weak. Flutter builds
#                 also ship libflutter.so.
#   godot:        libgodot_android.so is named in Godot's Android docs, under libs/<arch>/.
#                 A root-level .pck is weak on iOS because the .pck name is generic: any
#                 game can ship one, so it is only a lead.
#   cocos2d:      libcocos.so (Creator 3.x; loaded with System.loadLibrary("cocos") in a
#                 forum reverse-engineering thread) and libcocos2dcpp.so or libcocos2djs.so
#                 (earlier templates, forum build logs). A module the project renames
#                 (for example libgame.so) is not matched.
#   unreal:       libUE4.so and libUnreal.so come from forum crash reports and an Epic loader
#                 call quoted in a forum thread. No official packaging document was found.
#   react-native: libreactnative.so is named in the React Native 0.76 release post.
#   dotnet (iOS): Microsoft.iOS.dll is the .NET for iOS binding name. Its placement in an app
#                 bundle is not checked, so it is weak.
ANDROID_FAMILIES = [
    {"id": "flutter", "name": "Flutter", "see": "references/optional-platforms.md §4",
     "strong": [r"^lib/[^/]+/libflutter\.so$", r"^assets/flutter_assets/"],
     "weak": [r"^lib/[^/]+/libapp\.so$"]},
    {"id": "react-native", "name": "React Native", "see": "references/hermes-react-native.md",
     "strong": [r"^assets/index\.android\.bundle$", r"^lib/[^/]+/libhermes\.so$",
                r"^lib/[^/]+/libreactnative\.so$", r"^lib/[^/]+/libreactnativejni\.so$"],
     "weak": [r"^lib/[^/]+/libjsc\.so$"]},
    {"id": "unity", "name": "Unity", "see": "references/optional-platforms.md §2",
     "strong": [r"^lib/[^/]+/libunity\.so$", r"^lib/[^/]+/libil2cpp\.so$",
                r"^assets/bin/Data/Managed/Metadata/global-metadata\.dat$",
                r"^assets/bin/Data/Managed/Assembly-CSharp\.dll$"],
     "weak": []},
    {"id": "dotnet", "name": ".NET / Xamarin / MAUI", "see": "references/optional-platforms.md §4",
     "strong": [r"^lib/[^/]+/libmonodroid\.so$", r"^lib/[^/]+/libaot-[^/]+\.so$",
                r"^assemblies/[^/]+\.dll$"],
     "weak": []},
    {"id": "cordova", "name": "Cordova web shell", "see": "references/web.md",
     "strong": [r"^assets/www/cordova\.js$"], "weak": [r"^assets/www/index\.html$"]},
    {"id": "capacitor", "name": "Capacitor / Ionic web shell", "see": "references/web.md",
     "strong": [r"^assets/capacitor\.config\.json$"], "weak": [r"^assets/public/index\.html$"]},
    {"id": "godot", "name": "Godot", "see": None,
     "strong": [r"^lib/[^/]+/libgodot_android\.so$"], "weak": []},
    {"id": "cocos2d", "name": "Cocos2d-x / Cocos Creator", "see": None,
     "strong": [r"^lib/[^/]+/libcocos2d[^/]*\.so$", r"^lib/[^/]+/libcocos\.so$"], "weak": []},
    {"id": "unreal", "name": "Unreal Engine", "see": None,
     "strong": [r"^lib/[^/]+/libUE4\.so$", r"^lib/[^/]+/libUnreal\.so$"], "weak": []},
]

IOS_FAMILIES = [
    {"id": "flutter", "name": "Flutter", "see": "references/optional-platforms.md §4",
     "strong": [r"(^|/)App\.framework/App$", r"(^|/)Flutter\.framework/Flutter$"], "weak": []},
    {"id": "react-native", "name": "React Native", "see": "references/hermes-react-native.md",
     "strong": [r"(^|/)main\.jsbundle$", r"(^|/)hermes\.framework/hermes$",
                r"(^|/)React\.framework/React$"],
     "weak": []},
    {"id": "unity", "name": "Unity", "see": "references/optional-platforms.md §2",
     "strong": [r"(^|/)UnityFramework\.framework/UnityFramework$",
                r"^Data/Managed/Metadata/global-metadata\.dat$"],
     "weak": []},
    {"id": "dotnet", "name": ".NET / Xamarin", "see": "references/optional-platforms.md §4",
     "strong": [r"(^|/)Xamarin\.iOS\.dll$"],
     "weak": [r"(^|/)mscorlib\.dll$", r"(^|/)Microsoft\.iOS\.dll$"]},
    {"id": "cordova", "name": "Cordova web shell", "see": "references/web.md",
     "strong": [r"^www/cordova\.js$"], "weak": [r"^www/index\.html$"]},
    {"id": "capacitor", "name": "Capacitor / Ionic web shell", "see": "references/web.md",
     "strong": [r"^capacitor\.config\.json$"], "weak": [r"^public/index\.html$"]},
    {"id": "godot", "name": "Godot", "see": None,
     "strong": [], "weak": [r"^[^/]+\.pck$"]},
    {"id": "playcover-playtools", "name": "PlayCover PlayTools shim", "see": "references/ios-playcover.md",
     "strong": [r"(^|/)PlayTools\.framework/PlayTools$"], "weak": []},
]

APP_RE = re.compile(r"^Payload/([^/]+\.app)/")
MODULE_MANIFEST_RE = re.compile(r"^([^/]+)/manifest/AndroidManifest\.xml$")
DEX_RE = re.compile(r"^(?:dex/)?classes\d*\.dex$")
LIB_RE = re.compile(r"^lib/([^/]+)/[^/]+\.so$")
DOTNET_RE = re.compile(r"^(?:assemblies/|assets/bin/Data/Managed/).*\.dll$")
APPEX_RE = re.compile(r"^PlugIns/([^/]+\.appex)/")
WATCH_RE = re.compile(r"^Watch/([^/]+\.app)/")
FRAMEWORK_RE = re.compile(r"^Frameworks/([^/]+\.framework)/")
EMBEDDED_DYLIB_RE = re.compile(r"^Frameworks/([^/]+\.dylib)$")
SC_INFO_RE = re.compile(r"^SC_Info/([^/]+\.(?:sinf|supp))$")

LIMITATIONS = [
    "Read only: members are listed and read in memory under size caps; nothing is extracted, executed, decrypted, or written",
    "Runtime hints are marker matches. An SDK can bundle a marker and a leftover file can keep one, so treat each hint as a lead to check",
    "The package and version come from a bounded read of the base manifest: binary XML for APKs, protobuf for AABs. Components, permissions, and signing are not decoded",
    "Mach-O fields come from the arm64 slice of a fat executable, or its only slice. cryptid 0 means not FairPlay-encrypted; it does not make the binary safe to run",
    "Extension roles combine the path convention with NSExtensionPointIdentifier when Info.plist parses. Unknown identifiers are reported raw as unmapped",
    "iTunesMetadata.plist is reported by presence only; its content is never read",
    "Split APK sets are inspected one file at a time",
]


class Malformed(Exception):
    """A structure is inconsistent or runs past the end of its member."""


class NotMachO(Exception):
    """The executable does not start with a Mach-O or fat magic."""


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_member(zf, name, cap):
    """Bytes of one member, or (None, status) when it is missing, too large, or unreadable."""
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None, "missing"
    if info.file_size > cap:
        return None, "too_large"
    try:
        with zf.open(info) as fh:
            data = fh.read(cap + 1)
    except DECODE_ERRORS:
        return None, "unreadable"
    if len(data) > cap:
        return None, "too_large"
    return data, "ok"


def _unique_matches(values, regex):
    found = set()
    for value in values:
        m = regex.match(value)
        if m:
            found.add(m.group(1))
    return sorted(found)


def classify(names):
    """Return (kind, detail): 'ipa' with app paths, 'aab' with module names, 'apk', or 'unrecognized'."""
    name_set = set(names)
    apps = sorted({"Payload/" + m.group(1) for m in (APP_RE.match(n) for n in names) if m})
    if apps:
        return "ipa", apps
    if "BundleConfig.pb" in name_set:
        return "aab", _unique_matches(names, MODULE_MANIFEST_RE)
    if "AndroidManifest.xml" in name_set:
        return "apk", []
    modules = _unique_matches(names, MODULE_MANIFEST_RE)
    if modules:
        return "aab", modules
    return "unrecognized", []


# ------------------------------------------------------------- binary XML ------
class _StringPool:
    """String pool that decodes an entry on first use, once per index.

    Offsets may alias one large string, so the total decoded bytes are capped. The cap
    bounds the work however many indices point at the same bytes.
    """

    def __init__(self, data, base, offsets, end, utf8):
        self._data = data
        self._base = base
        self._offsets = offsets
        self._end = end
        self._utf8 = utf8
        self._cache = {}
        self._decoded = 0

    def get(self, index):
        if not 0 <= index < len(self._offsets):
            return None
        if index not in self._cache:
            self._cache[index] = self._decode(self._base + self._offsets[index])
        return self._cache[index]

    def _decode(self, p):
        data, end = self._data, self._end
        if p >= end:
            raise Malformed("string offset is outside the pool")
        if self._utf8:
            _chars, p = _read_len8(data, p, end)
            size, p = _read_len8(data, p, end)
            if p + size > end:
                raise Malformed("string bytes run past the pool")
            text = data[p:p + size].decode("utf-8", "replace")
        else:
            units, p = _read_len16(data, p, end)
            size = 2 * units
            if p + size > end:
                raise Malformed("string bytes run past the pool")
            text = data[p:p + size].decode("utf-16-le", "replace")
        self._decoded += size
        if self._decoded > MAX_POOL_DECODED_BYTES:
            raise Malformed("string pool decodes more than %d bytes" % MAX_POOL_DECODED_BYTES)
        return text


def _read_len8(data, p, end):
    if p + 1 > end:
        raise Malformed("string length runs past the pool")
    first = data[p]
    if first & 0x80:
        if p + 2 > end:
            raise Malformed("string length runs past the pool")
        return ((first & 0x7F) << 8) | data[p + 1], p + 2
    return first, p + 1


def _read_len16(data, p, end):
    if p + 2 > end:
        raise Malformed("string length runs past the pool")
    first = struct.unpack_from("<H", data, p)[0]
    if first & 0x8000:
        if p + 4 > end:
            raise Malformed("string length runs past the pool")
        return ((first & 0x7FFF) << 16) | struct.unpack_from("<H", data, p + 2)[0], p + 4
    return first, p + 2


def _string_pool(data, off):
    if off + 28 > len(data):
        raise Malformed("string pool header is outside the file")
    ctype, hsize, csize = struct.unpack_from("<HHI", data, off)
    if ctype != RES_STRING_POOL or hsize < 28 or csize < hsize or off + csize > len(data):
        raise Malformed("string pool is missing or inconsistent")
    count, _styles, flags, strings_start = struct.unpack_from("<IIII", data, off + 8)
    if count > MAX_AXML_STRINGS:
        raise Malformed("string pool holds %d strings; the limit is %d" % (count, MAX_AXML_STRINGS))
    end = off + csize
    offsets_at = off + hsize
    if offsets_at + 4 * count > end:
        raise Malformed("string offsets run past the pool")
    offsets = struct.unpack_from("<%dI" % count, data, offsets_at) if count else ()
    pool = _StringPool(data, off + strings_start, offsets, end, bool(flags & UTF8_FLAG))
    return pool, end


def _manifest_attributes(data, pos, elem_end, hsz, pool):
    ext = pos + hsz
    if ext + 20 > elem_end:
        raise Malformed("element extension runs past its chunk")
    attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, ext + 8)
    if attr_size < 20:
        raise Malformed("attribute entry size %d is below 20" % attr_size)
    base = ext + attr_start
    out = {"package": None, "version_code": None, "version_name": None}
    for i in range(attr_count):
        at = base + i * attr_size
        if at + 20 > elem_end:
            raise Malformed("attribute runs past its element")
        _ns, name_i, raw, _size, _res, dtype, value = struct.unpack_from("<IIIHBBI", data, at)
        key = pool.get(name_i)
        if key in ("package", "versionName"):
            text = pool.get(raw)
            if text is None and dtype == ATTR_TYPE_STRING:
                text = pool.get(value)
            out["package" if key == "package" else "version_name"] = text
        elif key == "versionCode":
            if dtype in (ATTR_TYPE_INT_DEC, ATTR_TYPE_INT_HEX):
                out["version_code"] = value
            else:
                text = pool.get(raw)
                if text and text.isdigit():
                    out["version_code"] = int(text)
    return out


def parse_axml(data):
    """Package, versionCode, and versionName from the manifest element of binary XML."""
    if len(data) < 8:
        raise Malformed("too short to be binary XML")
    ctype, hsize, total = struct.unpack_from("<HHI", data, 0)
    if ctype != RES_XML or hsize < 8 or total > len(data):
        raise Malformed("not binary XML")
    pool, pos = _string_pool(data, hsize)
    end = min(total, len(data))
    while pos + 8 <= end:
        ctype, hsz, csz = struct.unpack_from("<HHI", data, pos)
        if csz < 8 or hsz < 8 or pos + csz > end:
            raise Malformed("XML chunk at %d is inconsistent" % pos)
        if ctype == RES_XML_START_ELEMENT:
            if hsz < 16 or csz < hsz + 20:
                raise Malformed("element chunk at %d is too short" % pos)
            name_index = struct.unpack_from("<I", data, pos + hsz + 4)[0]
            if pool.get(name_index) == "manifest":
                return _manifest_attributes(data, pos, pos + csz, hsz, pool)
        pos += csz
    raise Malformed("no manifest element")


# ----------------------------------------------------------- protobuf XML -------
def _proto_varint(data, pos, end):
    value, shift = 0, 0
    for _ in range(10):
        if pos >= end:
            raise Malformed("varint runs past its message")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
    raise Malformed("varint is longer than 10 bytes")


def _proto_fields(data, start, end):
    """(field number, wire type, value) for each field of one message.

    Length-delimited values are (start, end) spans into data, varints are ints, and
    fixed-width fields carry None.
    """
    pos = start
    while pos < end:
        key, pos = _proto_varint(data, pos, end)
        field, wire = key >> 3, key & 7
        if field == 0:
            raise Malformed("protobuf field number 0")
        if wire == PROTO_VARINT:
            value, pos = _proto_varint(data, pos, end)
        elif wire == PROTO_LENGTH:
            length, pos = _proto_varint(data, pos, end)
            if length > end - pos:
                raise Malformed("length-delimited field runs past its message")
            value = (pos, pos + length)
            pos += length
        elif wire in (PROTO_FIXED64, PROTO_FIXED32):
            width = 8 if wire == PROTO_FIXED64 else 4
            if width > end - pos:
                raise Malformed("fixed-width field runs past its message")
            value = None
            pos += width
        else:
            raise Malformed("unsupported protobuf wire type %d" % wire)
        yield field, wire, value


def _span_text(data, span):
    return data[span[0]:span[1]].decode("utf-8", "replace")


def _proto_attribute(data, span):
    name = value = None
    for field, wire, val in _proto_fields(data, span[0], span[1]):
        if wire == PROTO_LENGTH and field == PB_XMLATTRIBUTE_NAME:
            name = _span_text(data, val)
        elif wire == PROTO_LENGTH and field == PB_XMLATTRIBUTE_VALUE:
            value = _span_text(data, val)
    return name, value


def parse_proto_manifest(data):
    """Package, versionCode, and versionName from an aapt2 protobuf manifest (an XmlNode)."""
    element = None
    for field, wire, value in _proto_fields(data, 0, len(data)):
        if field == PB_XMLNODE_ELEMENT and wire == PROTO_LENGTH:
            element = value
            break
    if element is None:
        raise Malformed("XML node holds no element")
    name, attrs = None, {}
    for field, wire, value in _proto_fields(data, element[0], element[1]):
        if wire != PROTO_LENGTH:
            continue
        if field == PB_XMLELEMENT_NAME:
            name = _span_text(data, value)
        elif field == PB_XMLELEMENT_ATTRIBUTE:
            key, text = _proto_attribute(data, value)
            if key is not None:
                attrs.setdefault(key, text)
    if name != "manifest":
        raise Malformed("root element is %r, not manifest" % name)
    code = attrs.get("versionCode")
    return {
        "package": attrs.get("package"),
        "version_code": int(code) if code and code.isdigit() else None,
        "version_name": attrs.get("versionName"),
    }


def parse_manifest(data):
    """Binary XML (APK) or protobuf XML (AAB). Binary XML starts with the 0x0003 chunk type."""
    if data[:2] == b"\x03\x00":
        return parse_axml(data)
    return parse_proto_manifest(data)


def read_manifest(zf, name):
    data, status = read_member(zf, name, MAX_MANIFEST_BYTES)
    if data is None:
        return {"status": status, "source": name}
    try:
        attrs = parse_manifest(data)
    except Malformed as exc:
        return {"status": "unparsed", "source": name, "reason": str(exc)}
    return dict(attrs, status="ok", source=name)


# ------------------------------------------------------------ Mach-O -----------
def _fill(fh, buf, size):
    while len(buf) < size:
        chunk = fh.read(min(size - len(buf), 1 << 20))
        if not chunk:
            raise Malformed("member ends before the expected structure")
        buf.extend(chunk)


def _discard(fh, count):
    while count > 0:
        chunk = fh.read(min(count, 1 << 20))
        if not chunk:
            raise Malformed("member ends before the first slice")
        count -= len(chunk)


def _walk_load_commands(cmds, ncmds):
    dylibs, cryptid, off = [], None, 0
    for _ in range(ncmds):
        if off + 8 > len(cmds):
            raise Malformed("load command header runs past the table")
        cmd, cmdsize = struct.unpack_from("<II", cmds, off)
        if cmdsize < 8 or off + cmdsize > len(cmds):
            raise Malformed("load command size %d is invalid" % cmdsize)
        if cmd in LC_LOAD_DYLIBS and cmdsize >= 12 and len(dylibs) < MAX_DYLIBS:
            name_off = struct.unpack_from("<I", cmds, off + 8)[0]
            raw = cmds[off + name_off:off + cmdsize]
            name = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
            if name:
                dylibs.append(name)
        if cmd in LC_ENCRYPTION and cryptid is None and cmdsize >= 20:
            cryptid = struct.unpack_from("<I", cmds, off + 16)[0]
        off += cmdsize
    return dylibs, cryptid


def _fat_table(fh, buf):
    """(cputype, offset) for each slice of a fat header. buf already holds the first bytes."""
    _fill(fh, buf, 8)
    nfat = struct.unpack_from(">I", buf, 4)[0]
    if not 1 <= nfat <= 20:
        raise Malformed("implausible fat architecture count %d" % nfat)
    _fill(fh, buf, 8 + 20 * nfat)
    table = []
    for i in range(nfat):
        cputype, _subtype, offset, _size, _align = struct.unpack_from(">IIIII", buf, 8 + 20 * i)
        table.append((cputype, offset))
    return table


def _slice_header(fh):
    """Architecture, linked dylibs, and cryptid of the thin Mach-O at the current position."""
    buf = bytearray()
    _fill(fh, buf, 4)
    magic = bytes(buf[:4])
    if magic == MH_MAGIC_64:
        header = 32
    elif magic == MH_MAGIC_32:
        header = 28
    else:
        raise NotMachO()
    _fill(fh, buf, header)
    cputype, _subtype, _ftype, ncmds, sizeofcmds = struct.unpack_from("<IIIII", buf, 4)
    if sizeofcmds > MAX_MACHO_HEADER_BYTES:
        raise Malformed("load commands (%d bytes) exceed the read limit" % sizeofcmds)
    _fill(fh, buf, header + sizeofcmds)
    dylibs, cryptid = _walk_load_commands(bytes(buf[header:header + sizeofcmds]), ncmds)
    return cputype, dylibs, cryptid


def macho_summary(zf, name):
    """Architectures, cryptid, and linked dylibs of a Mach-O or fat executable.

    A fat executable is read at its arm64 slice when it has one, since that is the slice
    PlayCover runs on Apple Silicon, and otherwise at its first slice. The slice read is named.
    """
    out = {"status": "ok", "slice": None, "archs": [], "cryptid": None,
           "encryption": "unknown", "linked_dylibs": []}
    try:
        info = zf.getinfo(name)
        with zf.open(info) as fh:
            head = bytearray()
            _fill(fh, head, 4)
            table = _fat_table(fh, head) if bytes(head) == FAT_MAGIC else None
        if table is None:
            with zf.open(info) as fh:
                cputype, dylibs, cryptid = _slice_header(fh)
            out["archs"] = [CPU_NAMES.get(cputype, "cpu-0x%08x" % cputype)]
        else:
            _cpu, offset = next(((c, o) for c, o in table if c == CPU_ARM64), table[0])
            if offset > MAX_SLICE_SKIP:
                raise Malformed("slice offset %d is beyond the read limit" % offset)
            out["archs"] = [CPU_NAMES.get(c, "cpu-0x%08x" % c) for c, _ in table]
            with zf.open(info) as fh:
                _discard(fh, offset)
                cputype, dylibs, cryptid = _slice_header(fh)
        out["slice"] = CPU_NAMES.get(cputype, "cpu-0x%08x" % cputype)
    except NotMachO:
        return dict(out, status="not-macho")
    except Malformed as exc:
        return dict(out, status="malformed", reason=str(exc))
    except (KeyError, *DECODE_ERRORS):
        return dict(out, status="unreadable")
    out["cryptid"] = cryptid
    if cryptid is None:
        out["encryption"] = "no-encryption-command"
    else:
        out["encryption"] = "not-encrypted" if cryptid == 0 else "encrypted"
    out["linked_dylibs"] = dylibs
    return out


# ------------------------------------------------------- runtime families ------
def _hits(candidates, patterns):
    if not patterns:
        return []
    compiled = [re.compile(p) for p in patterns]
    return [c for c in candidates if any(rx.search(c) for rx in compiled)]


def match_families(candidates, families, scope):
    hints = []
    for fam in families:
        strong = _hits(candidates, fam["strong"])
        weak = _hits(candidates, fam["weak"])
        if not strong and not weak:
            continue
        evidence = list(dict.fromkeys(strong + weak))
        hints.append({
            "scope": scope,
            "family": fam["id"],
            "name": fam["name"],
            "strength": "strong" if strong else "weak",
            "evidence": evidence[:MAX_EVIDENCE],
            "evidence_count": len(evidence),
            "see": fam["see"],
        })
    return hints


# ------------------------------------------------------------- Android ---------
def module_record(module, rels):
    dex = sorted(r for r in rels if DEX_RE.match(r))
    libs = sorted(r for r in rels if LIB_RE.match(r))
    native = {}
    for r in libs:
        abi = LIB_RE.match(r).group(1)
        native[abi] = native.get(abi, 0) + 1
    assets = {}
    for r in rels:
        if r.startswith("assets/"):
            rest = r[len("assets/"):]
            key = rest.split("/", 1)[0] if "/" in rest else "(files)"
            assets[key] = assets.get(key, 0) + 1
    top_assets = sorted(assets.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_EXAMPLES]
    return {
        "name": module,
        "dex_count": len(dex),
        "dex_files": dex[:MAX_EXAMPLES],
        "native_libs": dict(sorted(native.items())),
        "native_lib_count": len(libs),
        "native_lib_examples": libs[:MAX_EXAMPLES],
        "asset_dirs": dict(top_assets),
        "dotnet_assemblies": sum(1 for r in rels if DOTNET_RE.match(r)),
    }


def android_report(zf, names, kind, module_names):
    notes = []
    name_set = set(names)
    if kind == "apk":
        groups = {None: list(names)}
        manifest_rel = "AndroidManifest.xml"
    else:
        # One pass over the archive, grouping member names by their module directory.
        groups = {m: [] for m in module_names}
        for n in names:
            head, sep, rest = n.partition("/")
            if sep and head in groups:
                groups[head].append(rest)
        manifest_rel = "manifest/AndroidManifest.xml"
    primary = None
    if kind == "aab":
        primary = "base" if "base" in groups else module_names[0]
    modules, hints, manifest = [], [], None
    for module, rels in groups.items():
        record = module_record(module, rels)
        modules.append(record)
        scope = "apk" if module is None else "module:" + module
        hints.extend(match_families(rels, ANDROID_FAMILIES, scope))
        is_primary = module is None or module == primary
        if is_primary and record["dex_count"] == 0:
            notes.append("%s has no classes.dex: native-only, or DEX sits in another split"
                         % ("the APK" if module is None else "module " + module))
        if is_primary:
            prefix = "" if module is None else module + "/"
            manifest = read_manifest(zf, prefix + manifest_rel)
    if manifest is None:
        manifest = {"status": "missing"}
    if manifest["status"] != "ok":
        notes.append("manifest not decoded: %s" % manifest["status"])
    section = {
        "modules": modules,
        "manifest": manifest,
        "bundle_config": "BundleConfig.pb" in name_set,
    }
    return section, hints, notes


# ----------------------------------------------------------------- iOS ---------
def read_plist(zf, name):
    data, status = read_member(zf, name, MAX_PLIST_BYTES)
    if data is None:
        return None, status
    try:
        value = plistlib.loads(data)
    except Exception:  # plistlib raises several types on malformed input
        return None, "unparsed"
    if not isinstance(value, dict):
        return None, "unparsed"
    return value, "ok"


def info_summary(value, status):
    if value is None:
        return {"status": status}

    def text(key):
        v = value.get(key)
        return v if isinstance(v, str) else None

    return {
        "status": "ok",
        "bundle_id": text("CFBundleIdentifier"),
        "name": text("CFBundleDisplayName") or text("CFBundleName"),
        "executable": text("CFBundleExecutable"),
        "version": text("CFBundleVersion"),
        "short_version": text("CFBundleShortVersionString"),
        "minimum_os": text("MinimumOSVersion"),
        "package_type": text("CFBundlePackageType"),
    }


def extension_records(zf, names, prefix):
    found = set()
    for n in names:
        if n.startswith(prefix):
            m = APPEX_RE.match(n[len(prefix):])
            if m:
                found.add(m.group(1))
    out = []
    for appex in sorted(found):
        value, status = read_plist(zf, prefix + "PlugIns/" + appex + "/Info.plist")
        point, bundle_id = None, None
        if value is not None:
            ext = value.get("NSExtension")
            if isinstance(ext, dict) and isinstance(ext.get("NSExtensionPointIdentifier"), str):
                point = ext["NSExtensionPointIdentifier"]
            bid = value.get("CFBundleIdentifier")
            bundle_id = bid if isinstance(bid, str) else None
        if point is None:
            role = "unknown"
        else:
            role = EXTENSION_POINT_ROLES.get(point, "unmapped")
        out.append({
            "name": appex,
            "path": prefix + "PlugIns/" + appex,
            "path_role": "app-extension",
            "point": point,
            "role": role,
            "bundle_id": bundle_id,
            "info": status,
        })
    return out


def macho_for(zf, name_set, path):
    if path not in name_set:
        return {"path": path, "status": "missing"}
    return dict(macho_summary(zf, path), path=path)


def ios_report(zf, names, app_paths):
    notes = []
    app_dir = app_paths[0]
    if len(app_paths) > 1:
        notes.append("%d app bundles in Payload; inspected %s" % (len(app_paths), app_dir))
    prefix = app_dir + "/"
    name_set = set(names)
    rels = [n[len(prefix):] for n in names if n.startswith(prefix)]
    info_value, info_status = read_plist(zf, prefix + "Info.plist")
    info = info_summary(info_value, info_status)
    exec_name = info.get("executable")
    if not exec_name:
        exec_name = os.path.basename(app_dir)[:-len(".app")]
        if info_status == "ok":
            notes.append("CFBundleExecutable is missing; assumed %s" % exec_name)
        else:
            notes.append("Info.plist %s; executable assumed %s" % (info_status, exec_name))
    executable = macho_for(zf, name_set, prefix + exec_name)
    linked = executable.get("linked_dylibs") or []
    if executable.get("encryption") == "encrypted":
        notes.append("the %s slice of the main executable is FairPlay-encrypted (cryptid %s); "
                     "run it only from a decrypted dump (references/optional-platforms.md §1)"
                     % (executable.get("slice") or "main", executable.get("cryptid")))
    candidates = rels + ["linked: " + d for d in linked]
    hints = match_families(candidates, IOS_FAMILIES, "app")
    section = {
        "bundle_path": app_dir,
        "app_bundles": len(app_paths),
        "info": info,
        "executable": executable,
        "frameworks": _unique_matches(rels, FRAMEWORK_RE),
        "embedded_dylibs": _unique_matches(rels, EMBEDDED_DYLIB_RE),
        "extensions": extension_records(zf, names, prefix),
        "watch_apps": _unique_matches(rels, WATCH_RE),
        "sc_info": _unique_matches(rels, SC_INFO_RE),
        "itunes_metadata": "present" if "iTunesMetadata.plist" in name_set else "absent",
    }
    return section, hints, notes


# ------------------------------------------------------------- driver ----------
def _starts_with_zip(path):
    with open(path, "rb") as fh:
        return fh.read(4) in (b"PK\x03\x04", b"PK\x05\x06")


def inventory(path, max_entries=DEFAULT_MAX_ENTRIES):
    report = {
        "path": os.path.abspath(path),
        "size": os.path.getsize(path),
        "sha256": sha256_of(path),
        "status": "ok",
        "kind": "unrecognized",
        "route": None,
        "entries": 0,
        "android": None,
        "ios": None,
        "runtime_hints": [],
        "notes": [],
        "limitations": list(LIMITATIONS),
    }
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, zlib.error, NotImplementedError, ValueError):
        report["status"] = "malformed" if _starts_with_zip(path) else "unrecognized"
        return report
    with zf:
        names = zf.namelist()
        report["entries"] = len(names)
        if len(names) > max_entries:
            report["status"] = "too_many_entries"
            return report
        kind, detail = classify(names)
        report["kind"] = kind
        if kind == "unrecognized":
            report["status"] = "unrecognized"
            return report
        if kind == "aab" and not detail:
            report["status"] = "malformed"
            report["notes"] = ["AAB has no module manifests: nothing to inventory"]
            return report
        if kind == "ipa":
            report["route"] = "ios"
            report["ios"], report["runtime_hints"], report["notes"] = ios_report(zf, names, detail)
        else:
            report["route"] = "android"
            report["android"], report["runtime_hints"], report["notes"] = android_report(
                zf, names, kind, detail)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inventory an APK, AAB, or IPA without extracting it (JSON to stdout).")
    ap.add_argument("path", help="APK, AAB, or IPA file (read only; never extracted or executed)")
    ap.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES,
                    help="refuse archives with more members than this (default 200000)")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.path):
        sys.stderr.write("ERROR: not a regular file: %s\n" % args.path)
        return 2
    if args.max_entries < 1:
        sys.stderr.write("ERROR: --max-entries must be at least 1\n")
        return 2
    try:
        report = inventory(args.path, args.max_entries)
    except OSError as exc:
        sys.stderr.write("ERROR: cannot read %s: %s\n" % (args.path, exc))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
