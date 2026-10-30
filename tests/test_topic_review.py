"""Refreshing generated selections must preserve manual work and old captures."""

import contextlib
import io
import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import pin_requirement, link_challenge, review_requirement, load_requirements
from agent_sessions.cli import main
from agent_sessions.history import read_revision
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError
from agent_sessions.topic_review import prepare_topic_review, import_topic_review, mutate_topic_requirements
from agent_sessions.workspace import initialize_workspace, add_topic, get_topic, resume_topic, set_topic

PROJECT = '/workspace/example-project'
SCOPE = 'Discovery only. Do not implement or publish.'
TIMING = 'The timing is a proposed target, not a guarantee.'


class TopicReviewTests(unittest.TestCase):
    def test_over_budget_preparation_preserves_active_topic_and_capture_files(self):
        self.refresh()
        report, _ = resume_topic(self.workspace, 'example')
        self.assertTrue(report['ready'])
        before = {str(p.relative_to(self.workspace)): p.read_bytes() for p in self.workspace.rglob('*') if p.is_file()}
        result = prepare_topic_review(self.workspace, 'example', batch_review=True,
                                      compact_review=True, max_total_prompt_chars=1)
        self.assertEqual(result['status'], 'over_budget')
        self.assertIsNone(result['output'])
        after = {str(p.relative_to(self.workspace)): p.read_bytes() for p in self.workspace.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive, self.workspace = self.root / 'exports', self.root / 'workspace'
        self.manual = self.root / 'manual.json'
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE)
        self.export('synthetic-timing', 'The example cache timing needs care.\n\n' + TIMING)
        initialize_workspace(self.workspace, self.archive)
        add_topic(self.workspace, 'example', 'example cache', projects=[PROJECT])
        self.sequence = 0
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access'))
        home.start()
        self.addCleanup(home.stop)

    def export(self, sid, body):
        session = Session(id=sid, agent=Agent.CODEX, cwd=PROJECT, messages=[Message(role='user', text=body)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def prepare(self, selections=None, conflict=False):
        self.sequence += 1
        prepared = prepare_topic_review(self.workspace, 'example')
        packet = Path(prepared['output'])
        answer = self.root / f'answer-{self.sequence}.json'
        choices = selections if selections is not None else [('synthetic-scope', SCOPE)]
        answer.write_text(json.dumps(dict(review_id=prepared['review_id'], selected=[dict(session_id=sid, quote=quote, reason='Synthetic source selection.')
                                                    for sid, quote in choices],
                                         unresolved_conflicts=conflict, current_authorization='read_only')))
        return packet, answer

    def refresh(self, selections=None, conflict=False):
        packet, answer = self.prepare(selections, conflict)
        return import_topic_review(self.workspace, 'example', packet, answer)

    def current(self):
        return Path(get_topic(self.workspace, 'example')[2]['requirements'])

    def test_first_import_needs_no_manual_pin_and_retains_contract_capture(self):
        result = self.refresh()
        self.assertEqual(result['preserved_requirements'], 0)
        self.assertEqual(result['generated_requirements'], 1)
        self.assertTrue(self.current().is_file())
        self.assertEqual(Path(result['contract_captures'][0]).read_bytes(), self.current().read_bytes())
        report, _ = resume_topic(self.workspace, 'example')
        self.assertTrue(report['ready'])

    def test_external_manual_file_and_pin_survive_generated_refresh(self):
        pin_requirement(self.archive, self.manual, 'manual-scope', 'synthetic-scope', 1, SCOPE, unit='paragraph')
        set_topic(self.workspace, 'example', query='example cache')
        config = self.workspace / 'workspace.json'
        data = json.loads(config.read_text())
        data['topics']['example']['requirements'] = str(self.manual)
        config.write_text(json.dumps(data))
        original = self.manual.read_bytes()
        first = self.refresh([('synthetic-timing', TIMING)])
        old_active = self.current()
        old_bytes = old_active.read_bytes()
        previous, previous_text = resume_topic(self.workspace, 'example')
        second = self.refresh([('synthetic-scope', SCOPE)])
        ids = {item['id'] for item in load_requirements(self.current())['requirements']}
        self.assertIn('manual-scope', ids)
        self.assertEqual(second['preserved_requirements'], 1)
        self.assertEqual(self.manual.read_bytes(), original)
        self.assertEqual(old_active.read_bytes(), old_bytes)
        self.assertNotEqual(first['requirements_path'], second['requirements_path'])
        historical, _ = read_revision(self.workspace / 'history/example', previous['history']['revision'])
        self.assertEqual(historical, previous_text)

    def test_manual_pins_added_to_active_contract_survive_next_refresh(self):
        self.refresh()
        mutate_topic_requirements(self.workspace, 'example', lambda archive, path, topic:
                                  pin_requirement(archive, path, 'manual-timing', 'synthetic-timing', 1, TIMING, unit='paragraph'))
        result = self.refresh()
        self.assertEqual(result['preserved_requirements'], 1)
        self.assertIn('manual-timing', {item['id'] for item in load_requirements(self.current())['requirements']})

    def test_manual_links_keep_their_generated_target_when_new_selection_omits_it(self):
        correction = f'Replace "{SCOPE}" with "Implementation is proposed next.".'
        self.export('synthetic-challenge', correction)
        self.refresh()
        target = load_requirements(self.current())['requirements'][0]['id']
        mutate_topic_requirements(self.workspace, 'example', lambda archive, path, topic:
                                  link_challenge(archive, path, 'manual-link', target, 'synthetic-challenge', 1,
                                                 correction, 'Keep this reported challenge visible.', projects=[PROJECT]))
        self.refresh([('synthetic-timing', TIMING)])
        ids = {item['id'] for item in load_requirements(self.current())['requirements']}
        self.assertTrue({target, 'manual-link'} <= ids)

    def test_unchanged_generated_evidence_keeps_candidate_review_notes(self):
        self.export('synthetic-challenge', f'Replace "{SCOPE}" with "Implementation is proposed next.".')
        self.refresh()
        draft, _ = resume_topic(self.workspace, 'example')
        item = draft['manifest']['requirements'][0]
        candidate = item['unreviewed_candidates'][0]['review_id']
        mutate_topic_requirements(self.workspace, 'example', lambda archive, path, topic:
                                  review_requirement(archive, path, item['id'], candidate,
                                                     'Keep both statements. No implementation approval is inferred.', projects=[PROJECT]))
        before = load_requirements(self.current())['requirements'][0]['reviewed_candidates']
        self.refresh()
        after = load_requirements(self.current())['requirements'][0]['reviewed_candidates']
        self.assertEqual(before, after)
        self.assertTrue(resume_topic(self.workspace, 'example')[0]['ready'])

    def test_changed_topic_or_stale_sources_do_not_switch_the_active_contract(self):
        self.refresh()
        previous = self.current()
        packet, answer = self.prepare()
        set_topic(self.workspace, 'example', query='another topic')
        with self.assertRaises(ValueError):
            import_topic_review(self.workspace, 'example', packet, answer)
        self.assertEqual(self.current(), previous)
        set_topic(self.workspace, 'example', query='example cache')
        packet, answer = self.prepare()
        self.export('synthetic-new', 'A new historical instruction for the example cache.')
        with self.assertRaises(ValueError):
            import_topic_review(self.workspace, 'example', packet, answer)
        self.assertEqual(self.current(), previous)

    def test_damaged_contract_capture_prevents_silent_replacement(self):
        result = self.refresh()
        current = self.current()
        Path(result['contract_captures'][0]).write_text('Damaged capture.')
        with self.assertRaises(StorageError):
            self.refresh()
        self.assertEqual(self.current(), current)
        self.assertEqual(Path(result['contract_captures'][0]).read_text(), 'Damaged capture.')

    def test_failed_config_commit_preserves_original_pointer_and_bytes(self):
        from agent_sessions import topic_review
        self.refresh()
        previous = self.current()
        original_bytes = previous.read_bytes()
        packet, answer = self.prepare([('synthetic-timing', TIMING)])
        original_write = topic_review.atomic_write_text
        def write(path, text):
            if path == self.workspace / 'workspace.json':
                raise OSError('Synthetic config commit failure')
            return original_write(path, text)
        with patch.object(topic_review, 'atomic_write_text', write):
            with self.assertRaises(OSError):
                import_topic_review(self.workspace, 'example', packet, answer)
        self.assertEqual(self.current(), previous)
        self.assertEqual(previous.read_bytes(), original_bytes)

    def test_pin_waiting_for_refresh_resolves_the_new_active_file(self):
        from agent_sessions import topic_review
        self.refresh()
        previous = self.current()
        packet, answer = self.prepare([('synthetic-timing', TIMING)])
        reached, release, pin_started = threading.Event(), threading.Event(), threading.Event()
        original_capture = topic_review._capture
        def capture(*args):
            if not reached.is_set():
                reached.set()
                if not release.wait(5):
                    raise AssertionError('Refresh test release timed out')
            return original_capture(*args)
        def pin():
            pin_started.set()
            return mutate_topic_requirements(self.workspace, 'example', lambda archive, path, topic:
                                             pin_requirement(archive, path, 'concurrent-manual', 'synthetic-scope', 1, SCOPE))
        with patch.object(topic_review, '_capture', capture), ThreadPoolExecutor(max_workers=2) as executor:
            refresh = executor.submit(import_topic_review, self.workspace, 'example', packet, answer)
            self.assertTrue(reached.wait(5))
            pending_pin = executor.submit(pin)
            self.assertTrue(pin_started.wait(5))
            release.set()
            refresh.result(timeout=5)
            pending_pin.result(timeout=5)
        self.assertIn('concurrent-manual', {item['id'] for item in load_requirements(self.current())['requirements']})
        self.assertNotIn('concurrent-manual', {item['id'] for item in load_requirements(previous)['requirements']})

    def test_topic_cli_prepares_and_imports_without_user_pin_work(self):
        def cli(args):
            output = io.StringIO()
            with patch.object(sys, 'argv', ['agent-sessions', *args, '--workspace', str(self.workspace), '--json']), \
                    contextlib.redirect_stdout(output):
                main()
            return json.loads(output.getvalue())
        prepared = cli(['topic', 'prepare-review', 'example', '--batch-review'])
        packet = json.loads((Path(prepared['output']) / 'review-packet.json').read_text())
        answer = self.root / 'cli-answer.json'
        answer.write_text(json.dumps(dict(review_id=prepared['review_id'], selected=[dict(session_id='synthetic-scope', quote=SCOPE, reason='Synthetic selection.')],
                                         unresolved_conflicts=False, current_authorization='read_only', reviewed_batches=list(packet['batches']))))
        result = cli(['topic', 'import-review', 'example', prepared['output'], '--answer', str(answer)])
        self.assertEqual(result['generated_requirements'], 1)
        self.assertTrue(cli(['resume', 'example'])['ready'])

    def test_identical_review_does_not_switch_pointer_or_rewrite_current_files(self):
        self.refresh()
        active = self.current()
        config = self.workspace / 'workspace.json'
        original = (active.read_bytes(), active.stat().st_mtime_ns, config.read_bytes(), config.stat().st_mtime_ns)
        result = self.refresh()
        self.assertFalse(result['changed'])
        self.assertEqual(self.current(), active)
        self.assertEqual((active.read_bytes(), active.stat().st_mtime_ns, config.read_bytes(), config.stat().st_mtime_ns), original)
        self.assertEqual(len(result['contract_captures']), 1)

    def test_legacy_or_manually_protected_anchor_is_not_replaced_by_new_meaning(self):
        self.refresh()
        path = self.current()
        old = load_requirements(path)
        old['requirements'][0].pop('selection_origin')
        path.write_text(json.dumps(old))
        original = path.read_bytes()
        replacement = 'Implementation is proposed next.'
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n' + replacement)
        with self.assertRaises(ValueError):
            self.refresh([('synthetic-scope', replacement)])
        self.assertEqual(self.current(), path)
        self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
