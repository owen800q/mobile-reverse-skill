# desktop.md — desktop software (D0–D7)

Load this when the target is a Windows, macOS, or Linux program, an Electron, Tauri,
or NW.js application, a .NET assembly, a Java archive, or a PyInstaller bundle.
Start with `scripts/target_identify.py PATH` (D0). It reports the format, the
architecture, whether a .NET CLI header is present, whether a PyInstaller cookie
was found, and a route key.

Scope comes first: [operating-scope.md](operating-scope.md#desktop-targets). In
particular, protection analysis (licensing, activation, DRM, anti-tamper) is
limited to software you develop or are authorized to test. See the section below.

## Phases

| Phase | Goal | Tools |
|-|-|-|
| D0 Identify | Format, architecture, managed and packed markers, route key | `scripts/target_identify.py`; `file` and a hex dump for anything unclear |
| D1 Electron | Extract `app.asar`, check its integrity metadata, then run W1–W6 on the JavaScript | `scripts/asar_extract.py`, then `web.md` |
| D2 Native | Import the PE, Mach-O, or ELF into IDA; find the feature entry point through strings, imports, and cross-references | IDA Pro (primary; `idalib` for headless work). Ghidra as a fallback where IDA coverage for the architecture is weak |
| D3 .NET | Decompile managed code; deobfuscate protected assemblies first | A caller-installed .NET decompiler CLI (for example `ilspycmd` from ILSpy) at a pinned version; de4dot-style deobfuscation where the assembly is protected |
| D4 Java | Decompile `.jar` or `.class` | `jadx` reads both, the same engine the Android route uses |
| D5 PyInstaller | Extract the bundle; decompile `.pyc` files with a decompiler that matches the bundled Python version | A caller-installed extractor (for example `pyinstxtractor`) and a `.pyc` decompiler |
| D6 Capture | Observe network traffic and runtime values from the user's own installed copy | HAR export or mitmproxy with the user's own CA; SSLKEYLOGFILE for clients that honor it (verify per app); Frida on Windows or macOS for the user's own copy |
| D7 Report | Facts with evidence and provenance; R1–R3 apply unchanged | `scripts/findings.py` (`init --input`, `add-tool`) |

## Electron (D1)

- `asar_extract.py` reads the ASAR header directly and extracts into a new
  directory. It checks any integrity metadata the archive declares.
- A mismatch means the archive bytes differ from the hashes it declares. That can
  be tampering, a repack, or a build quirk. Record it; do not assume which.
- Unpacked entries live in `app.asar.unpacked`. Supply that directory if it exists;
  otherwise they are reported as unavailable.

## Native binaries (D2)

- IDA is the primary engine. Ghidra is an optional fallback for architectures
  where IDA's decompiler coverage is weak. It is caller-installed and recorded
  with `findings.py add-tool`, so each result names the engine that produced it.
- `ida_target_loader.py` is built around an Android `.so` flow. For PE or Mach-O
  input, open the file in IDA directly, or extend the loader and verify it on a
  real PE before relying on it.
- Use the same fingerprint discipline as Android: `constscan.py` reads constants in
  both endiannesses. `cryptoinstr.py` detects AArch64 crypto instructions only, so
  for x86 or other architectures rely on constants and call structure.
- eBPF tools (ecapture, stackplz) run on Linux and Android in this skill. There is
  no low-footprint eBPF branch for Windows or macOS.

## macOS

- Mach-O and code signing follow the iOS mode: local Frida, `codesign` entitlements,
  and hardened-runtime limits. See `ios-playcover.md`.

## Windows

- Frida can attach to a local process you run, but anti-debug and code-integrity
  checks are common. Record the failure and the check that caused it. Do not stack
  bypasses without a stated, in-scope reason.

## Capture (D6)

- Prefer passive capture first: a HAR export or a proxy with the user's own CA
  shows what the program sends. Pair it with `har_parse.py`.
- `SSLKEYLOGFILE` lets a tool decrypt captured TLS for clients that honor it. Many
  Chromium-based and NSS-based clients do. Verify that the specific program does.

## Protection analysis (licensing, activation, DRM, anti-tamper)

Scope: [operating-scope.md](operating-scope.md#desktop-targets). This workflow is for
software you develop, or software you are authorized to test under a written
engagement. It is defensive: its output is a finding and a fix, not a working bypass.

1. Locate the validation. Is it a local check, a server response, or both? Establish
   this from static evidence first.
2. Test where the decision is made. A check that only runs on the client is a
   finding in itself, because the server has to enforce the entitlement.
3. Work in a private copy. Record the minimum evidence that the check can be
   passed. Stop there.
4. Report the weakness with its evidence, and the mitigation: server-side
   enforcement, signed entitlements, or hardening. Name the test that would
   confirm the fix.
5. Do not package, publish, or share a modified binary, a keygen, or a license
   emulator. Keep the working copy in `SESSION_DIR` with restricted access.

Do not use this workflow to unlock commercial software you did not build, even for
private use. Record that step as `out_of_scope` in the ledger and stop it.
