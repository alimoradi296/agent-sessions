"""A correction must not be retroactively applied to an earlier operation."""

import unittest

from examples.chronology_replay_probe import CORRECTION, execute, operations


class ChronologyReplayTests(unittest.TestCase):
    def test_before_and_after_have_distinct_operation_outcomes(self):
        correction = ('text', CORRECTION)
        apply = ('apply', {'ttl_seconds': 60})
        self.assertTrue(execute([correction, apply])['failed'])
        self.assertFalse(execute([apply, correction])['failed'])
        self.assertFalse(execute([correction])['failed'])

    def test_assistant_claim_does_not_change_user_correction_state(self):
        statement = dict(type='assistant', message=dict(content=CORRECTION))
        self.assertEqual(list(operations(statement, 'claude')), [])
        call = dict(type='assistant', message=dict(content=[dict(type='tool_use', name='edit_example',
                                                               input=dict(ttl_seconds=60))]))
        sequence = [op for record in [statement, call] for op in operations(record, 'claude')]
        self.assertFalse(execute(sequence)['failed'])


if __name__ == '__main__':
    unittest.main()
