"""Passage retrieval, refresh, and privacy boundaries with synthetic exports."""

import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.search import CACHE_NAME, search_archive
from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.cli import main
from agent_sessions.models import Agent, Message, Session, ToolResult
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import StorageError


class SearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        home = patch.object(Path, 'home', side_effect=AssertionError('Unexpected home access'))
        home.start()
        self.addCleanup(home.stop)

    def export(self, sid, text, agent=Agent.CODEX, project='example', date=3, **extra):
        session = Session(id=sid, agent=agent, title='Unrelated title', project_slug=project,
                          started_at=datetime(2026, 2, date, tzinfo=timezone.utc),
                          messages=[Message(role='user', text='Inspect the example.'),
                                    Message(role='assistant', text=text)], **extra)
        MarkdownRenderer.write(session, self.directory)
        JsonIndexRenderer.update(session, self.directory / 'sessions.json')
        return session

    def test_transcript_matches_are_not_hidden_by_metadata_hits(self):
        self.export('synthetic-target', 'Decision: Keep cache retries bounded.')
        other = self.export('synthetic-title-only', 'No relevant passage here.')
        other.title = 'Cache retries'
        JsonIndexRenderer.update(other, self.directory / 'sessions.json')
        result = search_archive(self.directory, 'cache retries')
        self.assertEqual([h['session_id'] for h in result['hits']], ['synthetic-target'])
        hit = result['hits'][0]
        self.assertEqual(hit['section'], 2)
        section = conversation_sections(Path(hit['source_path']).read_text())[1][1]
        self.assertEqual(section[hit['quote_start']:hit['quote_end']], hit['quote'])
        self.assertEqual(len(hit['source_sha256']), 64)
        self.assertEqual(hit['verification'], 'not_checked')
        if os.name == 'posix':
            self.assertEqual((self.directory / CACHE_NAME).stat().st_mode & 0o777, 0o600)

    def test_filters_apply_before_limit_and_dates_keep_provenance(self):
        self.export('synthetic-other', 'Cache retry.', project='other')
        self.export('synthetic-target', 'Cache retry uses bounded retries.', agent=Agent.CURSOR, date=4)
        result = search_archive(self.directory, 'cache retry', limit=1, project='example', agent='cursor',
                                role='assistant', since='2026-02-04', until='2026-02-05')
        self.assertEqual(result['hits'][0]['session_id'], 'synthetic-target')
        self.assertEqual(result['hits'][0]['date_source'], 'transcript')
        self.assertFalse(search_archive(self.directory, 'cache retry', role='user')['hits'])

    def test_incremental_refresh_detects_same_size_and_mtime_changes(self):
        self.export('synthetic-edit', 'Cache uses red entries.')
        first = search_archive(self.directory, 'red')
        self.assertEqual(first['index']['updated'], 1)
        again = search_archive(self.directory, 'red')
        self.assertEqual(again['index']['unchanged'], 1)
        path = self.directory / 'synthetic-edit.md'
        stamp = path.stat()
        path.write_text(path.read_text().replace('red', 'tan'))
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertFalse(search_archive(self.directory, 'red')['hits'])
        updated = search_archive(self.directory, 'tan')
        self.assertEqual(updated['total_hits'], 1)
        self.assertNotEqual(first['hits'][0]['source_sha256'], updated['hits'][0]['source_sha256'])

    def test_deleted_transcripts_are_removed_with_a_warning(self):
        self.export('synthetic-delete', 'Cache retry evidence.')
        search_archive(self.directory, 'cache')
        (self.directory / 'synthetic-delete.md').unlink()
        result = search_archive(self.directory, 'cache')
        self.assertEqual(result['hits'], [])
        self.assertEqual(result['index']['removed'], 1)
        self.assertEqual(result['index']['warnings'][0]['code'], 'transcript_missing')

    def test_source_change_between_refresh_planning_and_insert_rolls_back(self):
        self.export('synthetic-race', 'Cache before.')
        search_archive(self.directory, 'cache')
        path = self.directory / 'synthetic-race.md'
        path.write_text(path.read_text().replace('before', 'planned'))
        original_read = Path.read_bytes
        reads = 0

        def concurrent_edit(candidate):
            nonlocal reads
            raw = original_read(candidate)
            if candidate == path:
                reads += 1
                if reads == 1:
                    candidate.write_bytes(raw.replace(b'planned', b'changed'))
            return raw

        with patch.object(Path, 'read_bytes', concurrent_edit):
            with self.assertRaisesRegex(StorageError, 'changed during search refresh'):
                search_archive(self.directory, 'cache')
        with contextlib.closing(sqlite3.connect(self.directory / CACHE_NAME)) as connection:
            self.assertIn('before', connection.execute('SELECT body FROM passages WHERE role="Assistant"').fetchone()[0])
        result = search_archive(self.directory, 'changed')
        self.assertEqual(result['total_hits'], 1)

    def test_bulk_replacement_and_removal_crosses_deletion_batch_boundary(self):
        rows = []
        for n in range(405):
            session = Session(id=f'synthetic-bulk-{n}', agent=Agent.CODEX,
                              messages=[Message(role='assistant', text='oldbulkmarker historical evidence.')])
            MarkdownRenderer.write(session, self.directory)
            rows.append(JsonIndexRenderer.session_to_dict(session))
        index = self.directory / 'sessions.json'
        index.write_text(json.dumps(dict(version=1, count=len(rows), sessions=rows)))
        self.assertEqual(search_archive(self.directory, 'oldbulkmarker')['total_hits'], 405)
        kept = []
        for n, row in enumerate(rows):
            path = self.directory / row['file']
            if n % 2:
                path.unlink()
            else:
                path.write_text(path.read_text().replace('oldbulkmarker', 'newbulkmarker'))
                kept.append(row)
        index.write_text(json.dumps(dict(version=1, count=len(kept), sessions=kept)))
        result = search_archive(self.directory, 'newbulkmarker')
        self.assertEqual(result['total_hits'], 203)
        self.assertEqual(result['index']['updated'], 203)
        self.assertEqual(result['index']['removed'], 202)
        self.assertFalse(search_archive(self.directory, 'oldbulkmarker')['hits'])
        with contextlib.closing(sqlite3.connect(self.directory / CACHE_NAME)) as connection:
            counts = dict(connection.execute('SELECT session_id, count(*) FROM passages GROUP BY session_id'))
        self.assertEqual(counts, {row['id']: 1 for row in kept})
        self.assertEqual(search_archive(self.directory, 'newbulkmarker', rebuild=True)['total_hits'], 203)

    def test_failed_refresh_rolls_back_and_never_returns_old_evidence(self):
        self.export('synthetic-read', 'Cache before.')
        search_archive(self.directory, 'cache')
        path = self.directory / 'synthetic-read.md'
        path.write_bytes(b'\xff')
        with self.assertRaisesRegex(StorageError, 'synthetic-read.md is not valid UTF-8'):
            search_archive(self.directory, 'cache')
        with contextlib.closing(sqlite3.connect(self.directory / CACHE_NAME)) as connection:
            self.assertIn('before', connection.execute('SELECT body FROM passages WHERE role="Assistant"').fetchone()[0])

    def test_unreadable_export_identifies_source_without_rebuilding_cache(self):
        self.export('synthetic-denied', 'Cache before.')
        search_archive(self.directory, 'cache')
        cache = self.directory / CACHE_NAME
        before = cache.read_bytes()
        path = self.directory / 'synthetic-denied.md'
        original_read = Path.read_bytes

        def denied_read(candidate):
            if candidate == path:
                raise PermissionError('synthetic permission failure')
            return original_read(candidate)

        with patch.object(Path, 'read_bytes', denied_read):
            with self.assertRaisesRegex(StorageError, r'Cannot read export synthetic-denied.md \(PermissionError\)'):
                search_archive(self.directory, 'cache')
        self.assertEqual(cache.read_bytes(), before)

    def test_oversized_query_does_not_refresh_changed_sources(self):
        self.export('synthetic-query', 'Cache before.')
        search_archive(self.directory, 'cache')
        cache = self.directory / CACHE_NAME
        before = cache.read_bytes()
        path = self.directory / 'synthetic-query.md'
        path.write_text(path.read_text().replace('before', 'changed'))
        with self.assertRaisesRegex(ValueError, '32 terms and 2000 characters'):
            search_archive(self.directory, ' '.join(f'term{n}' for n in range(33)))
        self.assertEqual(cache.read_bytes(), before)

    def test_corrupt_cache_requires_explicit_rebuild_and_keeps_exports(self):
        self.export('synthetic-corrupt', 'Cache evidence.')
        cache = self.directory / CACHE_NAME
        cache.write_bytes(b'not a database')
        with self.assertRaises(StorageError):
            search_archive(self.directory, 'cache')
        self.assertEqual(cache.read_bytes(), b'not a database')
        self.assertEqual(search_archive(self.directory, 'cache', rebuild=True)['total_hits'], 1)
        self.assertTrue((self.directory / 'synthetic-corrupt.md').exists())

    def test_tool_code_context_and_commentary_are_not_searchable(self):
        session = Session(id='synthetic-exclusions', agent=Agent.CODEX, messages=[
            Message(role='user', text='Inspect the cache.'),
            Message(role='assistant', phase='commentary', text='hiddencommentary'),
            Message(role='tool', text='', tool_results=[ToolResult('hiddentool')]),
            Message(role='assistant', text='Visible result.\n```\nhiddencode\n```\n'
                    '<environment_context>hiddencontext</environment_context>')])
        MarkdownRenderer.write(session, self.directory)
        JsonIndexRenderer.update(session, self.directory / 'sessions.json')
        self.assertEqual(search_archive(self.directory, 'visible')['total_hits'], 1)
        for query in ('hiddencommentary', 'hiddentool', 'hiddencode', 'hiddencontext'):
            self.assertEqual(search_archive(self.directory, query)['total_hits'], 0)

    def test_query_modes_unicode_and_operator_injection(self):
        self.export('synthetic-query', 'Cache retry is bounded. تصمیم روشن است.')
        self.assertEqual(search_archive(self.directory, 'retry cache')['total_hits'], 1)
        self.assertEqual(search_archive(self.directory, 'retry cache', match='phrase')['total_hits'], 0)
        self.assertEqual(search_archive(self.directory, 'cache unknown', match='any')['total_hits'], 1)
        self.assertEqual(search_archive(self.directory, 'تصمیم')['total_hits'], 1)
        self.assertEqual(search_archive(self.directory, 'cache OR nonexistent')['total_hits'], 0)
        self.assertEqual(search_archive(self.directory, 'cache cache', match='phrase')['total_hits'], 0)
        for query in ('', '!!!', ' '.join('x' + str(i) for i in range(33))):
            with self.assertRaises(ValueError):
                search_archive(self.directory, query)

    def test_symlinks_are_not_followed(self):
        self.export('synthetic-link', 'Cache evidence.')
        transcript = self.directory / 'synthetic-link.md'
        transcript.rename(self.directory / 'outside.md')
        transcript.symlink_to(self.directory / 'outside.md')
        result = search_archive(self.directory, 'cache')
        self.assertFalse(result['hits'])
        self.assertEqual(result['index']['warnings'][0]['code'], 'transcript_symlink_skipped')

    def test_cli_json_is_clean_and_missing_archives_are_not_created(self):
        self.export('synthetic-cli', 'Cache evidence.')
        with patch.object(sys, 'argv', ['agent-sessions', 'search', 'cache', '-d', str(self.directory), '--json']), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            main()
        self.assertEqual(json.loads(output.getvalue())['hits'][0]['session_id'], 'synthetic-cli')
        missing = self.directory / 'missing'
        with self.assertRaises(StorageError):
            search_archive(missing, 'cache')
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
