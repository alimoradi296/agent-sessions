"""Hook installation and execution tests with an isolated synthetic home."""

import contextlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.doctor import Doctor
from agent_sessions.cli import main
from agent_sessions.hook_setup import HookSetupError, install_hooks

ROOT = Path(__file__).resolve().parents[1]
SID = '55555555-5555-4555-8555-555555555555'
OTHER = '66666666-6666-4666-8666-666666666666'

# The child patches Path.home instead of changing HOME. It runs the actual
# generated launcher from an unrelated directory, without importing this repo
# through the working directory or a test-only PYTHONPATH.
DRIVER = '''
import runpy,sys
from pathlib import Path
from unittest.mock import patch
home, script = sys.argv[1:3]
sys.argv = [script]
with patch.object(Path, 'home', return_value=Path(home)):
    runpy.run_path(script, run_name='__main__')
'''


@unittest.skipUnless(os.name == 'posix', 'POSIX hook installer')
class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agent-sessions-hooks-test-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home with 'quotes' and $characters"
        self.home.mkdir()
        self.out = Path(self.tmp.name) / 'private exports'
        self.unrelated = Path(self.tmp.name) / 'unrelated workspace'
        (self.unrelated / 'docs').mkdir(parents=True)
        home_patch = patch.object(Path, 'home', return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def write_config(self, agent, data):
        path = self.home / f'.{agent}/hooks.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    def transcript(self, agent, sid=SID):
        if agent == 'cursor':
            path = self.home / f'.cursor/projects/example/agent-transcripts/{sid}/{sid}.jsonl'
            records = [
                {'role': 'user', 'message': {'content': [{'type': 'text', 'text': 'Inspect the synthetic example.'}]}},
                {'role': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'The synthetic example is complete.'}]}},
            ]
        else:
            path = self.home / f'.codex/sessions/2026/02/03/rollout-{sid}.jsonl'
            records = [
                {'type': 'session_meta', 'timestamp': '2026-02-03T10:00:00Z', 'payload': {'id': sid}},
                {'type': 'response_item', 'timestamp': '2026-02-03T10:00:01Z', 'payload': {
                    'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Synthetic example request.'}]}},
            ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(json.dumps(record) for record in records) + '\n')
        return path

    def run_hook(self, script, payload):
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, '-c', DRIVER, str(self.home), str(script)],
                              input=json.dumps(payload), text=True, capture_output=True,
                              cwd=self.unrelated, env=environment, timeout=20)

    def test_launchers_export_both_payload_formats_outside_checkout(self):
        for agent in ('codex', 'cursor'):
            with self.subTest(agent=agent):
                path = self.transcript(agent)
                result = install_hooks(agent, output=self.out / agent)
                config = json.loads(Path(result['config_path']).read_text())
                handler = config['hooks']['Stop'][0]['hooks'][0] if agent == 'codex' else config['hooks']['stop'][0]
                self.assertEqual(shlex.split(handler['command']), [sys.executable, result['script_path']])
                payload = {'session_id' if agent == 'codex' else 'conversation_id': SID,
                           'hook_event_name': 'Stop' if agent == 'codex' else 'stop',
                           'transcript_path': str(path), 'workspace_roots': [str(self.unrelated)]}
                process = self.run_hook(result['script_path'], payload)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(process.stdout, '{}\n')
                self.assertEqual(process.stderr, '')
                index = json.loads((self.out / agent / 'sessions.json').read_text())
                self.assertEqual(index['sessions'][0]['agent'], agent)
                self.assertEqual(index['sessions'][0]['id'], SID)
                self.assertFalse((self.unrelated / 'docs/sessions').exists())
                self.assertEqual(index['sessions'][0]['message_count'], 1 if agent == 'codex' else 2)

    def test_codex_payload_keeps_resumed_segments(self):
        path = self.transcript('codex')
        resume = path.with_name('resume.jsonl')
        resume.write_text(path.read_text() + json.dumps({
            'type': 'response_item', 'timestamp': '2026-02-03T10:00:02Z',
            'payload': {'type': 'message', 'role': 'assistant',
                        'content': [{'type': 'output_text', 'text': 'Synthetic resumed result.'}]}}) + '\n')
        result = install_hooks('codex', output=self.out)
        process = self.run_hook(result['script_path'], {'session_id': SID, 'transcript_path': str(path)})
        self.assertEqual(process.returncode, 0, process.stderr)
        row = json.loads((self.out / 'sessions.json').read_text())['sessions'][0]
        self.assertEqual(row['message_count'], 2)
        self.assertEqual(len(row['source_paths']), 2)

    def test_cursor_migration_preserves_unrelated_entries_and_is_idempotent(self):
        old = './hooks/export-session.sh'
        unrelated = {'command': 'echo preserve-this-hook', 'timeout': 7}
        mentioning = {'command': 'echo ' + shlex.quote(str(self.home / '.cursor/hooks/export-session.sh'))}
        module_mention = {'command': 'echo python3 -m agent_sessions hook --agent cursor'}
        original = {'version': 1, 'description': 'Synthetic user configuration',
                    'hooks': {'agent-end': [{'command': old}, unrelated],
                              'stop': [{'command': old}, mentioning, module_mention],
                              'beforeSubmitPrompt': [unrelated]}}
        config = self.write_config('cursor', original)
        result = install_hooks('cursor', output=self.out)
        data = json.loads(config.read_text())
        self.assertEqual(data['hooks']['agent-end'], [unrelated])
        self.assertIn(mentioning, data['hooks']['stop'])
        self.assertIn(module_mention, data['hooks']['stop'])
        self.assertEqual(data['hooks']['beforeSubmitPrompt'], [unrelated])
        self.assertEqual(data['description'], original['description'])
        self.assertEqual(json.loads(Path(result['backups'][0]).read_text()), original)
        before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in config.parent.rglob('*') if p.is_file()}
        again = install_hooks('cursor', output=self.out)
        self.assertFalse(again['changed'])
        self.assertEqual(again['backups'], [])
        after = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in config.parent.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_codex_mixed_handler_group_keeps_other_commands(self):
        other = {'type': 'command', 'command': 'echo another-handler'}
        self.write_config('codex', {'description': 'Synthetic config', 'hooks': {'Stop': [
            {'matcher': 'custom', 'hooks': [other, {'type': 'command',
              'command': 'bash ' + shlex.quote(str(self.home / '.codex/hooks/export-session.sh'))}]}]}})
        result = install_hooks('codex', output=self.out)
        data = json.loads(Path(result['config_path']).read_text())
        self.assertEqual(data['hooks']['Stop'][0], {'matcher': 'custom', 'hooks': [other]})
        self.assertEqual(len(data['hooks']['Stop']), 2)
        self.assertNotIn('async', data['hooks']['Stop'][1]['hooks'][0])

    def test_legacy_manual_module_commands_migrate_without_duplicates(self):
        for command in ('python3 -m agent_sessions hook',
                        'python3 -m agent_sessions hook --agent=cursor'):
            with self.subTest(command=command):
                self.write_config('cursor', {'version': 1, 'hooks': {'agent-end': [{'command': command}]}})
                result = install_hooks('cursor', output=self.out)
                data = json.loads(Path(result['config_path']).read_text())
                self.assertNotIn('agent-end', data['hooks'])
                self.assertEqual(len(data['hooks']['stop']), 1)

    def test_unrelated_cursor_prompt_hooks_are_preserved(self):
        prompt = {'type': 'prompt', 'prompt': 'Check the synthetic example.'}
        self.write_config('cursor', {'version': 1, 'hooks': {'stop': [prompt]}})
        result = install_hooks('cursor', output=self.out)
        data = json.loads(Path(result['config_path']).read_text())
        self.assertEqual(data['hooks']['stop'][0], prompt)
        self.assertEqual(len(data['hooks']['stop']), 2)

    def test_invalid_config_fails_without_replacing_script_or_config(self):
        for agent in ('codex', 'cursor'):
            path = self.write_config(agent, {})
            script = path.parent / 'hooks/agent-sessions-export.py'
            script.parent.mkdir()
            script.write_text('# Synthetic previous launcher\n')
            for invalid in ['{broken', 'null', '{"hooks": []}', '{"hooks": {"stop": "bad", "Stop": "bad"}}']:
                with self.subTest(agent=agent, invalid=invalid):
                    path.write_text(invalid)
                    with self.assertRaises(HookSetupError):
                        install_hooks(agent)
                    self.assertEqual(path.read_text(), invalid)
                    self.assertEqual(script.read_text(), '# Synthetic previous launcher\n')
            self.assertFalse(list(path.parent.rglob('*.agent-sessions-backup-*')))

    def test_dry_run_creates_nothing(self):
        for agent in ('codex', 'cursor'):
            result = install_hooks(agent, output=self.out, dry_run=True)
            self.assertTrue(result['dry_run'])
            self.assertFalse((self.home / f'.{agent}').exists())
        self.assertFalse(self.out.exists())

    def test_invalid_payload_mismatched_id_and_unsupported_sources_fail(self):
        path = self.transcript('cursor')
        result = install_hooks('cursor', output=self.out)
        for payload in [[], {}, {'conversation_id': '../escape'},
                        {'conversation_id': OTHER, 'transcript_path': str(path)},
                        {'conversation_id': SID, 'transcript_path': ['invalid']},
                        {'conversation_id': OTHER, 'transcript_path': str(path.with_suffix('.txt'))}]:
            with self.subTest(payload=payload):
                process = self.run_hook(result['script_path'], payload)
                self.assertEqual(process.returncode, 1)
                self.assertEqual(process.stdout, '')
                self.assertNotIn('Traceback', process.stderr)
        self.assertFalse(self.out.exists())

    def test_cursor_id_precedence_null_hint_and_default_private_output(self):
        self.transcript('cursor')
        with patch.object(sys, 'argv', ['agent-sessions', 'hook', '--agent', 'cursor']), \
             patch.object(sys, 'stdin', io.StringIO(json.dumps({
                 'conversation_id': SID, 'session_id': OTHER, 'transcript_path': None,
                 'cwd': str(self.unrelated)}))), contextlib.redirect_stdout(io.StringIO()) as output:
            main()
        self.assertEqual(output.getvalue(), '{}\n')
        self.assertTrue((self.home / '.agent-sessions/exports' / f'{SID}.md').exists())
        self.assertFalse((self.unrelated / 'docs/sessions').exists())

    def test_text_transcript_hint_falls_back_to_jsonl_discovery(self):
        path = self.transcript('cursor')
        result = install_hooks('cursor', output=self.out)
        process = self.run_hook(result['script_path'], {
            'conversation_id': SID, 'transcript_path': str(path.with_suffix('.txt'))})
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, '{}\n')
        self.assertTrue((self.out / f'{SID}.md').is_file())

    def test_doctor_recognizes_python_launcher_but_not_lifecycle_execution(self):
        install_hooks('cursor', output=self.out)
        doctor = Doctor(self.out, agents=['cursor'])
        doctor.check_hooks('cursor')
        self.assertIn('hook_export_reference', {f['code'] for f in doctor.findings})
        self.assertFalse(any(f['level'] in ('warning', 'error') for f in doctor.findings))
        self.assertTrue(any('unverified' in f['message'] for f in doctor.findings))


if __name__ == '__main__':
    unittest.main()
