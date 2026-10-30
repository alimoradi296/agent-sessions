"""Local, incremental passage retrieval with citations to current exports.

SQLite is a disposable search cache. Exports remain authoritative. Every search
refreshes source hashes under the export lock before returning any evidence.
No provider, embedding service, raw transcript discovery, or network is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from agent_sessions.analysis.transcript import conversation_sections, rendered_messages
from agent_sessions.analysis.scope import normalize_projects, project_matches, scope_summary
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.storage import StorageError, directory_lock

CACHE_NAME = '.agent-sessions-search.sqlite3'
SCHEMA_VERSION = 1


def _read_source(path):
    try:
        return path.read_bytes()
    except OSError as error:
        raise StorageError(f'Cannot read export {path.name} ({type(error).__name__}). '
                           'Restore access or re-export this source; rebuilding the search cache does not repair it.') from error


def _decode_source(raw, path):
    try:
        return raw.decode('utf-8')
    except UnicodeError as error:
        raise StorageError(f'Export {path.name} is not valid UTF-8. Restore or re-export this source; '
                           'rebuilding the search cache does not repair it.') from error


def query_terms(query: str) -> list[str]:
    # Treat query syntax as data. Quoted FTS terms cannot introduce operators.
    terms = re.findall(r'[^\W_]+', query, re.UNICODE)
    if not terms:
        raise ValueError('Search needs at least one letter or number.')
    if len(terms) > 32 or len(query) > 2000:
        raise ValueError('Search supports at most 32 terms and 2000 characters.')
    return terms


def _expression(query, match):
    terms = query_terms(query)
    if match == 'phrase':
        return '"' + ' '.join(terms) + '"'
    if match not in ('all', 'any'):
        raise ValueError('Match mode must be all, any, or phrase.')
    return (' AND ' if match == 'all' else ' OR ').join('"' + term + '"' for term in dict.fromkeys(terms))


def _initialize(connection):
    try:
        connection.executescript('''
            CREATE TABLE sources (
                id TEXT PRIMARY KEY, metadata TEXT NOT NULL, digest TEXT NOT NULL,
                agent TEXT, project TEXT, cwd TEXT, date TEXT
            );
            CREATE VIRTUAL TABLE passages USING fts5(
                session_id UNINDEXED, section UNINDEXED, role UNINDEXED, body,
                tokenize='unicode61'
            );
            PRAGMA user_version=1;
        ''')
    except sqlite3.OperationalError as error:
        raise StorageError('Passage search requires Python SQLite with FTS5 support.') from error


def _refresh(connection, directory, projects, view, *, empty_cache=False):
    if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        raise StorageError('Unsupported search cache. Run index --rebuild to replace it.')
    rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    scope = scope_summary(rows, projects)
    rows = {sid: row for sid, row in rows.items() if project_matches(row, projects)}
    existing = {row[0]: (row[1], row[2]) for row in
                connection.execute('SELECT id, metadata, digest FROM sources')}
    report = dict(updated=0, unchanged=0, removed=0, sessions=0, passages=0, warnings=[], scope=scope)
    current = set()
    updates = []
    for sid, row in rows.items():
        path = directory / f'{sid}.md'
        if path.is_symlink():
            report['warnings'].append(dict(code='transcript_symlink_skipped', session_id=sid))
            continue
        if not path.exists():
            report['warnings'].append(dict(code='transcript_missing', session_id=sid))
            continue
        raw = _read_source(path)
        digest = hashlib.sha256(raw).hexdigest()
        metadata = json.dumps(row, sort_keys=True, ensure_ascii=False)
        current.add(sid)
        if existing.get(sid) == (metadata, digest):
            report['unchanged'] += 1
            continue
        updates.append((sid, row, path, digest, metadata))
    removed = existing.keys() - current
    if not empty_cache:
        # session_id is unindexed in FTS5. Scan once per bounded batch rather
        # than once per source, including removals and replacement candidates.
        affected = [item[0] for item in updates] + sorted(removed)
        for offset in range(0, len(affected), 400):
            batch = affected[offset:offset + 400]
            marks = ','.join('?' for _ in batch)
            connection.execute(f'DELETE FROM passages WHERE session_id IN ({marks})', batch)
    for sid, row, path, digest, metadata in updates:
        if path.is_symlink():
            raise StorageError('A source changed during search refresh. Retry with settled exports.')
        raw = _read_source(path)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise StorageError('A source changed during search refresh. Retry with settled exports.')
        text = _decode_source(raw, path)
        sections = (conversation_sections(text) if view == 'dialogue' else
                    [(message['role'], message['text']) for message in rendered_messages(text)])
        connection.execute('INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (sid, metadata, digest, row.get('agent'), row.get('project_slug'),
                            row.get('cwd'), row.get('date')))
        connection.executemany('INSERT INTO passages VALUES (?, ?, ?, ?)',
                               ((sid, i, role, body) for i, (role, body) in enumerate(sections, 1)))
        report['updated'] += 1
    for sid in removed:
        connection.execute('DELETE FROM sources WHERE id=?', (sid,))
        report['removed'] += 1
    report['sessions'] = len(current)
    report['passages'] = connection.execute('SELECT count(*) FROM passages').fetchone()[0]
    return report


def _quote(text, query, length=420):
    # A contiguous source slice: never join fragments into a manufactured quote.
    direct = re.search(re.escape(query), text, re.IGNORECASE)
    matches = ([direct] if direct else [re.search(r'(?<![^\W_])' + re.escape(term) + r'(?![^\W_])',
                                                text, re.IGNORECASE) for term in query_terms(query)])
    start = max(0, min((match.start() for match in matches if match), default=0) - 100)
    start = min(start, max(0, len(text) - length))
    return text[start:start + length], start, min(len(text), start + length)


def _line_coordinates(text, start, end):
    """Use the same line boundaries as raw export parsing and numbered reads."""
    cursor = 0
    first = None
    for index, line in enumerate(text.splitlines(keepends=True)):
        if first is None and start < cursor + len(line):
            first = (index, start - cursor + 1)
        if end <= cursor + len(line):
            content = line.splitlines()[0] if line.splitlines() else ''
            return first[0], first[1], end >= cursor + len(content)
        cursor += len(line)
    raise StorageError('Evidence quote coordinates are outside its source message.')


def _parsed_tool_counts(row):
    """Validate optional export metadata; missing counts are not zero counts."""
    value = row.get('parsed_tool_records')
    keys = {'calls', 'calls_with_id', 'results', 'results_with_id'}
    if (not isinstance(value, dict) or set(value) != keys
            or any(type(n) is not int or n < 0 for n in value.values())
            or value['calls_with_id'] > value['calls'] or value['results_with_id'] > value['results']):
        return None
    return value


def _retrieve(connection, directory, query, match, limit, agent, projects, since, until, role, view):
    expression = _expression(query, match)
    # Metadata is filtered in SQL before LIMIT, so other projects cannot crowd
    # the requested project's evidence out of the result set.
    clauses = ['passages MATCH ?']
    values = [expression]
    if agent:
        clauses.append('s.agent=?')
        values.append(agent)
    if projects:
        clauses.append('(' + ' OR '.join('(s.project=? OR s.cwd=?)' for _ in projects) + ')')
        values.extend(value for project in projects for value in (project, project))
    if role:
        clauses.append('p.role=?')
        values.append(role.capitalize())
    for operator, value in (('>=', since), ('<', until)):
        if value:
            clauses.append(f"s.date{operator}?")
            values.append(value)
    where = ' AND '.join(clauses)
    total = connection.execute(f'SELECT count(*) FROM passages p JOIN sources s ON s.id=p.session_id WHERE {where}',
                               values).fetchone()[0]
    result = connection.execute(f'''
        SELECT p.session_id, p.section, p.role, p.body, s.metadata, s.digest, bm25(passages)
        FROM passages p JOIN sources s ON s.id=p.session_id
        WHERE {where}
        ORDER BY bm25(passages), p.session_id, CAST(p.section AS INTEGER)
        LIMIT ?
    ''', values + [limit])
    hits = []
    raw_sources = {}
    for sid, section, speaker, text, metadata, digest, score in result:
        row = json.loads(metadata)
        quote, start, end = _quote(text, query)
        hits.append(dict(session_id=sid, agent=row['agent'], title=row.get('title', ''),
                         project=row.get('project_slug') or row.get('cwd', ''),
                         project_metadata=dict(cwd=row.get('cwd') or '', project_slug=row.get('project_slug') or ''),
                         date=row.get('date', ''), date_source=row.get('date_source', 'unknown'),
                         section=int(section), role=speaker, quote=quote,
                         quote_start=start, quote_end=end, section_chars=len(text),
                         source_path=str((directory / f'{sid}.md').resolve()), source_sha256=digest,
                         score=-score, verification='not_checked'))
        if view == 'evidence':
            if sid not in raw_sources:
                path = directory / f'{sid}.md'
                raw = _read_source(path)
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise StorageError('Evidence changed during search. Retry with settled exports.')
                raw_sources[sid] = rendered_messages(_decode_source(raw, path))
            if not 1 <= int(section) <= len(raw_sources[sid]):
                raise StorageError('Evidence cache message locator is invalid. Rebuild the evidence index.')
            message = raw_sources[sid][int(section) - 1]
            if message['text'] != text or message['role'] != speaker:
                raise StorageError('Evidence cache does not match its source. Rebuild the evidence index.')
            hit = hits[-1]
            hit['parsed_tool_records'] = _parsed_tool_counts(row)
            hit['message'] = hit.pop('section')
            hit['message_chars'] = hit.pop('section_chars')
            line_offset, column, complete = _line_coordinates(text, start, end)
            hit.update(locator_method='rendered_message_v1', phase=message['phase'],
                       source_quote_start=message['body_start'] + start,
                       source_quote_end=message['body_start'] + end,
                       message_heading_line=message['heading_line'],
                       source_quote_line=message['heading_line'] + 1 + line_offset,
                       source_quote_column=column, quote_last_line_complete=complete)
    return hits, total


def search_cache_path(directory, projects=None, view='dialogue'):
    if view not in ('dialogue', 'evidence'):
        raise ValueError('Search view must be dialogue or evidence.')
    projects = normalize_projects(projects)
    suffix = '-evidence' if view == 'evidence' else ''
    if not projects:
        return directory / (CACHE_NAME if view == 'dialogue' else '.agent-sessions-search-evidence.sqlite3')
    digest = hashlib.sha256(json.dumps(projects, ensure_ascii=False).encode()).hexdigest()
    return directory / f'.agent-sessions-search-{digest}{suffix}.sqlite3'


def search_archive(directory: Path, query=None, *, match='all', limit=10, agent=None,
                   project=None, since=None, until=None, role=None, rebuild=False, projects=None, view='dialogue'):
    """Refresh only changed passages, then retrieve from the same transaction.

    Unreadable sources roll back the refresh; stale evidence is not returned.
    Missing transcripts are removed from the cache with explicit warnings.
    Rebuild replaces only this derived cache, never an export or source.
    """
    if project is not None and projects is not None:
        raise ValueError('Use project or projects, not both.')
    projects = normalize_projects(projects if projects is not None else [project] if project is not None else None)
    if query is not None:
        _expression(query, match)
    if not 1 <= limit <= 100:
        raise ValueError('Search limit must be between 1 and 100.')
    if since and until and since >= until:
        raise ValueError('--until must be after --since.')
    if not (directory / 'sessions.json').is_file():
        raise StorageError('No sessions.json found. Export sessions to this directory first.')
    cache = search_cache_path(directory, projects, view)
    temporary = None
    connection = None
    try:
        with directory_lock(directory):
            if cache.is_symlink():
                raise StorageError('Search cache must not be a symlink.')
            if cache.exists() and not cache.is_file():
                raise StorageError('Search cache must be a regular file.')
            create = rebuild or not cache.exists()
            if create:
                fd, name = tempfile.mkstemp(prefix='.agent-sessions-search-', suffix='.tmp', dir=directory)
                os.close(fd)
                temporary = Path(name)
            else:
                os.chmod(cache, 0o600)
            connection = sqlite3.connect(temporary if create else cache)
            if create:
                _initialize(connection)
            with connection:
                report = _refresh(connection, directory, projects, view, empty_cache=create)
                hits, total = (_retrieve(connection, directory, query, match, limit, agent, projects, since, until, role, view)
                               if query is not None else ([], 0))
            connection.close()
            connection = None
            if create:
                os.replace(temporary, cache)
                temporary = None
        return dict(version=1, query=query, match=match, method='sqlite_fts5_bm25', view=view,
                    verification='not_checked', projects=projects, total_hits=total, hits=hits, index=report)
    except (sqlite3.Error, OSError, UnicodeError) as error:
        rebuild_command = 'index --rebuild' + (' --view evidence' if view == 'evidence' else '')
        raise StorageError(f'Cannot search the local archive ({type(error).__name__}). '
                           f'Check exports with doctor; use {rebuild_command} with the same project selectors for a damaged search cache.') from error
    finally:
        if connection is not None:
            connection.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def render_search(report):
    lines = [f"{report['total_hits']} matching passage(s). Historical statements; not independently checked."]
    if report.get('view') == 'evidence':
        lines.append('Raw export messages include code and tool content. Role and phase labels do not establish authorship or execution.')
    if report.get('view') == 'evidence':
        lines.append('Tool counts come from export metadata; they do not establish source completeness, execution, or pairing.')
    described_sources = set()
    for i, hit in enumerate(report['hits'], 1):
        locator = f"message {hit['message']}" if 'message' in hit else f"section {hit['section']}"
        if 'message_heading_line' in hit:
            locator += f" / heading line {hit['message_heading_line']}"
        speaker = hit['role'] + (f" ({hit['phase']})" if hit.get('phase') else '')
        lines.extend(['', f"{i}. [{hit['agent']}] {hit['title']}",
                      f"   {hit['date']} ({hit['date_source']}) / {speaker} / {locator}",
                      '   Project metadata: ' + json.dumps(hit['project_metadata'], ensure_ascii=False),
                      f"   {hit['session_id']} → {hit['source_path']}"])
        if report.get('view') == 'evidence' and hit['session_id'] not in described_sources:
            described_sources.add(hit['session_id'])
            counts = hit.get('parsed_tool_records')
            if counts is None:
                lines.append('   Parsed tool-record counts unavailable in this export.')
            else:
                lines.append(f"   Export metadata: {counts['calls']} parsed calls ({counts['calls_with_id']} with IDs); "
                             f"{counts['results']} parsed results ({counts['results_with_id']} with IDs.")
        if 'source_quote_line' in hit:
            excerpt = hit['quote'].splitlines()
            for offset, line in enumerate(excerpt):
                fragment = ((offset == 0 and hit['source_quote_column'] != 1)
                            or (offset == len(excerpt)-1 and not hit['quote_last_line_complete']))
                marker = ' (fragment)' if fragment else ''
                lines.append(f"   L{hit['source_quote_line'] + offset}{marker}: {line}")
        else:
            lines.append('   ' + hit['quote'].replace('\n', '\n   '))
    for warning in report['index']['warnings']:
        lines.append(f"Warning: {warning['code']} / {warning['session_id']}")
    if report['total_hits'] > len(report['hits']):
        lines.append('\nMore passages match. Increase --limit or filter by agent, project, role, or date.')
    return '\n'.join(lines)
