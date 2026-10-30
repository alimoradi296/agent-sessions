"""Synthetic Cursor hook-output feasibility check; never installs or runs hooks."""

import argparse
import json
from pathlib import Path
import tempfile

from agent_sessions.analysis.search import search_archive
from agent_sessions.parsers.cursor import CursorParser
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


def fixture_records(payload):
    """Map authored documented payloads to parser inputs, not native transcripts.

    This experiment deliberately makes no pairing/merging claim about live data.
    postToolUse does not certify the nested command or application outcome.
    """
    event = payload['hook_event_name']
    if event not in ('postToolUse', 'postToolUseFailure'):
        raise ValueError('Unsupported experiment event.')
    call_id = payload.get('tool_use_id')
    if not isinstance(call_id, str) or not call_id:
        raise ValueError('A recorded tool_use_id is required; do not invent pairing.')
    if event == 'postToolUse':
        output = payload.get('tool_output')
        if not isinstance(output, str):
            raise ValueError('Keep the documented string tool_output intact.')
    else:
        if not isinstance(payload.get('error_message'), str):
            raise ValueError('A failure needs its recorded error_message.')
        output = json.dumps({k: payload[k] for k in ('error_message', 'failure_type', 'is_interrupt') if k in payload})
    result = dict(type='tool_result', tool_use_id=call_id, content=output)
    if event == 'postToolUseFailure':
        result['is_error'] = True
    return [
        dict(role='assistant', message=dict(content=[dict(type='tool_use', id=call_id,
             name=payload['tool_name'], input=payload['tool_input'])])),
        dict(role='user', message=dict(content=[result])),
    ]


def evaluate(fixtures=None):
    supplied = fixtures is not None
    if fixtures is None:
        fixtures = [
            dict(hook_event_name='postToolUse', tool_use_id='synthetic-shell', tool_name='Shell',
                 tool_input=dict(command='fictional-check'),
                 tool_output=json.dumps(dict(exitCode=0, stdout='SYNTHETIC_INNER_ERROR: check inconclusive'))),
            dict(hook_event_name='postToolUse', tool_use_id='synthetic-mcp', tool_name='mcp__example__check',
                 tool_input=dict(item='fictional'),
                 tool_output=json.dumps(dict(isError=True, content=[dict(type='text', text='SYNTHETIC_BACKEND_ERROR')]))),
            dict(hook_event_name='postToolUseFailure', tool_use_id='synthetic-timeout', tool_name='Shell',
                 tool_input=dict(command='fictional-check'), error_message='SYNTHETIC_TIMEOUT',
                 failure_type='timeout', is_interrupt=False),
        ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-receipts-') as temporary:
        root = Path(temporary)
        exports = root / 'exports'
        for i, fixture in enumerate(fixtures):
            records = fixture_records(fixture)
            original = root / f'original-{i}.jsonl'
            original.write_text(json.dumps(records[0]) + '\n')
            incomplete = CursorParser.parse(original)
            if sum(len(m.tool_results) for m in incomplete.messages) != 0:
                raise AssertionError('Call-only control unexpectedly has a result.')
            receipt = root / f'receipt-{i}.jsonl'
            receipt.write_text(''.join(json.dumps(r) + '\n' for r in records))
            parsed = CursorParser.parse(receipt)
            calls = [t for m in parsed.messages for t in m.tool_calls]
            results = [t for m in parsed.messages for t in m.tool_results]
            expected = records[1]['message']['content'][0]['content']
            if len(calls) != 1 or len(results) != 1 or calls[0].call_id != results[0].call_id:
                raise AssertionError('Fixture call/result pair not preserved.')
            if results[0].content != expected or json.loads(calls[0].arguments) != fixture['tool_input']:
                raise AssertionError('Fixture payload changed.')
            expected_flag = True if fixture['hook_event_name'] == 'postToolUseFailure' else None
            if results[0].is_error is not expected_flag:
                raise AssertionError('Unexpected inferred result status.')
            MarkdownRenderer.write(parsed, exports)
            JsonIndexRenderer.update(parsed, exports / 'sessions.json')
            token = next(t for t in ('SYNTHETIC_INNER_ERROR', 'SYNTHETIC_BACKEND_ERROR', 'SYNTHETIC_TIMEOUT') if t in expected)
            found = search_archive(exports, token, view='evidence', role='tool')
            hits = [hit for hit in found['hits'] if hit['session_id'] == parsed.id]
            if len(hits) != 1:
                raise AssertionError('Output not retrievable through existing evidence search.')
            hit = hits[0]
            source = Path(hit['source_path']).read_text()
            if source[hit['source_quote_start']:hit['source_quote_end']] != hit['quote']:
                raise AssertionError('Result citation does not match exported source.')
            rows.append(dict(event=fixture['hook_event_name'], result_preserved=True,
                             paired_fixture_id=True, searchable_with_source_coordinates=True,
                             parsed_is_error=results[0].is_error))
    return dict(synthetic_only=True, cases=rows, supplied_receipt_report=supplied, native_cursor_session_observed=False,
                limits='Synthetic hook-shaped records mapped to separate parser fixtures. Conversation/generation metadata is not merged into native transcripts. No installed capture, normal agent session, historical recovery, outcome certification, or distinct product advantage established.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt-report', type=Path, help='Synthetic output from the separate native component probe')
    args = parser.parse_args()
    fixtures = None
    if args.receipt_report:
        report = json.loads(args.receipt_report.read_text())
        if report.get('synthetic_only') is not True:
            raise ValueError('This experiment accepts synthetic reports only.')
        fixtures = report['receipts']
    print(json.dumps(evaluate(fixtures), indent=2))
