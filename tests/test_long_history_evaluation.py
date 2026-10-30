"""Validate fixed-budget preparation and predeclared citation alternatives."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.continuation_evaluation import REFERENCE, score_arms
from examples.long_history_evaluation import prepare


class LongHistoryEvaluationTests(unittest.TestCase):
    def test_budget_is_complete_prompt_and_manual_control_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access')):
            root = Path(temporary) / 'exercise'
            protocol = prepare(root)
            self.assertGreater(protocol['archive_chars'], protocol['complete_prompt_budget'])
            self.assertEqual(protocol['source_count'], 21)
            for arm in ('baseline', 'required', 'manual'):
                prompt = (root / f'{arm}-prompt.md').read_text()
                self.assertLessEqual(len(prompt), protocol['complete_prompt_budget'])
                self.assertEqual(protocol['arm_sizes'][arm]['prompt_chars'], len(prompt))
            self.assertNotIn('Discovery only.', (root / 'baseline-prompt.md').read_text())
            for arm in ('required', 'manual'):
                self.assertIn('Discovery only. Do not implement or publish.', (root / f'{arm}-prompt.md').read_text())
            self.assertIn('best-case operator control', protocol['selection']['manual'])

    def test_predeclared_alternative_counts_without_regrading_old_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            protocol = prepare(root)
            answer = {key: dict(value=item['value'], quote=item['quote']) for key, item in REFERENCE.items()}
            answer['checked_results']['quote'] = 'None independently checked by this command.'
            path = root / 'scripted-control.json'
            path.write_text(json.dumps(answer))
            result = score_arms(root, {'required': path}, 'scripted_accounting_control_not_a_reader')
            self.assertEqual(result['arms']['required']['supported_answers'], 5)
            del protocol['reference']['checked_results']['accepted_quotes']
            (root / 'reference.json').write_text(json.dumps(protocol))
            result = score_arms(root, {'required': path}, 'scripted_legacy_scoring_control')
            self.assertEqual(result['arms']['required']['supported_answers'], 4)
            protocol['reference']['checked_results']['accepted_quotes'] = ['']
            (root / 'reference.json').write_text(json.dumps(protocol))
            with self.assertRaises(ValueError):
                score_arms(root, {'required': path}, 'invalid_empty_citation_control')

    def test_impossible_budget_and_existing_directory_fail_before_a_reader_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            with self.assertRaises(ValueError):
                prepare(root, max_prompt_chars=100)
            with self.assertRaises(FileExistsError):
                prepare(root)


if __name__ == '__main__':
    unittest.main()
