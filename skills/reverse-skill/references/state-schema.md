# state-schema.md — the findings.json ledger

Every `/reverse-skill` run keeps **one** state file, `findings.json`, in the
project session directory (script default `./re_out/`; pass an absolute `--out`
when invoked through an installed skill). It is the shared record that the phases
write facts, intents and hypotheses to. `validate` and `check-report` run a fixed
set of mechanical checks on it; they do not judge whether an analysis is correct.
Change it through `scripts/findings.py`. `add-fact`, `set-fact`, `add-hypothesis` and
`set-hypothesis` refuse some bad arguments and store the rest as given, so a bad value can
be stored without error. Run `validate` and `check-report` before relying on a ledger.

Why bother with a ledger in a single session? Because the failure mode of
LLM-driven RE is confident fiction: naming an algorithm from a coincidental
constant, or asserting a call path you never actually traced. The ledger keeps
observations (facts, each graded on a rung) apart from guesses (hypotheses, each
with a confidence), so a later phase or a reviewer can tell a *fact* from a
*guess*. The rules below say which of these distinctions `validate` checks.

## Resume across agents

Claude Code and Codex are meant to load the same SKILL.md and the same session
files, including this schema. This was not run under Codex, so whether Codex reads
and writes `findings.json` with this schema is not verified.
Read an existing ledger with `show`; `init` rejects an existing path instead of
resetting it. Start a new session directory for a new investigation. Serialize
writes through one agent because the JSON ledger is not a concurrent database.
The legacy rung names below remain stable for existing callers and files.

## The three record types

Collapsed from Fausto's blackboard (Facts/Intents), Fausto's Guardian evidence
ladder (rungs), and algokiller's hypothesis ledger (fingerprint-gated
primitives):

- **facts** — observations, each graded on a 5-rung evidence ladder.
- **intents** — directed cross-phase targeting ("the signature sinks into
  `libsec.so`; P4 go reverse it"). This is the one piece of cross-phase routing
  worth keeping: a later phase can see what an earlier one routed to it.
- **hypotheses** — named crypto/algorithm guesses, each with a confidence. A medium or
  high one that names a primitive needs a fingerprint (R2).

Coverage is not a fourth record type. It says how much of the target a survey
actually examined, and it has its own section below.

## Schema

```json
{
  "target": "com.example.aa",
  "goal": "reverse login API",
  "phase": 0,
  "created": "2026-10-10T09:00:00",
  "updated": "2026-10-10T09:30:00",
  "input": {"path": "/abs/app.apk", "size": 1234, "sha256": "..."},
  "tools": [{"name": "jadx", "path": "/abs/jadx", "size": 5678, "sha256": "...",
             "version": "1.5.0", "recorded": "2026-10-10T09:05:00"}],
  "facts": [
    {
      "id": "f1",
      "phase": 1,
      "claim": "login endpoint is POST /api/v2/auth/login",
      "rung": "PATTERN",
      "evidence": [
        {"tool": "api_extract", "ref": "LoginApi.kt:31",
         "verbatim": "@POST(\"api/v2/auth/login\")"}
      ],
      "status": "open",
      "samples": [],
      "sample_artifacts": {},
      "control": "",
      "authority": "tool_output",
      "absence": false,
      "coverage_area": ""
    }
  ],
  "intents": [
    {"id": "i1", "from_phase": 3, "target": "libsec.so:Java_..._sign",
     "reason": "X-Sign header is built by a native call", "status": "open"}
  ],
  "hypotheses": [
    {"id": "h1", "phase": 4, "claim": "X-Sign = HMAC-SHA256(secret, user|ts)",
     "primitive": "HMAC-SHA256", "confidence": "low",
     "fingerprints": [], "supports": ["f1"], "contradicts": [], "status": "proposed"}
  ],
  "protocol_map": {
    "auth_fields": [], "signature_fields": [], "endpoint_parameter_map": {}
  },
  "endpoints": [],
  "requests": [],
  "coverage": [
    {"area": "smali classes", "examined": 40, "total": 120,
     "note": "excludes generated R classes", "recorded": "2026-10-10T09:00:00"}
  ],
  "artifacts": {}
}
```

`input` is null unless `init --input` was given. An evidence entry bound with
`--artifact` also has an `artifact` object, `{path, sha256}`, and a fact's
`sample_artifacts` maps each sample label to a `{path, sha256}` object. Facts have
no `confidence` field; hypotheses have one.

### Enumerations
- **rung** (fact evidence ladder, low→high): `PATTERN` → `REACHABLE` →
  `CONTROLLABLE` → `EXPLOITABLE` → `VERIFIED`.
  - `PATTERN`: a static match (a string, an annotation) suggests it.
  - `REACHABLE`: you traced a path that actually reaches it.
  - `CONTROLLABLE`: you can influence its inputs.
  - `EXPLOITABLE`: you can produce a chosen output (e.g. a valid sign for chosen data).
  - `VERIFIED`: reproduced against ground truth (recomputed the captured signature).
- **fact.status**: `open` | `confirmed` | `refuted` | `blocked` | `out_of_scope`.
- **fact.authority**: where the evidence came from, separate from the rung: `source_text`
  (read in the decompiled or decoded source), `tool_output` (a parser or analyzer
  result), `runtime_capture` (observed in a capture or trace), `external_record` (a
  public document or advisory), or `analyst_note` (the analyst's own reading). Set it
  with `--authority`. An `analyst_note` cannot support a rung above `CONTROLLABLE`.
- **hypothesis.supports / hypothesis.contradicts**: lists of fact IDs, set with
  `--supports` and `--contradicts` (repeatable).
- **hypothesis.confidence**: `low` | `medium` | `high`.
- **hypothesis.status**: `proposed` | `confirmed` | `refuted` | `blocked` | `out_of_scope`.
- **disposition**: `blocked` (a step could not run) and `out_of_scope` (the claim or
  step is outside the agreed scope). These are statuses on a fact or hypothesis. The
  ledger has no reason field for them, so say why in the report text. `validate` reports
  a disposed record as INFO and does not count it as verified: it is left out of the
  confirmed-hypothesis check, and a disposed fact is not live support for a hypothesis.
  `validate` still applies R1, R2, R3, the authority rule, the artifact digest and quote
  checks and the link checks to a disposed record, so a disposed record can FAIL; only the
  absence-coverage check exempts a blocked or out_of_scope absence fact.

## The rules and what `validate` checks

The rules below are the ones the ledger is built around. `validate` checks a narrower
version of each, as stated under each rule.

**Fact and hypothesis writes store what they are given, except for the refusals below.**
`add-fact`, `set-fact`, `add-hypothesis` and `set-hypothesis` do not run R1 to R3. They
refuse bad arguments: an unknown rung, status, authority or confidence, an unknown ID for
`set-fact` or `set-hypothesis`, or an artifact that is missing or outside the session
directory.
`add-coverage` refuses impossible counts and a partial area without `--note`. So a fact
that breaks R1 to R3 is stored without error, and `validate` is what reports it.

**R1 — a fact above `PATTERN` needs a verbatim quote.** If you claim you *traced* a
call path or *verified* an endpoint, the fact must carry an `evidence[].verbatim`
snippet copied from a tool's output (a `file:line`, a decompiled line, a captured
request). `validate` checks only that some evidence entry has a verbatim string that is
not blank. It does not check that the text is a copy, so a paraphrase passes. The text
is compared with a file only when the evidence is bound with `--artifact` (see Artifacts
below). A `PATTERN` fact may have no evidence.

**R2 — a hypothesis at `medium` or `high` that names a primitive needs a fingerprint.**
Its `primitive` is tested, or its `claim` when no primitive is given, for a substring in
`PRIMITIVE_TOKENS` in `scripts/findings.py`. The list includes AES, DES, RC4, SHA-256,
HMAC, RSA, ECC, GCM and base64. A match with no `fingerprints[]` entry fails `validate`.
Matching is by substring, so `keccak` matches `ecc`. The hyphenated SHA-384, PBKDF2,
Curve25519 and SHA3-256 match nothing and are not checked (the list has `sha384` without
the hyphen). When `--primitive` is given with text, only that text is tested and the
claim is not, so a `--primitive` of only spaces turns off the claim check. An empty
`--primitive` counts as not given, and the claim is tested.
`add-hypothesis` and `set-hypothesis` accept a medium or high hypothesis with no
fingerprint; `validate` then reports it.

`validate` counts `fingerprints[]` entries. It does not read their labels or text, so it
cannot tell a `constscan.py` "real" or "real_simd" hit, or a `cryptoinstr.py` hit, from
any other entry such as the free text "trust me". Which sources count is a convention (see
`crypto-id.md`). By convention a lone `alu_only` constant, the `0x9e3779b9` golden-ratio
trap, is not a fingerprint, because `constscan.py` says alu_only hits are not proof of a
cipher. `validate` does not enforce that: an entry labelled `constscan:alu_only:0x9e3779b9`
passes like any other.

`high` wants two independent signals (for example a SHA-256 K-table and `sha256h`
instructions), or a `VERIFIED` replay. `validate` warns when a high-confidence primitive
hypothesis has fewer than two entries, whether or not a `VERIFIED` replay exists. It does
not check that entries are independent. Two copies of one entry count
as two: `add-hypothesis` keeps duplicates, and `set-hypothesis` skips an entry that is
already present.

**R3 — `VERIFIED` needs two distinct samples and one control case.** A `VERIFIED` fact
must list at least two distinct sample labels that reproduce the claim (`--sample`), and
one control label (`--control`) that is not one of them. The control is an input
deliberately changed, whose output change the reconstruction predicted or correctly
rejected. One sample verifies one test vector. `validate` counts distinct non-empty
labels and does not check their text, so labels made only of spaces pass. It does not
check that the samples reproduce the claim, that two labels refer to different captures,
or that the control's output change was predicted or rejected; those checks are the
analyst's. A
sample that is not bound with `--sample-artifact` gets a WARN. A `VERIFIED` fact without
these fails `validate`; add them with `set-fact`, or lower the rung if the evidence does
not support it.

### What `validate` exits non-zero on

`validate` exits 1 when it prints any `FAIL` line. The `FAIL` checks are:

- a fact above `PATTERN` with no non-blank verbatim string in its evidence (R1);
- a hypothesis at `medium` or `high` whose primitive (or claim) names a `PRIMITIVE_TOKENS`
  substring, with no fingerprint entry (R2);
- a `VERIFIED` fact with fewer than two distinct sample labels, with no control label, or
  with a control label that is also a sample (R3);
- a bound artifact that is missing, or whose SHA-256 has changed, from `--artifact` or
  `--sample-artifact`;
- an evidence quote that does not appear in its bound artifact;
- an absence fact, not blocked or out_of_scope, whose coverage area has no record, a
  partial one, or a record with malformed counts;
- an `analyst_note` fact above `CONTROLLABLE`;
- an unknown authority, or an invalid rung, fact or hypothesis status, or confidence;
- a `supports` or `contradicts` ID that names no fact;
- a `confirmed` hypothesis that a `confirmed` fact lists in `contradicts`;
- a coverage record whose examined or total is not an integer, whose examined is below 0
  or above total, or whose total is below 1.

`validate` also prints lines that do not fail it:

- `WARN`: a high-confidence primitive hypothesis with fewer than two fingerprint entries;
  a `confirmed` hypothesis with no live supporting fact (a fact linked by `supports` that
  is not refuted or dispositioned); a `confirmed` hypothesis when no VERIFIED fact in the
  ledger meets R3; a VERIFIED fact with a sample that is not bound to an artifact.
- `INFO`: each blocked or out_of_scope fact and hypothesis; each partial coverage area, with
  its note; each fact above `PATTERN` with no authority recorded.

Run it before writing the final report.

## Provenance

`init --input <file>` records the input's absolute path, size and SHA-256. Without
`--input`, `input` is null. `add-tool --name <tool> --path <binary> --version <reported>`
records the binary's SHA-256 and the `--version` string exactly as passed. `add-tool` does
not run the binary, so the version is the analyst's statement, not one read from the tool:
pass the version the tool prints, not the one you expect. Recording a tool does not vouch
for its source revision. A fact's `tool` field is free text and is not checked against the
recorded tools, so the ledger does not show which tool produced a given fact.

## Coverage

`add-coverage --area <name> --examined N --total M [--note "..."]` records how much
of an area was examined: 40 of 120 smali classes, or 7 of 7 rootfs binaries. There is
one record per area, and a later call with the same `--area` replaces it.

A partial area (examined below total) needs a `--note` that says what was left out.
Without one, `add-coverage` exits 2 with "partial coverage needs --note saying what was
left out" and writes nothing. A complete area needs no note. `add-coverage` also refuses
impossible counts: examined below 0 or above total, or total below 1.

Record coverage whenever a conclusion rests on a survey: the classes searched for a method
name, the firmware binaries that were read, the HAR entries that were checked. `validate`
requires a record only for an absence fact (below); for other claims it is the analyst's
record.

`validate` prints an `INFO` line for each partial area, with its note. Partial coverage does
not fail validation by itself. `--coverage-area` is stored on any fact, but only an absence
fact is checked against its area, by `validate` and by `check-report`. A non-absence fact is
not linked to its area, so `check-report` gives it no coverage notice; the `INFO` line from
`validate` is the only notice about partial coverage.

## Absence claims, authority and links

- **Absence needs complete coverage.** A fact recorded with `--absence` says that
  something is not present ("no pinning in the login path"). It must name the area it
  covers with `--coverage-area`, and that area must have an `add-coverage` record with
  `examined == total`. `validate` fails when the record is missing or partial, and
  `check-report` refuses a cited absence claim in the same way. A blocked or out_of_scope
  absence fact is not checked for coverage.
- **Authority is not strength.** A rung says how strong a claim is. An authority says
  where its evidence came from. `validate` fails a fact above `CONTROLLABLE` whose
  authority is `analyst_note`. It does not check the evidence behind any other authority
  label: a fact labelled `tool_output` can carry analyst-written text. A fact above
  `PATTERN` with no authority gets an `INFO` line.
- **Hypotheses link to facts.** A `confirmed` hypothesis needs a live supporting fact (one
  linked by `--supports` that is not refuted or dispositioned), or `validate` warns. It
  fails if a fact it names in `--contradicts` is itself `confirmed`, and it fails if any
  `--supports` or `--contradicts` names a fact ID that does not exist.

## Artifacts and report checks

- `--artifact PATH` on `add-fact` or `set-fact` binds one evidence entry to a
  session-local file and records its SHA-256. The path must be inside the session
  directory. `validate` fails if the file is missing or its SHA-256 has changed. When the
  entry has a non-blank verbatim quote, `validate` also fails if the quote is not in the
  file. The quote check reads the file as UTF-8 text, collapses runs of whitespace on both
  sides, and runs only for files of at most 64 MiB. A file that is not UTF-8, or is over
  64 MiB, is reported as not containing the quote, even when the text is there.
- `--sample-artifact SAMPLE=PATH` binds a sample label to the file that holds it and
  records its SHA-256. `validate` checks that the file is present and that its SHA-256
  matches; it does not check the content. Two labels bound to one file pass.
- `findings.py --out S check-report --report FILE` checks the lines of a written report
  that cite ledger IDs against the ledger, one line at a time. A line that cites a fact or
  hypothesis, as `[fN]`, `[hN]`, or a list such as `[f1, f9]` or `[f1,h2]`, is checked for:
  - an unknown or refuted fact or hypothesis (an error);
  - a citation of an open, blocked or out_of_scope fact (a warning);
  - an absence claim without complete coverage (an error);
  - a rung word above the strongest cited fact (an error). Rung words are matched only in
    capitals. The rung check uses the cited fact's rung whatever its status;
  - a quoted phrase that is not in the verbatim evidence of the cited facts, or in the
    `--artifact` file bound to one of their evidence entries (an error). Files bound with
    `--sample-artifact` are not searched for quotes. A quote is a straight or curly
    double-quoted string of 8 or more characters.

  A line that cites only hypotheses gets the ID checks, and no rung or quote check. A line
  with no citation gets no rung-word check; if it contains a quote of 8 or more characters,
  it gets a warning, because that quote cannot be checked.
  check-report searches the `--artifact` files for quotes, but it does not check their
  digests; `validate` does. A report that fails this check should not be delivered. The
  rung check does not understand negation: write "not verified" on a line without a
  citation, or leave the rung word out of a cited line.

## Typical commands

```bash
S=./re_out
python3 scripts/findings.py --out $S init --target com.example.aa --goal "reverse login API"
python3 scripts/findings.py --out $S set-phase 1
python3 scripts/findings.py --out $S add-fact --phase 1 --rung PATTERN \
  --claim "POST /auth/login" --tool api_extract --ref LoginApi.kt:31 \
  --verbatim '@POST("auth/login")'
python3 scripts/findings.py --out $S add-intent --from-phase 3 \
  --target libsec.so:sign --reason "X-Sign built natively"
python3 scripts/findings.py --out $S add-hypothesis \
  --claim "X-Sign=HMAC-SHA256" --primitive HMAC-SHA256 --confidence low
python3 scripts/findings.py --out $S set-hypothesis --id h1 --confidence high \
  --fingerprint "constscan:sha256_k@0x4120" --fingerprint "cryptoinstr:sha256h" \
  --status confirmed
python3 scripts/findings.py --out $S add-tool --name unblob \
  --path /abs/venv/bin/unblob --version "26.6.4"
python3 scripts/findings.py --out $S add-coverage --area "smali classes" \
  --examined 40 --total 120 --note "excludes generated R classes"
python3 scripts/findings.py --out $S add-fact --rung VERIFIED \
  --claim "X-Sign = HMAC-SHA256(secret, user|ts)" \
  --verbatim 'recomputed sign == captured X-Sign' \
  --sample cap-login-1 --sample cap-login-2 --control cap-login-ts-changed
python3 scripts/findings.py --out $S show
python3 scripts/findings.py --out $S validate
```

## What `init` creates and what writes it

`init` creates `endpoints`, `requests` and `protocol_map` empty, and `artifacts` as an
empty object. No `findings.py` command writes them, and no script in the repository writes
`findings.json`. The phase outputs (`api_endpoints.json`, `requests.json`) are separate
files; record their durable conclusions as facts with `add-fact`. A bound artifact is
stored inside the fact that cites it, in its evidence entry or in `sample_artifacts`, not
in `artifacts`.
