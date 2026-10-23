"""Doctor checks use invented transcripts and an isolated temporary home."""

import contextlib
import hashlib
import io
import json
import os
import shlex
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.doctor import Doctor
from agent_sessions.cli import cmd_doctor, export_session
from agent_sessions.parsers.codex import CodexParser

SID = '33333333-3333-4333-8333-333333333333'


def synthetic_events():
    return [
        {'type': 'session_meta', 'timestamp': '2026-02-03T10:00:00Z',
         'payload': {'id': SID, 'cwd': '/workspace/example'}},
        {'type': 'response_item', 'timestamp': '2026-02-03T10:00:01Z',
         'payload': {'type': 'message', 'role': 'user',
                     'content': [{'type': 'input_text', 'text': 'Inspect the synthetic example.'}]}},
    ]


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        home_patch = patch.object(Path, 'home', return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.source = self.home / '.codex/sessions/2026/02/03/example.jsonl'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('\n'.join(json.dumps(e) for e in synthetic_events()) + '\n')
        self.out = self.home / 'exports'
        with contextlib.redirect_stdout(io.StringIO()):
            export_session(CodexParser.parse(self.source), self.out)

    def run_doctor(self, agents=None):
        return Doctor(self.out, agents=['codex'] if agents is None else agents).run()

    @staticmethod
    def codes(report):
        return {finding['code'] for finding in report['findings']}

    def edit_index(self, update):
        path = self.out / 'sessions.json'
        data = json.loads(path.read_text())
        update(data)
        path.write_text(json.dumps(data))

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.stat().st_mtime_ns,
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
                for p in self.home.rglob('*')}

    def test_consistent_archive_passes_without_writes_or_hook_execution(self):
        sentinel = self.home / 'must-not-exist'
        script = self.home / 'hook example.sh'
        script.write_text(f'#!/bin/sh\ntouch {shlex.quote(str(sentinel))}\n# agent-sessions export codex\n')
        config = self.home / '.codex/hooks.json'
        config.write_text(json.dumps({'hooks': {'Stop': [{'hooks': [
            {'command': f'bash {shlex.quote(str(script))}'}]}]}}))
        before = self.snapshot()
        with patch.object(Path, 'mkdir', side_effect=AssertionError('Doctor attempted mkdir')), \
             patch.object(Path, 'write_text', side_effect=AssertionError('Doctor attempted write')):
            report = self.run_doctor()
        self.assertEqual(report['exit_code'], 0)
        self.assertEqual(report['counts']['source_sessions'], 1)
        self.assertIn('hook_export_reference', self.codes(report))
        self.assertIn('hook_runtime_unverified', self.codes(report))
        self.assertFalse(sentinel.exists())
        self.assertEqual(before, self.snapshot())
        self.assertNotIn('Inspect the synthetic example.', json.dumps(report))
        self.assertNotIn('touch ', json.dumps(report))

    def test_missing_default_export_directory_is_not_created_by_cli(self):
        with contextlib.redirect_stdout(io.StringIO()) as output, \
             patch('agent_sessions.cli.resolve_output_dir', side_effect=AssertionError('Creates output')):
            with self.assertRaises(SystemExit) as error:
                cmd_doctor(Namespace(directory=None, agent='codex', project_dir=None, json=True))
        report = json.loads(output.getvalue())
        self.assertEqual(error.exception.code, 1)
        self.assertIn('export_directory_missing', self.codes(report))
        self.assertFalse((self.home / '.agent-sessions').exists())

    def test_missing_export_and_stale_resumed_source_are_detected(self):
        resume = self.source.with_name('resume.jsonl')
        resume.write_text(self.source.read_text())
        newest = (self.out / f'{SID}.md').stat().st_mtime_ns + 1_000_000
        os.utime(resume, ns=(newest, newest))
        report = self.run_doctor()
        self.assertIn('stale_export', self.codes(report))
        self.assertEqual(report['counts']['source_files'], 2)
        self.assertEqual(report['counts']['source_sessions'], 1)
        self.edit_index(lambda d: d.update(count=0, sessions=[]))
        report = self.run_doctor()
        self.assertIn('missing_export', self.codes(report))
        self.assertIn('unindexed_markdown', self.codes(report))

    def test_metadata_counts_duplicate_ids_and_missing_transcript(self):
        def corrupt(data):
            data['count'] = 99
            data['sessions'][0]['message_count'] = 99
            data['sessions'][0]['user_messages'] = 99
            data['sessions'].append(dict(data['sessions'][0]))
        self.edit_index(corrupt)
        report = self.run_doctor()
        self.assertTrue({'json_index_count', 'duplicate_index_id', 'source_message_counts',
                         'transcript_message_counts'} <= self.codes(report))
        path = self.out / f'{SID}.md'
        path.write_text(path.read_text().replace('**Agent:** codex', '**Agent:** cursor'))
        self.assertIn('transcript_metadata', self.codes(self.run_doctor()))
        path.unlink()
        self.assertIn('transcript_unreadable', self.codes(self.run_doctor()))

    def test_invalid_index_shapes_and_json_fail(self):
        index = self.out / 'sessions.json'
        for value in ['{broken', 'null', '42', '{"sessions": {}}']:
            with self.subTest(value=value):
                index.write_text(value)
                report = self.run_doctor()
                self.assertEqual(report['exit_code'], 1)
                self.assertTrue({'json_index_unreadable', 'json_index_shape'} & self.codes(report))
                self.assertNotIn('missing_export', self.codes(report))

    def test_unsafe_index_path_is_rejected(self):
        self.edit_index(lambda d: d['sessions'][0].update(id='../../outside', file='../../outside.md'))
        self.assertIn('json_index_entry', self.codes(self.run_doctor()))

    def test_markdown_index_missing_duplicate_and_orphan_links(self):
        path = self.out / 'SESSION_INDEX.md'
        text = path.read_text()
        entry = next(line for line in text.splitlines() if f'[{SID}.md]' in line)
        path.write_text(text + entry + '\n' + '| x | [orphan.md](orphan.md) |\n')
        report = self.run_doctor()
        self.assertIn('markdown_index_entry', self.codes(report))
        self.assertIn('markdown_index_orphan', self.codes(report))
        path.unlink()
        self.assertIn('markdown_index_unreadable', self.codes(self.run_doctor()))

    def test_empty_sources_and_uninstalled_optional_agents(self):
        empty = synthetic_events()[0]
        empty['payload']['id'] = '44444444-4444-4444-8444-444444444444'
        self.source.with_name('empty.jsonl').write_text(json.dumps(empty) + '\n')
        report = self.run_doctor(agents=['claude', 'codex'])
        self.assertEqual(report['counts']['sources_without_messages'], 1)
        self.assertNotIn('missing_export', self.codes(report))
        report = Doctor(self.out).run()
        absent = [f for f in report['findings'] if f['code'] == 'source_directory_missing']
        self.assertTrue(absent)
        self.assertTrue(all(f['level'] == 'info' for f in absent))
        self.assertEqual(report['exit_code'], 0)

    def test_discovery_and_parse_read_failures_are_errors(self):
        with patch.object(CodexParser, 'list_sessions', side_effect=PermissionError):
            self.assertIn('source_discovery_failed', self.codes(self.run_doctor()))
        with patch.object(CodexParser, 'parse_many', side_effect=PermissionError):
            self.assertIn('source_parse_failed', self.codes(self.run_doctor()))

    def test_hook_missing_script_invalid_config_and_disabled_setting(self):
        path = self.home / '.codex/hooks.json'
        path.write_text(json.dumps({'disableAllHooks': True, 'hooks': {'Stop': [
            {'hooks': [{'command': f'bash {self.home}/missing.sh'}]}]}}))
        report = self.run_doctor()
        self.assertIn('hooks_disabled', self.codes(report))
        self.assertIn('hook_script_unreadable', self.codes(report))
        for invalid in ['{broken', 'null', '{"hooks": []}', '{"hooks": {"Stop": "bad"}}']:
            with self.subTest(config=invalid):
                path.write_text(invalid)
                report = self.run_doctor()
                self.assertEqual(report['exit_code'], 1)
                self.assertTrue({'hook_config_unreadable', 'hook_config_shape'} & self.codes(report))

    def test_project_cursor_config_and_legacy_list_index(self):
        index = self.out / 'sessions.json'
        index.write_text(json.dumps(json.loads(index.read_text())['sessions']))
        config = self.home / 'project/.cursor/hooks.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'hooks': {'stop': [
            {'command': 'python3 -m agent_sessions hook --agent cursor'}]}}))
        report = Doctor(self.out, agents=['codex', 'cursor'], project_dir=self.home / 'project').run()
        references = [f for f in report['findings'] if f['code'] == 'hook_export_reference']
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]['agent'], 'cursor')


if __name__ == '__main__':
    unittest.main()
