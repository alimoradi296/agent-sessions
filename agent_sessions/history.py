"""Private content-addressed handoff revisions and evidence-change summaries.

Revision identities describe captured content, not truth or current authority.
The index is replaced last. Unindexed partial revisions are not history entries.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from agent_sessions.analysis.continuity import read_bundle_snapshot, write_bundle
from agent_sessions.storage import StorageError, atomic_write_text, directory_lock


def _revision_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise StorageError('Invalid handoff revision ID. Use the complete hash from topic history.')


def _revision_path(directory, revision):
    _revision_id(revision)
    path = directory / revision
    if path.is_symlink():
        raise StorageError('Historical revision directories must not be symlinks.')
    return path


def load_history(directory):
    directory = Path(directory)
    if directory.is_symlink() or (directory / 'history.json').is_symlink():
        raise StorageError('History paths must not be symlinks.')
    path = directory / 'history.json'
    if not path.exists():
        if directory.is_dir() and any(re.fullmatch(r'[0-9a-f]{64}', child.name) for child in directory.iterdir()):
            raise StorageError('History index is missing while revision directories exist. Restore the index before saving another capture.')
        return dict(version=1, head=None, previous_head=None, last_ready=None, revisions=[])
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or set(data) != {'version', 'head', 'previous_head', 'last_ready', 'revisions'}
            or data['version'] != 1 or not isinstance(data['revisions'], list)):
        raise StorageError('Invalid handoff history index. Restore it before saving another revision.')
    seen = {}
    for item in data['revisions']:
        if not isinstance(item, dict) or set(item) != {'id', 'ready'} or type(item['ready']) is not bool:
            raise StorageError('Invalid handoff history entry.')
        _revision_id(item['id'])
        if item['id'] in seen:
            raise StorageError('Duplicate handoff history revision.')
        seen[item['id']] = item
    for key in ('head', 'previous_head', 'last_ready'):
        if data[key] is not None and data[key] not in seen:
            raise StorageError('History pointer does not refer to a recorded revision.')
    if data['revisions'] and data['head'] is None:
        raise StorageError('Recorded revisions require a current history pointer.')
    if any(item['ready'] for item in data['revisions']) and data['last_ready'] is None:
        raise StorageError('Ready captures require a last-ready history pointer.')
    if data['last_ready'] is not None and not seen[data['last_ready']]['ready']:
        raise StorageError('The last-ready pointer refers to a draft.')
    return data


def read_revision(directory, revision):
    history = load_history(directory)
    entry = next((item for item in history['revisions'] if item['id'] == revision), None)
    if entry is None:
        raise ValueError('That revision is not in this topic history.')
    text, manifest = read_bundle_snapshot(_revision_path(Path(directory), revision))
    if manifest['manifest_sha256'] != revision or entry['ready'] != manifest.get('ready'):
        raise StorageError('Historical revision folder does not match the captured manifest.')
    return text, manifest


def inspect_history(directory):
    history = load_history(directory)
    for entry in history['revisions']:
        _, manifest = read_bundle_snapshot(_revision_path(Path(directory), entry['id']))
        if manifest['manifest_sha256'] != entry['id'] or manifest.get('ready') != entry['ready']:
            raise StorageError('History entry does not match its captured bundle.')
    return history


def compare_manifests(previous, current):
    """Describe observable changes without interpreting decisions or adoption."""
    previous = previous or {}
    before = {item['id']: item for item in previous.get('requirements', [])}
    after = {item['id']: item for item in current.get('requirements', [])}
    result = dict(initial=not bool(previous), query_changed=previous.get('query') != current.get('query'),
                  rendering_changed=previous.get('rendering') != current.get('rendering'),
                  assistant_review_changed=previous.get('assistant_review') != current.get('assistant_review'),
                  scope_changed=previous.get('scope', {}).get('projects', []) != current.get('scope', {}).get('projects', []),
                  scope_coverage_changed=previous.get('scope') != current.get('scope'),
                  requirements_added=sorted(after.keys() - before.keys()),
                  requirements_removed=sorted(before.keys() - after.keys()),
                  requirements_changed=[], review_opened=[], review_no_longer_pending=[],
                  source_updates=[], selected_sources_added=[], selected_sources_removed=[],
                  readiness_before=previous.get('ready'), readiness_after=current['ready'])
    old_inspection = {item['session_id']: item for item in previous.get('source_inspection', {}).get('sources', [])}
    new_inspection = {item['session_id']: item for item in current.get('source_inspection', {}).get('sources', [])}
    result['inspection_pending'] = current.get('source_inspection', {}).get('pending')
    result['inspection_queue_changed'] = old_inspection != new_inspection
    result['inspection_updates'] = [dict(session_id=sid, before=old_inspection.get(sid, {}).get('status'),
                                         after=new_inspection.get(sid, {}).get('status'))
                                    for sid in sorted(old_inspection.keys() | new_inspection.keys())
                                    if old_inspection.get(sid) != new_inspection.get(sid)]
    fields = ('status', 'quote', 'unit', 'section', 'pinned_section', 'agent', 'role',
              'section_sha256', 'paragraph', 'source_update', 'challenge_for', 'link_note', 'selection_reason', 'selection_origin')
    for identifier in sorted(before.keys() & after.keys()):
        changed = [field for field in fields if before[identifier].get(field) != after[identifier].get(field)]
        if changed:
            result['requirements_changed'].append(dict(id=identifier, fields=changed,
                                                       status_before=before[identifier]['status'],
                                                       status_after=after[identifier]['status']))
    for identifier in sorted(before.keys() | after.keys()):
        old = {item['review_id']: item for item in before.get(identifier, {}).get('unreviewed_candidates', [])}
        new = {item['review_id']: item for item in after.get(identifier, {}).get('unreviewed_candidates', [])}
        reviewed = {item['id'] for item in after.get(identifier, {}).get('reviewed_candidates', [])}
        for candidate_id in sorted(new.keys() - old.keys()):
            candidate = new[candidate_id]
            result['review_opened'].append(dict(requirement_id=identifier, review_id=candidate_id,
                                                kind=candidate['kind'], witness=candidate['witness']))
        for candidate_id in sorted(old.keys() - new.keys()):
            reason = ('requirement_removed' if identifier not in after else
                      'review_note_recorded' if candidate_id in reviewed else 'candidate_no_longer_pending')
            result['review_no_longer_pending'].append(dict(requirement_id=identifier, review_id=candidate_id, reason=reason))
    old_sources = {item['session_id']: item for item in previous.get('sources', [])}
    new_sources = {item['session_id']: item for item in current.get('sources', [])}
    result['selected_sources_added'] = sorted(new_sources.keys() - old_sources.keys())
    result['selected_sources_removed'] = sorted(old_sources.keys() - new_sources.keys())
    for sid in sorted(old_sources.keys() & new_sources.keys()):
        old, new = old_sources[sid], new_sources[sid]
        if old['source_sha256'] != new['source_sha256'] or old['selected_evidence'] != new['selected_evidence']:
            result['source_updates'].append(dict(session_id=sid,
                                                source_content_changed=old['source_sha256'] != new['source_sha256'],
                                                selected_evidence_changed=old['selected_evidence'] != new['selected_evidence']))
    return result


def record_revision(directory, text, manifest):
    directory = Path(directory)
    if directory.is_symlink():
        raise StorageError('History directories must not be symlinks.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    revision = manifest['manifest_sha256']
    with directory_lock(directory):
        history = load_history(directory)
        if not (directory / 'history.json').exists():
            atomic_write_text(directory / 'history.json', json.dumps(history, indent=2) + '\n')
        old_head = history['head']
        previous = read_revision(directory, old_head)[1] if old_head else None
        if history['last_ready'] and history['last_ready'] != old_head:
            read_revision(directory, history['last_ready'])
        path = _revision_path(directory, revision)
        if any(item['id'] == revision for item in history['revisions']):
            saved_text, saved_manifest = read_revision(directory, revision)
            if saved_manifest != manifest or saved_text != text:
                raise StorageError('Existing historical revision differs from the new capture.')
        else:
            write_bundle(path, text, manifest)
            read_bundle_snapshot(path)
            history['revisions'].append(dict(id=revision, ready=manifest['ready']))
        if revision != old_head:
            history['previous_head'] = old_head
            history['head'] = revision
            if manifest['ready']:
                history['last_ready'] = revision
            atomic_write_text(directory / 'history.json', json.dumps(history, indent=2) + '\n')
        return dict(revision=revision, previous_revision=old_head, last_ready_revision=history['last_ready'],
                    changed=revision != old_head, revision_count=len(history['revisions']),
                    revision_path=str(path), changes=compare_manifests(previous, manifest))


def latest_changes(directory, *, include_diff=False):
    history = load_history(directory)
    if not history['head']:
        raise ValueError('No handoff revisions yet. Run resume NAME first.')
    current_text, current = read_revision(directory, history['head'])
    previous_text, previous = (read_revision(directory, history['previous_head'])
                               if history['previous_head'] else ('', None))
    result = dict(head=history['head'], previous_head=history['previous_head'],
                  changes=compare_manifests(previous, current), historical=True, verification='not_checked')
    if include_diff:
        result['diff'] = ''.join(difflib.unified_diff(previous_text.splitlines(keepends=True),
                                                    current_text.splitlines(keepends=True),
                                                    fromfile='previous historical handoff', tofile='current captured handoff'))
    return result
