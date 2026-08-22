/*
 * socket_dump.js — iOS mode (PlayCover): capture non-HTTP / raw transports.
 *
 * Reach for this only when ssl_dump.js sees nothing because the app does NOT go
 * through the TLS record layer you can hook — a custom binary protocol over a
 * raw socket, or a raw NWConnection. Output is framed with "Write Data" /
 * "Read Data" markers + hexdump, so scripts/ecapture_parse.py can still ingest
 * it (it just won't parse non-HTTP payloads into requests — you read the bytes).
 *
 *   frida -n <ExecutableName> -l socket_dump.js
 *
 * Layering (see references/ios-playcover.md, engines & transports):
 *  - nw_connection_send carries PLAINTEXT application data for a raw NWConnection
 *    (TLS, if any, sits below in the nw protocol stack). Its payload arg is a
 *    `dispatch_data_t`, NOT a pointer+len — extract via dispatch_data_apply.
 *  - nw_connection_receive delivers data into a COMPLETION BLOCK, not a return
 *    value. Capturing it means wrapping that block, which is genuinely awkward
 *    in Frida; we log the call but flag the payload as block-delivered. If you
 *    need received bytes, prefer ssl_dump.js (if TLS) or a static read.
 *  - BSD send/recv/write/read catch true raw-socket / old-CFStream apps. They do
 *    NOT usefully surface NSURLSession / Network.framework traffic — for those
 *    use ssl_dump.js. Hooking write/read is noisy (files, pipes), so we filter
 *    to socket fds.
 *
 * If the framing is app-encrypted, pair this with hook_cccrypto.js to recover
 * the plaintext (Gate A generalized: crypto/framing above the socket).
 */
'use strict';

var MAX = 0x2000;

function frameBuf(direction, buf, len) {
    if (len <= 0 || buf.isNull()) return;
    var n = len < MAX ? len : MAX;
    console.log('\n' + direction + ' Data  len=' + len);
    try { console.log(hexdump(buf, { length: n, header: false, ansi: false })); }
    catch (e) { console.log('  <unreadable: ' + e + '>'); }
}

// --- dispatch_data_t extraction --------------------------------------------
// dispatch_data_apply(dispatch_data_t, block(region, offset, buffer, size)->bool)
function dumpDispatchData(direction, dd) {
    if (dd.isNull()) return;
    var apply = Module.findExportByName(null, 'dispatch_data_apply');
    if (!apply) { console.log('[sock] dispatch_data_apply unavailable'); return; }
    var applyFn = new NativeFunction(apply, 'bool', ['pointer', 'pointer']);
    var cb = new ObjC.Block({
        retType: 'bool',
        argTypes: ['pointer', 'pointer', 'pointer', 'pointer'],
        implementation: function (region, offset, buffer, size) {
            frameBuf(direction, buffer, size.toInt32 ? size.toInt32() : parseInt(size));
            return true; // continue iterating regions
        }
    });
    try { applyFn(dd, cb); }
    catch (e) { console.log('[sock] dispatch_data_apply failed: ' + e); }
}

// --- Network.framework -----------------------------------------------------
function hookNetworkFramework() {
    var send = Module.findExportByName(null, 'nw_connection_send');
    if (send) {
        Interceptor.attach(send, {
            // nw_connection_send(conn, content /*dispatch_data_t*/, context, is_complete, completion)
            onEnter: function (args) {
                if (ObjC.available) dumpDispatchData('Write', args[1]);
                else console.log('[sock] nw_connection_send (ObjC unavailable, cannot walk dispatch_data)');
            }
        });
        console.log('[sock] nw_connection_send hooked (dispatch_data_t)');
    }
    var recv = Module.findExportByName(null, 'nw_connection_receive');
    if (recv) {
        Interceptor.attach(recv, {
            onEnter: function () {
                console.log('\n[sock] nw_connection_receive called -> data is delivered into the');
                console.log('       completion BLOCK (not captured here). Use ssl_dump.js if TLS.');
            }
        });
        console.log('[sock] nw_connection_receive hooked (call-only; payload is block-delivered)');
    }
}

// --- BSD sockets (raw-socket / old CFStream apps only) ----------------------
function isSocketFd(fd) {
    // Cheap heuristic: getsockopt(SO_TYPE) succeeds only on sockets.
    try {
        var getsockopt = Module.findExportByName(null, 'getsockopt');
        if (!getsockopt) return true; // can't tell; don't over-filter
        var fn = new NativeFunction(getsockopt, 'int', ['int', 'int', 'int', 'pointer', 'pointer']);
        var optval = Memory.alloc(4);
        var optlen = Memory.alloc(4); optlen.writeU32(4);
        // SOL_SOCKET=0xffff, SO_TYPE=0x1008 on Darwin
        return fn(fd, 0xffff, 0x1008, optval, optlen) === 0;
    } catch (e) { return true; }
}

function hookBSD() {
    var pairs = [
        ['send', 'Write', 1, 2],
        ['write', 'Write', 1, 2],
        ['recv', 'Read', 1, 2],
        ['read', 'Read', 1, 2]
    ];
    pairs.forEach(function (p) {
        var fn = Module.findExportByName(null, p[0]);
        if (!fn) return;
        var name = p[0], dir = p[1], bufIdx = p[2], lenIdx = p[3];
        Interceptor.attach(fn, {
            onEnter: function (args) {
                this.fd = args[0].toInt32();
                this.buf = args[bufIdx];
                this.len = args[lenIdx].toInt32();
                this.isSock = isSocketFd(this.fd);
                if (this.isSock && (name === 'send' || name === 'write')) {
                    frameBuf(dir, this.buf, this.len); // data present on entry
                }
            },
            onLeave: function (retval) {
                if (this.isSock && (name === 'recv' || name === 'read')) {
                    var n = retval.toInt32();
                    if (n > 0) frameBuf(dir, this.buf, n); // filled on return
                }
            }
        });
        console.log('[sock] BSD ' + name + ' hooked (socket fds only)');
    });
}

(function main() {
    hookNetworkFramework();
    hookBSD();
    console.log('[sock] ready. For app-encrypted framing, also load hook_cccrypto.js.');
})();
