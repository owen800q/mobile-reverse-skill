# signing-replay.md — reconstruct the signing scheme and prove it (P5)

Enter only when reconstruction is part of the user's objective. Offline sample
verification is sufficient unless a live test is separately requested and
scoped. Required evidence may come from supplied fixtures or earlier analysis:

- the **target feature request** (endpoint, headers, body) captured as ground truth by
  ecapture — including the *actual value* of the client-computed signature/auth
  field for a **known** input (see `ecapture-capture.md`);
- the **code** that builds that field — a Java method, a native `sign()` in a
  `.so`, or both (see `android-triage.md`, `ida-workflow.md`);
- a **named primitive** with fingerprints (see `crypto-id.md`).

The job: assemble those into a function you can run yourself, then **prove it**
by recomputing the captured signature from the captured inputs. A match promotes
the fact about that sample to rung `VERIFIED`. It does not by itself prove
server acceptance or correctness for all inputs.

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

- **match** → the implementation reproduces this sample. Set the relevant fact to rung `VERIFIED`
  and mark the hypothesis `confirmed`:
  ```bash
  python3 scripts/findings.py --out ./re_out set-fact --id fN --rung VERIFIED \
    --status confirmed --tool sign_rebuilder --ref replay.py \
    --verbatim 'recomputed X-Sign == captured a1b2c3…'
  python3 scripts/findings.py --out ./re_out set-hypothesis --id hN --status confirmed
  ```
- **mismatch** → a Step-1 detail is wrong. Iterate the *cheap* variables first,
  since the oracle is fast: concatenation order, separators, casing,
  trailing/leading bytes, encoding, whether the timestamp is the signed one or a
  fresh one. Only after exhausting those should you revisit the primitive itself
  (maybe `crypto-id.md` named it wrong — go back and re-fingerprint).

## Step 4 — optional live validation client

Create or run a live client only when that deliverable is requested and the
session establishes the test service, account, allowed actions, and request
bound. Local package ownership or an offline signature match does not establish
permission to test the backend.

Prefer an owned test environment and synthetic records. If a live test is in
scope, use assets/templates/python_http_validation.py.tmpl as a starting
point, supply credentials locally, and inspect its behavior before execution.
Keep requests bounded. Booking, checkout, cancellation, account changes, and
other state-changing actions need specific authorization; API discovery alone
does not authorize them.

Stop on denial, throttling, or a challenge. Report offline verification and live
results separately. Include the field map, construction, fingerprints, redacted
evidence, and any untested assumptions. Do not publish raw keys or session tokens.

## Step 5 — diagnose a rejected request from evidence

A correct signature for one captured sample does not explain a later 4xx,
empty response, or timeout. Possible causes include expired sessions, nonce
reuse, timestamp skew, serialization differences, missing permissions, request
state, rate limits, application rules, and transport policy.

Inspect the actual status, response body, and diagnostics available in the
authorized test environment. Check the outgoing bytes against the specific
fixture and distinguish facts from possible explanations. Consult the service
owner's logs or supported test configuration when available.

Do not assume TLS fingerprinting from a blocked response, and do not follow an
automatic client-impersonation or challenge-solving ladder. If resolving the
failure requires a change outside the current scope, stop that action and
report the missing evidence or permission. Retain a successful offline result
as an offline result; do not turn it into a claim of live service success.

## Scope / ethics

Only do this against an app and account you are authorized to test. The replay
PoC exists to demonstrate that the signing scheme is understood; do not use it to
attack third-party accounts or infrastructure. See the safety note in `SKILL.md`.
