"""Private repeat-use workflows with synthetic data and an isolated filesystem."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError
from agent_sessions.workspace import initialize_workspace, add_topic, load_workspace, resume_topic


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'private-workspace'
        self.archive = self.root / 'exports'
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected developer home access'))
        home.start()
        self.addCleanup(home.stop)

    def cli(self, args, expected=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['agent-sessions', *args, '--workspace', str(self.workspace)]), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        self.assertEqual(code, expected, stderr.getvalue() + stdout.getvalue())
        return stdout.getvalue(), stderr.getvalue()

    def export(self, sid='synthetic-scope', text='Discovery only. Do not implement.', agent=Agent.CODEX):
        session = Session(id=sid, agent=agent, messages=[Message(role='assistant', text=text)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def setup_topic(self):
        self.export()
        self.cli(['init', '--archive', str(self.archive)])
        self.cli(['topic', 'add', 'example', '--query', 'example cache'])

    def pin(self):
        self.cli(['topic', 'pin', 'example', '--id', 'scope', '--session', 'synthetic-scope',
                  '--section', '1', '--quote', 'Discovery only.', '--unit', 'paragraph'])

    def test_complete_cli_workflow_and_cross_agent_review(self):
        self.setup_topic()
        self.pin()
        search, _ = self.cli(['topic', 'search', 'example', 'discovery', '--json'])
        self.assertEqual(json.loads(search)['hits'][0]['session_id'], 'synthetic-scope')
        text, _ = self.cli(['resume', 'example', '--print'])
        self.assertIn('Discovery only.', text)
        self.assertIn('All extracted claims are not checked.', text)
        manifest_path = self.workspace / 'handoffs/example/manifest.json'
        self.assertTrue(json.loads(manifest_path.read_text())['ready'])
        self.export('synthetic-correction',
                    'Correction: Replace "Discovery only. Do not implement." with "Implementation is proposed next.".',
                    Agent.CURSOR)
        stdout, stderr = self.cli(['resume', 'example', '--print'], expected=1)
        self.assertEqual(stdout, '')
        self.assertIn('review candidate', stderr)
        manifest = json.loads(manifest_path.read_text())
        candidate = manifest['requirements'][0]['unreviewed_candidates'][0]['review_id']
        self.cli(['topic', 'review', 'example', '--id', 'scope', '--candidate', candidate,
                  '--note', 'Preserve both statements. The replacement remains an unapproved proposal.'])
        output, _ = self.cli(['resume', 'example', '--json'])
        resumed = json.loads(output)
        self.assertTrue(resumed['ready'])
        self.assertEqual(resumed['manifest']['verification'], 'not_checked')
        self.assertIn('Operator note', Path(resumed['handoff_path']).read_text())

    def test_initialization_does_not_discover_or_create_the_archive(self):
        config = initialize_workspace(self.workspace, self.archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual(config['archive'], str(self.archive))
        path = self.workspace / 'workspace.json'
        before = path.read_bytes(), path.stat().st_mtime_ns
        initialize_workspace(self.workspace, self.archive)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
        if os.name == 'posix':
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.workspace.stat().st_mode & 0o777, 0o700)

    def test_topic_search_can_return_raw_message_locators(self):
        self.setup_topic()
        text, _ = self.cli(['topic', 'search', 'example', 'discovery', '--view', 'evidence', '--json'])
        result = json.loads(text)
        self.assertEqual(result['view'], 'evidence')
        self.assertTrue(result['hits'])
        self.assertIn('message', result['hits'][0])
        self.assertNotIn('section', result['hits'][0])

    def test_initialization_can_retry_after_a_failed_first_write(self):
        with patch('agent_sessions.workspace.atomic_write_text', side_effect=StorageError('Synthetic write failure')):
            with self.assertRaises(StorageError):
                initialize_workspace(self.workspace, self.archive)
        self.assertTrue((self.workspace / '.agent-sessions.lock').is_file())
        self.assertFalse((self.workspace / 'workspace.json').exists())
        config = initialize_workspace(self.workspace, self.archive)
        self.assertEqual(config['archive'], str(self.archive))
        self.assertTrue((self.workspace / 'workspace.json').is_file())

    def test_readonly_listing_and_missing_workspace_create_nothing(self):
        self.cli(['topic', 'list'], expected=1)
        self.assertFalse(self.workspace.exists())
        self.setup_topic()
        before = {str(p): (p.stat().st_mtime_ns, p.read_bytes())
                  for p in self.root.rglob('*') if p.is_file()}
        with patch.object(Path, 'mkdir', side_effect=AssertionError('List attempted a write')):
            output, _ = self.cli(['topic', 'list', '--json'])
        self.assertEqual(json.loads(output)['example']['query'], 'example cache')
        after = {str(p): (p.stat().st_mtime_ns, p.read_bytes())
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_workspace_refuses_git_checkouts_and_occupied_directories(self):
        repository = self.root / 'public-repository'
        (repository / '.git').mkdir(parents=True)
        (repository / '.git/HEAD').write_text('ref: refs/heads/main\n')
        (repository / '.git/objects').mkdir()
        with self.assertRaises(StorageError):
            initialize_workspace(repository / 'private-data', self.archive)
        self.assertFalse((repository / 'private-data').exists())
        occupied = self.root / 'occupied'
        occupied.mkdir()
        (occupied / 'existing.txt').write_text('Keep existing data.')
        with self.assertRaises(StorageError):
            initialize_workspace(occupied, self.archive)
        self.assertEqual((occupied / 'existing.txt').read_text(), 'Keep existing data.')

    def test_bad_names_duplicate_topics_and_invalid_config_preserve_state(self):
        initialize_workspace(self.workspace, self.archive)
        add_topic(self.workspace, 'example', 'example cache')
        config_path = self.workspace / 'workspace.json'
        before = config_path.read_bytes()
        for name in ('../escape', 'Uppercase', 'a/b', '', 'a' * 65):
            with self.assertRaises(ValueError):
                add_topic(self.workspace, name, 'example')
        with self.assertRaises(ValueError):
            add_topic(self.workspace, 'example', 'replacement')
        self.assertEqual(config_path.read_bytes(), before)
        config_path.write_text('{broken')
        with self.assertRaises(ValueError):
            add_topic(self.workspace, 'other', 'other query')
        self.assertEqual(config_path.read_text(), '{broken')

    def test_concurrent_topic_updates_keep_all_topics(self):
        initialize_workspace(self.workspace, self.archive)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(add_topic, self.workspace, f'topic-{i}', f'query {i}') for i in range(12)]
            for future in futures:
                future.result()
        _, config = load_workspace(self.workspace)
        self.assertEqual(len(config['topics']), 12)

    def test_missing_requirements_do_not_create_a_handoff(self):
        self.setup_topic()
        self.cli(['resume', 'example'], expected=1)
        self.assertFalse((self.workspace / 'handoffs').exists())

    def test_topic_limits_and_query_can_change_without_replacing_pins(self):
        self.setup_topic()
        self.pin()
        requirements = self.workspace / 'requirements/example.json'
        before = requirements.read_bytes()
        self.cli(['topic', 'set', 'example', '--query', 'discovery', '--max-total-chars', '5000'])
        _, config = load_workspace(self.workspace)
        self.assertEqual(config['topics']['example']['query'], 'discovery')
        self.assertEqual(config['topics']['example']['limits']['max_total_chars'], 5000)
        self.assertEqual(requirements.read_bytes(), before)
        self.cli(['resume', 'example'])

    def test_managed_symlinks_do_not_redirect_private_writes(self):
        self.setup_topic()
        outside = self.root / 'outside'
        outside.mkdir()
        (self.workspace / 'requirements').symlink_to(outside, target_is_directory=True)
        self.cli(['topic', 'pin', 'example', '--id', 'scope', '--session', 'synthetic-scope', '--section', '1'], expected=1)
        self.assertFalse(list(outside.iterdir()))

    def test_requirements_changes_during_resume_do_not_publish_a_stale_bundle(self):
        self.setup_topic()
        self.pin()
        from agent_sessions.analysis.continuity import compile_handoff

        def changing_compile(*args, **kwargs):
            result = compile_handoff(*args, **kwargs)
            requirements = Path(args[2])
            requirements.write_text(requirements.read_text() + ' ')
            return result

        with patch('agent_sessions.workspace.compile_handoff', side_effect=changing_compile):
            with self.assertRaises(StorageError):
                resume_topic(self.workspace, 'example')
        self.assertFalse((self.workspace / 'handoffs').exists())

    def test_saved_settings_changes_during_resume_require_a_retry(self):
        self.setup_topic()
        self.pin()
        from agent_sessions.analysis.continuity import compile_handoff

        def changing_compile(*args, **kwargs):
            result = compile_handoff(*args, **kwargs)
            add_topic(self.workspace, 'another-topic', 'another query')
            return result

        with patch('agent_sessions.workspace.compile_handoff', side_effect=changing_compile):
            with self.assertRaises(StorageError):
                resume_topic(self.workspace, 'example')
        self.assertFalse((self.workspace / 'handoffs').exists())


if __name__ == '__main__':
    unittest.main()
