"""Operator-linked challenges preserve exact evidence without semantic inference."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import (
    audit_bundle, compile_handoff, link_challenge, load_requirements,
    pin_requirement, review_requirement, write_bundle,
)
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.workspace import initialize_workspace, add_topic, resume_topic

ORIGINAL = 'Discovery only. Do not implement or publish.'
REVERSAL = 'بررسی تمام شد. اکنون اجازه داری پیاده‌سازی و انتشار را انجام دهی.'
PROJECT = '/workspace/example-project'


class OperatorLinkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive, self.requirements = self.root / 'exports', self.root / 'requirements.json'
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected home access'))
        home.start()
        self.addCleanup(home.stop)
        self.original = self.export('synthetic-original', [ORIGINAL])
        self.challenge = self.export('synthetic-challenge', [REVERSAL])
        pin_requirement(self.archive, self.requirements, 'scope', self.original.id, 1, ORIGINAL)

    def export(self, sid, texts, agent=Agent.CODEX, cwd=PROJECT):
        session = Session(id=sid, agent=agent, cwd=cwd,
                          messages=[Message(role='user', text=text) for text in texts])
        self.write(session)
        return session

    def write(self, session):
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def link(self, **kwargs):
        return link_challenge(self.archive, self.requirements, 'reversal', 'scope', self.challenge.id,
                              1, REVERSAL, 'This instruction reverses the pinned scope restriction.', **kwargs)

    def build(self, **kwargs):
        return compile_handoff(self.archive, 'example cache', self.requirements, **kwargs)

    def candidate(self):
        return self.build()[1]['requirements'][0]['unreviewed_candidates'][0]['review_id']

    def review(self):
        review_requirement(self.archive, self.requirements, 'scope', self.candidate(),
                           'Retain both statements. Acceptance and authority remain unresolved.')

    def test_unrecognized_reversal_is_retained_and_blocks_until_explicit_review(self):
        self.assertTrue(self.build()[1]['ready'])
        self.link()
        text, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['review_passed'])
        self.assertFalse(manifest['ready'])
        self.assertIn(ORIGINAL, text)
        self.assertIn(REVERSAL, text)
        self.assertIn('Paraphrases and other languages can be missed', text)
        self.assertEqual(manifest['requirements'][0]['unreviewed_candidates'][0]['kind'], 'operator_linked_challenge')
        self.review()
        text, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertEqual(manifest['verification'], 'not_checked')
        self.assertIn('Acceptance and authority remain unresolved.', text)
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 0)

    def test_unreviewed_link_audit_fails_and_reviewed_changed_link_does_not_pass(self):
        self.link()
        text, manifest = self.build()
        bundle = self.root / 'draft'
        write_bundle(bundle, text, manifest)
        codes = {item['code'] for item in audit_bundle(bundle, self.archive)['findings']}
        self.assertIn('operator_link_requires_review', codes)
        self.review()
        text, manifest = self.build()
        write_bundle(bundle, text, manifest)
        self.challenge.messages[0].text += ' A further qualification applies.'
        self.write(self.challenge)
        self.assertFalse(self.build()[1]['ready'])
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 1)
        with self.assertRaises(ValueError):
            review_requirement(self.archive, self.requirements, 'scope', manifest['requirements'][0]['review_candidates'][0]['review_id'],
                               'A stale review must fail.')

    def test_linked_evidence_is_mandatory_under_source_and_character_budgets(self):
        self.link()
        self.review()
        for options in (dict(last=1), dict(max_chars=10), dict(max_total_chars=100)):
            with self.subTest(options=options):
                self.assertFalse(self.build(**options)[1]['ready'])
        self.assertEqual(self.build(last=1)[1]['requirements'][1]['status'], 'source_limit_exceeded')

    def test_unrelated_appends_and_unique_relocation_preserve_the_review_identity(self):
        self.link()
        identifier = self.candidate()
        self.review()
        self.challenge.messages.append(Message(role='assistant', text='A separate naming question remains.'))
        self.write(self.challenge)
        self.assertTrue(self.build()[1]['ready'])
        self.challenge.messages.insert(0, Message(role='user', text='An unrelated preface.'))
        self.write(self.challenge)
        _, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['review_candidates'][0]['review_id'], identifier)

    def test_changed_link_reason_reopens_review(self):
        self.link()
        identifier = self.candidate()
        self.review()
        contract = json.loads(self.requirements.read_text())
        contract['requirements'][1]['link_note'] = 'The interpretation of this challenge has changed.'
        self.requirements.write_text(json.dumps(contract))
        self.assertNotEqual(self.candidate(), identifier)
        self.assertFalse(self.build()[1]['ready'])

    def test_paragraph_link_retains_qualification_binding(self):
        self.challenge.messages[0].text = 'This is still a proposed change.\n\n' + REVERSAL
        self.write(self.challenge)
        self.link(unit='paragraph')
        self.review()
        self.assertTrue(self.build()[1]['ready'])
        self.challenge.messages[0].text = 'This was rejected.\n\n' + REVERSAL
        self.write(self.challenge)
        self.assertFalse(self.build()[1]['ready'])
        self.assertEqual(self.build()[1]['requirements'][1]['status'], 'evidence_changed')

    def test_outside_scope_and_changed_target_links_do_not_write(self):
        original_bytes = self.requirements.read_bytes()
        self.challenge.cwd = '/workspace/other-project'
        self.write(self.challenge)
        with self.assertRaises(ValueError):
            self.link(projects=[PROJECT])
        self.assertEqual(self.requirements.read_bytes(), original_bytes)
        self.original.messages[0].text += ' New qualification.'
        self.write(self.original)
        with self.assertRaises(ValueError):
            self.link()
        self.assertEqual(self.requirements.read_bytes(), original_bytes)

    def test_missing_targets_chains_and_empty_notes_are_rejected(self):
        for target, note in [('missing', 'Explanation.'), ('scope', ''), ('scope', None)]:
            with self.subTest(target=target, note=note):
                with self.assertRaises(ValueError):
                    link_challenge(self.archive, self.requirements, 'invalid', target, self.challenge.id, 1, REVERSAL, note)
        self.link()
        with self.assertRaises(ValueError):
            link_challenge(self.archive, self.requirements, 'chain', 'reversal', self.original.id, 1, ORIGINAL, 'A chain.')
        contract = json.loads(self.requirements.read_text())
        contract['requirements'][1]['challenge_for'] = 'reversal'
        self.requirements.write_text(json.dumps(contract))
        with self.assertRaises(ValueError):
            load_requirements(self.requirements)

    def test_legacy_or_incomplete_targets_cannot_create_unreviewable_links(self):
        contract = json.loads(self.requirements.read_text())
        for key in ('agent', 'role', 'section_sha256'):
            contract['requirements'][0].pop(key)
        self.requirements.write_text(json.dumps(contract))
        original = self.requirements.read_bytes()
        with self.assertRaises(ValueError):
            self.link()
        self.assertEqual(self.requirements.read_bytes(), original)
        with self.assertRaises(ValueError):
            link_challenge(self.archive, self.requirements, 'invalid', None, self.challenge.id, 1, REVERSAL, None)

    def test_cli_topic_and_standalone_link_and_history(self):
        def cli(args):
            stdout = io.StringIO()
            with patch.object(sys, 'argv', ['agent-sessions', *args]), contextlib.redirect_stdout(stdout):
                main()
            return json.loads(stdout.getvalue())
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'example', 'example cache', requirements=self.requirements, projects=[PROJECT])
        before, _ = resume_topic(workspace, 'example')
        self.assertTrue(before['ready'])
        anchor = cli(['topic', 'link', 'example', '--workspace', str(workspace), '--id', 'reversal', '--target', 'scope',
                      '--session', self.challenge.id, '--section', '1', '--quote', REVERSAL, '--note', 'Reverses scope.', '--json'])
        self.assertEqual(anchor['challenge_for'], 'scope')
        after, _ = resume_topic(workspace, 'example')
        self.assertFalse(after['ready'])
        self.assertEqual(after['history']['changes']['requirements_added'], ['reversal'])
        self.assertEqual(after['history']['changes']['review_opened'][0]['kind'], 'operator_linked_challenge')
        standalone = self.root / 'standalone.json'
        pin_requirement(self.archive, standalone, 'scope', self.original.id, 1, ORIGINAL)
        anchor = cli(['handoff', 'link', '--requirements', str(standalone), '-d', str(self.archive), '--id', 'reversal',
                      '--target', 'scope', '--session', self.challenge.id, '--section', '1', '--quote', REVERSAL,
                      '--note', 'Reverses scope.', '--project', PROJECT, '--json'])
        self.assertEqual(anchor['challenge_for'], 'scope')


if __name__ == '__main__':
    unittest.main()
