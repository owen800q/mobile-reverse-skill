/*
 * ssl_dump.js — iOS mode (PlayCover): plaintext-below-TLS dump.
 *
 * The macOS/PlayCover analog of gojue/ecapture: instead of an eBPF uprobe we
 * attach a Frida Interceptor to the TLS record-layer read/write. It reads the
 * buffer the app itself handles — after decryption / before encryption — so
 * there is no proxy, no CA, and cert-pinning is irrelevant (there is no pin to
 * fail). Output is a canonical hexdump framed with "Write Data" / "Read Data"
 * markers so `scripts/ecapture_parse.py` can reassemble the HTTP requests
 * (same format ecapture text mode emits).
 *
 *   frida -n <ExecutableName> -l ssl_dump.js         # attach
 *   frida -f <path/to/.app/Exec> -l ssl_dump.js --no-pause   # spawn-gate
 *
 * Reality checks (see references/ios-playcover.md):
 *  - Native & React Native apps use the SYSTEM libboringssl.dylib (reached via
 *    Network.framework/CFNetwork), which lives in the dyld shared cache. We
 *    resolve SSL_read/SSL_write at runtime by scanning loaded modules — never a
 *    hardcoded path or an on-disk nm.
 *  - Flutter statically links its OWN, usually STRIPPED, BoringSSL — the named
 *    exports are absent. This script will report that it found nothing; fall
 *    back to a byte-pattern scan for ssl_read/ssl_write, or reFlutter. See the
 *    reference and the "consult the fable sub-agent" escalation.
 *  - HTTP/3 / QUIC bypasses the SSL_read/SSL_write record layer entirely, so a
 *    connection negotiated as h3 produces NO output here. Force TLS-over-TCP
 *    (disable h3 / block UDP 443) or accept the gap.
 *  - SSL_read fills its buffer on RETURN: we save the pointer in onEnter and
 *    read `retval` bytes in onLeave. SSL_write's plaintext is already present in
 *    onEnter. Getting this wrong is the #1 reason these hooks "run" but print
 *    nothing.
 */
'use strict';

var MAX_DUMP = 0x4000; // cap per-buffer hexdump so huge bodies stay readable

// --- resolve SSL_read / SSL_write across loaded modules --------------------
// Try the common module names first, then any module exporting the symbol.
var PREFERRED = ['libboringssl.dylib', 'libnetwork.dylib', 'libsystem_network.dylib'];

function resolve(sym) {
    // 1) preferred modules
    for (var i = 0; i < PREFERRED.length; i++) {
        try {
            var p = Module.findExportByName(PREFERRED[i], sym);
            if (p) return { addr: p, mod: PREFERRED[i] };
        } catch (e) { /* module not loaded */ }
    }
    // 2) global search (covers the dyld shared cache and app-bundled copies)
    try {
        var g = Module.findExportByName(null, sym);
        if (g) {
            var owner = Process.findModuleByAddress(g);
            return { addr: g, mod: owner ? owner.name : '??' };
        }
    } catch (e) { /* ignore */ }
    // 3) explicit per-module enumeration as a last resort
    var found = null;
    Process.enumerateModules().forEach(function (m) {
        if (found) return;
        try {
            var a = Module.findExportByName(m.name, sym);
            if (a) found = { addr: a, mod: m.name };
        } catch (e) { /* ignore */ }
    });
    return found;
}

function frame(direction, buf, len) {
    if (len <= 0) return;
    var n = len < MAX_DUMP ? len : MAX_DUMP;
    // marker line recognised by ecapture_parse.py DIRECTION_RE
    console.log('\n' + direction + ' Data  len=' + len + (n < len ? ' (truncated to ' + n + ')' : ''));
    try {
        console.log(hexdump(buf, { offset: 0, length: n, header: false, ansi: false }));
    } catch (e) {
        console.log('  <unreadable buffer: ' + e + '>');
    }
}

function hookWrite(info) {
    // int SSL_write(SSL *ssl, const void *buf, int num)
    Interceptor.attach(info.addr, {
        onEnter: function (args) {
            var len = args[2].toInt32();
            frame('Write', args[1], len); // plaintext already in the buffer
        }
    });
}

function hookRead(info) {
    // int SSL_read(SSL *ssl, void *buf, int num) -> bytes read (retval)
    Interceptor.attach(info.addr, {
        onEnter: function (args) { this.buf = args[1]; },
        onLeave: function (retval) {
            var n = retval.toInt32();
            if (n > 0 && this.buf) frame('Read', this.buf, n); // filled on return
        }
    });
}

// --- SecureTransport fallback (DEPRECATED since iOS 13 / macOS 10.15) -------
// Almost nothing modern uses this; kept as a tiny best-effort net.
function hookSecureTransport() {
    var names = ['SSLWrite', 'SSLRead'];
    var any = false;
    names.forEach(function (sym) {
        var info = resolve(sym);
        if (!info) return;
        any = true;
        if (sym === 'SSLWrite') {
            // OSStatus SSLWrite(ctx, const void *data, size_t len, size_t *processed)
            Interceptor.attach(info.addr, {
                onEnter: function (args) { frame('Write', args[1], args[2].toInt32()); }
            });
        } else {
            // OSStatus SSLRead(ctx, void *data, size_t len, size_t *processed)
            Interceptor.attach(info.addr, {
                onEnter: function (args) { this.buf = args[1]; this.pProc = args[3]; },
                onLeave: function () {
                    if (this.buf && !this.pProc.isNull()) {
                        var got = this.pProc.readULong();
                        if (got > 0) frame('Read', this.buf, got);
                    }
                }
            });
        }
    });
    if (any) console.log('[ssl_dump] SecureTransport (deprecated) hooks installed as fallback');
}

// --- main ------------------------------------------------------------------
(function main() {
    var w = resolve('SSL_write');
    var r = resolve('SSL_read');
    if (w) { hookWrite(w); console.log('[ssl_dump] SSL_write @ ' + w.addr + ' in ' + w.mod); }
    if (r) { hookRead(r); console.log('[ssl_dump] SSL_read  @ ' + r.addr + ' in ' + r.mod); }

    if (!w && !r) {
        console.log('[ssl_dump] SSL_read/SSL_write NOT found via exported symbols.');
        console.log('[ssl_dump] Likely a statically-linked, stripped BoringSSL (Flutter/gRPC).');
        console.log('[ssl_dump] -> byte-pattern-scan ssl_read/ssl_write, or use reFlutter;');
        console.log('[ssl_dump] -> see references/ios-playcover.md (engines & transports).');
        hookSecureTransport();
    }
    console.log('[ssl_dump] ready. Exercise the app; pipe stdout to ecapture_parse.py.');
})();
