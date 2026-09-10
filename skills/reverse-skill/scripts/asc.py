#!/usr/bin/env python3
"""Run ASC's focused APK queries in a subprocess and retain session evidence.

Example:
  asc.py --asc-root /tools/ASC --out re_out/asc/login findrefs app.apk string auth/login
  asc.py --out re_out/asc/api getclass app.apk 'Lcom/example/Api;'

ASC_ROOT and ASC_PYTHON select the checkout and its Python environment. This
helper neither installs dependencies nor imports ASC into the agent process.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def descriptor(value):
    if value.startswith('L') and value.endswith(';'):
        return value
    return 'L' + value.replace('.', '/') + ';'


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--asc-root', default=os.environ.get('ASC_ROOT'), help='ASC checkout containing main.py')
    p.add_argument('--python', default=os.environ.get('ASC_PYTHON', sys.executable), help='Python executable with ASC dependencies')
    p.add_argument('--out', required=True, help='new per-query directory; existing directories are never overwritten')
    p.add_argument('--threads', type=positive_int, default=8)
    sub = p.add_subparsers(dest='command', required=True)
    get = sub.add_parser('getclass', help='decompile one class with Androguard DAD')
    get.add_argument('apk', type=Path)
    get.add_argument('query', help='original dotted class name or quoted DEX descriptor')
    find = sub.add_parser('findrefs', help='search references across DEX entries in one APK')
    find.add_argument('apk', type=Path)
    find.add_argument('kind', choices=('string', 'type', 'method', 'field'))
    find.add_argument('query', nargs='?', help='ASC regex pattern; optional for class-only method/field queries')
    find.add_argument('--class', dest='class_name')
    find.add_argument('--fuzzy-class', action='store_true')
    return p


def build_command(args, python, main, output):
    cmd = [python, str(main), args.command, str(args.apk), '--threads', str(args.threads)]
    if args.command == 'getclass':
        cmd.append(descriptor(args.query))
    else:
        cmd.append(args.kind)
        if args.query is not None:
            cmd.append(args.query)
        if args.class_name:
            name = args.class_name if args.fuzzy_class else descriptor(args.class_name)
            cmd.extend(['--class', name])
        if args.fuzzy_class:
            cmd.append('--fuzzy-class')
    return cmd + ['-o', str(output)]


def run(args):
    if not args.asc_root:
        raise ValueError('set ASC_ROOT or --asc-root to an MG1937/ASC checkout; see references/asc.md')
    root = Path(args.asc_root).expanduser().resolve()
    main = root / 'main.py'
    if not main.is_file():
        raise ValueError('ASC main.py not found: ' + str(main))
    python = shutil.which(args.python)
    if python is None:
        raise ValueError('Python executable not found: ' + args.python)
    # Resolve relative executables before changing the child's working directory.
    python = str(Path(python).absolute())
    args.apk = args.apk.expanduser().resolve()
    if args.apk.suffix.lower() != '.apk':
        raise ValueError('ASC takes one APK; extract XAPK/APKS/APKM members or convert AAB first (references/asc.md)')
    with zipfile.ZipFile(args.apk) as apk:
        dex_entries = [n for n in apk.namelist() if '/' not in n and n.endswith('.dex')]
    if not dex_entries:
        raise ValueError('APK has no top-level DEX entries; inspect its splits, wrapper, or packer')
    if args.command == 'findrefs':
        if args.kind in ('string', 'type') and (not args.query or args.class_name or args.fuzzy_class):
            raise ValueError('string/type queries need a nonempty pattern and do not take --class/--fuzzy-class')
        if args.kind in ('method', 'field') and not (args.query or args.class_name):
            raise ValueError('method/field queries need a name pattern or --class')
        if args.fuzzy_class and not args.class_name:
            raise ValueError('--fuzzy-class needs --class')
    elif not args.query:
        raise ValueError('class name must be nonempty')

    out = Path(args.out).expanduser().resolve()
    input_hash = sha256(args.apk)
    out.mkdir(parents=True, exist_ok=False)
    output = out / ('Class.java' if args.command == 'getclass' else 'refs.txt')
    cmd = build_command(args, python, main, output)
    version = subprocess.run([python, '-c', 'import sys; print(sys.version)'], capture_output=True, text=True)
    revision = None
    try:
        git = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        if git.returncode == 0:
            revision = git.stdout.strip()
    except OSError:
        pass
    record = {
        'tool': 'ASC', 'asc_root': str(root), 'asc_revision': revision,
        'python_version': version.stdout.strip(),
        'asc_main_sha256': sha256(main), 'input': str(args.apk), 'input_sha256': input_hash,
        'dex_entries': dex_entries, 'command': cmd, 'cwd': str(root),
        'coverage': 'selected_class' if args.command == 'getclass' else 'code_references_in_one_apk',
        'output': str(output), 'stdout': str(out / 'stdout.txt'), 'stderr': str(out / 'stderr.txt'),
        'status': 'running',
    }
    summary = out / 'asc_summary.json'
    summary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    started = time.monotonic()
    with (out / 'stdout.txt').open('wb') as stdout, (out / 'stderr.txt').open('wb') as stderr:
        try:
            result = subprocess.run(cmd, cwd=str(root), stdout=stdout, stderr=stderr)
            rc = result.returncode
        except OSError as exc:
            stderr.write((str(exc) + '\n').encode('utf-8'))
            rc = 127
    data = output.read_text(encoding='utf-8', errors='replace') if output.is_file() else None
    failed = rc != 0 or data is None
    if args.command == 'getclass' and (not data or not data.strip() or data.lstrip().startswith('Error:')):
        failed = True  # Upstream can return an error string with exit status zero.
    changed = sha256(args.apk) != input_hash
    failed = failed or changed
    status = 'failed' if failed else ('no_matches' if not data.strip() else 'ok')
    record.update(status=status, exit_status=rc, input_unchanged=not changed,
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  output_sha256=sha256(output) if output.is_file() else None)
    summary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    print('ASC {}: {}'.format(status, summary), file=sys.stderr)
    # Keep the upstream exit status in the record; wrapper failures use 1.
    return (rc if 0 < rc < 126 else 1) if failed else 0


def main():
    args = parser().parse_args()
    try:
        return run(args)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print('asc.py: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
