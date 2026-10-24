"""Rebuild missing or different exports from local sources, without deleting history."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import json

from agent_sessions.parsers import PARSERS
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.renderers.index import IndexRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import (
    DEFAULT_LOCK_TIMEOUT, InvalidIndexError, StorageError, atomic_write_many,
    atomic_write_text, directory_lock, validate_session_id,
)

SOURCE_ERRORS = (OSError, UnicodeError, ValueError, TypeError, AttributeError, KeyError, IndexError)


def _signature(paths: list[Path]) -> list[tuple]:
    return [(str(p), s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            for p in paths for s in [p.stat()]]


def reconcile(directory: Path, agents: list[str] | None = None, *, dry_run: bool = False,
              lock_timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict:
    """Parse each source group; only replace exports that differ.

    A real run holds the directory lock across comparison and replacement.
    Dry runs create no directories, locks, or reports. Their view can race writers.
    Invalid indexes stop the run before any destination replacement.
    """
    selected = agents if agents is not None else list(PARSERS)
    report = dict(version=1, dry_run=dry_run, directory=str(directory), sources=[], discovery=[])
    with nullcontext() if dry_run else directory_lock(directory, timeout=lock_timeout):
        json_path = directory / 'sessions.json'
        index_path = directory / 'SESSION_INDEX.md'
        entries = JsonIndexRenderer.read_entries(json_path)
        _, md_entries = IndexRenderer.read_entries(index_path)
        if (entries and not index_path.exists()) or (md_entries and not json_path.exists()):
            raise InvalidIndexError('An archive index is missing. Run doctor and restore the missing index before reconciliation.')
        for agent in selected:
            parser = PARSERS[agent]
            try:
                base = parser.find_sessions_dir()
                present = base.is_dir()
                paths = parser.list_sessions() if present else []
                report['discovery'].append(dict(agent=agent, status='scanned' if present else 'absent',
                                                source_files=len(paths)))
                if not present and agents is not None:
                    report['discovery'][-1]['status'] = 'error'
            except SOURCE_ERRORS as error:
                report['discovery'].append(dict(agent=agent, status='error', error_type=type(error).__name__))
                continue
            groups: dict[str, list[Path]] = {}
            for path in paths:
                try:
                    sid = CodexParser.session_id(path) if agent == 'codex' else path.stem
                    validate_session_id(sid)
                    groups.setdefault(sid, []).append(path)
                except (*SOURCE_ERRORS, StorageError) as error:
                    report['sources'].append(dict(agent=agent, source_paths=[str(path)], status='error',
                                                   error_type=type(error).__name__))
            for sid, group in groups.items():
                row = dict(agent=agent, session_id=sid, source_paths=[str(p) for p in group])
                report['sources'].append(row)
                try:
                    if agent != 'codex' and len(group) != 1:
                        raise ValueError('Ambiguous session ID across source files')
                    before = _signature(group)
                    session = CodexParser.parse_many(group) if agent == 'codex' else parser.parse(group[0])
                    if before != _signature(group):
                        row.update(status='error', error_type='SourceChangedDuringRead')
                        continue
                    if session is None:
                        row['status'] = 'empty'
                        continue
                    validate_session_id(session.id)
                    if session.id != sid:
                        raise ValueError('Parsed session ID differs from discovery')
                except (*SOURCE_ERRORS, StorageError) as error:
                    row.update(status='error', error_type=type(error).__name__)
                    continue
                old = entries.get(sid)
                if old and old['agent'] != agent:
                    row.update(status='error', error_type='SessionIdCollision')
                    continue
                transcript = directory / f'{sid}.md'
                text = MarkdownRenderer.render(session)
                expected = JsonIndexRenderer.session_to_dict(session)
                reasons = []
                if old != expected:
                    reasons.append('metadata')
                if md_entries.get(sid) != IndexRenderer.make_entry(session):
                    reasons.append('markdown_index')
                try:
                    if transcript.read_text(encoding='utf-8') != text:
                        reasons.append('transcript')
                except FileNotFoundError:
                    reasons.append('missing_transcript')
                except (OSError, UnicodeError) as error:
                    row.update(status='error', error_type=type(error).__name__)
                    continue
                if not reasons:
                    row['status'] = 'unchanged'
                    continue
                row.update(status='would_export' if dry_run else 'exported', reasons=reasons)
                if not dry_run:
                    atomic_write_many({
                        transcript: text,
                        index_path: IndexRenderer.render_update(session, index_path),
                        json_path: JsonIndexRenderer.render_update(session, json_path),
                    })
                entries[sid] = expected
                md_entries[sid] = IndexRenderer.make_entry(session)
        report['counts'] = {status: sum(r['status'] == status for r in report['sources'])
                            for status in ('exported', 'would_export', 'unchanged', 'empty', 'error')}
        report['exit_code'] = int(bool(report['counts']['error'] or any(
            r['status'] == 'error' for r in report['discovery'])))
        if not dry_run:
            atomic_write_text(directory / 'reconcile.json', json.dumps(report, indent=2) + '\n')
    return report
