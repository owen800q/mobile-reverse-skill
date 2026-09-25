"""Fixture-based checks for documentation defects and inert CLI inspection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_skill_docs', ROOT / 'tools/check_skill_docs.py')
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='skill docs spaces ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / 'skills/reverse-skill'
        (self.skill / 'references').mkdir(parents=True)
        (self.skill / 'scripts').mkdir()
        self.write('SKILL.md', '# Test\n\n[Guide](references/guide.md#setup)\n')
        self.write('references/guide.md', '# Guide\n\n## Setup\n')

    def write(self, path, text):
        file = self.skill / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8')
        return file

    def check(self):
        return docs.validate(self.root)[0]

    def helper(self):
        self.write('scripts/example.py', '''import argparse
raise RuntimeError('must never import or run this script')
p = argparse.ArgumentParser()
p.add_argument('--output')
p.add_argument('--json', action='store_true')
''')

    def test_valid_links_and_fenced_helper_with_continuation(self):
        self.helper()
        self.write('references/guide.md', '# Guide\n\n## Setup\n\n```bash\npython3 "$SKILL_ROOT/scripts/example.py" \\\n  --output "$SESSION_DIR/a path" --json\n```\n')
        self.assertEqual(self.check(), [])

    def test_typo_in_helper_flag_fails_without_executing_example(self):
        self.helper()
        marker = self.root / 'never-created'
        self.write('references/guide.md', '# Guide\n\n## Setup\n\n```bash\npython3 scripts/example.py --out x; touch ' + str(marker) + '\n```\n')
        self.assertTrue(any('does not declare --out' in e for e in self.check()))
        self.assertFalse(marker.exists())

    def test_pipeline_flags_and_flag_like_argument_values_belong_to_other_contexts(self):
        self.helper()
        self.write('references/guide.md', '# Guide\n\n## Setup\n\n```bash\npython3 scripts/example.py --output "--literal-value" | external --unrelated\n```\n')
        self.assertEqual(self.check(), [])

    def test_broken_link_and_missing_heading_are_reported(self):
        self.write('references/guide.md', '# Guide\n\n## Setup\n[Missing](missing.md)\n[Bad heading](#unknown)\n')
        errors = self.check()
        self.assertTrue(any('missing link target: missing.md' in e for e in errors))
        self.assertTrue(any('missing heading: #unknown' in e for e in errors))

    def test_inline_code_is_not_a_markdown_link(self):
        self.write('references/guide.md', '# Guide\n\n## Setup\nRun `IMPORTS[pc](uc)` when appropriate.\n')
        self.assertEqual(self.check(), [])

    def test_unknown_resource_and_unrouted_reference_are_reported(self):
        self.write('references/orphan.md', '# Orphan\n')
        self.write('references/guide.md', '# Guide\n\n## Setup\nUse `scripts/missing.py`.\n')
        errors = self.check()
        self.assertTrue(any('no entry-point route' in e for e in errors))
        self.assertTrue(any('missing skill resource' in e for e in errors))

    def test_unicode_duplicate_and_inline_code_headings(self):
        self.write('references/guide.md', '# Guide\n\n## Setup\n## `API` 值\n## `API` 值\n[Again](#api-值-1)\n')
        self.assertEqual(self.check(), [])

    def test_external_links_and_kb_are_not_checked(self):
        self.write('references/guide.md', '# Guide\n\n## Setup\n[Remote](https://example.invalid/absent#heading)\n')
        self.write('kb/articles/untrusted.md', '[Missing](never.md)\n`references/not-shipped.md`\n')
        self.assertEqual(self.check(), [])

    def test_entry_point_budget_counts_unicode_bytes(self):
        self.write('SKILL.md', '# Test\nreferences/guide.md\n' + '字' * (docs.MAX_SKILL_BYTES // 3 + 1))
        self.assertTrue(any('UTF-8 bytes' in e for e in self.check()))

    def test_line_budget_catches_many_short_lines(self):
        self.write('SKILL.md', '# Test\nreferences/guide.md\n' + '\n' * docs.MAX_SKILL_LINES)
        self.assertTrue(any('exceeds 400 lines' in e for e in self.check()))

    def test_link_outside_checkout_is_not_accepted(self):
        self.write('references/guide.md', '# Guide\n\n## Setup\n[Outside](../../../../outside.md)\n')
        self.assertTrue(any('leaves the repository' in e for e in self.check()))

    def test_current_skill_documents_pass(self):
        errors, stats = docs.validate(ROOT)
        self.assertEqual(errors, [])
        self.assertGreater(stats['python_helpers_checked'], 0)


if __name__ == '__main__':
    unittest.main()
