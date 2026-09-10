"""Offline adapter tests and opt-in tests against a real ASC checkout.

Real tests need ASC_TEST_ROOT, ASC_PYTHON, ASC_TEST_D8, javac and java.
No downloads or installation happen in this test suite.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/reverse-skill/scripts/asc.py'
EXTRACTOR = ROOT / 'skills/reverse-skill/scripts/api_extract.py'
FAKE_ASC = '''import json, os, pathlib, sys
args = sys.argv[1:]
pathlib.Path('invocation.json').write_text(json.dumps(args))
out = pathlib.Path(args[args.index('-o') + 1])
mode = os.environ.get('FAKE_ASC_MODE', 'ok')
data = 'package com.example; public class Api {}' if args[0] == 'getclass' else 'classes2.dex | Lcom/example/Api;->login | matched=(auth/login)\\n'
if mode == 'empty': data = ''
if mode == 'whitespace': data = '   \\n'
if mode == 'error_text': data = 'Error: Class not found in reconstructed DEX.'
if mode != 'missing': out.write_text(data)
print('diagnostic stdout')
print('diagnostic stderr', file=sys.stderr)
sys.exit(7 if mode == 'fail' else 0)
'''


class AscAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='asc test spaces ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.asc = self.root / 'ASC checkout'
        self.asc.mkdir()
        (self.asc / 'main.py').write_text(FAKE_ASC)
        self.apk = self.root / 'example app.apk'
        with zipfile.ZipFile(self.apk, 'w') as apk:
            apk.writestr('classes.dex', b'fixture for adapter only')
        self.original = self.apk.read_bytes()
        self.out = self.root / 'query'

    def invoke(self, *query, mode='ok', out=None, apk=None, options=()):
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--asc-root', str(self.asc),
             '--python', sys.executable, '--out', str(out or self.out), *options,
             query[0], str(apk or self.apk), *query[1:]],
            env=dict(os.environ, FAKE_ASC_MODE=mode), capture_output=True, text=True)

    def test_findrefs_preserves_regex_and_shell_characters_and_evidence(self):
        query = r'auth/[a-z]+; $(echo unexpected)'
        result = self.invoke('findrefs', 'string', query, options=('--threads', '2'))
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        argv = json.loads((self.asc / 'invocation.json').read_text())
        self.assertEqual(argv[:6], ['findrefs', str(self.apk), '--threads', '2', 'string', query])
        self.assertEqual(record['status'], 'ok')
        self.assertEqual(record['input_sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(record['exit_status'], 0)
        self.assertEqual(record['dex_entries'], ['classes.dex'])
        self.assertEqual(self.apk.read_bytes(), self.original)
        self.assertEqual((self.out / 'stdout.txt').read_text(), 'diagnostic stdout\n')
        self.assertEqual((self.out / 'stderr.txt').read_text(), 'diagnostic stderr\n')
        self.assertEqual(record, json.loads((self.out / 'asc_summary.json').read_text()))

    def test_class_names_are_runtime_descriptors_including_inner_and_default_package(self):
        for i, (name, expected) in enumerate([
            ('com.example.Api$Inner', 'Lcom/example/Api$Inner;'),
            ('Login', 'LLogin;'), ('Lcom/example/Api;', 'Lcom/example/Api;')]):
            result = self.invoke('getclass', name, out=self.root / str(i))
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(result.stdout)
            self.assertIn(expected, record['command'])
            self.assertEqual(record['coverage'], 'selected_class')
            self.assertTrue(Path(record['output']).name.endswith('.java'))

    def test_member_class_queries_and_fuzzy_matching(self):
        for i, args in enumerate([
            ('method', '--class', 'com.example.Api'),
            ('field', 'token', '--class', 'com.example', '--fuzzy-class')]):
            result = self.invoke('findrefs', *args, out=self.root / str(i))
            self.assertEqual(result.returncode, 0, result.stderr)
            cmd = json.loads(result.stdout)['command']
            expected = 'com.example' if i else 'Lcom/example/Api;'
            self.assertEqual(cmd[cmd.index('--class') + 1], expected)

    def test_empty_search_is_distinct_from_empty_class_and_upstream_failure(self):
        for i, (query, mode, status, rc) in enumerate([
            (('findrefs', 'string', 'missing'), 'empty', 'no_matches', 0),
            (('getclass', 'com.example.Api'), 'empty', 'failed', 1),
            (('getclass', 'com.example.Api'), 'whitespace', 'failed', 1),
            (('getclass', 'com.example.Api'), 'error_text', 'failed', 1),
            (('findrefs', 'string', 'auth'), 'fail', 'failed', 7),
            (('findrefs', 'string', 'auth'), 'missing', 'failed', 1)]):
            result = self.invoke(*query, mode=mode, out=self.root / str(i))
            self.assertEqual(result.returncode, rc, result.stderr)
            record = json.loads(result.stdout)
            self.assertEqual(record['status'], status)
            self.assertEqual(record['exit_status'], 7 if mode == 'fail' else 0)
            self.assertTrue(Path(record['stderr']).is_file())

    def test_existing_output_preserved(self):
        self.out.mkdir()
        saved = self.out / 'Class.java'
        saved.write_text('prior evidence')
        result = self.invoke('getclass', 'com.example.Api')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(saved.read_text(), 'prior evidence')
        self.assertFalse((self.asc / 'invocation.json').exists())

    def test_invalid_inputs_do_not_launch_asc(self):
        for args in [('findrefs', 'method'), ('findrefs', 'string'),
                     ('findrefs', 'type', 'Api', '--class', 'Api'),
                     ('findrefs', 'field', 'token', '--fuzzy-class'), ('getclass', '')]:
            self.assertNotEqual(self.invoke(*args).returncode, 0)
        bundle = self.root / 'bundle.xapk'
        bundle.write_bytes(self.original)
        self.assertNotEqual(self.invoke('getclass', 'Api', apk=bundle).returncode, 0)
        with zipfile.ZipFile(self.apk, 'w') as apk:
            apk.writestr('base.apk', self.original)
        self.assertNotEqual(self.invoke('getclass', 'Api').returncode, 0)
        self.assertFalse((self.asc / 'invocation.json').exists())
        self.assertFalse(self.out.exists())

    def test_missing_checkout_has_setup_hint(self):
        (self.asc / 'main.py').unlink()
        result = self.invoke('getclass', 'Api')
        self.assertEqual(result.returncode, 2)
        self.assertIn('main.py not found', result.stderr)


@unittest.skipUnless(os.environ.get('ASC_TEST_ROOT') and os.environ.get('ASC_TEST_D8'),
                     'set ASC_TEST_ROOT and ASC_TEST_D8 for real upstream integration')
class AscIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='asc real integration ')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        sources = {
            'Api': '''package com.example;
                public class Api {
                    public static String token;
                    @retrofit2.http.POST("auth/login")
                    public static String login() { return "https://example.test/auth/login"; }
                    public static String send() { return login(); }
                    public static String readToken() { return token; }
                    public static Class<?> type() { return Api.class; }
                }''',
            'Other': '''package com.example;
                public class Other {
                    public static String other() { return "https://example.test/auth/login"; }
                }''',
        }
        for name, source in sources.items():
            base = cls.root / name
            base.mkdir()
            java = base / (name + '.java')
            java.write_text(source)
            java_files = [str(java)]
            class_files = [str(base / 'com/example' / (name + '.class'))]
            if name == 'Api':
                annotation = base / 'POST.java'
                annotation.write_text('''package retrofit2.http;
                    @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME)
                    public @interface POST { String value(); }''')
                java_files.append(str(annotation))
                class_files.append(str(base / 'retrofit2/http/POST.class'))
            subprocess.run(['javac', '--release', '8', '-d', str(base), *java_files],
                           check=True, capture_output=True)
            subprocess.run(['java', '-cp', os.environ['ASC_TEST_D8'], 'com.android.tools.r8.D8',
                            '--output', str(base), *class_files],
                           check=True, capture_output=True)
        cls.apk = cls.root / 'fixture.apk'
        with zipfile.ZipFile(cls.apk, 'w', zipfile.ZIP_DEFLATED) as apk:
            apk.write(cls.root / 'Api/classes.dex', 'classes.dex')
            apk.write(cls.root / 'Other/classes.dex', 'classes2.dex')

    def invoke(self, *query):
        out = self.root / self._testMethodName
        result = subprocess.run([sys.executable, str(SCRIPT), '--asc-root', os.environ['ASC_TEST_ROOT'],
                                 '--out', str(out), query[0], str(self.apk), *query[1:]],
                                capture_output=True, text=True)
        detail = (out / 'stderr.txt').read_text() if (out / 'stderr.txt').exists() else ''
        self.assertEqual(result.returncode, 0, result.stderr + detail)
        record = json.loads(result.stdout)
        self.assertTrue(record['input_unchanged'])
        return Path(record['output']).read_text(), out

    def test_string_search_finds_both_dex_entries(self):
        data, _ = self.invoke('findrefs', 'string', 'auth/login')
        self.assertIn('classes.dex | Lcom/example/Api;->login', data)
        self.assertIn('classes2.dex | Lcom/example/Other;->other', data)

    def test_type_reference(self):
        data, _ = self.invoke('findrefs', 'type', 'Lcom/example/Api;')
        self.assertIn('Lcom/example/Api;->type', data)

    def test_method_reference(self):
        data, _ = self.invoke('findrefs', 'method', 'login', '--class', 'com.example.Api')
        self.assertIn('Lcom/example/Api;->send', data)

    def test_field_reference(self):
        data, _ = self.invoke('findrefs', 'field', 'token', '--class', 'com.example.Api')
        self.assertIn('Lcom/example/Api;->readToken', data)

    def test_class_extraction_feeds_api_extractor(self):
        data, out = self.invoke('getclass', 'com.example.Api')
        self.assertIn('https://example.test/auth/login', data)
        self.assertIn('class Api', data)
        result = subprocess.run([sys.executable, str(EXTRACTOR), str(out), '--out', str(out / 'api')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        endpoints = json.loads((out / 'api/api_endpoints.json').read_text())
        self.assertIn('https://example.test/auth/login', json.dumps(endpoints))
        self.assertTrue(any(e['method'] == 'POST' and e['path'] == 'auth/login'
                            for e in endpoints['endpoints']))

    def test_no_matching_reference(self):
        data, out = self.invoke('findrefs', 'string', 'no-such-endpoint-123456')
        self.assertEqual(data, '')
        self.assertEqual(json.loads((out / 'asc_summary.json').read_text())['status'], 'no_matches')


if __name__ == '__main__':
    unittest.main()
