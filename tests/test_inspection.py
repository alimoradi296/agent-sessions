"""Persistent inspection queues must not confuse reads with operator notes."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import (
    load_requirements, note_source_inspection, pin_requirement, compile_handoff, write_bundle, audit_bundle,
)
from agent_sessions.analysis.inspection import inspection_report, render_inspection
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.workspace import initialize_workspace, add_topic, resume_topic

PROJECT = '/workspace/example-project'
ORIGINAL = 'Discovery only. Do not implement or publish.'


class InspectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive, self.requirements = self.root / 'exports', self.root / 'requirements.json'
        self.session = Session(id='synthetic-original', agent=Agent.CODEX, cwd=PROJECT,
                               messages=[Message(role='user', text=ORIGINAL)])
        self.write(self.session)
        pin_requirement(self.archive, self.requirements, 'scope', self.session.id, 1, ORIGINAL)
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected home access'))
        home.start()
        self.addCleanup(home.stop)

    def write(self, session):
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def report(self, **kwargs):
        return inspection_report(self.archive, load_requirements(self.requirements).get('source_inspections', []), **kwargs)

    def acknowledge(self, session=None):
        sid = session or self.session.id
        snapshot = self.report(session_id=sid)['selected_source']['inspection_id']
        return note_source_inspection(self.archive, self.requirements, sid, snapshot,
                                      'Read the current dialogue. This does not accept a proposed change.')

    def test_inspection_is_read_only_and_notes_do_not_prove_understanding(self):
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        report = self.report(session_id=self.session.id)
        self.assertEqual(report['pending'], 1)
        self.assertEqual(report['selected_source']['sections'][0]['text'], ORIGINAL)
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
        receipt = self.acknowledge()
        self.assertFalse(receipt['review_candidates_resolved'])
        self.assertEqual(self.report()['pending'], 0)
        self.assertEqual(self.report()['verification'], 'not_checked')

    def test_new_conversations_outside_the_query_are_queued_and_resume_does_not_clear_them(self):
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'example', 'example cache', requirements=self.requirements, projects=[PROJECT])
        self.acknowledge()
        self.write(Session(id='synthetic-reversal', agent=Agent.CURSOR, cwd=PROJECT,
                           messages=[Message(role='user', text='بررسی تمام شد. پیاده‌سازی مجاز است.')]))
        for _ in range(2):
            report, _ = resume_topic(workspace, 'example')
            self.assertTrue(report['ready'])
            self.assertEqual(report['manifest']['source_inspection']['pending'], 1)
        source = next(item for item in self.report()['sources'] if item['session_id'] == 'synthetic-reversal')
        self.assertEqual(source['status'], 'uninspected')

    def test_changed_source_requires_a_new_note_and_shows_only_new_complete_sections(self):
        self.acknowledge()
        self.session.messages.append(Message(role='user', text='A proposed scope change requires discussion.'))
        self.write(self.session)
        report = self.report(session_id=self.session.id, changed_only=True)
        self.assertEqual(report['sources'][0]['status'], 'changed')
        self.assertEqual(len(report['selected_source']['sections']), 1)
        self.assertEqual(report['selected_source']['sections'][0]['section'], 2)
        self.assertFalse(report['selected_source']['sections'][0]['unchanged_since_note'])
        self.acknowledge()
        self.assertEqual(self.report()['pending'], 0)

    def test_stale_bytes_and_changed_metadata_snapshots_are_rejected_without_writes(self):
        snapshot = self.report(session_id=self.session.id)['selected_source']['inspection_id']
        before = self.requirements.read_bytes()
        self.session.messages.append(Message(role='user', text='An update.'))
        self.write(self.session)
        with self.assertRaises(ValueError):
            note_source_inspection(self.archive, self.requirements, self.session.id, snapshot, 'Stale.')
        self.assertEqual(self.requirements.read_bytes(), before)
        snapshot = self.report(session_id=self.session.id)['selected_source']['inspection_id']
        index = self.archive / 'sessions.json'
        rows = json.loads(index.read_text())
        rows['sessions'][0]['cwd'] = '/workspace/other-project'
        index.write_text(json.dumps(rows))
        with self.assertRaises(ValueError):
            note_source_inspection(self.archive, self.requirements, self.session.id, snapshot, 'Stale metadata.')
        self.assertEqual(self.requirements.read_bytes(), before)

    def test_current_note_reopens_on_metadata_changes(self):
        self.acknowledge()
        index = self.archive / 'sessions.json'
        rows = json.loads(index.read_text())
        rows['sessions'][0]['agent'] = 'cursor'
        index.write_text(json.dumps(rows))
        self.assertEqual(self.report()['sources'][0]['status'], 'metadata_changed')
        self.assertEqual(self.report()['pending'], 1)

    def test_changed_only_counts_removed_and_duplicate_sections_without_inventing_old_text(self):
        self.session.messages.append(Message(role='user', text='An old qualification.'))
        self.write(self.session)
        self.acknowledge()
        self.session.messages = [Message(role='user', text=ORIGINAL), Message(role='user', text=ORIGINAL)]
        self.write(self.session)
        source = self.report(session_id=self.session.id, changed_only=True)['selected_source']
        self.assertEqual(len(source['sections']), 1)
        self.assertEqual(source['sections'][0]['section'], 2)
        self.assertEqual(source['removed_sections'], 1)
        self.assertFalse(source['prior_text_available'])

    def test_missing_files_stay_pending_and_excluded_contents_are_never_read(self):
        other = Session(id='synthetic-other', agent=Agent.CURSOR, cwd='/workspace/other-project',
                        messages=[Message(role='user', text='Unrelated private-marker-example.')])
        self.write(other)
        (self.archive / 'synthetic-other.md').write_bytes(b'\xff not dialogue')
        original_read = Path.read_bytes
        def read(path):
            if path.name == 'synthetic-other.md':
                raise AssertionError('Excluded source contents were read')
            return original_read(path)
        with patch.object(Path, 'read_bytes', read):
            report = self.report(projects=[PROJECT])
        self.assertEqual(len(report['sources']), 1)
        self.assertEqual(report['scope']['excluded_sources'], 1)
        with self.assertRaises(ValueError):
            self.report(session_id=other.id, projects=[PROJECT])
        (self.archive / f'{self.session.id}.md').unlink()
        self.assertEqual(self.report(projects=[PROJECT])['sources'][0]['status'], 'unavailable')

    def test_acknowledging_a_source_never_resolves_recognized_challenges(self):
        correction = Session(id='synthetic-correction', agent=Agent.CURSOR, cwd=PROJECT,
                             messages=[Message(role='user', text=f'Replace "{ORIGINAL}" with "Implementation is proposed next.".')])
        self.write(correction)
        self.acknowledge()
        self.acknowledge(correction.id)
        _, manifest = compile_handoff(self.archive, 'example cache', self.requirements)
        self.assertEqual(manifest['source_inspection']['pending'], 0)
        self.assertFalse(manifest['review_passed'])
        self.assertFalse(manifest['ready'])

    def test_audit_labels_captured_inspection_counts_as_historical_after_new_unselected_source(self):
        self.acknowledge()
        text, manifest = compile_handoff(self.archive, 'example cache', self.requirements)
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.write(Session(id='synthetic-new', agent=Agent.CODEX, cwd=PROJECT,
                           messages=[Message(role='user', text='A separate instruction to inspect.')]))
        audit = audit_bundle(bundle, self.archive)
        self.assertEqual(audit['exit_code'], 0)
        self.assertIn('inspection_queue_snapshot_changed', {note['code'] for note in audit['notes']})

    def test_invalid_note_state_fails_without_resetting_the_queue(self):
        self.acknowledge()
        contract = json.loads(self.requirements.read_text())
        contract['source_inspections'].append(contract['source_inspections'][0])
        self.requirements.write_text(json.dumps(contract))
        with self.assertRaises(ValueError):
            load_requirements(self.requirements)
        with self.assertRaises(ValueError):
            inspection_report(self.archive, [], changed_only=True)

    def test_cli_reports_acknowledges_and_preserves_queue_changes_in_history(self):
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'example', 'example cache', requirements=self.requirements)

        def cli(args):
            out = io.StringIO()
            with patch.object(sys, 'argv', ['agent-sessions', *args, '--workspace', str(workspace), '--json']), \
                    contextlib.redirect_stdout(out):
                main()
            return json.loads(out.getvalue())

        first, _ = resume_topic(workspace, 'example')
        report = cli(['topic', 'inspect', 'example', '--session', self.session.id])
        snapshot = report['selected_source']['inspection_id']
        cli(['topic', 'acknowledge', 'example', '--session', self.session.id, '--snapshot', snapshot,
             '--note', 'Read source, with no factual verification.'])
        second, _ = resume_topic(workspace, 'example')
        self.assertTrue(second['history']['changes']['inspection_queue_changed'])
        self.assertEqual(second['manifest']['source_inspection']['pending'], 0)
        self.assertEqual(first['manifest']['source_inspection']['pending'], 1)
        self.session.messages.append(Message(role='user', text='A later qualification.'))
        self.write(self.session)
        third, _ = resume_topic(workspace, 'example')
        self.assertEqual(third['manifest']['source_inspection']['pending'], 1)
        self.assertEqual(third['history']['changes']['inspection_updates'][0]['after'], 'changed')

    def test_no_current_sections_does_not_clear_changes_outside_cleaned_dialogue(self):
        self.acknowledge()
        source = self.archive / f'{self.session.id}.md'
        source.write_text(source.read_text() + '\n\n> A changed quoted example outside cleaned dialogue.\n')
        report = self.report(session_id=self.session.id, changed_only=True)
        self.assertEqual(report['pending'], 1)
        self.assertEqual(report['selected_source']['sections'], [])
        self.assertTrue(report['selected_source']['changes']['full_view_recommended'])

    def test_surviving_section_order_changes_are_visible_even_without_new_text(self):
        self.session.messages.extend([Message(role='user', text='First qualification.'),
                                      Message(role='user', text='Second qualification.')])
        self.write(self.session)
        self.acknowledge()
        self.session.messages[1], self.session.messages[2] = self.session.messages[2], self.session.messages[1]
        self.write(self.session)
        report = self.report(session_id=self.session.id, changed_only=True)
        view = report['selected_source']
        self.assertEqual(view['sections'], [])
        self.assertTrue(view['changes']['surviving_section_order_changed'])
        self.assertTrue(view['changes']['full_view_recommended'])
        self.assertFalse(view['changes']['correctness_or_relevance_established'])
        self.assertIn('Full view recommended:', render_inspection(report))

    def test_an_append_does_not_report_a_change_in_surviving_section_order(self):
        self.acknowledge()
        self.session.messages.append(Message(role='user', text='An unrelated appendix.'))
        self.write(self.session)
        view = self.report(session_id=self.session.id, changed_only=True)['selected_source']
        self.assertFalse(view['changes']['surviving_section_order_changed'])
        self.assertFalse(view['changes']['full_view_recommended'])
        self.assertEqual(view['changes']['new_or_changed_sections'], 1)

    def test_duplicate_matches_do_not_establish_which_occurrence_moved_or_disappeared(self):
        self.session.messages.extend([Message(role='user', text='Repeated qualification.'),
                                      Message(role='user', text='Different qualification.'),
                                      Message(role='user', text='Repeated qualification.')])
        self.write(self.session)
        self.acknowledge()
        self.session.messages.pop(1)
        self.write(self.session)
        report = self.report(session_id=self.session.id, changed_only=True)
        changes = report['selected_source']['changes']
        self.assertFalse(changes['surviving_section_order_changed'])
        self.assertTrue(changes['section_order_ambiguous'])
        self.assertTrue(changes['full_view_recommended'])
        self.assertIn('Repeated sections', render_inspection(report))


if __name__ == '__main__':
    unittest.main()
