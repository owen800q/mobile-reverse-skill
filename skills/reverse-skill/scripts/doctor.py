#!/usr/bin/env python3
"""Inventory prerequisites without importing third-party code or running tools.

Python 3.9+, standard library only. Device probes require --device SERIAL.
Exit 0: report produced (missing optional capabilities are report data).
Exit 2: invalid arguments. Exit 3: explicitly requested device probe failed.
Presence is not proof of a working tool, license, target, or runtime route.
"""

import argparse
from importlib.machinery import PathFinder
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


TOOLS = ('bash', 'java', 'unzip', 'jadx', 'apktool', 'adb', 'frida',
         'zipalign', 'apksigner', 'ipsw', 'otool', 'lipo', 'codesign')

# Every tuple is one requirement; alternatives within it are OR-ed.
CAPABILITIES = {
    'offline_helpers': ('all', [('python',)], [], 'state-schema.md'),
    'android_static': ('android', [('python',), ('bash',), ('java',),
                                   ('unzip',), ('jadx', 'apktool')],
                       [], 'android-triage.md'),
    'android_asc': ('android', [('asc_checkout',), ('asc_python',),
                                ('asc_version',), ('androguard',)],
                    ['ASC/Androguard compatibility and an actual query'], 'asc.md'),
    'native_ida_headless': ('all', [('python',), ('idapro',)],
                            ['IDA activation, SDK, license and target loading'], 'ida-workflow.md'),
    'android_frida': ('android', [('adb',), ('frida',), ('frida_module',)],
                      ['device access, matching server and target attachment'], 'dbi-detection.md'),
    'android_tls_capture': ('android', [('bash',), ('adb',), ('ecapture_binary',)],
                            ['device root, binary ABI, BTF/kernel support and capture'], 'ecapture-capture.md'),
    'android_native_trace': ('android', [('bash',), ('adb',), ('stackplz_binary',)],
                             ['device root, binary ABI, kernel support and trace'], 'native-tracing.md'),
    'android_repack': ('android', [('bash',), ('java',), ('apktool',),
                                   ('zipalign',), ('apksigner',)],
                       ['signing key, build, alignment and signature verification'], 'android-triage.md'),
    'ios_static': ('ios', [('python',), ('bash',), ('unzip',), ('ipsw', 'otool')],
                   ['IPA encryption state and Mach-O tool compatibility'], 'optional-platforms.md'),
    'ios_playcover': ('ios', [('apple_silicon',), ('frida',), ('frida_module',),
                              ('codesign',), ('lipo',), ('otool',)],
                      ['PlayCover app, decrypted IPA, entitlements and local attachment'], 'ios-playcover.md'),
}


def check(status, detail, path=None):
    result = {'status': status, 'detail': detail}
    if path is not None:
        result['path'] = str(path)
    return result


def executable(name):
    path = shutil.which(name)
    return check('found', 'executable located; not run', path) if path else check('missing', 'not on PATH: ' + name)


def module_location(name):
    # Unlike find_spec('package.submodule'), this never imports a parent package.
    try:
        spec = PathFinder.find_spec(name, sys.path)
    except (ImportError, OSError, ValueError) as exc:
        return check('unverified', 'module discovery failed: ' + type(exc).__name__)
    if spec is None:
        return check('missing', name + ' not found in this Python environment')
    return check('found', 'module located; import and initialization not tested', spec.origin)


def binary_candidate(name, supplied):
    if not supplied:
        return check('unverified', 'device binary not supplied; it may already exist on the device')
    path = Path(supplied).expanduser()
    if path.is_file():
        return check('found', name + ' file found; architecture and execution untested', path.resolve())
    return check('missing', name + ' file does not exist', path)


def host_inventory(args):
    found = {name: executable(name) for name in TOOLS}
    found['python'] = check('found' if sys.version_info >= (3, 9) else 'missing',
                            'requires Python 3.9+; running ' + platform.python_version(), sys.executable)
    found['idapro'] = module_location('idapro')
    found['frida_module'] = module_location('frida')
    apple = platform.system() == 'Darwin' and platform.machine().lower() in ('arm64', 'aarch64')
    found['apple_silicon'] = check('found' if apple else 'unverified',
                                  'Apple-Silicon host' if apple else
                                  'PlayCover needs Apple Silicon; verify host architecture (including Rosetta)')
    asc_main = Path(args.asc_root).expanduser() / 'main.py' if args.asc_root else None
    found['asc_checkout'] = check('found', 'ASC entry point located; not executed', asc_main.resolve()) \
        if asc_main and asc_main.is_file() else check('missing', 'set ASC_ROOT or --asc-root to a checkout containing main.py')
    found['asc_python'] = executable(args.asc_python)
    asc_exe = found['asc_python'].get('path')
    # Virtualenv executables can symlink to the same binary but have different
    # packages. Do not equate environments by resolving those symlinks.
    same_python = asc_exe and os.path.abspath(asc_exe) == os.path.abspath(sys.executable)
    if same_python:
        found['asc_version'] = check('found' if sys.version_info >= (3, 11) else 'missing',
                                     'ASC findrefs requires Python 3.11+')
        found['androguard'] = module_location('androguard')
    else:
        detail = 'not checked in the selected ASC interpreter; run doctor with that interpreter'
        found['asc_version'] = check('unverified', detail)
        found['androguard'] = check('unverified', detail)
    found['ecapture_binary'] = binary_candidate('eCapture', args.ecapture_bin)
    found['stackplz_binary'] = binary_candidate('stackplz', args.stackplz_bin)
    return found


def capability_report(inventory, selected_platform):
    report = {}
    for name, (target, groups, pending, reference) in CAPABILITIES.items():
        if selected_platform != 'all' and target not in ('all', selected_platform):
            continue
        missing, unknown = [], []
        for alternatives in groups:
            states = [inventory[item]['status'] for item in alternatives]
            if 'found' in states:
                continue
            label = ' or '.join(alternatives)
            (unknown if 'unverified' in states else missing).append(label)
        status = 'missing' if missing else 'needs_verification' if unknown or pending else 'available'
        report[name] = {'status': status, 'missing': missing, 'unverified': unknown,
                        'verify_before_use': list(pending), 'reference': 'references/' + reference}
    return report


def device_probe(adb, serial, timeout):
    """Only explicitly selected, bounded, read-only Android commands."""
    report = {'requested': True, 'serial': serial, 'status': 'failed', 'checks': {}}
    if not adb:
        report['error'] = 'adb not on PATH'
        return report
    commands = [('state', ['get-state']), ('abi', ['shell', 'getprop', 'ro.product.cpu.abi']),
                ('kernel', ['shell', 'uname', '-r'])]
    for label, command in commands:
        try:
            result = subprocess.run([adb, '-s', serial] + command, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            report['error'] = label + ': ' + type(exc).__name__
            return report
        output = result.stdout.strip()
        report['checks'][label] = {'exit_code': result.returncode, 'output': output[:512]}
        if result.returncode or not output or (label == 'state' and output != 'device'):
            report['error'] = label + ': device check did not succeed'
            return report
    report['status'] = 'reachable'
    report['limits'] = 'Does not test root, server versions, ABI compatibility, kernel features or app access.'
    return report


def bounded_timeout(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 30:
        raise argparse.ArgumentTypeError('must be finite and greater than 0, at most 30 seconds')
    return number


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--json', action='store_true', help='emit one JSON object, without a trailing status line')
    p.add_argument('--platform', choices=('all', 'android', 'ios'), default='all')
    p.add_argument('--device', metavar='SERIAL', help='explicitly probe this Android device (read-only)')
    p.add_argument('--timeout', type=bounded_timeout, default=5, help='seconds per device command (default: 5)')
    p.add_argument('--asc-root', default=os.environ.get('ASC_ROOT'))
    p.add_argument('--asc-python', default=os.environ.get('ASC_PYTHON') or sys.executable)
    p.add_argument('--ecapture-bin', help='local candidate device binary, never executed')
    p.add_argument('--stackplz-bin', help='local candidate device binary, never executed')
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.device is not None and (not args.device.strip() or args.platform == 'ios'):
        p.error('--device needs a nonempty Android serial and --platform android or all')
    inventory = host_inventory(args)
    device = device_probe(inventory['adb'].get('path'), args.device, args.timeout) \
        if args.device is not None else {'requested': False, 'status': 'not_checked'}
    report = {'schema_version': 1, 'python': sys.executable, 'platform': platform.system(),
              'machine': platform.machine(), 'inventory': inventory,
              'capabilities': capability_report(inventory, args.platform), 'device': device,
              'limits': 'Availability means prerequisites were located, not that a workflow was executed. '
                        'PATH and this interpreter are inspected; MCP services and other environments are not.'}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report['limits'])
        for name, item in report['capabilities'].items():
            print('\n%s: %s' % (name, item['status']))
            for key in ('missing', 'unverified', 'verify_before_use'):
                if item[key]:
                    print('  %s: %s' % (key, '; '.join(item[key])))
            print('  read: ' + item['reference'])
        print('\ndevice: ' + device['status'])
        if device.get('error'):
            print('  ' + device['error'])
    return 3 if device['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
