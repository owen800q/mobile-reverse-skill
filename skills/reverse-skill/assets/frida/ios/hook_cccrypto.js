/*
 * hook_cccrypto.js — iOS mode (PlayCover): observe the crypto sink.
 *
 * The iOS analog of assets/frida/hook_crypto.js (which hooks javax.crypto on
 * Android). Dumps key / IV / input / output at the primitive boundary so you
 * can read the pre-encryption plaintext and the material a request signature is
 * computed over (Gate A: is app-layer crypto above TLS?).
 *
 *   frida -n <ExecutableName> -l hook_cccrypto.js
 *
 * Backends, in priority order (see references/ios-playcover.md §crypto):
 *  1. CommonCrypto (libcommonCrypto.dylib): CCCrypt / CCCryptorUpdate / CCHmac.
 *     The primary target — most AES/HMAC request signing routes through here.
 *  2. corecrypto (libcorecrypto.dylib): cchmac / ccdigest / ccaes_*. Apple's
 *     CryptoKit is backed by CORECRYPTO, not BoringSSL — hook here to observe
 *     CryptoKit. Caveat: CryptoKit may INLINE small operations, so hooks can
 *     miss them; if so, reverse the app's own wrapper and hook it by address
 *     (reuse assets/templates/frida_runtime_observe.js.tmpl).
 *  3. EVP_* (bundled OpenSSL/BoringSSL): DEMOTED fallback — only apps that ship
 *     their own crypto lib for primitives (uncommon) use these.
 */
'use strict';

var MAX = 0x1000;

function dump(tag, ptrVal, len) {
    if (ptrVal.isNull() || len <= 0) { console.log(tag + ': <empty>'); return; }
    var n = len < MAX ? len : MAX;
    try {
        var bytes = new Uint8Array(ptrVal.readByteArray(n));
        var hex = '', ascii = '';
        for (var i = 0; i < bytes.length; i++) {
            var b = bytes[i];
            hex += ('0' + b.toString(16)).slice(-2);
            ascii += (b >= 0x20 && b < 0x7f) ? String.fromCharCode(b) : '.';
        }
        console.log(tag + ' (' + len + 'B) hex=' + hex);
        console.log(tag + ' (' + len + 'B) str=' + ascii);
    } catch (e) {
        console.log(tag + ': <unreadable: ' + e + '>');
    }
}

// --- CommonCrypto ----------------------------------------------------------
function hookCommonCrypto() {
    // CCCryptorStatus CCCrypt(op, alg, options, key, keyLen, iv,
    //                         dataIn, dataInLen, dataOut, dataOutAvail, dataOutMoved)
    var CCCrypt = Module.findExportByName(null, 'CCCrypt');
    if (CCCrypt) {
        Interceptor.attach(CCCrypt, {
            onEnter: function (a) {
                console.log('\n==== CCCrypt op=' + a[0].toInt32() + ' alg=' + a[1].toInt32() + ' ====');
                dump('  key', a[3], a[4].toInt32());
                dump('  iv ', a[5], 16);
                this.inPtr = a[6]; this.inLen = a[7].toInt32();
                this.outPtr = a[8]; this.outMoved = a[10];
                dump('  in ', this.inPtr, this.inLen);
            },
            onLeave: function () {
                var moved = this.outMoved.isNull() ? 0 : this.outMoved.readU32();
                dump('  out', this.outPtr, moved || this.inLen);
            }
        });
        console.log('[cc] CCCrypt hooked');
    }

    // CCCryptorUpdate(cryptorRef, dataIn, dataInLen, dataOut, dataOutAvail, dataOutMoved)
    var CCUpdate = Module.findExportByName(null, 'CCCryptorUpdate');
    if (CCUpdate) {
        Interceptor.attach(CCUpdate, {
            onEnter: function (a) {
                console.log('\n==== CCCryptorUpdate ====');
                this.outPtr = a[3]; this.outMoved = a[5];
                dump('  in ', a[1], a[2].toInt32());
            },
            onLeave: function () {
                var moved = this.outMoved.isNull() ? 0 : this.outMoved.readU32();
                dump('  out', this.outPtr, moved);
            }
        });
        console.log('[cc] CCCryptorUpdate hooked');
    }

    // void CCHmac(algorithm, key, keyLength, data, dataLength, macOut)
    var CCHmac = Module.findExportByName(null, 'CCHmac');
    if (CCHmac) {
        var MAC_LEN = { 0: 16, 1: 20, 2: 32, 3: 48, 4: 64, 5: 28 }; // MD5,SHA1,256,384,512,224
        Interceptor.attach(CCHmac, {
            onEnter: function (a) {
                this.alg = a[0].toInt32();
                console.log('\n==== CCHmac alg=' + this.alg + ' ====');
                dump('  key ', a[1], a[2].toInt32());
                dump('  data', a[3], a[4].toInt32());
                this.macOut = a[5];
            },
            onLeave: function () {
                dump('  mac ', this.macOut, MAC_LEN[this.alg] || 32);
            }
        });
        console.log('[cc] CCHmac hooked');
    }
}

// --- corecrypto (CryptoKit backend) ----------------------------------------
function hookCorecrypto() {
    // Best-effort: corecrypto exports are versioned and partly private. We hook
    // the stable one-shot HMAC when present. cchmac(di, key_len, key, data_len,
    // data, mac). `di` is a descriptor pointer; we can't cheaply size the mac,
    // so dump a conservative 64 bytes.
    var cchmac = Module.findExportByName(null, 'cchmac');
    if (cchmac) {
        Interceptor.attach(cchmac, {
            onEnter: function (a) {
                console.log('\n==== corecrypto cchmac ====');
                dump('  key ', a[2], a[1].toInt32());
                dump('  data', a[4], a[3].toInt32());
                this.mac = a[5];
            },
            onLeave: function () { dump('  mac ', this.mac, 64); }
        });
        console.log('[cc] corecrypto cchmac hooked (CryptoKit backend)');
    } else {
        console.log('[cc] corecrypto cchmac not exported (CryptoKit may inline; hook the app wrapper by address)');
    }
}

// --- bundled OpenSSL/BoringSSL EVP (demoted) -------------------------------
function hookEVP() {
    var EVP = Module.findExportByName(null, 'EVP_DigestSignUpdate');
    if (EVP) {
        Interceptor.attach(EVP, {
            onEnter: function (a) { console.log('\n==== EVP_DigestSignUpdate ===='); dump('  data', a[1], a[2].toInt32()); }
        });
        console.log('[cc] EVP_DigestSignUpdate hooked (bundled crypto fallback)');
    }
}

(function main() {
    hookCommonCrypto();
    hookCorecrypto();
    hookEVP();
    console.log('[cc] ready. Exercise the signed request to see key/iv/in/out.');
})();
