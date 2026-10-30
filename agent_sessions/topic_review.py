"""Refresh a saved topic from assistant review without losing manual evidence.

New active contracts and immutable captures are written before the topic pointer.
Captures record bytes, not factual truth or current authority.
"""

import contextlib
import hashlib
import json
import secrets
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import load_requirements, validate_requirements
from agent_sessions.analysis.selection_import import (
    prepare_selection_review, import_selection_review, read_selection_packet,
)
from agent_sessions.analysis.scope import normalize_projects
from agent_sessions.storage import StorageError, atomic_write_text, directory_lock
from agent_sessions.workspace import (
    CONFIG_NAME, _managed_path, _load_workspace_snapshot, get_topic,
)

ORIGIN = 'assistant_selection_import_v1'


@contextlib.contextmanager
def topic_review_lock(directory, name):
    root, _, _ = get_topic(directory, name)
    _managed_path(root, 'locks').mkdir(exist_ok=True, mode=0o700)
    with directory_lock(_managed_path(root, 'locks', name)):
        yield get_topic(root, name)


def mutate_topic_requirements(directory, name, operation):
    """Resolve the active file after acquiring the same lock used by refresh."""
    with topic_review_lock(directory, name) as (_, archive, topic):
        return operation(archive, Path(topic['requirements']), topic)


def prepare_topic_review(directory, name, *, max_prompt_chars=32_000, batch_review=False, compact_review=False,
                         max_total_prompt_chars=None, view=None):
    root, _, _ = get_topic(directory, name)
    _, config, config_hash = _load_workspace_snapshot(root)
    archive, topic = Path(config['archive']), config['topics'][name]
    requirements = Path(topic['requirements'])
    existing_view = load_requirements(requirements).get('view', 'dialogue') if requirements.is_file() else None
    if view is not None and existing_view is not None and view != existing_view:
        raise ValueError('Review views differ; existing work was preserved.')
    view = view or existing_view or 'dialogue'
    parent = _managed_path(root, 'selection-reviews', name)
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = _managed_path(root, 'selection-reviews', name, secrets.token_hex(12))
    result = prepare_selection_review(archive, output, topic['query'], projects=topic.get('projects'),
                                      max_prompt_chars=max_prompt_chars, batch_review=batch_review, compact_review=compact_review,
                                      max_total_prompt_chars=max_total_prompt_chars, view=view)
    if _load_workspace_snapshot(root)[2] != config_hash:
        raise StorageError('The saved topic changed during preparation. Prepare a new review packet.')
    return dict(result, topic=name)


def _evidence_key(anchor):
    return (anchor.get('view', 'dialogue'), anchor['session_id'], anchor.get('agent'), anchor.get('role'), anchor.get('section_sha256'),
            anchor.get('unit', 'section'), anchor.get('paragraph', {}).get('sha256'))


def _merge(old, incoming):
    view = incoming.get('view', 'dialogue')
    if (old.get('requirements') or 'view' in old) and old.get('view', 'dialogue') != view:
        raise ValueError('Review views differ; existing work was preserved.')
    before = {item['id']: item for item in old['requirements']}
    protected = {item['id'] for item in old['requirements'] if item.get('selection_origin') != ORIGIN}
    while True:
        targets = {before[identifier]['challenge_for'] for identifier in protected
                   if before[identifier].get('challenge_for')}
        if targets <= protected:
            break
        protected |= targets
    kept = [item for item in old['requirements'] if item['id'] in protected]
    old_generated = {}
    for item in old['requirements']:
        if item.get('selection_origin') == ORIGIN:
            old_generated.setdefault(_evidence_key(item), []).append(item)
    selected = []
    for item in incoming['requirements']:
        if item['id'] in protected:
            prior = before[item['id']]
            if _evidence_key(prior) != _evidence_key(item) or prior['quote'] != item['quote']:
                raise ValueError('An assistant selection would replace protected manual evidence. Existing work was preserved.')
            continue
        matches = old_generated.get(_evidence_key(item), [])
        if len(matches) == 1 and matches[0].get('reviewed_candidates'):
            item['reviewed_candidates'] = matches[0]['reviewed_candidates']
        selected.append(item)
    result = dict(old, requirements=kept + selected, assistant_review=incoming['assistant_review'])
    if view == 'evidence':
        result['view'] = view
    validate_requirements(result)
    return result, len(kept), len(selected)


def _capture(root, name, raw):
    digest = hashlib.sha256(raw).hexdigest()
    parent = _managed_path(root, 'requirement-captures', name)
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = _managed_path(root, 'requirement-captures', name, digest + '.json')
    if output.exists():
        if output.read_bytes() != raw:
            raise StorageError('An existing requirement capture is damaged. Restore it before refreshing.')
    else:
        atomic_write_text(output, raw.decode('utf-8'))
    return str(output)


def import_topic_review(directory, name, packet_directory, answer):
    with topic_review_lock(directory, name) as (root, archive, initial_topic):
        old_path = Path(initial_topic['requirements'])
        active_parent = _managed_path(root, 'reviewed-requirements', name)
        active_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        old_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with contextlib.ExitStack() as locks:
            for path in sorted({root, old_path.parent, active_parent}, key=str):
                locks.enter_context(directory_lock(path))
            _, config, _ = _load_workspace_snapshot(root)
            topic = config['topics'][name]
            if topic != initial_topic or Path(config['archive']) != archive:
                raise StorageError('The saved topic changed before refresh. Retry with the current topic.')
            packet = read_selection_packet(packet_directory)
            if (Path(packet['archive']) != archive or packet['query'] != topic['query']
                    or packet['projects'] != normalize_projects(topic.get('projects'))):
                raise ValueError('The review packet belongs to another archive, query, or project scope.')
            old_raw = old_path.read_bytes() if old_path.is_file() else None
            if old_raw is None:
                default = _managed_path(root, 'requirements', name + '.json')
                if old_path != default or (root / 'history' / name / 'history.json').exists():
                    raise StorageError('Existing topic requirements are missing. Restore them before refreshing.')
                old = dict(version=1, requirements=[])
            else:
                old = load_requirements(old_path)
            staging = _managed_path(root, 'selection-staging')
            staging.mkdir(exist_ok=True, mode=0o700)
            with tempfile.TemporaryDirectory(prefix=name + '-', dir=staging) as temporary:
                imported = Path(temporary) / 'imported.json'
                import_selection_review(packet_directory, answer, imported)
                merged, manual_count, generated_count = _merge(old, load_requirements(imported))
            raw = (json.dumps(merged, ensure_ascii=False, indent=2) + '\n').encode()
            captures = [_capture(root, name, old_raw)] if old_raw is not None else []
            captures.append(_capture(root, name, raw))
            captures = list(dict.fromkeys(captures))
            if read_selection_packet(packet_directory)['packet_sha256'] != packet['packet_sha256']:
                raise StorageError('The review packet changed during topic refresh.')
            if old_raw is not None and old_path.read_bytes() != old_raw:
                raise StorageError('Manual evidence changed during topic refresh. Retry with settled inputs.')
            if raw == old_raw:
                return dict(topic=name, requirements_path=str(old_path), previous_requirements_path=str(old_path),
                            preserved_requirements=manual_count, generated_requirements=generated_count,
                            contract_captures=captures, ready=False, changed=False)
            output = _managed_path(root, 'reviewed-requirements', name, secrets.token_hex(12) + '.json')
            if output.exists():
                raise StorageError('The new requirements path already exists. Retry the refresh.')
            atomic_write_text(output, raw.decode('utf-8'))
            topic['requirements'] = str(output)
            atomic_write_text(root / CONFIG_NAME, json.dumps(config, ensure_ascii=False, indent=2) + '\n')
            return dict(topic=name, requirements_path=str(output), previous_requirements_path=str(old_path),
                        preserved_requirements=manual_count, generated_requirements=generated_count,
                        contract_captures=captures, ready=False, changed=True)
