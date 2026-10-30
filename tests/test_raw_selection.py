"""Assistant review must preserve raw evidence identity, budgets, and old work."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_sessions.analysis.continuity import compile_handoff, audit_bundle, write_bundle, pin_requirement
from agent_sessions.analysis.selection_import import prepare_selection_review, import_selection_review
from agent_sessions.cli import main
from agent_sessions.models import Agent, Session, Message, ToolResult
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.topic_review import prepare_topic_review, import_topic_review
from agent_sessions.workspace import initialize_workspace, add_topic, get_topic

PROJECT = '/workspace/synthetic-raw-project'
SIGNAL = 'SYNTHETIC_RESULT: incomplete'


class RawSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive, self.packet = self.root / 'exports', self.root / 'packet'
        self.requirements = self.root / 'requirements.json'
        self.session = Session(id='synthetic-raw-selection', agent=Agent.CODEX, cwd=PROJECT, messages=[
            Message(role='user', text='Inspect fictional-check. Historical reference only.'),
            Message(role='assistant', text='fictional-check is fixed. This is a historical claim.'),
            Message(role='tool', text='', tool_results=[ToolResult(SIGNAL)]),
            Message(role='tool', text='', tool_results=[ToolResult(SIGNAL)])])
        self.export()

    def export(self):
        MarkdownRenderer.write(self.session, self.archive)
        JsonIndexRenderer.update(self.session, self.archive / 'sessions.json')

    def answer(self, packet_dir, records):
        packet = json.loads((packet_dir / 'review-packet.json').read_text())
        response = dict(review_id=packet['review_id'], selected=[dict(
            session_id=r['session_id'], section=r['section'], paragraph_start_line=r['paragraph']['start_line'],
            quote=SIGNAL if r['role'] == 'Tool' else r['paragraph']['text'],
            reason='Retain this authored evidence without certifying a fix.') for r in records],
            unresolved_conflicts=False, current_authorization='read_only')
        if 'batches' in packet:
            response['reviewed_batches'] = list(packet['batches'])
        path = self.root / 'answer.json'
        path.write_text(json.dumps(response))
        return path

    def prepare(self, **kwargs):
        return prepare_selection_review(self.archive, self.packet, 'fictional-check', projects=[PROJECT],
                                        view='evidence', **kwargs)

    def test_cli_raw_review_import_retains_distinct_occurrences_and_audits(self):
        argv = ['agent-sessions', 'handoff', 'prepare-review', 'fictional-check', '--view', 'evidence',
                '-d', str(self.archive), '-o', str(self.packet), '--project', PROJECT,
                '--batch-review', '--compact-review', '--max-total-prompt-chars', '32000']
        with patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
            main()
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        self.assertEqual(packet['view'], 'evidence')
        tools = [r for r in packet['records'] if r['role'] == 'Tool']
        self.assertEqual(len(tools), 2)
        answer = self.answer(self.packet, tools)
        import_selection_review(self.packet, answer, self.requirements)
        contract = json.loads(self.requirements.read_text())
        self.assertEqual(contract['assistant_review']['view'], 'evidence')
        self.assertEqual(len(contract['requirements']), 2)
        self.assertEqual({r['section'] for r in contract['requirements']}, {3, 4})
        self.assertTrue(all(r['unit'] == 'section' and 'paragraph' not in r for r in contract['requirements']))
        text, manifest = compile_handoff(self.archive, 'fictional-check', self.requirements)
        self.assertTrue(manifest['ready'])
        self.assertEqual(manifest['verification'], 'not_checked')
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 0)

    def test_giant_unreviewed_message_keeps_review_incomplete(self):
        self.session.messages[-1].tool_results[0].content += 'x' * 8000
        self.export()
        self.prepare(max_prompt_chars=2200)
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        self.assertTrue(packet['omissions'])
        self.assertTrue(packet['records'])
        answer = self.answer(self.packet, packet['records'][:1])
        import_selection_review(self.packet, answer, self.requirements)
        contract = json.loads(self.requirements.read_text())
        self.assertTrue(contract['assistant_review']['incomplete_source_review'])
        _, manifest = compile_handoff(self.archive, 'fictional-check', self.requirements)
        self.assertFalse(manifest['ready'])

    def test_total_budget_refusal_and_source_change_create_no_contract(self):
        result = self.prepare(batch_review=True, compact_review=True, max_total_prompt_chars=1)
        self.assertEqual(result['status'], 'over_budget')
        self.assertFalse(self.packet.exists())
        self.prepare()
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        answer = self.answer(self.packet, [r for r in packet['records'] if r['role'] == 'Tool'][:1])
        self.session.messages[-1].tool_results[0].content += ' Changed.'
        self.export()
        with self.assertRaisesRegex(ValueError, 'source changed'):
            import_selection_review(self.packet, answer, self.requirements)
        self.assertFalse(self.requirements.exists())

    def test_topic_refresh_infers_view_and_preserves_manual_raw_pin(self):
        pin_requirement(self.archive, self.requirements, 'manual-claim', self.session.id, 2,
                        'fictional-check is fixed', view='evidence')
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'check', 'fictional-check', requirements=self.requirements, projects=[PROJECT])
        result = prepare_topic_review(workspace, 'check', batch_review=True)
        packet_dir = Path(result['output'])
        packet = json.loads((packet_dir / 'review-packet.json').read_text())
        answer = self.answer(packet_dir, [r for r in packet['records'] if r['role'] == 'Tool'][:1])
        original = self.requirements.read_bytes()
        import_topic_review(workspace, 'check', packet_dir, answer)
        _, _, topic = get_topic(workspace, 'check')
        current = json.loads(Path(topic['requirements']).read_text())
        self.assertEqual(current['view'], 'evidence')
        self.assertEqual({r['id'] for r in current['requirements']} & {'manual-claim'}, {'manual-claim'})
        self.assertEqual(self.requirements.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'Review views differ'):
            prepare_topic_review(workspace, 'check', view='dialogue')

    def test_new_topic_can_start_in_raw_review_without_manual_pins(self):
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'check', 'fictional-check', projects=[PROJECT])
        result = prepare_topic_review(workspace, 'check', view='evidence')
        packet_dir = Path(result['output'])
        packet = json.loads((packet_dir / 'review-packet.json').read_text())
        answer = self.answer(packet_dir, [r for r in packet['records'] if r['role'] == 'Tool'][:1])
        import_topic_review(workspace, 'check', packet_dir, answer)
        _, _, topic = get_topic(workspace, 'check')
        self.assertEqual(json.loads(Path(topic['requirements']).read_text())['view'], 'evidence')
        next_packet = prepare_topic_review(workspace, 'check')
        self.assertEqual(json.loads((Path(next_packet['output']) / 'review-packet.json').read_text())['view'], 'evidence')

    def test_repeated_raw_quote_requires_message_coordinates(self):
        self.prepare()
        packet = json.loads((self.packet / 'review-packet.json').read_text())
        answer = self.answer(self.packet, [r for r in packet['records'] if r['role'] == 'Tool'][:1])
        response = json.loads(answer.read_text())
        response['selected'][0].pop('section')
        response['selected'][0].pop('paragraph_start_line')
        answer.write_text(json.dumps(response))
        with self.assertRaisesRegex(ValueError, 'matches multiple paragraphs'):
            import_selection_review(self.packet, answer, self.requirements)
        self.assertFalse(self.requirements.exists())
