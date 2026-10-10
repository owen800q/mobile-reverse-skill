# ios-playcover.md — iOS mode (apps running under PlayCover)

**Not the default Android flow.** You are here because triage found an **iOS** target —
an `.ipa`, or an app installed in **PlayCover** on an Apple-Silicon Mac — and `SKILL.md`
routed you to iOS mode. The goal is unchanged: from a bundle to a **verified**
reconstruction of the target API (endpoints, request fields, the client-side signing /
encryption scheme) plus a replay PoC. The ledger (`state-schema.md`), the crypto-id
fingerprint discipline (`crypto-id.md`), Gate D / TLS-fingerprint (`signing-replay.md` §5),
and the report step are **shared with the Android flow** — only the platform mechanics below
change.

## Why PlayCover changes the model

PlayCover runs an iOS (arm64) app as a **native local macOS process** — no device, no
jailbreak, no emulator. That single fact rewrites the toolchain:

| Android flow | iOS-mode (PlayCover) equivalent |
|-|-|
| `adb`, `frida-server`, rooted device | **local host Frida** (`frida -n/-f/-p`) — the process is on *this* Mac |
| ecapture / stackplz (eBPF uprobe) | **Frida Interceptor on the TLS record layer** — no eBPF on macOS |
| root | **`get-task-allow`** (an ad-hoc re-sign) — SIP stays on |
| APK is not encrypted | app must be **FairPlay-decrypted** first (`cryptid 0`) — a prerequisite |
| jadx / Java / Kotlin / JNI / `.so` | **ObjC/Swift + Mach-O + dylibs** (`ipsw`, IDA/Hopper/Ghidra) |
| `/proc/<pid>/mem` heap scan | on-disk container sources (Cache.db, PlayKeychain, defaults) |

Frida injects via the **task port**, so hardened-runtime / library-validation mostly don't
block *attach*; the real gates are `get-task-allow` (permission) and the app's own
**anti-debug** (timing). Both are handled below.

## The workflow (iP0–iP6)

| Phase | Goal | Tooling |
|-|-|-|
| iP0 Decode | Decrypted IPA/.app → Mach-O, cryptid, dylibs/frameworks, ObjC/Swift dump, engine fingerprint | `scripts/decode_ipa.sh`, `ipsw`, `otool` |
| iP1 Static API | Endpoint + request builder in ObjC/Swift; demangle Swift | `ipsw class-dump`, `strings`, `swift-demangle`, IDA/Hopper/Ghidra |
| iP2 Capture | Passive container scan, then plaintext-below-TLS dump | `scripts/ios_container.py`, `scripts/ios_capture.sh` + `assets/frida/ios/ssl_dump.js` |
| iP3 Align | Map captured fields to the builder; watch the crypto sink | `assets/frida/ios/hook_cccrypto.js`, PlayKeychain secrets |
| iP4 Native + crypto ID | Reverse the signer in the Mach-O; name the primitive by fingerprint | IDA/Hopper/Ghidra + `scripts/constscan.py`, `scripts/cryptoinstr.py` |
| iP5 Reconstruct + verify | Rebuild the scheme, recompute the captured sig, replay | `scripts/sign_rebuilder.py`, `assets/templates/python_http_validation.py.tmpl` |
| iP6 Report | Endpoint + field map + scheme + verification, from the ledger | `scripts/findings.py show/validate` |

Init the ledger exactly as on Android (`findings.py init --target <bundle-id> --goal ...`).

---

## iP0 — Decode

**When:** you have an `.ipa` or a PlayCover-installed `.app`. **Tool:** `scripts/decode_ipa.sh`.

1. **The binary must be decrypted.** PlayCover cannot run a FairPlay-encrypted App Store
   IPA — it re-signs ad-hoc, which invalidates the FairPlay path, so an encrypted binary
   won't launch. There is **no decrypt-on-Mac path**: obtain a decrypted IPA off-platform
   with a jailbroken dump (`frida-ios-dump` / `flexdecrypt` / `bagbak` — see
   `optional-platforms.md` §1). Community "decrypted IPA" mirrors exist but are a
   **supply-chain risk** — prefer your own dump.
2. **Verify + survey:** `bash scripts/decode_ipa.sh app.ipa` (or the installed `.app`). It
   reports **cryptid** (`0` = decrypted, good; `1` = still encrypted → re-dump), arch,
   linked dylibs (`otool -L`), embedded frameworks, and the **engine fingerprint**
   (PlayTools / Unity / Flutter / Hermes-RN), and runs a best-effort ObjC/Swift dump
   (`ipsw class-dump`, falling back to `dsdump`/`class-dump`).
3. **Route on the engine** (see *Engines & transports* below): Unity → `optional-platforms.md`
   §2; Flutter → §4; Hermes/RN → `hermes-react-native.md`.

**Without macOS tools:** `python3 scripts/mobile_inventory.py app.ipa` reads the cryptid of the arm64 slice (or the only slice),
linked dylibs, and engine hints in one read-only pass, and adds each extension's role (share,
widget, keyboard, and so on) from its `NSExtensionPointIdentifier`. An identifier it does not
recognise is reported raw as `unmapped`, not guessed. `decode_ipa.sh` still does the class dump.

**Why:** IDA/Ghidra/Hopper see garbage on an encrypted Mach-O, and the engine decides which
capture methods will even work.

## iP1 — Static API

**When:** you have a decrypted Mach-O + a class dump. **Tool:** `ipsw class-dump`, `strings`,
IDA/Hopper/Ghidra, `swift-demangle`.

- **`ipsw` is the primary tool** (actively maintained: `ipsw class-dump`, `ipsw macho info`,
  dyld-cache extraction). `dsdump`/`class-dump(-swift)` are **version-fragile** on Swift 5.7+
  ABI — treat their output as best-effort, not authoritative. `class-dump` (Nygard) is
  ObjC-only and unmaintained but still parses arm64.
- **Swift:** symbols are mangled `$s…`; demangle with `xcrun swift-demangle`. The Swift type
  metadata sections (`__swift5_types`, `__swift5_proto`) are the source of truth — IDA's
  Swift parser or `ipsw`/`dsdump` read them. Generics/witness tables make Swift harder than
  ObjC; for ObjC-heavy apps, a **Frida runtime `ObjC.classes` enumeration** sidesteps static
  mangling entirely.
- Anchor on endpoint strings (`auth/login`, host names, header names like `X-Sign`) and
  trace to the request builder. Log facts at `PATTERN` with verbatim refs, same as Android.

## iP2 — Capture

Two steps, cheap first.

### Passive: read what's already on disk — `scripts/ios_container.py`
PlayCover apps carry iOS container semantics, so the app has often already persisted useful
data. `python3 scripts/ios_container.py --bundle-id <id>` globs the install, then reads:

- **NSURLCache `Cache.db`** (SQLite, CFURLCache schema). **Reliable:** request URL +
  timestamps. **Best-effort:** headers/method (archived NSKeyedArchiver blobs) and response
  bodies (inline, or on disk in `fsCachedData/`). **Absent:** POST request bodies (only
  cacheable GETs are stored). Frequently empty (ephemeral sessions / `no-store`) — that's
  normal, not a failure.
- **PlayKeychain** — readable on-disk plists **only when PlayCover's PlayKeychain toggle is
  enabled**; otherwise items live in the macOS login keychain (`security find-generic-password`).
  A useful source for stored tokens/keys.
- **NSUserDefaults** plist — config, flags, sometimes tokens.

Records are merged into `requests.json` (same shape as ecapture output) for the ledger.

### Live: plaintext below TLS — `scripts/ios_capture.sh` + `assets/frida/ios/ssl_dump.js`
The ecapture analog. There is **no eBPF on macOS**, so instead of a kernel uprobe we attach a
Frida Interceptor to the TLS record layer and read the buffer the app itself handles — after
decryption / before encryption. **No proxy, no CA, pinning irrelevant.**

```bash
scripts/ios_capture.sh <ExecutableName>            # attach (frida -n)
scripts/ios_capture.sh <ExecutableName> --spawn --anti   # spawn-gate + anti-debug
```

It runs Frida, logs to `ssl_dump.log`, and reassembles HTTP with the **existing**
`ecapture_parse.py` (`ssl_dump.js` emits the same `Write/Read Data` + hexdump framing).
Critical mechanics baked into the script (get them wrong and it silently prints nothing):

- **Resolve the symbol at runtime, not by name.** Native & RN apps use the **system
  `libboringssl.dylib`** (via Network.framework/CFNetwork), which lives in the dyld shared
  cache — there is no on-disk file to `nm`. `ssl_dump.js` **enumerates loaded modules** for
  `SSL_read`/`SSL_write`.
- **`SSL_read` fills its buffer on return** — read it in `onLeave` by `retval` length.
  `SSL_write`'s plaintext is already in the buffer in `onEnter`.
- **HTTP/3 / QUIC is a blind spot.** QUIC has its own crypto and bypasses the SSL record
  layer, so an h3 connection produces **no output**. Force TLS-over-TCP (disable h3 / block
  UDP 443) or accept the gap.

**Fallback (terminating proxy):** `scripts/ios_capture.sh --proxy` sets the macOS system
proxy (`networksetup`) and prints the mitmproxy + System-keychain CA-trust recipe; add
`assets/frida/ios/ssl_unpin.js` if the app pins. Against the skill's no-proxy default — use it
only when you need to *edit*/replay traffic. **Flutter ignores the system proxy** (own CA).

## iP3 — Align

Map each captured field to its builder and find the **crypto sink** (Gate A). Watch it with
`assets/frida/ios/hook_cccrypto.js`:

- **CommonCrypto** (`CCCrypt`/`CCCryptorUpdate`/`CCHmac`, from `libcommonCrypto.dylib`) — the
  primary target; most AES/HMAC request signing routes through here. Dumps key/IV/in/out.
- **CryptoKit is backed by corecrypto, not BoringSSL** — the hook also covers
  `libcorecrypto` (`cchmac`/`ccdigest`/`ccaes_*`). Caveat: CryptoKit may **inline** small
  ops, so hooks can miss them → reverse the app's own wrapper and hook it by address (reuse
  `assets/templates/frida_runtime_observe.js.tmpl`).

Pull stored secrets from PlayKeychain (iP2). Record the input→signature oracle as a fact.

## iP4 — Native + crypto ID

Load the Mach-O into **IDA/Hopper/Ghidra** (they read Mach-O directly — no loader dance).
Then the **reused, platform-agnostic** fingerprint tools apply unchanged: `constscan.py`
(crypto-constant tables) and `cryptoinstr.py` (ARM64 crypto-extension instructions — same
arm64 as Android). Name the primitive only with a fingerprint, per `crypto-id.md` and R2.

## iP5 — Reconstruct + verify

`sign_rebuilder.py` and the replay template are platform-agnostic — recompute the captured
signature and, on a match, promote the fact to `VERIFIED`. Build the replay PoC from
`assets/templates/python_http_validation.py.tmpl`. **Gate D still applies**: a byte-correct
signature that still 4xx-es is TLS fingerprinting (`signing-replay.md` §5) — though for
native/RN the ClientHello reflects **Apple's** boringssl (it characterizes the platform, not
the app) unless the app brings its own TLS (Flutter, or a custom pinned stack).

## iP6 — Report

Identical to Android: `findings.py validate` (must pass R1/R2), then emit endpoint + field map
+ signing scheme + the passing replay from the ledger.

---

## get-task-allow re-sign (when attach is refused)

If `frida -n` returns `task_for_pid`/`EPERM`, the app lacks `get-task-allow`. It is **not** a
restricted entitlement, so an **ad-hoc** re-sign carries it — SIP can stay on. Do it right:

```bash
# 1) DUMP the app's current entitlements (do NOT invent a minimal plist).
codesign -d --entitlements :- "<App>.app/<Exec>" > ent.plist        # then edit
# 2) MERGE get-task-allow into ent.plist, keeping disable-library-validation,
#    keychain-access-groups, and app-groups (stripping them breaks PlayTools/keychain).
#      <key>com.apple.security.get-task-allow</key><true/>
# 3) Sign INSIDE-OUT (nested code first, main executable last). NOT --deep.
find "<App>.app/Frameworks" -name '*.dylib' -o -name '*.framework' | while read f; do
  codesign -f -s - "$f"; done
codesign -f -s - --entitlements ent.plist "<App>.app/<Exec>"        # get-task-allow ONLY here
# 4) VERIFY.
codesign -dv --verbose=4 "<App>.app/<Exec>" 2>&1 | grep -i get-task-allow
codesign --verify --verbose "<App>.app"
```

- Re-sign the **installed** bundle (in PlayCover's Applications dir). **PlayCover may re-sign
  at install/launch and revert your change** — re-check `codesign -dv` after launching; if it
  reverts, patch-then-let-PlayCover-install, or re-sign after each launch.
- `get-task-allow` belongs **only on the main executable** (the task you attach to). Nested
  code just needs a valid signature.
- `DevToolsSecurity -enable` is usually **not** required for same-user attach to a
  get-task-allow process (it governs lldb/taskgated); harmless if you run it.

## Anti-debug & the spawn-vs-attach tension

`get-task-allow` grants attach permission; it does **not** defeat `ptrace(PT_DENY_ATTACH)` or
a `sysctl`/`P_TRACED` probe. If those run early (a constructor or `main`), `frida -n` (attach)
arrives too late and the app dies. The instinct is to spawn (`frida -f`) and hook first — but
**spawning a PlayCover app is unreliable**: PlayCover's launch sets up the container /
environment and injects PlayTools (an added `LC_LOAD_DYLIB`) that a bare `posix_spawn` may not
reproduce. Escalation:

1. **Spawn + early-instrument** if it reproduces the env:
   `scripts/ios_capture.sh <Exec> --spawn --anti` (loads `anti_debug_bypass.js` first, which
   NOPs `ptrace`/`syscall(SYS_ptrace)`, clears the `sysctl` `P_TRACED` flag, and hides
   PlayTools/frida from `_dyld_get_image_name` scans).
2. **Static NOP-patch** the `ptrace`/`svc #0x80` anti-debug call sites in the Mach-O and
   re-sign (above) — the most reliable path when spawn misbehaves.
3. **`DYLD_INSERT_LIBRARIES` / constructor gadget** as a middle path.

If a check still bites after all three, **request a second analysis if delegation is available** (see *When stuck*
in `SKILL.md`) with the exact check and what you tried.

## Engines & transports

The Frida TLS-record capture covers most stacks, but via **different modules**:

| Engine | Networking | Proxy? | Cache.db? | Frida-SSL hook? | Notes |
|-|-|-|-|-|-|
| Native (ObjC/Swift) | NSURLSession | ✅ | ✅ | ✅ system libboringssl | the common case |
| React Native / Hermes | NSURLSession | ✅ | ✅ | ✅ system libboringssl | JS builders in `.jsbundle` → `hermes-react-native.md` |
| Flutter | own Dart stack | ❌ own CA | ❌ | ⚠️ **stripped** symbols | pattern-scan / reFlutter; Dart snapshot in `App.framework/App` → `optional-platforms.md` §4 |
| Custom TCP (non-HTTP) | raw socket / NWConnection | ❌ | ❌ | ✅ if TLS-over-TCP | else `socket_dump.js` |

- **Flutter** statically links its own BoringSSL with stripped symbols — `getExportByName`
  fails; `ssl_dump.js` reports "not found" and you fall back to a byte-pattern scan or
  reFlutter. This is a prime **second-analysis** opportunity.
- **Custom TCP:** `socket_dump.js` hooks `nw_connection_send` (payload is a **`dispatch_data_t`**,
  extracted via `dispatch_data_apply`) and BSD `send/recv` for true raw sockets.
  `nw_connection_receive` delivers into a **completion block** → hard to capture; prefer
  `ssl_dump.js` if the transport is TLS. If the framing is app-encrypted, pair with
  `hook_cccrypto.js` (Gate A generalized: crypto/framing above the socket).

## Assets (iOS)

`assets/frida/ios/` — load with local host Frida (`frida -n/-f`):
- `ssl_dump.js` — plaintext below TLS (the ecapture analog; default capture).
- `ssl_unpin.js` — BoringSSL custom-verify + NSURLSession challenge bypass (proxy path only).
- `hook_cccrypto.js` — CommonCrypto + corecrypto (CryptoKit) crypto-sink observer.
- `anti_debug_bypass.js` — ptrace/sysctl/dyld-scan/env-spoof (load at spawn).
- `socket_dump.js` — non-HTTP / raw-socket transports.
- `assets/templates/frida_runtime_observe.js.tmpl` (shared) — Interceptor sign-function I/O
  logger; works on a Mach-O export or address.

## See also

- `crypto-id.md`, `ida-workflow.md`, `signing-replay.md` (§5 JA3), `state-schema.md` — shared.
- `hermes-react-native.md` — RN/Hermes JS bundle (point it at the iOS `.jsbundle`).
- `optional-platforms.md` — §1 how to obtain a decrypted IPA; §2 Unity/IL2CPP; §4 Flutter.
- `SKILL.md` "When stuck — knowledge search and a second analysis" — for the hard steps above.

