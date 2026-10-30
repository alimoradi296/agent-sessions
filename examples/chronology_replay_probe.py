"""Compare raw records, canonical messages and a captured native payload.

The replay target is a deterministic synthetic TTL operation, not a model.
Raw JSON records feed the existing FailMin callback API without a new adapter.
"""

import argparse
import json
from pathlib import Path

from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.parsers.codex import CodexParser

CORRECTION = 'Correction: the TTL is 30 seconds, not 60.'


def operations(record, agent):
    """Small raw-format baseline for only the two documented fixture shapes."""
    if agent == 'codex':
        item = record.get('payload', {})
        if item.get('type') == 'message' and item.get('role') == 'user':
            yield from (('text', part.get('text', '')) for part in item.get('content', []))
        elif item.get('type') in ('function_call', 'custom_tool_call') and item.get('name') == 'edit_example':
            yield 'apply', json.loads(item.get('arguments', item.get('input', '{}')))
    elif record.get('type') == 'user' and isinstance(record.get('message', {}).get('content'), str):
        yield 'text', record['message']['content']
    elif record.get('type') == 'assistant':
        content = record.get('message', {}).get('content', [])
        for block in content if isinstance(content, list) else []:
            if block.get('type') == 'tool_use' and block.get('name') == 'edit_example':
                yield 'apply', block['input']


def execute(sequence):
    """Run an authored synthetic invariant at each captured apply operation."""
    expected = 60
    applied = None
    for kind, value in sequence:
        if kind == 'text' and value == CORRECTION:
            expected = 30
        elif kind == 'apply':
            applied = value['ttl_seconds']
            if applied != expected:
                return dict(failed=True, applied=applied, expected_at_call=expected)
    return dict(failed=False, applied=applied)


def canonical_operations(session):
    for message in session.messages:
        if message.role == 'user':
            yield 'text', message.text
        for call in message.tool_calls:
            if call.name == 'edit_example':
                yield 'apply', json.loads(call.arguments)


def evaluate(directory):
    try:
        from failmin import Trace, TraceEvent, RunResult, minimize
    except ImportError as exc:
        raise SystemExit('Use an isolated environment with failmin==0.2.0 installed.') from exc
    rows = []
    for agent, parser in [('codex', CodexParser), ('claude', ClaudeParser)]:
        for order in ('before', 'after'):
            path = directory / f'{agent}-{order}' / f'synthetic-{agent}.jsonl'
            records = [json.loads(line) for line in path.read_text().splitlines()]
            raw = execute(operation for record in records for operation in operations(record, agent))
            canonical = execute(canonical_operations(parser.parse(path)))
            row = dict(agent=agent, correction_order=order, raw_replay=raw, canonical_replay=canonical)
            if raw['failed']:
                trace = Trace(tuple(TraceEvent(id=f'synthetic-record-{n}', type='record', input=record)
                                    for n, record in enumerate(records, 1)))
                def replay(candidate):
                    return RunResult(output=execute(op for event in candidate.events for op in operations(event.input, agent)))
                reduced = minimize(trace, replay, lambda result: result.output['failed'])
                row['reduction'] = dict(original=len(trace.events), reduced=len(reduced.minimal.events),
                                        failure_reproduced=replay(reduced.minimal).output['failed'])
            rows.append(row)
        before = json.loads((directory / f'{agent}-before/payload.json').read_text())
        after = json.loads((directory / f'{agent}-after/payload.json').read_text())
        if before != after:
            raise ValueError('The expected collision did not occur; inspect the pinned parser outputs.')
    return dict(synthetic_only=True, rows=rows, native_payload_collision=True,
                native_replay_classification='unknown: follow-up position is unavailable',
                decision='Existing raw-format callback preserves the distinction without a new replay engine or production adapter.',
                limits='A deterministic authored operation invariant. No model, external tool, causal explanation, or production failure is replayed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.directory), indent=2))
