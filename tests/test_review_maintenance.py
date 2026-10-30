"""Imported reviews must preserve exact project boundaries during updates."""

import tempfile
import unittest
from pathlib import Path

from examples.evaluate_review_maintenance import evaluate


class ImportedMaintenanceTests(unittest.TestCase):
    def test_checkpoint_comparison_and_outside_scope_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = evaluate(Path(temporary))
        for signal in result['summary'].values():
            self.assertEqual(signal, dict(detected=5, missed=0, unrelated_alerts=2))
        for case in result['cases']:
            self.assertEqual(case['assistant_review_stale'], case['audit_review_stale'])
            self.assertEqual(case['current_ready'], case['case'] == 'outside-project-addition')
        controls = result['append_information']
        self.assertTrue(controls['known_append_prefixes_preserved'])
        self.assertTrue(controls['reduced_inputs_identical'])
        self.assertNotEqual(*controls['full_history_timeout_values'])
        self.assertFalse(controls['earlier_edit_preserves_prefix'])
        for recovered in controls['literal_and_indexed_retrieval']:
            self.assertTrue(recovered['literal_has_definition'])
            self.assertTrue(recovered['indexed_has_definition'])
        lookup = result['lookup_boundaries']['cases']
        conflict = lookup['conflicting-definitions']
        self.assertTrue(conflict['all_source_statements_in_quotes'])
        self.assertLess(conflict['limited_returned'], conflict['limited_total_hits'])
        self.assertFalse(lookup['indirect-definition']['all_source_statements_in_quotes'])
        self.assertTrue(lookup['indirect-definition']['follow_up_recovers_definition'])
        self.assertEqual(lookup['missing-literal-name']['total_hits'], 0)


if __name__ == '__main__':
    unittest.main()
