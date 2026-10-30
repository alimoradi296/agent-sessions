"""Update raw evidence without confusing exporter framing with event identity."""

from pathlib import Path
import tempfile
import unittest

from agent_sessions.analysis.continuity import pin_requirement, compile_handoff, write_bundle, audit_bundle
from agent_sessions.analysis.transcript import export_boundary_variant
from agent_sessions.models import Agent, Session, Message, ToolResult
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer

VALUE = 'SYNTHETIC_OBSERVATION: incomplete'


class RawUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / 'exports'
        self.requirements = self.root / 'private' / 'requirements.json'
        self.session = Session(id='synthetic-update', agent=Agent.CURSOR,
                               messages=[Message(role='tool', text='', tool_results=[ToolResult(VALUE)])])
        self.export()
        pin_requirement(self.archive, self.requirements, 'observation', self.session.id, 1, VALUE, view='evidence')

    def export(self):
        MarkdownRenderer.write(self.session, self.archive)
        JsonIndexRenderer.update(self.session, self.archive / 'sessions.json')

    def compile(self):
        return compile_handoff(self.archive, 'SYNTHETIC_OBSERVATION', self.requirements)

    def test_unrelated_append_preserves_payload_and_reports_framing_change(self):
        self.session.messages.append(Message(role='user', text='A separate fictional question.'))
        self.export()
        text, manifest = self.compile()
        self.assertTrue(manifest['ready'])
        anchor = manifest['requirements'][0]
        self.assertEqual(anchor['section'], 1)
        self.assertEqual(anchor['source_update'], 'export_boundary_changed')
        self.assertEqual(anchor['export_boundary_adjustment'], 'separator_newline')
        self.assertIn(VALUE, text)
        bundle = self.root / 'current-bundle'
        write_bundle(bundle, text, manifest)
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 0)

    def test_appended_identical_result_does_not_rebind_to_new_last_message(self):
        self.session.messages.append(Message(role='tool', text='', tool_results=[ToolResult(VALUE)]))
        self.export()
        _, manifest = self.compile()
        anchor = manifest['requirements'][0]
        self.assertFalse(manifest['ready'])
        self.assertEqual(anchor['status'], 'anchor_ambiguous')
        self.assertEqual(anchor['candidate_sections'], [1, 2])

    def test_payload_newline_change_is_not_an_export_boundary_change(self):
        self.session.messages[0].tool_results[0].content += '\n'
        self.export()
        _, manifest = self.compile()
        self.assertFalse(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['status'], 'evidence_changed')

    def test_unique_relocation_rebuilds_citations_and_old_bundle_fails(self):
        text, original = self.compile()
        old = self.root / 'old-bundle'
        write_bundle(old, text, original)
        self.session.messages.insert(0, Message(role='user', text='A preceding fictional question.'))
        self.export()
        self.assertEqual(audit_bundle(old, self.archive)['exit_code'], 1)
        text, current = self.compile()
        self.assertTrue(current['ready'])
        self.assertEqual(current['requirements'][0]['section'], 2)
        self.assertEqual(current['requirements'][0]['source_update'], 'relocated')
        new = self.root / 'new-bundle'
        write_bundle(new, text, current)
        self.assertEqual(audit_bundle(new, self.archive)['exit_code'], 0)

    def test_unclosed_fenced_data_cannot_be_normalized_as_export_framing(self):
        self.assertIsNone(export_boundary_variant('## Tool\n\n```text\nData\n---\n\n'))

    def test_audit_and_compile_both_reject_duplicate_dialogue_identity(self):
        # Dialogue content already ignores the separator, so this separately
        # checks audit's identity rule rather than raw-message formatting.
        self.session.messages = [Message(role='assistant', text=VALUE)]
        self.export()
        requirements = self.root / 'dialogue.json'
        pin_requirement(self.archive, requirements, 'dialogue-observation', self.session.id, 1, VALUE)
        text, manifest = compile_handoff(self.archive, VALUE, requirements)
        bundle = self.root / 'dialogue-bundle'
        write_bundle(bundle, text, manifest)
        self.session.messages.append(Message(role='assistant', text=VALUE))
        self.export()
        _, current = compile_handoff(self.archive, VALUE, requirements)
        self.assertEqual(current['requirements'][0]['status'], 'anchor_ambiguous')
        audit = audit_bundle(bundle, self.archive)
        self.assertEqual(audit['exit_code'], 1)
        self.assertTrue(any(f.get('anchor_status') == 'anchor_ambiguous' for f in audit['findings']))
