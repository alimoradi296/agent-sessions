"""Restore an authored two-module checkout and check behavior outside its archive.

This executes only authored Python and pinned recovery/editor programs. It never
reads user histories or executes commands obtained from arbitrary transcripts.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from examples.recovery_archive_probe import validate_source, validate_editor, REVISION, SOURCE_SHA256, EDITOR_BRIDGE_SHA256, SCOPED_EDITOR_SHA256, source_fingerprint


PRICING = 'def standard_fee():\n    return 5\n\ndef express_fee():\n    return 5\n'
CHECKOUT = ('import json\nfrom pricing import standard_fee, express_fee\n'
            'print(json.dumps(dict(standard=standard_fee(), express=express_fee())))\n')
UPDATE = '*** Update File: pricing.py\n@@ def express_fee():\n-    return 5\n+    return 12\n'
EXPECTED = dict(standard=5, express=12)


def evaluate(source, bun, editor):
    source = validate_source(source)
    fingerprint = source_fingerprint(source)
    if fingerprint not in (SOURCE_SHA256, EDITOR_BRIDGE_SHA256, SCOPED_EDITOR_SHA256):
        raise ValueError("This comparison requires upstream or the exact existing-editor bridge.")
    editor = validate_editor(editor)
    bun = str(Path(bun).resolve())
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-project-') as temporary:
        root = Path(temporary)
        for name in ('home', 'cache', 'codex-home', 'scratch', 'original', 'ordinary-replay', 'archive-restored'):
            (root / name).mkdir()
        env = dict(HOME=str(root / 'home'), PATH='/usr/bin:/bin', LANG='C.UTF-8',
                   XDG_CACHE_HOME=str(root / 'cache'), TMPDIR=str(root / 'scratch'),
                   CODEX_HOME=str(root / 'codex-home'), PYTHONDONTWRITEBYTECODE='1', DO_NOT_TRACK='1')
        if fingerprint in (EDITOR_BRIDGE_SHA256, SCOPED_EDITOR_SHA256):
            env['AGENT_SESSIONS_PATCH_EDITOR'] = editor
        def run(argv, cwd, **kwargs):
            return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                                  timeout=30, check=True, **kwargs)
        if run([bun, '--version'], source).stdout.strip() != '1.3.3':
            raise ValueError('Use the documented Bun 1.3.3 runtime.')
        patches = ['*** Add File: pricing.py\n' + ''.join('+' + line + '\n' for line in PRICING.splitlines()),
                   '*** Add File: checkout.py\n' + ''.join('+' + line + '\n' for line in CHECKOUT.splitlines()), UPDATE]
        records = [dict(type='session_meta', payload=dict(id='synthetic-project-recovery', cwd=str(root / 'original')))]
        for index, patch in enumerate(patches):
            # Relocate only these two authored paths; never interpret arbitrary archive paths.
            absolute = patch
            for filename in ('pricing.py', 'checkout.py'):
                for directive in ('*** Add File: ', '*** Update File: '):
                    absolute = absolute.replace(directive + filename + '\n', directive + str(root / 'original' / filename) + '\n')
            records += [dict(type='response_item', payload=dict(type='custom_tool_call', name='apply_patch',
                        call_id=f'authored-{index}', input='*** Begin Patch\n' + absolute + '*** End Patch\n')),
                        dict(type='response_item', payload=dict(type='custom_tool_call_output', call_id=f'authored-{index}',
                        output='Success. Updated the following files:\n'))]
            run([editor], root / 'ordinary-replay', input='*** Begin Patch\n' + patch + '*** End Patch\n')
        rollout = root / 'synthetic.jsonl'
        rollout.write_text(''.join(json.dumps(record) + '\n' for record in records))
        archive = root / 'recovered.zip'
        run([bun, 'src/main.ts', 'recover', str(rollout), '--out', str(archive),
             '--codex-home', str(root / 'codex-home'), '--json'], source)
        integrity = json.loads(run([bun, 'src/main.ts', 'verify', str(archive), '--json'], source).stdout)
        with zipfile.ZipFile(archive) as z:
            manifest = json.loads(z.read('manifest/files.json'))
            selected = []
            for filename in ('pricing.py', 'checkout.py'):
                entry = next(item for item in manifest if item['path'] == str(root / 'original' / filename))
                (root / 'archive-restored' / filename).write_bytes(z.read(entry['safeZipPath']))
                selected.append(dict(file=filename, status=entry['status'], warnings=entry['warnings']))
        results = {}
        for arm in ('ordinary-replay', 'archive-restored'):
            actual = json.loads(run([sys.executable, '-E', '-s', '-S', 'checkout.py'], root / arm).stdout)
            results[arm] = dict(actual=actual, matches_authored_behavior=actual == EXPECTED)
        untouched = not any((root / 'original').iterdir())
        if not untouched or not integrity['ok'] or not results['ordinary-replay']['matches_authored_behavior']:
            raise AssertionError('A baseline, archive integrity, or isolation control failed.')
        return dict(synthetic_only=True, source_revision=REVISION if fingerprint == SOURCE_SHA256 else None, parent_revision=REVISION,
            source_variant={SOURCE_SHA256: 'upstream', EDITOR_BRIDGE_SHA256: 'pinned-existing-editor-bridge',
                            SCOPED_EDITOR_SHA256: 'scoped-existing-editor-bridge'}[fingerprint],
            source_sha256=fingerprint,
            expected_behavior=EXPECTED, recovery_manifest=selected, archive_integrity_ok=integrity['ok'],
            arms=results, original_project_untouched=untouched,
            limits='Two authored Python modules and successful patch records with complete known bases. '
                   'The behavioral oracle is outside the recovered archive. No private incident, model, cloud '
                   'source retrieval, unknown mutation, binary recovery, receiving-user effort, uniqueness, or demand measured. '
                   'Exit zero means controls ran, not that both recovery arms restored correct behavior.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--bun', required=True)
    parser.add_argument('--editor', required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.source, args.bun, args.editor), indent=2))
