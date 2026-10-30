"""Run pinned recovery/verification on synthetic histories, never user rollouts."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

REVISION = '7fe5e66fe7d07f427adf83a08ad6508704a1337e'
SOURCE_SHA256 = '1e0c12264f46109855d63fd8ca22a1ee0709f02e59bd56317af9f63263dac329'
PROTOTYPE_SHA256 = 'e6118994a815605908418b70893147b7ec2c5122bed03d901c8ba5ec698474a5'
SCOPED_EDITOR_SHA256 = 'e87987f95a6e6fd63441125166b9b9eb8931db6c14eaa836d87878b59f926bef'
EDITOR_BRIDGE_SHA256 = 'f5b36e0475b5bc7c286b66315d9733d242287f9030576fb2e3d5af14e5cab21b'
EDITOR_SHA256 = 'b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306'


def source_fingerprint(source):
    source = Path(source).resolve()
    paths = sorted([source / 'package.json', source / 'bun.lock', *source.joinpath('src').glob('*.ts')],
                   key=lambda p: p.relative_to(source).as_posix())
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Provide the complete pinned source checkout.')
        digest.update(path.relative_to(source).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def validate_source(source):
    source = Path(source).resolve()
    if source_fingerprint(source) not in (SOURCE_SHA256, PROTOTYPE_SHA256, EDITOR_BRIDGE_SHA256, SCOPED_EDITOR_SHA256):
        raise ValueError('Source does not match the documented pin; execution refused.')
    return source


def scenarios():
    ordinary = '*** Update File: example.py\n@@\n-old\n+new\n'
    function_base = 'def first():\n    return 1\n\ndef second():\n    return 1\n'
    return [
        ('ordinary', 'old\n', ordinary, 'success', 'new\n'),
        ('function-selector', function_base, '*** Update File: example.py\n@@ def second():\n-    return 1\n+    return 2\n',
         'success', 'def first():\n    return 1\n\ndef second():\n    return 2\n'),
        ('eof-selector', 'value = 1\nseparator\nvalue = 1\n',
         '*** Update File: example.py\n@@\n-value = 1\n+value = 2\n*** End of File\n',
         'success', 'value = 1\nseparator\nvalue = 2\n'),
        ('missing-base', None, ordinary, 'success', None),
        ('replay-mismatch', 'old\n', '*** Update File: example.py\n@@\n-different\n+new\n', 'success', None),
        ('opaque-later', 'old\n', "sed -i 's/old/new/' example.py", 'shell', None),
        ('failed-later', 'old\n', ordinary, 'failed', None),
        ('missing-completion', 'old\n', ordinary, 'missing', None),
        ('missing-completion-filtered', 'old\n', ordinary, 'missing-filtered', None),
        ('copy-destination', 'old\n', 'cp other.py example.py', 'copy-destination', None),
        ('move-destination', 'old\n', 'mv other.py example.py', 'move-destination', None),
        ('move-source', 'old\n', 'mv example.py other.py', 'move-source', None),
    ]


def validate_editor(editor):
    # Preserve the apply_patch invocation name: resolving the alias can select
    # a different mode of the same executable.
    editor = Path(editor).absolute()
    if editor.name != 'apply_patch':
        raise ValueError('Provide the documented pinned apply_patch helper; execution refused.')
    digest = hashlib.sha256()
    with editor.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != EDITOR_SHA256:
        raise ValueError('Provide the documented pinned apply_patch helper; execution refused.')
    return str(editor)


def evaluate(source, bun, editor=None):
    source = validate_source(source)  # Before invoking any supplied executable.
    fingerprint = source_fingerprint(source)
    variant = {SOURCE_SHA256: 'upstream', PROTOTYPE_SHA256: 'uncertainty-filter-prototype',
               EDITOR_BRIDGE_SHA256: 'pinned-existing-editor-bridge',
               SCOPED_EDITOR_SHA256: 'scoped-existing-editor-bridge'}[fingerprint]
    if fingerprint in (EDITOR_BRIDGE_SHA256, SCOPED_EDITOR_SHA256) and editor is None:
        raise ValueError('The existing-editor bridge requires the pinned --editor helper.')
    editor = validate_editor(editor) if editor is not None else None
    bun = str(Path(bun).resolve())
    results = []
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-recovery-') as temporary:
        root = Path(temporary)
        for name in ('home', 'cache', 'scratch', 'codex-home'):
            (root / name).mkdir()
        env = dict(HOME=str(root / 'home'), PATH=str(Path(bun).parent) + ':/usr/bin:/bin', LANG='C.UTF-8',
                   XDG_CACHE_HOME=str(root / 'cache'), TMPDIR=str(root / 'scratch'),
                   CODEX_HOME=str(root / 'codex-home'), DO_NOT_TRACK='1')
        if fingerprint in (EDITOR_BRIDGE_SHA256, SCOPED_EDITOR_SHA256):
            env['AGENT_SESSIONS_PATCH_EDITOR'] = editor
        def run(*args):
            return subprocess.run([bun, *args], cwd=source, env=env, capture_output=True, text=True, check=True).stdout
        version = run('--version').strip()
        if version != '1.3.3':
            raise ValueError('Use the documented Bun 1.3.3 runtime for this comparison.')
        for name, base, patch, kind, expected in scenarios():
            case = root / name
            case.mkdir()
            project = case / 'project'
            project.mkdir()
            sentinel = project / 'keep.txt'
            sentinel.write_text('Synthetic sentinel.\n')
            target = str(project / 'example.py')
            records = [dict(type='session_meta', payload=dict(id='synthetic-' + name, cwd=str(project)))]
            def add_patch(call_id, text, status='success'):
                records.append(dict(type='response_item', payload=dict(type='custom_tool_call', name='apply_patch',
                    call_id=call_id, input='*** Begin Patch\n' + text.replace('example.py', target) + '*** End Patch\n')))
                if status != 'missing':
                    output = 'Exit code: 1\nOutput:\nverification failed' if status == 'failed' else 'Exit code: 0\nOutput:\nSuccess.'
                    records.append(dict(type='response_item', payload=dict(type='custom_tool_call_output', call_id=call_id, output=output)))
            if base is not None:
                add_patch('create', '*** Add File: example.py\n' + ''.join('+' + line + '\n' for line in base.splitlines()))
            cross_file = kind in ('copy-destination', 'move-destination', 'move-source')
            if cross_file:
                add_patch('create-other', '*** Add File: ' + str(project / 'other.py') + '\n+new\n')
            if kind == 'shell' or cross_file:
                records.extend([
                    dict(type='response_item', payload=dict(type='function_call', name='exec_command', call_id='later',
                         arguments=json.dumps(dict(cmd=patch.replace('example.py', target).replace('other.py', str(project / 'other.py')), workdir=str(project))))),
                    dict(type='response_item', payload=dict(type='function_call_output', call_id='later', output='Exit code: 0\nOutput:\n')),
                ])
            else:
                add_patch('later', patch, 'missing' if kind == 'missing-filtered' else kind)
            rollout = case / 'rollout.jsonl'
            rollout.write_text(''.join(json.dumps(record) + '\n' for record in records))
            archive = case / 'recovered.zip'
            args = ['src/main.ts', 'recover', str(rollout), '--out', str(archive), '--codex-home', str(root / 'codex-home'), '--json']
            if kind == 'missing-filtered' or cross_file:
                args.extend(['--paths', target])
            run(*args)
            verified = json.loads(run('src/main.ts', 'verify', str(archive), '--json'))
            with zipfile.ZipFile(archive) as z:
                files = json.loads(z.read('manifest/files.json'))
                file = next(item for item in files if item['path'] == target)
                unresolved = [line for line in z.read('manifest/unresolved-mutations.jsonl').splitlines() if line]
                content = z.read(file['safeZipPath']).decode() if file['safeZipPath'] in z.namelist() else None
            if sentinel.read_text() != 'Synthetic sentinel.\n' or (project / 'example.py').exists() or (project / 'other.py').exists():
                raise ValueError('Recovery modified the simulated live project.')
            row = dict(case=name, status=file['status'], warnings=file['warnings'], unresolved=len(unresolved),
                                content_sha256=None if content is None else hashlib.sha256(content.encode()).hexdigest(),
                                verify_ok=verified['ok'], matches_expected_latest=None if expected is None else content == expected,
                                path_filtered=kind == 'missing-filtered' or cross_file, live_project_untouched=True)
            if cross_file:
                row['authored_command_effect'] = 'source removed' if kind == 'move-source' else 'destination overwritten'
                row['uncertainty_visible'] = bool(unresolved or file['warnings'])
            if editor is not None:
                row['canonical_editor'] = dict(attempted=False, reason='Fixture does not establish a replayable successful patch.')
                if kind == 'success':
                    scratch = case / 'canonical'
                    scratch.mkdir()
                    target_file = scratch / 'example.py'
                    before = None if base is None else base.encode()
                    if before is not None:
                        target_file.write_bytes(before)
                    result = subprocess.run([editor], input='*** Begin Patch\n' + patch + '*** End Patch\n',
                        cwd=scratch, env=env, capture_output=True, text=True, timeout=20)
                    after = target_file.read_bytes() if target_file.exists() else None
                    row['canonical_editor'] = dict(attempted=True, exit_code=result.returncode,
                        matches_expected=None if expected is None else after == expected.encode(),
                        archive_matches_editor=None if result.returncode else content is not None and content.encode() == after,
                        base_preserved_on_failure=None if result.returncode == 0 else after == before,
                        output_sha256=None if after is None else hashlib.sha256(after).hexdigest())
                if sentinel.read_text() != 'Synthetic sentinel.\n' or (project / 'example.py').exists() or (project / 'other.py').exists():
                    raise ValueError('Editor comparison modified the simulated live project.')
            results.append(row)
    return dict(synthetic_only=True, revision=REVISION if variant == 'upstream' else None, parent_revision=REVISION,
                source_variant=variant, source_sha256=fingerprint, bun=version, cases=results,
                editor_binary_sha256=EDITOR_SHA256 if editor is not None else None,
                limits='Actual recover/verify CLI with absolute synthetic patch paths. No live-base reads, private history, model, or archived-command execution. ZIP integrity does not establish editor equivalence or latest file state.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--bun', required=True)
    parser.add_argument('--editor', help='Optional pinned local apply_patch helper for synthetic known-base comparison')
    args = parser.parse_args()
    print(json.dumps(evaluate(args.source, args.bun, args.editor), indent=2))
