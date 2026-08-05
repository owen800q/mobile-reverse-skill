# Native Emulation & Recovery (advanced)

On-demand reference for when the login-signing logic lives in a `.so` and static reading alone is
not enough. Three escalations: **run** the function offline (Unicorn), **shape** its data (struct
recovery), and **name** its callees (symbol recovery). Load this only when `ida-workflow.md` has you
staring at a small-but-obfuscated function and you need to execute it or reconstruct its types.

## Contents

1. [When to reach for this](#1-when-to-reach-for-this)
2. [Unicorn: emulate an isolated native function](#2-unicorn-emulate-an-isolated-native-function)
3. [Struct recovery from access patterns](#3-struct-recovery-from-access-patterns)
4. [Symbol / function-name recovery](#4-symbol--function-name-recovery)
5. [On-device instruction trace (QTrace / QBDI)](#5-on-device-instruction-trace-qtrace--qbdi)

Siblings: `ida-workflow.md` (native static) · `native-tracing.md` (eBPF dynamic) ·
`dbi-detection.md` (is Frida/QBDI burned?) · `crypto-id.md` (algorithm ID) ·
`signing-replay.md` (request reconstruction).

---

## 1. When to reach for this

You already isolated the sign/encrypt function in IDA (via `ida-workflow.md`) but:

- **The pseudocode is a soup** — obfuscated, but the function is *small and self-contained* (few
  imports, no huge call tree). Reading it top-down failed; **running** it with concrete inputs and
  watching the output is faster than deciphering it. → **Unicorn** (§2).
- **You want to reproduce signing without the device** — a pure offline oracle you can call from
  Python to forge `X-Sign` for arbitrary bodies, no Frida, no phone in the loop. → **Unicorn** (§2).
- **The code reads `*(a1 + 0x18)` everywhere and you can't tell what `a1` is** — you need the struct
  layout to make the decompiler readable. → **Struct recovery** (§3).
- **Every callee is `sub_401000` and you're guessing** — naming the helpers (this one is `malloc`,
  that one is `memcpy`, this is the SHA256 round) collapses the function into something legible.
  → **Symbol recovery** (§4).

If instead the function is *large*, has control-flow flattening, or pulls in the whole runtime,
don't emulate — capture the values as it runs. Prefer **eBPF tracing** (stackplz uprobe/brk,
`native-tracing.md`): it reads the JNI-boundary buffers without injecting anything, so it survives
anti-DBI targets. If control-flow flattening is defeating you and you need the *per-instruction
executed path* (not just boundary I/O), and the target is **not** DBI-hardened (verify first with
`dbi-detection.md`), use **QTrace** (§5). Fall back to Frida runtime tracing (`jni_trace.js`,
`signing-replay.md`) only when eBPF is unavailable. Unicorn shines on **small, deterministic,
dependency-light** code.

**Higher-level alternative for JNI:** if the target is a full `Java_com_...` JNI export that expects
a real `JNIEnv`, reflection, and Android libc, reach for **unidbg** (`https://github.com/zhkl0228/unidbg`)
instead of raw Unicorn. It ships an emulated Android/JNI/libc environment (VM, `JNIEnv`, syscalls,
common `.so` deps) so you write a small Java harness instead of hand-building every stub. Use raw
Unicorn (§2) when the target is a *leaf* algorithm with a handful of libc calls; use unidbg when it
is entangled with JNI and the Android runtime.

**unidbg as an off-device sign oracle (field-tested).** unidbg ran an OLLVM'd
`libscmain.so` `SecurityUtil.simpleSign([B,"getdata")` fine — **OLLVM obfuscation is
irrelevant to emulation** (it's real ARM execution; no deflattening needed). This is
a huge shortcut vs. static de-obfuscation, and vs. fighting an anti-Frida target
(`dbi-detection.md`): the app never runs. Practical notes from getting it working:

- **Make it a persistent stdin server.** JVM boot is ~15-30 s; pay it **once**. Read
  md5 (or body) lines on stdin, print signs on stdout, loop. Schema iteration during
  P5 is then instant instead of a fresh JVM per sign. (See the `scripts/sign_server`
  spec in `SKILL.md`.)
- **jitpack dep hell.** unidbg's transitive deps don't propagate through jitpack
  POMs — declare them **all** explicitly. Known-good set: `unidbg-api`,
  `unidbg-android`, `unicorn`, `capstone`, `keystone`, `jna`, `fastjson`,
  `apk-parser`, and the `commons-*` it pulls. A missing transitive is the #1 failure.
- **cwd matters.** Needs `base.apk` + the target `.so` alongside the jar; run from
  that directory or unidbg won't find them.

---

## 2. Unicorn: emulate an isolated native function

Goal: map just enough of the `.so` into a Unicorn VM, fake everything the target calls, and run it.
You are emulating **one function**, not the program — resist the urge to be complete.

### Core principles

- **Load raw first, parse ELF only if forced.** `open(so).read()` and map the bytes at the `.so`'s
  IDA base; you only need the code and rodata the function touches. Full ELF parsing (segments,
  relocations) is a fallback for when code references fixed segment addresses that raw loading
  didn't place. Less setup = fewer things to get wrong.
- **Fake the environment, don't provide it.** Every external call (libc, JNI, syscall) is *hooked*
  and answered in Python — you never load real libc.
- **Lean on callbacks.** Unicorn's hooks are your debugger: trace, error-recovery, and env
  simulation all ride on them.
- **Iterate on crashes.** The loop *is* the method (see below). Each crash tells you exactly what to
  map or hook next.
- **Trace at block level, not instruction level.** `UC_HOOK_BLOCK` with a counter; only turn on
  `UC_HOOK_CODE` instruction trace on a narrow address range when you're chasing a specific bug.
  Per-instruction logging on a crypto loop buries the signal.

### Calling convention & syscall basics

Set args in registers, put a sentinel in LR so you know when the function returns, then
`emu_start(func, until=sentinel)`.

| Arch | Uc arch/mode | Args | Return | LR / return-to | Syscall |
|-|-|-|-|-|-|
| ARM64 | `UC_ARCH_ARM64` LE | X0–X7 | X0 | X30 (set to sentinel) | nr in X8, `SVC #0` |
| ARM32 | `UC_ARCH_ARM` + THUMB/ARM | R0–R3 | R0 | LR (set to sentinel) | nr in R7, `SVC #0` |

THUMB matters on ARM32: if the function's low address bit is set (odd address), it's Thumb — use
`UC_MODE_THUMB` and start at `addr & ~1`. Getting this wrong decodes garbage immediately.

### The fake JNIEnv table

If the function takes `JNIEnv* env` (arg0 in most JNI helpers), it will do `(*env)->Fn(env, ...)` —
a double indirection through a function-pointer table. Build it:

1. Allocate a block of UC memory for the table (say 256 entries × 8 bytes on ARM64).
2. Allocate a second block, fill it with `RET` stubs (one small stub per slot, or point every slot
   at a single shared `RET` address).
3. Write each table slot = address of its stub. Write `*env = table_base`.
4. In your `UC_HOOK_CODE`/import hook, when PC lands on a stub address, look up **which JNI index**
   it was (by offset), run the Python simulation for that call (e.g. `GetStringUTFChars` → copy your
   input string into UC memory, return its pointer in X0), then `PC = LR`.

The RET stub guarantees control returns even for JNI calls you haven't modeled yet — you fill them
in as the crash loop reveals which ones actually get called.

### Simulating imports and libc

Bump-allocator `malloc`: keep a Python `heap_ptr`, return it, advance by (size rounded up). `free` is
a no-op. `memcpy`/`memset`/`strlen` read/write UC memory directly and set the return register. Hook
each import by its address: in a `UC_HOOK_CODE` callback, `if pc in IMPORTS: IMPORTS[pc](uc); pc = lr`.
Resolve import addresses from the PLT/GOT or IDA's import list.

| Dependency | How to fake |
|-|-|
| `malloc`/`calloc` | bump allocator, return `heap_ptr`, bump it |
| `free` | no-op |
| `memcpy`/`memmove`/`memset` | read args, do it in Python on UC mem, return dst |
| `strlen`/`strcmp` | walk UC mem, return len / compare result |
| JNI (`GetStringUTFChars`, `NewByteArray`, `GetArrayLength`) | fake JNIEnv slot → Python impl |
| syscalls (`gettimeofday`, `getrandom`, `read`) | `UC_HOOK_INTR`, dispatch on nr, return plausible value |

### Auto-map and syscall dispatch hooks

- `UC_HOOK_MEM_UNMAPPED`: return `True` after mapping a page at the faulting address (align down to
  page size, `mem_map`, optionally zero-fill). This makes uninitialized-pointer reads and missing
  stack/heap pages self-heal instead of aborting — you converge on the real memory map by running.
- `UC_HOOK_INTR`: fires on `SVC`/`INT`. Read the syscall number (X8/R7), dispatch, write the result
  to the return register. Stub `getrandom`/`clock_gettime` with fixed values so the run is
  deterministic and reproducible.

### The iterative crash → map/hook → rerun loop

This is the whole workflow. Run, read the fault, fix one thing, rerun:

1. **Run** `emu_start`; let it throw.
2. **Read the fault** from the exception / your hooks: faulting address + access type (fetch / read
   / write).
3. **Diagnose:** unmapped *fetch* → missing code page, map it (or you jumped into an unhooked
   import — hook it). Unmapped *read/write* → missing data page or a pointer you didn't set up.
   Landing on an import/JNI stub → add that Python simulation. Not terminating → add a
   `UC_HOOK_BLOCK` counter and stop past a threshold to find the loop.
4. **Fix** exactly that one cause.
5. **Rerun.** Repeat until X0/R0 holds the signature/ciphertext.

Then wrap it: a Python function that writes inputs into UC memory, runs, and reads the output — your
offline signing oracle. Cross-check its output against a live-captured request (`signing-replay.md`)
before trusting it.

---

## 3. Struct recovery from access patterns

When the decompiler shows `*(a1 + 0x18)` scattered across a function, recover the struct so IDA can
apply a type and the pseudocode becomes readable. Requires IDA access (MCP or an IDA-NO-MCP export
with per-function `decompile/<addr>.c` files carrying `callers:`/`callees:` metadata — see
`ida-workflow.md`).

### Collect offsets across the whole call graph

One function rarely touches every field. Widen the view:

1. **Target function** — record every `*(a1 + off)` on the suspected struct pointer: offset, access
   size (`_BYTE`/`_DWORD`/`_QWORD`), read vs write, array stride (`*(a1 + 8*i)` → 8-byte elements),
   nesting (`*(*a1 + 0x10)` → field at 0 is itself a pointer).
2. **Callers** — how the pointer is born tells you size and init: `v = malloc(0x40)` ⇒ struct ≈ 0x40
   bytes; `*(v+8) = cb; f(v)` ⇒ offset 8 set at construction; `f(&local)` ⇒ it's a stack struct.
3. **Callees** — the pointer gets passed down; each callee's `*(a1 + off)` adds more fields, and
   `g(a1 + 0x20)` hints that offset 0x20 begins a nested sub-struct.

### Type-by-usage heuristics

| Observed usage | Inferred field |
|-|-|
| offset 0 is a table of func pointers, called `(*(*this))(...)` | **vtable** (C++ object) |
| `++` / `--` then compared to 0 | **refcount** |
| passed to `strlen` / `printf("%s")` / `strcpy` | **char\* string** |
| stored, later `(*(this+off))(...)` | **function pointer / callback** |
| `this->next`/`prev` cross-linked; `n->next->prev == n` | **linked-list node** |
| `AND`/`OR` with `0x1`,`0x2`,`0x4`; compared to enum consts | **flags / enum** |
| used as count in `memcpy`/loop bound | **size / length** |

### Size and output

Struct size ≈ `max(offset) + sizeof(last field)`, rounded to alignment. Emit an annotated C struct
with an offset comment per field and a **confidence note** (High/Medium/Low) — High when callers
confirm the alloc size and most fields have a clear use; Low when you only saw a couple of offsets.

```c
// size ~0x48, confidence: Medium (alloc 0x48 seen in caller 0x401000)
struct login_ctx {
    /* 0x00 */ void   *vtable;    // (*(*this))() called
    /* 0x08 */ int     refcount;  // ++/-- around use
    /* 0x10 */ char   *key;       // -> strlen
    /* 0x18 */ void   *buf;
    /* 0x20 */ size_t  len;       // memcpy count
    /* 0x28 */ struct login_ctx *next;  // list link
};
```

Apply it in IDA (set the type on `a1`) and re-decompile — fields now read by name, and the next pass
of §4 gets easier.

---

## 4. Symbol / function-name recovery

Stripped `.so`: every helper is `sub_XXXX`. Naming even a few collapses the target into something
readable. Work from strongest signal to weakest.

### Magic constants → known algorithm

The fastest win. A magic number pins the algorithm outright. **Do not eyeball the constant tables** —
delegate identification to `crypto-id.md` / `constscan.py`, which scans the function's constants
against a signature database (MD5 `0x67452301…`, CRC32 `0xEDB88320`, AES S-box, Base64 charset, zlib
`0x78 0x9C`, SHA-2 round constants, etc.). A hit names the function immediately: `sub_401000` doing
MD5 init → `md5_init`.

### Paired-call patterns

Functions come in balanced pairs; match the shape even without symbols:

- `p = A(size); … B(p);` → **alloc / free** (`malloc`/`free`, `new`/`delete`).
- `A(lock); …critical…; B(lock);` (same object) → **lock / unlock**.
- `h = A(path, flags); … B(h);` → **open / close**.
- `A(&tid, 0, fn, arg); … B(tid, &ret);` → **pthread_create / join**.

Naming one half often names the other by position.

### Argument-shape heuristics

Fixed constant arguments betray the callee:

- `A(2, 1, 0)` → `socket(AF_INET, SOCK_STREAM, 0)`.
- `A(fd, &addr, 16)` → `connect`/`bind` (16 = `sockaddr_in`).
- `A(dst, src, n)` → `memcpy`/`memmove`; `A(ptr, 0, n)` → `memset`.
- `A(fd, buf, n)` returning a byte count → `read`/`write`.

### Return-value idioms

- `if ((fd = A(...)) == -1)` → file/socket call (−1 on error).
- `if (!(p = A(size)))` → allocator (NULL on failure).
- `if (A(...) != 0) goto err;` → success=0 convention.
- `len = A(str); memcpy(d, s, len);` → `A` is `strlen`.

### Walk the call chain to a known export

Cross-reference callees against `imports.txt`; a match names it directly. For unnamed internals,
climb **callers** until you hit a function with a symbol (from `exports.txt` — e.g. a `Java_*` JNI
export) and infer purpose from that named context and how the return value is consumed. Recurse up
the chain until the ambiguity resolves.

Output: suggested name + confidence + one-line reasoning per function, and apply the renames in IDA
so the next struct/emulation pass reads cleanly. Confirm any crypto guess with `crypto-id.md`; if the
function is small-but-obfuscated after naming, hand it to §2 to run.

---

## 5. On-device instruction trace (QTrace / QBDI)

[zgy0x01/QTrace](https://github.com/zgy0x01/QTrace) is a **QBDI-based** (Quarkslab Dynamic Binary
Instrumentation) on-device ARM64 tracer: it records the **executed instruction stream** plus memory
reads/writes, with custom hooks for target functions, JNI, and libc. Where Unicorn (§2) runs a leaf
function *off* the device in a faked environment and unidbg emulates the Android/JNI runtime off-device,
QTrace instruments the **real process on real hardware** — nothing to emulate, so environment-heavy or
anti-emulation code that breaks Unicorn/unidbg just runs.

**Its niche win — de-flattening.** Function-boundary tools (Frida, stackplz uprobe) show you inputs and
outputs; they don't show the path taken *through* an OLLVM control-flow-flattened function. A full
per-instruction trace does: you get the actual sequence of real basic blocks, which collapses the
flattening dispatcher into a linear trace you can read.

**The catch — it is a DBI, so it is detectable.** QTrace injects via Frida and executes the target from
a QBDI **code cache** — exactly the relocation that the checks in `dbi-detection.md` catch. So it is the
*opposite* of stealthy. Gate its use:

> Reach for QTrace **only** when (a) you need per-instruction flow to defeat control-flow flattening
> (boundary I/O from stackplz/Frida isn't enough), **and** (b) the target is not DBI/anti-instrumentation
> hardened — confirm with the `dbi-detection.md` triage first. Otherwise prefer stackplz (stealth,
> `native-tracing.md`) for I/O, or unidbg (§1) for an off-device oracle.

**Workflow (build-and-inject, not a script wrapper).** QTrace is an Android Studio project you configure
per target, so there's no `scripts/*.sh` for it — you drive it by hand:

1. Place the QBDI aarch64 static lib (`libQBDI.a`, from the bundled `libQBDI.zip` or QBDI releases) in
   the project's arm64 lib dir.
2. `adb push` the target `.so` to `/data/local/tmp`; on the device run `setenforce 0` as root (QBDI needs
   SELinux permissive — note this weakens the device for the session).
3. Edit `config()` in `native_main.cpp` to point at the target lib + the offset/symbol to trace; add
   custom hooks in `qbdihook.cpp` (functions), `libctrace.cpp` (libc), `jnitrace.cpp` (JNI).
4. Build (Generate APKs) to produce `libnativelib.so`, push it to `/data/local/tmp`, and inject it into
   the running target with the repo's Frida script (`inject.js`).
5. Read the emitted instruction/memory trace to recover the executed path; feed recovered constants and
   buffers to `crypto-id.md` and the executed path back into your IDA annotations (`ida-workflow.md`).

**Caveats:** heavy per-target setup (source edit + Gradle build), `setenforce 0` reduces device security,
Frida-injected QBDI is maximally detectable, and the project is low-activity with no documented trace
format or license — verify before relying on it. When it fits, though, it is the strongest tool here for
reading *through* obfuscation on real hardware.
