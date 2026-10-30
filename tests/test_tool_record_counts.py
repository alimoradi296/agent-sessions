"""Parsed evidence availability must not become an execution or pairing claim."""

import json
from pathlib import Path
import tempfile
import unittest

from agent_sessions.analysis.search import search_archive, render_search
from agent_sessions.models import Agent, Message, Session, ToolCall, ToolResult
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


class ToolRecordCountsTests(unittest.TestCase):
    def export(self, directory, session):
        MarkdownRenderer.write(session, directory)
        JsonIndexRenderer.update(session, directory / 'sessions.json')

    def test_call_without_id_and_without_results_is_visible(self):
        session = Session(id='synthetic-call-only', agent=Agent.CURSOR, messages=[Message(
            role='assistant', text='', tool_calls=[ToolCall('Shell', 'SYNTHETIC_CHECK', arguments='SYNTHETIC_CHECK')])])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.export(root, session)
            report = search_archive(root, 'SYNTHETIC_CHECK', view='evidence')
            self.assertEqual(report['hits'][0]['parsed_tool_records'],
                             dict(calls=1, calls_with_id=0, results=0, results_with_id=0))
            self.assertIn('1 parsed calls (0 with IDs); 0 parsed results', render_search(report))
            self.assertEqual(report['hits'][0]['verification'], 'not_checked')

    def test_equal_counts_with_different_ids_do_not_establish_pairing(self):
        session = Session(id='synthetic-unpaired', agent=Agent.CODEX, messages=[
            Message(role='assistant', text='', tool_calls=[ToolCall('Shell', 'SYNTHETIC_CHECK', call_id='call-a')]),
            Message(role='tool', text='', tool_results=[ToolResult('SYNTHETIC_CHECK output', call_id='call-b')])])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.export(root, session)
            report = search_archive(root, 'SYNTHETIC_CHECK', view='evidence')
            self.assertEqual(len(report['hits']), 2)
            for hit in report['hits']:
                self.assertEqual(hit['parsed_tool_records'], dict(calls=1, calls_with_id=1, results=1, results_with_id=1))
                self.assertEqual(hit['verification'], 'not_checked')
            output = render_search(report)
            self.assertIn('do not establish source completeness, execution, or pairing', output)
            self.assertEqual(output.count('Export metadata:'), 1)

    def test_missing_or_invalid_metadata_stays_unknown_after_cache_refresh(self):
        session = Session(id='synthetic-legacy', agent=Agent.CURSOR,
                          messages=[Message(role='assistant', text='SYNTHETIC_CHECK')])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.export(root, session)
            search_archive(root, 'SYNTHETIC_CHECK', view='evidence')
            index = root / 'sessions.json'
            document = json.loads(index.read_text())
            for value in (None, dict(calls=True, calls_with_id=0, results=0, results_with_id=0),
                          dict(calls=0, calls_with_id=1, results=0, results_with_id=0)):
                if value is None:
                    document['sessions'][0].pop('parsed_tool_records', None)
                else:
                    document['sessions'][0]['parsed_tool_records'] = value
                index.write_text(json.dumps(document))
                report = search_archive(root, 'SYNTHETIC_CHECK', view='evidence')
                self.assertIsNone(report['hits'][0]['parsed_tool_records'])
                self.assertIn('counts unavailable', render_search(report))
