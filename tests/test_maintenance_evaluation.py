"""Check maintenance comparison accounting and preserve known audit blind spots."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.evaluate_maintenance import evaluate


class MaintenanceEvaluationTests(unittest.TestCase):
    def test_strong_hash_baselines_and_unrecognized_reversal_stay_visible(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(Path, 'home', side_effect=AssertionError('Unexpected private history access')):
            report = evaluate(Path(temporary))
        self.assertTrue(report['synthetic_only'])
        rows = {row['case']: row for row in report['cases']}
        quoted = rows['new-quoted-challenge']
        self.assertFalse(quoted['cited_source_checkpoint_changed'])
        self.assertTrue(quoted['archive_checkpoint_changed'])
        self.assertTrue(quoted['audit_requires_attention'])
        paraphrased = rows['new-paraphrased-challenge']
        self.assertTrue(paraphrased['should_review'])
        self.assertFalse(paraphrased['audit_requires_attention'])
        self.assertTrue(paraphrased['current_ready'])
        self.assertEqual(paraphrased['inspection_pending'], 1)
        append = rows['cited-unrelated-append']
        self.assertTrue(append['cited_source_checkpoint_changed'])
        self.assertFalse(append['audit_requires_attention'])
        for signal, summary in report['summary'].items():
            self.assertEqual(summary['detected'] + summary['missed'], sum(row['should_review'] for row in rows.values()))
            self.assertEqual(summary['nonchallenge_alerts'], sum(not row['should_review'] and row[signal] for row in rows.values()))


if __name__ == '__main__':
    unittest.main()
