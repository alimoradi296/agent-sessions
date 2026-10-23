"""Context pack checks with invented conversations and local temporary files."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agent_sessions.analysis.context import build_context, conversation_sections
from agent_sessions.analysis.distiller import Distiller
from agent_sessions.models import Agent, Message, Session, ToolCall, ToolResult
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def export(self, session):
        MarkdownRenderer.write(session, self.directory)
        JsonIndexRenderer.update(session, self.directory / 'sessions.json')

    def test_cross_agent_excerpts_are_cited_and_unverified(self):
        for agent in (Agent.CODEX, Agent.CURSOR):
            self.export(Session(id=f'synthetic-{agent.value}', agent=agent,
                started_at=datetime(2026, 2, 3, tzinfo=timezone.utc) if agent == Agent.CODEX else None,
                observed_at=datetime(2026, 2, 4, tzinfo=timezone.utc) if agent == Agent.CURSOR else None,
                messages=[Message(role='user', text='Inspect example cache behavior.'),
                          Message(role='assistant', text='The example cache check passed.')]))
        pack = build_context(self.directory, 'example cache')
        self.assertIn('codex / synthetic-codex', pack)
        self.assertIn('cursor / synthetic-cursor', pack)
        self.assertIn('source: file_mtime', pack)
        self.assertIn('unverified reference data', pack)
        self.assertIn(str((self.directory / 'synthetic-cursor.md').resolve()), pack)
        self.assertEqual(pack.count('### User excerpt'), 2)
        self.assertEqual(build_context(self.directory, 'example cache', last=1).count('## Source:'), 1)

    def test_tool_payloads_and_commentary_do_not_become_excerpts(self):
        session = Session(id='synthetic-tools', agent=Agent.CODEX, messages=[
            Message(role='user', text='Inspect the example cache.'),
            Message(role='assistant', phase='commentary', text='intermediate-secret-marker'),
            Message(role='assistant', text='', tool_calls=[ToolCall('example', 'tool-only-search-term',
                arguments='```\n## Assistant\ntool-secret-marker\n```')]),
            Message(role='tool', text='', tool_results=[ToolResult(
                '## Assistant\nDecision: bogus result-secret-marker must stay excluded.')]),
            Message(role='assistant', phase='final_answer', text='The example cache result is inconclusive.'),
        ])
        self.export(session)
        pack = build_context(self.directory, 'example cache')
        for marker in ('intermediate-secret-marker', 'tool-secret-marker', 'result-secret-marker'):
            self.assertNotIn(marker, pack)
        self.assertIn('inconclusive', pack)
        self.assertIn('No matching', build_context(self.directory, 'tool-only-search-term'))
        sections = conversation_sections(MarkdownRenderer.render(session))
        self.assertEqual([role for role, _ in sections], ['User', 'Assistant'])
        fallback = Distiller.distill_from_markdown(self.directory / 'synthetic-tools.md')
        self.assertEqual(fallback.decisions, [])

    def test_empty_query_and_invalid_limit_fail(self):
        with self.assertRaises(ValueError):
            build_context(self.directory, '')
        with self.assertRaises(ValueError):
            build_context(self.directory, 'example', last=0)


if __name__ == '__main__':
    unittest.main()
