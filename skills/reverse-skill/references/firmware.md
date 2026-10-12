# firmware.md — firmware images (F0–F5, static only)

Load this when the input is a device firmware image, an OTA package, or an extracted
root filesystem. The scope is static analysis of supplied images. Emulation, hardware
access (UART, JTAG, SPI or flash reads), and any interaction with a live device need
separate, explicit scope from the device's owner. Until that scope is agreed, record
those steps as `out_of_scope` in the ledger.

Scope details: [operating-scope.md](operating-scope.md#firmware-targets).

## Phases

| Phase | Goal | Tools |
|-|-|-|
| F0 Identify | Container layers: OTA package, raw image, or rootfs | `scripts/target_identify.py`; a region listing from a caller-installed `binwalk` as a second opinion |
| F1 Unpack | Extract with a caller-installed `unblob`, recording hashes, tool version, and partial status | `scripts/firmware_unpack.py FIRMWARE --out DIR` with `UNBLOB_COMMAND` set to an absolute path |
| F2 Rootfs survey | Init scripts, accounts, key and certificate names, web roots, version banners | `scripts/firmware_survey.py DIR/extracted/<name>_extract --out DIR/survey`; unpack prints the rootfs candidates |
| F3 Routes | Map CGI and web-server routes to their handlers | Route candidates from `survey.json`, then `rg` for each handler. The list is a candidate list, not a route table |
| F4 Native handoff | Select the ELF binaries that matter (web server, daemons, updater) and open them with the architecture-matched tool | IDA (primary); Ghidra fallback where IDA coverage for the architecture is weak. `constscan.py` reads both endiannesses; `cryptoinstr.py` is AArch64 only |
| F5 Report | Facts with evidence; the input and tool hashes come from the ledger's provenance fields | `scripts/findings.py` |

## Unpacking

- Keep unblob's sandbox on. If it reports a sandbox failure, record the message and
  stop. Do not disable the sandbox to get past it.
- Status: `complete` means exit 0, no unknown, encrypted or unextracted chunks in the
  report, and at least one entry. `partial` means chunks are flagged, the report is
  unreadable, or the run failed after producing entries. `failed` means nothing was
  extracted, or the input changed during the run. Do not reconstruct flagged regions,
  and do not claim the image is fully recovered.
- unblob calls external extractors from `PATH` (7z and debugfs are examples). A missing
  extractor lowers coverage, and the manifest names the dependencies unblob reports.
  In testing, zip and tar.gz inputs failed without 7z.
- Output directories are created mode 0700, because extracted trees hold password
  hashes and private keys.
- A successful extraction does not establish a valid partition layout, a signature
  check, or runtime behavior.

## Rootfs survey

- `survey.json` lists ELF architecture per binary, init scripts, accounts (with
  password-hash *scheme* only, never the hash), key and certificate files (kind and
  hash, never contents), web roots, route-like strings, and version banners.
- Route candidates are strings. Confirm each one by reading its handler before it
  becomes a fact.
- `survey.json` is sensitive. Each route candidate carries up to 80 bytes before and
  160 bytes after its match, which can include nearby strings from the same file. The
  survey directory is created mode 0700; keep it that way.
- A version banner does not prove that a build is vulnerable. Record the version
  and compare it against the vendor's advisories as a separate, cited step.

## OTA packages

- An Android OTA ZIP usually carries `payload.bin` (A/B update format) and
  metadata. Route the updater's signature-verification code to F4 as a crypto
  target.
- Public keys found in the image are recorded by name and hash from the survey.
  Whether a key is meant to be public is the vendor's decision, not something
  this skill can assume.

## Companion apps

- Many devices ship a companion app. The app's request builders (Android P1–P5 or
  iOS iP) and the firmware's route candidates often describe the same protocol from
  two sides. Record a match as a fact in each session that cites the other
  session's fact IDs and artifacts. Keep the two ledgers separate.

## Architectures and crypto

- Confirm the processor module for the target architecture before starting F4.
  IDA's decompiler availability depends on the license and the processor module.
- `constscan.py` finds table constants in either byte order, so it works for big-endian
  MIPS as well as little-endian ARM. A hit is still a fingerprint, not a name: follow
  `crypto-id.md`.
- `cryptoinstr.py` detects AArch64 crypto instructions. For other architectures, do
  not claim an instruction-level fingerprint.

## Headerless images

A raw bootloader or MCU image has no header that names its CPU or load address. Supply both
yourself; never infer them from a `.bin` suffix or from bytes `target_identify.py` could not
classify.

- Record the CPU family, endianness and base address as supplied facts, with how each was
  derived, so a later reader can check them.
- Derive the base from the image. On a Cortex-M image the first word is the initial stack
  pointer, in RAM, and the second word is the reset handler address with the Thumb bit set.
  Clear that bit to get the entry. Elsewhere, pick the base at which many pointer-sized values
  land on string starts or function prologues.
- ARM and AArch64 entries are 4-byte aligned. A Thumb entry is 2-byte aligned. x86 entries may
  start at any byte.
- Ghidra headless takes the loader and base on the command line: `-loader BinaryLoader
  -loader-baseAddr ADDR -processor LANGUAGE_ID`. IDA asks for the processor and the loading
  address when it opens a headerless file.
- A wrong base shows up as strings with no cross-references and call targets that fall outside
  the image. Check those before trusting any address in the ledger.
