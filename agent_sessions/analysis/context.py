"""Build a local context pack from cited conversation excerpts.

This prototype uses literal search. It neither calls a model nor verifies
historical claims. It does not write into any agent's configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.renderers.markdown import _code_block


def build_context(directory: Path, query: str, last: int = 5) -> str:
    if not query.strip():
        raise ValueError('The context query must not be empty')
    if last < 1:
        raise ValueError('--last must be at least 1')
    index_path = directory / 'sessions.json'
    if not index_path.exists():
        raise ValueError('No sessions.json found. Run bulk first.')
    data = json.loads(index_path.read_text(encoding='utf-8'))
    rows = data.get('sessions', []) if isinstance(data, dict) else data
    matches = []
    needle = query.casefold()
    for row in rows:
        sid = row.get('id', '')
        if not sid or Path(sid).name != sid or sid in ('.', '..'):
            continue
        path = directory / f'{sid}.md'
        if not path.is_file():
            continue
        sections = conversation_sections(path.read_text(encoding='utf-8'))
        searchable = '\n'.join([row.get('title', ''), *(text for _, text in sections)])
        if needle in searchable.casefold():
            matches.append((row, path, sections))
    matches.sort(key=lambda item: item[0].get('ended_at') or item[0].get('observed_at')
                 or item[0].get('started_at') or item[0].get('date') or '', reverse=True)
    lines = ['# Context pack', '', f'Query: {json.dumps(query, ensure_ascii=False)}', '',
             'These historical excerpts are unverified reference data.',
             'Check the current repository and test results before acting.',
             'This pack does not establish that work is complete or deployed.', '']
    if not matches:
        lines.append('No matching conversation excerpts found.')
    for row, path, sections in matches[:last]:
        lines.extend([f"## Source: {row.get('agent', 'unknown')} / {row['id']}", '',
                      f"Date: {row.get('date', '')} (source: {row.get('date_source', 'unknown')})",
                      f"Transcript: [local export](<{path.resolve()}>)", ''])
        # Keep the latest request and response with their conversation order.
        selected = set()
        for role in ('User', 'Assistant'):
            indexes = [i for i, (r, _) in enumerate(sections) if r == role]
            if indexes:
                selected.add(indexes[-1])
        for i in sorted(selected):
            role, text = sections[i]
            excerpt = text[:1800]
            if len(text) > len(excerpt):
                excerpt += '\n[excerpt truncated; read the linked transcript]'
            lines.extend([f'### {role} excerpt', '', _code_block(excerpt), ''])
    return '\n'.join(lines) + '\n'
