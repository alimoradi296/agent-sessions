"""The coding comparison must supply equivalent facts and catch stale behavior."""

import tempfile
import unittest
from pathlib import Path

from examples.changed_context_coding import HISTORY, prepare, score


class ChangedContextCodingTests(unittest.TestCase):
    def test_complete_evidence_and_stale_starter_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            protocol = prepare(root)
            self.assertTrue(protocol['handoff_coverage_passed'])
            self.assertFalse(protocol['handoff_ready'])
            for arm in ('notes', 'handoff'):
                prompt = (root / arm / 'request.md').read_text()
                for _, text in HISTORY:
                    self.assertIn(text, prompt)
            result = score(root)
            for arm in result['results'].values():
                self.assertLess(arm['passed'], arm['total'])
                self.assertFalse(dict(arm['checks'])['default'])
                self.assertTrue(arm['request_unchanged'])
                self.assertTrue(arm['exclusion_function_unchanged'])


if __name__ == '__main__':
    unittest.main()
