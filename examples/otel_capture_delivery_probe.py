"""Check persisted synthetic output, pending batches, and recovery in pinned hooks."""

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from examples.otel_hook_capture_probe import REVISION, SOURCE_SHA256, source_fingerprint

PROTOTYPE_SHA256 = '9423b43b649ff59e08fe7d2e2887351b0720d04c097f1165ad550ee9e40e7640'
MARKER = 'SYNTHETIC_CANARY_PERSISTENCE_MARKER'


def evaluate(source, python=sys.executable):
    source = Path(source).resolve()
    fingerprint = source_fingerprint(source)
    if fingerprint not in (SOURCE_SHA256, PROTOTYPE_SHA256):
        raise ValueError('Unpinned source; execution refused.')
    prototype = fingerprint == PROTOTYPE_SHA256
    cases = []
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-delivery-') as temporary:
        root = Path(temporary)
        for blocked in (False, True):
            case = root / ('blocked' if blocked else 'healthy')
            for name in ('home', 'state', 'project/.cursor'):
                (case / name).mkdir(mode=0o700, parents=True, exist_ok=True)
            project, state = case / 'project', case / 'state'
            config = case / 'config.json'
            config.write_text('{}')
            command = shlex.join([str(python), str(source / 'otel_hook.py')])
            (project / '.cursor/hooks.json').write_text(json.dumps(dict(version=1, hooks={
                'postToolUse': [dict(command=command)]})))
            target = state / '.state/local_spans'
            if blocked:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('Authored file obstruction.')
            env = dict(HOME=str(case / 'home'), PATH='/usr/bin:/bin', LANG='C.UTF-8',
                       IDE_OTEL_HOOK_HOME=str(state), IDE_OTEL_CONFIG=str(config), IDE_OTEL_SKIP_MDM='true',
                       IDE_OTEL_LOCAL_SPANS='true', IDE_OTEL_ENABLE_LOGS='false', IDE_OTEL_BATCH_ON_STOP='true',
                       IDE_OTEL_DISABLE_BATCH='true', IDE_OTEL_CAPTURE_TEXT='true',
                       IDE_OTEL_CAPTURE_TOOL_INPUT_CONTENT='true', IDE_OTEL_TEXT_MAX_CHARS='20000',
                       OTEL_EXPORTER_OTLP_ENDPOINT='')
            subprocess.run([str(python), '-c', 'import click; import opentelemetry.sdk.trace.export; '
                            'import opentelemetry.exporter.otlp.proto.grpc.trace_exporter; '
                            'import opentelemetry.exporter.otlp.proto.http.trace_exporter'],
                           env=env, cwd=case, check=True, capture_output=True)
            def invoke(*args, event=None):
                return subprocess.run([str(python), str(source / 'otel_hook.py'), *args],
                                      input=None if event is None else json.dumps(event), env=env, cwd=project,
                                      capture_output=True, text=True, timeout=15)
            def marker_files():
                return sorted(str(p.relative_to(state)) for p in state.rglob('*')
                              if p.is_file() and MARKER.encode() in p.read_bytes())
            def output_present():
                if not target.is_dir():
                    return False
                spans = [json.loads(line) for p in target.glob('*.jsonl') for line in p.read_text().splitlines() if line]
                return any(s.get('attributes', {}).get('gen_ai.client.tool_output.text') == MARKER
                           and s['attributes'].get('gen_ai.client.tool_use_id') == 'synthetic-call'
                           and s['attributes'].get('gen_ai.client.session_id') == 'synthetic-session'
                           and s['attributes'].get('gen_ai.client.generation_id') == 'synthetic-generation'
                           for s in spans)
            def doctor():
                result = invoke('doctor', '--agent', 'cursor', '--no-global', '--cwd', str(project), '--json')
                payload = json.loads(result.stdout)
                return dict(exit_code=result.returncode, status=payload['status'],
                            exporter_status=payload['exporter']['status'], batches=payload['state']['batches'])
            base = dict(ide_name='cursor', conversation_id='synthetic-session', generation_id='synthetic-generation',
                        cwd=str(project), workspace_roots=[str(project)])
            tool = dict(base, tool_name='Shell', tool_use_id='synthetic-call', tool_input={'command': 'fictional-check'})
            events = [dict(base, hook_event_name='sessionStart'),
                      dict(base, hook_event_name='beforeSubmitPrompt', prompt='Authored test.'),
                      dict(tool, hook_event_name='preToolUse'),
                      dict(tool, hook_event_name='postToolUse', tool_output=MARKER)]
            replies = [invoke(event=e) for e in events]
            before = marker_files()
            stop = dict(base, hook_event_name='stop', status='completed')
            replies.append(invoke(event=stop))
            after, health = marker_files(), doctor()
            row = dict(blocked=blocked, callback_exit_codes=[p.returncode for p in replies],
                       diagnostics_present=any(p.stderr for p in replies), buffered_before_stop=bool(before),
                       marker_files_after_stop=after, output_persisted_after_stop=output_present(), doctor=health)
            if not before or any(p.returncode for p in replies):
                raise AssertionError('Authored callbacks did not reach the expected buffered state.')
            if not blocked:
                if not row['output_persisted_after_stop'] or health['exit_code'] != 0 or health['batches']:
                    raise AssertionError('Healthy control failed.')
            else:
                target.unlink()
                target.mkdir()
                recovery = invoke(event=stop)
                row.update(recovery_exit_code=recovery.returncode, marker_files_after_retry=marker_files(),
                           doctor_after_retry=doctor(), output_persisted_after_retry=output_present())
                if prototype:
                    if row['output_persisted_after_stop'] or health['status'] != 'degraded' or not health['batches'] or not row['output_persisted_after_retry'] or row['doctor_after_retry']['exit_code'] != 0 or row['doctor_after_retry']['batches']:
                        raise AssertionError('Prototype did not retain pending output and recover: ' + json.dumps(row))
                elif row['output_persisted_after_stop'] or after or health['status'] != 'healthy' or health['batches'] or row['marker_files_after_retry']:
                    raise AssertionError('Upstream behavior differs from the documented bounded observation.')
            cases.append(row)
    return dict(synthetic_only=True, source_variant='file-persistence-prototype' if prototype else 'upstream',
                revision=None if prototype else REVISION, parent_revision=REVISION, source_sha256=fingerprint,
                cases=cases, limits='Actual CLI with a deliberately obstructed local export path and authored callbacks. No real archive, installed hook, normal agent session, remote exporter, crash/partial-write guarantee, or commercial advantage.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--python', default=sys.executable)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.source, args.python), indent=2))
