"""Explicit relationship checks use invented statements and evidence coordinates."""

from pathlib import Path
import unittest

from agent_sessions.analysis.claims import section_evidence
from agent_sessions.analysis.relations import find_relations, render_relations

OLD = 'Keep the example cache local.'
NEW = 'Use the example queue instead.'


def section(text, index=1, sid='synthetic-source', role='Assistant', agent='codex'):
    return section_evidence(Path('/workspace') / f'{sid}.md', index, role, agent), text


class RelationTests(unittest.TestCase):
    def test_replacement_keeps_witness_and_original_context_with_exact_coordinates(self):
        old = section(f'Decision: {OLD}', 2)
        witness = section(f'TASK-042\nCorrection: Replace "{OLD}" with "{NEW}".', 5)
        relations = find_relations([old, witness])
        self.assertEqual(len(relations), 1)
        r = relations[0]
        self.assertEqual((r['kind'], r['status']), ('proposed_correction', 'linked'))
        self.assertEqual((r['original'], r['replacement']), (OLD, NEW))
        self.assertEqual(r['verification'], 'not_checked')
        self.assertEqual(r['witness']['conversation_section'], 5)
        self.assertEqual(r['witness']['section_line'], 2)
        self.assertEqual(r['original_sources'][0]['conversation_section'], 2)
        self.assertEqual(r['original_sources'][0]['quote'], f'Decision: {OLD}')
        self.assertEqual(r['original_sources'][0]['matched_quote'], OLD)
        self.assertEqual(r['replacement_sources'][0]['quote'], r['witness']['quote'])
        self.assertEqual(relations, find_relations([old, witness]))
        rendered = '\n'.join(render_relations(relations))
        self.assertIn('does not establish adoption or correctness', rendered)
        self.assertIn('cleaned section line 2', rendered)
        self.assertIn(f'Decision: {OLD}', rendered)

    def test_supported_quotes_and_explicit_framing(self):
        witnesses = [
            f'Replace "{OLD}" with "{NEW}".',
            f'Please replace “{OLD}” with: “{NEW}”.',
            f'- **Correction:** Replace `{OLD}` with `{NEW}`.',
            f"Correction: Replace '{OLD}' with '{NEW}'.",
            f'Correction: Replace ‘{OLD}’ with ‘{NEW}’.',
        ]
        for text in witnesses:
            with self.subTest(text=text):
                r = find_relations([section(OLD), section(text, 2)])[0]
                self.assertEqual(r['kind'], 'proposed_correction')
                self.assertEqual(r['status'], 'linked')

    def test_supersession_and_correction_direction_do_not_depend_on_input_order(self):
        for verb, kind in [('supersedes', 'reported_supersession'), ('corrects', 'reported_correction')]:
            with self.subTest(verb=verb):
                witness = section(f'"{NEW}" {verb} "{OLD}".', 4, 'synthetic-cursor', agent='cursor')
                r = find_relations([witness, section(OLD, 2)])[0]
                self.assertEqual((r['kind'], r['status']), (kind, 'linked'))
                self.assertEqual((r['original'], r['replacement']), (OLD, NEW))
                self.assertEqual(r['witness']['agent'], 'cursor')
                self.assertEqual(r['original_sources'][0]['agent'], 'codex')

    def test_conflict_requires_both_references_outside_relationship_lines(self):
        witness = section(f'Conflict: "{OLD}" conflicts with "{NEW}".', 3)
        r = find_relations([section(OLD), section(NEW, 2), witness])[0]
        self.assertEqual((r['kind'], r['status']), ('reported_conflict', 'linked'))
        missing = find_relations([section(OLD), witness])[0]
        self.assertEqual(missing['status'], 'unresolved')
        self.assertEqual(missing['replacement_sources'], [])
        self.assertEqual(find_relations([witness])[0]['original_sources'], [])

    def test_duplicates_remain_ambiguous_including_copied_cross_agent_statements(self):
        witnesses = [section(OLD), section(OLD, 1, 'synthetic-copy', agent='cursor'),
                     section(f'Replace "{OLD}" with "{NEW}".', 2)]
        r = find_relations(witnesses)[0]
        self.assertEqual(r['status'], 'ambiguous')
        self.assertEqual(len(r['original_sources']), 2)
        rendered = '\n'.join(render_relations([r]))
        self.assertIn('synthetic-source', rendered)
        self.assertIn('synthetic-copy', rendered)
        self.assertIn('Multiple matches remain visible', rendered)

    def test_relationship_quotes_cannot_provide_each_others_missing_original(self):
        text = f'Replace "{OLD}" with "{NEW}".'
        relations = find_relations([section(text), section(text, 2)])
        self.assertEqual(len(relations), 2)
        self.assertTrue(all(r['status'] == 'unresolved' and not r['original_sources'] for r in relations))

    def test_target_context_preserves_negation_without_claiming_semantic_agreement(self):
        text = f'Do not accept this proposal: {OLD}'
        r = find_relations([section(text), section(f'Replace "{OLD}" with "{NEW}".', 2)])[0]
        self.assertEqual(r['status'], 'linked')  # Reference location only, not semantic verification.
        self.assertEqual(r['original_sources'][0]['quote'], text)
        self.assertIn(text, '\n'.join(render_relations([r])))
        self.assertEqual(r['verification'], 'not_checked')

    def test_casual_hypothetical_negative_question_short_and_multi_quote_wording_abstains(self):
        cases = [
            f'I prefer "{OLD}" over "{NEW}".',
            f'If needed, replace "{OLD}" with "{NEW}".',
            f'Do not replace "{OLD}" with "{NEW}".',
            f'Replace "{OLD}" with "{NEW}"?',
            'Replace "cache" with "queue".',
            'Replace "        " with "a synthetic alternative".',
            f'Replace "{OLD}" with "{OLD}".',
            f'Replace "{OLD}" with "{NEW}" or "another example approach".',
            f'Correction: the earlier conclusion was wrong. {NEW}',
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(find_relations([section(OLD), section(text, 2)]), [])

    def test_same_section_can_cite_an_original_line_and_later_relationship_line(self):
        r = find_relations([section(f'{OLD}\nReplace "{OLD}" with "{NEW}".')])[0]
        self.assertEqual(r['status'], 'linked')
        self.assertEqual(r['original_sources'][0]['section_line'], 1)
        self.assertEqual(r['witness']['section_line'], 2)


if __name__ == '__main__':
    unittest.main()
