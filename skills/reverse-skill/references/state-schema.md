# state-schema.md — the findings.json ledger

Every `/reverse-skill` run keeps **one** state file, `findings.json`, in the
project session directory (script default `./re_out/`; pass an absolute `--out`
when invoked through an installed skill). It is the blackboard that ties the
phases together, and it is the thing that keeps the analysis honest. Manage it
only through `scripts/findings.py` (which enforces the rules below) — do not
hand-edit it, or the discipline evaporates.

Why bother with a ledger in a single session? Because the failure mode of
LLM-driven RE is confident fiction: naming an algorithm from a coincidental
constant, or asserting a call path you never actually traced. The ledger makes
every durable claim carry its evidence and its confidence, so a later phase (or
a reviewer, or you after a compaction) can tell a *fact* from a *guess*.

## Resume across agents

Claude Code and Codex use this exact schema and the same session artifacts.
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
  worth keeping; it stops each phase from re-deriving the last one's work.
- **hypotheses** — named crypto/algorithm guesses, gated by fingerprints.

## Schema

```json
{
  "target": "com.example.aa",
  "goal": "reverse login API",
  "phase": 0,
  "input": {"path": "/abs/app.apk", "size": 1234, "sha256": "..."},
  "tools": [{"name": "jadx", "path": "/abs/jadx", "version": "1.5.0", "sha256": "..."}],
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
      "control": ""
    }
  ],
  "intents": [
    {"id": "i1", "from_phase": 3, "target": "libsec.so:Java_..._sign",
     "reason": "X-Sign header is built by a native call", "status": "open"}
  ],
  "hypotheses": [
    {"id": "h1", "phase": 4, "claim": "X-Sign = HMAC-SHA256(secret, user|ts)",
     "primitive": "HMAC-SHA256", "confidence": "low",
     "fingerprints": [], "status": "proposed"}
  ],
  "protocol_map": {
    "auth_fields": [], "signature_fields": [], "endpoint_parameter_map": {}
  },
  "endpoints": [],
  "requests": [],
  "artifacts": {"decompile_dir": "", "ecapture_out": "", "ida_db": ""}
}
```

### Enumerations
- **rung** (fact evidence ladder, low→high): `PATTERN` → `REACHABLE` →
  `CONTROLLABLE` → `EXPLOITABLE` → `VERIFIED`.
  - `PATTERN`: a static match (a string, an annotation) suggests it.
  - `REACHABLE`: you traced a path that actually reaches it.
  - `CONTROLLABLE`: you can influence its inputs.
  - `EXPLOITABLE`: you can produce a chosen output (e.g. a valid sign for chosen data).
  - `VERIFIED`: reproduced against ground truth (recomputed the captured signature).
- **fact.status**: `open` | `confirmed` | `refuted` | `blocked` | `out_of_scope`.
- **hypothesis.confidence**: `low` | `medium` | `high`.
- **hypothesis.status**: `proposed` | `confirmed` | `refuted` | `blocked` | `out_of_scope`.
- **disposition**: `blocked` (a step could not run; say why) and `out_of_scope` (the
  claim or step is outside the agreed scope). Dispositions are recorded and reported,
  and are never counted as verified.

## The enforced rules (`findings.py validate`)

**R1 — no rung above PATTERN without a verbatim quote.** If you claim you
*traced* a call path or *verified* an endpoint, the fact must carry an
`evidence[].verbatim` snippet copied from a tool's output (a `file:line`, a
decompiled line, a captured request). Paraphrase does not count. This is what
stops "I'm confident the flow goes A→B→C" from being recorded as if observed.

**R2 — no primitive name at confidence ≥ medium without a fingerprint.** A
hypothesis whose `primitive`/`claim` names a crypto primitive (AES, SHA-256,
SM4, HMAC, TEA, …) may not be raised to `medium` until it has at least one
`fingerprints[]` entry — a `constscan.py` "real"/"real_simd" hit or a
`cryptoinstr.py` instruction hit. `high` wants **two** independent signals
(e.g. a SHA-256 K-table *and* `sha256h` instructions), or a `VERIFIED` replay.
A lone `alu_only` constant (the `0x9e3779b9` golden-ratio trap) is not a
fingerprint. See `crypto-id.md`.

**R3 — VERIFIED needs two distinct samples and one control case.** A `VERIFIED`
fact must list at least two distinct captured samples that reproduce the claim
(`--sample`), and one control case (`--control`): an input deliberately changed,
whose output change the reconstruction predicted or correctly rejected. One sample
verifies one test vector. A `VERIFIED` fact without these fails `validate`; add them
with `set-fact`, or lower the rung if the evidence does not support it.

`validate` exits non-zero on any R1, R2, or R3 violation. It prints warnings for
weaker smells (high confidence on one signal; `status:confirmed` without a fact that
meets R3). It prints `INFO` lines for dispositions. Run it before writing the final
report.

## Provenance

`init --input <file>` records the target's absolute path, size, and SHA-256.
`add-tool --name <tool> --path <binary> --version <reported>` records each engine's
binary SHA-256 and the version string it reports. Use the version the tool prints,
not the one you expect. Readers can then tell which bytes and which engine produced
a result. Recording a tool does not vouch for its source revision.

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
python3 scripts/findings.py --out $S add-fact --rung VERIFIED \
  --claim "X-Sign = HMAC-SHA256(secret, user|ts)" \
  --verbatim 'recomputed sign == captured X-Sign' \
  --sample cap-login-1 --sample cap-login-2 --control cap-login-ts-changed
python3 scripts/findings.py --out $S show
python3 scripts/findings.py --out $S validate
```

`endpoints`, `requests`, and `protocol_map` are populated from the phase
scripts' own JSON outputs (`api_endpoints.json`, `requests.json`); copy the
durable conclusions in as facts. `artifacts` just records where the big outputs
live so later phases and the report can find them.

