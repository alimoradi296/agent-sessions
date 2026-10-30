"""Compare a pinned CASS release with evidence exports using synthetic inputs only.

Downloads nothing. Requires the checksum-verified Linux amd64 v0.10.0 binary.
All subprocesses receive a new synthetic home and an isolated data directory.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from agent_sessions.analysis.search import search_archive
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.workspace import _private_root

BINARY_SHA256 = 'd221153d8e0a79ae37eb492855d32cd2aadb98e707c74c37445f779a46c626dd'
ARCHIVE_SHA256 = '638ea8a8a9023c2e046bf8868392e6191218b89cf006e81af3ca205b546c4681'
RELEASE_REVISION = '2bfe708d35734656f0d34eab112bf051e354519c'


def fixtures(home):
    def event(payload, second):
        return dict(type='response_item', payload=payload, timestamp=f'2026-02-03T10:00:{second:02}Z')

    def message(role, text, second, **extra):
        return event(dict(type='message', role=role, content=[dict(type='input_text' if role == 'user' else 'output_text',
                         text=text)], **extra), second)

    long = lambda name: name + 'needle ' + 'invented content ' * 100 + name + 'tail'
    sid = '11111111-1111-4111-8111-111111111111'
    records = [dict(type='session_meta', timestamp='2026-02-03T10:00:00Z',
                    payload=dict(id=sid, cwd='/workspace/example-project', git=dict(branch='feature/synthetic-evidence'))),
               message('user', 'codexrequestneedle Analyze only; no deployment.', 1),
               message('assistant', 'codexanalysisneedle Synthetic reasoning.', 2, phase='analysis'),
               event(dict(type='function_call', name='run_check', call_id='synthetic-function',
                          arguments=json.dumps(dict(text=long('functionargument')))), 3),
               event(dict(type='function_call_output', call_id='synthetic-function', output=long('functionresult')), 4),
               event(dict(type='custom_tool_call', name='apply_patch', call_id='synthetic-custom', input=long('customargument')), 5),
               event(dict(type='custom_tool_call_output', call_id='synthetic-custom', output=long('customresult')), 6),
               message('user', 'codexcorrectionneedle Keep timing a proposal.', 7),
               message('assistant', 'codexfinalneedle No verified deployment.', 8, phase='final_answer')]
    codex = home / '.codex/sessions/2026/02/03' / f'rollout-2026-02-03T10-00-00-{sid}.jsonl'
    cid = '22222222-2222-4222-8222-222222222222'
    cursor = home / '.cursor/projects/workspace-example-project/agent-transcripts' / cid / f'{cid}.jsonl'
    cursor_records = [dict(role='user', message=dict(content=[dict(type='text', text='cursorrequestneedle Analyze only.')])),
                      dict(role='assistant', message=dict(content=[dict(type='text', text='cursoranswerneedle A proposal.'),
                           dict(type='tool_use', id='synthetic-cursor-call', name='run_check', input=dict(text=long('cursorargument')))])),
                      dict(role='user', message=dict(content=[dict(type='tool_result', tool_use_id='synthetic-cursor-call',
                           content=long('cursorresult'), is_error=True)])), dict(type='turn_ended', status='success')]
    for path, rows in ((codex, records), (cursor, cursor_records)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    markers = ['codexrequestneedle', 'codexanalysisneedle', 'codexcorrectionneedle', 'codexfinalneedle',
               'cursorrequestneedle', 'cursoranswerneedle']
    markers += [name + suffix for name in ('functionargument', 'functionresult', 'customargument', 'customresult',
                                           'cursorargument', 'cursorresult') for suffix in ('needle', 'tail')]
    return dict(codex=codex, cursor=cursor), markers


def compare(binary, output):
    binary = Path(binary).resolve()
    if hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA256:
        raise ValueError('Use the documented Linux amd64 CASS v0.10.0 release binary.')
    root = _private_root(output)
    root.mkdir(parents=True, mode=0o700)  # Never reuse another probe or user home.
    home = root / 'synthetic-home'
    home.mkdir(mode=0o700)
    env = dict(HOME=str(home), PATH='/usr/bin:/bin', LANG='C.UTF-8', NO_COLOR='1',
               XDG_CONFIG_HOME=str(home / '.config'), XDG_DATA_HOME=str(home / '.local/share'),
               XDG_CACHE_HOME=str(home / '.cache'), CASS_DATA_DIR=str(root / 'cass-data'))
    paths, markers = fixtures(home)
    hashes = {agent: hashlib.sha256(path.read_bytes()).hexdigest() for agent, path in paths.items()}

    def run(label, *args):
        result = subprocess.run([str(binary), *args], cwd=root, env=env, capture_output=True, text=True, timeout=90)
        (root / f'{label}.json').write_text(result.stdout)
        (root / f'{label}.stderr').write_text(result.stderr)
        result.check_returncode()
        return json.loads(result.stdout)

    indexed = run('index', 'index', '--full', '--json', '--no-progress-events')
    archive = root / 'our-exports'
    for agent, parser in (('codex', CodexParser), ('cursor', CursorParser)):
        session = parser.parse(paths[agent])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
    results, cass_reports = [], {}
    for marker in markers:
        cass = run('search-' + marker, 'search', marker, '--json', '--mode', 'lexical', '--no-maintenance', '--limit', '5')
        if cass.get('budget', {}).get('timed_out') is not False:
            raise ValueError('An incomplete CASS query cannot establish missing evidence.')
        cass_reports[marker] = cass
        ours = search_archive(archive, marker, view='evidence')
        results.append(dict(marker=marker, our_hits=ours['total_hits'],
                            cass_content_hits=sum(marker in hit.get('content', '') for hit in cass['hits'])))
    hit = next(hit for hit in cass_reports['cursoranswerneedle']['hits'] if 'cursoranswerneedle' in hit.get('content', ''))
    canonical = run('cursor-canonical', 'view', str(paths['cursor']), '--message-index', str(hit['line_number']),
                    '--source', hit['source_id'], '--conversation-id', str(hit['conversation_id']), '-C', '0', '--json')
    physical = {name: run('cursor-physical-' + name, 'view', str(paths['cursor']), '-n', str(line), '-C', '0', '--json')
                for name, line in (('argument', 2), ('result', 3))}
    # A stronger baseline can find the source without being given its path.
    # This is literal raw-file inspection, not another semantic search engine.
    raw_locations = [(path, line) for path in home.rglob('*.jsonl')
                     for line, text in enumerate(path.read_text().splitlines(), 1) if 'cursorresultneedle' in text]
    if len(raw_locations) != 1:
        raise ValueError('The raw fallback did not identify one fixture location.')
    recovered_path, recovered_line = raw_locations[0]
    recovery = run('cursor-literal-recovery', 'view', str(recovered_path), '-n', str(recovered_line), '-C', '1', '--json')
    recovery_text = json.dumps(recovery)
    recovered_records = [json.loads(line['content']) for line in recovery['lines'] if line.get('content', '').startswith('{')]
    recovered_flags = [block.get('is_error') for row in recovered_records
                       for block in row.get('message', {}).get('content', []) if block.get('type') == 'tool_result']
    unchanged = all(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[agent] for agent, path in paths.items())
    if not unchanged:
        raise ValueError('A fixture source changed during the probe.')
    report = dict(synthetic_only=True, release='v0.10.0', release_revision=RELEASE_REVISION,
                  binary_sha256=BINARY_SHA256, archive_sha256=ARCHIVE_SHA256,
                  indexed_conversations=indexed['conversations'], indexed_messages=indexed['messages'], queries=results,
                  canonical_cursor_argument_visible='cursorargumentneedle' in json.dumps(canonical),
                  physical_cursor_argument_visible='cursorargumentneedle' in json.dumps(physical['argument']),
                  physical_cursor_result_visible='cursorresultneedle' in json.dumps(physical['result']),
                  raw_fallback_found_location_without_supplied_path=True,
                  raw_fallback_argument_visible='cursorargumentneedle' in recovery_text,
                  raw_fallback_result_visible='cursorresultneedle' in recovery_text,
                  raw_fallback_error_flag_visible=True in recovered_flags,
                  our_cursor_error_flag_rendered='[is_error: true]' in (archive / (paths['cursor'].stem + '.md')).read_text(),
                  source_bytes_unchanged=unchanged,
                  limits='Two authored fixtures and one pinned Linux release. Content-marker coverage is not semantic '
                         'accuracy, exhaustive format coverage, irrecoverable archive loss, current-main behavior, or commercial validation.')
    (root / 'report.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--output', required=True, help='New private probe directory outside Git checkouts')
    args = parser.parse_args()
    print(json.dumps(compare(args.binary, args.output), indent=2))
