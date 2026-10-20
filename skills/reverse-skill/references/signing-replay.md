# signing-replay.md — reconstruct the signing scheme and prove it (P5)

This is the payoff phase. By now you have, from earlier phases:

- the **login request** (endpoint, headers, body) captured as ground truth by
  ecapture — including the *actual value* of the client-computed signature/auth
  field for a **known** input (see `ecapture-capture.md`);
- the **code** that builds that field — a Java method, a native `sign()` in a
  `.so`, or both (see `android-triage.md`, `ida-workflow.md`);
- a **named primitive** with fingerprints (see `crypto-id.md`).

The job: assemble those into a function you can run yourself, then **prove it**
by recomputing the captured signature from the captured inputs. A match supports
that vector. Promote to `VERIFIED` only when the ledger's independent samples and
control requirements are met (`state-schema.md`, R3). Offline verification does
not establish fresh-session behavior or live server acceptance; report those separately.

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
unreadable statically, use supplied test vectors or isolated emulation
(`native-emulation.md`). When runtime observation is needed and in scope,
`assets/frida/hook_crypto.js` observes `javax.crypto` in/out/key/iv and
`assets/frida/jni_trace.js` traces JNI calls. Keep collected secrets private.

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

- **match** → record the reproduced vector and its artifact. One match is not
  sufficient for `VERIFIED`. When at least two independent samples and a distinct
  control satisfy R3, promote the fact with the actual sample/control identifiers
  (`state-schema.md`). Keep offline reproduction separate from server acceptance.
- **mismatch** → a Step-1 detail is wrong. Iterate the *cheap* variables first,
  since the oracle is fast: concatenation order, separators, casing,
  trailing/leading bytes, encoding, whether the timestamp is the signed one or a
  fresh one. Only after exhausting those should you revisit the primitive itself
  (maybe `crypto-id.md` named it wrong — go back and re-fingerprint).

## Step 4 — build the replay PoC

Once the captured vector is verified, build a minimal validation client using
`assets/templates/python_http_validation.py.tmpl` when that deliverable is in
scope. Execute it only against the agreed environment with a test account and
bounded requests. An offline-only task ends with a reproducible local vector;
it does not require contacting a service. Record unexecuted validation explicitly.

Report the endpoint, parameter map, signed-string construction, primitive and
fingerprints, key derivation (with secret values redacted), captured-vs-recomputed
result, and any separately observed server result. Never call an unrun PoC a
passing replay.

## Step 5 — diagnose failed live validation

This is **Gate D** (see `SKILL.md`). A matching signature with a 4xx, empty body,
challenge, or timeout does not identify the cause. Preserve the response status,
redacted headers/body, timing, and request construction as separate evidence.

Check the following against the captured client behavior:

- Byte serialization, encoding, signed fields, and content type.
- Token lifetime, cookies, nonce reuse, timestamp/clock skew, and device binding.
- Endpoint/API version, required request order, and account permissions.
- Rate limits, service errors, and transport/protocol differences.

TLS ClientHello (JA3/JA4), HTTP version, and client profiles are possible
transport variables. In an authorized staging/lab comparison, tools such as
`curl_cffi`, `tls-client`, or `utls` can help isolate these differences. Change
one variable at a time, compare logs, and record the selected profile and result;
do not infer a WAF cause or promise that a profile will pass. Do not rotate
profiles or identities to continue past a denied production request.

Use explicit request timeouts and the agreed attempt limit. Honor a rate-limit
or access-denial response and stop at that boundary unless the approved test
procedure specifically covers it. Preserve the offline result and report what
additional test-environment access or server-side evidence would resolve the gap.

## Scope / ethics

Apply `operating-scope.md` to each operation. Local analysis and offline
reconstruction from supplied artifacts or test vectors do not require ownership
of a third-party app or a publisher approval letter. Instrumentation and secret
collection use the established device/app/data scope. Live replay separately
needs the agreed endpoint, account, action, environment, and attempt limit.
An offline result is complete without a live PoC when that is the requested task.

