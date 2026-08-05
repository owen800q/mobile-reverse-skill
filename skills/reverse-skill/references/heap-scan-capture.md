# heap-scan-capture.md — read plaintext from the heap instead of breaking the crypto

On-demand reference for the case Gate A sends you to when the cipher is
**unreachable**: business crypto is self-contained in an OLLVM/stripped `.so`, you
cannot find or hook the primitive, and ecapture sees only ciphertext. Don't break
the encryption — **read the plaintext the app already produced**. Request bodies
are plaintext right *before* native encryption; responses are plaintext right
*after* native decryption. Both live in the Java/Hermes heap for a window of time.

Load this when: crypto is above TLS (Gate A blob), the signer is anti-DBI-hardened
(`dbi-detection.md`) so you can't cleanly hook it, and you have **root**. This beat
OLLVM self-contained crypto on a real engagement without touching the algorithm.

Siblings: `ecapture-capture.md` (TLS ground-truth) · `dbi-detection.md` (why hooks
fail here) · `hermes-react-native.md` (where RN keeps params persistently) ·
`native-tracing.md` (eBPF read of the same buffers at the JNI boundary).

## Premise

- **Bodies** are plaintext in the heap between "object built" and "native encrypt".
  This window is short (tens of ms for a native request) — often too fast to freeze.
- **Responses** are plaintext in the heap right after decrypt, for as long as the
  page/store holds them. This is the reliable capture — freeze **during response
  processing**, not during the outgoing request.
- Native (Java-list) responses parse to objects and are discarded within ~1s.
  Hermes/CRN pages persist **much** longer in the RN getData store → the easiest
  capture. Prefer RN pages when the target has them (`hermes-react-native.md`).

## Method (rooted) — SIGSTOP freeze, scan, SIGCONT

Freeze the process to beat GC, scan the `rw-p` regions of `/proc/<pid>/mem`, grep
for known markers, resume. Use a **self-resuming** one-liner so the app always
continues even if the scan errors — a process left in `T` state looks like a hang:

```sh
PID=$(adb shell pidof <pkg>)
adb shell "su -c 'kill -STOP $PID
 grep rw-p /proc/$PID/maps | while read l; do r=\${l%% *}; s=0x\${r%%-*}; e=0x\${r##*-}; sz=\$((e-s));
  [ \$sz -gt 60000 ] && [ \$sz -lt 60000000 ] &&
   dd if=/proc/$PID/mem bs=4096 skip=\$((s/4096)) count=\$((sz/4096)) 2>/dev/null |
   strings -n 20 | grep -aE \"<markers>\"; done > /data/local/tmp/hits.txt
 kill -CONT $PID'"
```

- **`<markers>`**: distinctive field names / enum strings from the response you
  want — e.g. `hotelName|roomList|"queryType"|traceKey`. Pick tokens that are rare
  outside your JSON so the hit file stays small.
- **Region size filter** (`60000 < sz < 60000000`): skips tiny mappings and the
  huge guarded regions, keeping the scan to the arenas that actually hold heap
  objects. Widen if you miss the object.
- **Timing**: trigger the freeze *while the result is on screen*. For a list result
  you have ~1s after the rows render; for an RN page, seconds to minutes.

## Extracting the WHOLE object (UTF-8 trap)

`strings` is ASCII: Chinese / emoji bytes in a body truncate the match **mid-value**,
so `hits.txt` gives you a fragment, not the full JSON. When you need the complete
object, do the extraction **host-side**, UTF-8-aware:

1. Find the region containing the marker (from the maps line), `cp` that region's
   bytes to a file on-device, `adb pull` it.
   ```sh
   adb shell "su -c 'dd if=/proc/$PID/mem bs=4096 skip=\$((START/4096)) count=\$((SZ/4096)) of=/data/local/tmp/region.bin 2>/dev/null'"
   adb pull /data/local/tmp/region.bin .
   ```
2. On the host, locate the marker offset and run a **balanced-brace scan** (count
   `{`/`}` over the UTF-8-decoded bytes from the object's opening brace) to carve
   out the exact object. Android's toybox `grep` has **no `-P`** (PCRE), so lazy
   quantifiers and non-greedy grabs fail on-device — never try to carve the object
   with an on-device regex. Do it in Python.

## Gotchas (all hit for real)

- **Freeze misses transient request bodies.** Built→encrypted in tens of ms; a
  hand-timed SIGSTOP almost never lands in that window. To get a *request*: (a)
  capture the persisted RN getData params (`hermes-react-native.md`), or (b)
  reconstruct the body from the JS bundle and only use the heap to *confirm* a
  field — don't rely on freezing to catch it live.
- **Use FUTURE dates.** Past-dated check-in/search params return "no-rate"/empty
  results, so there's no interesting plaintext to find. Drive the app to a query
  that returns real rows before freezing.
- **Restart the app between attempts** if you hooked/attached anything first — a
  hardened target may have already killed instrumentation and be in a degraded
  state (`dbi-detection.md`).
- **Always confirm SIGCONT.** After the scan, `adb shell "su -c 'cat /proc/$PID/stat'"`
  — field 3 should not be `T`. A wrapped self-resuming command avoids this, but
  verify when iterating by hand.

## Why this beats hooking on hardened targets

The process runs untouched — no ptrace attach, no injected agent, no code-cache
divergence — so the app's anti-Frida / anti-ptrace defenses (`dbi-detection.md`)
never fire. You pay nothing in stealth and read exactly the plaintext the app
decrypted for its own use. It is the capture of last resort when the cipher is
self-contained and unhookable, and the first resort when the app is aggressively
anti-DBI. Feed the recovered object into P3 alignment (field map) and P5 replay
(`signing-replay.md`); reconstruct the request builder separately.
