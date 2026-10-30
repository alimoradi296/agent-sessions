"""Validate evaluation accounting with labeled answers, not model-run claims."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from examples.continuation_evaluation import REFERENCE, prepare, score


class EvaluationAccountingTests(unittest.TestCase):
    def test_supported_abstained_and_unsupported_answers_stay_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(root / 'prepared')
            baseline = {key: dict(value='unknown', quote='') for key in REFERENCE}
            required = {key: dict(value=item['value'], quote=item['quote']) for key, item in REFERENCE.items()}
            for key in ('checked_results', 'current_authorization'):
                baseline[key] = required[key]
            baseline_path, required_path = root / 'baseline.json', root / 'required.json'
            baseline_path.write_text(json.dumps(baseline))
            required_path.write_text(json.dumps(required))
            result = score(root / 'prepared', baseline_path, required_path, 'scripted_accounting_control_not_a_model')
            self.assertEqual(result['arms']['baseline']['supported_answers'], 2)
            self.assertEqual(result['arms']['baseline']['abstentions'], 3)
            self.assertEqual(result['arms']['required']['supported_answers'], 5)
            self.assertEqual(result['arms']['required']['unsupported_answers'], 0)
            required['checked_results'] = dict(value='independently_checked', quote='Verified: All checks passed.')
            required_path.write_text(json.dumps(required))
            result = score(root / 'prepared', baseline_path, required_path, 'scripted_negative_control_not_a_model')
            self.assertEqual(result['arms']['required']['unsupported_answers'], 1)
            self.assertEqual(result['arms']['required']['supported_answers'], 4)

    def test_correct_guess_without_available_evidence_is_not_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(root / 'prepared')
            answer = {key: dict(value=item['value'], quote=item['quote']) for key, item in REFERENCE.items()}
            path = root / 'answer.json'
            path.write_text(json.dumps(answer))
            result = score(root / 'prepared', path, path, 'scripted_citation_control_not_a_model')
            self.assertEqual(result['arms']['baseline']['unsupported_answers'], 3)
            self.assertEqual(result['arms']['required']['unsupported_answers'], 0)
            prompt = root / 'prepared/required-prompt.md'
            prompt.write_text(prompt.read_text() + 'Changed input.')
            with self.assertRaises(ValueError):
                score(root / 'prepared', path, path, 'not_a_model')

    def test_full_source_baseline_and_sizes_remain_distinct_from_query_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(root / 'prepared')
            answer = {key: dict(value=item['value'], quote=item['quote']) for key, item in REFERENCE.items()}
            path = root / 'answer.json'
            path.write_text(json.dumps(answer))
            result = score(root / 'prepared', path, path, 'scripted_accounting_control_not_a_reader', path)
            self.assertTrue(result['full_source_baseline_included'])
            self.assertEqual(result['arms']['full_source']['supported_answers'], 5)
            self.assertEqual(result['arms']['baseline']['unsupported_answers'], 3)
            self.assertEqual(set(result['arm_sizes']), {'baseline', 'required', 'full_source'})
            for arm in result['arm_sizes']:
                self.assertEqual(result['arm_sizes'][arm]['prompt_chars'],
                                 len((root / 'prepared' / f'{arm}-prompt.md').read_text()))
            prompt = root / 'prepared/full_source-prompt.md'
            prompt.write_text(prompt.read_text() + 'Changed source input.')
            with self.assertRaises(ValueError):
                score(root / 'prepared', path, path, 'not_a_reader', path)
