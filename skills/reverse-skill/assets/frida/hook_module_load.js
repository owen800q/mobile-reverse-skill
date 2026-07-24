/*
 * hook_module_load.js — reliable "run my callback the moment libX.so is loaded".
 *
 * The classic Android native-hooking bug is timing: you attach, but the target
 * .so (often a packed/decrypted signing lib) isn't mapped yet, so
 * Module.getExportByName throws or your Interceptor never fires. Hooking
 * .init_array / JNI_OnLoad blindly is fragile — anti-debug constructors run
 * there too. Instead we hook the loader (android_dlopen_ext / dlopen) and fire
 * on the *return*, after the module's constructors have run, deduped by base.
 *
 * Usage: edit TARGETS + onLoaded(), then:
 *   frida -U -f com.example.aa -l hook_module_load.js
 * (see references/ida-workflow.md and rev-frida doctrine for why this shape.)
 */
'use strict';

// Substring match against the loaded path, e.g. "libsec.so". Empty => all.
var TARGETS = ['libsec.so'];

// Your per-module work. `mod` is a Frida Module. Install your Interceptors here.
function onLoaded(mod) {
    console.log('[+] loaded ' + mod.name + ' @ ' + mod.base + ' size=' + mod.size);
    // Example: resolve and hook the signer once it's really mapped.
    // var sign = mod.findExportByName('Java_com_example_aa_Native_sign');
    // if (sign) Interceptor.attach(sign, {
    //     onEnter: function (a) { this.env = a[0]; console.log('sign() called'); },
    //     onLeave: function (r) { /* dump result */ }
    // });
}

var seen = {};
function matches(path) {
    if (!path) return false;
    if (TARGETS.length === 0) return true;
    for (var i = 0; i < TARGETS.length; i++) {
        if (path.indexOf(TARGETS[i]) !== -1) return true;
    }
    return false;
}
function fire(path) {
    var name = path.substring(path.lastIndexOf('/') + 1);
    var mod = Process.findModuleByName(name);
    if (!mod) { try { mod = Process.getModuleByName(name); } catch (e) { return; } }
    if (!mod || seen[mod.base]) return;
    seen[mod.base] = true;
    try { onLoaded(mod); } catch (e) { console.log('[!] onLoaded error: ' + e); }
}

function hook(sym) {
    var p = Module.findExportByName(null, sym);
    if (!p) return false;
    Interceptor.attach(p, {
        onEnter: function (args) {
            // android_dlopen_ext(filename, flags, extinfo); dlopen(filename, flags)
            try { this.path = args[0].readCString(); } catch (e) { this.path = null; }
        },
        onLeave: function () {
            if (this.path && matches(this.path)) fire(this.path);
        }
    });
    console.log('[*] hooked ' + sym);
    return true;
}

// Prefer android_dlopen_ext (used by System.loadLibrary on modern Android),
// fall back to dlopen. Also sweep already-mapped modules in case we're late.
var any = hook('android_dlopen_ext');
any = hook('dlopen') || any;
if (!any) console.log('[!] no dlopen symbol found to hook');

Process.enumerateModules().forEach(function (m) {
    if (matches(m.path || m.name) && !seen[m.base]) { seen[m.base] = true;
        try { onLoaded(m); } catch (e) {} }
});
