# native-tracing (stackplz): eBPF observation of native code

Use [SeeFlowerX/stackplz](https://github.com/SeeFlowerX/stackplz) when the requested
analysis needs native call arguments/results, syscall evidence, or observations
at a known address. It provides syscall, uprobe, and hardware-breakpoint modes.
Apply `operating-scope.md` to the selected process, device, app, account, and data
before running the examples. An opaque payload or failed Frida attach alone does
not select this branch.

## Contents
- [Instrumentation effects](#instrumentation-effects)
- [Requirements and preflight](#requirements-and-preflight)
- [Three modes and when to use each](#three-modes-and-when-to-use-each)
- [Recipes](#recipes)
- [Folding events into findings.json](#folding-events-into-findingsjson)
- [Caveats](#caveats)
- [See also](#see-also)

## Instrumentation effects

Frida hooks, Stalker/QBDI code-cache tracing, kernel uprobes, and hardware
breakpoints are distinct mechanisms. Uprobes can install software breakpoints;
hardware breakpoints use debug facilities. Neither guarantees unchanged timing
or immunity to detection. See `dbi-detection.md` and the
[Linux uprobe documentation](https://docs.kernel.org/trace/uprobetracer.html).

Choose a method for its evidence coverage, platform support, and measured
process effects. Frida remains useful for scriptable Java/JNI observations;
stackplz remains useful for the native and syscall modes below. Record an
uninstrumented baseline where the effect of tracing matters to the conclusion.

## Requirements and preflight

- **Root**, **aarch64**, kernel **≥ 5.10** (4.14 works if
  `CONFIG_HAVE_HW_BREAKPOINT=y`). Check: `adb shell uname -r`.
- Check stackplz's own kernel/build prerequisites as well as the BTF/BPF caveats
  in `ecapture-capture.md`. A successful ecapture run does not prove that every
  stackplz mode is supported.
- Grab the aarch64 build from
  [releases](https://github.com/SeeFlowerX/stackplz/releases); `scripts/stackplz_run.sh`
  pushes/chmods it, verifies root, and streams the chosen mode.

## Three modes and when to use each

| Mode | What it does | Reach for it when |
|-|-|-|
| **syscall** | Trace syscalls by name or `%group` (`%net`,`%file`), with args, stack, hexdump | **P3 align** — correlate captured request bytes to the code that made the `sendto`/`connect`, no proxy. Or find *what* a signer reads (`openat` of a keystore, `getrandom` for a nonce). |
| **uprobe** | Hook an exported symbol or `lib+offset`, dump typed args + backtrace at entry/exit | **P4** — read the plaintext going *into* a JNI signer and the signature coming *out*, when you know the symbol but static reading is slow. |
| **brk** | Hardware breakpoint at a **lib-relative offset** (the crypto sink from P1/P4); dump registers + memory | **P4, known address** — observe the selected buffers/registers at call time within established scope; record breakpoint effects and coverage. |

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

**Hardware breakpoint at a selected native address (Gate B):**

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
# Record the in-scope pre-encryption buffer observed at the selected uprobe:
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
- `dbi-detection.md` — detection mechanisms and limits when interpreting a trace.
- `ecapture-capture.md` — the TLS half of the eBPF-first workflow; same
  root/kernel preflight.
- `crypto-id.md` / `signing-replay.md` — turn the captured buffers into a named
  primitive and a verified replay.
- `native-emulation.md` — when you'd rather run the function offline (unidbg) or
  need per-instruction flow (QTrace) instead of function-boundary tracing.
