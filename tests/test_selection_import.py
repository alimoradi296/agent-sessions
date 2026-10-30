"""Assistant-selected text must pass exact source binding before becoming pins."""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.continuity import compile_handoff, audit_bundle, write_bundle, load_requirements
from agent_sessions.analysis.selection_import import prepare_selection_review, import_selection_review
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError

PROJECT = '/workspace/example-project'
SCOPE = 'Discovery only. Do not implement or publish.'


class SelectionImportTests(unittest.TestCase):
    def test_over_total_budget_reports_size_without_publishing_packet(self):
        result = prepare_selection_review(self.archive, self.packet, 'example cache', projects=[PROJECT],
                                          batch_review=True, max_total_prompt_chars=1)
        self.assertEqual(result['status'], 'over_budget')
        self.assertFalse(result['ready'])
        self.assertIsNone(result['output'])
        self.assertNotIn('review_id', result)
        self.assertEqual(result['budget_exceeded_by'], result['total_prompt_chars'] - 1)
        self.assertFalse(self.packet.exists())
        self.assertFalse(list(self.root.glob('.review-plans-*')))

    def test_exact_total_budget_keeps_ordinary_packet_and_import(self):
        plain_dir = self.root / 'ordinary'
        plain = prepare_selection_review(self.archive, plain_dir, 'example cache', projects=[PROJECT])
        result = prepare_selection_review(self.archive, self.packet, 'example cache', projects=[PROJECT],
                                          max_total_prompt_chars=plain['total_prompt_chars'])
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(result['review_id'], plain['review_id'])
        self.assertEqual((self.packet / 'review-packet.json').read_bytes(), (plain_dir / 'review-packet.json').read_bytes())
        self.response['review_id'] = result['review_id']
        self.import_response()

    def test_compact_plan_can_fit_total_budget_that_ordinary_plan_exceeds(self):
        body = ('Historical reference only. ' + 'A fictional alternative remains unresolved. ' * 20).strip()
        self.export('synthetic-repeated', '\n\n'.join([body] * 30))
        result = prepare_selection_review(self.archive, self.packet, 'example cache', projects=[PROJECT],
            max_prompt_chars=4000, batch_review=True, compact_review=True, max_total_prompt_chars=10000)
        self.assertEqual(result['status'], 'prepared')
        self.assertLessEqual(result['total_prompt_chars'], 10000)
        self.assertGreater(result['review_encoding']['ordinary_total_chars'], 10000)
        self.assertFalse(result['review_encoding']['fallback'])
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        self.assertFalse(packet['omissions'])

    def test_over_budget_cli_returns_json_and_nonzero_without_packet(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), patch.object(sys, 'argv',
                ['agent-sessions', 'handoff', 'prepare-review', 'example cache', '-d', str(self.archive), '-o', str(self.packet),
                 '--project', PROJECT, '--max-total-prompt-chars', '1']):
            with self.assertRaises(SystemExit) as stopped:
                main()
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue())['status'], 'over_budget')
        self.assertFalse(self.packet.exists())

    def test_complete_input_size_report_counts_all_batches(self):
        self.export('synthetic-volume', '\n\n'.join(f'Fictional observation {i}. ' + 'Proposed detail. ' * 30 for i in range(20)))
        report = self.prepare(batch_review=True, max_prompt_chars=3000)
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        texts = [(self.packet / 'review-prompt.txt').read_text()] + [
            (self.packet / name).read_text() for name in packet['batches']]
        self.assertGreater(len(texts), 2)
        self.assertEqual(report['total_prompt_chars'], sum(map(len, texts)))
        self.assertEqual(report['largest_prompt_chars'], max(map(len, texts)))
        self.assertGreater(report['total_prompt_chars'], report['prompt_chars'])

    def test_single_prompt_size_report_has_no_batch_overhead(self):
        report = self.prepare()
        self.assertEqual(report['total_prompt_chars'], report['prompt_chars'])
        self.assertEqual(report['largest_prompt_chars'], report['prompt_chars'])

    def test_compact_cli_packet_keeps_located_import_and_distinct_identity(self):
        body = ('Historical reference only. ' + 'A fictional alternative remains under review. ' * 20).strip()
        session = Session(id='synthetic-repeated', agent=Agent.CODEX, cwd=PROJECT,
            messages=[Message(role='user' if n % 2 else 'assistant', text=body) for n in range(40)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')
        plain_dir = self.root / 'ordinary'
        plain = prepare_selection_review(self.archive, plain_dir, 'example cache', projects=[PROJECT],
            max_prompt_chars=4000, batch_review=True)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), patch.object(sys, 'argv',
                ['agent-sessions', 'handoff', 'prepare-review', 'example cache', '-d', str(self.archive), '-o', str(self.packet),
                 '--project', PROJECT, '--batch-review', '--compact-review', '--max-prompt-chars', '4000']):
            main()
        result = json.loads(stream.getvalue())
        self.assertFalse(result['review_encoding']['fallback'])
        self.assertLess(result['review_encoding']['selected_total_chars'], result['review_encoding']['ordinary_total_chars'])
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        baseline = json.loads((plain_dir / 'review-packet.json').read_text())
        self.assertEqual(packet['records'], baseline['records'])
        self.assertNotEqual(result['review_id'], plain['review_id'])
        self.assertEqual(packet['prompt_format'], 'adaptive_exact_text_v1')
        self.assertTrue(all(len((self.packet / name).read_text()) <= 4000 for name in packet['batches']))
        self.response.update(review_id=result['review_id'], reviewed_batches=list(packet['batches']),
            selected=[dict(session_id='synthetic-repeated', quote=body, reason='A repeated historical occurrence.',
                           section=40, paragraph_start_line=1)])
        self.import_response()
        contract = json.loads(self.output.read_text())
        self.assertEqual(contract['requirements'][0]['section'], 40)
        self.assertEqual(contract['requirements'][0]['role'], 'User')

    def test_compact_request_falls_back_to_identical_ordinary_packet(self):
        plain_dir = self.root / 'ordinary'
        plain = prepare_selection_review(self.archive, plain_dir, 'example cache', projects=[PROJECT])
        result = self.prepare(compact_review=True)
        self.assertTrue(result['review_encoding']['fallback'])
        self.assertEqual(result['review_id'], plain['review_id'])
        self.assertEqual((self.packet / 'review-packet.json').read_bytes(), (plain_dir / 'review-packet.json').read_bytes())
        self.import_response()

    def test_source_change_between_plans_does_not_publish_packet(self):
        from agent_sessions.analysis import selection_import as selection
        original = selection._prepare_selection_review
        calls = []
        def prepare(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            if len(calls) == 1:
                source = self.archive / 'synthetic-scope.md'
                source.write_text(source.read_text() + '\nNew historical text.\n')
            return result
        with patch.object(selection, '_prepare_selection_review', side_effect=prepare):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                self.prepare(compact_review=True)
        self.assertFalse(self.packet.exists())
        self.assertFalse(list(self.root.glob('.review-plans-*')))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive, self.packet = self.root / 'exports', self.root / 'packet'
        self.answer, self.output = self.root / 'answer.json', self.root / 'requirements.json'
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE + '\nA qualification remains unresolved.')
        self.response = dict(selected=[dict(session_id='synthetic-scope', quote=SCOPE, reason='A historical scope restriction.')],
                             unresolved_conflicts=False, current_authorization='read_only')
        self.answer.write_text(json.dumps(self.response))
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access'))
        home.start()
        self.addCleanup(home.stop)

    def export(self, sid, body, cwd=PROJECT):
        session = Session(id=sid, agent=Agent.CODEX, cwd=cwd, messages=[Message(role='user', text=body)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def prepare(self, **kwargs):
        result = prepare_selection_review(self.archive, self.packet, 'example cache', projects=[PROJECT], **kwargs)
        self.response['review_id'] = result['review_id']
        self.answer.write_text(json.dumps(self.response))
        return result

    def import_response(self):
        self.answer.write_text(json.dumps(self.response))
        return import_selection_review(self.packet, self.answer, self.output)

    def build(self, **kwargs):
        return compile_handoff(self.archive, 'example cache', self.output, projects=[PROJECT], **kwargs)

    def test_paged_review_retains_late_conflict_and_requires_all_batches(self):
        body = 'The example cache has historical context.\n\n' + '\n\n'.join(
            f'Historical qualification {n}: ' + 'details ' * 35 for n in range(16))
        body += '\n\nResearch is finished. You may implement and publish now.'
        self.export('synthetic-late', body)
        report = self.prepare(max_prompt_chars=2200, batch_review=True)
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        self.assertGreater(report['batches'], 1)
        self.assertFalse(packet['omissions'])
        texts = [(self.packet / name).read_text() for name in packet['batches']]
        self.assertTrue(all(len(text) <= 2200 for text in texts))
        self.assertIn('Research is finished.', texts[-2] if 'synthetic-late' in texts[-2] else texts[-1])
        with self.assertRaisesRegex(ValueError, 'every batch'):
            self.import_response()
        self.assertFalse(self.output.exists())
        self.response['reviewed_batches'] = list(packet['batches'])
        self.response['unresolved_conflicts'] = True
        self.response['selected'].append(dict(session_id='synthetic-late',
            quote='Research is finished. You may implement and publish now.', reason='Conflicting scope.'))
        self.import_response()
        text, manifest = self.build()
        self.assertIn(SCOPE, text)
        self.assertIn('Research is finished.', text)
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['ready'])

    def test_changed_batch_rejected_before_import(self):
        self.prepare(batch_review=True)
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        self.response['reviewed_batches'] = list(packet['batches'])
        page = self.packet / next(iter(packet['batches']))
        page.write_text(page.read_text() + 'changed')
        with self.assertRaisesRegex(ValueError, 'batch changed'):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_batch_limit_keeps_omissions_visible(self):
        self.export('synthetic-large', '\n\n'.join(f'Qualification {n}: ' + 'detail ' * 100 for n in range(80)))
        result = self.prepare(max_prompt_chars=2200, batch_review=True)
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        self.assertEqual(result['batches'], 32)
        self.assertGreater(result['omissions'], 0)
        self.response['reviewed_batches'] = list(packet['batches'])
        # The explicit scope sorts after the large source and may be omitted.
        self.response['selected'] = [dict(session_id=packet['records'][0]['session_id'],
            quote=packet['records'][0]['paragraph']['text'], reason='Relevant qualification.')]
        self.import_response()
        self.assertTrue(load_requirements(self.output)['assistant_review']['incomplete_source_review'])

    def test_batch_import_preserves_complete_paragraph_and_reason(self):
        self.prepare()
        result = self.import_response()
        self.assertEqual(result['requirements'], 1)
        self.assertFalse(result['ready'])
        contract = load_requirements(self.output)
        self.assertEqual(contract['requirements'][0]['unit'], 'paragraph')
        text, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertIn(SCOPE + '\nA qualification remains unresolved.', text)
        self.assertIn('A historical scope restriction.', text)
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 0)

    def test_repeated_quote_requires_location_and_preserves_selected_occurrence(self):
        self.export('synthetic-scope', SCOPE + '\n\nIntervening context.\n\n' + SCOPE)
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'multiple paragraphs'):
            self.import_response()
        self.assertFalse(self.output.exists())
        self.response['selected'][0].update(section=1, paragraph_start_line=5)
        self.import_response()
        anchor = load_requirements(self.output)['requirements'][0]
        self.assertEqual(anchor['section'], 1)
        self.assertEqual(anchor['paragraph']['start_line'], 5)
        self.assertEqual(anchor['quote'], SCOPE)
        text, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertIn(SCOPE, text)

    def test_locator_cannot_select_other_text_or_forge_a_source_position(self):
        self.prepare()
        selection = self.response['selected'][0]
        for section, line in ((2, 3), (1, 1), (1, 4)):
            with self.subTest(section=section, line=line):
                selection.update(section=section, paragraph_start_line=line)
                with self.assertRaisesRegex(ValueError, 'absent'):
                    self.import_response()
                self.assertFalse(self.output.exists())

    def test_located_repeated_quotes_survive_import_compile_and_audit_above_eight_sections(self):
        session = Session(id='synthetic-scope', agent=Agent.CODEX, cwd=PROJECT,
                          messages=[Message(role='user', text=f'Context {n}.\n\n' + SCOPE) for n in range(9)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')
        self.prepare()
        self.response['selected'] = [dict(session_id='synthetic-scope', section=n + 1,
            paragraph_start_line=3, quote=SCOPE, reason=f'Retain occurrence {n + 1}.') for n in range(9)]
        self.import_response()
        text, manifest = self.build()
        self.assertTrue(manifest['ready'])
        self.assertEqual(len(manifest['requirements']), 9)
        self.assertTrue(all(item['status'] == 'covered' for item in manifest['requirements']))
        self.assertEqual(manifest['sources'][0]['selected_sections'], list(range(1, 10)))
        write_bundle(self.root / 'located-bundle', text, manifest)
        self.assertEqual(audit_bundle(self.root / 'located-bundle', self.archive)['exit_code'], 0)

    def test_locator_fields_are_paired_positive_integers(self):
        self.prepare()
        original = dict(self.response['selected'][0])
        for fields in ({'section': 1}, {'paragraph_start_line': 3},
                       {'section': True, 'paragraph_start_line': 3},
                       {'section': 1, 'paragraph_start_line': 0},
                       {'section': '1', 'paragraph_start_line': 3}):
            with self.subTest(fields=fields):
                self.response['selected'][0] = dict(original, **fields)
                with self.assertRaises(ValueError):
                    self.import_response()
                self.assertFalse(self.output.exists())

    def test_assistant_conflict_report_blocks_compile_and_audit(self):
        self.prepare()
        self.response['unresolved_conflicts'] = True
        self.import_response()
        text, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['review_passed'])
        self.assertFalse(manifest['ready'])
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.assertIn('assistant_conflicts_unresolved', {item['code'] for item in audit_bundle(bundle, self.archive)['findings']})

    def test_embedded_skill_hint_does_not_discard_its_scope_evidence(self):
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n<skill>\n' + SCOPE + '\n</skill>')
        self.prepare()
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        record = next(record for record in packet['records'] if SCOPE in record['paragraph']['text'])
        self.assertEqual(record['origin_hint'], 'embedded_reference')
        self.assertIn('embedded_reference', (self.packet / 'review-prompt.txt').read_text())
        self.import_response()
        text, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertIn(SCOPE, text)

    def test_invented_or_out_of_packet_sources_fail_without_partial_writes(self):
        self.prepare()
        self.response['selected'].append(dict(session_id='synthetic-unknown', quote='Invented quote.', reason='Unfounded.'))
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_ambiguous_quotes_and_duplicate_paragraphs_are_rejected(self):
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE + '\n\n' + SCOPE)
        self.prepare()
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_source_changes_and_metadata_changes_are_stale(self):
        self.prepare()
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE + '\nA changed qualification.')
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_metadata_only_change_is_stale_even_with_identical_source_bytes(self):
        self.prepare()
        index = self.archive / 'sessions.json'
        data = json.loads(index.read_text())
        data['sessions'][0]['agent'] = 'cursor'
        index.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.import_response()

    def test_excluded_project_update_preserves_packet_compile_and_audit_freshness(self):
        self.prepare()
        self.export('synthetic-excluded', 'Do not implement another project.', cwd='/workspace/other-project')
        self.import_response()
        text, manifest = self.build()
        self.assertFalse(manifest['assistant_review_stale'])
        self.assertTrue(manifest['ready'])
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.export('synthetic-excluded', 'Changed another project.', cwd='/workspace/other-project')
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 0)

    def test_new_scope_member_invalidates_review_even_when_its_bytes_do_not_change(self):
        self.export('synthetic-excluded', 'You may implement now.', cwd='/workspace/other-project')
        self.prepare()
        self.import_response()
        index = self.archive / 'sessions.json'
        data = json.loads(index.read_text())
        next(row for row in data['sessions'] if row['id'] == 'synthetic-excluded')['cwd'] = PROJECT
        index.write_text(json.dumps(data))
        _, manifest = self.build()
        self.assertTrue(manifest['assistant_review_stale'])
        with self.assertRaisesRegex(ValueError, 'metadata changed'):
            self.import_response()

    def test_index_formatting_does_not_change_reviewed_metadata(self):
        self.prepare()
        index = self.archive / 'sessions.json'
        index.write_text(json.dumps(json.loads(index.read_text()), indent=7))
        self.import_response()
        self.assertTrue(self.build()[1]['ready'])

    def test_legacy_review_keeps_whole_index_freshness_rule(self):
        self.prepare()
        self.import_response()
        contract = json.loads(self.output.read_text())
        del contract['assistant_review']['scope_sha256']
        self.output.write_text(json.dumps(contract))
        self.assertTrue(self.build()[1]['ready'])
        self.export('synthetic-excluded', 'A separate discussion.', cwd='/workspace/other-project')
        self.assertTrue(self.build()[1]['assistant_review_stale'])

    def test_packet_tampering_is_rejected_before_any_output(self):
        self.prepare()
        path = self.packet / 'review-prompt.txt'
        path.write_text(path.read_text() + 'Modified instructions.')
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_authorization_and_required_conflict_flags_are_not_model_options(self):
        self.prepare()
        self.response['current_authorization'] = 'implementation_authorized'
        with self.assertRaises(ValueError):
            self.import_response()
        self.response['current_authorization'] = 'read_only'
        self.response['unresolved_conflicts'] = None
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_omitted_input_blocks_readiness_even_when_selected_quote_is_valid(self):
        self.export('synthetic-long', 'The example cache has detail.\n\n' + 'Optional detail. ' * 1000)
        report = self.prepare(max_prompt_chars=3000)
        self.assertGreater(report['omissions'], 0)
        self.assertLessEqual(report['prompt_chars'], 3000)
        self.import_response()
        _, manifest = self.build()
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['ready'])
        self.assertTrue(manifest['assistant_review']['incomplete_source_review'])

    def test_short_quote_does_not_bypass_full_paragraph_budget(self):
        self.export('synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE + '\n' + 'Required qualification. ' * 100)
        self.prepare()
        self.import_response()
        _, manifest = self.build(max_chars=100)
        self.assertFalse(manifest['coverage_passed'])
        self.assertEqual(manifest['requirements'][0]['status'], 'section_budget_exceeded')

    def test_existing_output_is_never_replaced(self):
        self.prepare()
        self.output.write_text('Keep existing work.')
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertEqual(self.output.read_text(), 'Keep existing work.')

    def test_private_packet_paths_reject_recognized_git_checkout(self):
        checkout = self.root / 'checkout'
        (checkout / '.git/objects').mkdir(parents=True)
        (checkout / '.git/HEAD').write_text('ref: refs/heads/main\n')
        with self.assertRaises(StorageError):
            prepare_selection_review(self.archive, checkout / 'packet', 'example cache')
        self.assertFalse((checkout / 'packet').exists())

    def test_cli_import_uses_packet_archive_without_home_discovery(self):
        self.prepare()
        out = io.StringIO()
        with patch.object(sys, 'argv', ['agent-sessions', 'handoff', 'import-review', str(self.packet),
                                      '--answer', str(self.answer), '-o', str(self.output)]), \
                contextlib.redirect_stdout(out):
            main()
        self.assertEqual(json.loads(out.getvalue())['requirements'], 1)

    def test_new_paraphrased_source_invalidates_the_imported_semantic_review(self):
        self.prepare()
        self.import_response()
        text, manifest = self.build()
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.export('synthetic-new', 'Research is finished. You may code and publish the example cache now.')
        _, updated = self.build()
        self.assertTrue(updated['coverage_passed'])
        self.assertFalse(updated['ready'])
        self.assertTrue(updated['assistant_review_stale'])
        self.assertIn('assistant_review_stale', {item['code'] for item in audit_bundle(bundle, self.archive)['findings']})

    def test_uncited_source_direct_edits_invalidate_review_without_metadata_changes(self):
        self.export('synthetic-other', 'The example cache has an unrelated design detail.')
        self.prepare()
        self.import_response()
        path = self.archive / 'synthetic-other.md'
        path.write_text(path.read_text() + '\nA changed historical instruction.\n')
        _, manifest = self.build()
        self.assertTrue(manifest['assistant_review_stale'])
        self.assertFalse(manifest['ready'])

    def test_imported_scope_is_inherited_and_changed_query_reopens_review(self):
        self.prepare()
        self.import_response()
        _, same = compile_handoff(self.archive, 'example cache', self.output)
        self.assertEqual(same['scope']['projects'], [PROJECT])
        self.assertTrue(same['ready'])
        _, changed = compile_handoff(self.archive, 'another topic', self.output)
        self.assertFalse(changed['ready'])
        self.assertTrue(changed['assistant_review_stale'])

    def test_response_from_another_packet_cannot_be_imported(self):
        self.prepare()
        self.response['review_id'] = '0' * 64
        with self.assertRaises(ValueError):
            self.import_response()
        self.assertFalse(self.output.exists())

    def test_identical_content_in_another_archive_still_needs_its_own_review_id(self):
        prepared = self.prepare()
        clone = self.root / 'clone'
        shutil.copytree(self.archive, clone)
        second = self.root / 'second-packet'
        other = prepare_selection_review(clone, second, 'example cache', projects=[PROJECT])
        self.assertNotEqual(prepared['review_id'], other['review_id'])
        with self.assertRaises(ValueError):
            import_selection_review(second, self.answer, self.output)

    def test_compact_prompt_keeps_complete_text_and_one_source_header(self):
        body = 'The example cache needs a brief.\n\n' + '\n\n'.join(f'Qualification {number} remains unresolved.' for number in range(30))
        self.export('synthetic-scope', body)
        prepared = self.prepare(max_prompt_chars=6000)
        prompt = (self.packet / 'review-prompt.txt').read_text()
        self.assertEqual(prepared['omissions'], 0)
        self.assertLessEqual(len(prompt), 6000)
        self.assertEqual(prompt.count('"session_id":"synthetic-scope"'), 1)
        for number in range(30):
            self.assertIn(f'Qualification {number} remains unresolved.', prompt)
        data = json.loads((self.packet / 'review-packet.json').read_text())
        self.assertTrue(all(record['source_sha256'] for record in data['records']))


if __name__ == '__main__':
    unittest.main()
