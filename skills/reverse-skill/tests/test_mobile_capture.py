"""Exercise the mobile capture parsers without a device or network connection."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import ecapture_parse


class MobileCaptureTests(unittest.TestCase):
    def test_http_request_keeps_fields_needed_for_signature_alignment(self):
        payload = (
            b'POST /v2/session/login HTTP/1.1\r\n'
            b'Host: api.example.test\r\nContent-Type: application/json\r\n'
            b'X-Sign: sample-signature\r\n\r\n'
            b'{"user":"test-user","nonce":"sample-nonce"}'
        )
        record = ecapture_parse.extract_http('send', payload)
        self.assertEqual(record['method'], 'POST')
        self.assertEqual(record['path'], '/v2/session/login')
        self.assertEqual(record['host'], 'api.example.test')
        self.assertEqual(json.loads(record['body'])['user'], 'test-user')
        self.assertEqual(record['sig_candidates']['X-Sign'], 'sample-signature')

    def test_stackplz_cli_normalizes_a_supplied_mobile_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'capture.json'
            source.write_text(json.dumps([
                {'comm': 'com.example.app', 'pid': 123, 'name': 'SSL_write',
                 'buf': 'POST /login HTTP/1.1'}
            ]))
            out = Path(tmp) / 'parsed'
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'stackplz_parse.py'),
                 str(source), '--out', str(out)],
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            records = json.loads((out / 'stackplz_events.json').read_text())
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['comm'], 'com.example.app')
            self.assertEqual(records[0]['name'], 'SSL_write')
            self.assertEqual(records[0]['buffers'][0]['text'], 'POST /login HTTP/1.1')


if __name__ == '__main__':
    unittest.main()
