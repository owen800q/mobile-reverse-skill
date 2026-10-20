# dbi-detection: interpreting instrumentation effects

Use this reference to identify detection mechanisms and interpret runtime evidence.
Static triage is local analysis. A dynamic experiment uses the established
process, app, account, and data scope from `operating-scope.md`. A detected probe
is not an instruction to bypass a check or change tools until access succeeds.
Choose among the existing tools by the observations needed and their measured
side effects; no method is guaranteed invisible.

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

Do not generalize this code-cache mechanism to all instrumentation. Stalker
translation, Interceptor hooks, kernel uprobes, and hardware breakpoints have
different implementations. Uprobes can install software breakpoints and execute
a displaced instruction; hardware breakpoints use debug facilities. Neither
implies an unchanged or unobservable process. Compare behavior with an
uninstrumented baseline in the scoped test environment.

Primary references: [Frida Stalker](https://frida.re/docs/stalker/),
[Frida Interceptor](https://frida.re/docs/javascript-api/#interceptor), and
[Linux uprobe tracing](https://docs.kernel.org/trace/uprobetracer.html), and the
[uprobe implementation discussion](https://www.kernel.org/doc/ols/2007/ols2007v1-pages-215-224.pdf)
(§6.1, displaced instructions; implementations vary by architecture and version).

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
These are separate mechanisms. Confirm the actual check and its effect from
code or a scoped experiment; do not infer detectability from a marker alone.

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
and, if you later confirm the check runs, record its observed outcome and the
specific evidence still needed. The result does not mandate eBPF or a bypass.

## Decision: what a hit means for tool choice

| Triage result | Interpretation | Next analysis option |
|-|-|-|
| No matching check found | Coverage may be incomplete | Select Frida, QBDI, or eBPF by the observation needed; record limitations |
| Signal or BRK PC check found | A code-cache trace may affect behavior | Inspect the check statically; compare methods only within the established dynamic scope |
| Process exits or changes behavior | Cause is not established by the symptom alone | Preserve logs and compare with a baseline; use an isolated harness where practical |

`native-tracing.md` and `ecapture-capture.md` remain available for scoped eBPF
observations. Their kernel requirements and probe effects are part of tool
selection, not a promise that target checks will pass.

## What this means for bypass.js

`assets/frida/bypass.js` retains the root / emulator / proxy / SSL-pinning /
`Debug.isDebuggerConnected` options. Enabled groups override Java check results;
they change behavior rather than merely observe it. Use only the groups needed
for an explicitly scoped mobile protection-change experiment under
`operating-scope.md`, and record the original and changed results.

It does not implement a general solution for native PC-divergence checks.
Identify such checks and document the limit. Finding one does not automatically
select additional hooks, memory inspection, or a different tracer.

## Anti-ptrace / attach-killing: Frida as a call-only oracle

Native anti-ptrace, launch-environment differences, and hook-induced failures can
all end a session. A previous target-specific case (Ctrip) observed failures on
attach and heavy hooking, with a minimal spawn-time call-only agent completing
one native call. That observation does not establish behavior for another build.

For an explicitly scoped mobile experiment, the existing techniques include
spawn-time instrumentation, a narrow Frida RPC/native-call oracle, and the
`Interceptor.replace` changes to `exit`/`_exit`/`kill` used in that case. The last
option suppresses termination and changes program behavior; it is not a default
repair for failed attachment. Record the affected checks and restore the test
state after the experiment. Restart only a session-owned frida-server when logs
support a stale-server diagnosis; do not prescribe an unconditional process kill.

Compare static inspection, isolated unidbg emulation, and scoped eBPF or memory
observations by their evidence coverage. No alternative is guaranteed to avoid
the target's checks, and none expands the established data/service scope.

## Self-test: is my own DBI visible here?

If you must use Frida or QTrace on a target you *think* is clean, you can borrow
dbi_detect's `DBI_TRACE_DETECTED()` macro as a probe: compile it into a tiny
native sample (or the target's own harness) and run it under your Frida/QTrace
session. A non-zero result means your instrumentation is observable in this
process. Record the observation, compare with a baseline, and assess whether it
changes the measurement you need. It does not by itself select another tool.

## Caveats

- dbi_detect implements **two** techniques, not a complete anti-DBI suite — a
  real target may add maps/port/string scans and timing checks on top. Absence
  of these two is not proof the app is DBI-blind.
- **ARM64 only**, and the repo is sample/education-grade — the *value is the
  knowledge* (how the detection works, what to grep for), not the binary.
- eBPF tracing has observable effects too, including probe timing and debug
  facilities. Measure those effects rather than treating any method as invisible.
  Limit trace coverage and captured data to the question being investigated.

## See also

- `native-tracing.md` — stackplz observation modes, requirements, and limits.
- `ecapture-capture.md` — scoped TLS observations using eBPF uprobes.
- `native-emulation.md` — QTrace/QBDI section: powerful instruction trace, but
  it is precisely what these checks catch, so gate it on a clean triage.
- `ida-workflow.md` — where you read the `.so` to find (and confirm) these
  checks.
