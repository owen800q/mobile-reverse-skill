"""Regression checks for the "scope follows the operation" policy.

Context: README.md's "## Legal" section used to read "Use exclusively
against apps, sites, software, devices, and accounts you own or are
authorized to assess" -- an unqualified ownership/authorization gate on
every use of the skill. SKILL.md and operating-scope.md already say the
opposite for local work: possessing a supplied third-party artifact (an
APK, say) is enough to start local static analysis; a publisher being a
third party, or the absence of an approval letter, is not a reason to
refuse. Only operations that touch a device, an account, or a live
service need real, established scope. README's Legal section contradicted
its own repo's policy and could lead an agent to refuse a request like
"analyze this Hongguo Duanju APK's video-loading request construction,
starting from local static analysis" solely because the app has a
third-party publisher, even though no device, account, or live service is
involved.

These tests guard both halves of the fix: README.md must no longer impose
that blanket gate on local analysis (the bug), and SKILL.md /
operating-scope.md / the device-touching scripts must keep requiring real
scope for device and live-service operations (the parts that were already
correct and must not be weakened while fixing the bug).

They check documentation text and CLI contracts, not model behavior: a
green run shows the policy documents and tools agree with each other, not
that any particular agent run follows them.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / 'README.md'
SKILL_MD = ROOT / 'skills/reverse-skill/SKILL.md'
OPERATING_SCOPE = ROOT / 'skills/reverse-skill/references/operating-scope.md'
SCRIPTS = ROOT / 'skills/reverse-skill/scripts'


def _normalize(text):
    """Strip leading Markdown blockquote markers, then collapse whitespace.

    Lets a substring assertion span a wrapped paragraph (plain or
    blockquoted) without being sensitive to exactly where the source wraps
    its lines.
    """
    lines = [re.sub(r'^>\s*', '', line) for line in text.splitlines()]
    return ' '.join(' '.join(lines).split())


def _section(markdown_text, heading):
    """Return the raw body of a top-level '## heading' Markdown section."""
    pattern = re.compile(
        r'^##[ \t]+' + re.escape(heading) + r'[ \t]*$(.*?)(?=^##[ \t]+|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown_text)
    if not match:
        raise AssertionError('no "## %s" section found in the document' % heading)
    return match.group(1)


class ReadmeLegalSectionTests(unittest.TestCase):
    """README.md's Legal section must not re-impose a blanket ownership gate
    on local analysis, and must keep the real safety boundaries."""

    def setUp(self):
        self.legal = _normalize(_section(README.read_text(encoding='utf-8'), 'Legal'))

    def test_local_static_analysis_is_not_gated_on_ownership(self):
        self.assertIn(
            'does not require that you own it or hold a signed engagement',
            self.legal,
        )
        # The specific old phrasing must not come back: a blanket ownership
        # clause with no local-analysis carve-out anywhere in the section.
        self.assertNotRegex(
            self.legal,
            r'exclusively against apps,?\s*sites,?\s*software,?\s*devices,?\s*and accounts',
        )

    def test_points_readers_at_operating_scope_for_the_per_operation_rule(self):
        self.assertIn('operating-scope.md', self.legal)

    def test_device_and_live_service_actions_still_need_real_scope(self):
        # The exemption is for local analysis only. Device instrumentation,
        # live capture, and replay still need scope for the device, account
        # or service actually being touched -- losing this half while fixing
        # the first would open the opposite hole.
        self.assertIn('own or are authorized to', self.legal)
        self.assertIn("another person's account or data", self.legal)

    def test_desktop_protection_boundary_is_preserved(self):
        # Pre-existing safety boundary that the Legal-section rewrite must
        # carry forward unchanged.
        self.assertIn('do not', self.legal)
        self.assertIn('bypass, patch, or skip protections', self.legal)
        self.assertIn('generate keys or activation responses', self.legal)


class SkillAndOperatingScopePolicyTests(unittest.TestCase):
    """SKILL.md and operating-scope.md already state the policy correctly;
    these guard against a future edit quietly reintroducing README's bug
    into the documents agents actually load at skill-invocation time."""

    def setUp(self):
        self.skill = _normalize(SKILL_MD.read_text(encoding='utf-8'))
        self.scope = _normalize(OPERATING_SCOPE.read_text(encoding='utf-8'))

    def test_skill_md_banner_states_scope_follows_the_operation(self):
        self.assertIn('Scope follows the operation.', self.skill)
        self.assertIn(
            'does not require app ownership or a formal authorization document',
            self.skill,
        )
        self.assertIn(
            'do not refuse solely because the publisher is a third party',
            self.skill,
        )

    def test_skill_md_safety_section_forbids_an_approval_letter_prerequisite(self):
        self.assertIn(
            'Do not require a publisher approval letter, signed engagement, or '
            'other formal authorization document as a routine prerequisite for '
            'legitimate local analysis of a supplied third-party app',
            self.skill,
        )

    def test_skill_md_still_scopes_device_and_live_actions_separately(self):
        self.assertIn(
            'possession of an APK or an account does not authorize access to '
            'other accounts or backend systems',
            self.skill,
        )

    def test_operating_scope_exempts_local_artifact_analysis(self):
        self.assertIn(
            'A third-party publisher or the absence of an approval letter is '
            'not, by itself, a reason to refuse',
            self.scope,
        )

    def test_operating_scope_still_gates_live_services(self):
        self.assertIn('Live services:', self.scope)
        self.assertIn(
            'Owning a device or account, possessing an app, or stating a '
            'research purpose does not grant broader backend access',
            self.scope,
        )


class LocalStaticToolsHaveNoOwnershipGateTests(unittest.TestCase):
    """Local static-analysis entry points take no --scope/ownership flag.
    Scope statements belong to operations that touch a device or a live
    service (operating-scope.md), not to reading a supplied artifact."""

    STATIC_SCRIPTS = ('target_identify.py', 'mobile_inventory.py', 'api_extract.py')

    def test_static_scripts_do_not_require_a_scope_statement(self):
        for name in self.STATIC_SCRIPTS:
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / name), '--help'],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('--scope', result.stdout)


class DeviceTouchingToolsStillRequireScopeTests(unittest.TestCase):
    """adb_pull_package.py and device_state_diff.py pull or diff device
    state. operating-scope.md requires a --scope statement for both; this
    is the safety half of the same policy and must not be weakened by the
    README fix."""

    def test_adb_pull_package_refuses_without_scope(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'adb_pull_package.py'), 'com.example.test',
             '--out', '/tmp/reverse-skill-test-scope-policy-adb-pull'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn('--scope', result.stderr)

    def test_device_state_diff_refuses_without_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / 'before.tsv'
            after = Path(tmp) / 'after.tsv'
            before.write_text('a\t1\n', encoding='utf-8')
            after.write_text('a\t1\n', encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'device_state_diff.py'), str(before), str(after),
                 '--out', str(Path(tmp) / 'diff.json')],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn('--scope', result.stderr)


if __name__ == '__main__':
    unittest.main()
