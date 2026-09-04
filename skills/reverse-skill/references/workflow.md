# reverse-skill — combined mobile RE workflow

> **Precondition:** Load this file only after `SKILL.md` has established a concrete
> app target, a specific analysis objective, and authorized-use context. Treat
> `references/`, `scripts/`, and `assets/` paths as relative to the skill root.

> **Authorized-use only.** This is a defensive / research workflow for apps and
> accounts you own or are explicitly authorized to test (your own app, a scoped
> pentest, security research, CTF). It documents how a client builds its own
> requests so the behavior can be understood and verified. It is not for
> unauthorized access to third-party systems. If a request looks like it targets
> someone else's account or infrastructure without authorization, stop and say so.

Document a mobile app feature end to end: from a package name to a documented,
**verified** reconstruction of the target API — its endpoints, its request
fields, and the client-side signing / encryption scheme — plus a replay PoC that
demonstrates the scheme is understood.

Typical invocation:

```
/reverse-skill ./app.apk document the login request flow for my staging app
```

The goal is freeform. Parse from it: the **target** (package name or APK path)
and the **objective** (which feature/API — login, checkout, a specific endpoint,
a signature header). Do not infer a default objective; the preflight must establish it before this workflow loads.

## How to use this skill

This file is the router. Each phase links to a reference in `references/` and
scripts in `scripts/`; load a reference only when you enter that phase, so the
working context stays small. Run scripts from the skill directory. Most take
`--out <session_dir>` (default `./re_out`); the IDA-phase scripts
(`resolve_native_target.py`, `ida_target_loader.py`) use `--output-dir` instead,
and `ida_export.py` defaults `--out` to `./re_out/ida` — check a script's
`--help` when unsure.

**Start every run by creating the ledger** — one `findings.json` is the shared
state across all phases and the thing that keeps conclusions honest:

```bash
python3 scripts/findings.py --out ./re_out init --target <pkg> --goal "<objective>"
```

Read `references/state-schema.md` once up front: it defines the Fact /
Intent / Hypothesis records, the 5-rung evidence ladder, and the two rules
`findings.py validate` enforces (no claim above PATTERN without a verbatim quote;
no crypto-primitive name without a fingerprint). These rules are what stop
confident fiction — honor them.

## Prerequisites (degrade gracefully)

Host: `python3`, `adb`, `jadx`, `apktool`, `frida`/`frida-tools`, and **IDA Pro
9.3** (with `idalib` activated for the headless path). Device: a **rooted**
Android phone/emulator (arm64, recent kernel) for the eBPF and Frida tooling.
eBPF capture/tracing uses **gojue/ecapture** for TLS (and optionally the
ecaptureQ GUI) and **SeeFlowerX/stackplz** for native function / syscall /
hardware-breakpoint tracing — the same low-detection kernel-side surface applied
beyond TLS. If a tool is missing, each script prints an install hint and you
continue with what is available — never fake a step you could not run; record it
as not-done in the ledger.

**iOS / PlayCover mode** needs instead: an **Apple-Silicon Mac** running
**PlayCover** with the target installed, host **`frida`/`frida-tools`** (local,
no device), **`ipsw`** (primary Mach-O/ObjC/Swift tool) plus `otool`/`codesign`/`lipo`
(Xcode Command Line Tools), and optionally `mitmproxy`. A **FairPlay-decrypted IPA**
(`cryptid 0`) is a prerequisite obtained off-platform (jailbroken dump — see
`references/optional-platforms.md` §1). See `references/ios-playcover.md`.

## The workflow

Phases are a default order, not a rigid pipeline — a single session revisits
earlier phases as evidence arrives. Update `findings.py set-phase N` as you go.

| Phase | Goal | Reference | Key tooling |
|-|-|-|-|
| P0 Decode | APK/AAB → sources, manifest, .so list, package survey. Detect Hermes/RN (`libhermes.so`) → `references/hermes-react-native.md` | `references/android-triage.md`, `references/hermes-react-native.md` | `scripts/decode_apk.sh` |
| P1 Static API | Find the target endpoint + the code that builds the request (for RN, the request builders are in the JS bundle, not DEX — `references/hermes-react-native.md`) | `references/android-triage.md`, `references/hermes-react-native.md` | `scripts/api_extract.py` |
| P2 Capture | Ground-truth the real request + signature value over TLS. If crypto is above TLS and unhookable, read plaintext from the heap (`references/heap-scan-capture.md`) | `references/ecapture-capture.md`, `references/heap-scan-capture.md` | `scripts/ecapture_run.sh`, `scripts/ecapture_parse.py` |
| P3 Align | Map each captured field to its builder in code; locate the crypto sink | `references/android-triage.md`, `references/native-tracing.md` | `findings.py`, protocol_map, `scripts/stackplz_run.sh` (syscall trace) |
| P4 Native + crypto ID | Reverse the .so signer; name the primitive by fingerprint | `references/ida-workflow.md`, `references/crypto-id.md`, `references/native-tracing.md` | `resolve_native_target.py`, `ida_target_loader.py`, `ida_export.py`, `constscan.py`, `cryptoinstr.py`, `stackplz_run.sh`/`stackplz_parse.py` |
| P5 Reconstruct + verify | Rebuild the scheme; recompute the captured signature; replay. If a byte-correct sign still blocks, it's TLS fingerprinting — **Gate D** + `references/signing-replay.md` §5 | `references/signing-replay.md` | `scripts/sign_rebuilder.py` |
| P6 Report | Endpoint + field map + signing scheme + verification, from the ledger | `references/state-schema.md` | `findings.py show/validate` |

Optional/on-demand references, loaded only when triage calls for them:

- `references/native-tracing.md` — **stackplz** (eBPF) tracing of native
  functions, syscalls, and hardware breakpoints: the low-footprint dynamic branch of
  Gate B, and the eBPF-first counterpart to ecapture. Reach here when a signer is
  anti-instrumentation-hardened or you need to watch native code run without
  Frida's footprint.
- `references/dbi-detection.md` — how apps detect Frida/QBDI (code-cache
  PC-divergence checks) and what a hit means for tool choice. The pre-dynamic
  triage that *justifies* eBPF-first and bounds what `bypass.js` should attempt.
- `references/native-emulation.md` — Unicorn/unidbg emulation of an isolated JNI
  function, struct recovery, symbol renaming, and **QTrace** (on-device QBDI
  instruction trace for de-flattening) — when a signer is statically unreadable,
  you need to run it offline, or you need the per-instruction executed path.
- `references/ios-playcover.md` — **iOS mode**: apps running under PlayCover on an
  Apple-Silicon Mac. The full `iP0–iP6` iOS workflow (local-host Frida, Mach-O/ObjC/Swift,
  plaintext-below-TLS capture, get-task-allow re-sign, anti-debug). Route here when the
  target is an `.ipa` / PlayCover app (see "iOS mode" above).
- `references/optional-platforms.md` — decrypting an iOS binary (砸壳), Unity/IL2CPP,
  Flutter/Blutter, packed-DEX unpacking. Non-default targets; route here only if P0 detects
  them (for a PlayCover app, prefer `ios-playcover.md`).
- `references/hermes-react-native.md` — Hermes / React Native (CRN) apps. The
  request builders live in a JS bundle, not DEX; the packaged `.jsbundle` is often
  plain minified JS you can grep directly (no Hermes decompile). Route here when P0
  finds `libhermes.so`/`libreactnativejni.so`. Watch the session-token and
  head-completeness traps.
- `references/slider-captcha-cv.md` — jigsaw/slider captchas (易盾, GeeTest, 顶象…)
  standing between you and the endpoint you are reversing. Locate the gap with
  classical CV and compute the drag distance. Read the ordering rule first: a
  captured token usually beats solving the widget, and a solved slider is evidence
  about the *widget*, never about the app's signing scheme.
- `references/heap-scan-capture.md` — when business crypto is self-contained in an
  OLLVM/stripped `.so` and unhookable, don't break the cipher: `SIGSTOP`-freeze the
  pid and scan `/proc/<pid>/mem` for the plaintext the app already decrypted. The
  capture of last resort behind Gate A and the anti-DBI-hardened branch of Gate B.

## iOS mode (PlayCover)

**Mode switch.** If the target is an **`.ipa`**, an app installed in **PlayCover** on an
Apple-Silicon Mac, or a **Bundle ID** (or the user says iOS/PlayCover/Mach-O/dylib), leave
the Android path and follow **`references/ios-playcover.md`** and its `iP0–iP6` table. The
ledger (`state-schema.md`), the crypto-id fingerprint discipline (`crypto-id.md`), Gate C/D,
`sign_rebuilder.py`, and the report step are **shared** — only the platform mechanics differ:

- PlayCover runs the app as a **native local arm64 macOS process** → dynamic instrumentation
  is **local host Frida** (`frida -n/-f/-p`); no `adb`, no `frida-server`, no device.
- **No eBPF on macOS** → the P2 ecapture/stackplz path is replaced by a **Frida Interceptor
  on the TLS record layer** (`scripts/ios_capture.sh` + `assets/frida/ios/ssl_dump.js`),
  reassembled by the same `ecapture_parse.py`. Read on-disk sources first
  (`scripts/ios_container.py`: Cache.db / PlayKeychain / defaults).
- Decode is `scripts/decode_ipa.sh` (not `decode_apk.sh`); the app must be **FairPlay-decrypted**
  (`cryptid 0`) — a prerequisite obtained off-platform (`optional-platforms.md` §1).
- Attach is gated by **`get-task-allow`** (an ad-hoc re-sign), **not root**; the hard part is
  the app's **anti-debug** timing (spawn-vs-attach) — both covered in the reference.

## When stuck — consult the fable sub-agent

A second "when stuck" resource alongside the KB search below, usable from **any** phase. When
the workflow hits a difficulty it cannot resolve from the references, the KB, or direct
analysis — a symbol that won't resolve (e.g. Flutter's stripped BoringSSL), an anti-debug /
anti-tamper that won't yield, an unfamiliar packer/obfuscator or crypto construction, a tool
misbehaving, or a platform quirk not covered here — **launch a fable sub-agent to explore it**:
the `Agent` tool with `model: fable` and a **focused, self-contained** problem statement (what
you're targeting, what you tried, what failed, the concrete artifacts / error output), asking
for domain expertise and concrete options.

- **Ordering:** search the KB first for "has someone hit *this exact* target/packer" (cheap,
  local); use the fable sub-agent for domain-reasoning gaps, novel difficulties, or when the
  KB verdict is `NONE`. Either can precede sinking hours into a hard step.
- **Discipline:** treat the sub-agent's output as **leads to verify against the target**, not
  ground truth — the ledger's fact rungs (R1/R2) still apply, exactly like KB hits.
- **Degrade gracefully:** if no sub-agent / fable model is available in the session, fall back
  to the KB + first-principles and record the difficulty in the ledger.

## Four decision gates

**Gate A — is app-layer crypto above TLS?** After P2, look at the captured
request body. If it is readable JSON, the signing/auth fields are your targets
(P3→P4). If the body is an opaque base64/hex blob, the app encrypts *before* TLS;
ecapture only sees the blob, so pivot to static/native and observe the
pre-encryption data at the crypto sink. Prefer a **low-footprint eBPF uprobe/brk**
(stackplz, `references/native-tracing.md`) to read the plaintext buffers — it
survives anti-instrumentation targets; use the Frida crypto hook
(`assets/frida/hook_crypto.js`) when the app is not hardened or eBPF is
unavailable (run the `references/dbi-detection.md` triage to decide). See
`references/ecapture-capture.md`.

When the cipher is **self-contained in an OLLVM/stripped `.so`** — you can't find
or hook the primitive and even the eBPF uprobe has no clean sink — stop trying to
break it and **read the plaintext the app already decrypted**: `SIGSTOP`-freeze the
pid and scan `/proc/<pid>/mem` (`references/heap-scan-capture.md`). It runs the
process untouched, so it survives the most anti-DBI targets, and it's the fastest
capture when the app is Hermes/RN (persisted getData store holds the plaintext).

**Gate B — static, or dynamic, and which dynamic tool?** Before sinking time into
IDA on a `.so`, apply the survey heuristic (`references/android-triage.md`): many
small, clean functions → IDA is productive (P4 static). A library of a few huge
functions is OLLVM/flattened → don't grind static analysis, capture its behavior
dynamically. When you go dynamic, pick the tool by two questions — *is the target
DBI-hardened?* and *do you need boundary I/O or the per-instruction path?*

Run the `references/dbi-detection.md` pre-triage first: if the `.so` carries
code-cache PC-divergence checks, **Frida Stalker and QBDI/QTrace are detectable
here** — prefer eBPF. Then:

| Situation | Tool | Why |
|-|-|-|
| Anti-DBI/anti-debug present, or you want minimal footprint | **stackplz** HW-brk / uprobe (`native-tracing.md`) | eBPF, code runs in place → not visible to code-cache checks |
| Need function I/O + syscalls without a device-side agent | **stackplz** syscall/uprobe | same eBPF surface as ecapture, beyond TLS |
| Off-device / environment-independent oracle | **unidbg** (`native-emulation.md` §1) | emulated Android/JNI, scriptable, no phone in the loop |
| OLLVM flattening, target **not** hardened, need executed path | **QTrace** (`native-emulation.md` §5) | per-instruction QBDI trace de-flattens control flow |
| Deep static / algorithm ID | **IDA** + `constscan`/`cryptoinstr` (`ida-workflow.md`) | fingerprint discipline names the primitive |

Default to stackplz for the dynamic branch; treat Frida (`jni_trace.js`) as the
fallback for when eBPF is unavailable and the target is not hardened. See
`references/ida-workflow.md` and `references/native-tracing.md`.

**Gate C — IDA MCP or headless?** If IDA Pro MCP tools are present in the
session, drive IDA live via MCP. Otherwise run `scripts/ida_export.py` (idalib
headless) to dump pseudocode to flat files and read those. Both paths start by
building the database with `scripts/ida_target_loader.py`. See
`references/ida-workflow.md`.

**Gate D — signature correct but still blocked? Suspect TLS fingerprinting.** After
P5, if you recompute the signature correctly (verified against the Step-3 oracle),
the body and headers are right, and the replay **still** 4xx / returns
`whaleguard block` / returns `Ack:"Success"` with empty data / hangs — the sign is
not the problem. A WAF (WhaleGuard, Akamai, Cloudflare) is fingerprinting the TLS
ClientHello (**JA3/JA4**). Plain `curl`/`requests` present a non-app JA3 → blocked;
the same bytes via `curl_cffi` `impersonate="chrome124"` → `Success`. **Rule: a
byte-correct signature that still blocks means TLS, not sign — check the fingerprint
before re-litigating the sign.** Escalation ladder: plain `requests` → `curl_cffi`
impersonate → `tls-client`/`utls` → capture and match the app's real JA3. Drive
replays from Python, not `curl` one-liners. See `references/signing-replay.md` §5.

**Gates in iOS mode.** The gates still apply, with these substitutions (full detail in
`references/ios-playcover.md`): **Gate A** — run the same readable-vs-opaque test on the
`SSL_write` body; the pivot generalizes to "crypto/framing above the socket" for non-HTTP
transports. **Gate B** — local Frida is the only DBI (no eBPF), so the decision is not
*which* tool but handling anti-debug timing (spawn-gate + `anti_debug_bypass.js`, or a static
NOP-patch). **Gate C** — IDA/Hopper/Ghidra read the Mach-O directly. **Gate D** — unchanged,
but for native/RN the ClientHello reflects **Apple's** boringssl (the platform), not the app,
unless the app ships its own TLS (Flutter / a custom pinned stack).

## Worked example — `reverse the login API from com.example.aa`

1. **Init** ledger (`target=com.example.aa`, goal login API).
2. **P0** `decode_apk.sh app.apk` → jadx sources (no `--deobf`), `libsec.so`
   found, package/components surveyed.
3. **P1** `api_extract.py` + the login call-flow playbook: anchor on the
   `"auth/login"` string → obfuscated Retrofit interface → repository →
   `LoginViewModel` → `LoginActivity`. Log facts at rung PATTERN with verbatim
   refs; note an `X-Sign` header.
4. **P2** `ecapture_run.sh --pkg com.example.aa` while you perform one login →
   `ecapture_parse.py` yields the real request: body `{user,pass,ts}` and
   `X-Sign: a1b2c3…` (a known input→signature pair).
5. **P3** Align fields: `X-Sign` is a signature_field; inputs are `{user,ts,secret}`;
   the builder dead-ends at a native call → raise an **Intent** on `libsec.so`.
6. **P4** `resolve_native_target.py` confirms `libsec.so`; `ida_target_loader.py`
   builds the `.i64`; read the signer (MCP or `ida_export.py`). `constscan.py`
   finds a SHA-256 K-table (`real`) and `cryptoinstr.py` finds `sha256h` + an
   HMAC ipad/opad constant → hypothesis `X-Sign = HMAC-SHA256` earns two
   fingerprints, promoted to high (`references/crypto-id.md`).
7. **P5** `sign_rebuilder.py` reproduces `HMAC-SHA256(secret, user|ts)`,
   recomputes the P2 signature — it **matches** → fact rung `VERIFIED`. Build a
   replay PoC that posts a fresh login (`references/signing-replay.md`).
8. **P6** `findings.py validate` (must pass), then emit the report: endpoint,
   field map, HMAC-SHA256 scheme + key derivation, and the passing replay.

## Prior art — search the knowledge base

`kb/articles/` holds 635 精华 (digest) writeups from the 看雪 Android security
board, 2023-01 onward: packers, Frida/DBI detection, unidbg, OLLVM, kernel hooks,
signing schemes. **Search it before burning hours on a hard step** — someone has
usually already published the exact packer, detection trick, or `.so` you are
staring at. Most useful at P0 (what am I looking at), Gate B (this target detects
Frida — what worked for others), and P4 (this signer is obfuscated).

```
python3 scripts/kb_search.py "libmsaoaidsec frida 检测" --top 5
python3 scripts/kb_search.py "unidbg 补环境" --json      # machine-readable
```

Read the `CONFIDENCE` line before you trust the hits:

| verdict | meaning | what to do |
|-|-|-|
| `HIGH` | the top hit really is about your query | open the files, use them as evidence |
| `LOW` | plausible but weak | skim before relying on it; do not cite it as fact |
| `NONE` | nothing relevant in the KB | say so and continue with your own analysis — **never** invent an answer "from the KB" |

Articles are forum posts, not documentation: an OP plus labelled `## 回复 by
{author} (#{floor})` sections, and the answer is often three floors down rather
than in the OP. Treat every claim as a lead to verify against the target, not as
ground truth — the ledger's fact rungs still apply. Each file's frontmatter has
the source `url`, `author` and `date`; cite those when a finding leans on one.

Search degrades gracefully. BM25 works with just `pip install rank_bm25`; the
index self-builds on first run (~5s). Semantic ranking additionally needs
`pip install sentence-transformers` and Python ≥3.9 — without it you get
keyword-only results and a `(semantic search unavailable)` note, which is fine.
To rebuild after editing `kb/articles/`: `python3 scripts/kb_build_index.py`
(CI does this for you — `.github/workflows/kb-index.yml`). `kb/INDEX.md` lists
every article for straight browsing.

## Assets

- `assets/frida/` — gap-filler hooks, used only when static/capture leaves a gap:
  `hook_crypto.js` (dump `javax.crypto` in/out/key/iv), `jni_trace.js` (trace JNI
  of a target .so), `hook_module_load.js` (fire on a lib load, correct timing),
  `bypass.js` (root/emulator/proxy/pinning/anti-debug Java-policy checks — usually
  unnecessary because ecapture needs none of it, and it deliberately does **not**
  address code-integrity DBI detection; see `references/dbi-detection.md`),
  `ssl_keylog.js` (BoringSSL keylog as a proxy-free Wireshark path), `dex_dump.js`
  (dump runtime DEX for packers).
- `scripts/rebuild_sign.sh` + `assets/debug.keystore` — rebuild and sign a
  patched APK (`apktool b` → `zipalign` → `apksigner`, optional `adb install`)
  when you patch smali to get past a check during authorized testing. `debug.keystore` is the signing key
  (auto-generated with `keytool` if missing).
- `assets/templates/` — PoC skeletons for P5: `python_http_validation.py.tmpl`
  (replay client) and `frida_runtime_observe.js.tmpl` (single-hook I/O logger).

## Safety

Use only against apps and accounts you are **authorized** to test (your own app,
a pentest engagement with scope, security research, CTF). The replay PoC exists
to prove the scheme is understood — do not use it against third-party accounts or
infrastructure. If a request looks like unauthorized access to someone else's
system, stop and say so.
