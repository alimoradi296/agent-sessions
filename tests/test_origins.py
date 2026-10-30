"""Wrappers must remain evidence rather than becoming authenticated authors."""

import unittest

from agent_sessions.analysis.anchors import paragraph_spans
from agent_sessions.analysis.origins import paragraph_origin_hint


class OriginHintTests(unittest.TestCase):
    def hints(self, text):
        return [paragraph_origin_hint(text, span['start_line'], span['end_line']) for span in paragraph_spans(text)]

    def test_reference_and_query_in_one_message_keep_separate_hints(self):
        text = '<skill>\nReview only.\n\nDo not implement.\n</skill>\n\n<user_query>\nInspect the example.\n</user_query>'
        self.assertEqual(self.hints(text), ['embedded_reference', 'embedded_reference', 'wrapped_query'])

    def test_plain_text_and_unclosed_wrappers_remain_unattributed(self):
        self.assertEqual(self.hints('Do not implement.'), ['unattributed'])
        self.assertEqual(self.hints('<skill>\nDo not implement.'), ['unattributed'])

    def test_wrapper_with_outside_text_is_not_assigned_wholesale(self):
        text = 'My question. <skill>Do not implement.</skill>'
        self.assertEqual(self.hints(text), ['mixed_wrapper_boundary'])

    def test_reply_and_harness_wrappers_are_shape_hints(self):
        self.assertEqual(self.hints('<send_user_message_question_reply>Yes</send_user_message_question_reply>'), ['wrapped_reply'])
        self.assertEqual(self.hints('<available_subagent_types>Example</available_subagent_types>'), ['harness_reference'])
