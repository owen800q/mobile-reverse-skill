# Optional Platforms (parked branches)

**Not part of the default Android-login flow.** The main `SKILL.md` triages a standard Java/Kotlin +
optional-`.so` Android app; that path never loads this file. You are here only because **triage
detected a non-default target** and routed to the matching section below:

- **Unity / IL2CPP** — app ships `libil2cpp.so` + `global-metadata.dat`, or jadx shows a near-empty
  app dominated by `com.unity3d.*`. → §2
- **Packed / 加固 DEX** — jadx yields almost no real Java, classes appear at runtime, or the
  manifest's Application class belongs to a known packer (乐固/梆梆/娜迦/爱加密). → §3
- **iOS** — target is an `.ipa` / jailbroken device, not an APK. → §1. **Running under
  PlayCover on a Mac?** §1 only *obtains* a decrypted binary; the full non-jailbroken
  workflow (capture, instrumentation, signer reversal) is in **`ios-playcover.md`**.
- **Flutter / .NET** — `libapp.so`+`libflutter.so`, or Xamarin/.NET assemblies. → §4
- **HarmonyOS** — a `.hap` / `.hsp` / `.app` pack from `target_identify.py` (route `harmony`). → §5

Each section is self-contained: **when to load it · the tool · the key steps · why**. Do the
platform-specific extraction here, then return to the normal flow (`android-triage.md` for API
extraction, `ida-workflow.md` for native, `signing-replay.md` for reconstruction).

## Contents

1. [iOS app decryption (砸壳)](#1-ios-app-decryption-砸壳)
2. [Unity / IL2CPP symbol dump](#2-unity--il2cpp-symbol-dump)
3. [DEX unpacking / packers (加固)](#3-dex-unpacking--packers-加固)
4. [Flutter and .NET (pointers)](#4-flutter-and-net-pointers)
5. [HarmonyOS packages (identification)](#5-harmonyos-packages-identification)

---

## 1. iOS app decryption (砸壳)

**When:** the target is an iOS app. App Store binaries are FairPlay-encrypted, so IDA/Ghidra/Hopper
see garbage until you dump the **decrypted** Mach-O from a running process. Needs a **jailbroken
device** with SSH + `frida-server`.

**Tool:** `frida-ios-dump` (`https://github.com/P4nda0s/frida-ios-dump`) — attaches Frida to the
live process and writes decrypted pages back out as an `.ipa`.

**Key steps:**

1. **Prep the device.** `frida-server` running on device; host has `frida`+`frida-tools`. Verify:
   `frida-ps -H <device_ip> -a` (also lists Bundle IDs). Match `frida-server` **major version** to
   host `frida` — mismatch is the #1 failure.
2. **Build the agent** (this fork uses a TS agent): `npm install --ignore-scripts` then
   `npx frida-compile dump.ts -o dist/dump.js`. Without this, `dump.py` won't run.
3. **Launch the target app and keep it foreground/unlocked** — the dumper reads decrypted memory
   from the live process.
4. **Dump:** `python3 dump.py -H <ip> -u mobile -P <pw> <bundle_id>` (fresh jailbreak default pw
   `alpine`). Produces `<app>.ipa`.
5. **Verify decryption — this is the whole point:**
   ```bash
   unzip -o app.ipa -d out/
   otool -l out/Payload/App.app/App | grep -A4 LC_ENCRYPTION_INFO
   ```
   **`cryptid 0` = decrypted.** `cryptid 1` = still encrypted → app wasn't running / dump failed,
   retry. Apps with jailbreak detection may kill themselves first — bypass detection then re-dump.

Then: load the Mach-O into IDA, `class-dump` for ObjC headers, and continue with the normal native/
symbol flow. (If it's a Unity iOS build, `UnityFramework` inside the IPA feeds §2; a Flutter iOS
build feeds §4.)

**Running the app under PlayCover instead of a jailbroken device?** A decrypted IPA (`cryptid 0`,
whether dumped as above or already decrypted) installs into **PlayCover** on an Apple-Silicon Mac
and runs as a native process — no device in the loop. That is a first-class path with its own
end-to-end guide: **`ios-playcover.md`** covers local-host Frida, plaintext-below-TLS capture,
`get-task-allow` re-signing, anti-debug, and the ObjC/Swift/Mach-O tooling. This §1 remains the way
to *obtain* the decrypted binary that PlayCover requires.

---

## 2. Unity / IL2CPP symbol dump

**When:** APK has `lib/<abi>/libil2cpp.so` + `assets/bin/Data/Managed/Metadata/global-metadata.dat`
(iOS: `UnityFramework` + `Data/.../global-metadata.dat`). IL2CPP AOT-compiles C# to native and
**strips names from the binary but keeps them in the metadata** — recover the address↔name mapping
and the stripped `.so` becomes navigable.

**Tool:** `Il2CppDumper`. **Metadata version dictates the fork** — check it first:

```bash
xxd -l 8 global-metadata.dat   # magic af1bb1fa, then version LE: 27 00 00 00 = 0x27 = v39
```

| Metadata version | Unity | Tool |
|-|-|-|
| ≤ 29 | 2021 and earlier | Perfare/Il2CppDumper (original) |
| 39 (0x27) | Unity 6 (6000.x) | **roytu/Il2CppDumper, branch `v39`** |

The original errors `not a supported version[39]` on Unity 6 — that's your signal to switch to the
`roytu` v39 fork.

**Key steps:**

1. Extract `libil2cpp.so` (pick the arch you'll analyze) and `global-metadata.dat` from the APK/IPA.
2. Build + run the v39 fork:
   ```bash
   git clone -b v39 https://github.com/roytu/Il2CppDumper.git && cd Il2CppDumper
   DOTNET_ROLL_FORWARD=LatestMajor dotnet run --project Il2CppDumper/Il2CppDumper.csproj \
     -c Release --framework net8.0 -- <libil2cpp.so> <global-metadata.dat> out/
   ```
   `DOTNET_ROLL_FORWARD=LatestMajor` lets it run on newer .NET. **Exit 134** (`Console.ReadKey`) is
   normal in non-interactive mode — the dump still completed. macOS SIGKILL → `codesign -s - <bin>`.
3. Outputs: **`script.json`** (addresses + names + signatures, for IDA/Ghidra import), `dump.cs`
   (readable C# class dump with RVA/VA — your quickest grep reference), **`il2cpp.h`** (C structs),
   `ida_py3.py`.
4. **Import into IDA:** open `libil2cpp.so`, put `script.json` beside `ida_py3.py`, run it via
   `File → Script file…` → every function auto-renames to `Class$$Method`. Then
   `Load file → Parse C header file… → il2cpp.h` for type info. (Ghidra: `ghidra_with_struct.py`.)

Now grep `dump.cs` for the login/sign method, jump to its address in the renamed IDB, and continue.
`script.json` addresses are **decimal** — `hex(40865744)` for IDA.

---

## 3. DEX unpacking / packers (加固)

**When:** jadx decodes the APK but there's almost no real application code — just a packer stub —
or classes only materialize at runtime. The real DEX is decrypted in memory by the packer's class
loader, so you must dump it **from a running process after the shell has unpacked it**. Navigate past
the splash screen first, or the real DEX isn't loaded yet.

Two approaches; both need root/device access:

**A) ptrace dumper (`panda-dex-dumper`)** — native tool, attaches via `ptrace`, scavenges DEX images
from process memory. **arm64 + root required.**

```bash
adb push panda-dex-dumper /data/local/tmp/ && adb shell chmod +x /data/local/tmp/panda-dex-dumper
PID=$(adb shell pidof <pkg>)   # launch the app first if empty
adb shell "cd /data/local/tmp && ./panda-dex-dumper -p $PID"
adb pull /data/local/tmp/panda/ ./        # dumped DEX land here
adb shell rm -rf /data/local/tmp/panda /data/local/tmp/panda-dex-dumper   # clean up
```
Multiple DEX out is normal for packed apps — pull them all.

**B) Frida hook (`assets/frida/dex_dump.js`)** — intercepts DEX loading at the **lowest common choke
points**, so it's packer-agnostic (every shell must eventually hand real DEX to ART):

- `libart.so` `DexFile::OpenMemory` (native, tries several mangled symbol names across Android
  versions) — the catch-all;
- `dalvik.system.InMemoryDexClassLoader` (Java, Android 8+ in-memory loading — 乐固 etc.);
- `dalvik.system.DexClassLoader` (file-path loaders that drop-then-load).

It validates the `dex\n` magic, reads `file_size` from the header, dedups, and writes to
`/sdcard/dump/`. Run: `frida -U -f <pkg> -l assets/frida/dex_dump.js --no-pause`, exercise the app,
then `adb pull /sdcard/dump/`.

**Which to use:** Frida is easier and version-robust and catches in-memory-only shells; the ptrace
dumper is the fallback when Frida is detected/blocked or you want a full memory sweep. After pulling,
feed the DEX back through `android-triage.md` (jadx → API extraction) as if it were the base APK.

---

## 4. Flutter and .NET (pointers)

Brief — reach for these only if triage fingerprints the framework; then follow the tool's own docs.

**Flutter** — app ships `libflutter.so` + `libapp.so`; **HTTP does not use the Java network stack**,
so OkHttp/interceptor hooks and the standard `android-triage.md` login playbook find nothing, and
Flutter has its own TLS (system CA hooks won't intercept). `libapp.so` is a **Dart AOT snapshot**,
not normal native code. Options: **reFlutter** (`https://github.com/Impact-I/reFlutter`) patches the
engine to log traffic / disable cert pinning; **Blutter** (`https://github.com/worawit/blutter`)
parses the snapshot and emits IDA scripts + Dart class/method names for static analysis. Match the
tool build to the exact Flutter/Dart engine version (snapshot format is version-locked).

**.NET / Xamarin** — the app is C# compiled to **managed assemblies**, not Java. Look under
`assemblies/` in the APK (may be compressed/AOT'd or bundled in `libmonodroid.so` /
`libaot-*.so`). Extract the `*.dll` and decompile with **dnSpy / ILSpy / dotPeek** — that's where the
login/sign logic lives. If assemblies are AOT-compiled to native, fall back to the standard
`ida-workflow.md` native path.

---

## 5. HarmonyOS packages (identification)

**When:** `target_identify.py` reports `harmonyos package (hap|hsp)` or `harmonyos app pack`. This
skill has no HarmonyOS tooling; this section only says what the identification proves and where
the usual routes still apply.

**What the identification proves.** A verified ZIP whose name ends `.hap` / `.hsp` and whose root
has `module.json` (Stage model) or `config.json` (FA model). A `.app` root that lists `.hap` /
`.hsp` children or `pack.info` is a distribution App Pack; its children are listed by path and not
opened. Everything is read from member names. Manifest content, bytecode and signatures are not read.

**Routes that still apply:**

1. **Native libraries** — `libs/<abi>/*.so` are ordinary ELF files. Unzip the member, then use
   `ida-workflow.md` and `native-tracing.md` exactly as for an Android `.so`.
2. **Ark bytecode** — `.abc` members are Ark bytecode, not DEX. jadx and apktool do not read them.
   Record the member path and SHA-256 and treat the ArkTS logic as not yet read, rather than
   assuming it matches any visible JavaScript.
3. **FA-model JavaScript** — `config.json` packages may carry plain JavaScript under the module's
   assets; the `web.md` route applies to that source.
4. **Signing** — `META-INF/` entries show that signing material exists. They do not show that the
   signature is valid or who signed it.

Do not carry Android conclusions over: there is no `AndroidManifest.xml`, no Dalvik, and no
Java-layer hook surface here.
