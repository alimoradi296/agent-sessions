"""Authored rollback markers stay inspectable without claiming active replay."""
import json
from pathlib import Path
import tempfile
import unittest

from agent_sessions.parsers.codex import CodexParser
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.analysis.continuity import pin_requirement, compile_handoff, write_bundle, audit_bundle
from agent_sessions.analysis.transcript import sections_for_view


class RollbackEvidenceTests(unittest.TestCase):
    def parse(self, repetitions=1):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'synthetic.jsonl'
        def record(kind, payload):
            return dict(type=kind, payload=payload)
        rows = [record('session_meta', dict(id='synthetic-rollback')),
                record('response_item', dict(type='message', role='user',
                       content=[dict(type='input_text', text='Fictional earlier request.')])),
                record('response_item', dict(type='message', role='assistant',
                       content=[dict(type='output_text', text='Fictional historical result.')]))]
        rows += [record('event_msg', dict(type='thread_rolled_back', num_turns=1))] * repetitions
        rows += [record('response_item', dict(type='message', role='user',
                        content=[dict(type='input_text', text='Fictional replacement request.')]))]
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        diagnostics = {}
        return CodexParser.parse(path, diagnostics), diagnostics

    def test_marker_survives_between_earlier_history_and_replacement(self):
        session, diagnostics = self.parse()
        self.assertEqual([m.role for m in session.messages], ['user', 'assistant', 'system', 'user'])
        marker = session.messages[2]
        self.assertIn('"num_turns": 1', marker.text)
        self.assertEqual(marker.source_line, 4)
        self.assertIn('does not reconstruct active context', marker.text)
        # Retention must not silently certify native replay support.
        self.assertEqual(next(iter(diagnostics.values()))['unsupported'], 1)
        raw = sections_for_view(MarkdownRenderer.render(session), 'evidence')
        self.assertEqual(raw[2][0], 'System')
        self.assertIn('thread_rolled_back', raw[2][1])

    def test_repeated_markers_within_one_file_stay_distinct(self):
        session, diagnostics = self.parse(repetitions=2)
        markers = [m for m in session.messages if m.role == 'system']
        self.assertEqual([m.source_line for m in markers], [4, 5])
        self.assertEqual(next(iter(diagnostics.values()))['unsupported'], 2)

    def test_marker_can_be_required_and_audited_as_historical_evidence(self):
        session, _ = self.parse()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        archive = root / 'exports'
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
        requirements = root / 'requirements.json'
        pin_requirement(archive, requirements, 'rollback-marker', session.id, 3,
                        'thread_rolled_back', view='evidence')
        text, manifest = compile_handoff(archive, 'Fictional', requirements)
        self.assertTrue(manifest['ready'])
        self.assertIn('does not reconstruct active context', text)
        bundle = root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.assertEqual(audit_bundle(bundle, archive)['exit_code'], 0)
