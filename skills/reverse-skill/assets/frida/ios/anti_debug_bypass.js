/*
 * anti_debug_bypass.js — iOS mode (PlayCover): neutralize anti-debug / env checks.
 *
 * The iOS analog of assets/frida/bypass.js. get-task-allow gets you attach
 * PERMISSION, but it does NOT defeat an app that actively refuses a debugger or
 * refuses to run under PlayCover. Load this EARLY — spawn-gate so it runs before
 * the app's constructors:
 *
 *   frida -f <path/to/.app/Exec> -l anti_debug_bypass.js --no-pause
 *
 * If spawning under PlayCover is unreliable (PlayCover sets up the container /
 * PlayTools env that a bare posix_spawn does not reproduce), fall back to a
 * static NOP-patch of the ptrace/svc call sites + re-sign. See the "anti-debug
 * & spawn-vs-attach" section of references/ios-playcover.md, and escalate to the
 * fable sub-agent if a check still bites.
 *
 * Covers:
 *  - ptrace(PT_DENY_ATTACH) — the classic self-defense.
 *  - sysctl(KERN_PROC ...) P_TRACED probe — clear the traced flag on return.
 *  - dyld image-name scan that detects PlayTools / injected dylibs / frida.
 *  - environment probes that reveal "this is a Mac, not an iPhone".
 */
'use strict';

// --- ptrace(PT_DENY_ATTACH) -> no-op ---------------------------------------
(function () {
    var ptrace = Module.findExportByName(null, 'ptrace');
    if (!ptrace) return;
    Interceptor.attach(ptrace, {
        onEnter: function (args) {
            // request 31 == PT_DENY_ATTACH
            if (args[0].toInt32() === 31) { this.deny = true; }
        },
        onLeave: function (retval) {
            if (this.deny) retval.replace(0);
        }
    });
    console.log('[anti] ptrace(PT_DENY_ATTACH) neutralized');
})();

// Some apps call ptrace via syscall(SYS_ptrace, ...) to dodge the export hook.
(function () {
    var sc = Module.findExportByName(null, 'syscall');
    if (!sc) return;
    Interceptor.attach(sc, {
        onEnter: function (args) {
            // SYS_ptrace == 26; arg1 (request) 31 == PT_DENY_ATTACH
            if (args[0].toInt32() === 26 && args[1].toInt32() === 31) this.deny = true;
        },
        onLeave: function (retval) { if (this.deny) retval.replace(0); }
    });
    console.log('[anti] syscall(SYS_ptrace, PT_DENY_ATTACH) neutralized');
})();

// --- sysctl P_TRACED probe -> clear the flag -------------------------------
(function () {
    var sysctl = Module.findExportByName(null, 'sysctl');
    if (!sysctl) return;
    var P_TRACED = 0x00000800;
    Interceptor.attach(sysctl, {
        onEnter: function (args) { this.oldp = args[2]; },
        onLeave: function () {
            // kinfo_proc.kp_proc.p_flag sits at offset 32 in the returned struct.
            try {
                if (this.oldp && !this.oldp.isNull()) {
                    var flagPtr = this.oldp.add(32);
                    var flags = flagPtr.readU32();
                    if (flags & P_TRACED) flagPtr.writeU32(flags & ~P_TRACED);
                }
            } catch (e) { /* not the proc-info shape; ignore */ }
        }
    });
    console.log('[anti] sysctl P_TRACED flag cleared');
})();

// --- hide PlayTools / frida / injected dylibs from dyld scans ---------------
(function () {
    var HIDE = /playtools|frida|gadget|substrate|cynject|libhooker/i;
    var getName = Module.findExportByName(null, '_dyld_get_image_name');
    if (!getName) return;
    var real = new NativeFunction(getName, 'pointer', ['uint']);
    Interceptor.replace(getName, new NativeCallback(function (i) {
        var namePtr = real(i);
        try {
            var name = namePtr.readUtf8String();
            if (name && HIDE.test(name)) {
                // Redirect to a benign system path so scanners see nothing odd.
                return Memory.allocUtf8String('/usr/lib/libSystem.B.dylib');
            }
        } catch (e) { /* ignore */ }
        return namePtr;
    }, 'pointer', ['uint']));
    console.log('[anti] _dyld_get_image_name filtered (PlayTools/frida hidden)');
})();

// --- spoof "am I on iOS?" environment probes -------------------------------
(function () {
    if (!ObjC.available) return;
    try {
        // NSProcessInfo.isiOSAppOnMac / isMacCatalystApp -> NO
        ['isiOSAppOnMac', 'isMacCatalystApp'].forEach(function (sel) {
            var pi = ObjC.classes.NSProcessInfo;
            if (pi && pi[sel]) {
                Interceptor.attach(pi['- ' + sel].implementation, {
                    onLeave: function (retval) { retval.replace(ptr(0)); }
                });
                console.log('[anti] NSProcessInfo ' + sel + ' -> NO');
            }
        });
    } catch (e) { /* selector shape varies; ignore */ }
})();

console.log('[anti] ready. Load at spawn for early checks (frida -f ... --no-pause).');
