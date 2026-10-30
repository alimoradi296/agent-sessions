import copy
import unittest

from examples.compare_review_compaction import batch_plan, compact, compare_batches, compatibility_controls, experimental_renderer, expand, synthetic_controls, synthetic_records
from agent_sessions.analysis.selection_import import _prompt


class ReviewCompactionTests(unittest.TestCase):
    def test_literal_reference_markers_survive_serialized_codec(self):
        import json
        original = self.fixture()
        literals = ['[[ref:R1 previously shown]]', '[[ref:R1]]\nshort note',
                    '[[ref:R999]]\nshort note', '{"texts":["literal"],"text_ref":0}']
        for literal in literals:
            for section in original[0]['sections']:
                section['paragraphs'][0]['text'] = literal
            wire = json.dumps(compact(original), ensure_ascii=False)
            self.assertEqual(expand(json.loads(wire)), original)

    def test_aligned_framing_keeps_unique_source_prompt_identical(self):
        records = synthetic_records('unique')[:3]
        args = ('fictional review', ['/workspace/example'], records, 0, '0' * 64)
        self.assertEqual(experimental_renderer(*args, aligned=True), _prompt(*args))
        empty = (args[0], args[1], [], args[3], args[4])
        self.assertNotEqual(experimental_renderer(*empty, aligned=True), _prompt(*empty))

    def test_aligned_framing_preserves_actual_import_checks(self):
        report = compatibility_controls(repeats=1, aligned=True)
        self.assertTrue(report['imported_anchors_equal'])
        self.assertTrue(report['review_ids_distinct'])
        self.assertEqual(len(report['rejected_controls']), 6)
        self.assertLess(report['results']['experimental']['total_chars'], report['results']['ordinary']['total_chars'])

    def test_actual_packet_and_import_contract_with_experimental_renderer(self):
        report = compatibility_controls(repeats=1)
        self.assertTrue(report['imported_anchors_equal'])
        self.assertTrue(report['review_ids_distinct'])
        self.assertEqual(report['results']['experimental']['records'], 40)
        self.assertGreater(report['results']['experimental']['compact_batches'], 0)
        self.assertEqual(set(report['rejected_controls']), {'wrong-review-id', 'missing-batch',
            'ambiguous-quote', 'wrong-location', 'changed-batch', 'changed-source'})

    def test_batch_budget_and_occurrence_coverage_with_long_repetition(self):
        records = synthetic_records('long-repeated')[:40]
        plan = batch_plan(records, 4000, allow_compact=True)
        self.assertEqual(plan['included'], list(range(40)))
        self.assertFalse(plan['omitted'])
        self.assertLessEqual(plan['max_prompt_chars'], 4000)
        self.assertGreater(plan['compact_batches'], 0)

    def test_individual_oversize_paragraph_stays_an_omission(self):
        records = synthetic_records('unique')[:3]
        records[1]['paragraph']['text'] = 'x' * 10000
        plan = batch_plan(records, 4000, allow_compact=True)
        self.assertEqual(plan['omitted'], [1])
        self.assertEqual(plan['included'], [0, 2])

    def test_batch_limit_cannot_silently_drop_records(self):
        records = synthetic_records('unique')[:30]
        plan = batch_plan(records, 2500, max_batches=2)
        self.assertEqual(plan['batches'], 2)
        self.assertTrue(plan['omitted'])
        self.assertEqual(sorted(plan['included'] + plan['omitted']), list(range(30)))

    def test_chosen_plan_does_not_add_omissions_or_total_text(self):
        for name in ('unique', 'short-repeated', 'long-repeated'):
            result = compare_batches(synthetic_records(name)[:30], 4000)
            self.assertLessEqual(result['chosen']['total_chars'], result['plain']['total_chars'])
            self.assertTrue(set(result['plain']['included']).issubset(result['chosen']['included']))

    def fixture(self):
        return [dict(session_id='synthetic-a', sections=[
            dict(section=1, role='User', paragraphs=[dict(start_line=1, end_line=1, text='Same words.')]),
            dict(section=2, role='Assistant', paragraphs=[dict(start_line=5, end_line=5, text='Same words.', origin_hint='embedded_reference')]),
            dict(section=3, role='User', paragraphs=[dict(start_line=9, end_line=9, text='Different words.')]),
        ]), dict(session_id='synthetic-b', sections=[
            dict(section=1, role='User', paragraphs=[dict(start_line=1, end_line=1, text='Same words.')])])]

    def test_roundtrip_retains_order_roles_locators_and_wrapper_hints(self):
        original = self.fixture()
        snapshot = copy.deepcopy(original)
        packed = compact(original)
        self.assertEqual(len(packed['texts']), 2)
        self.assertEqual(expand(packed), original)
        self.assertEqual(original, snapshot)
        self.assertEqual(len(packed['sources']), 2)
        self.assertEqual(len(packed['sources'][0]['sections']), 3)

    def test_invalid_reference_rejected(self):
        for ref in (-1, True, 99, '0'):
            packed = compact(self.fixture())
            packed['sources'][0]['sections'][0]['paragraphs'][0]['text_ref'] = ref
            with self.assertRaises(ValueError):
                expand(packed)

    def test_text_equality_is_exact(self):
        original = self.fixture()
        original[0]['sections'][1]['paragraphs'][0]['text'] = 'same words.'
        self.assertEqual(len(compact(original)['texts']), 3)

    def test_synthetic_report_preserves_all_occurrences(self):
        report = synthetic_controls()
        self.assertTrue(all(c['paragraphs'] == 240 and c['exact_roundtrip'] for c in report['cases']))
        self.assertFalse(report['production_format_changed'])
