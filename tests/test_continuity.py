"""Handoff loss and drift scenarios, with synthetic evidence only."""

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import (
    compile_handoff, write_bundle, audit_bundle, pin_requirement, review_requirement,
)
from agent_sessions.analysis.handoff import build_handoff
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / 'exports'
        self.bundle = self.root / 'bundle'
        self.contract = self.root / 'requirements.json'
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected home access'))
        home.start()
        self.addCleanup(home.stop)

    def export(self, sid, texts, agent=Agent.CODEX):
        session = Session(id=sid, agent=agent, messages=[Message(role='assistant', text=text) for text in texts])
        MarkdownRenderer.write(session, self.directory)
        JsonIndexRenderer.update(session, self.directory / 'sessions.json')

    def requirements(self, anchors=None):
        anchors = anchors or [dict(id='scope', session_id='synthetic-scope', section=1,
                                   quote='Discovery only. Do not implement.')]
        self.contract.write_text(json.dumps(dict(version=1, requirements=anchors)))

    def build(self, **kwargs):
        return compile_handoff(self.directory, 'example cache', self.contract, **kwargs)

    def test_pinned_scope_survives_query_mismatch_and_source_ranking(self):
        self.export('synthetic-match', ['The example cache uses a queue.'])
        self.export('synthetic-scope', ['Discovery only. Do not implement.'], Agent.CURSOR)
        self.requirements()
        baseline = build_handoff(self.directory, 'example cache', last=1)
        self.assertNotIn('Discovery only', baseline)
        text, manifest = self.build(last=2)
        self.assertTrue(manifest['coverage_passed'])
        self.assertIn('Discovery only. Do not implement.', text)
        self.assertIn('required evidence anchor', text)
        self.assertIn('not factual correctness', text)
        self.assertEqual(manifest['requirements'][0]['status'], 'covered')
        write_bundle(self.bundle, text, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 0)

    def test_budget_failure_returns_a_draft_and_never_claims_coverage(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement. ' + 'Details. ' * 100])
        self.requirements()
        text, manifest = self.build(max_chars=50)
        self.assertFalse(manifest['coverage_passed'])
        self.assertEqual(manifest['requirements'][0]['status'], 'section_budget_exceeded')
        self.assertIn('FAIL — draft only', text)
        write_bundle(self.bundle, text, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 1)

    def test_source_limit_failure_is_explicit(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        self.export('synthetic-correction', ['Correction: The target is a proposal, not a guarantee.'])
        self.requirements([dict(id='scope', session_id='synthetic-scope', section=1,
                                quote='Discovery only.'),
                           dict(id='correction', session_id='synthetic-correction', section=1,
                                quote='The target is a proposal, not a guarantee.')])
        _, manifest = self.build(last=1)
        self.assertFalse(manifest['coverage_passed'])
        self.assertEqual(manifest['requirements'][1]['status'], 'source_limit_exceeded')

    def test_required_evidence_can_exceed_ranked_context_count_limit(self):
        self.export('synthetic-scope', [f'Required detail {i}.' for i in range(9)] + ['Optional example cache context.'])
        self.requirements([dict(id=f'detail-{i}', session_id='synthetic-scope', section=i + 1,
                                quote=f'Required detail {i}.') for i in range(9)])
        text, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertTrue(manifest['ready'])
        self.assertEqual(sum(a['status'] == 'covered' for a in manifest['requirements']), 9)
        self.assertEqual(manifest['limits']['sections_per_source'], 9)
        self.assertNotIn('Optional example cache context.', text)
        for i in range(9):
            self.assertIn(f'Required detail {i}.', text)
        write_bundle(self.bundle, text, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 0)

        # Increasing the count allowance must not bypass either character cap.
        _, manifest = self.build(max_chars=sum(len(f'Required detail {i}.') for i in range(8)))
        self.assertFalse(manifest['coverage_passed'])
        self.assertEqual(sum(a['status'] == 'covered' for a in manifest['requirements']), 8)
        self.assertEqual(manifest['requirements'][-1]['status'], 'section_budget_exceeded')
        text, manifest = self.build(max_total_chars=100)
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['total_budget_passed'])
        self.assertFalse(manifest['ready'])
        write_bundle(self.bundle, text, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 1)

    def test_stale_or_wrong_anchors_are_not_relocated_by_guessing(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        for changes, status in ((dict(quote='Missing qualification.'), 'quote_mismatch'),
                                (dict(section=2), 'section_missing'),
                                (dict(source_sha256='0' * 64), 'source_changed'),
                                (dict(session_id='synthetic-missing'), 'source_missing')):
            with self.subTest(status=status):
                anchor = dict(id='scope', session_id='synthetic-scope', section=1,
                              quote='Discovery only.')
                anchor.update(changes)
                self.requirements([anchor])
                _, manifest = self.build()
                self.assertEqual(manifest['requirements'][0]['status'], status)
                self.assertFalse(manifest['coverage_passed'])

    def test_audit_detects_source_drift_and_does_not_modify_any_files(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        self.requirements()
        text, manifest = self.build()
        write_bundle(self.bundle, text, manifest)
        source = self.directory / 'synthetic-scope.md'
        source.write_text(source.read_text().replace('Do not implement.', 'Implementation is now allowed.'))
        before = {str(p): (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(Path, 'mkdir', side_effect=AssertionError('Audit attempted mkdir')), \
             patch.object(Path, 'write_text', side_effect=AssertionError('Audit attempted write')):
            report = audit_bundle(self.bundle, self.directory)
        after = {str(p): (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(report['exit_code'], 1)
        self.assertIn('source_changed', {f['code'] for f in report['findings']})
        self.assertIn('required_anchor_not_current', {f['code'] for f in report['findings']})

    def test_audit_detects_missing_sources_and_modified_bundle(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        self.requirements()
        text, manifest = self.build()
        write_bundle(self.bundle, text, manifest)
        (self.bundle / 'handoff.md').write_text(text + '\nChanged.')
        (self.directory / 'synthetic-scope.md').unlink()
        report = audit_bundle(self.bundle, self.directory)
        self.assertEqual(report['exit_code'], 1)
        self.assertEqual({f['code'] for f in report['findings']},
                         {'handoff_changed', 'source_missing', 'required_anchor_not_current', 'relationship_source_missing'})

    def test_invalid_contracts_cannot_read_arbitrary_paths(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        for sid in ('../outside', '/outside', None):
            self.requirements([dict(id='scope', session_id=sid, section=1, quote='Example.')])
            with self.assertRaises((ValueError, StorageError)):
                self.build()

    def test_private_atomic_output_and_cli_failure_are_reviewable(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        self.requirements()
        argv = ['agent-sessions', 'handoff', 'build', 'example cache', '--requirements', str(self.contract),
                '-d', str(self.directory), '-o', str(self.bundle), '--max-chars', '5', '--json']
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(json.loads(output.getvalue())['coverage_passed'])
        self.assertTrue((self.bundle / 'handoff.md').is_file())
        if os.name == 'posix':
            self.assertEqual(self.bundle.stat().st_mode & 0o777, 0o700)
            self.assertEqual((self.bundle / 'manifest.json').stat().st_mode & 0o777, 0o600)

    def test_historical_results_never_become_checked(self):
        self.export('synthetic-scope', ['Verified: All checks passed.'])
        self.requirements([dict(id='reported-result', session_id='synthetic-scope', section=1,
                                quote='Verified: All checks passed.')])
        text, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertEqual(manifest['verification'], 'not_checked')
        self.assertEqual(text.count('Verified: All checks passed.'), 1)
        self.assertIn('None independently checked', text)
        self.assertEqual(manifest['rendering'], 'evidence_excerpts_v1')

    def test_pin_appends_exact_hash_bound_anchors_and_rejects_duplicates(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        anchor = pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1,
                                 'Discovery only.')
        self.assertEqual(anchor['source_sha256'], hashlib.sha256(
            (self.directory / 'synthetic-scope.md').read_bytes()).hexdigest())
        pin_requirement(self.directory, self.contract, 'restriction', 'synthetic-scope', 1,
                         'Do not implement.')
        self.assertEqual(len(json.loads(self.contract.read_text())['requirements']), 2)
        before = self.contract.read_bytes()
        with self.assertRaises(ValueError):
            pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        self.assertEqual(self.contract.read_bytes(), before)
        with self.assertRaises(ValueError):
            pin_requirement(self.directory, self.contract, 'wrong', 'synthetic-scope', 1,
                             'Not in the source.')

    def test_pin_hash_rejects_added_context_inside_the_same_section(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        source = self.directory / 'synthetic-scope.md'
        source.write_text(source.read_text() + '\nAdditional content.\n')
        _, manifest = self.build()
        self.assertFalse(manifest['coverage_passed'])
        self.assertEqual(manifest['requirements'][0]['status'], 'evidence_changed')

    def test_unrelated_appended_messages_keep_required_evidence_current(self):
        text = 'Discovery only. Do not implement.'
        self.export('synthetic-scope', [text])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        handoff, manifest = self.build()
        write_bundle(self.bundle, handoff, manifest)
        self.export('synthetic-scope', [text, 'A separate unrelated discussion.'])
        _, refreshed = self.build()
        self.assertTrue(refreshed['ready'])
        self.assertEqual(refreshed['requirements'][0]['source_update'], 'unrelated_changes')
        audit = audit_bundle(self.bundle, self.directory)
        self.assertEqual(audit['exit_code'], 0)
        self.assertEqual(audit['notes'][0]['code'], 'source_changed_selected_evidence_unchanged')

    def test_unique_complete_section_can_relocate_without_guessing(self):
        text = 'Discovery only. Do not implement.'
        self.export('synthetic-scope', [text])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        self.export('synthetic-scope', ['Earlier unrelated discussion.', text])
        handoff, manifest = self.build()
        anchor = manifest['requirements'][0]
        self.assertTrue(manifest['ready'])
        self.assertEqual(anchor['pinned_section'], 1)
        self.assertEqual(anchor['section'], 2)
        self.assertEqual(anchor['source_update'], 'relocated')
        self.assertIn('Pinned section 1, current section 2.', handoff)
        write_bundle(self.bundle, handoff, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 0)

    def test_identical_duplicates_after_source_change_remain_ambiguous(self):
        text = 'Discovery only. Do not implement.'
        self.export('synthetic-scope', [text])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        self.export('synthetic-scope', [text, 'Unrelated discussion.', text])
        _, manifest = self.build()
        self.assertFalse(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['status'], 'anchor_ambiguous')
        self.assertEqual(manifest['requirements'][0]['candidate_sections'], [1, 3])

    def test_preserved_quote_does_not_hide_a_changed_qualification(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1, 'Discovery only.')
        self.export('synthetic-scope', ['Hypothetical example: Discovery only. Do not implement.'])
        _, manifest = self.build()
        self.assertFalse(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['status'], 'evidence_changed')

    def test_equal_words_from_a_different_speaker_are_not_the_same_anchor(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        session = Session(id='synthetic-scope', agent=Agent.CODEX,
                          messages=[Message(role='user', text='Discovery only. Do not implement.')])
        MarkdownRenderer.write(session, self.directory)
        JsonIndexRenderer.update(session, self.directory / 'sessions.json')
        _, manifest = self.build()
        self.assertFalse(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['status'], 'evidence_changed')

    def test_new_cross_agent_correction_reopens_review_even_if_old_source_is_unchanged(self):
        original = 'Discovery only. Do not implement.'
        self.export('synthetic-scope', [original])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        text, manifest = self.build()
        write_bundle(self.bundle, text, manifest)
        original_bytes = (self.directory / 'synthetic-scope.md').read_bytes()
        self.export('synthetic-correction', [
            'Correction: Replace "Discovery only. Do not implement." with "Implementation is proposed next.".'
        ], agent=Agent.CURSOR)
        text, manifest = self.build()
        self.assertEqual((self.directory / 'synthetic-scope.md').read_bytes(), original_bytes)
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['review_passed'])
        self.assertFalse(manifest['ready'])
        candidates = manifest['requirements'][0]['review_candidates']
        self.assertEqual(candidates[0]['kind'], 'proposed_correction')
        self.assertEqual(candidates[0]['witness']['agent'], 'cursor')
        self.assertIn('Implementation is proposed next.', text)
        self.assertIn('Discovery only. Do not implement.', text)
        audit = audit_bundle(self.bundle, self.directory)
        self.assertEqual(audit['exit_code'], 1)
        self.assertIn('quoted_change_requires_review', {f['code'] for f in audit['findings']})

    def test_tool_payloads_do_not_reopen_review(self):
        original = 'Discovery only. Do not implement.'
        self.export('synthetic-scope', [original])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        self.export('synthetic-fenced', ['Example:\n```\nCorrection: Replace "Discovery only. Do not implement." '
                    'with "Implementation is proposed next.".\n```'])
        _, manifest = self.build()
        self.assertTrue(manifest['ready'])

    def test_explicit_review_keeps_both_statements_without_promoting_either(self):
        original = 'Discovery only. Do not implement.'
        self.export('synthetic-scope', [original])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        self.export('synthetic-correction', [
            'Correction: Replace "Discovery only. Do not implement." with "Implementation is proposed next.".'
        ], agent=Agent.CURSOR)
        _, draft = self.build()
        candidate = draft['requirements'][0]['unreviewed_candidates'][0]
        review_requirement(self.directory, self.contract, 'scope', candidate['review_id'],
                           'Keep both statements visible. The proposal does not authorize implementation.')
        text, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertEqual(manifest['verification'], 'not_checked')
        self.assertIn('Operator note (not authorization or factual proof)', text)
        self.assertIn('Discovery only. Do not implement.', text)
        self.assertIn('Implementation is proposed next.', text)
        write_bundle(self.bundle, text, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 0)
        self.export('synthetic-correction', [
            'Correction: Replace "Discovery only. Do not implement." with "Publish the proposed implementation.".'
        ], agent=Agent.CURSOR)
        _, changed = self.build()
        self.assertFalse(changed['ready'])
        self.assertTrue(changed['requirements'][0]['unreviewed_candidates'])
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 1)

    def test_review_rejects_unrelated_or_missing_candidates(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        before = self.contract.read_bytes()
        with self.assertRaises(ValueError):
            review_requirement(self.directory, self.contract, 'scope', '0' * 20, 'Unrelated note.')
        self.assertEqual(self.contract.read_bytes(), before)

    def test_manifest_edits_are_detected_even_if_handoff_text_is_unchanged(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        text, manifest = self.build()
        write_bundle(self.bundle, text, manifest)
        manifest['query'] = 'A different task'
        (self.bundle / 'manifest.json').write_text(json.dumps(manifest))
        audit = audit_bundle(self.bundle, self.directory)
        self.assertEqual(audit['exit_code'], 1)
        self.assertIn('manifest_changed', {f['code'] for f in audit['findings']})

    def test_total_budget_removes_optional_sections_before_required_evidence(self):
        original = 'Discovery only. Do not implement.'
        optional = 'The example cache has optional design details. ' * 180
        self.export('synthetic-scope', [original, optional])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        text, manifest = self.build(max_total_chars=4000)
        self.assertTrue(manifest['ready'])
        self.assertTrue(manifest['total_budget_passed'])
        self.assertLessEqual(len(text), 4000)
        self.assertIn(original, text)
        self.assertNotIn(optional, text)
        self.assertEqual(manifest['sources'][0]['selected_sections'], [1])

    def test_total_budget_failure_never_produces_a_ready_bundle(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        text, manifest = self.build(max_total_chars=100)
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['total_budget_passed'])
        self.assertFalse(manifest['ready'])
        self.assertIn('Total budget gate: FAIL', text)
        write_bundle(self.bundle, text, manifest)
        audit = audit_bundle(self.bundle, self.directory)
        self.assertIn('total_budget_exceeded', {f['code'] for f in audit['findings']})

    def test_readiness_tail_probe_rejects_small_budget_and_retains_the_full_section(self):
        fixture = Path(__file__).parent / 'fixtures/continuity_tail_case.json'
        case = json.loads(fixture.read_text())
        text = case['prefix'] + case['detail'] * case['repeat'] + '\n' + case['required_quote']
        self.export('synthetic-scope', [text])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1, case['required_quote'])
        outcomes = []
        for budget in case['budgets']:
            handoff, manifest = self.build(max_chars=budget, max_total_chars=budget)
            outcomes.append(manifest['ready'])
            if manifest['ready']:
                self.assertLessEqual(len(handoff), budget)
                self.assertIn(text, handoff)
        # Evidence-only rendering now fits this complete source at 6000 chars.
        self.assertEqual(outcomes, [False, True, True])

    def test_changed_agent_identity_is_not_an_unrelated_update(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1)
        text, manifest = self.build()
        write_bundle(self.bundle, text, manifest)
        index = self.directory / 'sessions.json'
        data = json.loads(index.read_text())
        data['sessions'][0]['agent'] = 'cursor'
        index.write_text(json.dumps(data))
        _, changed = self.build()
        self.assertFalse(changed['ready'])
        self.assertEqual(changed['requirements'][0]['status'], 'source_agent_changed')
        audit = audit_bundle(self.bundle, self.directory)
        self.assertIn('source_agent_changed', {item['code'] for item in audit['findings']})

    def test_explicit_paragraph_pin_fits_a_long_turn_and_preserves_its_whole_paragraph(self):
        paragraph = 'Discovery only. Do not implement.\nThe restriction applies to every proposed change.'
        text = 'Optional earlier context. ' * 300 + '\n\n' + paragraph + '\n\n' + 'Optional later context. ' * 300
        self.export('synthetic-scope', [text])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1,
                         'Discovery only.', unit='paragraph')
        handoff, manifest = self.build(max_chars=300, max_total_chars=6000)
        self.assertTrue(manifest['ready'])
        self.assertIn(paragraph, handoff)
        self.assertNotIn('Optional earlier context.', handoff)
        self.assertNotIn('Optional later context.', handoff)
        self.assertIn('Only explicitly selected paragraphs are shown.', handoff)
        self.assertIn('Cleaned section lines 3–4:', handoff)
        self.assertNotIn('**request**', handoff)
        selected = manifest['sources'][0]['selected_evidence'][0]
        self.assertEqual(selected['unit'], 'paragraph')
        self.assertEqual(selected['paragraphs'][0]['start_line'], 3)
        write_bundle(self.bundle, handoff, manifest)
        self.assertEqual(audit_bundle(self.bundle, self.directory)['exit_code'], 0)

    def test_paragraph_pin_still_rejects_a_changed_surrounding_section(self):
        text = 'Context qualification.\n\nDiscovery only. Do not implement.'
        self.export('synthetic-scope', [text])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1,
                         'Discovery only.', unit='paragraph')
        self.export('synthetic-scope', [text.replace('Context qualification.', 'Hypothetical context qualification.')])
        _, manifest = self.build()
        self.assertFalse(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['status'], 'evidence_changed')

    def test_paragraph_pins_do_not_guess_between_duplicate_or_cross_paragraph_quotes(self):
        self.export('synthetic-scope', ['Discovery only.\n\nDiscovery only.'])
        with self.assertRaises(ValueError):
            pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1,
                             'Discovery only.', unit='paragraph')
        with self.assertRaises(ValueError):
            pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1,
                             'Discovery only.\n\nDiscovery only.', unit='paragraph')
        with self.assertRaises(ValueError):
            pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1, unit='paragraph')

    def test_multiple_paragraph_pins_preserve_separate_source_ranges(self):
        self.export('synthetic-scope', ['Discovery only.\n\nUnrelated middle detail.\n\nDo not publish.'])
        pin_requirement(self.directory, self.contract, 'scope', 'synthetic-scope', 1,
                         'Discovery only.', unit='paragraph')
        pin_requirement(self.directory, self.contract, 'publishing', 'synthetic-scope', 1,
                         'Do not publish.', unit='paragraph')
        text, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertNotIn('Unrelated middle detail.', text)
        self.assertIn('Cleaned section lines 1–1:', text)
        self.assertIn('Cleaned section lines 5–5:', text)
        self.assertEqual(len(manifest['sources'][0]['selected_evidence'][0]['paragraphs']), 2)

    def test_compile_detects_sources_changing_during_render(self):
        self.export('synthetic-scope', ['Discovery only. Do not implement.'])
        self.requirements()
        source = self.directory / 'synthetic-scope.md'
        from agent_sessions.analysis.context import render_sources

        def changing_render(*args, **kwargs):
            rendered = render_sources(*args, **kwargs)
            source.write_text(source.read_text() + '\nConcurrent change.\n')
            return rendered

        with patch('agent_sessions.analysis.continuity.render_sources', side_effect=changing_render):
            with self.assertRaises(StorageError):
                self.build()

    def test_requirements_pack_keeps_full_evidence_without_duplicate_claim_summaries(self):
        body = 'The example cache is a proposal.\nVerified: All checks passed.\nA qualification remains unresolved.'
        self.export('synthetic-scope', [body])
        pin_requirement(self.directory, self.contract, 'qualification', 'synthetic-scope', 1,
                        'A qualification remains unresolved.')
        text, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertEqual(text.count(body), 1)
        self.assertEqual(text.count('Verified: All checks passed.'), 1)
        self.assertNotIn('## Reported blockers', text)
        self.assertNotIn('## Decision candidates', text)
        self.assertIn('Source: codex / synthetic-scope', text)
        self.assertIn('Assistant excerpt — section 1', text)
        self.assertIn('None independently checked', text)
        self.assertIn('reported_result', build_handoff(self.directory, 'example cache'))
        self.assertEqual(manifest['size_breakdown']['selected_excerpt_chars'], len(body))
        self.assertEqual(sum(manifest['size_breakdown'].values()), len(text))


if __name__ == '__main__':
    unittest.main()
