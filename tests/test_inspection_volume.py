"""Check workload accounting without treating displayed volume as user effort."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.evaluate_inspection_volume import evaluate


class InspectionVolumeTests(unittest.TestCase):
    def test_counts_expose_initial_cost_and_empty_changed_views(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access')):
            result = evaluate(Path(temporary))
        self.assertTrue(result['synthetic_only'])
        self.assertTrue(result['scripted_inspection_notes'])
        self.assertEqual(result['initial_inspection']['sections'], result['initial_inspection']['sources'] * 24)
        repeated = result['repeated_use']
        self.assertEqual(repeated['pending_sources'], len(result['cases']))
        for key in ('sections', 'dialogue_chars'):
            self.assertEqual(repeated['queued_full_sources'][key], sum(row['full_source'][key] for row in result['cases']))
            self.assertEqual(repeated['changed_view'][key], sum(row['changed_view'][key] for row in result['cases']))
            self.assertEqual(repeated['with_full_view_recommendations'][key],
                             sum(row['full_source' if row['full_view_recommended'] else 'changed_view'][key]
                                 for row in result['cases']))
            self.assertLess(repeated['changed_view'][key], repeated['queued_full_sources'][key])
        cases = {row['case']: row for row in result['cases']}
        self.assertEqual(cases['deleted-qualification']['removed_sections'], 1)
        self.assertEqual(cases['duplicate-appended']['changed_view']['sections'], 1)
        for case in ('deleted-qualification', 'metadata-change', 'section-reordered'):
            self.assertEqual(cases[case]['changed_view']['sections'], 0)
            self.assertTrue(cases[case]['full_view_recommended'])
        self.assertFalse(cases['deleted-qualification']['prior_text_available'])


if __name__ == '__main__':
    unittest.main()
