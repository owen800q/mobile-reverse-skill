# mobile-reverse-skill

A single, opinionated **Claude Code skill** for reverse-engineering mobile apps —
Android-first — end to end: from a package name to a **verified** reconstruction
of a target API (endpoints, request fields, and the client-side signing /
encryption scheme), plus a replay PoC.

```
/reverse-skill ./app.apk document the login request flow for my staging app
```

It merges the strongest parts of five community RE skill collections into one
coherent workflow, standardized on the tools this repo prefers:

- **IDA Pro 9.3** for native (`.so`) analysis — supports both an IDA MCP server
  and a no-MCP headless (`idalib`) export path. Ghidra is intentionally out.
- **[gojue/ecapture](https://github.com/gojue/ecapture)** (eBPF) for TLS capture
  — no CA cert, no proxy, no SSL-pinning bypass, minimal detection surface. The
  GUI **[ecaptureQ](https://github.com/gojue/ecaptureQ)** is supported too.
- **[SeeFlowerX/stackplz](https://github.com/SeeFlowerX/stackplz)** (eBPF) for
  native function / syscall / hardware-breakpoint tracing — the same low-detection
  kernel-side surface as ecapture, applied beyond TLS, so anti-instrumentation
  targets that trip on Frida sail through.
- **jadx + apktool** for decode, **Frida** for gap-filling dynamic hooks (with a
  documented honesty bound: apps that ship code-cache DBI detection burn Frida and
  QBDI, which is *why* the workflow prefers eBPF).

## Why one skill

Reversing something like a login API isn't a single trick — it's decode → find
the endpoint → capture ground truth → align code to traffic → reverse the native
signer → name the crypto → reconstruct and prove it. Each source skill did part
of that well; this stitches them into one phased flow with shared state so the
phases actually feed each other, and adds a discipline that stops the model from
inventing an algorithm name it can't back up.

## Install

```bash
./install.sh          # copy into ~/.claude/skills/reverse-skill
./install.sh --link   # or symlink (for hacking on the skill)
```

Then in Claude Code: `/reverse-skill <authorized target> <specific objective>`.

The skill is manual-only. Running `/reverse-skill` without arguments performs a
short preflight: it asks for the target, objective, and authorized-use context
without loading the detailed analysis workflow.

## The workflow

| Phase | Goal | Tooling |
|-|-|-|
| P0 Decode | APK/AAB → sources, manifest, `.so` list | `decode_apk.sh` (jadx + apktool) |
| P1 Static API | Find the endpoint + the request-building code | `api_extract.py` |
| P2 Capture | Ground-truth the real request + signature value | `ecapture_run.sh`, `ecapture_parse.py` |
| P3 Align | Map captured fields to code; locate the crypto sink | `findings.py` protocol_map, `stackplz_run.sh` (syscall trace) |
| P4 Native + crypto ID | Reverse the signer; name the primitive by fingerprint | IDA loader/export, `constscan.py`, `cryptoinstr.py`, `stackplz_run.sh`/`stackplz_parse.py` |
| P5 Reconstruct + verify | Rebuild the scheme; recompute the captured signature; replay | `sign_rebuilder.py` |
| P6 Report | Endpoint + field map + signing scheme + verification | `findings.py show/validate` |

Optional branches (loaded on demand): stealthy eBPF native tracing (stackplz —
syscalls, uprobes, hardware breakpoints), DBI-detection triage (the pre-dynamic
check that decides Frida vs eBPF), native emulation (Unicorn/unidbg, struct &
symbol recovery, on-device QBDI instruction trace via QTrace), slider-captcha CV
(computing the drag distance when a jigsaw gate sits in front of the endpoint you
are reversing — see [`tools/slider-cv`](tools/slider-cv/)), and other platforms
(iOS, Unity/IL2CPP, Flutter, packed DEX).

### iOS mode (PlayCover)

For iOS apps running under **[PlayCover](https://github.com/PlayCover/PlayCover)** on an
Apple-Silicon Mac, the skill switches to an iOS-native `iP0–iP6` flow
(`references/ios-playcover.md`). PlayCover runs the app as a **native local macOS process**,
so there is no device, no `frida-server`, and no eBPF: dynamic work is **local-host Frida**
(`frida -n/-f/-p`), and the ecapture equivalent is a Frida Interceptor on the TLS record layer
(`assets/frida/ios/ssl_dump.js`), reassembled by the same `ecapture_parse.py`. Decode is
`decode_ipa.sh` (cryptid check, ObjC/Swift dump via `ipsw`), passive on-disk sources come from
`ios_container.py` (NSURLCache `Cache.db`, PlayKeychain, defaults), attach is gated by
`get-task-allow` (an ad-hoc re-sign, not root), and RN/Hermes, Flutter, and custom-TCP targets
are each routed appropriately. The ledger, crypto-id discipline, and replay/verify steps are
shared with the Android flow. A FairPlay-decrypted IPA (`cryptid 0`) is a prerequisite.

When a run gets stuck on a hard step (a stripped Flutter BoringSSL, stubborn anti-debug, an
unfamiliar crypto construction), the skill can **launch a fable sub-agent** to explore the
difficulty — a "when stuck" escalation alongside the knowledge-base search.

### The honesty ledger

Every run keeps one `findings.json` (managed by `scripts/findings.py`) — Facts on
a 5-rung evidence ladder, cross-phase Intents, and fingerprint-gated Hypotheses.
`findings.py validate` mechanically enforces two rules:

1. No claim above rung `PATTERN` without a verbatim evidence quote.
2. No crypto-primitive name at confidence ≥ medium without a fingerprint
   (a `constscan`/`cryptoinstr` hit). A lone `0x9e3779b9` is not proof of TEA.

The strongest rung, `VERIFIED`, means you recomputed the *actual captured*
signature from its *actual captured* inputs — ecapture turns algorithm recovery
into verification instead of guesswork.

## Prerequisites

`python3`, `adb`, `jadx`, `apktool`, `frida`/`frida-tools`, IDA Pro 9.3 (with
`idalib` for the headless path), and a **rooted** Android device/emulator (arm64,
kernel ≥ 5.10 for stackplz) for the eBPF + Frida tooling. ecapture and stackplz
are fetched from their releases —
[ecapture](https://github.com/gojue/ecapture/releases) and
[stackplz](https://github.com/SeeFlowerX/stackplz/releases) (android/aarch64).
Every script degrades gracefully and prints an install hint when a tool is absent.

## Layout

```
skills/reverse-skill/
  SKILL.md                 authorization + target/objective preflight
  references/workflow.md   detailed router: phases, gates, worked example
  references/              per-phase docs (loaded on demand)
  scripts/                 decode / capture / eBPF trace / IDA / crypto-ID / ledger / replay
  assets/frida/            gap-filler hooks + debug.keystore + PoC templates
tools/
  kanxue-crawler/          archives the 看雪 Android board into the KB corpus
  slider-cv/               jigsaw-captcha gap finder (OpenCV) + Playwright drag driver
  cloakbrowser-ci/         the pinned, reproducible browser runtime the crawl runs in
```

## Credits

Built by combining and adapting these projects (see each for original license):

- [P4nda0s/reverse-skills](https://github.com/P4nda0s/reverse-skills) — IDA/IDAPython, Frida, Unicorn, struct/symbol recovery, dumpers
- [Fausto-404/ai-mobile-reverse-skills](https://github.com/Fausto-404/ai-mobile-reverse-skills) — pipeline/state model, IDA loader, sign rebuilder
- [haikow/claude-reverse-skills](https://github.com/haikow/claude-reverse-skills) — IDA-via-MCP, APK decode/rebuild scripts
- [CreditTone/android-reverse-engineering-skill](https://github.com/CreditTone/android-reverse-engineering-skill) — Android static triage, API/call-flow patterns, Frida scripts
- [icloudza/algokiller-plugin](https://github.com/icloudza/algokiller-plugin) — crypto-constant/instruction identification, hypothesis-ledger discipline
- [gojue/ecapture](https://github.com/gojue/ecapture) & [ecaptureQ](https://github.com/gojue/ecaptureQ) — eBPF TLS capture
- [SeeFlowerX/stackplz](https://github.com/SeeFlowerX/stackplz) — eBPF native function / syscall / hardware-breakpoint tracing (the stealthy dynamic branch)
- [SoyBeanMilkx/dbi_detect](https://github.com/SoyBeanMilkx/dbi_detect) — DBI code-cache detection techniques (the "why eBPF-first" doctrine)
- [zgy0x01/QTrace](https://github.com/zgy0x01/QTrace) — on-device QBDI instruction trace for control-flow de-flattening

## Legal

For authorized security testing, research, and education only. Use exclusively
against apps and accounts you own or are authorized to assess.
