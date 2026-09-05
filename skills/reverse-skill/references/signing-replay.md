# signing-replay.md — reconstruct the signing scheme and prove it (P5)

Use this phase only when the task calls for reconstructing request signing.
Apply the objective and scope selected in `SKILL.md`; a live test is optional.
For local verification, you need:

- the **relevant request** (endpoint, headers, body) from a supplied fixture or
  scoped capture — including the *actual value* of the client-computed signature/auth
  field for a **known** input (see `ecapture-capture.md`);
- the **code** that builds that field — a Java method, a native `sign()` in a
  `.so`, or both (see `android-triage.md`, `ida-workflow.md`);
- an evidence-backed description of the transform; if a primitive is named,
  its supporting fingerprints (see `crypto-id.md`).

The job: assemble those into a function you can run yourself, then **prove it**
by recomputing the captured signature from the captured inputs. A match promotes
the fact to rung `VERIFIED` for that test case. It does not prove server
acceptance or correctness on every input.

## Why ecapture makes this tractable

Because ecapture hands you a known plaintext → known signature pair, P5 is a
*verification* problem, not a *search* problem. You are not guessing a key out of
the ether; you are checking whether `f(inputs) == captured_signature` for a
candidate `f`. That oracle also disambiguates the fiddly bits that static
reading leaves open: input concatenation order, field casing, trailing
separators, encoding (hex vs base64 vs base64url), and whether a timestamp or
nonce is inside the signed string.

## Step 1 — pin down the signed string

From the code, determine exactly what bytes go into the primitive:

- **which fields**, in **which order** (e.g. `appid + timestamp + body + secret`);
- **separators** (`&`, `|`, none), and whether keys are sorted;
- **the key / secret**: a hardcoded constant (grep it, `secrets.json`), a value
  derived at runtime (KDF, device id), or an HMAC key;
- **pre/post encoding**: is the input UTF-8 of a JSON string? is the output hex,
  base64, base64url, or raw bytes in a header?

Record each as a fact with the verbatim code line. If the builder is native and
unreadable statically, get the input/output pair directly by hooking it
(`assets/frida/hook_crypto.js` dumps `javax.crypto` in/out/key/iv;
`assets/frida/jni_trace.js` traces the JNI call) or emulate it
(`native-emulation.md`).

## Step 2 — reconstruct with `sign_rebuilder.py`

`scripts/sign_rebuilder.py` implements the common primitives and lets you chain
them, so you rarely have to write crypto by hand. It covers hashes (md5, sha1,
sha224/256/384/512, sm3), HMAC variants, symmetric ciphers (aes, des, sm4 in the
usual modes), and asymmetric signing (rsa, ecdsa), plus chained pipelines
(e.g. `sha256` then `base64`). Point it at the algorithm from `crypto-id.md` and
the signed string from Step 1.

`sign_rebuilder.py` is **config-driven**: you describe the scheme in a small JSON
config (algorithm, key, which fields in which order, encoding), then run it
against the captured payload.

```bash
# 1. print sample configs to see the schema:
python3 scripts/sign_rebuilder.py --example

# 2. write sign.json for your scheme, then reproduce the signature. -v prints the
#    exact sign-input string it built — invaluable for fixing field order/seps:
python3 scripts/sign_rebuilder.py --config sign.json \
  --payload '{"user":"a","ts":"1699...","secret":"..."}' -v

# or drive it straight from captured traffic (uses the first request):
python3 scripts/sign_rebuilder.py --config sign.json --traffic-file re_out/requests.json
```

`--auto-config <crypto_native_analysis.json|vuln_analysis.json>` can generate a
starting config from P4 output, and `--override-key` swaps the key without
editing the file.

If the app uses a **custom** or **white-box** transform (no textbook primitive —
`crypto-id.md` tells you when to stop naming one), do not force it into
`sign_rebuilder.py`. Instead port the recovered algorithm to a small standalone
script, or wrap the native function via Frida RPC / unidbg and call it as a black
box. Either way the verification in Step 3 is identical.

## Step 3 — verify against ground truth (the oracle)

Recompute the signature from the **captured** inputs and compare to the
**captured** signature value:

- **match** → the implementation reproduces this test vector. Set the relevant fact to rung `VERIFIED`
  and mark the hypothesis `confirmed`:
  ```bash
  python3 scripts/findings.py --out ./re_out set-fact --id fN --rung VERIFIED \
    --status confirmed --tool sign_rebuilder --ref replay.py \
    --verbatim 'recomputed X-Sign == captured a1b2c3…'
  python3 scripts/findings.py --out ./re_out set-hypothesis --id hN --status confirmed
  ```
- **mismatch** → check the fixture inputs and reconstruction; the cause is not yet established. Iterate the *cheap* variables first,
  since the oracle is fast: concatenation order, separators, casing,
  trailing/leading bytes, encoding, whether the timestamp is the signed one or a
  fresh one. Only after exhausting those should you revisit the primitive itself
  (maybe `crypto-id.md` named it wrong — go back and re-fingerprint).

## Step 4 — optional live validation

Local reconstruction can complete P5. Build or run a live validation client only
when the user requested it and the endpoint, account and operation are in scope.
Respect authorization already provided; clarify only missing material scope.
Use a test environment when available and synthetic/test-account inputs. A
booking, purchase or other state-changing operation needs authorization for that
specific action; API documentation alone does not provide it.

For an in-scope test, `assets/templates/python_http_validation.py.tmpl` is a
starting point to inspect and adapt, not a command to execute unchanged. Limit
the test to the intended operation, avoid automatic retries, respect documented
limits and stop on challenges or access denials. Keep secrets out of source and
shared output. Report local-vector verification separately from the live result.
Describe key derivation with redacted values rather than publishing usable keys.

## Step 5 — diagnose a failed live validation from evidence

This is **Gate D** in `SKILL.md`. Matching a captured signature establishes a
local input/output result. It does not prove the current session, nonce,
permissions, serialization or server-side state are valid. A 4xx response,
empty payload, challenge or timeout does not identify TLS fingerprinting as the
cause.

Review the existing request and response, timestamps, session validity, nonce
freshness, body encoding, required fields and documented limits. If available,
use server logs or the authorized test environment to distinguish hypotheses.
TLS/client compatibility is one possible hypothesis and needs its own evidence;
do not mark it confirmed merely because a signature matched.

Record the failure and stop repeated requests when the service blocks or
challenges the client. Do not automatically switch impersonation profiles,
solve challenges or escalate transport techniques. Further testing requires a
specific in-scope question and evidence that the proposed step addresses it.
A report with a verified local fixture and an unresolved live failure is a valid
result; do not describe it as a successful replay.

## Scope / ethics

Only do this against an app and account you are authorized to test. The replay
PoC exists to demonstrate that the signing scheme is understood; do not use it to
attack third-party accounts or infrastructure. See the safety note in `SKILL.md`.

