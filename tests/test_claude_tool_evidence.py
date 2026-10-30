"""Synthetic Claude imports must preserve the evidence needed for replay."""

import json
import tempfile
import unittest
from pathlib import Path

from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.analysis.transcript import conversation_sections


class ClaudeToolEvidenceTests(unittest.TestCase):
    def test_complete_paired_tool_evidence_and_source_locations(self):
        argument = 'synthetic argument ' * 70
        output = 'synthetic output ' * 100
        records = [
            dict(type='user', message=dict(content='Inspect the example.')),
            dict(type='assistant', message=dict(content=[dict(type='tool_use', id='synthetic-call',
                 name='run_example', input=dict(text=argument))])),
            dict(type='user', message=dict(content=[dict(type='tool_result', tool_use_id='synthetic-call',
                 content=output, is_error=True)])),
            dict(type='user', message=dict(content='Correction: the TTL is 30 seconds.')),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic-claude.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in records) + '\n')
            session = ClaudeParser.parse(path)
            call = session.messages[1].tool_calls[0]
            result = session.messages[2].tool_results[0]
            self.assertEqual(call.call_id, result.call_id)
            self.assertEqual(call.call_id, 'synthetic-call')
            self.assertEqual(json.loads(call.arguments)['text'], argument)
            self.assertLessEqual(len(call.input_summary), 300)
            self.assertEqual(result.content, output)
            self.assertIs(result.is_error, True)
            self.assertEqual([m.source_line for m in session.messages], [1, 2, 3, 4])
            self.assertTrue(all(m.source_path == str(path) for m in session.messages))
            rendered = MarkdownRenderer.render(session)
            self.assertIn(argument, rendered)
            self.assertIn(output, rendered)
            self.assertIn('[is_error: true]', rendered)
            self.assertFalse(any('is_error' in body for _, body in conversation_sections(rendered)))

    def test_absent_error_flag_remains_unknown_and_false_is_preserved(self):
        records = [dict(type='user', message=dict(content=[dict(type='tool_result', tool_use_id='synthetic-a',
                        content='A captured result.')])),
                   dict(type='user', message=dict(content=[dict(type='tool_result', tool_use_id='synthetic-b',
                        content='A captured result.', is_error=False)]))]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic-claude.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in records))
            session = ClaudeParser.parse(path)
        self.assertIsNone(session.messages[0].tool_results[0].is_error)
        self.assertIs(session.messages[1].tool_results[0].is_error, False)
        rendered = MarkdownRenderer.render(session)
        self.assertEqual(rendered.count('[is_error:'), 1)
        self.assertIn('[is_error: false]', rendered)


if __name__ == '__main__':
    unittest.main()
