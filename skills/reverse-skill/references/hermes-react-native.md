# hermes-react-native.md — reversing Hermes / React Native (CRN) apps

On-demand reference for when the feature you're after is built in **React Native**
(Ctrip calls theirs CRN), not native Java/Kotlin. The `android-triage.md` login
playbook (Retrofit interface → repository → ViewModel) finds nothing, because the
request builders live in a **JS bundle**, not in DEX. The big win: the bundle
usually ships **plain minified JS** alongside the Hermes bytecode, so you read the
request builders directly — no Hermes decompilation.

Load this when P0 detects RN. Route back to `signing-replay.md` for reconstruction
and `heap-scan-capture.md` to confirm recovered params against the live heap.

Siblings: `android-triage.md` (native path) · `heap-scan-capture.md` (persisted RN
getData store is the easiest plaintext capture) · `optional-platforms.md` (other
non-Java frameworks).

## Detect

- `libhermes.so` and/or `libreactnativejni.so` in `lib/<abi>/`.
- UI bundles under app data dirs, not in the APK. Ctrip:
  `/data/data/<pkg>/app_ctripwebapp6/<product>/`, product dirs named like
  `rn_xtaro_hotel_map`. Pull the whole product dir with root:
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

Confirm the recovered object shape against the live app with a heap freeze
(`heap-scan-capture.md`) — the persisted RN getData store holds these params long
enough to grab.

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

Lesson: for standalone replay, target the **discovery / first-load** endpoint;
avoid session-token-chained follow-ups. Identify which is which in the service
registry before you invest in a replay.

**The head-completeness trap.** A minimal SOA2 `head` returned `Ack:"Success"` but
**empty data**. The full head was required to get real rows: `syscode`, `auth`
(session ticket), `lang`, and a rich `extension[]`. Lesson: capture and replay the
**complete** head, not a hand-minimized one — `Ack:"Success"` + empty data is the
signature of a head that's missing a required field, not of a wrong body.

## Handoff

You now have: the wire service code (registry), the exact body schema and enum
values (builder), and the complete head (capture). Reconstruct and verify in
`signing-replay.md`; if the body still fails after a byte-correct signature, it's
the TLS layer — see the WAF / JA3 section there.
