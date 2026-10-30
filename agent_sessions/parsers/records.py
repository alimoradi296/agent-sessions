"""Read JSONL once, with payload-free, per-source record counts.

Counts describe parser coverage, not data-loss estimates. A supported record
can contain no exportable text; an unsupported block can accompany kept text.
"""

from __future__ import annotations

import json
from pathlib import Path


def _content_status(content, text_types, tool_types):
    if isinstance(content, str):
        return 'handled'
    if not isinstance(content, list):
        return 'malformed'
    unsupported = False
    for block in content:
        if not isinstance(block, dict):
            return 'malformed'
        kind = block.get('type')
        if kind in text_types:
            if not isinstance(block.get('text', ''), str):
                return 'malformed'
        elif kind in tool_types:
            result = block.get('content', '')
            if kind == 'tool_result' and isinstance(result, list):
                if any(not isinstance(b, dict) or not isinstance(b.get('text', ''), str)
                       for b in result):
                    return 'malformed'
        else:
            unsupported = True
    return 'unsupported' if unsupported else 'handled'


def record_status(agent, record):
    if not isinstance(record, dict):
        return 'malformed'
    kind = record.get('type')
    if agent == 'codex':
        payload = record.get('payload', {})
        if not isinstance(payload, dict):
            return 'malformed'
        subtype = payload.get('type')
        if kind == 'session_meta':
            if not isinstance(payload.get('git', {}), (dict, type(None))):
                return 'malformed'
            return 'handled'
        if kind == 'turn_context':
            return 'handled'
        if kind == 'event_msg':
            if subtype in ('user_message', 'agent_message'):
                return 'handled' if isinstance(payload.get('message', ''), str) else 'malformed'
            if subtype == 'token_count':
                info = payload.get('info') or {}
                if not isinstance(info, dict):
                    return 'malformed'
                total = info.get('total_token_usage') or {}
                return 'handled' if isinstance(total, dict) else 'malformed'
            if subtype in ('task_started', 'turn_completed', 'turn_aborted', 'task_complete'):
                return 'handled'
            if subtype in ('agent_reasoning', 'agent_reasoning_raw_content'):
                return 'ignored'
            return 'unsupported'
        if kind == 'response_item':
            if subtype in (None, 'message'):
                if payload.get('role') not in ('user', 'assistant'):
                    return 'ignored' if payload.get('role') in ('system', 'developer') else 'unsupported'
                content = payload.get('content') or []
                if not isinstance(content, list):
                    return 'malformed'
                return _content_status(content, ('input_text', 'output_text'), ())
            if subtype in ('function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'):
                return 'handled'
            if subtype == 'reasoning':
                return 'ignored'
            return 'unsupported'
        if kind == 'compacted':
            return 'ignored'
        return 'unsupported'

    role = record.get('role') if agent == 'cursor' else kind
    if role in ('user', 'assistant'):
        if agent == 'claude' and record.get('isSidechain'):
            return 'ignored'
        message = record.get('message', {})
        if not isinstance(message, dict):
            return 'malformed'
        if agent == 'claude' and record.get('forkedFrom') is not None:
            if not isinstance(record['forkedFrom'], dict):
                return 'malformed'
        return _content_status(message.get('content', ''), ('text',), ('tool_use', 'tool_result'))
    if agent == 'cursor':
        return 'handled' if kind == 'turn_ended' else 'unsupported'
    if kind in ('ai-title', 'custom-title'):
        return 'handled'
    if kind == 'system':
        if record.get('subtype') == 'away_summary':
            return 'handled' if isinstance(record.get('content', ''), str) else 'malformed'
        return 'ignored'
    if kind in ('attachment', 'mode', 'agent-name', 'progress', 'file-history-snapshot',
                'queue-operation', 'summary'):
        return 'ignored'
    return 'unsupported'


def read_records(path: Path, agent: str, diagnostics=None):
    """Yield valid objects with original line numbers, even for unknown types.

    Diagnostics count physical source records before Codex overlap removal.
    No transcript text, event names, or raw lines enter the report.
    """
    counts = dict(records=0, blank_lines=0, handled=0, ignored=0, malformed=0, unsupported=0)
    if diagnostics is not None:
        diagnostics[str(path)] = counts
    with path.open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                counts['blank_lines'] += 1
                continue
            counts['records'] += 1
            try:
                record = json.loads(line)
            except ValueError:
                counts['malformed'] += 1
                continue
            status = record_status(agent, record)
            counts[status] += 1
            if status != 'malformed':
                yield line_number, record
