# desktop.md — desktop software (D0–D8)

Load this when the target is a Windows, macOS, or Linux program, an Electron, Tauri,
or NW.js application, a .NET assembly, a Java archive, or a PyInstaller bundle.
Start with `scripts/target_identify.py PATH` (D0). It reports the format, the
architecture, whether a .NET CLI header is present, whether a PyInstaller cookie
was found, and a route key.

Scope: [operating-scope.md](operating-scope.md#desktop-targets). Protection analysis
(D6) is for research and defense. It describes how a protection mechanism works and
where its decisions are made. It does not bypass, patch, or skip a check.

## Phases

| Phase | Goal | Tools |
|-|-|-|
| D0 Identify | Format, architecture, managed and packed markers, route key | `scripts/target_identify.py`; `file` and a hex dump for anything unclear |
| D1 Electron | Extract `app.asar`, check its integrity metadata, then run W1–W6 on the JavaScript | `scripts/asar_extract.py`, then `web.md` |
| D2 Native | Import the PE, Mach-O, or ELF into IDA; find the feature entry point through strings, imports, and cross-references | IDA Pro (primary; `idalib` for headless work). Ghidra as a fallback where IDA coverage for the architecture is weak |
| D3 .NET | Decompile managed code; deobfuscate protected assemblies first | A caller-installed .NET decompiler CLI (for example `ilspycmd` from ILSpy) at a pinned version; de4dot-style deobfuscation where the assembly is protected |
| D4 Java | Decompile `.jar` or `.class` | `jadx` reads both, the same engine the Android route uses |
| D5 PyInstaller | Extract the bundle; decompile `.pyc` files with a decompiler that matches the bundled Python version | A caller-installed extractor (for example `pyinstxtractor`) and a `.pyc` decompiler |
| D6 Protection mechanisms (research) | Inventory the indicators, locate their decision points, observe the boundary in the user's own run, classify the design, and write up the mechanism with evidence | `scripts/protection_inventory.py`; IDA for decision points; D7 capture for the boundary; `findings.py` |
| D7 Capture | Observe network traffic and runtime values from the user's own installed copy, as evidence for other phases | HAR export or a proxy with the user's own CA; SSLKEYLOGFILE for clients that honor it (verify per app); Frida on Windows or macOS for the user's own copy |
| D8 Report | Facts with evidence and provenance; R1–R3 apply unchanged | `scripts/findings.py` (`init --input`, `add-tool`) |

## Electron (D1)

- `asar_extract.py` reads the ASAR header directly and extracts into a new
  directory. It checks SHA256 integrity metadata, whole-file and per block, for each
  entry that declares it. An integrity object that uses another algorithm, or is
  malformed, is reported as unavailable and is not compared. It does not verify the
  ElectronAsarIntegrity value that the host app stores.
- Each entry's `integrity` value in the manifest is `verified`, `mismatch`, `absent`
  (no integrity object declared) or `unavailable`. A mismatch means the bytes do not
  match the SHA256 that the archive header recorded for that entry. The cause is not
  established: it can be tampering, a repack, or a build quirk. Record it; do not
  assume which. An unpacked entry has no bytes in the archive, so its hash is checked
  against the companion file in `app.asar.unpacked`.
- Unpacked entries live in `app.asar.unpacked`. Supply that directory if it exists;
  otherwise they are reported as unavailable.
- `electron_ipc_map.py DIR --out FILE` maps the IPC surface statically, one line at a
  time. It pairs each channel's request side with its handler (`invoke` with `handle`,
  renderer `send` with main `on`, main `webContents.send` with renderer `on`) and lists
  the `contextBridge.exposeInMainWorld` names that are string literals on the call's
  line, with file and line. A channel name is read
  only from a string literal that is the whole first argument on its line. Any other
  first argument, such as `'app:' + name` or a variable, is listed under `dynamic` with
  its text and is never paired. A `contextBridge` name that is not such a literal is
  listed under `dynamic_exposed`. A call is matched only when its name and opening
  parenthesis are on one line; when its first argument is not complete on that line, it
  is listed under `dynamic` with the text found there. Other calls split across lines
  are not matched. Files over 16 MiB, symlinks with a scanned extension, and symlinked
  directories are listed under `skipped` and not read. `unhandled` means a request or
  send with no receiver of the matching kind; `unused` means no request or send was
  found. These are leads only.
- `cdp_script_inventory.py EVENTS --out FILE` inventories the scripts that a recorded
  CDP log reports as parsed (`Debugger.scriptParsed` events), for a page or
  Node/Electron process. A script with no such event in the log does not appear. It
  does not attach, evaluate or set breakpoints. Recording the log is a live step, so it
  needs the scope in `operating-scope.md` first. Each run appends its log entries to
  `trace.jsonl` beside FILE, with no script URLs or script content.

## Go binaries

- `go_buildinfo.py BINARY` reads the Go version, main module, dependencies with
  replacements, and build settings from the inline build-info block, without running the
  binary. It scans the whole file and reports the first block that decodes, so a copy of
  the block placed earlier in the file is reported in place of the toolchain's. Go's
  debug/buildinfo searches only the build-info section or the writable data range. Build
  settings, including any `-ldflags` value, are not redacted: review the output before
  sharing it. `go_version_valid` is a format check on the version string only, so a
  development build reports false. A block from a build before Go 1.18 is listed as
  undecoded (`encoding` pointer, `decoded` false). `found` is false, and the exit code is
  1, when no inline block decodes; `block_count` and `undecoded_blocks` tell that apart
  from a binary with no block.

## Native binaries (D2)

- IDA is the primary engine. Ghidra is an optional fallback for architectures where
  IDA's decompiler coverage is weak. It is caller-installed and recorded with
  `findings.py add-tool`, so each result names the engine that produced it.
- `ida_target_loader.py` is built around an Android `.so` flow. For PE or Mach-O
  input, open the file in IDA directly, or extend the loader and verify it on a real
  PE before relying on it.
- Use the same fingerprint discipline as Android: `constscan.py` reads constants in
  both endiannesses. `cryptoinstr.py` detects AArch64 crypto instructions only, so
  for x86 or other architectures rely on constants and call structure.
- eBPF tools (ecapture, stackplz) run on Linux and Android in this skill. There is no
  low-footprint eBPF branch for Windows or macOS.

## macOS

- Mach-O and code signing follow the iOS mode: local Frida, `codesign` entitlements,
  and hardened-runtime limits. See `ios-playcover.md`.

## Windows

- Frida can attach to a local process you run, but anti-debug and code-integrity
  checks are common. Record the failure and the check that caused it. That record is
  itself a finding about the mechanism.

## Protection mechanisms (D6, research)

This phase covers how a licensing, activation, DRM, anti-tamper, integrity, pinning,
or packing mechanism is built, where its decisions are made, and what it depends on.
The output is a mechanism description with evidence, the uncertainties, and
design-level mitigations. It is not a method for defeating the mechanism.

1. **Inventory (M0).** Run `python3 "$SKILL_ROOT/scripts/protection_inventory.py" <path>`.
   It lists indicator names and markers with byte offsets: anti-debugging APIs,
   code-signing checks, licensing terms, license-server URLs, pinning APIs, packer
   markers, anti-VM and root checks, and instrumentation-detection strings. A hit
   shows that a name is present. It does not show that the code runs or that a check
   is enforced. Weak hits are generic words; cite them only in context.
2. **Locate decision points (M1).** For each strong hit, find the code that references
   it: a cross-reference in IDA, or the function that reads the string. Record the
   function as a fact with a verbatim quote from the disassembly or decompiler (R1).
   Describe what the code checks and what it does with the result.
3. **Observe the boundary (M2).** Run the program normally and capture what it sends
   and receives for licensing or activation (D7). Record the request and response
   shapes and what the client does with each field. Do not change a response, and do
   not supply one the server did not send.
4. **Classify the design (M3).** Where is the authoritative decision made: on the
   client, on the server, or on both? What does the server verify, and what does it
   trust from the client? Where are keys and entitlements stored, and in what form?
   Which integrity checks cover which code, and do they cover one another? Each answer
   needs a fact with evidence. Mark anything you cannot establish as unknown.
5. **Write up (M4).** Describe the scheme, the evidence for each claim, what remains
   uncertain, and mitigations in design terms: server-side entitlement checks, keys
   held server-side, integrity checks in more than one place, and monitoring. Name a
   test the vendor can run to confirm each mitigation. Describe weaknesses by design
   class, for example "the check exists only on the client", not as a working method
   against a specific build.

Not included in this phase: patching or skipping a check; generating keys, licenses,
or activation responses; emulating a license server; altering or replaying responses
to pass a check; disabling an integrity or anti-debug check to run the software; or
publishing a method that defeats a specific product. Record a request for any of
these as `out_of_scope` in the ledger, and continue with M0–M4.

## Capture (D7)

- Prefer passive capture first: a HAR export or a proxy with the user's own CA shows
  what the program sends. Pair it with `har_parse.py`.
- `SSLKEYLOGFILE` lets a tool decrypt captured TLS for clients that honor it. Many
  Chromium-based and NSS-based clients do. Verify that the specific program does.
