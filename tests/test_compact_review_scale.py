import unittest

from examples.evaluate_compact_review import evaluate


class CompactReviewScaleTests(unittest.TestCase):
    def test_complete_cli_retains_or_reports_every_occurrence(self):
        result = evaluate(sources=2, messages=8, repeats=1, budget=4000)
        for case in result['cases']:
            for plan in case['results'].values():
                self.assertEqual(plan['records'] + plan['omissions'], 16)
                self.assertTrue(plan['display_verified'])
            ordinary, adaptive = case['results']['ordinary'], case['results']['adaptive']
            self.assertLessEqual(adaptive['total_chars'], ordinary['total_chars'])
            self.assertLessEqual(adaptive['omissions'], ordinary['omissions'])
