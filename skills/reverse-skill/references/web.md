# web.md — web apps, sites, and their JavaScript (W0–W6)

Load this when the target is a URL, a saved page, a HAR export, a JavaScript or
WebAssembly file, a source map, or an Electron renderer already extracted by
`desktop.md` D1. React Native bundles inside a mobile app also need
`hermes-react-native.md`.

Scope comes first: [operating-scope.md](operating-scope.md#web-targets). Passive
analysis of pages and scripts is the default. A live request needs an agreed
endpoint, account, purpose, and attempt limit.

## Phases

| Phase | Goal | Tools |
|-|-|-|
| W0 Snapshot | Save what the page loads: HTML, script and style URLs, inline scripts, source-map references, WASM modules, service workers. Hash each file. | Browser DevTools on the user's machine; `scripts/target_identify.py` on each file |
| W1 Unpack | Recover readable source. Source maps first; an unminifier only as a readability aid | `scripts/js_sourcemap_extract.py`; optional Wakaru (caller-installed, pinned, its SHA-256 recorded with `findings.py add-tool`) |
| W2 Request map | Find where requests are built: `fetch`, `XMLHttpRequest`, client libraries, WebSocket, GraphQL, signed query strings | `rg` over the recovered sources; `scripts/constscan.py` for constant tables in JavaScript text |
| W3 Capture | Ground-truth real requests from the user's own session | Browser HAR export ("Save all as HAR with content"), then `scripts/har_parse.py`; mitmproxy with the user's own CA for traffic outside the browser |
| W4 Align | Map each captured field to its builder; find the sink of any signature | Ledger facts with `--ref file:line` and a verbatim quote |
| W5 Crypto | Name primitives by fingerprint: WebCrypto (`crypto.subtle`), common JavaScript crypto libraries, RSA helpers, or WASM | `constscan.py`; WASM with WABT (`wasm2wat`, and `wasm-decompile` where available); `crypto-id.md` applies unchanged |
| W6 Reconstruct | Recompute the captured signature offline from at least two samples plus one control case (R3) | `scripts/sign_rebuilder.py` on `requests.json`; `findings.py add-fact --sample ... --control ...` |

## Capture notes

- A HAR is producer-decoded. Chromium's `content.text` for a compressed body is
  decoded text, not the wire bytes. Record that in the ledger's limitations.
- A HAR holds cookies, tokens, and personal data. Keep the raw file in
  `SESSION_DIR`, and run `har_parse.py --redact` before any output leaves the session.
- `har_parse.py` never re-sends a request. Replaying one is a separate live step
  under Gate D.
- A HAR does not prove which server answered. Treat addresses in it as recorded
  values, not as verified origins.

## Source maps

- `js_sourcemap_extract.py` reads `sourceMappingURL` comments and `.map` files and
  writes `sourcesContent` under a new directory. Paths are sanitized, and nothing
  outside that directory is written.
- `js_sourcemap_lookup.py GENERATED.js MAP.json LINE COLUMN` maps one position back to
  its original source. Use it to check a claim about a specific line of the bundle.
  COLUMN counts code points. It uses the last segment at or before the position on that
  line; a one-field (generated-only) segment has no source, so a position at or after it
  gets no mapping. The original text is checked only when the map embeds `sourcesContent`
  for that source; otherwise `checks.original_text` is `not_embedded` and `consistent`
  says nothing about the original text. `checks.verdict: mismatch` means the original-side
  check failed (the text at the original position does not start with the name, or the
  position is outside the embedded source: its line is not in the embedded text, or its
  column is past the end of that line), and the position must not be cited. A generated
  name that differs is not a mismatch: minified names usually differ from the original.
  The map does not record the generated file's hash, so `consistent` does not prove that
  the map belongs to that file.
- A map shows what the build embedded. It does not prove that it matches the
  shipped file. Search the shipped bundle for a distinctive string or call site
  before citing a recovered function.
- Recovered sources are a lead, not evidence of runtime behavior.

## Minified code without a map

- Grep the shipped text first. Endpoint paths, header names, and object field
  names survive minification better than local variable names.
- Use an unminifier to read control flow, and verify each function you cite
  against the shipped text.
- Keep unminified copies in the session. Never edit the shipped file in place.

## WebAssembly

- `target_identify.py` recognizes the `\0asm` magic. Disassemble with WABT.
- Function names are usually stripped. Locate crypto from constants in data
  segments and from call structure, not from names.

## Challenges and anti-bot boundaries

- A CAPTCHA, bot-manager challenge, rate limit, or access denial ends that live
  path. Record it and stop; do not retry in a loop (Gate D).
- A CAPTCHA tool is for widgets you own or are authorized to test. Do not use one
  to pass a third-party production challenge ([operating-scope.md](operating-scope.md#web-targets)).

## Electron renderers

- Renderer code in an Electron app usually sits inside `app.asar`. Extract it with
  `desktop.md` D1, then run W1–W6 on the extracted tree.
