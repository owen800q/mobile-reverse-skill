#!/usr/bin/env python3
"""Flat-file export of an IDA-analyzed database for MCP-less reverse engineering.

This is the "no-MCP" IDA export path for the Android reverse-engineering skill.
It runs headlessly under IDA's idalib-activated Python (IDA 9.x), opens (or
creates and auto-analyzes) a database, and writes a flat tree that Claude can
read directly without an IDA MCP server:

    <out>/decompile/0x<ea>.c   Hex-Rays pseudocode per function, each prefixed
                               with a header comment listing name, ea, size,
                               callers and callees.
    <out>/functions.txt        addr <TAB> name <TAB> size
    <out>/strings.txt          addr <TAB> string
    <out>/imports.txt          addr <TAB> module <TAB> symbol
    <out>/exports.txt          addr <TAB> name <TAB> ordinal=N

Modeled on P4nda0s's IDA-NO-MCP / IDALib decompile-export approach.

Usage:
    ida_export.py <binary.so | existing.i64> [--out DIR] [--max N] \
                  [--funcs 0xADDR,0xADDR]

The IDA modules imported here (idapro, ida_hexrays, idautils, ...) do not exist
in a plain Python environment. That is expected: every IDA import is deferred
into load_ida() so `python3 -m py_compile ida_export.py` still passes on a
machine without IDA. When idalib is not activated the script prints activation
instructions and exits non-zero instead of dumping a raw traceback.
"""

from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path


ACTIVATION_HELP = """\
[!] IDA idalib is not activated for this Python interpreter.

    This script must run under a Python that has IDA's idalib installed and
    activated (IDA 9.x). Set it up once, then re-run with that same Python:

      1. Point IDADIR at your IDA install (the folder with the ida/idat
         binaries). On macOS that is inside the .app bundle, e.g.:
           export IDADIR="/Applications/IDA Professional 9.3.app/Contents/MacOS"

      2. Install the idalib wheel into your Python:
           pip install "$IDADIR"/idalib/python/idapro-*.whl

      3. Activate idalib for this interpreter:
           python "$IDADIR"/idalib/python/py-activate-idalib.py

      4. Re-run this script with that same Python interpreter, e.g.:
           python ida_export.py target.so --out ./re_out/ida
"""


def eprint(*args, **kwargs) -> None:
    """Print progress / diagnostics to stderr (stdout is kept clean)."""
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)


def hexaddr(ea: int) -> str:
    return f"0x{ea:x}"


def load_ida():
    """Import IDA idalib modules, or print activation help and return None.

    All IDA imports live here so the module byte-compiles without IDA present.
    """
    try:
        import idapro  # must be importable before the rest of the IDA SDK
    except Exception as exc:  # noqa: BLE001 - any import failure means "not activated"
        eprint(f"[!] Could not import 'idapro' ({exc.__class__.__name__}: {exc})")
        eprint(ACTIVATION_HELP)
        return None

    try:
        import ida_hexrays
        import idautils
        import idc
        import ida_funcs
        import ida_nalt
        import ida_bytes
        import ida_name
        import ida_auto
        import idaapi
    except Exception as exc:  # noqa: BLE001
        eprint(f"[!] idapro imported but the IDA SDK is incomplete ({exc}).")
        eprint(ACTIVATION_HELP)
        return None

    return types.SimpleNamespace(
        idapro=idapro,
        ida_hexrays=ida_hexrays,
        idautils=idautils,
        idc=idc,
        ida_funcs=ida_funcs,
        ida_nalt=ida_nalt,
        ida_bytes=ida_bytes,
        ida_name=ida_name,
        ida_auto=ida_auto,
        idaapi=idaapi,
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="ida_export.py",
        description="Export a flat-file view of an IDA database (no MCP needed).",
    )
    parser.add_argument(
        "target",
        help="Path to a native binary (.so) or an existing IDA database (.i64/.idb).",
    )
    parser.add_argument(
        "--out",
        default="./re_out/ida",
        help="Output directory root (default: ./re_out/ida).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Max number of functions to decompile (0 = no limit).",
    )
    parser.add_argument(
        "--funcs",
        default=None,
        help="Comma-separated function addresses to restrict the export "
        "(e.g. 0x1234,0x5678). Overrides --max; thunk/library skipping is "
        "disabled for explicitly requested functions.",
    )
    return parser.parse_args(argv)


def wait_for_analysis(ns) -> None:
    """Block until IDA's auto-analysis queue is drained."""
    try:
        if hasattr(ns.idapro, "auto_wait"):
            ns.idapro.auto_wait()
            return
    except Exception:  # noqa: BLE001 - fall through to ida_auto
        pass
    try:
        ns.ida_auto.auto_wait()
    except Exception as exc:  # noqa: BLE001
        eprint(f"[!] auto_wait failed (continuing): {exc}")


def is_skippable(ns, func) -> bool:
    """Skip thunks and library functions for decompilation when reasonable."""
    flags = getattr(func, "flags", 0)
    if flags & ns.ida_funcs.FUNC_THUNK:
        return True
    if flags & ns.ida_funcs.FUNC_LIB:
        return True
    return False


def get_callers(ns, func_ea):
    """Return [(ea, name)] of functions that reference func_ea (resolved)."""
    callers = []
    seen = set()
    try:
        refs = list(ns.idautils.CodeRefsTo(func_ea, 0))
    except Exception:  # noqa: BLE001
        refs = []
    for ref in refs:
        owner = ns.ida_funcs.get_func(ref)
        target = owner.start_ea if owner else ref
        if target in seen:
            continue
        seen.add(target)
        name = ns.idc.get_func_name(target) or ns.ida_name.get_name(target) or hexaddr(target)
        callers.append((target, name))
    return callers


def get_callees(ns, func):
    """Return [(ea, name)] of call targets inside func.

    Scans each instruction; for call instructions it collects the cross
    references leaving that instruction (idautils.CodeRefsFrom with flow=0),
    which resolves both direct calls and import stubs.
    """
    callees = []
    seen = set()
    try:
        heads = list(ns.idautils.FuncItems(func.start_ea))
    except Exception:  # noqa: BLE001
        heads = []
    for head in heads:
        try:
            if not ns.idaapi.is_call_insn(head):
                continue
        except Exception:  # noqa: BLE001
            continue
        try:
            targets = list(ns.idautils.CodeRefsFrom(head, 0))
        except Exception:  # noqa: BLE001
            targets = []
        for tgt in targets:
            owner = ns.ida_funcs.get_func(tgt)
            if owner is not None:
                tgt = owner.start_ea
            if tgt in seen:
                continue
            name = ns.idc.get_func_name(tgt) or ns.ida_name.get_name(tgt)
            if not name:
                # Unnamed, non-function target (rare); keep the raw address.
                name = hexaddr(tgt)
            seen.add(tgt)
            callees.append((tgt, name))
    return callees


def build_header(name, ea, size, callers, callees) -> str:
    def fmt(pairs):
        if not pairs:
            return "(none)"
        return ", ".join(f"{nm} ({hexaddr(a)})" for a, nm in pairs)

    lines = [
        "/*",
        f" * Function : {name}",
        f" * Address  : {hexaddr(ea)}",
        f" * Size     : {size} bytes",
        f" * Callers  : {fmt(callers)}",
        f" * Callees  : {fmt(callees)}",
        " */",
        "",
    ]
    return "\n".join(lines)


def decompile_one(ns, ea, dec_dir, have_hexrays) -> str:
    """Decompile one function and write <dec_dir>/0x<ea>.c. Returns status."""
    func = ns.ida_funcs.get_func(ea)
    if func is None:
        return "skip"

    name = ns.idc.get_func_name(ea) or hexaddr(ea)
    size = func.end_ea - func.start_ea
    callers = get_callers(ns, func.start_ea)
    callees = get_callees(ns, func)
    header = build_header(name, ea, size, callers, callees)

    body = None
    if have_hexrays:
        try:
            cfunc = ns.ida_hexrays.decompile(ea)
            if cfunc is not None:
                body = str(cfunc)
        except Exception as exc:  # noqa: BLE001 - one failure must not abort the batch
            eprint(f"[!] decompile failed at {hexaddr(ea)}: {exc}")

    if body is None:
        body = "// <decompilation unavailable>\n"
        status = "fail"
    else:
        status = "ok"

    out_path = dec_dir / f"0x{ea:x}.c"
    out_path.write_text(header + body + "\n", encoding="utf-8")
    return status


def select_targets(ns, args):
    """Resolve the list of function EAs to decompile."""
    if args.funcs:
        eas = []
        for tok in args.funcs.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                eas.append(int(tok, 0))
            except ValueError:
                eprint(f"[!] ignoring invalid --funcs token: {tok!r}")
        return eas, True

    eas = list(ns.idautils.Functions())
    if args.max and args.max > 0:
        eas = eas[: args.max]
    return eas, False


def export_functions(ns, path) -> int:
    lines = []
    for ea in ns.idautils.Functions():
        func = ns.ida_funcs.get_func(ea)
        size = (func.end_ea - func.start_ea) if func else 0
        name = ns.idc.get_func_name(ea) or hexaddr(ea)
        lines.append(f"{hexaddr(ea)}\t{name}\t{size}")
    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def export_strings(ns, path) -> int:
    count = 0
    with open(path, "w", encoding="utf-8", errors="replace") as fh:
        try:
            strings = ns.idautils.Strings()
        except Exception as exc:  # noqa: BLE001
            eprint(f"[!] string enumeration failed: {exc}")
            return 0
        for item in strings:
            try:
                text = str(item)
            except Exception:  # noqa: BLE001
                continue
            # Keep each string on a single line.
            text = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
            fh.write(f"{hexaddr(item.ea)}\t{text}\n")
            count += 1
    return count


def export_imports(ns, path) -> int:
    lines = []

    def make_cb(module_name):
        def imp_cb(ea, name, ordinal):
            symbol = name if name else f"ordinal_{ordinal}"
            lines.append(f"{hexaddr(ea)}\t{module_name}\t{symbol}")
            return True
        return imp_cb

    try:
        qty = ns.ida_nalt.get_import_module_qty()
    except Exception as exc:  # noqa: BLE001
        eprint(f"[!] import enumeration failed: {exc}")
        qty = 0

    for i in range(qty):
        module_name = ns.ida_nalt.get_import_module_name(i) or "<unnamed>"
        try:
            ns.ida_nalt.enum_import_names(i, make_cb(module_name))
        except Exception as exc:  # noqa: BLE001
            eprint(f"[!] enum_import_names failed for module {module_name}: {exc}")

    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def export_exports(ns, path) -> int:
    lines = []
    try:
        entries = list(ns.idautils.Entries())
    except Exception as exc:  # noqa: BLE001
        eprint(f"[!] export enumeration failed: {exc}")
        entries = []
    for entry in entries:
        # Entries() yields (index, ordinal, ea, name); be tolerant of shape.
        try:
            ordinal, ea, name = entry[1], entry[2], entry[3]
        except Exception:  # noqa: BLE001
            continue
        name = name or hexaddr(ea)
        lines.append(f"{hexaddr(ea)}\t{name}\tordinal={ordinal}")
    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def run_export(ns, args) -> int:
    target = Path(args.target).expanduser().resolve()
    if not target.is_file():
        eprint(f"[!] target not found: {target}")
        return 2

    out_dir = Path(args.out).expanduser().resolve()
    dec_dir = out_dir / "decompile"
    dec_dir.mkdir(parents=True, exist_ok=True)

    is_db = target.suffix.lower() in (".i64", ".idb")
    eprint(f"[*] opening {'database' if is_db else 'binary'}: {target}")
    try:
        # For an existing DB do not re-run auto-analysis; for a raw binary do.
        rc = ns.idapro.open_database(str(target), not is_db)
    except Exception as exc:  # noqa: BLE001
        eprint(f"[!] open_database failed: {exc}")
        return 1
    if rc:
        eprint(f"[!] open_database returned non-zero ({rc}); aborting.")
        return 1

    try:
        wait_for_analysis(ns)

        try:
            have_hexrays = bool(ns.ida_hexrays.init_hexrays_plugin())
        except Exception as exc:  # noqa: BLE001
            eprint(f"[!] init_hexrays_plugin raised: {exc}")
            have_hexrays = False
        if not have_hexrays:
            eprint("[!] Hex-Rays decompiler unavailable; exporting metadata only.")

        # Metadata exports first, so they exist even if decompilation is long.
        n_funcs = export_functions(ns, out_dir / "functions.txt")
        n_strings = export_strings(ns, out_dir / "strings.txt")
        n_imports = export_imports(ns, out_dir / "imports.txt")
        n_exports = export_exports(ns, out_dir / "exports.txt")
        eprint(
            f"[*] metadata: {n_funcs} functions, {n_strings} strings, "
            f"{n_imports} imports, {n_exports} exports"
        )

        targets, explicit = select_targets(ns, args)
        total = len(targets)
        eprint(f"[*] decompiling {total} function(s) -> {dec_dir}")

        ok = fail = skipped = 0
        for i, ea in enumerate(targets, 1):
            try:
                func = ns.ida_funcs.get_func(ea)
                if func is None:
                    skipped += 1
                    continue
                if not explicit and is_skippable(ns, func):
                    skipped += 1
                    continue
                status = decompile_one(ns, ea, dec_dir, have_hexrays)
                if status == "ok":
                    ok += 1
                elif status == "fail":
                    fail += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001 - keep the batch alive
                fail += 1
                eprint(f"[!] error on {hexaddr(ea)}: {exc}")

            if total and (i % 50 == 0 or i == total):
                eprint(
                    f"[*] progress {i}/{total} "
                    f"(ok={ok} fail={fail} skip={skipped})"
                )

        eprint(
            f"[+] done: {ok} decompiled, {fail} failed, {skipped} skipped; "
            f"output in {out_dir}"
        )
        return 0
    finally:
        try:
            ns.idapro.close_database(False)
        except Exception as exc:  # noqa: BLE001
            eprint(f"[!] close_database error: {exc}")


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    ns = load_ida()
    if ns is None:
        return 2
    try:
        return run_export(ns, args)
    except Exception as exc:  # noqa: BLE001 - never surface a raw traceback
        eprint(f"[!] fatal: {exc.__class__.__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
