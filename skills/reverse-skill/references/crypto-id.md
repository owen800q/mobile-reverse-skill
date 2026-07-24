# Crypto / Algorithm Identification

The **P4** phase of `reverse-skill`: put a *name* on the client-side login-signing / encryption
primitive — "this is HMAC-SHA256", "this is SM4-CBC", "this is a custom XXTEA" — using only evidence
you can point at. You arrive here from `ida-workflow.md` (the decompiled/traced sign function) or from
a Frida/GumTrace capture. You leave with named, evidence-backed hypotheses recorded in `findings.json`.

**Why this phase has its own discipline.** Naming a crypto primitive is the single highest-leverage
place to hallucinate. An LLM that "recognizes" AES from a function name, or SHA-256 from a vibe, will
confidently emit a wrong primitive — and every downstream step (`signing-replay.md` reconstruction,
the Python replayer, the request you send to the server) inherits that lie and fails silently. A wrong
name is worse than no name: it *looks* like progress and burns the whole budget chasing a key that
isn't there. This doc exists to force every name through a fingerprint gate before it can poison the
reconstruction.

## Contents

1. [The identification workflow](#1-the-identification-workflow)
2. [The VERDICT taxonomy and the alu_only trap](#2-the-verdict-taxonomy-and-the-alu_only-trap)
3. [The ledger discipline (anti-hallucination core)](#3-the-ledger-discipline-anti-hallucination-core)
4. [Constant cheatsheet](#4-constant-cheatsheet)
5. [The obfuscation fork — stop hunting for a key](#5-the-obfuscation-fork--stop-hunting-for-a-key)

Siblings: `ida-workflow.md` (get the function) · `signing-replay.md` (reconstruct + verify) ·
`state-schema.md` (findings.json / ledger fields) · `android-triage.md` (static API discovery).

---

## 1. The identification workflow

Four steps, in order. Do not skip ahead — naming an algorithm while still in Detection is the
classic phase-error that produces confident nonsense.

| Step | Goal | Action |
|-|-|-|
| **Detection** | Are there any crypto signals at all, and where? | Run both scanners over the sign function's bytes / trace |
| **Identification** | Which primitive family does each signal name? | Read the JSON `verdict` + `evidence`, cross-check families |
| **Analysis** | Is it stock or modified? What mode / round count? | Data-flow around the fingerprint: key schedule, round count, table access |
| **Extraction** | Reproduce and prove it | Hand to `signing-replay.md`; recompute the captured signature |

**Run the two scanners on the sign function you isolated in `ida-workflow.md`.** They are
complementary blind-spot patches for each other — run *both*, always.

```bash
scripts/constscan.py   <target.so|func_bytes.bin>  --out out/   # constant fingerprints -> const_fingerprints.json
scripts/cryptoinstr.py <target.so|func_bytes.bin>  --out out/   # ARM Crypto-Extension insns -> crypto_instr.json
```

- **`constscan.py`** scans for cryptographic *constant* fingerprints — hash IVs, round-constant
  tables (SHA-256 K[], MD5 T[], SM3 T_j), S-boxes, deltas, HMAC pads, CRC polynomials, base64
  alphabets. Emits `const_fingerprints.json`: one record per fingerprint with a `verdict` (§2), a `category`
  (hash / cipher_sym / mac / crc / ecc), an `evidence` breakdown (`load_imm` / `mem_r` / `alu` /
  `simd_broadcast`), and `sample_lines` / offsets you cite verbatim.
- **`cryptoinstr.py`** scans for ARMv8 Crypto-Extension *instructions* (`aese/aesmc/aesd/aesimc`,
  `sha1*`, `sha256h/su*`, `sha512*`, `sm3*`, `sm4e/sm4ekey`, `pmull/pmull2`, `eor3/rax1/xar/bcax`).
  This is the patch for constscan's blind spot: when the binary uses hardware crypto (Android
  Keystore HW path, BoringSSL ARM, libsodium-arm), the software S-boxes and constant tables vanish
  entirely — only the instructions themselves reveal the algorithm. **`cryptoinstr.py` is AArch64-only:**
  empty output on an x86/x86_64 or `armeabi-v7a` lib means "scanner N/A for this ABI", **not** "no hardware
  crypto" — corroborate with `constscan.py` before concluding anything.

**Read them together, that is the whole point:**

- constscan hit + cryptoinstr **0** ⇒ pure software implementation (typical self-rolled sign `.so`
  running MD5/SHA/AES-Te/SM3 software T-tables).
- constscan **0** + cryptoinstr hit ⇒ pure hardware crypto. `AES.Te0 = 0` does **not** mean "no AES"
  if `aese` fired — it means AES ran in hardware.
- both hit ⇒ hybrid (hot path hardware, fallback software).
- both **0** ⇒ either no crypto in this slice, or it is obfuscated / white-boxed and both scanners
  are blind — go to §5, do not start guessing.

---

## 2. The VERDICT taxonomy and the alu_only trap

Every `const_fingerprints.json` record carries a `verdict`. **The verdict is the source of truth, not
`total_hits`.** A high hit count with a bad verdict is noise, not signal.

| verdict | Meaning | Trust it? |
|-|-|-|
| `real` | Scalar literal genuinely loaded (`load_imm > 0`) or read from a constant table (`mem_r > 0`) | Yes — primary signal |
| `real_simd` | NEON broadcast evidence (e.g. `movi v0.16b, #0x36` for HMAC ipad) | Yes — primary signal |
| `weak` | Only indirect signal (`mem_w` / computed address), no direct load | Corroboration only, never alone |
| `alu_only` | The "constant" is an ALU-arithmetic collision, a false positive | **Ignore. Always.** |

**The `alu_only` trap — internalize this, it is the most common way this phase goes wrong.** Some
famous crypto constants are also generic arithmetic values that fall out of ordinary code by
coincidence:

- **`0x9e3779b9`** (golden ratio × 2³²) is the TEA/XTEA/XXTEA `delta`. It is **also** a standard
  hash-mixing constant used all over non-crypto code (hashmap spreaders, PRNGs, `boost::hash_combine`,
  Fibonacci hashing). A lone `0x9e3779b9` is **not** proof of a cipher. Worse: `0x9e3779b9` added to
  itself is `0x3c6ef372` = SHA-256's `h2` init word — the scanner can register a phantom SHA-256 hit
  from pure TEA arithmetic. This is exactly why `verdict` exists and why `total_hits` lies.
- **A single CRC polynomial** (`0xEDB88320`) can appear from a table generator or a non-crypto
  checksum and does not prove a keyed primitive.

**Rule: never name a primitive from an `alu_only` hit alone.** An `alu_only` on `0x9e3779b9` earns
you a *candidate* to investigate (does the 32-round Feistel shape exist? is there a `sum += delta`
loop?), never a named conclusion. Promote it only when a `real` signal or a matching data-flow
shape appears alongside it.

---

## 3. The ledger discipline (anti-hallucination core)

Ported from AlgoKiller, kept lightweight. These four rules are the reason a named primitive in
`findings.json` can be trusted. They map directly onto the `hypotheses[]` entries defined in
`state-schema.md` — each hypothesis is `{ claim, confidence, fingerprints[], status }`, carrying **two
independent axes**: `confidence` ∈ {low, medium, high} **and** `status` ∈ {proposed, confirmed, refuted}.
Rules 1–4 below are the P4-specific expansion of the generic **R1/R2** enforcement rules defined in
`state-schema.md` (and checked by `scripts/findings.py validate`).

**Rule 1 — No primitive name without a fingerprint.** You may **not** write a crypto primitive name
(AES / SHA-256 / SM4 / HMAC / …) into a `findings.json` `claim` unless you hold **at least one**
concrete fingerprint for it:

- a constscan `real` or `real_simd` hit, **or**
- a `cryptoinstr` hit, **or**
- a recovered constant table with **immediate-sequence evidence** (you saw the actual table bytes /
  the `movz/movk` immediate sequence that builds them, not just one lucky word).

No fingerprint ⇒ the name does not go in. A function called `sign()` or `aesEncrypt()` is a *lead*,
not a fingerprint — names are attacker-controlled and routinely lie. Each qualifying fingerprint is
appended to the hypothesis's `fingerprints[]` array with its verbatim anchor.

**Rule 2 — Two independent signals before `confidence = high`.** A single fingerprint gets you
`confidence = low` or `medium`. Reaching `high` requires **≥2 independent signals** for the same
claim — independent meaning *different evidence type*, not two reads of the same table. Examples that
qualify:

- a SHA-256 K-table (`constscan real`) **and** `sha256h` instructions (`cryptoinstr`), or
- an HMAC `ipad/opad` `real_simd` broadcast **and** a matching double-hash data-flow, or
- a recovered constant **and** a round-count / block-shape data-flow that matches the primitive.

**Rule 3 — Evidence is quoted, never paraphrased.** Every entry in `fingerprints[]` must quote the
tool output **verbatim** — the offset, the `sample_lines` line, the exact `verdict` and `evidence`
fields. Write `const_fingerprints.json: SHA256.K[0] verdict=real load_imm=1 @ 0x14a20` — not "constscan found
SHA-256". Paraphrase is where hallucinated detail creeps in; a verbatim offset is checkable.

**Rule 4 — Behavioral verification is the ultimate proof, recorded as a FACT.** The strongest possible
evidence is *not* a constant — it is reproducing the captured signature. Hand the named hypothesis to
`signing-replay.md`, reconstruct the primitive with the recovered key/inputs, and recompute the
signature you captured on the wire. **A byte-for-byte match is recorded as a linked FACT at rung
`VERIFIED`** — the top of the fact evidence ladder (recomputing the captured signature) — which is what
lets you set the hypothesis `status = confirmed`. A constant tells you what the code *looks like*; a
matching recomputation proves what it *does*.

**The two axes (not one ladder).** Track each hypothesis on two independent fields, never conflate them:

- **`confidence` ∈ {low, medium, high}** — raise it as fingerprints accumulate: `low` on a first
  qualifying fingerprint, `medium` once a primitive is named on that fingerprint (Rule 1), `high` only
  with ≥2 independent signals (Rule 2).
- **`status` ∈ {proposed, confirmed, refuted}** — `proposed` on creation; move to `confirmed` when a
  linked `VERIFIED` fact proves the claim (Rule 4), or `refuted` when evidence contradicts it.

`verified` is **not** a hypothesis status — it is the `VERIFIED` rung on the linked *fact*. Downgrade
either axis freely when evidence contradicts; never upgrade without the corresponding rule satisfied.

---

## 4. Constant cheatsheet

A `real` hit on one of these is a strong candidate — but still cross-check block size, round count,
and structure per Rule 2 before naming. The **Role** column flags the usual deployment: **sign** =
API request signing, **enc** = body/payload encryption.

| Primitive | Signature constant(s) | Role |
|-|-|-|
| SHA-256 | K[0]=`0x428a2f98` (64-word K table); IV[0]=`0x6a09e667` | sign |
| SHA-1 | IV=`0x67452301 efcdab89 98badcfe 10325476 c3d2e1f0` | sign |
| MD5 | T/sine table T[1]=`0xd76aa478`; IV=`0x67452301 efcdab89…` | sign |
| AES | S-box[0]=`0x63`; Te0[0]=`0xc66363a5`; Rcon `01 02 04 08…1b 36` | enc |
| SM3 | IV=`0x7380166f …`; T_j=`0x79cc4519` (r0-15) / `0x7a879d8a` (r16-63) | sign |
| SM4 | SBOX[0]=`0xd6`; FK=`0xa3b1bac6 …`; CK[0]=`0x00070e15` | enc |
| TEA/XTEA/XXTEA | delta=`0x9e3779b9` — **alu_only unless** paired with the 32-round Feistel `sum+=delta` shape | sign |
| HMAC | ipad=`0x36` / opad=`0x5c` (often `movi v.16b,#0x36` → `real_simd`) | sign |
| CRC32 | `0xEDB88320` (reflected) / `0x04C11DB7` (normal) | sign(weak) |
| base64 | alphabet `ABC…XYZabc…xyz0-9+/` (and url-safe `-_`) | encode |
| RC4 | **no constant** — identify by the 256-byte KSA swap loop (`S[i]↔S[j]`, `j=(j+S[i]+key)&0xff`) | enc |
| GHASH / GCM | reduction `0xE1000000…` + `pmull/pmull2` | enc |
| Poly1305 | clamp `0x0ffffffc` (r &= `…0ffffffc0ffffffc0fffffff`) | sign(MAC) |

**Reading the roles.** Request-signing schemes on Android are dominated by **HMAC-SHA256, plain
MD5, SM3, and custom-TEA/XXTEA** over a canonicalized param string. Body/payload encryption is
usually **AES-CBC or AES-GCM, SM4, or RC4**. AEAD combos (AES-GCM = AES + GHASH + tag compare;
ChaCha20-Poly1305 = `expand 32-byte k` + Poly1305 clamp) appear when both confidentiality and
integrity are wanted. RC4 has **no constant** — you must recognize it structurally by the KSA swap
loop, so it will never show up in constscan; a `.so` doing a 256-entry byte-permutation swap loop
with no crypto constants is your RC4 tell.

---

## 5. The obfuscation fork — stop hunting for a key

If both scanners come back empty (§1: both 0) *and* the function does not disassemble into
recognizable crypto shapes, check for obfuscation before assuming "no crypto". You are at a fork:
one branch names a textbook primitive, the other treats the function as a black box you *replay*.
Taking the wrong branch wastes the entire budget.

**Signals you are on the black-box branch:**

- **OLLVM / control-flow flattening** — one giant function, a `switch_var` dispatcher, `cmp
  wSW,#N; b.eq` chains or an indirect jump table, real blocks buried in case bodies.
- **VMP / self-rolled VM** — a dispatcher hit thousands of times, `ldr xN,[xCTX,xOP,lsl#3]; br xN`
  handler-table jumps, a fixed VM-context register, opcode-like immediates.
- **White-box crypto** — huge lookup tables (16-256 KB, vs 4 KB for a stock AES T-table), **no**
  recognizable round constants or S-box first byte, `xor-table-xor` sandwiched rounds, and — the
  decisive tell — **no key is ever loaded** (the key is baked into the tables).

**When any of these fires, STOP trying to name a textbook primitive.** Do not report "custom AES"
from a white-box; do not attempt to reverse VM opcodes to recover a constant; **do not keep hunting
for a key that does not exist as a loadable value.** The correct move is to pivot to **dynamic
capture** and treat the sign function as a black box you feed and observe, not a primitive you name:

- Hook the JNI boundary and the crypto calls with `assets/frida/jni_trace.js` and
  `assets/frida/hook_crypto.js` — capture the *actual* inputs and outputs of the sign function at
  runtime (plaintext in, signature out), regardless of what happens inside.
- Or drive a GumTrace of the function and recover the **semantic-operator sequence** on the I/O
  buffer (which XOR / ADD / ROL / table-lookup steps actually touch the input→output data), ignoring
  the dispatcher machinery.
- Record the result in `findings.json` as an obfuscated black-box hypothesis: `claim` = "sign fn is
  OLLVM-flattened / VMP / white-box, primitive not statically nameable", `status = proposed`, with
  the obfuscation fingerprints cited. Then hand the captured I/O pairs to `signing-replay.md` and
  replay the function as an oracle — you reproduce its behavior without ever naming the primitive.

This is the "stop hunting for a key" fork: a black box you can replay end-to-end is a complete
deliverable; a hallucinated primitive name is a broken one.

---

Hand off: named + fingerprinted primitive → `signing-replay.md` to reconstruct and recompute the
captured signature (Rule 4 verification). Ledger field definitions → `state-schema.md`. Need to
re-isolate or re-decompile the sign function → back to `ida-workflow.md`.
