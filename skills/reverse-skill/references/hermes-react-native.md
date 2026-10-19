# hermes-react-native.md — reversing Hermes / React Native (CRN) apps

On-demand reference for when the feature you're after is built in **React Native**
(Ctrip calls theirs CRN), not native Java/Kotlin. The `android-triage.md` login
playbook (Retrofit interface → repository → ViewModel) finds nothing, because the
request builders live in a **JS bundle**, not in DEX. The big win: the bundle
usually ships **plain minified JS** alongside the Hermes bytecode, so you read the
request builders directly — no Hermes decompilation.

Load this when P0 detects RN. Route back to `signing-replay.md` for reconstruction
and, when runtime evidence is needed within established device/app/data scope,
`heap-scan-capture.md` for a bounded object inspection. A local bundle analysis
does not require a live heap read or request.

Siblings: `android-triage.md` (native path) · `heap-scan-capture.md` (persisted RN
getData store is the easiest plaintext capture) · `optional-platforms.md` (other
non-Java frameworks).

## Detect

- `libhermes.so` and/or `libreactnativejni.so` in `lib/<abi>/`.
- UI bundles under app data dirs, not in the APK. Ctrip:
  `/data/data/<pkg>/app_ctripwebapp6/<product>/`, product dirs named like
  `rn_xtaro_hotel_map`. Prefer supplied bundles. If acquisition of that named
  product directory is within established device/app/data scope, a root copy is:
  `adb shell "su -c 'cp -r /data/data/<pkg>/app_ctripwebapp6/<product> /data/local/tmp/'"` then `adb pull`.

## KEY WIN — check for the .jsbundle first

A packaged product often ships **both**:

- `rn_business.hbcbundle` — Hermes bytecode (needs disassembly), and
- `rn_business.jsbundle` — **plain minified JS, ~4 MB, directly readable**.

If the `.jsbundle` is present you do **not** need to decompile Hermes. Pull it and
grep the request builders. Always look for `.jsbundle` before reaching for any
bytecode tool.

## Workflow (from a .jsbundle)

Start from a **service method name** you know (from UI strings, network capture, or
a native-side SOA2 code), e.g. `getMapListForMapDrag`. Then in the minified JS find:

1. **The service registry** — a `{productId, serviceCode}` table that maps the
   symbolic service to the numeric SOA2 code actually sent on the wire. Grep the
   method name, then the productId/serviceCode near it.
2. **The body builder** — a `buildMapParamCore`-style function that assembles the
   request object. The minified JS reveals exact **field names, nesting, enum
   string values** (e.g. `queryType: "Preload" | "MapDrag" | ...`), and **which
   fields are stringified-JSON** vs nested objects. This is everything P5 needs.

Compare the recovered object shape with supplied test vectors or captures.
If the objective requires runtime confirmation and it is in scope, use a bounded
heap observation (`heap-scan-capture.md`); object lifetimes vary. Record the gap
when that evidence is unavailable instead of making a live read mandatory.

## If only .hbcbundle exists

- `hbctool` or `hermes-dec` to disassemble the bytecode, **matched to the Hermes
  bytecode version** (check the header; version-locked like every snapshot format).
- Or hook `libhermes` JSI calls (`hermes::vm::` / `facebook::jsi::`) to observe
  strings and calls at runtime.
- But re-check for a `.jsbundle` in every product dir first — one readable bundle
  saves the whole detour.

## Two traps that cost real time

**The two-phase / session-token trap.** RN feature flows often split into a
self-contained first-load call and session-bound follow-ups:

- The **list / first-load** service (Ctrip: `getmaplistforpreload`) is
  self-contained — city + dates + bounds → hotels + prices — and **replayable**.
- The **refresh** services (`getmaplistforasyncprice`, `dynamicbusprice`) need
  per-item `tag` / `traceKey` tokens **minted by the list call** and bound to a
  `mapSessionId` → **not** standalone-replayable.

Identify these dependencies in the service registry. For a requested, scoped
replay, reproduce the intended flow using the agreed test account/environment;
do not select a different endpoint merely because it has fewer session checks.

**The head-completeness trap.** A minimal SOA2 `head` returned `Ack:"Success"` but
**empty data**. The full head was required to get real rows: `syscode`, `auth`
(session ticket), `lang`, and a rich `extension[]`. Lesson: capture and replay the
**complete** head, not a hand-minimized one — `Ack:"Success"` + empty data is the
possible symptom of missing fields. Compare the full construction and response
before assigning a cause; the same symptom can have other explanations.

## Handoff

You now have: the wire service code (registry), the exact body schema and enum
values (builder), and the complete head (capture). Reconstruct and verify in
`signing-replay.md`. A byte-correct signature does not establish the cause of a
failed live request; use its Gate D diagnosis and preserve the offline result.
