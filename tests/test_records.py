"""Record coverage tests use synthetic data and an isolated home."""

import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.doctor import Doctor, render_doctor
from agent_sessions.cli import cmd_bulk
from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser


SID = '44444444-4444-4444-8444-444444444444'


def codex(kind, **payload):
    return {'type': kind, 'payload': payload}


def message(agent, content='Synthetic example.'):
    if agent == 'codex':
        return codex('response_item', type='message', role='user',
                     content=[{'type': 'input_text', 'text': content}])
    return {('role' if agent == 'cursor' else 'type'): 'user',
            'message': {'content': content}}


class RecordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        home_patch = patch.object(Path, 'home', return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def write(self, name, records, suffix=''):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(r) + '\n' for r in records) + suffix)
        return path

    def test_all_parsers_count_records_without_losing_valid_messages(self):
        for agent, parser, ignored in (
            ('claude', ClaudeParser, {'type': 'attachment'}),
            ('codex', CodexParser, codex('response_item', type='reasoning')),
            # Cursor turn_ended is handled metadata, not ignored dialogue.
            ('cursor', CursorParser, {'type': 'turn_ended', 'status': 'success'}),
        ):
            with self.subTest(agent=agent):
                records = [message(agent), ignored, {'type': 'future_event'}, None, [],
                           {'type': 'response_item', 'payload': []} if agent == 'codex'
                           else {('role' if agent == 'cursor' else 'type'): 'user', 'message': []}]
                path = self.write(agent + '.jsonl', records, '\n{broken\n')
                diagnostics = {}
                session = parser.parse(path, diagnostics=diagnostics)
                self.assertEqual([m.text for m in session.messages], ['Synthetic example.'])
                counts = diagnostics[str(path)]
                self.assertEqual(counts['records'], 7)
                self.assertEqual(counts['blank_lines'], 1)
                self.assertEqual(counts['malformed'], 4)
                self.assertEqual(counts['unsupported'], 1)
                self.assertEqual(counts['ignored'], 0 if agent == 'cursor' else 1)
                self.assertEqual(counts['handled'], 2 if agent == 'cursor' else 1)
                self.assertEqual(counts['records'], sum(counts[k] for k in
                                 ('handled', 'ignored', 'malformed', 'unsupported')))

    def test_unknown_content_is_reported_and_known_text_survives(self):
        for agent, parser, text_kind in (('claude', ClaudeParser, 'text'),
                                        ('cursor', CursorParser, 'text'),
                                        ('codex', CodexParser, 'input_text')):
            with self.subTest(agent=agent):
                record = message(agent)
                target = record['payload'] if agent == 'codex' else record['message']
                target['content'] = [{'type': text_kind, 'text': 'Keep this.'},
                                     {'type': 'future_block', 'data': 'PRIVATE_SENTINEL'}]
                path = self.write(agent + '.jsonl', [record])
                diagnostics = {}
                session = parser.parse(path, diagnostics=diagnostics)
                self.assertEqual(session.messages[0].text, 'Keep this.')
                self.assertEqual(diagnostics[str(path)]['unsupported'], 1)
                self.assertNotIn('PRIVATE_SENTINEL', json.dumps(diagnostics))
                self.assertNotIn('future_block', json.dumps(diagnostics))

    def test_codex_resume_counts_are_per_physical_file_before_deduplication(self):
        records = [codex('session_meta', id=SID), message('codex'),
                   codex('event_msg', type='future_event')]
        first = self.write('a.jsonl', records, 'broken\n')
        second = self.write('b.jsonl', records, 'broken\n')
        diagnostics = {}
        session = CodexParser.parse_many([first, second], diagnostics=diagnostics)
        self.assertEqual(session.message_count, 1)
        self.assertEqual(len(diagnostics), 2)
        self.assertEqual(diagnostics[str(first)], diagnostics[str(second)])
        self.assertEqual(diagnostics[str(first)]['records'], 4)
        self.assertEqual(diagnostics[str(first)]['unsupported'], 1)

    def test_malformed_content_shapes_are_skipped(self):
        for agent, parser in (('claude', ClaudeParser), ('cursor', CursorParser),
                              ('codex', CodexParser)):
            for content in (42, [{'type': 'text' if agent != 'codex' else 'input_text', 'text': []}],
                            [None]):
                with self.subTest(agent=agent, content=content):
                    record = message(agent)
                    target = record['payload'] if agent == 'codex' else record['message']
                    target['content'] = content
                    path = self.write(agent + '.jsonl', [record])
                    diagnostics = {}
                    self.assertIsNone(parser.parse(path, diagnostics=diagnostics))
                    self.assertEqual(diagnostics[str(path)]['malformed'], 1)

    def test_bulk_and_readonly_doctor_report_empty_and_partial_sources(self):
        first = self.write('.codex/sessions/a.jsonl', [codex('session_meta', id=SID),
                           message('codex'), codex('event_msg', type='future_event')])
        second = self.write('.codex/sessions/empty.jsonl', [], 'null\n{broken\n')
        out = self.home / 'exports'
        args = Namespace(agent='codex', project=None, output=str(out), cwd=None,
                         dry_run=False, coverage=True, since=None, until=None)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            cmd_bulk(args)
        self.assertIn('Coverage warning: 2 source file(s)', err.getvalue())
        report = json.loads((out / 'coverage.json').read_text())
        self.assertEqual(report['version'], 2)
        rows = {r['source_path']: r for r in report['sources']}
        self.assertEqual(rows[str(first)]['status'], 'exported')
        self.assertEqual(rows[str(first)]['record_counts']['unsupported'], 1)
        self.assertEqual(rows[str(second)]['status'], 'empty')
        self.assertEqual(rows[str(second)]['record_counts']['malformed'], 2)
        before = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        with patch.object(Path, 'mkdir', side_effect=AssertionError('Doctor attempted mkdir')), \
             patch.object(Path, 'write_text', side_effect=AssertionError('Doctor attempted write')):
            diagnosis = Doctor(out, agents=['codex']).run()
        after = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(diagnosis['exit_code'], 1)
        self.assertEqual(diagnosis['counts']['source_malformed'], 2)
        self.assertEqual(diagnosis['counts']['source_unsupported'], 1)
        warnings = [f for f in diagnosis['findings'] if f['code'] == 'source_record_coverage']
        self.assertEqual(len(warnings), 2)
        self.assertIn('2 malformed', render_doctor(diagnosis))
        self.assertNotIn('Synthetic example.', json.dumps(diagnosis))

    def test_known_ignored_events_do_not_trigger_coverage_warning(self):
        self.write('.codex/sessions/ignored.jsonl', [
            codex('response_item', type='reasoning'),
            codex('response_item', type='message', role='developer'),
            codex('event_msg', type='agent_reasoning'), codex('compacted')])
        diagnosis = Doctor(self.home / 'missing-exports', agents=['codex']).run()
        self.assertEqual(diagnosis['counts']['source_ignored'], 4)
        self.assertFalse(any(f['code'] == 'source_record_coverage' for f in diagnosis['findings']))


if __name__ == '__main__':
    unittest.main()
