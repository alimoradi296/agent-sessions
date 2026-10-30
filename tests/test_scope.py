"""Exact metadata scopes over synthetic archives containing several projects."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.context import build_context
from agent_sessions.analysis.continuity import compile_handoff, pin_requirement, write_bundle, audit_bundle
from agent_sessions.analysis.search import search_archive, search_cache_path
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.workspace import initialize_workspace, add_topic, resume_topic

PROJECT_A = '/workspace/project-a'
PROJECT_B = '/workspace/project-b'
CURSOR_A = 'workspace-project-a'
ORIGINAL = 'Discovery only. Do not implement.'
CORRECTION = 'Correction: Replace "Discovery only. Do not implement." with "Implementation is proposed next.".'


class ScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / 'exports'
        self.requirements = self.root / 'requirements.json'
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected home access'))
        home.start()
        self.addCleanup(home.stop)
        self.export('synthetic-a', 'The example cache needs discovery.\n\n' + ORIGINAL, cwd=PROJECT_A)
        pin_requirement(self.archive, self.requirements, 'scope', 'synthetic-a', 1, ORIGINAL,
                         unit='paragraph', projects=[PROJECT_A])

    def export(self, sid, text, *, cwd='', slug='', agent=Agent.CODEX):
        session = Session(id=sid, agent=agent, cwd=cwd, project_slug=slug,
                          messages=[Message(role='assistant', text=text)])
        MarkdownRenderer.write(session, self.archive)
        JsonIndexRenderer.update(session, self.archive / 'sessions.json')

    def unrelated_project(self):
        self.export('synthetic-b-original', 'The example cache belongs to a separate project.\n' + ORIGINAL
                    + '\nproject-b-only-marker', cwd=PROJECT_B)
        self.export('synthetic-b-correction', CORRECTION, slug='workspace-project-b', agent=Agent.CURSOR)

    def build(self, projects):
        return compile_handoff(self.archive, 'example cache', self.requirements, projects=projects)

    def test_unrelated_project_cannot_reopen_a_scoped_review(self):
        self.unrelated_project()
        _, global_pack = self.build(None)
        self.assertFalse(global_pack['review_passed'])
        text, scoped = self.build([PROJECT_A])
        self.assertTrue(scoped['ready'])
        self.assertNotIn('project-b-only-marker', text)
        self.assertNotIn('synthetic-b-correction', text)
        self.assertEqual(scoped['scope']['in_scope_sources'], 1)
        self.assertEqual(scoped['scope']['excluded_sources'], 2)
        self.assertEqual(scoped['requirements'][0]['unreviewed_candidates'], [])

    def test_explicit_cross_agent_alias_keeps_in_scope_corrections_visible(self):
        self.unrelated_project()
        self.export('synthetic-a-correction', CORRECTION, slug=CURSOR_A, agent=Agent.CURSOR)
        _, single = self.build([PROJECT_A])
        self.assertTrue(single['ready'])
        _, aliased = self.build([PROJECT_A, CURSOR_A])
        self.assertFalse(aliased['ready'])
        candidates = aliased['requirements'][0]['unreviewed_candidates']
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['witness']['session_id'], 'synthetic-a-correction')
        self.assertEqual(candidates[0]['witness']['agent'], 'cursor')

    def test_pins_outside_the_declared_scope_are_rejected_not_silently_included(self):
        self.export('synthetic-b', ORIGINAL, cwd=PROJECT_B)
        with self.assertRaises(ValueError):
            pin_requirement(self.archive, self.root / 'outside.json', 'other', 'synthetic-b', 1,
                             ORIGINAL, projects=[PROJECT_A])
        self.assertFalse((self.root / 'outside.json').exists())
        _, manifest = self.build([PROJECT_B])
        self.assertFalse(manifest['ready'])
        self.assertEqual(manifest['requirements'][0]['status'], 'outside_project_scope')

    def test_scoped_handoff_and_audit_do_not_read_excluded_transcript_contents(self):
        self.unrelated_project()
        for name in ('synthetic-b-original.md', 'synthetic-b-correction.md'):
            (self.archive / name).write_bytes(b'\xff invalid UTF-8 in an excluded source')
        text, manifest = self.build([PROJECT_A, CURSOR_A])
        self.assertTrue(manifest['ready'])
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        self.assertEqual(audit_bundle(bundle, self.archive)['exit_code'], 0)
        self.assertEqual(search_archive(self.archive, 'example cache', projects=[PROJECT_A])['total_hits'], 1)
        self.export('synthetic-a-correction', CORRECTION, slug=CURSOR_A, agent=Agent.CURSOR)
        audit = audit_bundle(bundle, self.archive)
        self.assertEqual(audit['exit_code'], 1)
        self.assertIn('quoted_change_requires_review', {finding['code'] for finding in audit['findings']})

    def test_changed_project_metadata_invalidates_a_captured_source(self):
        text, manifest = self.build([PROJECT_A])
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        index = self.archive / 'sessions.json'
        data = json.loads(index.read_text())
        data['sessions'][0]['cwd'] = PROJECT_B
        index.write_text(json.dumps(data))
        audit = audit_bundle(bundle, self.archive)
        self.assertEqual(audit['exit_code'], 1)
        self.assertIn('source_outside_project_scope', {finding['code'] for finding in audit['findings']})

    def test_missing_in_scope_sources_still_block_review_completion(self):
        self.export('synthetic-a-missing', 'Additional project evidence.', cwd=PROJECT_A)
        (self.archive / 'synthetic-a-missing.md').unlink()
        _, manifest = self.build([PROJECT_A])
        self.assertTrue(manifest['coverage_passed'])
        self.assertFalse(manifest['review_passed'])
        self.assertEqual(manifest['relationship_scan_warnings'][0]['code'], 'relationship_source_missing')

    def test_unknown_metadata_and_prefix_matches_are_not_guessed(self):
        self.export('synthetic-unknown', 'The example cache has unknown-project-marker.')
        self.export('synthetic-nearby', 'The example cache has nearby-project-marker.', cwd=PROJECT_A + '-other')
        text, manifest = self.build([PROJECT_A])
        self.assertTrue(manifest['ready'])
        self.assertNotIn('unknown-project-marker', text)
        self.assertNotIn('nearby-project-marker', text)
        self.assertEqual(manifest['scope']['missing_project_metadata'], 1)
        self.assertEqual(manifest['scope']['excluded_sources'], 2)
        excerpts = build_context(self.archive, 'example cache', projects=[PROJECT_A])
        self.assertNotIn('nearby-project-marker', excerpts)

    def test_multiple_search_selectors_filter_before_the_result_limit(self):
        self.unrelated_project()
        self.export('synthetic-a-cursor', 'The example cache has another relevant passage.', slug=CURSOR_A, agent=Agent.CURSOR)
        result = search_archive(self.archive, 'example cache', projects=[PROJECT_A, CURSOR_A], limit=100)
        self.assertEqual({hit['session_id'] for hit in result['hits']}, {'synthetic-a', 'synthetic-a-cursor'})
        self.assertNotIn('project-b-only-marker', json.dumps(result))

    def test_topic_scope_applies_to_search_pin_resume_review_and_history(self):
        self.unrelated_project()
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'example', 'example cache', requirements=self.requirements, projects=[PROJECT_A, CURSOR_A])
        first, _ = resume_topic(workspace, 'example')
        self.assertTrue(first['ready'])

        def cli(args, expected=0):
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(sys, 'argv', ['agent-sessions', *args, '--workspace', str(workspace)]), \
                 contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    main()
                    code = 0
                except SystemExit as error:
                    code = error.code
            self.assertEqual(code, expected, stderr.getvalue())
            return stdout.getvalue()

        search = json.loads(cli(['topic', 'search', 'example', '--json']))
        self.assertEqual({hit['session_id'] for hit in search['hits']}, {'synthetic-a'})
        cli(['topic', 'pin', 'example', '--id', 'bad', '--session', 'synthetic-b-original', '--section', '1'], expected=1)
        self.export('synthetic-a-correction', CORRECTION, slug=CURSOR_A, agent=Agent.CURSOR)
        draft = json.loads(cli(['resume', 'example', '--json'], expected=1))
        candidate = draft['manifest']['requirements'][0]['unreviewed_candidates'][0]['review_id']
        cli(['topic', 'review', 'example', '--id', 'scope', '--candidate', candidate,
             '--note', 'Retain both historical statements without accepting implementation.'])
        self.assertTrue(json.loads(cli(['resume', 'example', '--json']))['ready'])
        cli(['topic', 'set', 'example', '--all-projects'])
        global_pack = json.loads(cli(['resume', 'example', '--json'], expected=1))
        self.assertEqual(global_pack['manifest']['scope']['projects'], [])
        self.assertTrue(global_pack['history']['changes']['scope_changed'])

    def test_invalid_scope_values_fail_before_cache_creation(self):
        for value in ('not-a-list', [''], ['x'] * 33, [None]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.build(value)
                with self.assertRaises(ValueError):
                    search_archive(self.archive, 'example', projects=value)

    def test_scoped_cache_is_separate_and_selector_order_has_no_authority(self):
        self.unrelated_project()
        self.export('synthetic-a-cursor', 'The example cache has another relevant passage.', slug=CURSOR_A, agent=Agent.CURSOR)
        global_result = search_archive(self.archive, 'example cache')
        self.assertEqual(global_result['index']['sessions'], 4)
        scoped = search_archive(self.archive, 'example cache', projects=[CURSOR_A, PROJECT_A])
        self.assertEqual(scoped['index']['sessions'], 2)
        self.assertNotEqual(search_cache_path(self.archive), search_cache_path(self.archive, [PROJECT_A, CURSOR_A]))
        self.assertEqual(search_cache_path(self.archive, [PROJECT_A, CURSOR_A]),
                         search_cache_path(self.archive, [CURSOR_A, PROJECT_A]))
        again = search_archive(self.archive, 'example cache', projects=[PROJECT_A, CURSOR_A])
        self.assertEqual(again['index']['updated'], 0)
        self.assertEqual(again['index']['unchanged'], 2)

    def test_metadata_move_removes_old_scope_cache_entries_without_reading_the_moved_source(self):
        self.assertEqual(search_archive(self.archive, 'example cache', projects=[PROJECT_A])['total_hits'], 1)
        index = self.archive / 'sessions.json'
        data = json.loads(index.read_text())
        data['sessions'][0]['cwd'] = PROJECT_B
        index.write_text(json.dumps(data))
        (self.archive / 'synthetic-a.md').write_bytes(b'\xff now outside scope')
        result = search_archive(self.archive, 'example cache', projects=[PROJECT_A])
        self.assertEqual(result['total_hits'], 0)
        self.assertEqual(result['index']['removed'], 1)

    def test_changed_manifest_cannot_broaden_audit_reads_before_identity_validation(self):
        self.unrelated_project()
        text, manifest = self.build([PROJECT_A])
        bundle = self.root / 'bundle'
        write_bundle(bundle, text, manifest)
        manifest['scope']['projects'] = []
        (bundle / 'manifest.json').write_text(json.dumps(manifest))
        for path in self.archive.glob('*.md'):
            path.write_bytes(b'\xff must not be read after invalid manifest identity')
        audit = audit_bundle(bundle, self.archive)
        self.assertEqual(audit['exit_code'], 1)
        self.assertEqual([finding['code'] for finding in audit['findings']], ['manifest_changed'])

    def test_null_saved_scope_does_not_silently_become_all_projects(self):
        workspace = self.root / 'workspace'
        initialize_workspace(workspace, self.archive)
        add_topic(workspace, 'example', 'example cache', requirements=self.requirements, projects=[PROJECT_A])
        path = workspace / 'workspace.json'
        config = json.loads(path.read_text())
        config['topics']['example']['projects'] = None
        path.write_text(json.dumps(config))
        from agent_sessions.storage import StorageError
        with self.assertRaises(StorageError):
            resume_topic(workspace, 'example')


if __name__ == '__main__':
    unittest.main()
