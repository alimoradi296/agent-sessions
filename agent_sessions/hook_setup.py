"""Install user-level Codex and Cursor exporters without shell PATH assumptions.

Only this exporter's known commands are replaced. Generated launchers and
backups contain local paths and belong outside public repositories.
"""

from __future__ import annotations

import copy
import json
import os
import shlex
import sys
import time
from pathlib import Path

from agent_sessions.storage import StorageError, atomic_write_many, atomic_write_text, directory_lock


class HookSetupError(StorageError):
    pass


def launcher_text(agent: str, output: Path) -> str:
    package_root = Path(__file__).resolve().parents[1]
    arguments = ['agent-sessions', 'hook', '--agent', agent, '--output', str(output)]
    return (
        '# Managed by agent-sessions. Reinstall after moving the Python environment or package.\n'
        'import sys\n'
        f'sys.path.insert(0, {str(package_root)!r})\n'
        'from agent_sessions.cli import main\n'
        'if __name__ == "__main__":\n'
        f'    sys.argv = {arguments!r} + sys.argv[1:]\n'
        '    main()\n'
    )


def _managed(command: str, agent: str, base: Path) -> bool:
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    # Known historical and current launcher paths, resolved relative to the
    # user hook directory, identify our own entries without basename guesses.
    known = {base / 'hooks/export-session.sh', base / 'hooks/agent-sessions-export.py'}
    program = Path(words[0]).name if words else ''
    script_tokens = words[:1]
    if program in ('sh', 'bash', 'dash', 'zsh') or program.startswith('python'):
        script_tokens = [word for word in words[1:3] if not word.startswith('-')]
    for token in script_tokens:
        path = Path(token).expanduser()
        if not path.is_absolute():
            path = base / path
        if path.resolve() in {p.resolve() for p in known}:
            return True
    is_cli = program == 'agent-sessions' and words[1:2] == ['hook']
    is_module = program.startswith('python') and any(
        words[i:i + 3] == ['-m', 'agent_sessions', 'hook'] for i in range(len(words) - 2))
    if not (is_cli or is_module):
        return False
    declared = next((words[i + 1] for i in range(len(words) - 1) if words[i] == '--agent'), None)
    declared = next((word.split('=', 1)[1] for word in words if word.startswith('--agent=')), declared)
    # Older Cursor snippets omitted --agent entirely. Their exporter command
    # is still ours, even though the historical default selected Claude.
    return declared in (None, agent)


def _read_config(path: Path) -> tuple[dict, str | None]:
    if not path.exists():
        return {}, None
    try:
        original = path.read_text(encoding='utf-8')
        config = json.loads(original)
    except (OSError, UnicodeError, ValueError) as error:
        raise HookSetupError('Hook configuration is invalid or unreadable. Restore it before installation.') from error
    if not isinstance(config, dict) or not isinstance(config.get('hooks', {}), dict):
        raise HookSetupError('Hook configuration must contain a hooks object.')
    return config, original


def _merge(config: dict, agent: str, base: Path, command: str) -> dict:
    result = copy.deepcopy(config)
    if agent == 'cursor':
        if 'version' in result and (type(result['version']) is not int or result['version'] != 1):
            raise HookSetupError('Unsupported Cursor hook configuration version.')
        result['version'] = 1
    hooks = result.setdefault('hooks', {})
    events = ('stop', 'agent-end') if agent == 'cursor' else ('Stop',)
    for event in events:
        if event not in hooks:
            continue
        entries = hooks[event]
        if not isinstance(entries, list):
            raise HookSetupError('Expected a list of hook entries.')
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise HookSetupError('Expected hook entry objects.')
            if agent == 'cursor':
                if entry.get('type') == 'prompt':
                    kept.append(entry)
                    continue
                if not isinstance(entry.get('command'), str):
                    raise HookSetupError('Expected a hook command string.')
                if not _managed(entry['command'], agent, base):
                    kept.append(entry)
            else:
                children = entry.get('hooks')
                if not isinstance(children, list) or not all(isinstance(child, dict) for child in children):
                    raise HookSetupError('Expected a list of Codex hook handlers.')
                remaining = [child for child in children if not (
                    isinstance(child.get('command'), str) and _managed(child['command'], agent, base))]
                if remaining:
                    kept.append({**entry, 'hooks': remaining})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    handler = {'command': command, 'timeout': 60}
    if agent == 'codex':
        handler['type'] = 'command'
        hooks.setdefault('Stop', []).append({'hooks': [handler]})
    else:
        hooks.setdefault('stop', []).append(handler)
    return result


def install_hooks(agent: str, output: Path | None = None, dry_run: bool = False) -> dict:
    if agent not in ('codex', 'cursor'):
        raise HookSetupError('This installer supports Codex and Cursor.')
    if os.name != 'posix':
        raise HookSetupError('Hook installation currently requires a POSIX shell environment.')
    base = Path.home() / f'.{agent}'
    config_path = base / 'hooks.json'
    script = base / 'hooks/agent-sessions-export.py'
    output = (output or (Path.home() / '.agent-sessions/exports')).expanduser().resolve()
    python = Path(sys.executable).absolute()
    command = shlex.join([str(python), str(script)])
    script_text = launcher_text(agent, output)

    def prepare():
        config, original = _read_config(config_path)
        merged = _merge(config, agent, base, command)
        config_text = json.dumps(merged, indent=2, ensure_ascii=False) + '\n'
        try:
            previous_script = script.read_text(encoding='utf-8') if script.exists() else None
        except (OSError, UnicodeError) as error:
            raise HookSetupError('Existing exporter launcher is unreadable.') from error
        return original, previous_script, config_text

    backups = []
    if dry_run:
        original, previous_script, config_text = prepare()
    else:
        with directory_lock(base):
            original, previous_script, config_text = prepare()
            changes = {}
            for path, before, after in ((script, previous_script, script_text),
                                        (config_path, original, config_text)):
                if before == after:
                    continue
                if before is not None:
                    backup = path.with_name(f'{path.name}.agent-sessions-backup-{time.time_ns()}')
                    atomic_write_text(backup, before)
                    backups.append(str(backup))
                changes[path] = after
            # The launcher is staged before configuration references it.
            atomic_write_many(changes)
    return dict(agent=agent, config_path=str(config_path), script_path=str(script),
                output=str(output), command=command, backups=backups, dry_run=dry_run,
                changed=original != config_text or previous_script != script_text)
