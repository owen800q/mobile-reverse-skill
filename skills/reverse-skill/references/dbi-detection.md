# dbi-detection: why eBPF-first, and when Frida/QBDI are already burned

This is the **doctrine** behind the skill's eBPF-first stance, made concrete.
It's not a phase — it's a **pre-dynamic triage** you run before Gate A/B choose a
dynamic tool. The question it answers: *before I inject Frida (or QBDI/QTrace),
will the app notice?* If the target ships the checks below, the answer is yes,
and the honest move is to go invisible with eBPF (`native-tracing.md` /
`ecapture-capture.md`) rather than start a losing bypass arms race.

Grounded in [SoyBeanMilkx/dbi_detect](https://github.com/SoyBeanMilkx/dbi_detect),
a minimal ARM64 demonstration of how native code detects that it's being traced
by a **DBI** (dynamic binary instrumentation) engine.

## Contents
- [The core idea: DBI relocates code, so the PC diverges](#the-core-idea-dbi-relocates-code-so-the-pc-diverges)
- [The two techniques](#the-two-techniques)
- [Spotting these checks in a target](#spotting-these-checks-in-a-target)
- [Decision: what a hit means for tool choice](#decision-what-a-hit-means-for-tool-choice)
- [What this means for bypass.js](#what-this-means-for-bypassjs)
- [Self-test: is my own DBI visible here?](#self-test-is-my-own-dbi-visible-here)
- [Caveats](#caveats)
- [See also](#see-also)

## The core idea: DBI relocates code, so the PC diverges

Frida's Stalker and QBDI (which QTrace is built on) work by **translating the
target's instructions into a code cache** and executing the copy. That copy
lives at a different address than the original. So at the moment a traced
instruction runs, the **Program Counter points into the code cache, not at the
original on-disk address.** Every detection here is a way to observe that one
fact: *is the code executing where it's supposed to, or from a relocated copy?*

eBPF uprobes and hardware breakpoints (stackplz, ecapture) do **not** relocate
code — the app's own instructions run in place, unchanged, at their real
addresses. So the PC always matches, and these checks pass clean. That is the
mechanical reason the skill prefers eBPF against hardened targets.

## The two techniques

**1. Asynchronous signal PC sampling (passive).** A watchdog thread periodically
sends a signal to the protected thread; the signal handler reads
`ucontext->uc_mcontext.pc` (the interrupted thread's PC) and compares it to the
expected address range of the protected function. Under Frida Stalker/QBDI the
sampled PC lands in the code cache → mismatch → traced. The protected code never
cooperates; it's caught by an outside observer.

**2. Self-triggered `BRK` exception (active).** The function executes a `BRK #imm`
(software breakpoint) and installs a `SIGTRAP`/`SIGILL` handler. The handler
reads the PC from the exception context and compares it to the address of the
`BRK` instruction it just ran. In-place execution → PCs match; DBI-relocated
execution → the exception fires from the code cache → mismatch → traced.

Both are **code-integrity / PC-divergence** checks. Note what they are *not*:
classic anti-Frida indicators (a scan for the `frida-server` port 27042, a
`/proc/self/maps` search for `frida-agent`, thread-name checks, D-Bus probes).
Those are noisy and easy to bypass; PC-divergence is intrinsic to how DBI works
and effectively unbypassable *from inside the very engine it detects*.

## Spotting these checks in a target

During P4 (or before any dynamic step), scan the selected `.so` for the
signatures. From the IDA export (`ida-workflow.md` Path B) or `rabin2`/`grep`:

- **Signal-based:** imports/xrefs to `sigaction`/`sigaltstack`, a handler that
  dereferences `ucontext`/`uc_mcontext` and reads offset for `pc` (on arm64,
  `pc` sits after the 31 GP regs in `sigcontext`), plus a thread that loops
  sending `pthread_kill`/`tgkill`/`raise`.
- **BRK-based:** a literal `BRK #imm` (`brk` mnemonic; encoding `0xD42?????`) in
  application code — not compiler-inserted `brk #0x3e8` bounds checks — paired
  with a `SIGTRAP`/`SIGILL` `sigaction` handler that reads the fault PC.
- **General:** handler code that computes `expected_addr - actual_pc` or compares
  a PC against `dladdr`/module-base arithmetic.

```sh
# quick triage from an IDA headless export
grep -iE 'sigaction|uc_mcontext|ucontext|sigcontext' imports.txt strings.txt
grep -rliE '\bbrk\b|SIGTRAP|SIGILL' decompile/    # then read the matching function
```

If you find them, log a **fact** (rung `PATTERN`, verbatim the decompiled line)
and, if you later confirm the check runs, an **intent** that says "DBI detection
present → dynamic analysis must use eBPF."

## Decision: what a hit means for tool choice

| Triage result | Frida (Stalker/Interceptor) | QTrace / QBDI | stackplz / ecapture (eBPF) |
|-|-|-|-|
| No DBI-detection found | fine (gap-filler) | fine (instruction trace) | still preferred for stealth |
| Signal or BRK PC check present | **burned** — will be detected | **burned** — QBDI is exactly the target | **use these** — invisible to code-cache checks |

So the heuristic folded back into the gates: **DBI-detection present → skip
Frida/QTrace, go straight to `native-tracing.md` (stackplz uprobe/brk) and
`ecapture-capture.md`.** This is *why* Gate B's dynamic branch defaults to eBPF
and treats Frida as the fallback, not the first move.

## What this means for bypass.js

`assets/frida/bypass.js` covers root / emulator / proxy / SSL-pinning /
`Debug.isDebuggerConnected` — Java-layer *policy* checks it can neutralize by
overriding return values. It deliberately does **not** try to defeat the two
checks here, and shouldn't:

- They observe a low-level, physical fact (where the PC is), not a Java API you
  can stub. "Fixing" them means forging `ucontext.pc`/the exception frame from
  inside the same Frida engine being detected, or hijacking the signal/BRK
  handler — brittle, target-specific, and itself detectable.
- The right response to detecting them is **not another hook** — it's to change
  tools. Finding a PC-divergence check is the trigger to pivot to eBPF, where the
  check is a no-op because nothing was relocated.

Treat this file as the scope boundary for bypass.js: it handles environment
policy; it does not fight code-integrity DBI detection, and that's by design.

## Anti-ptrace / attach-killing: Frida as a call-only oracle

Separate from the PC-divergence checks above, a hardened target often also carries
**native anti-ptrace** that kills any Frida **ATTACH** instantly, and kills heavy
hooking even under **SPAWN**. Field-tested behavior on such an app (Ctrip):

- **ATTACH → dead on arrival.** Don't attach to a running hardened process.
- **SPAWN + minimal, call-only agent → survives.** Block `exit`/`_exit`/`kill`
  via `Interceptor.replace`, then call **one** native method as an oracle. That's it.
- **Heavy hooking → killed.** Multiple `.implementation` overrides, or hooking a
  **hot** method (e.g. `getMD5`), trips the defense and the app kills the Frida
  connection.
- **Restart frida-server fresh before EACH spawn** of a hardened app
  (`pkill -9 frida-server` then relaunch) — a reused server carries poisoned state.

Doctrine: on hardened targets, treat Frida as a **narrow "call this one native
function" oracle**, not an instrumentation platform. For anything broader, prefer
eBPF (stackplz, `native-tracing.md`), **unidbg** off-device
(`native-emulation.md`), or **heap-scan** (`heap-scan-capture.md`) — all of which
sidestep the attach/hook defenses entirely.

## Self-test: is my own DBI visible here?

If you must use Frida or QTrace on a target you *think* is clean, you can borrow
dbi_detect's `DBI_TRACE_DETECTED()` macro as a probe: compile it into a tiny
native sample (or the target's own harness) and run it under your Frida/QTrace
session. A non-zero result means your instrumentation is observable in this
process — pivot to stackplz before you trust anything you hooked. This turns the
project from an adversary's tool into a red-team check on your own approach.

## Caveats

- dbi_detect implements **two** techniques, not a complete anti-DBI suite — a
  real target may add maps/port/string scans and timing checks on top. Absence
  of these two is not proof the app is DBI-blind.
- **ARM64 only**, and the repo is sample/education-grade — the *value is the
  knowledge* (how the detection works, what to grep for), not the binary.
- eBPF is quieter, not magic: hardware debug registers and uprobe-induced timing
  are theoretically observable. Against an extremely hardened target, prefer
  passive syscall tracing and full-request `ecapture` capture over an active HW
  breakpoint.

## See also

- `native-tracing.md` — the eBPF answer (stackplz) you pivot to when these checks
  are present.
- `ecapture-capture.md` — the same argument for TLS ("Why ecapture is the
  default"): out-of-process eBPF vs a detectable in-process hook.
- `native-emulation.md` — QTrace/QBDI section: powerful instruction trace, but
  it is precisely what these checks catch, so gate it on a clean triage.
- `ida-workflow.md` — where you read the `.so` to find (and confirm) these
  checks.
