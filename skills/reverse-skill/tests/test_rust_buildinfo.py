#!/usr/bin/env python3
"""Tests for scripts/rust_buildinfo.py using synthetic ELF64 files with a .dep-v0 section."""
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "rust_buildinfo.py"
sys.path.insert(0, str(SCRIPT.parent))

import rust_buildinfo as rb  # noqa: E402

PACKAGES = {
    "format": 0,
    "packages": [
        {"name": "app", "version": "0.1.0", "source": "local", "root": True, "dependencies": [1, 2]},
        {"name": "serde", "version": "1.0.200", "source": "crates.io", "dependencies": []},
        {"name": "cc", "version": "1.0.0", "source": "crates.io", "kind": "build", "dependencies": []},
    ],
}


def elf64(sections):
    """A minimal little-endian ELF64 with the given (name, bytes) sections plus .shstrtab."""
    names = [name for name, _ in sections] + [".shstrtab"]
    strtab = b"\x00" + b"".join(n.encode() + b"\x00" for n in names)
    payload, offsets = bytearray(), {}
    base = 64
    blobs = [(n, b) for n, b in sections] + [(".shstrtab", strtab)]
    for name, blob in blobs:
        offsets[name] = base + len(payload)
        payload += blob
    shoff = base + len(payload)
    headers = bytearray(64)  # the null section header
    name_pos = 1
    for name, blob in blobs:
        headers += struct.pack("<IIQQQQIIQQ", name_pos, 1, 0, 0, offsets[name], len(blob), 0, 0, 1, 0)
        name_pos += len(name) + 1
    ident = b"\x7fELF" + bytes([2, 1, 1]) + b"\x00" * 9
    header = ident + struct.pack("<HHIQQQIHHHHHH", 2, 62, 1, 0, 0, shoff, 0, 64, 0, 0, 64,
                                 len(blobs) + 1, len(blobs))
    return bytes(header) + bytes(payload) + bytes(headers)


def dep_section(doc):
    return zlib.compress(json.dumps(doc).encode())


class RustBuildinfoTest(unittest.TestCase):
    def write(self, data):
        d = tempfile.mkdtemp()
        p = Path(d) / "bin"
        p.write_bytes(data)
        return str(p)

    def test_reads_packages_edges_and_root(self):
        path = self.write(elf64([(".dep-v0", dep_section(PACKAGES))]))
        info = rb.read_binary_info(path)
        self.assertTrue(info["found"])
        self.assertEqual(info["section"]["name"], ".dep-v0")
        self.assertEqual(info["section"]["format_version"], 0)
        self.assertEqual([p["name"] for p in info["packages"]], ["app", "serde", "cc"])
        self.assertEqual(info["root_indices"], [0])
        self.assertEqual(info["dependency_edge_count"], 2)
        self.assertEqual(info["packages"][2]["kind"], "build")
        self.assertEqual(info["packages"][1]["kind"], "runtime")

    def test_unknown_fields_are_kept_under_extra(self):
        doc = {"packages": [{"name": "x", "version": "1", "source": "git", "future": 7}]}
        info = rb.read_binary_info(self.write(elf64([(".dep-v0", dep_section(doc))])))
        self.assertEqual(info["packages"][0]["extra"], {"future": 7})

    def test_rustc_commit_paths_are_listed(self):
        commit = "a" * 40
        blob = b"panicked at /rustc/" + commit.encode() + b"/library/core/src/x.rs\x00"
        info = rb.read_binary_info(self.write(elf64([(".dep-v0", dep_section(PACKAGES)), (".rodata", blob)])))
        self.assertEqual(info["rustc_commits"], [{"commit": commit, "count": 1}])

    def test_missing_section_is_not_found(self):
        info = rb.read_binary_info(self.write(elf64([(".text", b"\x90" * 16)])))
        self.assertFalse(info["found"])
        self.assertIn("no .dep-v0", info["error"])

    def test_trailing_bytes_after_zlib_stream_are_malformed(self):
        info = rb.read_binary_info(self.write(elf64([(".dep-v0", dep_section(PACKAGES) + b"junk")])))
        self.assertFalse(info["found"])
        self.assertIn("after the zlib stream", info["error"])

    def test_dependency_index_out_of_range_is_malformed(self):
        doc = {"packages": [{"name": "a", "version": "1", "source": "s", "dependencies": [5]}]}
        info = rb.read_binary_info(self.write(elf64([(".dep-v0", dep_section(doc))])))
        self.assertFalse(info["found"])
        self.assertIn("out of range", info["error"])

    def test_inflate_limit_is_enforced(self):
        big = {"packages": [{"name": "a" * 200000, "version": "1", "source": "s"}]}
        blob = zlib.compress(json.dumps(big).encode())
        # The ratio cap is 64 times the compressed size, so this well-formed stream is refused.
        with self.assertRaises(ValueError):
            rb.inflate_section(blob)


if __name__ == "__main__":
    unittest.main()
