# IDA Workflow — Native (.so) Analysis (Phase 4)

Reference for analyzing the extracted native library with **IDA Pro 9.3 (+ idalib)**.
One workflow, two interfaces (live MCP or headless export), chosen by a capability check.

> Ghidra is **not supported here** — use IDA. For fast triage only (`rabin2 -zzI`, quick
> symbol/string peek) see `references/android-triage.md`; do the real work in IDA.

## Capability gate (decide first, keep it short)

- **If IDA MCP tools are available in this session** (any `idapro_*` / `idalib_*` /
  `decompile` / `analyze_function` tool is callable) → drive IDA **live via MCP** (Path A).
- **Otherwise** → use the **headless export path** (Path B): run `scripts/ida_export.py`,
  then READ the exported files. No IDA GUI, no MCP needed.

Both paths share the same first two steps below.

## Contents
- [Step 0 — pick which .so](#step-0--pick-which-so)
- [Step 1 — shared entry: build the DB + open GUI](#step-1--shared-entry)
- [Path A — MCP-driven (live IDA)](#path-a--mcp-driven-live-ida)
- [Path B — headless export (no MCP)](#path-b--headless-export-no-mcp)
- [High-value IDAPython recipes](#high-value-idapython-recipes)
- [Login-task tie-in: find the JNI sign function](#login-task-tie-in-find-the-jni-sign-function)

---

## Step 0 — pick which .so

Don't guess. `scripts/resolve_native_target.py` scores every `.so` (crypto import names,
JNI `RegisterNatives`, string xrefs, ABI priority arm64→armeabi→x86_64→x86) and writes
`selected_native_target.json` + `native_target_candidates.json`.

```bash
python scripts/resolve_native_target.py --output-dir <analysis_out> [--target-dir <apk_root>]
```

Review the selection artifact; override with an explicit path in Step 1 if wrong.

## Step 1 — shared entry

`scripts/ida_target_loader.py` is **MCP-agnostic** and is always the first IDA step once
the target is known. It headless-analyzes with `idat -A -o<db> -S<autowait.py>` (full
auto-analysis, blocks on `auto_wait()`), producing a **`.i64`** (or `.idb` for 32-bit
targets), then best-effort foregrounds the IDA GUI on that DB.

```bash
python scripts/ida_target_loader.py \
  --selected-target-json <out>/step2/selected_native_target.json \
  --output-dir <out>            # DB → <out>/step3/<name>.i64
# or: --so-path /abs/path/libfoo.so   --no-analysis (open raw .so, skip auto-analysis)
```

Notes: IDA 9.x uses unified `ida` (GUI) / `idat` (headless); a pre-built `.i64` reopens
in seconds. idalib licence is typically **single-instance** — close a GUI IDA before
running headless, and vice-versa.

---

## Path A — MCP-driven (live IDA)

### Server + prerequisites (terse — full install in the source repo)

Recommended server: **`ida-multi-mcp`** (stdio, multi-instance). It is **not on PyPI** —
install from GitHub (`pip install "git+https://github.com/MeroZemory/ida-multi-mcp"`),
register in Claude Code as a stdio server with `IDADIR` in `env`. Claude Code auto-launches
it; no manual server process.

idalib activation (once): set `IDADIR` → the IDA dir, then
`pip install "$IDADIR/idalib/python/idapro-"*.whl` and
`python "$IDADIR/idalib/python/py-activate-idalib.py" -d "$IDADIR"`.
Without the wheel + activation, `import idapro` raises `ModuleNotFoundError`.

**Known plugin-loader fix:** `--install` soft-links `plugins/ida_multi_mcp.py`, which
**collides with the package name** (`.plugin is not a package`) and misses custom venvs on
`sys.path`. Fix = replace it with a differently-named loader (`mcp_multi_loader.py`) that
injects your venv `site-packages` into `sys.path`. Keep venv Python == IDA's Python (ABI).
Full snippet: `mcp/README.md` in the source repo.

> Tool names vary by server: `ida-multi-mcp` exposes bare names (`decompile`,
> `analyze_function`, `callees`, `idalib_open`…); the `ida-pro-mcp` fork exposes the fuller
> `idapro_*` set (~72 tools). Capabilities below are grouped by purpose — map to whichever
> names your session offers.

### Useful tools, grouped by use

- **Survey (always first):** `idapro_survey_binary(detail_level="minimal")` — funcs,
  strings, segments, entry points, imports classified (crypto/net/file). `list_funcs`,
  `entity_query(kind, filter)`.
- **Read a function:** `analyze_function(addr)` (pseudocode + strings + consts + callers +
  callees + blocks in one shot), `decompile(addr)`, `disasm(addr, max_instructions)`.
- **Xrefs / data flow:** `xrefs_to(addrs)`, `xref_query(addr, direction)`, `callees`,
  `callgraph(roots, max_depth)`, `trace_data_flow(addr, direction, max_depth)`.
- **Search:** `find_bytes(patterns, limit)` (supports `??` wildcards), `find_regex`,
  `search_text`, `find(type, targets)`.
- **Annotate:** `rename(batch=…)` (batch func/global/local/stack), `set_comments` /
  `append_comments` (sync disasm↔pseudocode).
- **Signatures:** `make_signature` / `make_signature_for_function` / `find_xref_signatures`
  — stable byte sigs to relocate a function across rebuilds.
- **Escape hatch:** `py_eval(code)` runs arbitrary IDAPython in the live DB — use it for any
  recipe below that has no dedicated tool. `int_convert` for base conversions (don't hand-math).

### 7-step loop

1. **survey** → 2. **analyze** key funcs → 3. **xref** interesting strings/consts →
4. **rename + comment** as you learn (raises accuracy of later steps) →
5. **trace data flow** for keys/inputs → 6. repeat 2–5 → 7. **report** findings.

Principle: survey before deep-dive; annotate continuously; follow xrefs from any
interesting datum; pre-process obfuscation (string decrypt, CFF) before reading logic.

---

## Path B — headless export (no MCP)

Run the idalib headless exporter, then just **READ** the output files.

```bash
python scripts/ida_export.py <libfoo.so | libfoo.i64> --out <out_dir>
```

Export layout under `<out_dir>/`:

| Path | Contents |
|-|-|
| `decompile/<hexaddr>.c` | one Hex-Rays pseudocode file per function; header comment lists `// callers:` and `// callees:` |
| `functions.txt` | address, name, size for every function |
| `strings.txt` | all string literals (+ addresses) |
| `imports.txt` | imported symbols (spot `AES`/`HMAC`/`SHA`/`RegisterNatives`) |
| `exports.txt` | exported symbols (spot `Java_*`, `JNI_OnLoad`) |

Then work purely from files: grep `imports.txt`/`exports.txt`/`strings.txt` for leads,
open the matching `decompile/<addr>.c`, and follow its `callers:`/`callees:` comments to
walk the call graph without a live DB.

---

## High-value IDAPython recipes

Short "when you need X, do Y" snippets (run via `py_eval` on Path A, or inside an
`idapro`/idalib script). Verified on IDA 9.x.

**Walk basic blocks (preds/succs)** — CFG traversal, loop/branch analysis:
```python
fc = idaapi.FlowChart(idaapi.get_func(fn), flags=idaapi.FC_PREDS)
for b in fc:
    for s in b.succs(): ...   # successors
    for p in b.preds(): ...   # predecessors (needs FC_PREDS)
```

**Wildcard byte search** — locate a stub/const with unknown operands:
```python
ea = idc.find_bytes("55 ??", ea + 1)   # loop until BADADDR; "??" = any byte
```

**Who calls the sign function** — trace callers up to Java/JNI glue:
```python
[r.frm for r in idautils.XrefsTo(sign_ea)]
```

**Actually invoke a debuggee function (Appcall)** — verify a guessed signer live:
```python
res = ida_idd.Appcall.sign(ida_idd.Appcall.byref(payload))   # returns byref buffers
```

**OLLVM "real block" recovery** — find real blocks = predecessors of the dispatcher merge:
```python
for b in idaapi.FlowChart(idaapi.get_func(fn), flags=idaapi.FC_PREDS):
    for s in b.succs():
        if s.start_ea == ollvm_merge_ea:   # merge point you identified
            idc.add_bpt(b.start_ea)        # bp each real block
```

**Decompile + microcode** — read logic; drop to microcode when the decompiler folds too much:
```python
print(str(ida_hexrays.decompile(func_ea)))
# microcode maturities: MMAT_GENERATED … MMAT_GLBOPT3 … MMAT_LVARS (gen_microcode + vd_printer_t)
```

**Read STL in the debugger** — inspect a key/IV held in a container at a breakpoint:
```python
# std::string (64-bit): ptr is at the object base
s = read_cstr(idc.read_dbg_qword(obj_ea))
# libstdc++ std::map: header root at +0x10; node left/right at +0x10/+0x18, data at +0x20
```

**Arch-aware NOP** — patch out a check (ARM NOP `1F 20 03 D5`, x86 `90`); decode each insn
length before overwriting so you don't split instructions.

More snippets (import-table enumeration, type/struct traversal, batch decompile to JSON,
firmware prologue scan) live in the source `rev-idapython` skill.

---

## Login-task tie-in: find the JNI sign function

Goal: locate the request-signing routine, name its crypto primitive, and recover its
key/IV so the signature can be replayed.

1. **Locate the JNI entry.** Two registration styles:
   - **Static:** exported `Java_<pkg>_<Class>_<method>` symbol → search `exports.txt`
     (Path B) or `entity_query(kind="exports", filter="Java_")` / survey (Path A).
   - **Dynamic:** `JNI_OnLoad` calls `RegisterNatives` with a `{name, sig, fnPtr}` table.
     Decompile `JNI_OnLoad`, read the `JNINativeMethod` array, and map the Java method
     name (e.g. `sign`, `getSign`, `encrypt`) to its native `fnPtr`.
2. **Reach the signer from the table.** Follow xrefs from the `RegisterNatives` method
   table (or the `Java_*` export) into the real implementation; rename it `sign_native`.
3. **Name the primitive.** Feed the decompiled sign function to `constscan.py` /
   `cryptoinstr.py` (magic constants + crypto instructions like AES-NI/SM-round) to
   identify AES/HMAC/SHA/SM3/SM4 — see `references/crypto-id.md`.
4. **Recover key/IV derivation.** `trace_data_flow(..., direction="backward")` (or walk
   `callers:`/`callees:` in the export) from the cipher's key/IV arguments to their source
   — hardcoded bytes, a KDF, or a runtime value. Hand the recovered key/IV + algorithm to
   `references/signing-replay.md` to rebuild signatures offline.
