"""Manually labeled synthetic cases; no developer transcripts or home reads."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

from agent_sessions.analysis.claims import METHOD, claims_from_session
from agent_sessions.analysis.distiller import DistilledSession, Distiller
from agent_sessions.analysis.obsidian import ObsidianExporter
from agent_sessions.analysis.report import WeeklyReport
from agent_sessions.models import Agent, Message, Session, ToolCall, ToolResult
from agent_sessions.renderers.markdown import MarkdownRenderer


class ClaimTests(unittest.TestCase):
    def session(self, messages, **kwargs):
        return Session(id='synthetic-claims', agent=Agent.CODEX, messages=messages, **kwargs)

    def test_labeled_synthetic_dataset(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/claim_labels.json').read_text())
        for case in cases:
            with self.subTest(case=case['name']):
                session = self.session([Message(role=case['role'], text=case['text'], phase=case.get('phase', ''))])
                claims = claims_from_session(session)
                self.assertEqual([c['kind'] for c in claims], case['expected'])
                for claim in claims:
                    self.assertEqual(claim['method'], METHOD)
                    self.assertEqual(claim['verification'], 'not_checked')
                    self.assertIn(claim['evidence']['quote'], case['text'])
                    self.assertEqual(claim['evidence']['role'], case['role'])

    def test_references_preserve_raw_message_index_line_speaker_and_quote(self):
        session = self.session([
            Message(role='tool', text='Tests passed in an ignored tool result.'),
            Message(role='assistant', text='Decision: Keep the example cache local.\nTests passed for the example module.',
                    source_path='/workspace/example/transcript.jsonl', source_line=42),
            Message(role='user', text='Please review the example draft.'),
        ])
        claims = Distiller.distill(session).claims
        self.assertEqual(len(claims), 3)
        self.assertEqual(claims[0]['evidence'], dict(
            session_id=session.id, agent='codex', role='assistant', source='transcript_message',
            message_index=2, source_path='/workspace/example/transcript.jsonl', source_line=42,
            quote='Decision: Keep the example cache local.'))
        self.assertEqual(claims[2]['evidence']['message_index'], 3)
        self.assertIsNone(claims[2]['evidence']['source_line'])
        self.assertIsNone(claims[2]['evidence']['source_path'])
        self.assertEqual(claims, Distiller.distill(session).claims)
        self.assertEqual(len({c['id'] for c in claims}), 3)

    def test_same_quote_in_different_messages_preserves_separate_evidence(self):
        session = self.session([Message(role='assistant', text='Tests passed for the synthetic example.') for _ in range(2)])
        claims = Distiller.distill(session).claims
        self.assertEqual(len(claims), 2)
        self.assertNotEqual(claims[0]['id'], claims[1]['id'])

    def test_full_claim_quote_survives_legacy_snippet_limits(self):
        quote = 'Decision: ' + 'Keep the synthetic evidence available. ' * 30
        distilled = Distiller.distill(self.session([Message(role='assistant', text=quote)]))
        self.assertEqual(distilled.claims[0]['evidence']['quote'], quote.strip())
        self.assertEqual(distilled.claims[0]['text'], quote.strip())
        self.assertGreater(len(distilled.claims[0]['text']), 200)

    def test_requests_proposals_titles_and_tools_never_establish_outcomes(self):
        session = self.session([
            Message(role='user', text='Implement and deploy the example repair.'),
            Message(role='assistant', text='Proposal: deploy the example repair after testing.'),
            Message(role='assistant', text='', tool_calls=[ToolCall('example', 'Implemented: bogus tool summary')]),
            Message(role='tool', text='', tool_results=[ToolResult('Tests passed for the example module.')]),
        ], title='Implemented and deployed the example repair', summary='Tests passed, according to a summary.')
        distilled = Distiller.distill(session)
        self.assertEqual(distilled.outcome, 'unknown')
        self.assertEqual([c['kind'] for c in distilled.claims], ['request', 'proposal'])
        self.assertEqual(distilled.decisions, [])

    def test_reported_execution_is_never_independently_checked(self):
        distilled = Distiller.distill(self.session([
            Message(role='assistant', text='I ran the example tests.\nTests passed for the synthetic module.\nVerified: the build is deployed.')]))
        self.assertEqual(distilled.outcome_source, 'heuristic_unverified')
        self.assertEqual({c['kind'] for c in distilled.claims}, {'reported_result'})
        self.assertTrue(all(c['verification'] == 'not_checked' for c in distilled.claims))
        self.assertNotIn('checked_result', [c['kind'] for c in distilled.claims])

    def test_markdown_fallback_uses_cleaned_sections_without_inventing_raw_lines(self):
        session = self.session([
            Message(role='assistant', phase='commentary', text='Decision: Ignore this commentary.'),
            Message(role='user', text='Please review the example draft.'),
            Message(role='assistant', text='Decision: Keep the example cache local.\nTests passed for the example module.'),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = MarkdownRenderer.write(session, Path(tmp))
            fallback = Distiller.distill_from_markdown(path, {'agent': 'codex'})
            direct = Distiller.distill(session)
            self.assertEqual([(c['kind'], c['text']) for c in fallback.claims],
                             [(c['kind'], c['text']) for c in direct.claims])
            evidence = fallback.claims[-1]['evidence']
            self.assertEqual(evidence['source'], 'export_section')
            self.assertEqual(evidence['conversation_section'], 2)
            self.assertEqual(evidence['source_path'], str(path.resolve()))
            self.assertIsNone(evidence['source_line'])
            self.assertNotIn('message_index', evidence)

    def test_legacy_load_round_trip_and_owner_only_save(self):
        distilled = Distiller.distill(self.session([Message(role='assistant', text='Decision: Keep the example cache local.')]))
        with tempfile.TemporaryDirectory() as tmp:
            path = distilled.save(Path(tmp))
            self.assertEqual(DistilledSession.load(path).claims, distilled.claims)
            self.assertEqual(DistilledSession.load(path).distill_version, 3)
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            old = distilled.to_dict()
            old.pop('claims')
            old['distill_version'] = 2
            path.write_text(json.dumps(old))
            legacy = DistilledSession.load(path)
            self.assertEqual(legacy.claims, [])
            self.assertEqual(legacy.distill_version, 2)
            self.assertEqual(legacy.decisions, distilled.decisions)
            self.assertNotIn('Source:', ObsidianExporter.render(legacy))
            old.pop('distill_version')
            path.write_text(json.dumps(old))
            self.assertEqual(DistilledSession.load(path).distill_version, 1)

    def test_cli_distillation_emits_cited_schema_v3_from_export_fallback(self):
        from agent_sessions.cli import cmd_distill, export_session
        session = self.session([
            Message(role='user', text='Please implement the example retry limit.'),
            Message(role='assistant', text='Proposal: keep the example retry limit at three.')])
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                export_session(session, directory)
            args = Namespace(directory=str(directory), session_id=session.id,
                             significant_only=False, min_duration=30, dry_run=False)
            with patch('agent_sessions.cli.load_source_session', return_value=None), \
                 contextlib.redirect_stdout(io.StringIO()):
                cmd_distill(args)
            saved = DistilledSession.load(directory / 'distilled' / f'{session.id}.distilled.json')
            self.assertEqual(saved.distill_version, 3)
            self.assertEqual(saved.outcome, 'unknown')
            self.assertEqual([c['kind'] for c in saved.claims], ['request', 'proposal'])
            self.assertEqual(saved.claims[0]['evidence']['source'], 'export_section')

    def test_reports_and_notes_keep_labels_and_citations(self):
        distilled = Distiller.distill(self.session([
            Message(role='user', text='Please implement the example repair.'),
            Message(role='assistant', text='Tests passed for the example module.',
                    source_path='/workspace/example/events.jsonl', source_line=17)]))
        for rendered in (ObsidianExporter.render(distilled), WeeklyReport([{"id": distilled.session_id, "agent": distilled.agent}], [distilled.to_dict()]).render()):
            self.assertIn('request', rendered)
            self.assertIn('reported_result', rendered)
            self.assertIn('not checked', rendered)
            self.assertIn('message 2, source line 17', rendered)
            self.assertIn('/workspace/example/events.jsonl', rendered)
            self.assertIn('synthetic-claims', rendered)


if __name__ == '__main__':
    unittest.main()
