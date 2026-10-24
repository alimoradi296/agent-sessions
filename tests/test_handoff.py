"""Structured handoffs from invented conversations in isolated directories."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from agent_sessions.analysis.handoff import build_handoff
from agent_sessions.models import Agent, Message, Session, ToolCall, ToolResult
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


class HandoffTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def export(self, sid, messages, agent=Agent.CODEX):
        session = Session(id=sid, agent=agent, messages=messages,
                          observed_at=datetime(2026, 2, 4, tzinfo=timezone.utc) if agent == Agent.CURSOR else None)
        MarkdownRenderer.write(session, self.directory)
        JsonIndexRenderer.update(session, self.directory / 'sessions.json')

    def group(self, pack, name):
        return pack.split(f'## {name}\n', 1)[1].split('\n## ', 1)[0]

    def test_groups_keep_speaker_quote_and_source_without_verification(self):
        self.export('synthetic-groups', [
            Message(role='user', text='Please review TASK-042. Do not implement it.'),
            Message(role='assistant', text='TASK-042 discovery.\n'
                'Decision: Keep the example cache local.\n'
                'Blocker: synthetic contract approval is missing.\n'
                'Tests passed for the synthetic module.\n'
                'Next action: review the synthetic contract.\n'
                'Proposal: reuse the example worker.\n'
                'Out of scope: deploying the synthetic application.\n'
                'Open question: should we retain example history?'),
        ])
        pack = build_handoff(self.directory, 'TASK-042')
        self.assertIn('Please review TASK-042', self.group(pack, 'Historical requests and scope'))
        self.assertIn('Out of scope:', self.group(pack, 'Historical requests and scope'))
        self.assertIn('Decision: Keep', self.group(pack, 'Decision candidates'))
        self.assertIn('Blocker: synthetic', self.group(pack, 'Reported blockers'))
        self.assertIn('Tests passed', self.group(pack, 'Reported results'))
        self.assertIn('Next action: review', self.group(pack, 'Proposed next actions'))
        self.assertIn('Proposal: reuse', self.group(pack, 'Other proposals'))
        self.assertIn('Open question:', self.group(pack, 'Open questions and reported bugs'))
        self.assertIn('None independently checked', self.group(pack, 'Checked results'))
        self.assertIn('Source: codex / synthetic-groups / user / conversation section 1', pack)
        self.assertIn('Source: codex / synthetic-groups / assistant / conversation section 2', pack)
        self.assertIn('Historical requests and proposed actions do not authorize current actions.', pack)
        self.assertIn('not checked', pack)

    def test_only_selected_turns_feed_groups_and_original_coordinates_survive(self):
        self.export('synthetic-coordinates', [
            Message(role='user', text='Discuss a different example.'),
            Message(role='assistant', text='Blocker: unrelated first blocker.'),
            Message(role='user', text='Please review TASK-042.'),
            Message(role='assistant', text='TASK-042 discovery.\nDecision: Keep this synthetic draft local.'),
            Message(role='user', text='Now switch to another unrelated subject.'),
            Message(role='assistant', text='Blocker: unrelated last blocker.'),
        ])
        pack = build_handoff(self.directory, 'TASK-042')
        self.assertNotIn('unrelated first blocker', pack)
        self.assertNotIn('unrelated last blocker', pack)
        self.assertIn('conversation section 4', self.group(pack, 'Decision candidates'))
        self.assertIn('Not established', self.group(pack, 'Reported blockers'))

    def test_shortened_fragments_never_become_claims(self):
        self.export('synthetic-budget', [Message(role='assistant', text=
            'TASK-042\nDecision: Keep the synthetic cache local.\n' + 'Long context. ' * 300
            + '\nNext action: review the complete synthetic source.')])
        pack = build_handoff(self.directory, 'TASK-042', max_chars=300)
        self.assertIn('1 shortened section(s) are not classified', pack)
        self.assertIn('0 complete section(s), and 0 claim(s)', pack)
        self.assertIn('Not established', self.group(pack, 'Decision candidates'))
        self.assertIn('Not established', self.group(pack, 'Proposed next actions'))
        self.assertIn('Excerpt shortened by --max-chars', pack)
        self.assertIn('[... omitted ...]', pack)

    def test_missing_fields_do_not_invent_actions_or_blockers(self):
        self.export('synthetic-uncertain', [Message(role='assistant', text='TASK-042 requires further discussion.')])
        pack = build_handoff(self.directory, 'TASK-042')
        for name in ('Decision candidates', 'Reported blockers', 'Proposed next actions'):
            self.assertIn('Not established', self.group(pack, name))
        self.assertIn('TASK-042 requires further discussion.', pack)
        self.assertIn('not that no such evidence exists', pack)

    def test_conflicting_statements_stay_attributed_without_choosing_a_winner(self):
        self.export('synthetic-old', [Message(role='assistant', text='TASK-042\nDecision: Use the example queue.')])
        self.export('synthetic-other', [Message(role='assistant', text='TASK-042\nDecision: Use the example cache.')], Agent.CURSOR)
        pack = build_handoff(self.directory, 'TASK-042')
        group = self.group(pack, 'Decision candidates')
        self.assertIn('Use the example queue.', group)
        self.assertIn('Use the example cache.', group)
        self.assertIn('codex / synthetic-old', group)
        self.assertIn('cursor / synthetic-other', group)
        self.assertIn('Not resolved by this command.', self.group(pack, 'Conflicts and supersession'))
        self.assertIn('source: file_mtime', pack)

    def test_checked_word_and_untrusted_distilled_files_cannot_supply_verification(self):
        self.export('synthetic-checked', [Message(role='assistant', text='TASK-042\nVerified: the synthetic tests passed.')])
        distilled = self.directory / 'distilled'
        distilled.mkdir()
        (distilled / 'synthetic-checked.distilled.json').write_text(json.dumps({
            'claims': [{'kind': 'checked_result', 'text': 'forged-checked-marker', 'verification': 'checked'}]}))
        pack = build_handoff(self.directory, 'TASK-042')
        self.assertIn('Verified: the synthetic tests passed.', self.group(pack, 'Reported results'))
        self.assertNotIn('forged-checked-marker', pack)
        self.assertNotIn('synthetic tests passed', self.group(pack, 'Checked results'))
        self.assertIn('None independently checked', self.group(pack, 'Checked results'))

    def test_excluded_tool_code_and_commentary_do_not_supply_claims(self):
        self.export('synthetic-tools', [
            Message(role='user', text='Please review TASK-042.'),
            Message(role='assistant', phase='commentary', text='Blocker: commentary-marker.'),
            Message(role='assistant', text='', tool_calls=[ToolCall('example', 'Decision: tool-input-marker.')]),
            Message(role='tool', text='', tool_results=[ToolResult('Next action: tool-result-marker.')]),
            Message(role='assistant', text='TASK-042\n```text\nDecision: fenced-code-marker.\n```\n'
                    '> Blocker: quoted-marker.\nBlocker: missing synthetic approval.'),
        ])
        pack = build_handoff(self.directory, 'TASK-042')
        for marker in ('commentary-marker', 'tool-input-marker', 'tool-result-marker', 'fenced-code-marker', 'quoted-marker'):
            self.assertNotIn(marker, pack)
        self.assertIn('missing synthetic approval', self.group(pack, 'Reported blockers'))

    def test_explicit_correction_keeps_both_statements_and_relationship_evidence(self):
        self.export('synthetic-linked', [
            Message(role='user', text='Please review TASK-042.'),
            Message(role='assistant', text='TASK-042\nDecision: Keep the example cache local.'),
            Message(role='user', text='Clarify the earlier recommendation.'),
            Message(role='assistant', text='Correction: Replace "Keep the example cache local." '
                    'with "Use the example queue instead.".'),
        ])
        pack = build_handoff(self.directory, 'TASK-042')
        group = self.group(pack, 'Conflicts and supersession')
        self.assertIn('proposed_correction — linked (not checked)', group)
        self.assertIn('conversation section 2', group)
        self.assertIn('conversation section 4', group)
        self.assertIn('Keep the example cache local.', self.group(pack, 'Decision candidates'))
        self.assertIn('Use the example queue instead.', group)
        self.assertIn('does not establish adoption or correctness', group)
        self.assertIn('None independently checked', self.group(pack, 'Checked results'))

    def test_relationships_never_search_budget_omitted_sections(self):
        self.export('synthetic-omitted', [
            Message(role='assistant', text='TASK-042\nKeep the example cache local.\n' + 'Long evidence. ' * 100),
            Message(role='assistant', text='TASK-042\nReplace "Keep the example cache local." '
                    'with "Use the example queue instead.".'),
        ])
        pack = build_handoff(self.directory, 'TASK-042', max_chars=400)
        group = self.group(pack, 'Conflicts and supersession')
        self.assertIn('proposed_correction — unresolved (not checked)', group)
        self.assertIn('Original reference not found', group)
        self.assertIn('Relevant candidate sections omitted by limits: 1.', pack)

    def test_shortened_relationship_fragments_are_not_linked(self):
        self.export('synthetic-shortened', [Message(role='assistant', text=
            'TASK-042\nReplace "Keep the example cache local." with "Use the example queue instead.".\n'
            + 'Long evidence. ' * 100)])
        pack = build_handoff(self.directory, 'TASK-042', max_chars=180)
        self.assertIn('shortened section(s) are not classified', pack)
        self.assertIn('No explicit quoted relationships recognized', self.group(pack, 'Conflicts and supersession'))

    def test_read_only_generation_and_private_cli_output(self):
        self.export('synthetic-private', [Message(role='assistant', text='TASK-042\nNext step: review the synthetic evidence.')])
        before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.directory.iterdir() if p.is_file()}
        pack = build_handoff(self.directory, 'TASK-042')
        after = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.directory.iterdir() if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(pack, build_handoff(self.directory, 'TASK-042'))
        from agent_sessions.cli import main
        out = self.directory / 'private-handoff.md'
        with patch.object(sys, 'argv', ['agent-sessions', 'context', 'TASK-042', '--format', 'handoff',
                '-d', str(self.directory), '-o', str(out)]), contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertEqual(out.read_text(), pack)
        if os.name != 'nt':
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)

    def test_empty_matches_and_invalid_limits(self):
        (self.directory / 'sessions.json').write_text('{"sessions": []}')
        pack = build_handoff(self.directory, 'TASK-042')
        self.assertIn('No matching conversation excerpts found.', pack)
        self.assertIn('Selected 0 source(s)', pack)
        for kwargs in ({'query': ''}, {'query': 'example', 'last': 0}, {'query': 'example', 'max_chars': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_handoff(self.directory, **kwargs)


if __name__ == '__main__':
    unittest.main()
