# mobile-reverse-skill

A single, opinionated **Claude Code skill** for reverse-engineering mobile apps —
Android-first — end to end: from a package name to a **verified** reconstruction
of a target API (endpoints, request fields, and the client-side signing /
encryption scheme), plus a replay PoC.

```
/reverse-skill reverse the login API from com.example.aa
```

It merges the strongest parts of five community RE skill collections into one
coherent workflow, standardized on the tools this repo prefers:

- **IDA Pro 9.3** for native (`.so`) analysis — supports both an IDA MCP server
  and a no-MCP headless (`idalib`) export path. Ghidra is intentionally out.
- **[gojue/ecapture](https://github.com/gojue/ecapture)** (eBPF) for TLS capture
  — no CA cert, no proxy, no SSL-pinning bypass, minimal detection surface. The
  GUI **[ecaptureQ](https://github.com/gojue/ecaptureQ)** is supported too.
- **jadx + apktool** for decode, **Frida** for gap-filling dynamic hooks.

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

Then in Claude Code: `/reverse-skill <what you want reversed>`.

## The workflow

| Phase | Goal | Tooling |
|-|-|-|
| P0 Decode | APK/AAB → sources, manifest, `.so` list | `decode_apk.sh` (jadx + apktool) |
| P1 Static API | Find the endpoint + the request-building code | `api_extract.py` |
| P2 Capture | Ground-truth the real request + signature value | `ecapture_run.sh`, `ecapture_parse.py` |
| P3 Align | Map captured fields to code; locate the crypto sink | `findings.py` protocol_map |
| P4 Native + crypto ID | Reverse the signer; name the primitive by fingerprint | IDA loader/export, `constscan.py`, `cryptoinstr.py` |
| P5 Reconstruct + verify | Rebuild the scheme; recompute the captured signature; replay | `sign_rebuilder.py` |
| P6 Report | Endpoint + field map + signing scheme + verification | `findings.py show/validate` |

Optional branches (loaded on demand): native emulation (Unicorn/unidbg, struct &
symbol recovery) and other platforms (iOS, Unity/IL2CPP, Flutter, packed DEX).

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
`idalib` for the headless path), and a **rooted** Android device/emulator for
ecapture + Frida. ecapture is fetched from its
[releases](https://github.com/gojue/ecapture/releases) (android/aarch64). Every
script degrades gracefully and prints an install hint when a tool is absent.

## Layout

```
skills/reverse-skill/
  SKILL.md                 router: phases, gates, worked example
  references/              per-phase docs (loaded on demand)
  scripts/                 decode / capture / IDA / crypto-ID / ledger / replay
  assets/frida/            gap-filler hooks + debug.keystore + PoC templates
```

## Credits

Built by combining and adapting these projects (see each for original license):

- [P4nda0s/reverse-skills](https://github.com/P4nda0s/reverse-skills) — IDA/IDAPython, Frida, Unicorn, struct/symbol recovery, dumpers
- [Fausto-404/ai-mobile-reverse-skills](https://github.com/Fausto-404/ai-mobile-reverse-skills) — pipeline/state model, IDA loader, sign rebuilder
- [haikow/claude-reverse-skills](https://github.com/haikow/claude-reverse-skills) — IDA-via-MCP, APK decode/rebuild scripts
- [CreditTone/android-reverse-engineering-skill](https://github.com/CreditTone/android-reverse-engineering-skill) — Android static triage, API/call-flow patterns, Frida scripts
- [icloudza/algokiller-plugin](https://github.com/icloudza/algokiller-plugin) — crypto-constant/instruction identification, hypothesis-ledger discipline
- [gojue/ecapture](https://github.com/gojue/ecapture) & [ecaptureQ](https://github.com/gojue/ecaptureQ) — eBPF TLS capture

## Legal

For authorized security testing, research, and education only. Use exclusively
against apps and accounts you own or are authorized to assess.
