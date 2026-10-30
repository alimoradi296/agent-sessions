"""Keep automatic selection accounting and known omissions visible."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.evaluate_suggestions import evaluate


class SuggestionEvaluationTests(unittest.TestCase):
    def test_no_manual_pins_and_no_inference_of_complete_discovery(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access')):
            root = Path(temporary)
            report = evaluate(root)
            self.assertFalse(any(root.glob('*requirements*.json')))
        self.assertFalse(report['manual_pins_created'])
        self.assertFalse(report['ready'])
        positives = sum(row['should_propose'] for row in report['cases'])
        self.assertEqual(report['detected'] + report['missed'], positives)
        self.assertEqual(report['irrelevant_proposals'], sum(not row['should_propose'] and row['proposed'] for row in report['cases']))
        self.assertEqual(report['oversized_paragraphs_omitted'], 1)
        self.assertEqual(report['actionable_omission_locators'], 1)


if __name__ == '__main__':
    unittest.main()
