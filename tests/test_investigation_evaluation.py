"""Driver observations must count failures and preserve literal-search semantics."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from examples.investigation_reader_evaluation import drive, prepare


class InvestigationEvaluationTests(unittest.TestCase):
    def test_failed_driver_call_is_recorded_and_has_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            prepare(root)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as error:
                    drive(root, 'literal', ['read', '../reference.json', '1', '20'])
            self.assertEqual(error.exception.code, 2)
            self.assertIn('error', json.loads(output.getvalue()))
            events = [json.loads(line) for line in (root / 'literal/driver-events.jsonl').read_text().splitlines()]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['status'], 'error')

    def test_evidence_role_filter_returns_only_requested_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            prepare(root)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                drive(root, 'evidence', ['search', 'incidentA', '--role', 'user'])
            report = json.loads(output.getvalue())
            self.assertEqual(report['total_hits'], 1)
            self.assertEqual(report['hits'][0]['role'], 'User')
