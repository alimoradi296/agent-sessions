"""Private named topics for the search → pin → resume workflow.

Workspace state lives outside Git checkouts. Initialization never discovers
transcripts, installs hooks, runs commands, contacts a service, or exports data.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from agent_sessions.analysis.continuity import compile_handoff, write_bundle
from agent_sessions.history import record_revision
from agent_sessions.analysis.scope import normalize_projects
from agent_sessions.storage import LOCK_FILENAME, StorageError, atomic_write_text, directory_lock

CONFIG_NAME = 'workspace.json'
DEFAULT_LIMITS = dict(last=5, max_chars=24_000, max_total_chars=64_000)


def default_workspace():
    return Path.home() / '.agent-sessions' / 'workspace'


def validate_topic_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', name):
        raise ValueError('Topic names need 1–64 lowercase letters, digits, underscores, or hyphens, starting with a letter.')


def _git_checkout_marker(parent):
    marker = parent / '.git'
    if marker.is_symlink():
        return True
    if marker.is_file():
        with marker.open('rb') as stream:
            return stream.read(7) == b'gitdir:'
    return (marker / 'HEAD').is_file() and ((marker / 'objects').is_dir() or (marker / 'commondir').is_file())


def _private_root(directory):
    directory = Path(directory).expanduser()
    if directory.is_symlink():
        raise StorageError('The workspace directory must not be a symlink.')
    resolved = directory.resolve()
    if any(_git_checkout_marker(parent) for parent in [resolved, *resolved.parents]):
        raise StorageError('Keep private workspace state outside Git checkouts. Choose a separate private directory.')
    return resolved


def _managed_path(root, *parts):
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise StorageError('Managed workspace paths must not be symlinks.')
    return path


def _load_workspace_snapshot(directory):
    root = _private_root(directory)
    path = _managed_path(root, CONFIG_NAME)
    if not path.is_file():
        raise StorageError('No workspace.json found. Run init --archive PATH --workspace PATH first.')
    raw = path.read_bytes()
    config = json.loads(raw.decode('utf-8'))
    if (not isinstance(config, dict) or config.get('version') != 1
            or set(config) != {'version', 'archive', 'topics'}
            or not isinstance(config['archive'], str) or not Path(config['archive']).is_absolute()
            or not isinstance(config['topics'], dict)):
        raise StorageError('Invalid workspace configuration. Restore it before updating topics.')
    for name, topic in config['topics'].items():
        validate_topic_name(name)
        if (not isinstance(topic, dict) or set(topic) not in ({'query', 'requirements', 'limits'}, {'query', 'requirements', 'limits', 'projects'})
                or not isinstance(topic['query'], str) or not topic['query'].strip()
                or len(topic['query']) > 2000
                or not isinstance(topic['requirements'], str) or not Path(topic['requirements']).is_absolute()
                or not isinstance(topic['limits'], dict) or set(topic['limits']) != set(DEFAULT_LIMITS)
                or any(type(value) is not int or value < 1 for value in topic['limits'].values())):
            raise StorageError('Invalid saved topic. Restore its configuration before updating the workspace.')
        if 'projects' in topic and topic['projects'] is None:
            raise StorageError('Saved project selectors must be a list. Use an empty list only for an explicit all-projects scope.')
        normalize_projects(topic.get('projects'))
    return root, config, hashlib.sha256(raw).digest()


def load_workspace(directory):
    root, config, _ = _load_workspace_snapshot(directory)
    return root, config


def initialize_workspace(directory, archive):
    root = _private_root(directory)
    archive = Path(archive).expanduser().resolve()
    config_path = _managed_path(root, CONFIG_NAME)
    if not config_path.exists() and root.exists():
        if not root.is_dir() or any(path.name != LOCK_FILENAME for path in root.iterdir()):
            raise StorageError('Choose a new or empty private workspace directory.')
        if os.name == 'posix' and root.stat().st_mode & 0o077:
            raise StorageError('The existing workspace directory must have owner-only permissions.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with directory_lock(root):
        if config_path.exists():
            _, existing = load_workspace(root)
            if existing['archive'] != str(archive):
                raise StorageError('This workspace already uses another archive. Choose another workspace directory.')
            return existing
        config = dict(version=1, archive=str(archive), topics={})
        atomic_write_text(config_path, json.dumps(config, indent=2) + '\n')
    return config


def add_topic(directory, name, query, *, requirements=None, limits=None, projects=None):
    validate_topic_name(name)
    projects = normalize_projects(projects)
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError('A topic needs a nonempty query of at most 2000 characters.')
    selected_limits = dict(DEFAULT_LIMITS, **(limits or {}))
    if set(selected_limits) != set(DEFAULT_LIMITS) or any(type(value) is not int or value < 1 for value in selected_limits.values()):
        raise ValueError('Topic limits must be positive integers for last, max_chars, and max_total_chars.')
    root, _ = load_workspace(directory)
    with directory_lock(root):
        _, config = load_workspace(root)
        if name in config['topics']:
            raise ValueError('Topic already exists. Its saved requirements were not changed.')
        requirement_path = (Path(requirements).expanduser().resolve() if requirements else
                            _managed_path(root, 'requirements', name + '.json'))
        topic = dict(query=query.strip(), requirements=str(requirement_path), limits=selected_limits, projects=projects)
        config['topics'][name] = topic
        atomic_write_text(root / CONFIG_NAME, json.dumps(config, indent=2, ensure_ascii=False) + '\n')
    return topic


def get_topic(directory, name):
    validate_topic_name(name)
    root, config = load_workspace(directory)
    topic = config['topics'].get(name)
    if topic is None:
        raise ValueError('Unknown topic. Use topic list to inspect saved names.')
    requirement_path = Path(topic['requirements'])
    if requirement_path.is_relative_to(root):
        _managed_path(root, *requirement_path.relative_to(root).parts)
    return root, Path(config['archive']), topic


def set_topic(directory, name, *, query=None, limits=None, projects=None):
    validate_topic_name(name)
    if query is None and not limits and projects is None:
        raise ValueError('Specify a query or handoff limit to change.')
    if query is not None and (not isinstance(query, str) or not query.strip() or len(query) > 2000):
        raise ValueError('A topic needs a nonempty query of at most 2000 characters.')
    if limits and (not set(limits) <= set(DEFAULT_LIMITS)
                   or any(type(value) is not int or value < 1 for value in limits.values())):
        raise ValueError('Topic limits must be positive integers for last, max_chars, and max_total_chars.')
    root, _ = load_workspace(directory)
    with directory_lock(root):
        _, config = load_workspace(root)
        if name not in config['topics']:
            raise ValueError('Unknown topic. Use topic list to inspect saved names.')
        topic = config['topics'][name]
        if query is not None:
            topic['query'] = query.strip()
        topic['limits'].update(limits or {})
        if projects is not None:
            topic['projects'] = normalize_projects(projects)
        atomic_write_text(root / CONFIG_NAME, json.dumps(config, indent=2, ensure_ascii=False) + '\n')
    return topic


def topic_history_directory(directory, name):
    root, _, _ = get_topic(directory, name)
    return _managed_path(root, 'history', name)


def resume_topic(directory, name):
    """Serialize captures for a topic so a slower resume cannot overwrite a newer one."""
    root, _, _ = get_topic(directory, name)
    locks = _managed_path(root, 'locks')
    locks.mkdir(exist_ok=True, mode=0o700)
    with directory_lock(_managed_path(root, 'locks', name)):
        return _resume_topic_locked(root, name)


def _resume_topic_locked(directory, name):
    """Rebuild a named handoff, refusing drafts for stdout consumption.

    Source freshness and review remain the continuity compiler's responsibility.
    Input hashes before and after compilation detect concurrent changes.
    """
    validate_topic_name(name)
    root, config, config_hash = _load_workspace_snapshot(directory)
    topic = config['topics'].get(name)
    if topic is None:
        raise ValueError('Unknown topic. Use topic list to inspect saved names.')
    archive = Path(config['archive'])
    requirements = Path(topic['requirements'])
    if requirements.is_relative_to(root):
        _managed_path(root, *requirements.relative_to(root).parts)
    if not requirements.is_file():
        raise StorageError('This topic has no evidence requirements yet. Use topic pin NAME to add an anchor.')
    requirements_hash = hashlib.sha256(requirements.read_bytes()).digest()
    text, manifest = compile_handoff(archive, topic['query'], requirements, projects=topic.get('projects'), **topic['limits'])
    if (hashlib.sha256((root / CONFIG_NAME).read_bytes()).digest() != config_hash
            or hashlib.sha256(requirements.read_bytes()).digest() != requirements_hash):
        raise StorageError('Saved topic or evidence requirements changed during resume. Retry with settled inputs.')
    output = _managed_path(root, 'handoffs', name)
    history_parent = _managed_path(root, 'history')
    history_parent.mkdir(exist_ok=True, mode=0o700)
    history_directory = _managed_path(root, 'history', name)
    history = record_revision(history_directory, text, manifest)
    output.parent.mkdir(exist_ok=True, mode=0o700)
    with directory_lock(output):
        write_bundle(output, text, manifest)
    last_ready = history['last_ready_revision']
    return dict(topic=name, ready=manifest['ready'], handoff_path=str(output / 'handoff.md'),
                manifest_path=str(output / 'manifest.json'), manifest=manifest, history=history,
                last_ready_handoff_path=str(history_directory / last_ready / 'handoff.md') if last_ready else None), text
