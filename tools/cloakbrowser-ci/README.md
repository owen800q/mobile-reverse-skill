# CloakBrowser crawler runtime

This directory contains the reproducible, container-only runtime used by
`.github/workflows/kb-crawl.yml`. It downloads and verifies the exact
CloakBrowser `150.0.7871.114.6` Linux x64 release, applies a hash- and
byte-guarded in-memory patch, and exposes that launch path to Playwright.

The archive, extracted browser, profiles, session files, and logs stay under
ignored runtime paths. The license key is read from the environment only and is
never written into the image or repository.

Pinned release identity:

- Archive SHA-256: `6c79c5b0794368ce2f0fb8b3993e42113be3921840aef206b823c9a4e9b1c51e`
- ELF SHA-256: `80fc8186a8a80198ca845349c4f463e5689f2448c8840eb6c8e62bead04b33b0`
- ELF Build ID: `54a5ac40ae5f57e867b107f9d5af745e33dc034c`

The workflow requires these repository secrets:

- `CLOAKBROWSER_LICENSE_KEY`: download key for the pinned release.
- `KANXUE_SESSION_STATE`: Playwright storage-state JSON for the crawler login.

Build and fetch inside Docker:

```bash
docker build -f tools/cloakbrowser-ci/Dockerfile -t cloakbrowser-crawler:150 .
docker run --rm \
  -e CLOAKBROWSER_LICENSE_KEY \
  -v "$PWD:/repo" \
  cloakbrowser-crawler:150 fetch
```

Verify the no-key baseline and three concurrent patched instances:

```bash
docker run --rm \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  -v "$PWD:/repo" \
  cloakbrowser-crawler:150 verify-target
```

The successful smoke-test summary is:

```text
baseline_rc=77 patched_concurrent_ready=3
```

## Verifying it is cloaked, not merely alive

`verify-target` proves the patched binary boots and exposes DevTools. It says
nothing about whether the fingerprint spoofing survived the patch — and since the
patch neuters `LicenseRuntime::Start/End`, a build that gates its cloaking on that
entry point would still pass `verify-target` while behaving like plain headless
Chromium. `verify_stealth.py` is the other half:

```bash
docker run --rm \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v "$PWD:/repo" \
  cloakbrowser-crawler:150 verify-stealth
```

Two passes. The **fingerprint probes** are offline and deterministic, so they gate
CI: `navigator.webdriver`, a `HeadlessChrome` UA, chromedriver `cdc_` globals, empty
plugin/language lists, and — the pair the old crawler launch options were failing —
agreement between the UA string, `navigator.userAgentData` and `navigator.platform`.
A software WebGL rasteriser is a warning only, since a GPU-less runner legitimately
has one.

The **Turnstile pass** drives a live widget and is advisory unless you pass
`--require-turnstile`. Note what the default URL actually tests: 2captcha's demo
embeds sitekey `3x00000000000000000000FF`, Cloudflare's documented *"always force an
interactive challenge"* test key. Clearing it shows the browser can complete a forced
interactive challenge, and the token it returns is a test token with no server-side
validity — it is a behavioural smoke test, not a measure of how a production
Turnstile deployment would score this browser.

Useful flags: `--no-turnstile` (offline probes only), `--headed`, `--screenshot-dir`,
`--json`, and `--user-agent` to reproduce the UA/Client-Hints desync described in
`../kanxue-crawler/README.md`. Behind a TLS-intercepting proxy add
`--browser-arg=--no-proxy-server --browser-arg=--ignore-certificate-errors`, and
discount the Turnstile result: the proxy re-originates TLS, so Cloudflare fingerprints
the proxy rather than this browser.

### Measured

Patched CloakBrowser 150 against stock headless Chromium 141 (the fallback the
crawler used to take silently), same host, same page:

| probe | stock Chromium 141 | patched CloakBrowser 150 |
|-|-|-|
| `navigator.webdriver` | `true` | `false` |
| user agent | `HeadlessChrome/141.0.0.0` | `Chrome/150.0.0.0` |
| WebGL renderer | `SwiftShader` (software) | `NVIDIA GeForce RTX 3080` |
| `deviceMemory` | 8 | 16 |
| UA ↔ Client Hints ↔ `navigator.platform` | consistent | consistent |
| **fingerprint checks** | **7/10, 1 warning** | **11/11** |

The spoofed NVIDIA renderer on a GPU-less container is the direct evidence that
the fingerprint engine is still live after `LicenseRuntime::Start/End -> ret` —
which is precisely what `verify-target` alone could not tell us.

Ten concurrent instances, each with its own profile, all passed 11/11, and the
spoofing is per-profile rather than per-build: nine distinct GPUs across the ten
(RTX 3080, 3070 Ti ×2, 2070, 4060 Ti, 4080 SUPER, 4090, 4070 Ti, GTX 1650, GTX
1060). `hardwareConcurrency` is not randomised — it tracked the host's real core
count on every instance.

Neither browser obtained a Turnstile token (0/10 concurrent, 0/1 single; Cloudflare
never rendered a visible widget for either). **That result is not evidence about
CloakBrowser.** It was measured behind a TLS-intercepting egress proxy —

```console
$ openssl s_client -connect challenges.cloudflare.com:443 </dev/null | grep issuer
issuer=O = Anthropic, CN = Egress Gateway SDS Issuing CA (production)
```

— so Cloudflare was fingerprinting the gateway's TLS and datacenter IP, not this
browser. Turnstile weighs both heavily, and no amount of in-page spoofing reaches
them. Re-run the Turnstile leg from an un-intercepted network before drawing any
conclusion from it; the fingerprint probes need no network and are unaffected.

Run the crawler through the same container runtime:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  -v "$PWD:/repo" \
  cloakbrowser-crawler:150 \
  crawl tools/kanxue-crawler/update.sh --headless --no-push
```
