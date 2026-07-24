# Android Static Triage & API Discovery

Static-first playbook for the STATIC phases of `reverse-skill`: **P0** decode, **P1** static API
extraction, **P3** code↔traffic alignment. Goal: learn the network stack, the request/interceptor
chain, where signing/crypto happens, and whether logic lives in Java or a `.so` — *before* spending
any budget on Frida, packet capture, or IDA. Every dynamic tool is expensive and noisy; static
triage tells you exactly where to point it.

## Contents

1. [P0 — Decode the package](#1-p0--decode-the-package)
2. [P0 — Package survey](#2-p0--package-survey)
3. [P1 — API extraction](#3-p1--api-extraction)
4. [The LOGIN call-flow playbook](#4-the-login-call-flow-playbook-centerpiece)
5. [The go-native / IDA-vs-Frida gate](#5-the-go-native--ida-vs-frida-gate)
6. [Quick native triage (pre-IDA)](#6-quick-native-triage-pre-ida)

Siblings: `ecapture-capture.md` (P2 traffic capture) · `ida-workflow.md` (native static) ·
`crypto-id.md` (algorithm ID) · `signing-replay.md` (request reconstruction).

---

## 1. P0 — Decode the package

Run the wrapper; do not hand-drive jadx:

```bash
scripts/decode_apk.sh <app.apk|app.xapk> --out out/
```

What it does and **why it does it that way**:

- **jadx first-pass WITHOUT `--deobf`.** Runtime-faithful class names are non-negotiable here.
  `--deobf` invents readable aliases (`p000.LoginService`) that **do not exist at runtime**, so any
  later Frida `Java.use()` / JNI `FindClass` / unidbg load keyed off those names silently fails.
  Keeping the real obfuscated names (`c.a.b.d`) means the names you grep in source are the exact
  names you hook. Only re-run with `--deobf` into a *separate* dir if a human needs to read a
  tangled class — never as the primary tree.
- **apktool only for resources/manifest.** jadx decompiles code but mangles some resource edge
  cases; apktool gives a faithful `AndroidManifest.xml`, `res/`, and `assets/`. Use jadx for Java,
  apktool for manifest/resources. Do not decompile smali by hand unless a class fails in jadx.
- **XAPK / split handling.** XAPK is a ZIP of `base.apk` + `split_config.*.apk`. The script unzips,
  decompiles `base.apk` (the code carrier) and merges DEX from splits. If an outer APK yields very
  few Java files but contains `base.apk` inside, it is a thin wrapper — the script re-targets
  `base.apk` automatically. Watch for `split_config.arm64_v8a.apk`: that is where the `.so` files
  live, and it is your native-code inventory.

**`decode_summary.json`** is the machine-readable index of the decode. Read it first every session —
it lists: output paths (`sources/`, `resources/`), package name, `minSdk`/`targetSdk`, dex count,
`.so` files with ABIs, whether obfuscation was detected, and file/class counts. It saves you from
re-globbing the tree and tells you immediately whether native code is in play.

---

## 2. P0 — Package survey

Read `resources/AndroidManifest.xml` first — it is the ground truth of entry points and is never
obfuscated (component names must resolve at runtime):

```bash
grep -nE 'uses-permission' resources/AndroidManifest.xml         # INTERNET, network state, etc.
grep -nE 'android:name=".*Activity"' resources/AndroidManifest.xml
grep -nE 'android:exported="true"' resources/AndroidManifest.xml  # attack surface
grep -B2 -A6 'android.intent.action.MAIN' resources/AndroidManifest.xml  # launcher activity
grep -n 'android:name' resources/AndroidManifest.xml | grep -i application  # Application class
```

Why: the **launcher activity** and **Application subclass** are your two guaranteed real-named
anchors into an obfuscated tree. `Application.onCreate()` almost always builds the Retrofit/OkHttp
singleton, sets the base URL, and initializes DI — read it before anything else.

**Detect the architecture** (tells you where network calls hide):

```bash
grep -rl 'ViewModel\|LiveData\|StateFlow' sources/   # MVVM
grep -rl 'Presenter' sources/                        # MVP
ls sources/<pkg>/ | grep -iE 'domain|data|presentation'  # Clean Architecture
```

MVVM → click handler calls a ViewModel → Repository → API interface. MVP → Presenter. Clean → the
API interface lives under `data/`. Knowing the pattern turns "grep the whole app" into "grep three
classes".

**Find native code** — this decides whether P0 escalates to native work at all:

```bash
grep -rn 'System.loadLibrary\|System.load(' sources/     # -> the .so base name
grep -rn 'native ' sources/ | grep -v '//'               # JNI method declarations
```

`System.loadLibrary("foo")` ⇒ `lib/<abi>/libfoo.so`. A Java method that is declared `native` and has
no body is a JNI wrapper — the real logic is in that `.so`. Note these now; §5 decides how to attack
them.

---

## 3. P1 — API extraction

Run the extractor for a broad sweep, then read call sites by hand:

```bash
scripts/api_extract.py sources/ --out out/
```

It emits **`api_endpoints.json`** (method, path, params, body/response types, source file:line,
detected base URL) and **`secrets.json`** (candidate keys, tokens, sign constants with locations).
Treat both as leads to verify in source, not as final truth.

The concrete grep pattern sets it runs, **by library** — run any of these by hand to dig:

**Retrofit** (most common; annotations survive R8 because they are library-public):
```bash
grep -rnE '@(GET|POST|PUT|DELETE|PATCH|HEAD)\(' sources/
grep -rnE '@(Query|QueryMap|Path|Body|Field|FieldMap|Part|Header|HeaderMap|Headers)\b' sources/
grep -rn '\.baseUrl(' sources/
```
Capture per endpoint: method, path, path/query params, body type, response type, static headers.

**OkHttp** (direct use or Retrofit's transport; where headers/signatures get injected):
```bash
grep -rnE 'Request\.Builder|\.url\(|\.addHeader\(|\.post\(|\.put\(' sources/
grep -rnE 'HttpUrl|\.addQueryParameter|\.addPathSegment' sources/
grep -rnE 'Interceptor|addInterceptor|addNetworkInterceptor|intercept\(' sources/
```

**Volley**: `grep -rnE 'StringRequest|JsonObjectRequest|newRequestQueue|getHeaders|getParams' sources/`
**HttpURLConnection (legacy)**: `grep -rnE 'openConnection|setRequestMethod|setRequestProperty' sources/`
**WebView / JS bridge**: `grep -rnE 'loadUrl|evaluateJavascript|addJavascriptInterface|@JavascriptInterface' sources/`

**Hardcoded URLs, base-URL constants, secrets** (string literals are never obfuscated — your best
anchors):
```bash
grep -rnE '"https?://[^"]*"' sources/
grep -rniE 'BASE_URL|API_URL|SERVER_URL|ENDPOINT|API_BASE' sources/
grep -rniE 'api[_-]?key|api[_-]?secret|client[_-]?secret|access[_-]?token|bearer|sign|hmac|secret' sources/
```

Reading the JSON: cross-check every `api_endpoints.json` path against the base URL from
`Application.onCreate()` to build full URLs; treat `secrets.json` hits as *candidates* — a constant
named `SIGN_KEY` may be a red herring or only half the input. Confirm crypto usage with
`crypto-id.md`.

---

## 4. The LOGIN call-flow playbook (centerpiece)

This is **obfuscation-anchored tracing**: R8 renames classes/methods/fields to `a`, `b`, `c` but
leaves string literals, Android framework classes, manifest names, and library-public annotations
intact. Anchor on those survivors and walk the graph by cross-reference. Never try to read
obfuscated code top-down.

**Anchor → walk up the stack. Exact sequence:**

```bash
# 1. Anchor on a stable string the server contract forces to exist.
grep -rn '"auth/login"\|"/login"\|"signin"' sources/
#    -> hit lands in an obfuscated interface, e.g. c/a/b/d.java

# 2. Confirm it is the Retrofit interface: the annotation survived R8.
grep -n '@POST\|@FormUrlEncoded\|@Body' sources/c/a/b/d.java
#    @POST("auth/login") Call<...> e(@Body ... );  <- this IS the login endpoint

# 3. Who calls the interface? -> the repository.
grep -rn 'c.a.b.d' sources/ | grep -v 'c/a/b/d.java'
#    -> c.a.b.f references it: the repository/data source

# 4. Who calls the repository? -> the ViewModel/Presenter.
grep -rn 'c.a.b.f' sources/
#    -> c.a.a.g holds a field of that type: the ViewModel

# 5. Who owns the ViewModel? -> the real-named screen (from the manifest).
grep -rln 'c.a.a.g' sources/ | xargs grep -ln 'Activity\|Fragment'
#    -> LoginActivity / LoginFragment

# 6. Read the click handler to see where inputs originate.
grep -n 'setOnClickListener\|onClick\|binding\.' sources/**/LoginActivity.java
```

Result: `LoginActivity → LoginViewModel(c.a.a.g) → Repository(c.a.b.f) → Retrofit @POST("auth/login")`.

**Why each hop matters:** the string gives you a foothold R8 cannot remove; the annotation proves
the class is the API surface; each `grep for usages` climbs exactly one architectural layer; the
manifest-named Activity is where the *plaintext* username/password enter before any transform. If
DI (Hilt/Dagger) hides the concrete type, jump via bindings:
`grep -rnE '@Provides|@Binds|@Inject' sources/` and match the interface to its provider.

**The interceptor is where auth headers and signatures are injected — check it explicitly.** The
Retrofit interface declares the *shape*; the OkHttp `Interceptor` mutates every outbound request to
add `Authorization`, `X-Sign`, timestamps, device IDs. If your reconstructed request is rejected by
the server but the body looks right, the missing piece is almost always in an interceptor:

```bash
grep -rln 'implements Interceptor\|Interceptor {' sources/
# then read intercept(): look for .addHeader(...), a sign()/hmac() call, or a native method
```

An interceptor calling a `native` method for the signature is your handoff signal to §5 →
`signing-replay.md`. This is also the P3 **code↔traffic alignment** join point: line up the headers
you see the interceptor add against the headers captured live (see `ecapture-capture.md`), confirming
which are static, which are per-request (timestamp/nonce), and which are signed.

---

## 5. The go-native / IDA-vs-Frida gate

Only escalate to native when Java tracing hits a wall: an interceptor or login path calls a `native`
method for signing/encryption, or the final request cannot be reconstructed from Java alone.
Signals that logic has moved into a `.so`:

- A `native`-declared Java method with no body, reached from the sign/login path.
- An empty or trivial Java method right after `System.loadLibrary(...)` — the body is registered
  dynamically from native via `RegisterNatives`.
- `secrets.json` finds a key *name* but no algorithm in Java — the crypto is native.

**Once native is in play, choose IDA vs Frida with a function-survey heuristic. Do not open IDA
blindly.** This "survey" is **not** a bundled script — there is no `scripts/survey_binary`. It is the
IDA-MCP tool **`idapro_survey_binary`** when an IDA MCP is present, or, without an MCP, a manual
heuristic: run `rabin2`/`nm` (below) and read the exported function list yourself. Either way, look at
the function-size distribution:

- **Few, huge functions (a handful > ~10 KB each), sparse imports, encrypted strings** ⇒
  control-flow flattening / OLLVM. Static pseudocode will be an unreadable soup. **Do not waste
  budget on static IDA.** Defer to Frida runtime tracing (`jni_trace.js`) to capture the decrypted
  inputs/outputs at the JNI boundary — see `signing-replay.md`.
- **Many small functions, recognizable boundaries, readable strings, named imports** ⇒ standard
  compiler output. **IDA is productive** — decompile the JNI export to C, trace xrefs to the key
  string, recover the algorithm statically. Proceed with `ida-workflow.md`.

Also send it straight to Frida (not IDA) when: all strings are encrypted (static search finds
nothing), you need runtime *values* (keys, tokens, decrypted body), or you have not yet identified
*which* `.so` handles the logic — trace at the JNI boundary first to pick the target, then decide.

**IDA is the primary native static tool; Ghidra and radare2 are fallbacks only.**

---

## 6. Quick native triage (pre-IDA)

Before committing IDA, spend 60 seconds with `rabin2`/`nm` to identify the target and feed the §5
gate. This is reconnaissance, not analysis:

```bash
rabin2 -I libfoo.so    # arch/bits/ABI, NX, canary, stripped? -> confirms which .so, matches ABI
rabin2 -z libfoo.so    # strings: URLs, log tags, 'sign', 'AES', 'HMAC', JNI clues
rabin2 -i libfoo.so    # imports: presence of crypto/socket libs hints at what it does
rabin2 -E libfoo.so    # exports: Java_* names reveal statically-registered JNI methods
nm -D libfoo.so | grep -E 'Java_|JNI_OnLoad|RegisterNatives'
```

How to read it: `Java_com_example_...` exports mean **static** JNI binding — the export name maps
directly to the Java `native` method, so you already know the target function. No `Java_*` exports
but a `JNI_OnLoad` present ⇒ **dynamic** binding via `RegisterNatives`; the mapping is resolved at
runtime, so Frida is the fast path to find it. Encrypted/absent strings from `-z` plus a stripped
binary is a strong OLLVM tell — combine with the function-size check from §5 and, if obfuscated,
skip IDA for Frida.

Hand off: confirmed target + readable code → `ida-workflow.md`; obfuscated or runtime-only →
`signing-replay.md` (+ `jni_trace.js`); identifying the crypto primitive → `crypto-id.md`.
