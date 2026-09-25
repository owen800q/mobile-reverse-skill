# Capability checks

Load this before choosing a tool route, when a helper cannot start, or after
moving a session between hosts. Run checks only after intake establishes a
target and objective; a bare skill invocation still asks for the target first.

```bash
python3 "$SKILL_ROOT/scripts/doctor.py" --platform android --json
```

The default run inspects PATH, files, and top-level Python module locations.
It does not run executables, import third-party packages, install dependencies,
enumerate devices, initialize a ledger, or contact a service. It reports what
this interpreter can see; an IDA MCP server or another virtual environment may
have capabilities it cannot inspect. A missing tool on PATH is not proof that
it is absent from the machine.

| Status | Meaning | Next step |
|---|---|---|
| `available` | Required local prerequisites were located | Use the smallest relevant operation to verify the route. |
| `needs_verification` | Some prerequisites or runtime conditions remain unchecked | Read `unverified` and `verify_before_use`; resolve only what the task needs. |
| `missing` | At least one required local prerequisite was not found | Read its inventory detail and linked reference; use an available route meanwhile. |

An installed `idapro` module does not prove license activation. A Frida command
does not prove a matching device server. A local eCapture/stackplz binary does
not prove that it matches the phone's ABI or kernel. Do not turn a diagnostic
report into evidence that an app, hook, capture, or signing scheme works.

For ASC, supply the same `ASC_ROOT` and `ASC_PYTHON` used by `asc.py`. A separate
ASC interpreter is reported as unverified; run the doctor with that interpreter
to inspect its Python version and Androguard availability. Reference searches
need Python 3.11+; follow [asc.md](asc.md) for the tested dependency setup.
Use `--ecapture-bin` / `--stackplz-bin` to inventory local device binaries.
Without these, their location remains unverified, since they may already be on
the phone. Files supplied here are inspected for presence, never executed.

If Android device access is already in scope, explicitly name the serial:

```bash
python3 "$SKILL_ROOT/scripts/doctor.py" --platform android \
  --device "$SERIAL" --timeout 5 --json
```

This runs only `adb -s SERIAL get-state`, `getprop ro.product.cpu.abi`, and
`uname -r`, with a timeout on each command. It may start the host ADB server.
It does not request root, push binaries, attach to apps, or capture traffic.
Device reachability leaves the route-specific runtime checks unverified.

Exit `0` means a report was produced, including reports with missing optional
tools. Exit `2` means invalid arguments; exit `3` means an explicitly requested
device probe failed. `--json` prints one JSON object without a trailing token.
Keep a report in the project session only when it explains a decision; record
the relevant observation in the existing findings ledger.
