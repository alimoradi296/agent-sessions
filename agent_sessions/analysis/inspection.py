"""Explicit operator inspection notes bound to source bytes and metadata.

Notes report an operator action. They do not establish understanding, truth,
authorization, or the absence of conflicting instructions.
"""

import hashlib
import json
from collections import Counter

from agent_sessions.analysis.anchors import section_hash
from agent_sessions.analysis.scope import normalize_projects, project_matches, scope_summary
from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.storage import validate_session_id


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_inspections(notes):
    if not isinstance(notes, list) or len(notes) > 10_000:
        raise ValueError('Source inspection notes must be a list with at most 10000 entries.')
    seen = set()
    for note in notes:
        if (not isinstance(note, dict)
                or set(note) != {'session_id', 'agent', 'cwd', 'project_slug', 'source_sha256', 'sections', 'note'}):
            raise ValueError('Invalid source inspection note fields.')
        validate_session_id(note['session_id'])
        if (note['session_id'] in seen or note['agent'] not in ('claude', 'codex', 'cursor')
                or not all(isinstance(note[key], str) for key in ('cwd', 'project_slug'))
                or not _digest(note['source_sha256']) or not isinstance(note['note'], str)
                or not note['note'].strip() or len(note['note']) > 10_000
                or not isinstance(note['sections'], list) or len(note['sections']) > 100_000
                or any(not _digest(value) for value in note['sections'])):
            raise ValueError('Invalid or duplicate source inspection note.')
        seen.add(note['session_id'])
    return notes


def source_identity(row, digest):
    return dict(session_id=row['id'], agent=row['agent'], cwd=row.get('cwd', ''),
                project_slug=row.get('project_slug', ''), source_sha256=digest)


def inspection_id(identity):
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def inspection_summary(rows, digests, notes, projects=None):
    projects = normalize_projects(projects)
    notes = {note['session_id']: note for note in validate_inspections(notes)}
    sources = []
    for sid, row in rows.items():
        if not project_matches(row, projects):
            continue
        prior = notes.get(sid)
        digest = digests.get(sid)
        identity = source_identity(row, digest)
        status = ('unavailable' if digest is None else 'uninspected' if prior is None else
                  'metadata_changed' if any(prior[key] != identity[key] for key in ('agent', 'cwd', 'project_slug')) else
                  'changed' if prior['source_sha256'] != digest else 'note_current')
        prior_identity = {key: prior[key] for key in identity} if prior else None
        sources.append(dict(identity, status=status, inspection_id=inspection_id(identity) if digest else None,
                            prior_source_sha256=prior['source_sha256'] if prior else None,
                            inspection_note=dict(snapshot=inspection_id(prior_identity), note=prior['note']) if prior else None))
    return dict(method='operator_source_notes_v1', pending=sum(source['status'] != 'note_current' for source in sources),
                noted=sum(source['status'] == 'note_current' for source in sources), sources=sources,
                affects_readiness=False, verification='not_checked')


def read_source(directory, session_id, projects=None):
    validate_session_id(session_id)
    projects = normalize_projects(projects)
    rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    row = rows.get(session_id)
    path = directory / f'{session_id}.md'
    if row is None or not project_matches(row, projects) or not path.is_file() or path.is_symlink():
        raise ValueError('Inspection needs an indexed, in-scope regular transcript file.')
    raw = path.read_bytes()
    identity = source_identity(row, hashlib.sha256(raw).hexdigest())
    return identity, conversation_sections(raw.decode('utf-8'))


def _shared_order(sequence, common):
    remaining = common.copy()
    result = []
    for digest in sequence:
        if remaining[digest] > 0:
            result.append(digest)
            remaining[digest] -= 1
    return result


def inspection_report(directory, notes, *, projects=None, session_id=None, changed_only=False):
    """Read current exports without recording that the operator inspected them."""
    projects = normalize_projects(projects)
    if changed_only and session_id is None:
        raise ValueError('Changed-only inspection needs an explicit session id.')
    if not (directory / 'sessions.json').is_file():
        raise ValueError('Inspection needs an existing archive index.')
    rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    digests = {}
    for sid, row in rows.items():
        if not project_matches(row, projects):
            continue
        path = directory / f'{sid}.md'
        if path.is_file() and not path.is_symlink():
            digests[sid] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = inspection_summary(rows, digests, notes, projects)
    report.update(scope=scope_summary(rows, projects), read_only=True,
                  boundary='Current indexed exports only. Notes do not establish understanding or resolve review candidates.')
    if session_id is not None:
        identity, sections = read_source(directory, session_id, projects)
        if identity['source_sha256'] != digests.get(session_id) or source_identity(rows[session_id], identity['source_sha256']) != identity:
            raise ValueError('The source changed during inspection. Retry with settled exports.')
        prior = next((note for note in notes if note['session_id'] == session_id), None)
        prior_hashes = prior['sections'] if prior else []
        current_hashes = [section_hash(role, body) for role, body in sections]
        common = Counter(prior_hashes) & Counter(current_hashes)
        order_differs = bool(prior) and _shared_order(prior_hashes, common) != _shared_order(current_hashes, common)
        repeated = {digest for sequence in (prior_hashes, current_hashes)
                    for digest, count in Counter(sequence).items() if count > 1}
        order_ambiguous = order_differs and bool(repeated & common.keys())
        order_changed = order_differs and not order_ambiguous
        metadata_changed = [key for key in ('agent', 'cwd', 'project_slug') if prior and prior[key] != identity[key]]
        remaining = Counter(prior_hashes)
        excerpts = []
        new_sections = 0
        for number, (role, body) in enumerate(sections, 1):
            digest = section_hash(role, body)
            unchanged = remaining[digest] > 0
            if unchanged:
                remaining[digest] -= 1
            else:
                new_sections += 1
            if not changed_only or not unchanged:
                excerpts.append(dict(section=number, role=role, text=body, section_sha256=digest,
                                     unchanged_since_note=unchanged))
        removed = sum(remaining.values())
        full_view_reasons = []
        if removed:
            full_view_reasons.append('prior_sections_no_longer_match')
        if order_changed:
            full_view_reasons.append('surviving_section_order_changed')
        if order_ambiguous:
            full_view_reasons.append('duplicate_section_order_ambiguous')
        if metadata_changed:
            full_view_reasons.append('source_metadata_changed')
        if prior and prior['source_sha256'] != identity['source_sha256'] and new_sections == 0:
            full_view_reasons.append('source_changed_without_added_dialogue')
        report['selected_source'] = dict(identity, inspection_id=inspection_id(identity), sections=excerpts,
                                        changed_only=changed_only, removed_sections=sum(remaining.values()),
                                        prior_text_available=False,
                                        changes=dict(new_or_changed_sections=new_sections, removed_sections=removed,
                                                     surviving_section_order_changed=order_changed,
                                                     section_order_ambiguous=order_ambiguous,
                                                     metadata_fields_changed=metadata_changed,
                                                     full_view_recommended=changed_only and bool(full_view_reasons),
                                                     full_view_reasons=full_view_reasons,
                                                     correctness_or_relevance_established=False))
    return report


def render_inspection(report):
    lines = [f"Source inspection notes: {report['noted']} current, {report['pending']} pending.",
             'Independent of handoff readiness. Opening this view records no inspection note.',
             report['boundary']]
    for source in report['sources']:
        if source['status'] != 'note_current':
            lines.append(f"{source['session_id']} / {source['agent']}: {source['status']}")
    selected = report.get('selected_source')
    if selected:
        lines.extend(['', f"Inspection snapshot: {selected['inspection_id']}",
                      f"Removed dialogue sections since note: {selected['removed_sections']}. Prior text is not stored here."])
        if selected['changed_only']:
            lines.append('Changed sections only. Unchanged surrounding dialogue is omitted.')
        changes = selected['changes']
        if changes['surviving_section_order_changed']:
            lines.append('Surviving dialogue sections changed order. A hash match does not establish equivalent meaning.')
        if changes['section_order_ambiguous']:
            lines.append('Repeated sections make the change in dialogue order ambiguous.')
        if changes['metadata_fields_changed']:
            lines.append('Metadata changed: ' + ', '.join(changes['metadata_fields_changed']))
        if changes['full_view_recommended']:
            lines.append('Full view recommended: ' + ', '.join(changes['full_view_reasons']) + '.')
        for section in selected['sections']:
            lines.extend(['', f"Section {section['section']} / {section['role']} (source claim, not checked)", section['text']])
    return '\n'.join(lines) + '\n'
