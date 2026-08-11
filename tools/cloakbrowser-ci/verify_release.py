#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PINNED_KEY_B64 = "MKFKwIhUcKWq5xTuNA0Ovg99njcDEcEJvmWYYhApvaU="


def parse_manifest(raw: bytes) -> tuple[str | None, dict[str, str]]:
    version = None
    hashes: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if line.startswith("version="):
            version = line.split("=", 1)[1].strip()
            continue
        parts = line.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            hashes[parts[1].strip()] = parts[0].lower()
    return version, hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--archive-name", required=True)
    args = parser.parse_args()

    manifest = args.manifest.read_bytes()
    signature = base64.b64decode(args.signature.read_bytes().strip(), validate=True)
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PINNED_KEY_B64))
    public_key.verify(signature, manifest)

    declared, hashes = parse_manifest(manifest)
    if declared != args.version:
        raise SystemExit(f"manifest version mismatch: {declared!r} != {args.version!r}")
    expected = hashes.get(args.archive_name)
    if expected is None:
        raise SystemExit(f"manifest has no hash for {args.archive_name}")
    actual = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"archive SHA-256 mismatch: {actual} != {expected}")

    print(
        json.dumps(
            {
                "signature": "Ed25519 verified",
                "version": declared,
                "archive": str(args.archive),
                "sha256": actual,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
