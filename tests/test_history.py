"""Captured-handoff history with invented conversations and isolated state."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import pin_requirement, read_bundle_snapshot, review_requirement
from agent_sessions.cli import main
from agent_sessions.history import inspect_history, latest_changes, read_revision
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError
from agent_sessions.workspace import initialize_workspace, add_topic, resume_topic


class HistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'workspace'
        self.archive = self.root / 'exports'
        self.history = self.workspace / 'history/example'
        self.requirements = self.workspace / 'requirements/example.json'
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected home access'))
        home.start()
        self.addCleanup(home.stop)
        self.export('synthetic-scope', 'The example cache needs discovery.\n\nDiscovery only. Do not implement.')
        initialize_workspace(self.workspace, self.archive)
        add_topic(self.workspace, 'example', 'example cache')
        pin_requirement(self.archive, self.requirements, 'scope', 'synthetic-scope', 1,
                         'Discovery only.', unit='paragraph')

    def export(self, sid, text, agent=Agent.CODEX):
        session = Session(id=sid, agent=agent, messages=[Message(role='assistant', text=text)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def capture(self):
        return resume_topic(self.workspace, 'example')

    def challenge(self):
        self.export('synthetic-correction',
                    'Correction: Replace "Discovery only. Do not implement." with "Implementation is proposed next.".',
                    Agent.CURSOR)

    def test_unchanged_capture_deduplicates_without_rewriting_history_index(self):
        first, text = self.capture()
        index = self.history / 'history.json'
        before = index.read_bytes(), index.stat().st_mtime_ns
        again, same_text = self.capture()
        self.assertEqual(first['history']['revision'], again['history']['revision'])
        self.assertEqual(text, same_text)
        self.assertFalse(again['history']['changed'])
        self.assertEqual(again['history']['revision_count'], 1)
        self.assertEqual(before, (index.read_bytes(), index.stat().st_mtime_ns))

    def test_failed_review_keeps_the_prior_ready_snapshot_without_using_it(self):
        first, original = self.capture()
        ready_id = first['history']['revision']
        self.challenge()
        draft, _ = self.capture()
        self.assertFalse(draft['ready'])
        self.assertEqual(draft['history']['last_ready_revision'], ready_id)
        self.assertEqual(Path(draft['last_ready_handoff_path']).read_text(), original)
        changes = draft['history']['changes']
        self.assertEqual(changes['readiness_before'], True)
        self.assertEqual(changes['readiness_after'], False)
        self.assertEqual(changes['review_opened'][0]['witness']['agent'], 'cursor')
        with patch.object(sys, 'argv', ['agent-sessions', 'resume', 'example', '--print', '--workspace', str(self.workspace)]), \
             contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main()
        self.assertEqual(output.getvalue(), '')

    def test_review_note_changes_are_not_called_factual_resolution(self):
        self.capture()
        self.challenge()
        draft, _ = self.capture()
        candidate = draft['manifest']['requirements'][0]['unreviewed_candidates'][0]['review_id']
        review_requirement(self.archive, self.requirements, 'scope', candidate,
                           'Retain both historical statements. The replacement remains a proposal.')
        reviewed, _ = self.capture()
        changes = reviewed['history']['changes']
        self.assertTrue(reviewed['ready'])
        self.assertEqual(changes['review_no_longer_pending'][0]['reason'], 'review_note_recorded')
        self.assertEqual(reviewed['manifest']['verification'], 'not_checked')
        self.assertEqual(inspect_history(self.history)['last_ready'], reviewed['history']['revision'])

    def test_changed_evidence_and_actual_handoff_diff_remain_inspectable(self):
        first, original = self.capture()
        self.export('synthetic-scope', 'The example cache needs discovery.\n\nHypothetical example: Discovery only. Do not implement.')
        draft, _ = self.capture()
        self.assertFalse(draft['ready'])
        changes = latest_changes(self.history, include_diff=True)
        self.assertTrue(changes['historical'])
        self.assertEqual(changes['verification'], 'not_checked')
        self.assertEqual(changes['changes']['requirements_changed'][0]['status_after'], 'evidence_changed')
        self.assertIn('Hypothetical example:', changes['diff'])
        self.assertEqual(read_revision(self.history, first['history']['revision'])[0], original)

    def test_latest_bundle_can_be_repaired_from_a_new_capture_without_losing_history(self):
        first, original = self.capture()
        Path(first['handoff_path']).write_text('Damaged derived latest view.')
        repaired, _ = self.capture()
        self.assertEqual(Path(repaired['handoff_path']).read_text(), original)
        self.assertEqual(repaired['history']['revision_count'], 1)

    def test_corrupted_history_prevents_silent_overwrite(self):
        first, _ = self.capture()
        revision = self.history / first['history']['revision']
        (revision / 'handoff.md').write_text('Changed historical bytes.')
        index = (self.history / 'history.json').read_bytes()
        with self.assertRaises(StorageError):
            self.capture()
        self.assertEqual((self.history / 'history.json').read_bytes(), index)
        self.assertEqual((revision / 'handoff.md').read_text(), 'Changed historical bytes.')

    def test_snapshot_identity_checks_bytes_including_line_endings(self):
        first, _ = self.capture()
        revision = self.history / first['history']['revision']
        path = revision / 'handoff.md'
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        with self.assertRaises(StorageError):
            read_bundle_snapshot(revision)

    def test_missing_history_index_does_not_discard_existing_captures(self):
        self.capture()
        (self.history / 'history.json').unlink()
        with self.assertRaises(StorageError):
            self.capture()
        self.assertFalse((self.history / 'history.json').exists())

    def test_failed_index_commit_keeps_previous_head_and_can_retry(self):
        first, _ = self.capture()
        self.challenge()
        with patch('agent_sessions.history.atomic_write_text', side_effect=StorageError('Synthetic index write failure')):
            with self.assertRaises(StorageError):
                self.capture()
        self.assertEqual(inspect_history(self.history)['head'], first['history']['revision'])
        retried, _ = self.capture()
        self.assertFalse(retried['ready'])
        self.assertEqual(retried['history']['revision_count'], 2)

    def test_failed_latest_view_write_preserves_complete_history(self):
        first, original = self.capture()
        self.challenge()
        with patch('agent_sessions.workspace.write_bundle', side_effect=StorageError('Synthetic latest-view failure')):
            with self.assertRaises(StorageError):
                self.capture()
        history = inspect_history(self.history)
        self.assertNotEqual(history['head'], first['history']['revision'])
        self.assertFalse(read_revision(self.history, history['head'])[1]['ready'])
        self.assertEqual(read_revision(self.history, history['last_ready'])[0], original)
        self.assertEqual(Path(first['handoff_path']).read_text(), original)

    def test_readonly_history_views_and_no_history_listing_do_not_write(self):
        self.assertEqual(inspect_history(self.history)['revisions'], [])
        self.assertFalse(self.history.exists())
        self.capture()
        self.challenge()
        self.capture()
        before = {str(p): (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(Path, 'mkdir', side_effect=AssertionError('History reader attempted mkdir')), \
             patch.object(Path, 'write_text', side_effect=AssertionError('History reader attempted write')):
            history = inspect_history(self.history)
            latest_changes(self.history, include_diff=True)
            read_revision(self.history, history['last_ready'])
        after = {str(p): (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_concurrent_resumes_create_one_consistent_revision(self):
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: self.capture()[0], range(5)))
        ids = {item['history']['revision'] for item in results}
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(inspect_history(self.history)['revisions']), 1)
        read_bundle_snapshot(self.workspace / 'handoffs/example')

    def test_history_and_change_cli_views_retain_capture_labels(self):
        first, _ = self.capture()
        self.challenge()
        self.capture()

        def cli(arguments):
            with patch.object(sys, 'argv', ['agent-sessions', 'topic', *arguments, '--workspace', str(self.workspace)]), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                main()
            return output.getvalue()

        history = json.loads(cli(['history', 'example', '--json']))
        self.assertEqual(len(history['revisions']), 2)
        self.assertEqual(history['last_ready'], first['history']['revision'])
        changes = cli(['changes', 'example', '--diff'])
        self.assertIn('readiness_after: false', changes)
        self.assertIn('proposed_correction', changes)
        old = cli(['show', 'example', '--revision', first['history']['revision']])
        self.assertTrue(old.startswith('Historical capture.'))
        self.assertIn('Discovery only.', old)


if __name__ == '__main__':
    unittest.main()
