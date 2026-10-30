"""Check evaluation accounting without declaring heuristic misses acceptable."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.evaluate_review_burden import evaluate, summarize


class ReviewBurdenTests(unittest.TestCase):
    def test_confusion_counts_and_empty_denominators(self):
        rows = [dict(should_review=expected, review_triggered=observed)
                for expected in (True, False) for observed in (True, False)]
        result = summarize(rows)
        for key in ('detected_challenges', 'missed_challenges', 'unnecessary_reviews', 'quiet_nonchallenges'):
            self.assertEqual(result[key], 1)
        self.assertEqual(result['challenge_detection_rate'], 0.5)
        self.assertEqual(result['nonchallenge_review_rate'], 0.5)
        self.assertIsNone(summarize([])['challenge_detection_rate'])

    def test_evaluation_uses_only_synthetic_sources_and_keeps_each_label(self):
        cases = [dict(id='literal', should_review=True, rationale='Explicit proposed change.',
                      text='Replace "Discovery only. Do not implement or publish." with "Implementation is proposed next.".'),
                 dict(id='quiet', should_review=False, rationale='Unrelated update.', text='A naming question remains.')]
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access')):
            report = evaluate(Path(temporary), cases)
        self.assertTrue(report['synthetic_only'])
        self.assertEqual(len(report['cases']), 6)
        for mode in ('scoped', 'unscoped'):
            self.assertEqual(report['summary'][mode]['detected_challenges'], 1)
            self.assertEqual(report['summary'][mode]['quiet_nonchallenges'], 1)

    def test_label_guided_links_are_reported_as_interventions_not_scanner_improvements(self):
        cases = [dict(id='plain', should_review=True, rationale='The proposed scope changes.',
                      text='Discovery is finished. Implementation and publication are proposed next.')]
        with tempfile.TemporaryDirectory() as temporary:
            report = evaluate(Path(temporary), cases)
        self.assertEqual(report['summary']['scoped']['missed_challenges'], 1)
        self.assertEqual(report['summary']['operator_assisted']['detected_challenges'], 1)
        self.assertTrue(report['operator_intervention']['label_guided'])
        self.assertEqual(report['operator_intervention']['links'], 1)


if __name__ == '__main__':
    unittest.main()
