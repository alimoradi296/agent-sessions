"""Scoring must require grounded paragraphs rather than matching source IDs."""

import json
import tempfile
import unittest
from pathlib import Path

from examples.review_scaling_evaluation import prepare, score


class ReviewScalingTests(unittest.TestCase):
    def test_grounded_selection_and_reuse_arithmetic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'exercise'
            prepared = prepare(root, sizes=(24,))
            self.assertEqual(prepared['rows'][0]['omissions'], 0)
            case = root / 'size-24'
            packet = json.loads((case / 'packet/review-packet.json').read_text())
            expected = json.loads((case / 'reference.json').read_text())['expected']
            response = dict(selected=[dict(session_id=sid, quote=quote, reason='Authored test replay.')
                                      for sid, quote in expected.items()],
                            unresolved_conflicts=True, current_authorization='read_only')
            (case / 'full-answer.json').write_text(json.dumps(response))
            response.update(review_id=packet['review_id'], reviewed_batches=list(packet['batches']))
            (case / 'batch-answer.json').write_text(json.dumps(response))
            result = score(root, 'Scripted test replay, not a reader observation.')
            self.assertEqual(result['selection']['batch']['retained'], 6)
            self.assertFalse(result['handoff_ready'])
            self.assertEqual(result['anchors'], 6)
            self.assertLess(result['saved_notes_chars'], result['handoff_chars'])
            one, two = result['repeated_character_accounting'][:2]
            self.assertEqual(two['review_then_handoff_chars'] - one['review_then_handoff_chars'],
                             result['handoff_chars'])
            # A correct source ID with an unrelated quote must not earn credit.
            full = json.loads((case / 'full-answer.json').read_text())
            full['selected'][0]['quote'] = 'Discussion of the example cache.'
            (case / 'full-answer.json').write_text(json.dumps(full))
            changed = score(root, 'Scripted invalid selection replay.')
            self.assertEqual(changed['selection']['full']['retained'], 5)
            self.assertEqual(len(changed['selection']['full']['unexpected']), 1)


if __name__ == '__main__':
    unittest.main()
