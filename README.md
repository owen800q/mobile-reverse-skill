# mobile-reverse-skill

A Claude Code skill for mobile package analysis and API documentation, with
additional workflows for scoped runtime debugging and security assessment.

```text
/reverse-skill ./app.apk list its permissions and bundled SDKs
/reverse-skill ./app.apk document the appointment-list request builder from local code only
```

## Install

```bash
./install.sh          # copy into ~/.claude/skills/reverse-skill
./install.sh --link   # or symlink for development
```

The skill is manual-only. Invoke it with an app file or identifier and a concrete
question. Attachments and relevant context in the current conversation count;
there is no special authorization phrase to repeat.

## How requests are handled

| Request | Behavior |
| --- | --- |
| No target or goal | Ask for both, then stop without tools |
| Only an APK/IPA or identifier | Ask what the user wants to learn; do not start analysis |
| Package permissions or SDK inventory | Inspect local package evidence and report |
| API or feature documentation | Trace relevant local code and document uncertainty |
| Scoped runtime debugging or native analysis | Select the activities needed for the stated goal |
| Offline algorithm verification | Compare scoped test vectors; live replay is separate |

Routine local work follows
[`local-review.md`](skills/reverse-skill/references/local-review.md).
It can finish without a device, traffic capture, algorithm reconstruction, or
backend request. Static route declarations do not establish that an endpoint is
active or that an appointment is available.

Advanced work follows the scoped activity router in
[`workflow.md`](skills/reverse-skill/references/workflow.md).
The existing P0–P6 labels are retained for script/ledger compatibility, but
completing every phase is not required. Permission to inspect an app package does
not by itself authorize interacting with its backend.

## Tools and evidence

Use tools only as required by the selected activity:

- Package/source review: local archive readers, jadx, apktool, and focused searches.
- Native static analysis: IDA with MCP or the documented headless export path.
- Scoped runtime observation: ecapture, stackplz, or applicable platform tooling.
- Algorithm identification and offline verification: fingerprint helpers and test vectors.
- Longer investigations: `scripts/findings.py` and the evidence schema.

Platform and framework references cover Android, iOS/PlayCover, React Native,
Flutter, and other packaged code. Reading a platform reference does not expand
the task into all the activities it describes.

The findings ledger distinguishes facts, intentions, and hypotheses. Source
quotes and algorithm fingerprints support claims; an offline match does not
prove a live request succeeds. Missing tools and evidence remain explicit.

## Model safeguards

This revision changes the actual default behavior and scope of the workflow.
It does not promise a particular provider classification or disable safeguards.
Do not rename sensitive operations, suppress their context, switch models, or
retry a refused request through another agent to evade a safety decision.

A provider may still flag a legitimate task. Report the actual request and
relevant diagnostics through its feedback process. Structural validation of this
skill is not a live Fable test.

## Layout

```text
skills/reverse-skill/
  SKILL.md                    task intake and routing
  references/local-review.md  complete local documentation path
  references/workflow.md      scoped advanced activities
  references/                 task-specific technical guidance
  scripts/                    existing analysis and evidence helpers
  assets/                     existing runtime hooks and output templates
tools/                        supporting utilities
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
