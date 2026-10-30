"""Automatic candidates are bounded source proposals, never accepted evidence."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import validate_requirements
from agent_sessions.analysis.suggestions import suggest_requirements
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError

PROJECT = '/workspace/example-project'


class SuggestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / 'exports'
        self.export('synthetic-query', 'The example cache needs a brief.\n\nDo not implement or publish.\nThis applies to all proposed changes.')
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access'))
        home.start()
        self.addCleanup(home.stop)

    def export(self, sid, text, cwd=PROJECT):
        session = Session(id=sid, agent=Agent.CODEX, cwd=cwd, messages=[Message(role='user', text=text)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def test_complete_paragraph_proposals_are_read_only_and_not_ready(self):
        before = {path: path.read_bytes() for path in self.archive.iterdir() if path.is_file()}
        report = suggest_requirements(self.archive, 'example cache')
        self.assertFalse(report['ready'])
        self.assertFalse(report['coverage_established'])
        self.assertTrue(report['read_only'])
        anchor = report['candidates'][0]['anchor']
        self.assertEqual(anchor['quote'], 'Do not implement or publish.\nThis applies to all proposed changes.')
        self.assertEqual(anchor['paragraph']['start_line'], 3)
        self.assertEqual(anchor['paragraph']['end_line'], 4)
        validate_requirements(dict(version=1, requirements=[anchor]))
        self.assertEqual(before, {path: path.read_bytes() for path in self.archive.iterdir() if path.is_file()})

    def test_embedded_constraints_remain_candidates_with_origin_hints(self):
        self.export('synthetic-skill', '<skill>\nDo not publish.\n</skill>')
        report = suggest_requirements(self.archive, 'example cache', projects=[PROJECT])
        candidate = next(item for item in report['candidates'] if item['anchor']['session_id'] == 'synthetic-skill')
        self.assertEqual(candidate['origin_hint'], 'embedded_reference')
        self.assertIn('Do not publish.', candidate['anchor']['quote'])
        self.assertFalse(report['ready'])

    def test_cross_session_candidates_need_explicit_metadata_scope(self):
        self.export('synthetic-timing', 'Open question: Should timing remain a proposed target?')
        self.export('synthetic-other', 'Discovery only. Do not implement.', cwd='/workspace/other-project')
        report = suggest_requirements(self.archive, 'example cache')
        self.assertEqual({item['anchor']['session_id'] for item in report['candidates']}, {'synthetic-query'})
        report = suggest_requirements(self.archive, 'example cache', projects=[PROJECT])
        self.assertEqual({item['anchor']['session_id'] for item in report['candidates']}, {'synthetic-query', 'synthetic-timing'})
        timing = next(item for item in report['candidates'] if item['anchor']['session_id'] == 'synthetic-timing')
        self.assertEqual(timing['topic_relation'], 'declared_metadata_scope_only')

    def test_excluded_contents_and_fenced_instructions_do_not_enter_proposals(self):
        self.export('synthetic-other', 'Do not publish.', cwd='/workspace/other-project')
        self.export('synthetic-code', 'The example cache has a syntax example.\n```text\nDo not publish.\n```')
        original = Path.read_bytes
        def read(path):
            if path.name == 'synthetic-other.md':
                raise AssertionError('Excluded source was read')
            return original(path)
        with patch.object(Path, 'read_bytes', read):
            report = suggest_requirements(self.archive, 'example cache', projects=[PROJECT])
        self.assertNotIn('synthetic-code', {item['anchor']['session_id'] for item in report['candidates']})

    def test_limits_expose_omissions_without_shortening_selected_paragraphs(self):
        self.export('synthetic-extra', 'The example cache remains scoped.\n\nDiscovery only.\n\nOpen question: Should work proceed?')
        report = suggest_requirements(self.archive, 'example cache', limit=1)
        self.assertEqual(len(report['candidates']), 1)
        self.assertGreater(report['candidates_omitted'], 0)
        report = suggest_requirements(self.archive, 'example cache', max_paragraph_chars=10)
        self.assertEqual(report['candidates'], [])
        self.assertGreater(report['oversized_paragraphs_omitted'], 0)
        self.assertEqual(report['omissions'][0]['reason'], 'paragraph_too_large')
        self.assertGreater(report['omissions'][0]['paragraph_chars'], 10)

    def test_qualification_variants_are_proposals_without_truth_or_authority(self):
        for text in ('The release remains unapproved.', 'This is not deployed.', 'The deadline is a proposed target.'):
            self.export('synthetic-qualification', 'The example cache needs clarification.\n\n' + text)
            report = suggest_requirements(self.archive, 'example cache')
            candidate = next(item for item in report['candidates'] if item['anchor']['session_id'] == 'synthetic-qualification')
            self.assertIn('qualification_candidate', candidate['reasons'])
            self.assertEqual(candidate['verification'], 'not_checked')
            self.assertFalse(report['ready'])

    def test_missing_sources_are_explicit_and_invalid_inputs_fail(self):
        (self.archive / 'synthetic-query.md').unlink()
        report = suggest_requirements(self.archive, 'example cache')
        self.assertEqual(report['warnings'][0]['code'], 'suggestion_source_unavailable')
        for options in (dict(limit=0), dict(limit=101), dict(max_paragraph_chars=0)):
            with self.assertRaises(ValueError):
                suggest_requirements(self.archive, 'example cache', **options)

    def test_metadata_race_is_detected_before_returning_candidates(self):
        from agent_sessions.analysis import suggestions
        original = suggestions._labels
        def changed(body, role):
            index = self.archive / 'sessions.json'
            data = json.loads(index.read_text())
            data['sessions'][0]['agent'] = 'cursor'
            index.write_text(json.dumps(data))
            return original(body, role)
        with patch.object(suggestions, '_labels', changed):
            with self.assertRaises(StorageError):
                suggest_requirements(self.archive, 'example cache')

    def test_cli_emits_json_for_assistant_consumption(self):
        stdout = io.StringIO()
        with patch.object(sys, 'argv', ['agent-sessions', 'handoff', 'suggest', 'example cache', '-d', str(self.archive)]), \
                contextlib.redirect_stdout(stdout):
            main()
        report = json.loads(stdout.getvalue())
        self.assertEqual(report['method'], 'bounded_paragraph_suggestions_v1')
        self.assertFalse(report['ready'])


if __name__ == '__main__':
    unittest.main()
