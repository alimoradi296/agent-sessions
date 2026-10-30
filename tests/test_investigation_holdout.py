"""A holdout's different references must not reuse the original answer labels."""

import json
import tempfile
import unittest
from pathlib import Path

from examples.investigation_text_holdout import prepare
from examples.investigation_reader_evaluation import score


class InvestigationHoldoutTests(unittest.TestCase):
    def test_clarified_followup_is_separate_and_actor_boundary_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'followup'
            result = prepare(root, clarify_actor=True)
            self.assertFalse(result['holdout'])
            self.assertTrue(result['clarified_followup'])
            task = (root / 'literal/request.txt').read_text()
            self.assertIn('User-pasted code does not establish Assistant supply.', task)
            self.assertIn('in the same conversation', task)

    def test_scoring_uses_declared_holdout_sources_and_conclusions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            prepare(root)
            protocol = json.loads((root / 'reference.json').read_text())
            refs = protocol['supporting_lines']
            def items(source, quotes):
                return [dict(source=source, line=line, quote=quote) for quote in quotes for line in refs[source][quote]]
            a, b = protocol['sources']
            answer = dict(case_a=dict(conclusion='latest_version', evidence=items(a, protocol['code_quotes'])),
                          case_b=dict(conclusion='unattributed', evidence=items(b, protocol['case_b_quotes'])),
                          fix_status='not_established', fix_evidence=items(a, [protocol['fix_quote']]), next_action='analysis_only')
            for arm in ('literal', 'evidence'):
                (root / arm / 'answer.json').write_text(json.dumps(answer))
                (root / arm / 'driver-events.jsonl').write_text('')
            self.assertEqual(score(root)['results']['literal']['passed'], 4)
            answer['case_a']['conclusion'] = 'earlier_version'
            answer['case_b']['conclusion'] = 'multiple_candidates'
            (root / 'literal/answer.json').write_text(json.dumps(answer))
            self.assertEqual(score(root)['results']['literal']['passed'], 2)


if __name__ == '__main__':
    unittest.main()
