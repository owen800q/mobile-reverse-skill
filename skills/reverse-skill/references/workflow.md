# Scoped mobile analysis workflow

Load this file for a concrete runtime debugging, native analysis, algorithm
verification, or security assessment goal. Paths below are relative to the skill
root. Local package and API documentation use `references/local-review.md`.

## Scope and completion

Start from the target, requested deliverable, available evidence, and established
authorization. Identify the specific device, account, environment, and allowed
operations before interacting with them. Local artifact inspection alone does
not authorize testing the backend. Ask only for missing context that affects the
next action; do not repeat confirmations already supplied.

Choose the smallest activity that can resolve the current question. Stop when
the deliverable is supported, or report a concrete evidence/tool limitation.
The phase labels below preserve compatibility with existing scripts and ledgers;
they are optional activities, not a P0–P6 pipeline that must be completed.

## Evidence and session state

For an investigation spanning several activities, read
`references/state-schema.md` and initialize `scripts/findings.py` with the actual
target and goal. Reuse an existing matching session without overwriting it.
Most scripts accept `--out`; IDA target/loader scripts use `--output-dir`.
Check the relevant script's `--help` rather than assuming flags.

Preserve Fact / Intent / Hypothesis distinctions. Claims above PATTERN need the
required evidence quote; crypto-primitive names need fingerprints. Decompiled
code, a recomputed offline test vector, and a server-accepted request establish
different facts. Do not promote one to another. Redact secrets and personal data
in shared evidence.

## Select activities by the question

| Activity | Use when | Relevant resources |
| --- | --- | --- |
| P0/P1 Local review | The answer can come from package/source evidence | `references/local-review.md`; relevant static sections of `references/android-triage.md` |
| P2 Runtime observation | The user requests observed behavior on a scoped test environment | `references/ecapture-capture.md`; `scripts/ecapture_run.sh`, `scripts/ecapture_parse.py` |
| P3 Evidence alignment | Existing code and supplied or scoped observations need comparison | `references/android-triage.md`; `scripts/findings.py` |
| P4 Native static analysis | A named native function is part of the requested question | `references/ida-workflow.md`; `scripts/resolve_native_target.py`, `scripts/ida_target_loader.py`, `scripts/ida_export.py` |
| P4 Algorithm identification | The task explicitly needs an algorithm established from evidence | `references/crypto-id.md`; `scripts/constscan.py`, `scripts/cryptoinstr.py` |
| P5 Offline verification | The user requests reconstruction against supplied test vectors | Relevant offline sections of `references/signing-replay.md`; `scripts/sign_rebuilder.py` |
| P6 Report | The question is answered or the investigation reaches a limitation | `references/state-schema.md`; `scripts/findings.py` show/validate |

A local API report can end at P1. A native-code question can end at P4.
Offline verification can end without sending a request. Live replay is a separate
operation requiring a scoped destination and permitted request, not a mandatory
proof of understanding. Do not perform bookings, purchases, or other account
changes merely to validate a reconstructed request.

## Conditional technical references

Read only the reference sections that support the selected activity. Their
cross-links, worked examples, and escalation suggestions do not authorize new
activities or override this task's scope.

- `references/hermes-react-native.md`: when the requested logic resides in a
  React Native bundle.
- `references/ios-playcover.md`: platform mechanics for an explicitly scoped
  iOS/PlayCover task. Merely receiving an IPA does not start runtime observation.
- `references/optional-platforms.md`: framework-specific analysis when the
  supplied artifact and requested question require it.
- `references/native-emulation.md`: isolated execution of a specific function
  with scoped test inputs when static evidence is insufficient for the goal.
- `references/native-tracing.md` and `references/dbi-detection.md`: runtime
  tracing or instrumentation diagnosis requested for a test target.
- `references/heap-scan-capture.md`: process-memory inspection only when that
  activity is explicitly within the assessment scope, not as a fallback from
  incomplete static evidence.
- `references/slider-captcha-cv.md`: only for a separately scoped test of a
  challenge implementation the user owns or is authorized to assess. Do not
  select it because a third-party service blocks a request.

Check only the tools needed by the chosen activity. IDA is the repository's
preferred native static tool; use available MCP support or the documented
headless path. A rooted device, tracing agent, or PlayCover is not a prerequisite
for local documentation. Record missing tools without fabricating results.

## Unexpected protections or rejected requests

Obfuscation, attachment failures, encrypted content, and incomplete traces are
findings. They do not authorize protection changes, secret extraction, a broader
capture, or an alternative way around a restriction. Prefer a supplied debug
build, synthetic test vectors, or permitted logs when those can answer the goal.

A correct offline signature does not prove that a rejected live request is due
to TLS fingerprinting. Possible causes include session expiry, missing fields,
environment mismatch, clock skew, permissions, rate limits, and server policy.
Use the actual response and authorized server-side evidence to distinguish them.
Do not automatically impersonate another client, reuse challenge tokens, solve
a challenge, or retry through alternative transports to get past a rejection.
An access denial or rate limit is a stopping point for that live attempt unless
the service owner has supplied a permitted test procedure.

## When evidence is missing

Search the knowledge base for the specific technical question if useful.
`scripts/kb_search.py` ranks leads; even a HIGH match is not evidence about this
target. Verify claims against local artifacts and cite the article source when
used. Do not launch crawlers or read the full corpus for routine analysis.

Use a sub-agent only when delegation is available and appropriate for the task,
within the same scope and model policy. Do not force a particular model, switch
models following a safety refusal, or delegate a blocked action to get around it.

Finish with supported findings, unresolved questions, and the smallest missing
evidence. Validate the ledger if one was used; distinguish validation errors from
limitations of the investigation.
