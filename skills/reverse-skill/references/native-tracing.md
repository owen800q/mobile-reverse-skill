# native-tracing (stackplz): stealthy eBPF tracing of native code

On-demand reference for the **eBPF dynamic branch of Gate B**. When you need to
watch native code *run* — a JNI signer, a syscall carrying request bytes, the
inputs/outputs of a crypto sink — but you want to stay off the radar of an app
that hardens against instrumentation, use
[SeeFlowerX/stackplz](https://github.com/SeeFlowerX/stackplz) (eBPF) instead of
Frida.

ecapture (P2, `ecapture-capture.md`) already proves the eBPF-first thesis for
TLS. stackplz is the other half of it: the **same kernel-side, out-of-process
uprobe/perf technology, applied to arbitrary userspace functions, syscalls, and
hardware breakpoints.** Load this file when P4 triage (`ida-workflow.md` Gate B)
tells you static reading won't pay off, or when a signer is anti-debug/anti-DBI
hardened and Frida would be seen (`dbi-detection.md`).

## Contents
- [Why eBPF tracing beats a Frida hook here](#why-ebpf-tracing-beats-a-frida-hook-here)
- [Requirements and preflight](#requirements-and-preflight)
- [Three modes and when to use each](#three-modes-and-when-to-use-each)
- [Recipes](#recipes)
- [Folding events into findings.json](#folding-events-into-findingsjson)
- [Caveats](#caveats)
- [See also](#see-also)

## Why eBPF tracing beats a Frida hook here

Frida's `jni_trace.js` / `hook_crypto.js` do the same *job* — observe a native
call's arguments and results — but they do it by injecting an agent into the
app's address space (inline hooks, `libfrida-agent` maps, ptrace, a Gum code
cache). Every one of those is detectable, and Frida's Stalker/Interceptor
relocates code into a translated cache, which is exactly what the checks in
`dbi-detection.md` measure.

stackplz sets a kernel uprobe or a **hardware** breakpoint (a CPU debug
register / perf event). The target instruction is **not** rewritten or
relocated; the app's code executes in place and byte-for-byte unchanged. The
PC the app sees always matches the on-disk address, so the code-cache /
PC-divergence detections come up clean. It is not literally zero-detection
(HW debug registers are theoretically observable), but it is dramatically
quieter than any in-process DBI. Reach for stackplz first; fall back to Frida
only when the kernel is too old for eBPF or you need scripting stackplz can't do.

## Requirements and preflight

- **Root**, **aarch64**, kernel **≥ 5.10** (4.14 works if
  `CONFIG_HAVE_HW_BREAKPOINT=y`). Check: `adb shell uname -r`.
- Same BTF/BPF caveats as ecapture — see `ecapture-capture.md` "Requirements and
  preflight". If ecapture ran, stackplz will too.
- Grab the aarch64 build from
  [releases](https://github.com/SeeFlowerX/stackplz/releases); `scripts/stackplz_run.sh`
  pushes/chmods it, verifies root, and streams the chosen mode.

## Three modes and when to use each

| Mode | What it does | Reach for it when |
|-|-|-|
| **syscall** | Trace syscalls by name or `%group` (`%net`,`%file`), with args, stack, hexdump | **P3 align** — correlate captured request bytes to the code that made the `sendto`/`connect`, no proxy. Or find *what* a signer reads (`openat` of a keystore, `getrandom` for a nonce). |
| **uprobe** | Hook an exported symbol or `lib+offset`, dump typed args + backtrace at entry/exit | **P4** — read the plaintext going *into* a JNI signer and the signature coming *out*, when you know the symbol but static reading is slow. |
| **brk** | Hardware breakpoint at a **lib-relative offset** (the crypto sink from P1/P4); dump registers + memory | **Gate B, hardened target** — the signer is OLLVM-flattened and/or anti-DBI. Break at the sink address, read the buffers at call time. No IDA grind, no Frida footprint. |

Decision heuristic within Gate B's dynamic branch: **known symbol → uprobe;
known address inside an obfuscated function → brk; don't know where the data
enters/leaves → syscall trace to bracket it first.**

## Recipes

All via `scripts/stackplz_run.sh` (see `--help`); it wraps the flags below and
pulls a JSON artifact you parse with `scripts/stackplz_parse.py`.

**Bracket the request with a syscall trace (P3):**

```sh
scripts/stackplz_run.sh --pkg com.target.app --mode syscall \
  --syscalls connect,sendto,recvfrom --out re_out
# raw equivalent: stackplz -n com.target.app --syscall connect,sendto,recvfrom --stack --dumphex --json
```

The hexdump of `sendto` is the on-wire bytes; the `--stack` backtrace names the
`.so` frames that built them — that is your bridge from captured traffic to code.

**Read a JNI signer's I/O by symbol (P4):**

```sh
scripts/stackplz_run.sh --pkg com.target.app --mode uprobe \
  --lib libsec.so --point 'Java_com_target_Sign_getSign[str,int]' --out re_out
```

`--point 'sym[argspec]'` types the args (`str`,`int`,`ptr`,`buf:64`,`buf:x2` =
buffer sized by register x2). Entry shows the plaintext; add an exit read for the
returned signature.

**Hardware breakpoint on an obfuscated sink (Gate B, hardened):**

```sh
# 0xf3a4 is the sink offset you found in IDA (P1/P4). App must be running.
scripts/stackplz_run.sh --pkg com.target.app --mode brk \
  --lib libsec.so --brk 0xf3a4 --brk-type x --out re_out
```

Registers + memory at the breakpoint give the exact input/output buffers — feed
those to `constscan.py`/`cryptoinstr.py` (`crypto-id.md`) to fingerprint the
primitive, and to `sign_rebuilder.py` (`signing-replay.md`) as a known I/O pair.

**Parse whatever fired:**

```sh
scripts/stackplz_parse.py re_out/stackplz_events.json --out re_out
```

It normalizes events, decodes hexdumps to readable text, flags crypto/auth-
looking buffers and backtrace frames, and prints `findings.py` hints.

## Folding events into findings.json

stackplz output is *evidence that code ran*, so it earns rungs above `PATTERN`
(P1 static matches were `PATTERN`; a trace that shows the call actually
happened is `REACHABLE`, and buffers you can vary are `CONTROLLABLE`). Promote
with a **verbatim** quote — the decoded buffer line or a backtrace frame — so
`findings.py validate` R1 is satisfied:

```sh
S=./re_out
# The signer really executes on the login path (not just a static string match):
findings.py --out $S add-fact --phase 4 --rung REACHABLE \
  --claim "libsec.so getSign runs during login" --tool stackplz \
  --ref "stackplz_events.json" --verbatim "#00 libsec.so!Java_com_target_Sign_getSign"
# Pre-encryption plaintext seen at the uprobe defeats a Gate A opaque blob:
findings.py --out $S add-fact --phase 3 --rung CONTROLLABLE \
  --claim "plaintext body before app-layer AES" --tool stackplz \
  --ref "stackplz_events.json" --verbatim 'user=alice&ts=1699…'
```

A stackplz trace does **not** by itself name a crypto primitive — that still
needs a `constscan`/`cryptoinstr` fingerprint (R2). Use the captured buffers as
the *inputs* to that identification and to the P5 replay, where recomputing the
captured signature earns the `VERIFIED` rung.

## Caveats

- **brk uses lib-relative offsets only.** `stackplz_run.sh` always passes
  `--brk-lib`; never hand it a raw absolute address — stackplz warns that a
  kernel-address hardware breakpoint can reboot the device.
- **Syscall returns are errno**, not libc-style return values — read args and
  buffers, not the raw return, for semantics.
- **Symbol aliasing:** libc has multiple implementations (`strchr` vs
  `__strchr_aarch64`); if a `--point` by name misses, use the concrete offset.
- **Dropped samples** ("perf ring buffer full") on chatty targets → raise the
  buffer with `--buffer 32`.
- **Maintenance/version drift:** flags and JSON schema move between stackplz
  releases; `stackplz_parse.py` is deliberately tolerant, but if it can't find
  events, read the raw `stackplz_stdout.log` and adjust.

## See also

- `ida-workflow.md` — Gate B (static-vs-dynamic) and finding the sink address to
  break on.
- `dbi-detection.md` — *why* you pivoted to eBPF: how apps detect the Frida/QBDI
  alternative, and why stackplz stays invisible to those checks.
- `ecapture-capture.md` — the TLS half of the eBPF-first workflow; same
  root/kernel preflight.
- `crypto-id.md` / `signing-replay.md` — turn the captured buffers into a named
  primitive and a verified replay.
- `native-emulation.md` — when you'd rather run the function offline (unidbg) or
  need per-instruction flow (QTrace) instead of function-boundary tracing.
