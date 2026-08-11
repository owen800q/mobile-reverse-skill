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

Run the crawler through the same container runtime:

```bash
docker run --rm \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  -v "$PWD:/repo" \
  cloakbrowser-crawler:150 \
  crawl tools/kanxue-crawler/update.sh --headless --no-push
```
