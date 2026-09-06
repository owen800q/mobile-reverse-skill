import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_skill', ROOT / 'tools/install_skill.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='reverse skill test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'repo/skills/reverse-skill'
        for name, data in {
            'SKILL.md': '---\nname: reverse-skill\ndescription: Test fixture\n---\n',
            'references/native.md': 'shared native reference',
            'kb/articles/example.md': 'shared knowledge',
            'kb/index/embeddings.npy': b'\x00\x01\xff',
            'scripts/helper.py': 'print("helper")\n',
            'assets/example.bin': b'\x00\xff',
        }.items():
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data if isinstance(data, bytes) else data.encode())
        self.claude = self.root / 'claude/skills/reverse-skill'
        self.codex = self.root / 'codex/skills/reverse-skill'
        self.shared = self.root / 'shared/reverse-skill'
        self.env = {
            'CLAUDE_SKILLS_DIR': str(self.claude.parent),
            'CODEX_SKILLS_DIR': str(self.codex.parent),
            'REVERSE_SKILL_SHARED_DIR': str(self.shared),
        }
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env).start()

    def install(self, agent='claude', link=False):
        with contextlib.redirect_stdout(io.StringIO()):
            installer.install(self.source, agent, link)

    def test_claude_copy_keeps_defaults_and_complete_content(self):
        self.install()
        self.assertFalse(self.claude.is_symlink())
        self.assertFalse(self.codex.exists())
        for p in self.source.rglob('*'):
            if p.is_file():
                self.assertEqual(p.read_bytes(), (self.claude / p.relative_to(self.source)).read_bytes())
        self.assertTrue(os.access(self.claude / 'scripts/helper.py', os.X_OK))

    def test_claude_legacy_link(self):
        self.install(link=True)
        self.assertTrue(self.claude.samefile(self.source))

    def test_codex_only(self):
        self.install('codex')
        self.assertTrue((self.codex / 'SKILL.md').is_file())
        self.assertFalse(self.claude.exists())

    def test_both_snapshot_has_one_knowledge_tree(self):
        self.install('both')
        self.assertTrue(self.claude.samefile(self.shared))
        self.assertTrue(self.codex.samefile(self.shared))
        article = 'kb/articles/example.md'
        (self.claude / article).write_text('shared edit')
        self.assertEqual((self.codex / article).read_text(), 'shared edit')
        self.assertEqual((self.source / article).read_text(), 'shared knowledge')

    def test_both_link_sees_checkout_updates(self):
        self.install('both', link=True)
        (self.source / 'kb/articles/example.md').write_text('updated')
        self.assertTrue(self.codex.samefile(self.source))
        self.assertTrue(self.claude.samefile(self.source))
        self.assertEqual((self.codex / 'kb/articles/example.md').read_text(), 'updated')
        self.assertFalse(self.shared.exists())

    def test_reinstall_preserves_old_copy_and_refreshes_shared_content(self):
        self.install('both')
        (self.shared / 'local-note.txt').write_text('keep me')
        (self.source / 'kb/articles/example.md').write_text('v2')
        self.install('both')
        self.assertEqual((self.codex / 'kb/articles/example.md').read_text(), 'v2')
        saved = list((self.shared.parent.parent / 'reverse-skill-install-backups').glob('*/local-note.txt'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(), 'keep me')

    def test_migrates_existing_independent_installs(self):
        self.install('claude')
        self.install('codex')
        self.install('both', link=True)
        self.assertTrue(self.claude.samefile(self.codex))

    def test_replacing_link_never_changes_target(self):
        external = self.root / 'external'
        external.mkdir()
        (external / 'keep').write_text('untouched')
        self.claude.parent.mkdir(parents=True)
        self.claude.symlink_to(external, target_is_directory=True)
        self.install()
        self.assertEqual((external / 'keep').read_text(), 'untouched')

    def test_source_overlap_and_destination_collision_rejected_before_changes(self):
        with patch.dict(os.environ, {'CLAUDE_SKILLS_DIR': str(self.source.parent)}):
            with self.assertRaisesRegex(ValueError, 'overlaps source'):
                self.install()
        with patch.dict(os.environ, {'CODEX_SKILLS_DIR': str(self.claude.parent)}):
            with self.assertRaisesRegex(ValueError, 'destinations overlap'):
                self.install('both')
        self.assertFalse(self.shared.exists())
        self.assertTrue((self.source / 'SKILL.md').is_file())

    def test_empty_override_rejected(self):
        with patch.dict(os.environ, {'CODEX_SKILLS_DIR': ''}):
            with self.assertRaisesRegex(ValueError, 'must not be empty'):
                self.install('codex')

    def test_rollback_restores_all_existing_installations(self):
        self.install('both')
        (self.shared / 'local-note.txt').write_text('original')
        original = Path.rename
        def fail_last(payload, dest):
            if '.reverse-skill-stage-' in str(payload) and Path(dest) == self.codex:
                raise OSError('simulated publication failure')
            return original(payload, dest)
        with patch.object(Path, 'rename', fail_last):
            with self.assertRaisesRegex(OSError, 'simulated'):
                self.install('both')
        self.assertTrue(self.claude.samefile(self.codex))
        self.assertEqual((self.codex / 'local-note.txt').read_text(), 'original')
        self.assertFalse(list(self.root.rglob('.reverse-skill-stage-*')))

    def test_wrapper_parses_old_and_new_commands(self):
        repo = self.source.parents[1]
        (repo / 'tools').mkdir()
        (repo / 'install.sh').write_bytes((ROOT / 'install.sh').read_bytes())
        (repo / 'tools/install_skill.py').write_bytes((ROOT / 'tools/install_skill.py').read_bytes())
        for args in ([], ['--link'], ['--agent', 'codex'], ['--link', '--agent', 'both']):
            result = subprocess.run(['bash', str(repo / 'install.sh'), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(['bash', str(repo / 'install.sh'), '--agent', 'invalid'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_documented_default_directories(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'home', return_value=self.root / 'user'):
            self.install('both')
        self.assertTrue((self.root / 'user/.claude/skills/reverse-skill').samefile(
            self.root / 'user/.agents/skills/reverse-skill'))


if __name__ == '__main__':
    unittest.main()
