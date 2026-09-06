import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

FINDINGS = Path(__file__).resolve().parents[1] / 'skills/reverse-skill/scripts/findings.py'


class SharedSessionTests(unittest.TestCase):
    def test_handoff_preserves_ledger_and_existing_validation(self):
        with tempfile.TemporaryDirectory() as session:
            def run(*args):
                return subprocess.run([sys.executable, str(FINDINGS), '--out', session, *args],
                                      capture_output=True, text=True)
            self.assertEqual(run('init', '--target', 'com.example.test', '--goal', 'inspect API').returncode, 0)
            self.assertEqual(run('add-fact', '--claim', 'endpoint found', '--rung', 'PATTERN').returncode, 0)
            ledger = Path(session) / 'findings.json'
            original = ledger.read_bytes()
            self.assertEqual(run('show').returncode, 0)
            self.assertNotEqual(run('init', '--target', 'other').returncode, 0)
            self.assertEqual(ledger.read_bytes(), original)
            self.assertEqual(run('set-phase', '1').returncode, 0)
            self.assertEqual(len(json.loads(ledger.read_text())['facts']), 1)
            self.assertEqual(run('validate').returncode, 0)
            # Evidence rules remain enforced after the other agent continues.
            self.assertEqual(run('add-fact', '--claim', 'unproven', '--rung', 'VERIFIED').returncode, 0)
            self.assertNotEqual(run('validate').returncode, 0)


if __name__ == '__main__':
    unittest.main()
