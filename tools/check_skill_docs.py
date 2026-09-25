#!/usr/bin/env python3
"""Check curated skill links, Python command flags and entry-point size offline.

Never execute documentation, import helper modules, or scan the crawled KB.
CLI checks cover literal long options in shell fences, not arbitrary shell
semantics, argument values, subcommand ordering or external-tool interfaces.
"""

import argparse
import ast
import json
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import unquote, urlsplit


MAX_SKILL_BYTES = 26000
MAX_SKILL_LINES = 400
LINK = re.compile(r'\[[^\]\n]*\]\(([^\s)]+)\)')
RESOURCE = re.compile(r'(?<![\w/])(?:references|scripts|assets)/[\w./-]+\.(?:md|py|sh|js|tmpl)\b')
SCRIPT_TOKEN = re.compile(r'(?:^|/)scripts/([\w.-]+\.py)$')
LONG_OPTION = re.compile(r'^--[a-zA-Z][\w-]*(?:=.*)?$')


def sections(text):
    """Yield (line, text, fence-language); None means prose."""
    fence, language = None, None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if marker:
            mark, rest = marker.groups()
            if fence is None:
                fence, language = mark, rest.strip().lower()
            elif mark[0] == fence[0] and len(mark) >= len(fence) and not rest.strip():
                fence, language = None, None
            continue
        yield number, line, language if fence else None


def anchors(text):
    counts, result = {}, set()
    for _, line, language in sections(text):
        if language is not None:
            continue
        match = re.match(r'^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?$', line)
        if not match:
            continue
        title = re.sub(r'<[^>]*>', '', match.group(1)).lower()
        title = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', title)
        slug = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        count = counts.get(slug, 0)
        result.add(slug + ('-' + str(count) if count else ''))
        counts[slug] = count + 1
    return result


def python_options(path):
    """Read argparse declarations without importing or running the helper."""
    options = {'--help': False}
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != 'add_argument':
            continue
        settings = {kw.arg: kw.value.value for kw in node.keywords if isinstance(kw.value, ast.Constant)}
        takes_value = settings.get('action') not in ('store_true', 'store_false', 'count', 'help', 'version', 'store_const', 'append_const')
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith('--'):
                options[arg.value] = takes_value
    return options


def shell_commands(text):
    pending, start = '', 0
    for number, line, language in sections(text):
        if language not in ('bash', 'sh', 'shell', 'console', ''):
            pending = ''
            continue
        if not pending:
            start = number
        pending += line.rstrip().removesuffix('\\')
        if line.rstrip().endswith('\\'):
            pending += ' '
            continue
        if pending.strip() and not pending.lstrip().startswith('#'):
            yield start, pending
        pending = ''


def check_document(path, root, skill, option_cache):
    errors = []
    text = path.read_text(encoding='utf-8')

    def fail(number, message):
        errors.append('%s:%d: %s' % (path.relative_to(root), number, message))

    for number, line, language in sections(text):
        if language is None:
            prose = re.sub(r'(`+).*?\1', '', line)
            for match in LINK.finditer(prose):
                url = urlsplit(match.group(1).strip('<>'))
                if url.scheme or url.netloc:
                    continue
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                if not target.is_relative_to(root):
                    fail(number, 'link leaves the repository: ' + match.group(1))
                elif not target.exists():
                    fail(number, 'missing link target: ' + match.group(1))
                elif url.fragment and target.suffix == '.md' and unquote(url.fragment) not in anchors(target.read_text(encoding='utf-8')):
                    fail(number, 'missing heading: ' + match.group(1))
        for match in RESOURCE.finditer(line):
            # resources mentioned as skill-root paths also occur inside code fences.
            if not (skill / match.group()).is_file():
                fail(number, 'missing skill resource: ' + match.group())

    for number, command in shell_commands(text):
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars='|&;')
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            if 'scripts/' in command:
                fail(number, 'cannot tokenize helper command; check quoting')
            continue
        for index, token in enumerate(tokens):
            match = SCRIPT_TOKEN.search(token)
            if not match:
                continue
            script = skill / 'scripts' / match.group(1)
            if not script.is_file():
                continue  # Resource check above supplies the error.
            if script not in option_cache:
                option_cache[script] = python_options(script)
            options = option_cache[script]
            rest = iter(tokens[index + 1:])
            for arg in rest:
                if arg in ('|', '||', '&&', ';', '--'):
                    break
                if not LONG_OPTION.match(arg):
                    continue
                flag = arg.split('=', 1)[0]
                if flag not in options:
                    fail(number, '%s does not declare %s' % (script.name, flag))
                elif options[flag] and '=' not in arg:
                    next(rest, None)  # Values may themselves contain literal --flags.
    return errors


def validate(root):
    root = Path(root).resolve()
    skill = root / 'skills' / 'reverse-skill'
    entry = skill / 'SKILL.md'
    if not entry.is_file():
        return ['missing skills/reverse-skill/SKILL.md'], {}
    data = entry.read_bytes()
    text = data.decode('utf-8')
    refs = sorted((skill / 'references').glob('*.md'))
    docs = [entry] + refs
    if (root / 'README.md').is_file():
        docs.append(root / 'README.md')
    errors = []
    if len(data) > MAX_SKILL_BYTES:
        errors.append('SKILL.md exceeds %d UTF-8 bytes (%d); move detail into references' % (MAX_SKILL_BYTES, len(data)))
    if len(text.splitlines()) > MAX_SKILL_LINES:
        errors.append('SKILL.md exceeds %d lines; move detail into references' % MAX_SKILL_LINES)
    for ref in refs:
        if 'references/' + ref.name not in text:
            errors.append('reference has no entry-point route: references/' + ref.name)
    option_cache = {}
    for doc in docs:
        try:
            errors.extend(check_document(doc, root, skill, option_cache))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append('%s: %s' % (doc.relative_to(root), exc))
    return sorted(set(errors)), {'documents': len(docs), 'skill_bytes': len(data),
                                 'skill_lines': len(text.splitlines()), 'python_helpers_checked': len(option_cache)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--json', action='store_true')
    args = p.parse_args(argv)
    try:
        errors, stats = validate(args.root)
    except (OSError, UnicodeError) as exc:
        errors, stats = [str(exc)], {}
    if args.json:
        print(json.dumps({'ok': not errors, 'errors': errors, 'stats': stats}, indent=2))
    else:
        for error in errors:
            print(error)
        print('Skill documentation: %s %s' % ('FAIL' if errors else 'PASS', json.dumps(stats, sort_keys=True)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
