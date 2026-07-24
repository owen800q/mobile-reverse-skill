# ecapture-capture (P2): TLS plaintext without a proxy

Phase P2 of the reverse workflow. Goal: obtain **ground-truth** network traffic
of the target app — the real login endpoint, exact headers/body, and the
concrete value of any client-computed signature header — using
[gojue/ecapture](https://github.com/gojue/ecapture) (eBPF). This known
input/output pair is the correctness oracle for P4 (crypto-id) and P5
(signing-replay).

Prereqs: you have the package name and native target notes from P1
(`android-triage.md`). Outputs of this phase: `re_out/ecapture_text.log` (or
`.pcapng`), plus `requests.json` from `scripts/ecapture_parse.py` — whose records each carry a
`sig_candidates` field (a field inside each record, not a separate artifact) — folded into `findings.json`.

## Contents
- [Why ecapture is the default](#why-ecapture-is-the-default)
- [Requirements and preflight](#requirements-and-preflight)
- [Subcommands](#subcommands)
- [Output modes for `tls`](#output-modes-for-tls)
- [Filtering to one app](#filtering-to-one-app)
- [Android deployment](#android-deployment)
- [ecaptureQ (GUI)](#ecaptureq-gui)
- [Recognizing app-layer encryption (the pivot signal)](#recognizing-app-layer-encryption-the-pivot-signal)
- [Mapping fields into findings.json](#mapping-fields-into-findingsjson)
- [Troubleshooting](#troubleshooting)
- [See also](#see-also)

## Why ecapture is the default

ecapture attaches eBPF **uprobes** directly to TLS library functions
(`SSL_read`/`SSL_write` in OpenSSL/BoringSSL; also GnuTLS, NSS, and Go's
`crypto/tls` via `gotls`). It reads the buffer **after decryption / before
encryption**, i.e. the plaintext the app itself handles. Consequences that make
it beat every alternative:

- **No CA cert, no proxy, no MITM.** You never terminate TLS. Nothing in the
  trust store changes, so cert-pinning is irrelevant — there is no pin to fail.
- **No SSL-pinning bypass needed.** Burp/mitmproxy require you to defeat pinning
  (Frida script, patched APK, network-security-config). ecapture sidesteps the
  entire arms race.
- **Minimal detection surface.** A Frida `SSL_read` hook lives in the app's own
  address space (inline hooks, `libfrida` maps, ptrace) and is trivially
  detectable; a proxy is visible via `getDefaultProxy`, cert-store diffing, and
  connectivity checks. ecapture runs kernel-side out-of-process — the app sees a
  normal, unmodified TLS session. Anti-tamper apps that trip on Frida or a proxy
  usually sail straight through.

Cost: it needs **root** and a modern kernel (below). When those hold, prefer it
over Burp+pinning-bypass and over the Frida `ssl_keylog.js` hook. Fall back to
Frida only when the kernel/BTF is unsupported or the lib is statically linked
and unhookable by uprobe.

## Requirements and preflight

- **Root.** eBPF program loading requires it. Verify: `adb shell su -c id`
  must report `uid=0`.
- **Kernel:** x86_64 ≥ **4.18**, aarch64 (arm64) ≥ **5.5**. Most current arm64
  phones qualify; check `adb shell uname -r`.
- **BTF + BPF support.** Some vendor kernels ship without CO-RE BTF or the
  needed BPF configs and ecapture will refuse to load. Check:

```sh
adb shell su -c 'ls -l /sys/kernel/btf/vmlinux'          # must exist
adb shell su -c 'zcat /proc/config.gz | grep -iE "BPF|BTF"'
```

Want `CONFIG_BPF=y`, `CONFIG_BPF_SYSCALL=y`, `CONFIG_DEBUG_INFO_BTF=y`,
`CONFIG_UPROBES=y`. Missing `DEBUG_INFO_BTF` (no `/sys/kernel/btf/vmlinux`) is
the usual blocker → fall back to Frida (`assets/frida/ssl_keylog.js`).

## Subcommands

- **`tls`** — OpenSSL/BoringSSL/GnuTLS/NSS. The one you use for Android apps.
- **`gotls`** — apps built in Go (some Flutter/gRPC backends, Go CLI tools).
  Needs the on-device binary path: `ecapture gotls --elfpath=/path/to/bin`.
- `bash` / `zsh` / `mysqld` / `postgres` — host/server audit (shell input, DB
  queries). Not app RE; ignore for this phase.

## Output modes for `tls`

Selected with `-m`. Pick by what you need downstream:

- **`-m text`** — plaintext events to stdout/file. Add `--hex` for a lossless
  hexdump (safe for binary bodies). **Use for quick reading** and when you just
  need to eyeball the login request. This is `ecapture_run.sh --mode text`, the
  default, and what `ecapture_parse.py` parses best.

  ```sh
  ecapture tls -m text --hex
  ```

- **`-m pcap` / `-m pcapng`** — writes a capture file (with the plaintext) plus
  a BPF-style filter expression. **Use for full bidirectional flows / many
  requests**, or when a lib is statically linked and text hooks miss it. Open in
  Wireshark.

  ```sh
  ecapture tls -m pcap --pcapfile=/data/local/tmp/ecapture.pcapng tcp port 443
  ```

- **`-m keylog`** (alias `-m key`) — dumps TLS master secrets (SSLKEYLOGFILE
  format), **not** the plaintext. **Use with a separate `tcpdump`/pcap** you
  captured in parallel: load both in Wireshark (Preferences → TLS →
  (Pre)-Master-Secret log filename) to decrypt. Choose this when you want a
  standard tcpdump + Wireshark pipeline or need genuine encrypted-on-wire bytes.

  ```sh
  ecapture tls -m keylog --keylogfile=/data/local/tmp/key.log
  ```

Rule of thumb: **text** to read a login fast, **pcap** for full flows / stubborn
libs, **keylog** when you already run tcpdump.

## Filtering to one app

Unfiltered `tls` captures every process's TLS — huge noise. Filter by the target
app:

```sh
adb shell dumpsys package <pkg> | grep -m1 userId=   # -> userId=101234
ecapture tls -m text --hex --uid 101234              # only that app
```

`--uid` (app UID) or `--pid` both work. `ecapture_run.sh --pkg <pkg>` resolves
the UID automatically. UID survives app restarts; PID does not.

## Android deployment

Manual:

```sh
# 1. Grab the android/aarch64 release asset (arm64-v8a) from GitHub releases,
#    or build from source. Confirm ABI: adb shell getprop ro.product.cpu.abi
adb push ecapture /data/local/tmp/ecapture
adb shell su -c 'chmod 755 /data/local/tmp/ecapture'
adb shell su -c '/data/local/tmp/ecapture tls -m text --hex --uid <uid>'
# Now perform the LOGIN in the app. Ctrl-C to stop.
```

Automated — prefer the scripts:

- **`scripts/ecapture_run.sh`** — checks a single adb device, detects ABI,
  pushes/chmods the binary (or reuses one on device), verifies root, resolves
  `--pkg`→uid, streams the chosen mode, and on stop pulls artifacts into
  `--out`. Flags: `--serial --out --pkg --bin --mode text|pcap|keylog
  --duration`.
- **`scripts/ecapture_parse.py`** — reassembles the text log (or reads the
  pcapng via scapy/pyshark) into HTTP request objects, writes
  `<out>/requests.json`, and flags auth/signature material as `sig_candidates`
  (authorization, x-sign/signature, token, nonce, timestamp/ts …). Login-looking
  requests print to stderr.

```sh
scripts/ecapture_run.sh --pkg com.target.app --mode text --out re_out
scripts/ecapture_parse.py re_out/ecapture_text.log --out re_out
```

## ecaptureQ (GUI)

Tauri front-end for teams/triage:

- **Integrated Mode (Android):** bundles ecapture, needs **root** on the device.
  Press **Start**; capture runs locally with no adb dance.
- **Remote Mode:** on the device/server run
  `ecapture tls --ecaptureq ws://0.0.0.0:28257`, then connect the desktop
  ecaptureQ client to that WebSocket. The client itself needs **no root** — good
  for a rooted phone + unprivileged laptop.
- Supports **SQL-style packet filtering**, e.g.
  `dst_port = 443 AND pname = 'chrome'` — a convenient live filter equivalent to
  the CLI `--uid`/`--pid`.

## Recognizing app-layer encryption (the pivot signal)

ecapture shows **only what crosses TLS**. If the app encrypts the request body
at the **application layer before** handing it to TLS, ecapture prints that
ciphertext — the plaintext body is itself an opaque blob. Recognize it:

- Body is **base64 or hex**, or raw bytes, **not JSON/form data**
  (`{"data":"3Qk9...=="}` or a single `encrypted=...` field).
- Response bodies are likewise unreadable blobs.
- Headers may include a bare `Content-Type: application/octet-stream` or a
  custom type.

That is the signal that **crypto sits above TLS**. ecapture has done its job
(it proved where the boundary is); pivot to static/native analysis and hook the
crypto primitives to see pre-encryption data:

- Identify the cipher/keys in P4 → `crypto-id.md`.
- Java-layer: `assets/frida/hook_crypto.js` (Cipher init/doFinal, mode, key,
  IV, plaintext ↔ ciphertext).
- If crypto is native (JNI), use the P1 native target + JNI tracing.

Conversely, if ecapture already shows clean JSON with a signed header, there is
no app-layer crypto to break — go straight to reconstructing the signature.

## Mapping fields into findings.json

For each captured request, classify every header and body field so P4/P5 know
what to reconstruct. Suggested `protocol_map` roles:

- **auth_field** — `Authorization`, session/access/refresh tokens, cookies.
- **signature_field** — `X-Sign`, `sign`, `signature`, HMAC-looking hex/base64;
  the header whose value changes with the request. Mark **computed
  client-side** → primary reversing candidate.
- **timestamp** — `ts`, `timestamp`, `X-Timestamp` (usually a signature input).
- **nonce** — `nonce`, `random`, `X-Nonce`, request-id (signature input).
- **normal param** — plain business fields (username, device model, appVersion).

Record, per signature candidate, the **exact known input** (method, path,
sorted params, body, timestamp, nonce) and its **known output** (the header
value). That concrete pair is the oracle. `ecapture_parse.py` seeds this via
`sig_candidates`; promote the confirmed ones into `findings.json`.

## Troubleshooting

- **No output / capture is empty.** Wrong TLS lib hooked, or **statically-linked
  BoringSSL** (common in Flutter/React-Native/Go) where symbols aren't exported
  for uprobe. Try **`-m pcap`** (different hook path), try `gotls` for Go, and
  confirm you filtered the right `--uid`. Verify traffic actually happened.
- **eBPF/BTF load error, or capture dies immediately.** Kernel too old or no
  BTF (see preflight). No fix on-device → fall back to Frida
  `assets/frida/ssl_keylog.js` + a proxy/pcap.
- **Only some requests appear; login endpoint missing.** App may use **QUIC /
  HTTP3 (UDP 443)**. ecapture's TLS uprobes target the TLS-over-TCP libs; HTTP3
  support is limited/absent. Force HTTP/2 by blocking UDP 443
  (`iptables`/AdGuard) so the app downgrades to TCP TLS, then re-capture.
- **Root check fails.** `su -c id` ≠ `uid=0` → no eBPF. Nothing works until the
  device is rooted.
- **Binary won't run (`not executable` / wrong ABI).** Mismatched build; match
  `getprop ro.product.cpu.abi` (arm64-v8a → android/aarch64).

## See also

- `android-triage.md` — P1: package/UID, native target, unpacking (feeds this
  phase).
- `crypto-id.md` — P4: identify cipher/keys once you see an app-layer blob.
- `signing-replay.md` — P5: use the captured known input/output pair to rebuild
  and replay the signature.
