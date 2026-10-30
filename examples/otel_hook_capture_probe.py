"""Compare pinned third-party capture using authored events and file-only export."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REVISION = '2b922aeddab9e83bea5e932e3d2558f0bd397e3b'
SOURCE_SHA256 = '90c163f80f5cd1db51373fac10b35c86f0c394a2f793aab73ff73b8636d7014c'


def source_fingerprint(source):
    source = Path(source).resolve()
    digest = hashlib.sha256()
    for name in ('enrichment_connectors.py', 'otel_hook.py', 'pyproject.toml'):
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Provide the complete pinned source; execution refused.')
        digest.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def validate_source(source):
    source = Path(source).resolve()
    if source_fingerprint(source) != SOURCE_SHA256:
        raise ValueError('Unpinned source; execution refused.')
    return source


def evaluate(source, python=sys.executable):
    source = validate_source(source)
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-otel-') as temporary:
        root = Path(temporary)
        for name in ('home', 'state', 'project'):
            (root / name).mkdir(mode=0o700)
        config = root / 'config.json'
        config.write_text('{}')  # Prevent copying the example localhost exporter.
        env = dict(HOME=str(root / 'home'), PATH='/usr/bin:/bin', LANG='C.UTF-8',
                   IDE_OTEL_HOOK_HOME=str(root / 'state'), IDE_OTEL_CONFIG=str(config),
                   IDE_OTEL_LOCAL_SPANS='true', IDE_OTEL_SKIP_MDM='true', IDE_OTEL_ENABLE_LOGS='false',
                   IDE_OTEL_BATCH_ON_STOP='false', IDE_OTEL_DISABLE_BATCH='true',
                   IDE_OTEL_CAPTURE_TOOL_INPUT_CONTENT='true', IDE_OTEL_CAPTURE_TEXT='true',
                   IDE_OTEL_TEXT_MAX_CHARS='20000', OTEL_EXPORTER_OTLP_ENDPOINT='')
        # Refuse before importing upstream if its import-time bootstrap would install dependencies.
        subprocess.run([str(python), '-c', 'import click; import opentelemetry.sdk.trace.export; '
                        'import opentelemetry.exporter.otlp.proto.grpc.trace_exporter; '
                        'import opentelemetry.exporter.otlp.proto.http.trace_exporter'],
                       env=env, cwd=root, check=True, capture_output=True, text=True)
        base = dict(ide_name='cursor', conversation_id='synthetic-session', cwd=str(root / 'project'),
                    workspace_roots=[str(root / 'project')])
        events = [dict(base, hook_event_name='sessionStart')]
        for generation, marker in [('a', 'SYNTHETIC_RESULT_A'), ('b', 'SYNTHETIC_RESULT_B'), ('c', 'SYNTHETIC_TIMEOUT')]:
            call = dict(base, generation_id='synthetic-generation-' + generation,
                        tool_use_id='synthetic-shared-id', tool_name='Shell', tool_input={'command': 'fictional-check'})
            events += [dict(base, generation_id=call['generation_id'], hook_event_name='beforeSubmitPrompt', prompt='Fictional task.'),
                       dict(call, hook_event_name='preToolUse')]
            if generation == 'c':
                events.append(dict(call, hook_event_name='postToolUseFailure', error_message=marker,
                                   failure_type='timeout', is_interrupt=False))
            else:
                events.append(dict(call, hook_event_name='postToolUse', tool_output=marker))
                if generation == 'a':
                    events.append(dict(events[-1]))
            events.append(dict(base, generation_id=call['generation_id'], hook_event_name='stop', status='completed'))
        events.append(dict(base, conversation_id='', generation_id='', hook_event_name='postToolUse',
                           tool_use_id='synthetic-orphan', tool_name='Shell', tool_output='SYNTHETIC_ORPHAN'))
        for event in events:
            result = subprocess.run([str(python), str(source / 'otel_hook.py')], input=json.dumps(event), env=env,
                                    cwd=root / 'project', capture_output=True, text=True, timeout=15, check=True)
            if result.stderr:
                raise ValueError('Upstream emitted diagnostics; inspect before accepting this comparison: ' + result.stderr)
        spans = [json.loads(line) for path in (root / 'state').rglob('local_spans/*.jsonl')
                 for line in path.read_text().splitlines() if line]
        attrs = [span['attributes'] for span in spans if span.get('attributes', {}).get('gen_ai.client.hook.event')
                 in ('PostToolUse', 'PostToolUseFailure')]
        def matching(marker, field='tool_output'):
            return [a for a in attrs if a.get('gen_ai.client.' + field + '.text') == marker]
        cases = dict(repeated_callback_collapsed=len(matching('SYNTHETIC_RESULT_A')) == 1,
                     reused_id_next_generation_retained=len(matching('SYNTHETIC_RESULT_B')) == 1,
                     failure_text_retained=len(matching('SYNTHETIC_TIMEOUT', 'error')) == 1,
                     orphan_retained_without_session=len(matching('SYNTHETIC_ORPHAN')) == 1
                     and matching('SYNTHETIC_ORPHAN')[0].get('gen_ai.client.session_id') == '')
        if not all(cases.values()) or len(attrs) != 4:
            raise ValueError('Observed capture does not match the authored lifecycle controls: ' + json.dumps(cases))
        return dict(synthetic_only=True, revision=REVISION, source_sha256=SOURCE_SHA256,
                    cli_invocations=len(events), output_records=len(attrs), cases=cases,
                    limits='Actual upstream CLI with complete authored session lifecycle, opt-in text, 20000-character cap, explicit empty exporter endpoint, and logs disabled. Not a normal agent session, historical recovery, native transcript merge, full-fidelity guarantee, or product advantage.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--python', default=sys.executable, help='Temporary environment with upstream dependencies already installed')
    args = parser.parse_args()
    print(json.dumps(evaluate(args.source, args.python), indent=2))
