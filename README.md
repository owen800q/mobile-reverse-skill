# mobile-reverse-skill

A Claude Code skill for inspecting Android and iOS packages, documenting feature
and API call flows, and performing scoped mobile security analysis. It begins
with the user's question and local evidence; runtime capture and live validation
are used only when needed and authorized.

    /reverse-skill ./app.apk document how the appointment list request is built

## Install

    ./install.sh          # copy into ~/.claude/skills/reverse-skill
    ./install.sh --link   # or symlink for skill development

Then invoke /reverse-skill with a package or a concrete question.

## Invocation behavior

| Request | Behavior |
|---|---|
| /reverse-skill with no context | Ask for a package or question; no tools, device discovery, or ledger |
| An APK/IPA alone, or "analyze this app" | Local metadata and archive overview; ask which feature to examine |
| A package name or bundle ID alone | Ask for the file or a selected test installation |
| A feature/API question with a package | Trace relevant local code and report evidence and unknowns |
| A supplied test capture | Align the supplied evidence; no new capture by default |
| Explicit scoped runtime analysis | Observe only what is necessary on the selected test target |
| Requested signing reconstruction | Verify offline samples; live requests are an additional scoped action |

Existing target, objective, and authorization in the conversation are reused.
Login is not the default objective. Package possession does not establish
permission to test the backend service, and API discovery does not authorize
booking, checkout, cancellation, or other state changes.

## The workflow

Phase numbers remain compatible with the existing scripts and findings ledger.
Choose only the phases needed; a static report is a complete outcome.

| Phase | Goal | Tooling |
|---|---|---|
| P0 Local overview | File identity, metadata, archive and framework inventory | Local archive/platform metadata tools |
| P0/P1 Static feature analysis | Decode and trace the requested feature | decode_apk.sh; targeted source searches; api_extract.py when a broad scan is needed |
| P2 Capture, if scoped | Obtain missing runtime evidence | ecapture_run.sh, ecapture_parse.py; iOS capture helpers |
| P3 Align | Map supplied or captured fields to code | findings.py |
| P4 Native / algorithm analysis, if needed | Resolve the relevant native behavior and identify primitives from evidence | IDA loader/export, constscan.py, cryptoinstr.py |
| P5 Requested reconstruction | Recompute a known test sample; optionally perform a scoped live test | sign_rebuilder.py |
| P6 Report | Findings, evidence, verification level, and limitations | findings.py show/validate for ledger-backed work |

The entrypoint routes to detailed guides only when the current question needs
them. Existing native tracing, emulation, engine, and runtime resources remain
available for scoped work. Reference instructions never broaden the user's
objective or authorize additional actions. A blocked request does not
automatically trigger client impersonation, protection changes, or challenge
solving.

### iOS / PlayCover

An IPA alone receives a local package overview. A stated iOS code question uses
the static sections of references/ios-playcover.md. Runtime work on a selected
PlayCover test app uses the guide's applicable runtime sections. Container reads,
re-signing, process attachment, and traffic capture are separate scoped actions.

An encrypted executable is a code-analysis limitation; metadata inspection can
still finish. Request a suitable authorized development/test artifact when code
inspection is needed instead of automatically routing to decryption.

### Evidence ledger

Substantive feature analysis keeps one findings.json, managed by
scripts/findings.py. Empty invocations and short package overviews do not create
a ledger. Reuse a matching session and preserve existing evidence.

The existing evidence ladder and fingerprint checks are retained:

1. No claim above PATTERN without a verbatim evidence quote.
2. Crypto-primitive claims at medium or higher confidence require fingerprints.

A reproduced signature verifies that sample. It does not establish server
acceptance or correctness for every input. Keep raw credentials, tokens,
personal records, and captures out of reports and commits; use redacted evidence
and local artifact references.

### Safeguard reports

This revision changes the actions selected by default: package intake no longer
starts a login/capture/replay pipeline. It also removes model-specific escalation
and the unsupported assumption that a blocked request with a correct sample
signature must be a TLS-fingerprint problem.

These changes do not guarantee any provider's safeguard outcome. If legitimate
work is still flagged, use the feedback mechanism shown by the provider with a
minimal redacted reproduction, model/version, exact request, and warning. Do not
disguise the task or switch models to circumvent a safeguard.

For manual verification after installing this revision, use an owned test
package and check these behaviors:

| Scenario | Expected result |
|---|---|
| Empty invocation without prior target | One intake question; no tool calls |
| APK or IPA only | Local overview; no device/capture/secret scan/replay |
| APK plus a static feature question | Relevant code analysis; stop after the answer |
| Explicitly scoped runtime task | Preserve stated scope; do not ask for already supplied details |
| Offline signature match | Report sample verification without claiming live success |
| Live test returns 403 or 429 | Report denial/throttling; no automatic client rotation or challenge solving |

This is a behavior checklist, not evidence that Fable 5.1 has been tested.

## Prerequisites

A local overview uses standard archive tools or Python's standard library;
platform metadata tools improve manifest details when available. Full Android
decoding needs jadx/apktool and accepts APK/XAPK/APKS/APKM. The decoder does not
support AAB directly.

Install additional tools only for the requested analysis: IDA for native static
work; adb, ecapture/stackplz, and an appropriate test device for scoped Android
runtime work; macOS tooling for iOS code analysis; PlayCover and local Frida for
selected PlayCover runtime tests. Check each helper's --help and report missing
capabilities accurately.

## Layout

- skills/reverse-skill/SKILL.md — intake, scope, phase routing, evidence rules.
- skills/reverse-skill/references/ — local intake and task-specific guides.
- skills/reverse-skill/scripts/ — decode, capture, IDA, ledger, and reconstruction helpers.
- skills/reverse-skill/assets/ — runtime hooks and validation templates.
- tools/ — existing KB crawler, browser runtime, and slider test tooling.

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
