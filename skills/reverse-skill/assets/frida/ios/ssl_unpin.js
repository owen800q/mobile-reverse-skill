/*
 * ssl_unpin.js — iOS mode (PlayCover): defeat TLS cert pinning.
 *
 * Only needed for the mitmproxy/system-proxy fallback path. The DEFAULT capture
 * (ssl_dump.js) reads plaintext below TLS and needs no unpinning at all — reach
 * for this only when you deliberately want a terminating proxy (e.g. to edit or
 * replay traffic through Burp/mitmproxy) and the app pins.
 *
 *   frida -n <ExecutableName> -l ssl_unpin.js
 *
 * Covers the two stacks a PlayCover app realistically uses:
 *  - BoringSSL custom verify (system libboringssl, used by URLSession/
 *    Network.framework and by React Native): force the verify callback to
 *    return "OK". This is the modern pinning choke point.
 *  - NSURLSession delegate challenge (App-level pinning in ObjC/Swift): answer
 *    the auth challenge with the server trust, bypassing the app's evaluation.
 *
 * Flutter pins inside its own stripped BoringSSL — this script will not reach
 * it; use reFlutter. See references/ios-playcover.md.
 */
'use strict';

// --- BoringSSL: SSL_VERIFY_NONE + neutered custom verify --------------------
var SSL_VERIFY_NONE = 0;

function patchBoringSSL() {
    // int SSL_get_verify_result(const SSL *ssl) -> X509_V_OK (0)
    var getVerify = Module.findExportByName(null, 'SSL_get_verify_result');
    if (getVerify) {
        Interceptor.replace(getVerify, new NativeCallback(function () {
            return 0; // X509_V_OK
        }, 'long', ['pointer']));
        console.log('[unpin] SSL_get_verify_result -> X509_V_OK');
    }

    // void SSL_set_custom_verify(SSL*, int mode, cb) and the CTX variant.
    // Replace the callback with one that always returns ssl_verify_ok (0).
    ['SSL_set_custom_verify', 'SSL_CTX_set_custom_verify'].forEach(function (name) {
        var fn = Module.findExportByName(null, name);
        if (!fn) return;
        var okCb = new NativeCallback(function () {
            return 0; // ssl_verify_ok
        }, 'int', ['pointer', 'pointer']);
        Interceptor.attach(fn, {
            onEnter: function (args) {
                args[1] = ptr(SSL_VERIFY_NONE);
                args[2] = okCb;
            }
        });
        console.log('[unpin] ' + name + ' -> verify OK');
    });
}

// --- NSURLSession delegate challenge ---------------------------------------
function patchNSURLSession() {
    if (!ObjC.available) return;
    try {
        var resolver = new ApiResolver('objc');
        // Match any class implementing the session-level challenge handler.
        var sel = '- URLSession:didReceiveChallenge:completionHandler:';
        var matches = resolver.enumerateMatches('*[* ' + sel.slice(2) + ']');
        matches.forEach(function (m) {
            Interceptor.attach(m.address, {
                onEnter: function (args) {
                    // args[2]=session, args[3]=challenge, args[4]=completionHandler block
                    this.challenge = new ObjC.Object(args[3]);
                    this.handler = new ObjC.Block(args[4]);
                    this.hijack = true;
                },
                onLeave: function () {
                    if (!this.hijack) return;
                    try {
                        var NSURLCredential = ObjC.classes.NSURLCredential;
                        var trust = this.challenge.protectionSpace().serverTrust();
                        var cred = NSURLCredential.credentialForTrust_(trust);
                        // 1 == NSURLSessionAuthChallengeUseCredential
                        this.handler.implementation(1, cred);
                    } catch (e) { /* not a server-trust challenge; leave it */ }
                }
            });
        });
        if (matches.length) {
            console.log('[unpin] NSURLSession challenge handlers hijacked: ' + matches.length);
        }
    } catch (e) {
        console.log('[unpin] NSURLSession hook skipped: ' + e);
    }
}

(function main() {
    patchBoringSSL();
    patchNSURLSession();
    console.log('[unpin] ready (proxy path only; ssl_dump.js needs none of this)');
})();
