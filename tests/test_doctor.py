"""Offline contracts: discovery is inert; device work is explicit and bounded."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/reverse-skill/scripts/doctor.py'
spec = importlib.util.spec_from_file_location('skill_doctor', SCRIPT)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class DoctorTests(unittest.TestCase):
    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = doctor.main(['--json', *args])
        return rc, json.loads(out.getvalue())

    def test_default_report_runs_no_tools_even_when_adb_is_present(self):
        with patch.object(doctor.shutil, 'which', return_value='/fake/tool'), \
                patch.object(doctor.subprocess, 'run') as run:
            rc, report = self.run_main('--platform', 'android')
        run.assert_not_called()
        self.assertEqual(rc, 0)
        self.assertEqual(report['device'], {'requested': False, 'status': 'not_checked'})
        self.assertEqual(report['capabilities']['android_tls_capture']['status'], 'needs_verification')
        self.assertNotIn('ios_static', report['capabilities'])

    def test_discovery_does_not_import_a_located_module(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / 'inert_doctor_fixture.py'
            module.write_text('raise RuntimeError("this module must not be imported")\n')
            with patch.object(sys, 'path', [directory]):
                result = doctor.module_location('inert_doctor_fixture')
        self.assertEqual(result['status'], 'found')
        self.assertNotIn('inert_doctor_fixture', sys.modules)

    def test_missing_optional_tools_do_not_fail_offline_report(self):
        with patch.object(doctor.shutil, 'which', return_value=None):
            rc, report = self.run_main()
        self.assertEqual(rc, 0)
        self.assertEqual(report['capabilities']['offline_helpers']['status'], 'available')
        self.assertEqual(report['capabilities']['android_repack']['status'], 'missing')

    def test_static_decompiler_alternatives_and_signing_requirements(self):
        with patch.object(doctor.shutil, 'which', side_effect=lambda n: '/bin/' + n if n in ('bash', 'java', 'unzip', 'jadx') else None):
            _, report = self.run_main('--platform', 'android')
        self.assertEqual(report['capabilities']['android_static']['status'], 'available')
        self.assertIn('zipalign', report['capabilities']['android_repack']['missing'])
        self.assertIn('apksigner', report['capabilities']['android_repack']['missing'])

    def test_located_ida_is_not_reported_as_runtime_verified(self):
        with patch.object(doctor, 'module_location', return_value=doctor.check('found', 'located')):
            _, report = self.run_main()
        self.assertEqual(report['capabilities']['native_ida_headless']['status'], 'needs_verification')

    def test_external_venv_sharing_a_binary_does_not_inherit_host_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'main.py').write_text('raise RuntimeError("never execute ASC")')
            other = root / 'python'
            other.symlink_to(sys.executable)
            _, report = self.run_main('--asc-root', str(root), '--asc-python', str(other))
        self.assertEqual(report['inventory']['asc_checkout']['status'], 'found')
        self.assertEqual(report['inventory']['asc_version']['status'], 'unverified')
        self.assertEqual(report['inventory']['androguard']['status'], 'unverified')

    def test_asc_checks_version_of_current_interpreter(self):
        with patch.object(doctor.sys, 'version_info', (3, 9, 0)):
            _, report = self.run_main('--asc-python', sys.executable)
        self.assertEqual(report['inventory']['python']['status'], 'found')
        self.assertEqual(report['inventory']['asc_version']['status'], 'missing')

    def test_candidate_device_binary_is_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'device binary'
            binary.write_bytes(b'not a host executable')
            with patch.object(doctor.subprocess, 'run') as run:
                _, report = self.run_main('--ecapture-bin', str(binary))
        run.assert_not_called()
        self.assertEqual(report['inventory']['ecapture_binary']['status'], 'found')
        self.assertTrue(report['capabilities']['android_tls_capture']['verify_before_use'])

    def test_explicit_device_uses_selected_serial_without_shell_and_has_timeouts(self):
        replies = [subprocess.CompletedProcess([], 0, value, '') for value in ('device\n', 'arm64-v8a\n', '6.1\n')]
        serial = 'serial with spaces;literal'
        with patch.object(doctor.subprocess, 'run', side_effect=replies) as run:
            result = doctor.device_probe('/path/adb', serial, 2.5)
        self.assertEqual(result['status'], 'reachable')
        self.assertEqual([c.args[0][3:] for c in run.call_args_list],
                         [['get-state'], ['shell', 'getprop', 'ro.product.cpu.abi'], ['shell', 'uname', '-r']])
        for call in run.call_args_list:
            self.assertEqual(call.args[0][:3], ['/path/adb', '-s', serial])
            self.assertEqual(call.kwargs['timeout'], 2.5)
            self.assertFalse(call.kwargs.get('shell', False))

    def test_timeout_is_failed_probe_not_target_failure_and_stops_commands(self):
        with patch.object(doctor.shutil, 'which', return_value='/fake/adb'), \
                patch.object(doctor.subprocess, 'run', side_effect=subprocess.TimeoutExpired('adb', 1)) as run:
            rc, report = self.run_main('--device', 'fixture', '--timeout', '1')
        self.assertEqual(rc, 3)
        self.assertEqual(run.call_count, 1)
        self.assertIn('TimeoutExpired', report['device']['error'])

    def test_offline_or_unauthorized_device_stops_after_get_state(self):
        for value in ('offline\n', 'unauthorized\n', ''):
            with self.subTest(value=value), patch.object(doctor.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, value, '')) as run:
                result = doctor.device_probe('/fake/adb', 'fixture', 1)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(run.call_count, 1)

    def test_invalid_device_and_timeout_arguments_cannot_start_a_probe(self):
        for args in (['--device', ''], ['--device', 'x', '--platform', 'ios'],
                     ['--timeout', 'nan'], ['--timeout', 'inf'], ['--timeout', '0'], ['--timeout', '31']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(doctor.subprocess, 'run') as run:
                with self.assertRaises(SystemExit) as error:
                    doctor.main(args)
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    def test_cli_output_is_one_json_document(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--platform', 'ios', '--json'],
                                capture_output=True, text=True, timeout=10,
                                env=dict(os.environ, ASC_PYTHON=sys.executable))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['schema_version'], 1)
        self.assertNotIn('android_static', report['capabilities'])
        self.assertEqual(report['device']['status'], 'not_checked')


if __name__ == '__main__':
    unittest.main()
