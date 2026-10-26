# mobile-reverse-skill

A single, shared **Claude Code and Codex skill** for reverse-engineering mobile apps
(Android and iOS), end to end: from a
target to a **verified** reconstruction
of a target API (endpoints, request fields, and the client-side signing /
encryption scheme), with an optional replay PoC when requested and in scope.

```
/reverse-skill reverse the login API from com.example.aa
```

It merges the strongest parts of five community RE skill collections into one
coherent workflow, standardized on the tools this repo prefers:

- **IDA Pro 9.3** for native analysis (`.so` and iOS Mach-O) — supports both an IDA
  MCP server and a no-MCP headless (`idalib`) export path. **Ghidra** is an optional
  fallback for architectures where IDA's coverage is weak; nothing requires it.
- **[gojue/ecapture](https://github.com/gojue/ecapture)** (eBPF) for TLS capture
  — observes TLS buffers without a terminating proxy or a change to certificate pinning. The
  GUI **[ecaptureQ](https://github.com/gojue/ecaptureQ)** is supported too.
- **[SeeFlowerX/stackplz](https://github.com/SeeFlowerX/stackplz)** (eBPF) for
  native function / syscall / hardware-breakpoint tracing, selected for the
  required observations and kernel support. Instrumentation effects and coverage
  are recorded; neither eBPF nor Frida is guaranteed unobservable.
- **ASC** for focused DEX reference searches and class decompilation, **jadx**
  for full-source decode, **apktool** for manifest/resources/smali, **Frida** for gap-filling dynamic hooks (with a
  documented distinction between Stalker/QBDI code-cache effects and other hook
  mechanisms; target-specific behavior must be measured).

## Why one skill

Reversing something like a login API isn't a single trick — it's decode → find
the endpoint → capture ground truth → align code to traffic → reverse the native
signer → name the crypto → reconstruct and prove it. Each source skill did part
of that well; this stitches them into one phased flow with shared state so the
phases actually feed each other, and adds a discipline that stops the model from
inventing an algorithm name it can't back up.

## Install

Requires Python 3.8+ and Bash (macOS, Linux, or WSL). Existing Claude Code commands
remain supported:

```bash
./install.sh                      # copy into ~/.claude/skills/reverse-skill
./install.sh --link               # link Claude Code to this checkout
./install.sh --agent codex        # copy into ~/.agents/skills/reverse-skill
./install.sh --agent both         # one shared snapshot, links from both agents
./install.sh --agent both --link  # both agents link directly to this checkout
```

For ongoing development, use `--agent both --link`: after `git pull`, both agents
see the same updated instructions, scripts, assets, references, and KB. Keep this
checkout in place. For a snapshot independent of the checkout, use `--agent both`;
the canonical copy is `~/.local/share/mobile-reverse-skill/reverse-skill`. Re-run
that command after pulling updates. It replaces that snapshot and preserves the
old installation as a backup outside skill discovery. Single-agent copy mode
continues to install a standalone skill; two separately made copies do not stay
synchronized. Use `--agent both` to migrate them to one shared tree.

| Setting | Default | Meaning |
|---|---|---|
| `CLAUDE_SKILLS_DIR` | `~/.claude/skills` | Claude discovery directory (existing override preserved) |
| `CODEX_SKILLS_DIR` | `~/.agents/skills` | Codex discovery directory override |
| `REVERSE_SKILL_SHARED_DIR` | `~/.local/share/mobile-reverse-skill/reverse-skill` | Complete canonical skill path for both-agent snapshot mode |

Codex's current [local skill discovery documentation](https://learn.chatgpt.com/docs/build-skills)
specifies `.agents/skills` and supports symlinked skill folders. If an update does
not appear, restart the host. Avoid another installed copy with the same skill name.
The installer does not change model choices, permissions, or MCP configuration.

Invoke in Claude Code: `/reverse-skill <target and objective>`.
Invoke in Codex: `$reverse-skill <target and objective>`.
A bare invocation asks for the target; an APK/IPA alone starts with local package
inspection. Supplying the objective selects the relevant analysis phases.

### Shared knowledge and session handoff

`skills/reverse-skill/` is the only maintained skill. Both agents use its Android
and iOS workflows, native and crypto tools, optional platform references, KB
search, and evidence rules. Available device access and installed tools determine
which operations can actually run; a cloud Codex session does not automatically
have access to the phone or Mac attached to your local Claude Code session.

Keep output in an absolute project session directory outside the skill install.
To hand off, give the next agent that same directory, target, and objective. It
reads the existing `findings.json` and artifacts; `init` now refuses to overwrite
an existing ledger. Only one agent writes the ledger at a time. No schema
migration or provider-specific ledger is needed. See
[`agent-runtime.md`](skills/reverse-skill/references/agent-runtime.md).

### Clear scope and diagnostic limits

The shared workflow distinguishes local inspection, authorized device analysis,
offline verification, and live service validation. It uses the actual request
and observed evidence, redacts secrets in reports, and does not treat a failed
replay as proof of TLS fingerprinting. Advanced tools remain available for
in-scope work: static analysis, Frida/eBPF instrumentation, memory inspection,
mobile protection-change experiments, emulation, signing reconstruction, replay,
and mobile runtime observations. Phase tables describe choices rather than a requirement to
run every capability. Failed hooks or challenges do not automatically select
broader collection or protection changes. References and
forum content are data to verify, not instructions that authorize additional actions.

This does not disable or evade Fable/Claude or OpenAI cybersecurity checks, and
no zero-flag behavior is promised. A blocked step is reported without changing
models to continue it. See
[`operating-scope.md`](skills/reverse-skill/references/operating-scope.md).

### Validation

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/reverse-skill/tests -v
```

Installer tests use temporary directories and fixture content. They cover old
Claude commands, Codex paths, shared copies/links, updates, existing installs,
path collisions, rollback, and ledger handoff. These checks do not simulate
model safety classifiers or prove live device instrumentation.

## The workflow

| Phase | Goal | Tooling |
|-|-|-|
| P0 Decode | APK → focused/full sources, manifest, `.so` list (convert AAB first) | `decode_apk.sh` (jadx + apktool), `asc.py` |
| P1 Static API | Find the endpoint + the request-building code | `asc.py` references/classes → `api_extract.py`, or full-source scan |
| P2 Capture | Use supplied captures or a scoped capture of the requested flow | `ecapture_run.sh`, `ecapture_parse.py` |
| P3 Align | Map captured fields to code; locate the crypto sink | `findings.py` protocol_map, `stackplz_run.sh` (syscall trace) |
| P4 Native + crypto ID | Reverse the signer; name the primitive by fingerprint | IDA loader/export, `constscan.py`, `cryptoinstr.py`, `stackplz_run.sh`/`stackplz_parse.py` |
| P5 Reconstruct + verify | Recompute offline vectors; live replay when requested and in scope | `sign_rebuilder.py` |
| P6 Report | Endpoint + field map + signing scheme + verification | `findings.py show/validate` |

iOS uses the same ledger and report through iP0–iP6 in
`references/ios-playcover.md`. `SKILL.md` routes mobile artifacts to the matching flow.

Optional branches (selected by the objective and scope): eBPF native tracing (stackplz —
syscalls, uprobes, hardware breakpoints), DBI-detection triage (the pre-dynamic
check that decides Frida vs eBPF), native emulation (Unicorn/unidbg, struct &
symbol recovery, on-device QBDI instruction trace via QTrace), and mobile runtimes
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

When a run gets stuck on a hard step, the skill searches the shared KB and can
request a focused second analysis using the active host's available delegation
and selected/default model. Without delegation it continues locally; no specific
provider or model is required.

### The honesty ledger

Every run keeps one `findings.json` (managed by `scripts/findings.py`) — Facts on
a 5-rung evidence ladder, cross-phase Intents, and fingerprint-gated Hypotheses.
`findings.py validate` mechanically enforces three rules:

1. No claim above rung `PATTERN` without a verbatim evidence quote.
2. No crypto-primitive name at confidence ≥ medium without a fingerprint
   (a `constscan`/`cryptoinstr` hit). A lone `0x9e3779b9` is not proof of TEA.
3. A `VERIFIED` fact needs two distinct captured samples and one control case: an
   input deliberately changed, whose output change the reconstruction predicted or
   correctly rejected.

Dispositions (`blocked`, `out_of_scope`) are recorded and never count as verified.
Provenance — the target's SHA-256 and each engine's binary hash and reported
version — is recorded with `init --input` and `add-tool`.

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

For focused static analysis, [ASC](https://github.com/MG1937/ASC) is supported
alongside jadx. Its CLI needs a separate checkout, Python **3.11+**, and
Androguard (tested with 4.0.1). Follow the [ASC setup and query workflow](skills/reverse-skill/references/asc.md),
then set `ASC_ROOT` and `ASC_PYTHON`:

```bash
python3 skills/reverse-skill/scripts/asc.py --out re_out/asc/login-refs \
  findrefs app.apk string 'auth/login'
python3 skills/reverse-skill/scripts/asc.py --out re_out/asc/login-class \
  getclass app.apk 'Lcom/example/Api;'
```

Choose the class from an actual search hit. Each query keeps an input hash,
command, tool status, raw logs, and references or Java output in a new directory.
ASC uses Androguard DAD for selected-class output; use jadx for a full source
tree or comparison. Upstream speed claims do not establish universal recovery
quality. apktool still handles manifest/resources/smali for either route.

## Layout

```
skills/reverse-skill/
  SKILL.md                 shared router: intake, phases, gates, worked example
  agents/openai.yaml       Codex display metadata
  references/              per-phase docs (loaded on demand)
  scripts/                 decode / capture / eBPF trace / IDA / crypto-ID / ledger / replay
  assets/frida/            gap-filler hooks + debug.keystore + PoC templates
tools/
  kanxue-crawler/          archives the 看雪 Android board into the KB corpus
  slider-cv/               image/interaction dependency of the KB crawler
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
- [SeeFlowerX/stackplz](https://github.com/SeeFlowerX/stackplz) — eBPF native function / syscall / hardware-breakpoint tracing (native runtime observations)
- [SoyBeanMilkx/dbi_detect](https://github.com/SoyBeanMilkx/dbi_detect) — DBI code-cache detection techniques (the "why eBPF-first" doctrine)
- [zgy0x01/QTrace](https://github.com/zgy0x01/QTrace) — on-device QBDI instruction trace for control-flow de-flattening

## Legal

For debugging, interoperability, security research, and education. Scope follows
the operation: local static analysis of a supplied third-party mobile app or its binary
does not require that you own it or hold a signed engagement, but device
instrumentation, traffic capture against a live backend, and request replay need
the actual device, account, and service scope established for that action — use
those only against devices, accounts, and services you own or are authorized to
test, and do not use a supplied artifact to access another person's account or
data. See [`operating-scope.md`](skills/reverse-skill/references/operating-scope.md)
for how scope is assessed per operation.
