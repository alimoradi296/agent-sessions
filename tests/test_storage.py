"""Synthetic process-concurrency and interrupted-write regression tests."""

import contextlib
import errno
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.doctor import Doctor
from agent_sessions.cli import export_session, main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.index import IndexRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.storage import InvalidIndexError, StorageError, directory_lock

ROOT = Path(__file__).resolve().parents[1]

WORKER = r'''
import sys
from pathlib import Path
from agent_sessions.cli import export_session
from agent_sessions.models import Agent, Message, Session
print('ready', flush=True)
export_session(Session(id=sys.argv[2], agent=Agent.CODEX,
    title='Synthetic | example\nSecond line',
    messages=[Message(role='user', text='Inspect the example.')]),
    Path(sys.argv[1]), lock_timeout=15)
'''

INTERRUPTED_WORKER = r'''
import os
import sys
from pathlib import Path
from unittest.mock import patch
from agent_sessions import storage
from agent_sessions.cli import export_session
from agent_sessions.models import Agent, Message, Session
original = os.replace
count = 0
def pause_before_replace(source, destination):
    global count
    count += 1
    if count == int(sys.argv[3]):
        print('staged', flush=True)
        sys.stdin.read(1)
    return original(source, destination)
with patch.object(storage.os, 'replace', side_effect=pause_before_replace):
    export_session(Session(id=sys.argv[2], agent=Agent.CODEX,
        messages=[Message(role='assistant', text='Synthetic complete response.')]), Path(sys.argv[1]))
'''


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agent-sessions-test-')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'exports'
        self.processes = []
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def start(self, script, *args):
        process = subprocess.Popen([sys.executable, '-c', script, *(str(arg) for arg in args)],
                                   cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        return process

    def export(self, sid='synthetic-old'):
        session = Session(id=sid, agent=Agent.CODEX,
                          messages=[Message(role='user', text='Synthetic request.')])
        with contextlib.redirect_stdout(io.StringIO()):
            export_session(session, self.out)
        return session

    def destinations(self):
        return {path.name: path.read_bytes() for path in self.out.iterdir()
                if path.name.endswith('.md') or path.name == 'sessions.json'}

    def test_concurrent_processes_keep_every_session_in_both_indexes(self):
        ids = [f'synthetic-shared-prefix-{i}' for i in range(6)]
        with directory_lock(self.out):
            processes = [self.start(WORKER, self.out, sid) for sid in ids]
            for process in processes:
                self.assertEqual(process.stdout.readline().strip(), 'ready')
        for process in processes:
            _, error = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, error)
        data = json.loads((self.out / 'sessions.json').read_text())
        self.assertEqual(data['count'], len(ids))
        self.assertEqual({entry['id'] for entry in data['sessions']}, set(ids))
        md_index = (self.out / 'SESSION_INDEX.md').read_text()
        for sid in ids:
            self.assertEqual(md_index.count(f'[{sid}.md]({sid}.md)'), 1)
            self.assertTrue((self.out / f'{sid}.md').exists())
        self.assertEqual(len([line for line in md_index.splitlines() if line.startswith('| `')]), len(ids))
        self.assertIn('&#124;', md_index)
        self.assertEqual(Doctor(self.out, agents=[]).run()['exit_code'], 0)

    def test_invalid_indexes_never_replace_existing_destinations(self):
        self.export()
        index_path = self.out / 'sessions.json'
        valid_json = index_path.read_text()
        md_index = self.out / 'SESSION_INDEX.md'
        valid_md = md_index.read_text()
        for invalid in ['{broken', 'null', '{"count": 1, "sessions": []}',
                        '{"sessions": [null]}']:
            with self.subTest(index=invalid):
                index_path.write_text(invalid)
                before = self.destinations()
                with patch('agent_sessions.storage.os.replace') as replace:
                    with self.assertRaises(InvalidIndexError):
                        self.export('synthetic-new')
                replace.assert_not_called()
                self.assertEqual(before, self.destinations())
        index_path.write_text(valid_json)
        for invalid in ['', '# broken index\n', valid_md + 'broken row\n']:
            with self.subTest(markdown=invalid):
                md_index.write_text(invalid)
                before = self.destinations()
                with self.assertRaises(InvalidIndexError):
                    self.export('synthetic-new')
                self.assertEqual(before, self.destinations())
        self.assertFalse(list(self.out.glob('.agent-sessions-*.tmp')))

    def test_duplicate_json_ids_and_agent_collisions_are_rejected(self):
        session = self.export()
        path = self.out / 'sessions.json'
        data = json.loads(path.read_text())
        row = data['sessions'][0]
        path.write_text(json.dumps([row, row]))
        with self.assertRaises(InvalidIndexError):
            self.export('synthetic-new')
        path.write_text(json.dumps([row]))
        session.agent = Agent.CURSOR
        with self.assertRaises(InvalidIndexError):
            JsonIndexRenderer.update(session, path)

    def test_legacy_list_index_and_full_id_updates_preserve_other_entries(self):
        self.export('synthetic-same-prefix-a')
        path = self.out / 'sessions.json'
        path.write_text(json.dumps(json.loads(path.read_text())['sessions']))
        session = self.export('synthetic-same-prefix-b')
        session.title = 'Updated synthetic title'
        IndexRenderer.update(session, self.out / 'SESSION_INDEX.md')
        JsonIndexRenderer.update(session, path)
        self.assertEqual(json.loads(path.read_text())['count'], 2)
        text = (self.out / 'SESSION_INDEX.md').read_text()
        self.assertEqual(text.count('[synthetic-same-prefix-a.md]'), 1)
        self.assertEqual(text.count('[synthetic-same-prefix-b.md]'), 1)

    def test_staging_failure_leaves_old_files_and_cleans_temporary_files(self):
        self.export()
        before = self.destinations()
        with patch('agent_sessions.storage.os.fsync', side_effect=OSError(errno.ENOSPC, 'synthetic disk full')):
            with self.assertRaisesRegex(StorageError, 'No destination files were replaced'):
                self.export('synthetic-new')
        self.assertEqual(before, self.destinations())
        self.assertFalse(list(self.out.glob('.agent-sessions-*.tmp')))
        self.export('synthetic-new')  # failure released the lock

    def test_replacement_failure_is_detectable_and_retry_restores_consistency(self):
        self.export()
        original = os.replace
        count = 0
        def fail_second(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError(errno.EIO, 'synthetic replacement failure')
            return original(source, destination)
        with patch('agent_sessions.storage.os.replace', side_effect=fail_second):
            with self.assertRaisesRegex(StorageError, 'Run doctor and retry'):
                self.export('synthetic-new')
        self.assertEqual(json.loads((self.out / 'sessions.json').read_text())['count'], 1)
        self.assertIn('Synthetic request.', (self.out / 'synthetic-new.md').read_text())
        report = Doctor(self.out, agents=[]).run()
        self.assertIn('unindexed_markdown', {finding['code'] for finding in report['findings']})
        self.assertFalse(list(self.out.glob('.agent-sessions-*.tmp')))
        self.export('synthetic-new')
        self.assertEqual(Doctor(self.out, agents=[]).run()['exit_code'], 0)

    def test_unencodable_transcript_preserves_previous_exports(self):
        self.export()
        before = self.destinations()
        session = Session(id='synthetic-unicode', agent=Agent.CODEX,
                          messages=[Message(role='user', text='Synthetic invalid Unicode: \ud800')])
        with self.assertRaisesRegex(StorageError, 'UnicodeEncodeError'):
            export_session(session, self.out)
        self.assertEqual(before, self.destinations())
        self.assertFalse(list(self.out.glob('.agent-sessions-*.tmp')))

    def test_process_death_releases_lock_and_keeps_files_complete(self):
        for replacement in (1, 2):
            with self.subTest(replacement=replacement):
                self.out = Path(self.tmp.name) / f'interrupted-{replacement}'
                self.export()
                before = self.destinations()
                process = self.start(INTERRUPTED_WORKER, self.out, 'synthetic-new', replacement)
                self.assertEqual(process.stdout.readline().strip(), 'staged')
                process.kill()
                process.communicate(timeout=5)
                self.assertEqual(json.loads((self.out / 'sessions.json').read_text())['count'], 1)
                if replacement == 1:
                    self.assertEqual(before, self.destinations())
                else:
                    self.assertIn('Synthetic complete response.', (self.out / 'synthetic-new.md').read_text())
                with directory_lock(self.out, timeout=0):
                    pass
                self.export('synthetic-new')
                self.assertEqual(Doctor(self.out, agents=[]).run()['exit_code'], 0)

    def test_cli_timeout_is_clear_and_does_not_write_destinations(self):
        session = Session(id='synthetic-timeout', agent=Agent.CODEX)
        with directory_lock(self.out), patch('agent_sessions.cli.load_source_session', return_value=session), \
             patch.object(sys, 'argv', ['agent-sessions', 'export', 'codex', session.id,
                   '-o', str(self.out), '--lock-timeout', '0']), \
             contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as result:
                main()
        self.assertEqual(result.exception.code, 1)
        self.assertIn('Timed out waiting for the export lock', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())
        self.assertEqual(self.destinations(), {})

    def test_invalid_timeout_values_are_argument_errors(self):
        for value in ('-1', 'nan', 'inf'):
            with self.subTest(value=value), patch.object(sys, 'argv', [
                    'agent-sessions', 'bulk', '-o', str(self.out), '--lock-timeout', value]), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.out.exists())

    def test_invalid_session_id_and_dry_run_create_nothing(self):
        session = Session(id='../escape', agent=Agent.CODEX)
        with self.assertRaises(StorageError):
            export_session(session, self.out)
        self.assertFalse(self.out.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            export_session(Session(id='synthetic-dry-run', agent=Agent.CODEX), self.out, dry_run=True)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
