# Route by the observed symptom

Load this when a result contradicts the current plan, a helper fails, or an
attempt repeats a previous failure. Read the matching reference before another
attempt. These rows select an investigation; they are not diagnoses.

| Observation | First check | Reference |
|---|---|---|
| A tool is missing or a helper cannot start | Inspect this host's prerequisites; separate missing dependencies from target failures. | [environment-checks.md](environment-checks.md) |
| ASC reports no matches, or jadx shows little application code | Check query coverage, annotations, every code-bearing split, wrappers and runtime framework before declaring the endpoint absent. | [asc.md](asc.md), [android-triage.md](android-triage.md) |
| DEX methods have no useful bodies | Distinguish loading/extraction from native implementations; a dump is useful only if the requested bytecode exists at runtime. | [optional-platforms.md](optional-platforms.md), [native-emulation.md](native-emulation.md) |
| A hook or trace produces zero events | Check attachment, process, load timing and whether the feature ran; compare a known working probe before attributing this to detection. | [native-tracing.md](native-tracing.md), [dbi-detection.md](dbi-detection.md) |
| Captured TLS payloads are still opaque | Identify encoding, framing and app-layer encryption from evidence; inspect the builder or crypto boundary. | [ecapture-capture.md](ecapture-capture.md), [crypto-id.md](crypto-id.md) |
| A signature matches offline but a live request fails | Check the actual response and session conditions; a 4xx or timeout alone does not identify transport fingerprinting. | [signing-replay.md](signing-replay.md) |
| A rebuilt app installs but the requested feature fails | Compare the original and a zero-change rebuild through the same pipeline; isolate signing, resources and environment before blaming the patch. | [android-triage.md](android-triage.md), [signing-replay.md](signing-replay.md) |
| A native signer resists static analysis | Reassess the owning library and instrumentation constraints before choosing emulation or tracing. | [ida-workflow.md](ida-workflow.md), [native-emulation.md](native-emulation.md) |
| Android hooks find nothing in a React Native or iOS app | Verify the runtime and follow its request-building and capture route. | [hermes-react-native.md](hermes-react-native.md), [ios-playcover.md](ios-playcover.md) |
| A resumed session repeats an earlier experiment | Read existing facts, refutations and intents before choosing the next experiment. | [state-schema.md](state-schema.md), [agent-runtime.md](agent-runtime.md) |

## Keep experiments attributable

State the requested deliverable and what observation would verify it. Preserve
the input hash, command, output/error, environment, and result of each meaningful
attempt in session artifacts. Change one relevant variable per comparison.
For patching, keep an untouched original and a zero-change pipeline control;
installation or launch alone does not verify the requested feature.

After two attempts fail in the same way, pause that route and reassess the
hypothesis, measurement and tool prerequisites. Do not make a third parameter
variation unless new evidence explains why it should distinguish the cause.
Continue another useful route when available. This checkpoint never overrides
an earlier access denial or rate limit; follow [operating-scope.md](operating-scope.md).

Use the existing `findings.py` schema instead of starting a second ledger:

- Record an observed failure as a fact with the exact command/output reference.
- Mark the specific disproven claim or hypothesis `refuted`, retaining evidence
  and the conditions under which it failed. Tool unavailability does not refute
  a claim about the target, and a failed method does not rule out every route.
- Add an intent for the next discriminating experiment, including which new
  evidence would justify retrying a parked route.
- On handoff, read these entries and the session artifacts before repeating work.

If no row fits, name the uncertainty and choose the smallest scoped experiment
that would identify the owning layer. Report untested steps as untested; a local
inspection or offline verification remains a valid deliverable.
