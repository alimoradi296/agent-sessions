"""Incident evidence needs raw source quotes rather than cleaned dialogue."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.search import search_archive, search_cache_path, render_search
from agent_sessions.analysis.transcript import rendered_messages
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session, ToolResult
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError


class EvidenceSearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        session = Session(id='synthetic-evidence', agent=Agent.CODEX, cwd='/workspace/example', messages=[
            Message(role='user', text='Inspect the example.'),
            Message(role='assistant', text='Use this snippet:\n\n```python\nprint(entry.caption)\n## User fakeheading\n```'),
            Message(role='user', text='```text\nAttributeError: missing caption\n```'),
            Message(role='tool', text='', tool_results=[ToolResult('tool_output_sentinel', call_id='synthetic-call')]),
            Message(role='assistant', text='phase_sentinel', phase='commentary'),
        ])
        MarkdownRenderer.write(session, self.root)
        JsonIndexRenderer.update(session, self.root / 'sessions.json')

    def test_code_and_traceback_retained_with_exact_raw_coordinates(self):
        self.assertFalse(search_archive(self.root, 'entry.caption')['hits'])
        report = search_archive(self.root, 'entry.caption', view='evidence')
        hit = report['hits'][0]
        self.assertEqual(hit['role'], 'Assistant')
        self.assertEqual(hit['message'], 2)
        self.assertNotIn('section', hit)
        self.assertEqual(hit['locator_method'], 'rendered_message_v1')
        source = Path(hit['source_path']).read_text()
        self.assertEqual(source[hit['source_quote_start']:hit['source_quote_end']], hit['quote'])
        self.assertIn('## User fakeheading', hit['quote'])
        self.assertIn('message 2', render_search(report))
        self.assertIn(f"heading line {hit['message_heading_line']}", render_search(report))
        self.assertEqual(search_archive(self.root, 'AttributeError', view='evidence')['hits'][0]['role'], 'User')

    def test_tool_results_and_phase_labels_remain_distinguishable(self):
        self.assertFalse(search_archive(self.root, 'tool_output_sentinel')['hits'])
        hit = search_archive(self.root, 'tool_output_sentinel', view='evidence', role='tool')['hits'][0]
        self.assertEqual(hit['role'], 'Tool')
        phase = search_archive(self.root, 'phase_sentinel', view='evidence')['hits'][0]
        self.assertEqual(phase['phase'], 'commentary')
        self.assertFalse(search_archive(self.root, 'phase_sentinel')['hits'])

    def test_changed_code_refreshes_evidence_cache_even_with_same_mtime(self):
        import os
        search_archive(self.root, 'entry.caption', view='evidence', role='assistant')
        path = self.root / 'synthetic-evidence.md'
        stamp = path.stat()
        path.write_text(path.read_text().replace('entry.caption', 'entry.subject'))
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertFalse(search_archive(self.root, 'entry.caption', view='evidence', role='assistant')['hits'])
        self.assertTrue(search_archive(self.root, 'entry.subject', view='evidence', role='assistant')['hits'])

    def test_compound_expression_quote_is_not_anchored_to_a_substring(self):
        path = self.root / 'synthetic-evidence.md'
        path.write_text(path.read_text().replace('Use this snippet:', 'A caption discussion. ' * 70 + 'Use this snippet:'))
        hit = search_archive(self.root, 'entry.caption', view='evidence', role='assistant')['hits'][0]
        self.assertIn('entry.caption', hit['quote'])

    def test_numbered_evidence_lines_match_the_export(self):
        report = search_archive(self.root, 'entry.caption', view='evidence', role='assistant')
        hit = report['hits'][0]
        source = Path(hit['source_path']).read_text().splitlines()
        line = next(n for n, text in enumerate(source, 1) if text == 'print(entry.caption)')
        self.assertIn(f'L{line}: print(entry.caption)', render_search(report))
        self.assertEqual(hit['source_quote_column'], 1)

    def test_partial_lines_are_marked_in_text_output(self):
        path = self.root / 'synthetic-evidence.md'
        source = path.read_text().replace('Use this snippet:', 'A long preface ' * 100 + '\nUse this snippet:')
        path.write_text(source)
        report = search_archive(self.root, 'entry.caption', view='evidence', role='assistant')
        hit = report['hits'][0]
        self.assertGreater(hit['source_quote_column'], 1)
        self.assertIn('(fragment)', render_search(report))
        line = next(n for n, text in enumerate(source.splitlines(), 1) if text == 'print(entry.caption)')
        self.assertIn(f'L{line}: print(entry.caption)', render_search(report))

    def test_numbering_handles_crlf_and_carriage_return_content(self):
        path = self.root / 'synthetic-evidence.md'
        raw = path.read_bytes().replace(b'Use this snippet:', 'متن\rSecond line\rUse this snippet:'.encode())
        raw = raw.replace(b'\n', b'\r\n')
        path.write_bytes(raw)
        report = search_archive(self.root, 'entry.caption', view='evidence', role='assistant')
        hit = report['hits'][0]
        source = raw.decode('utf-8')
        self.assertEqual(source[hit['source_quote_start']:hit['source_quote_end']], hit['quote'])
        line = next(n for n, text in enumerate(source.splitlines(), 1) if text == 'print(entry.caption)')
        self.assertIn(f'L{line}: print(entry.caption)', render_search(report))

    def test_truncated_last_line_is_not_presented_as_complete(self):
        path = self.root / 'synthetic-evidence.md'
        path.write_text(path.read_text().replace('print(entry.caption)', 'print(entry.caption)' + 'x' * 900))
        report = search_archive(self.root, 'entry.caption', view='evidence', role='assistant')
        self.assertFalse(report['hits'][0]['quote_last_line_complete'])
        self.assertIn('(fragment)', render_search(report))

    def test_views_and_project_scopes_have_independent_caches(self):
        search_archive(self.root, 'Inspect')
        search_archive(self.root, 'Inspect', view='evidence')
        caches = {search_cache_path(self.root), search_cache_path(self.root, view='evidence'),
                  search_cache_path(self.root, ['/workspace/example'], view='evidence')}
        self.assertEqual(len(caches), 3)
        self.assertFalse(search_archive(self.root, 'caption', projects=['/workspace/other'], view='evidence')['hits'])
        path = search_cache_path(self.root, view='evidence')
        path.write_bytes(b'broken cache')
        with self.assertRaises(StorageError):
            search_archive(self.root, 'caption', view='evidence')
        self.assertTrue(search_archive(self.root, 'Inspect')['hits'])
        self.assertTrue(search_archive(self.root, 'caption', view='evidence', rebuild=True)['hits'])

    def test_crlf_and_unicode_offsets_are_character_locations(self):
        text = '# Archive\r\n\r\n## User\r\n\r\nمتن\r\n```text\r\n## Tool quoted\r\n```\r\n## Tool\r\nresult\r\n'
        messages = rendered_messages(text)
        self.assertEqual([m['role'] for m in messages], ['User', 'Tool'])
        self.assertEqual(text[messages[0]['body_start']:messages[1]['body_start'] - len('## Tool\r\n')], messages[0]['text'])

    def test_invalid_cached_message_locator_is_rejected(self):
        import sqlite3
        search_archive(self.root, 'caption', view='evidence')
        with contextlib.closing(sqlite3.connect(search_cache_path(self.root, view='evidence'))) as connection:
            connection.execute("UPDATE passages SET section='9999'")
            connection.commit()
        with self.assertRaisesRegex(StorageError, 'locator is invalid'):
            search_archive(self.root, 'caption', view='evidence')

    def test_cli_search_and_index_use_selected_view(self):
        for command in [['search', 'caption', '--view', 'evidence'], ['index', '--view', 'evidence', '--rebuild']]:
            with patch('sys.argv', ['agent-sessions', *command, '-d', str(self.root), '--json']), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                main()
            self.assertEqual(json.loads(output.getvalue())['view'], 'evidence')
