"""Reconciliation uses synthetic sources in a temporary, isolated home."""

import contextlib
import hashlib
import io
import sys
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_sessions.parsers.codex import CodexParser
from agent_sessions.reconcile import reconcile
from agent_sessions.storage import InvalidIndexError, StorageError, directory_lock

SID = '55555555-5555-4555-8555-555555555555'
OTHER = '66666666-6666-4666-8666-666666666666'


def events(sid=SID, text='Inspect the synthetic example.'):
    return [dict(type='session_meta', timestamp='2026-02-03T10:00:00Z',
                 payload=dict(id=sid, cwd='/workspace/example')),
            dict(type='response_item', timestamp='2026-02-03T10:00:01Z',
                 payload=dict(type='message', role='user',
                              content=[dict(type='input_text', text=text)]))]


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        home_patch = patch.object(Path, 'home', return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.source = self.home / '.codex/sessions/2026/02/03/example.jsonl'
        self.source.parent.mkdir(parents=True)
        self.write(self.source, events())
        self.out = self.home / 'exports'

    def write(self, path, rows):
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')

    def run_reconcile(self, **kwargs):
        return reconcile(self.out, ['codex'], **kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.stat().st_mtime_ns,
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
                for p in self.home.rglob('*')}

    def test_dry_run_is_read_only_even_when_output_is_absent(self):
        before = self.snapshot()
        with patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir')), \
             patch('agent_sessions.reconcile.atomic_write_many', side_effect=AssertionError('write')):
            report = self.run_reconcile(dry_run=True)
        self.assertEqual(report['counts']['would_export'], 1)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn('Inspect the synthetic example.', json.dumps(report))
        self.assertFalse(self.out.exists())

    def test_rerun_leaves_all_export_files_untouched(self):
        self.assertEqual(self.run_reconcile()['counts']['exported'], 1)
        files = [self.out / name for name in (f'{SID}.md', 'sessions.json', 'SESSION_INDEX.md')]
        before = [(p.stat().st_mtime_ns, p.read_bytes()) for p in files]
        self.assertEqual(self.run_reconcile()['counts']['unchanged'], 1)
        self.assertEqual(before, [(p.stat().st_mtime_ns, p.read_bytes()) for p in files])
        self.assertEqual(json.loads((self.out / 'reconcile.json').read_text())['exit_code'], 0)

    def test_same_size_content_change_with_old_mtime_is_detected(self):
        self.run_reconcile()
        stat = self.source.stat()
        text = self.source.read_text().replace('synthetic', 'invented!')
        self.source.write_text(text)
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report = self.run_reconcile()
        self.assertEqual(report['counts']['exported'], 1)
        self.assertIn('invented!', (self.out / f'{SID}.md').read_text())

    def test_resumed_files_are_merged_and_source_paths_updated(self):
        self.run_reconcile()
        resume = self.source.with_name('resume.jsonl')
        self.write(resume, events(text='A resumed synthetic request.'))
        report = self.run_reconcile()
        self.assertEqual(report['counts']['exported'], 1)
        index = json.loads((self.out / 'sessions.json').read_text())
        self.assertEqual(index['count'], 1)
        self.assertEqual(index['sessions'][0]['message_count'], 2)
        self.assertEqual(len(index['sessions'][0]['source_paths']), 2)
        self.assertEqual(self.run_reconcile()['counts']['unchanged'], 1)

    def test_partial_replacement_failure_is_repaired_on_retry(self):
        self.run_reconcile()
        self.write(self.source, events() + events(text='A changed synthetic request.')[1:])
        replace = os.replace
        def interrupt(src, dst):
            if Path(dst).name == 'sessions.json':
                raise OSError('synthetic interruption')
            return replace(src, dst)
        with patch('agent_sessions.storage.os.replace', side_effect=interrupt):
            with self.assertRaises(StorageError):
                self.run_reconcile()
        self.assertEqual(self.run_reconcile()['counts']['exported'], 1)
        self.assertEqual(self.run_reconcile()['counts']['unchanged'], 1)
        self.assertEqual(json.loads((self.out / 'sessions.json').read_text())['sessions'][0]['message_count'], 2)

    def test_missing_transcript_and_missing_index_row_are_recovered(self):
        self.run_reconcile()
        (self.out / f'{SID}.md').unlink()
        self.assertEqual(self.run_reconcile()['counts']['exported'], 1)
        index = self.out / 'SESSION_INDEX.md'
        index.write_text('\n'.join(line for line in index.read_text().splitlines() if SID not in line) + '\n')
        self.assertEqual(self.run_reconcile()['counts']['exported'], 1)
        self.assertEqual(self.run_reconcile()['counts']['unchanged'], 1)

    def test_unavailable_source_entries_are_preserved(self):
        other = self.source.with_name('other.jsonl')
        self.write(other, events(OTHER))
        self.run_reconcile()
        other.unlink()
        before = (self.out / f'{OTHER}.md').read_bytes()
        self.write(self.source, events(text='A new synthetic request.'))
        self.run_reconcile()
        self.assertEqual(json.loads((self.out / 'sessions.json').read_text())['count'], 2)
        self.assertEqual(before, (self.out / f'{OTHER}.md').read_bytes())
        self.assertIn(OTHER, (self.out / 'SESSION_INDEX.md').read_text())

    def test_invalid_indexes_stop_before_replacing_any_files(self):
        self.run_reconcile()
        for name in ('sessions.json', 'SESSION_INDEX.md'):
            with self.subTest(name=name):
                path = self.out / name
                original = path.read_bytes()
                path.write_text('invalid')
                before = self.snapshot()
                with self.assertRaises(InvalidIndexError):
                    self.run_reconcile()
                self.assertEqual(before, self.snapshot())
                path.write_bytes(original)

    def test_missing_index_requires_explicit_restoration(self):
        self.run_reconcile()
        (self.out / 'SESSION_INDEX.md').unlink()
        before = self.snapshot()
        with self.assertRaises(InvalidIndexError):
            self.run_reconcile()
        self.assertEqual(before, self.snapshot())

    def test_source_errors_and_empty_sources_are_reported(self):
        self.write(self.source.with_name('empty.jsonl'), events(OTHER)[:1])
        with patch.object(CodexParser, 'parse_many', side_effect=PermissionError):
            report = self.run_reconcile()
        self.assertEqual(report['exit_code'], 1)
        self.assertEqual(report['counts']['error'], 2)
        self.assertEqual(self.run_reconcile()['counts']['empty'], 1)
        with patch.object(CodexParser, 'list_sessions', side_effect=PermissionError):
            self.assertEqual(self.run_reconcile()['exit_code'], 1)
        self.assertEqual(reconcile(self.out, ['cursor'])['exit_code'], 1)
        self.assertEqual(reconcile(self.out)['exit_code'], 0)

    def test_source_changes_during_parse_are_deferred(self):
        parse = CodexParser.parse_many
        def changing(paths):
            session = parse(paths)
            self.write(paths[0], events(text='A later request in the active source.'))
            return session
        with patch.object(CodexParser, 'parse_many', side_effect=changing):
            report = self.run_reconcile()
        self.assertEqual(report['sources'][0]['error_type'], 'SourceChangedDuringRead')
        self.assertFalse((self.out / f'{SID}.md').exists())
        self.assertEqual(self.run_reconcile()['counts']['exported'], 1)

    def test_lock_prevents_concurrent_reconciliation(self):
        with directory_lock(self.out):
            with self.assertRaises(StorageError):
                self.run_reconcile(lock_timeout=0)
        self.assertFalse((self.out / 'sessions.json').exists())

    def test_cli_defaults_to_private_output_and_returns_source_errors(self):
        from agent_sessions.cli import main
        argv = ['agent-sessions', 'reconcile', '--agent', 'codex', '--dry-run', '--json']
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()) as output:
            main()
        report = json.loads(output.getvalue())
        self.assertEqual(report['directory'], str(self.home / '.agent-sessions/exports'))
        self.assertEqual(report['counts']['would_export'], 1)
        self.assertFalse((self.home / '.agent-sessions').exists())
        with patch.object(sys, 'argv', argv), \
             patch.object(CodexParser, 'list_sessions', side_effect=PermissionError), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue())['exit_code'], 1)

    def test_cross_agent_id_collision_is_reported_in_dry_and_real_runs(self):
        cursor = self.home / '.cursor/projects/example/agent-transcripts' / SID / f'{SID}.jsonl'
        cursor.parent.mkdir(parents=True)
        self.write(cursor, [dict(role='user', message=dict(content='A synthetic Cursor request.'))])
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run):
                report = reconcile(self.out, ['codex', 'cursor'], dry_run=dry_run)
                self.assertEqual(report['counts']['error'], 1)
                self.assertEqual(report['sources'][-1]['error_type'], 'SessionIdCollision')
        self.assertIn('**Agent:** codex', (self.out / f'{SID}.md').read_text())

    def test_cursor_and_claude_use_shared_reconciliation(self):
        cursor = self.home / '.cursor/projects/example/agent-transcripts' / SID / f'{SID}.jsonl'
        cursor.parent.mkdir(parents=True)
        self.write(cursor, [dict(role='user', message=dict(content='A synthetic Cursor request.'))])
        self.assertEqual(reconcile(self.out, ['cursor'])['counts']['exported'], 1)
        self.assertEqual(reconcile(self.out, ['cursor'])['counts']['unchanged'], 1)
        claude = self.home / '.claude/projects/example' / f'{OTHER}.jsonl'
        claude.parent.mkdir(parents=True)
        self.write(claude, [dict(type='user', sessionId=OTHER, cwd='/workspace/example',
                                 timestamp='2026-02-03T10:00:00Z',
                                 message=dict(role='user', content='A synthetic Claude request.'))])
        self.assertEqual(reconcile(self.out, ['claude'])['counts']['exported'], 1)
        self.assertEqual(reconcile(self.out, ['claude'])['counts']['unchanged'], 1)


if __name__ == '__main__':
    unittest.main()
