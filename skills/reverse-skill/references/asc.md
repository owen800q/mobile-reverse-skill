# ASC: focused DEX search and class decompilation

Use [MG1937/ASC](https://github.com/MG1937/ASC) for a concrete string, class,
method, or field investigation, especially when full APK decompilation is costly.
It searches DEX directly, reconstructs a small DEX for a selected class, and uses
**Androguard DAD** to emit Java. Choose jadx for a complete source tree or a
second rendering of difficult methods. ASC's upstream speed figures are its own
benchmark, not evidence that it recovers every app's code better than jadx.

## Setup and compatibility

The CLI and internals were checked at commit
`6bd94926c700d4254723efb137753d965a6151ac` (2026-09-10). Use a separate checkout
and Python environment, outside the installed skill. The source has no dependency
manifest at this revision. **Python 3.11+ is required for reference searches**:
`findrefs/locator/insn_locator.py` uses atomic regex groups `(?>...)`. Python 3.8
can pass `--help` and even `getclass`, then fail on `findrefs`.

One-time setup, with absolute paths chosen for the host:

```bash
git clone https://github.com/MG1937/ASC.git "$ASC_ROOT"
git -C "$ASC_ROOT" checkout 6bd94926c700d4254723efb137753d965a6151ac
python3.12 -m venv "$ASC_ROOT/.venv"
"$ASC_ROOT/.venv/bin/python" -m pip install 'androguard==4.0.1'
export ASC_ROOT
export ASC_PYTHON="$ASC_ROOT/.venv/bin/python"
"$ASC_PYTHON" "$ASC_ROOT/main.py" --help
```

`ASC_ROOT` must be set to the desired checkout path before these commands.
Androguard 4.0.1 is the tested version; pinning matters because ASC monkey-patches
its internals. GUI dependencies are unnecessary for this CLI workflow. Run ASC
in a subprocess: its decompiler replaces many `sys.modules` entries, including
standard-library modules. Do not import it into a long-lived agent/helper process.
The skill's `scripts/asc.py` handles this isolation and does no installation or
network access.

## P0 / P1: search, extract, follow callers

Resolve `SKILL_ROOT` and `SESSION_DIR` as in `agent-runtime.md`. Use the original
APK and runtime class names. Each `--out` is a **new per-query directory**; choose
another name on a retry. Wrapper options precede the subcommand.

```bash
# Save cross-DEX references to the endpoint string without a full Java export.
python3 "$SKILL_ROOT/scripts/asc.py" --out "$SESSION_DIR/asc/login-refs" \
  findrefs "$APK" string 'auth/login'

# Replace the class below with the class in an actual reference hit.
python3 "$SKILL_ROOT/scripts/asc.py" --out "$SESSION_DIR/asc/login-class" \
  getclass "$APK" 'Lcom/example/Api;'

# Find callers or field users; --class is exact unless --fuzzy-class is supplied.
python3 "$SKILL_ROOT/scripts/asc.py" --out "$SESSION_DIR/asc/login-callers" \
  findrefs "$APK" method login --class com.example.Api
python3 "$SKILL_ROOT/scripts/asc.py" --out "$SESSION_DIR/asc/token-users" \
  findrefs "$APK" field token --class com.example.Session
python3 "$SKILL_ROOT/scripts/asc.py" --out "$SESSION_DIR/asc/type-users" \
  findrefs "$APK" type 'Lcom/example/Api;'

# Scan only the selected Java output; this is not a whole-app inventory.
python3 "$SKILL_ROOT/scripts/api_extract.py" "$SESSION_DIR/asc/login-class" \
  --out "$SESSION_DIR/api/login-class"
```

`--asc-root /absolute/ASC` and `--python /absolute/venv/bin/python` override the
environment variables. `--threads N` controls ASC workers (default 8).
`getclass` accepts dotted names or descriptors; quote descriptors containing `;`
and inner-class names containing `$`. Method/field searches also accept a
class-only query: `findrefs "$APK" method --class com.example.Api`.

Search patterns use Python **regex**, not literal substring matching. Escape
metacharacters when needed (e.g. `'api\.example\.com'`). Type queries are raw
descriptor patterns: use slashes, not dotted Java package names. A member's
`--class` is normalized by the wrapper; `--fuzzy-class` uses upstream's fuzzy
matching. The raw `main.py` command places `--threads` before the `string/type/
method/field` subcommand and `-o` after it; the wrapper constructs that order.

References look like `classes2.dex | Lcom/example/Api;->login | matched=(...)`.
Keep the DEX identity and original class/member name. Follow one caller layer at
a time and extract the hit classes; do not automatically decompile every class
matching a broad term such as `token`. A reference hit is a lead, not proof of
request semantics. Read the method, align captured fields, and apply the ledger's
existing evidence rules.

## Outputs and failure handling

Each launched query writes `asc_summary.json`, `stdout.txt`, `stderr.txt`, and either
`refs.txt` or `Class.java` when ASC emits it. The summary records the input SHA-256,
DEX entries, upstream commit and entrypoint hash, Python version, exact argv,
working directory, exit status, output hash, and limited coverage. A Git commit
identifies the checkout revision, not a guarantee that all its files are clean.
Original stdout/stderr are retained even on a nonzero exit. The wrapper prints
the summary JSON to stdout; class/source text lives in the output file.
Invalid inputs or setup paths fail before launch with a diagnostic on stderr.

- `ok` means ASC exited zero and emitted output, not that every method is correct.
  Inspect DAD warnings and pseudocode; use jadx or smali to resolve disagreements.
- `no_matches` means a successful query emitted no references. It does not prove
  the string/member is absent: queries inspect code references, not every resource,
  annotation, reflection target, native string, or runtime-decrypted DEX. At the
  checked revision `StringLocator` also excludes the final string-data item from
  its search window; corroborate a negative result before drawing conclusions.
  Retrofit endpoint strings may exist only in annotations: extract a known API
  interface with `getclass`, or use a full jadx export plus `api_extract.py` to
  discover interfaces when a code-reference query finds nothing.
- `failed` preserves partial output for inspection and returns nonzero. Check
  `stderr.txt` for missing `androguard`/`mutf8`, Python regex incompatibility,
  unsupported DEX, or class extraction errors. The wrapper also rejects an empty
  class output or an upstream `Error:` string even if ASC exits zero. A class not
  found may live in another split or a runtime DEX; inspect those artifacts next.
- `running` without completion requires checking the actual process before retrying.

Use a new query directory for another attempt and preserve the earlier record.
The wrapper never overwrites an existing directory or imports ASC modules.

## Package coverage and the existing decode path

ASC takes **one APK**, scanning its top-level DEX entries. It does not replace
apktool's manifest/resources/smali decode or the native-library survey. For that
metadata without full jadx export, when apktool is installed:

```bash
bash "$SKILL_ROOT/scripts/decode_apk.sh" "$APK" \
  --out "$SESSION_DIR/decode" --skip-jadx
```

For a full source tree, run the same command without `--skip-jadx` in a separate
output directory. Read `decode_summary.json` for tool statuses and package/native
metadata, and use `decode/jadx/sources` for full-source API extraction. ASC has its
own query summaries; `decode_apk.sh` does not run ASC implicitly.

For XAPK/APKS/APKM, extract members into a persistent session directory first,
identify the base and **every code-bearing split**, and query each relevant APK
separately. `decode_apk.sh` selects a base for Java and surveys native libraries
across splits; it does not merge split DEX. Its temporary base paths disappear
after exit. Nested APK wrappers need the actual inner APK; ASC does not recurse.
AAB needs conversion to APKs before either route. A loose runtime `.dex` can be
copied into a new ZIP as `classes.dex` with an `.apk` suffix for code-only ASC
queries; that container is not an installable package or a manifest source.

For Hermes/RN, Flutter, IL2CPP, or packed DEX, use the platform/unpacking reference
selected by P0. ASC searches the DEX present in the supplied APK, not those other
languages or missing runtime code.

## Repeatable integration check

From this repository, with Java (`javac`, `java`) and Android SDK `d8.jar` available:

```bash
ASC_TEST_ROOT="$ASC_ROOT" ASC_PYTHON="$ASC_PYTHON" \
ASC_TEST_D8="/absolute/android-sdk/build-tools/33.0.2/lib/d8.jar" \
  python3 -m unittest discover -s tests -p test_asc.py -v
```

The opt-in tests build a tiny two-DEX APK from Java, run the real ASC CLI, verify
all four reference kinds and class extraction, and feed the result into
`api_extract.py`. Default tests use a fake child CLI to check argument boundaries,
failure evidence, and output preservation without downloading ASC or dependencies.
