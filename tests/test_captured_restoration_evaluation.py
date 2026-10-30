import unittest

from examples.evaluate_captured_restoration import evaluate


class CapturedRestorationEvaluationTests(unittest.TestCase):
    def test_public_comparison_has_exact_expected_outcome(self):
        result = evaluate()
        self.assertEqual(result["wrapper_aware_files"], 3)
        self.assertEqual(result["direct_call_baseline_files"], 1)
        self.assertEqual(result["additional_files_recovered"], 2)
        self.assertEqual(result["exact_updates_applied"], 1)
        self.assertTrue(result["all_expected_bytes_match"])
        self.assertFalse(result["archived_commands_executed"])
