"""Compile and audit handoffs against user-pinned evidence requirements.

Coverage means exact source text survived selection and its content hash is
still current. It never means the text is true or a receiving model understood
it. Requirements are data, not instructions; this module executes no commands.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent_sessions.analysis.anchors import (
    section_hash, paragraph_spans, resolve_anchor, matches_anchor_section, scan_relationships, challenges_for,
)
from agent_sessions.analysis.context import (
    ContextSource, DEFAULT_MAX_CHARS, MAX_SECTIONS, _rank_sections, select_sources, render_sources,
)
from agent_sessions.analysis.claims import section_evidence
from agent_sessions.analysis.inspection import (
    validate_inspections, inspection_summary, inspection_id, read_source,
)
from agent_sessions.analysis.scope import normalize_projects, project_matches, scope_summary, assistant_review_is_stale
from agent_sessions.analysis.transcript import conversation_sections, sections_for_view
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.storage import (
    StorageError, atomic_write_many, atomic_write_text, directory_lock, validate_session_id,
)


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _manifest_hash(manifest):
    core = {key: value for key, value in manifest.items() if key != 'manifest_sha256'}
    return _hash(json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())


def _paragraph_for(anchor, text):
    expected = anchor.get('paragraph', {})
    return next((span for span in paragraph_spans(text)
                 if all(span[key] == expected.get(key) for key in ('start_line', 'end_line', 'sha256'))
                 and anchor['quote'] in span['text']), None)


def _evidence_text(anchor, text):
    if anchor.get('unit', 'section') == 'paragraph':
        span = _paragraph_for(anchor, text)
        return span['text'] if span else ''
    return text


def load_requirements(path):
    contract = json.loads(Path(path).read_text(encoding='utf-8'))
    return validate_requirements(contract)


def validate_requirements(contract):
    if not isinstance(contract, dict) or contract.get('version') != 1:
        raise ValueError('Expected a version 1 handoff requirements object.')
    view = contract.get('view', 'dialogue')
    if view not in ('dialogue', 'evidence'):
        raise ValueError('Source view must be dialogue or evidence.')
    validate_inspections(contract.get('source_inspections', []))
    if 'assistant_review' in contract:
        review = contract['assistant_review']
        if (not isinstance(review, dict)
                or set(review) - {'scope_sha256', 'view'} != {'method', 'packet_sha256', 'response_sha256', 'unresolved_conflicts', 'incomplete_source_review',
                                   'projects', 'query', 'index_sha256', 'source_snapshots'}
                or review.get('view', 'dialogue') != view
                or review['method'] != 'assistant_selection_import_v1'
                or not isinstance(review['query'], str) or not review['query'].strip()
                or any(type(review[key]) is not bool for key in ('unresolved_conflicts', 'incomplete_source_review'))
                or any(not isinstance(review[key], str) or len(review[key]) != 64
                       or any(c not in '0123456789abcdef' for c in review[key])
                       for key in ('packet_sha256', 'response_sha256', 'index_sha256') +
                       (('scope_sha256',) if 'scope_sha256' in review else ()))
                or not isinstance(review['projects'], list)
                or not isinstance(review['source_snapshots'], dict) or len(review['source_snapshots']) > 10_000):
            raise ValueError('Invalid assistant review provenance or review gate flags.')
        normalize_projects(review['projects'])
        for sid, digest in review['source_snapshots'].items():
            validate_session_id(sid)
            if (not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
                raise ValueError('Invalid assistant source review snapshot.')
    requirements = contract.get('requirements')
    if not isinstance(requirements, list) or not requirements or len(requirements) > 100:
        raise ValueError('Requirements must contain between 1 and 100 evidence anchors.')
    seen = set()
    for anchor in requirements:
        if not isinstance(anchor, dict):
            raise ValueError('Each requirement must be an evidence anchor object.')
        if anchor.get('view', 'dialogue') != view:
            raise ValueError('Do not mix dialogue sections and raw message coordinates in one contract.')
        if view == 'evidence' and any(not anchor.get(key) for key in ('section_sha256', 'source_sha256', 'agent', 'role')):
            raise ValueError('Raw evidence anchors need complete message and source hashes, agent, and role.')
        if view == 'evidence' and anchor.get('unit', 'section') != 'section':
            raise ValueError('Raw evidence pins retain complete messages; paragraph pins are unsupported.')
        identifier = anchor.get('id')
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('Each requirement needs a unique nonempty id.')
        seen.add(identifier)
        reviews = anchor.get('reviewed_candidates', [])
        if not isinstance(reviews, list) or len(reviews) > 100:
            raise ValueError('Reviewed candidates must be a list with at most 100 entries.')
        review_ids = set()
        for review in reviews:
            if (not isinstance(review, dict) or not isinstance(review.get('id'), str)
                    or len(review['id']) != 20 or any(c not in '0123456789abcdef' for c in review['id'])
                    or review['id'] in review_ids or not isinstance(review.get('note'), str)
                    or not review['note'].strip()):
                raise ValueError('Each reviewed candidate needs a unique review id and nonempty note.')
            review_ids.add(review['id'])
        validate_session_id(anchor.get('session_id'))
        if anchor.get('agent') is not None and anchor['agent'] not in ('claude', 'codex', 'cursor'):
            raise ValueError('Requirement agent must be claude, codex, or cursor.')
        if type(anchor.get('section')) is not int or anchor['section'] < 1:
            raise ValueError('Each requirement needs a positive cleaned conversation section number.')
        if not isinstance(anchor.get('quote'), str) or not anchor['quote'].strip():
            raise ValueError('Each requirement needs a nonempty exact source quote.')
        if anchor.get('unit', 'section') not in ('section', 'paragraph'):
            raise ValueError('Evidence unit must be section or paragraph.')
        if anchor.get('unit') == 'paragraph':
            span = anchor.get('paragraph')
            if (not isinstance(span, dict) or type(span.get('start_line')) is not int
                    or type(span.get('end_line')) is not int or span['start_line'] < 1
                    or span['end_line'] < span['start_line'] or not isinstance(span.get('sha256'), str)
                    or len(span['sha256']) != 64 or not anchor.get('section_sha256')):
                raise ValueError('Paragraph evidence needs a complete-section hash and a valid paragraph locator.')
        section_digest = anchor.get('section_sha256')
        if section_digest is not None:
            if (not isinstance(section_digest, str) or len(section_digest) != 64
                    or any(c not in '0123456789abcdef' for c in section_digest)
                    or anchor.get('role') not in (('User', 'Assistant', 'Tool', 'System') if view == 'evidence' else ('User', 'Assistant'))):
                raise ValueError('Complete-section anchors need a valid section hash and speaker.')
        digest = anchor.get('source_sha256')
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64
                                   or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('source_sha256 must be a lowercase SHA-256 digest.')
    by_id = {anchor['id']: anchor for anchor in requirements}
    for anchor in requirements:
        if 'challenge_for' in anchor or 'link_note' in anchor:
            target = anchor.get('challenge_for')
            if (not isinstance(target, str) or target not in by_id or target == anchor['id']
                    or 'challenge_for' in by_id[target] or not isinstance(anchor.get('link_note'), str)
                    or not anchor['link_note'].strip()):
                raise ValueError('A challenge link needs an existing ordinary requirement and a nonempty link note.')
            if any(not item.get('section_sha256') or not item.get('agent') or not item.get('role')
                   for item in (anchor, by_id[target])):
                raise ValueError('Challenge links need complete-section hashes, agents, and speakers on both anchors.')
    return contract


def _current_anchor(directory, anchor, rows, projects):
    """Resolve a complete anchor before accepting an operator link or review."""
    row = rows.get(anchor['session_id'])
    path = directory / f"{anchor['session_id']}.md"
    if (row is None or not project_matches(row, projects)
            or (anchor.get('agent') and row['agent'] != anchor['agent'])
            or not path.is_file() or path.is_symlink()):
        raise ValueError('Linked evidence must be indexed, in scope, and have its original agent identity.')
    raw = path.read_bytes()
    sections = sections_for_view(raw.decode('utf-8'), anchor.get('view', 'dialogue'))
    resolved = resolve_anchor(anchor, _hash(raw), sections)
    if (resolved['status'] != 'pending_selection'
            or not _evidence_text(resolved, sections[resolved['section'] - 1][1])):
        raise ValueError('Linked evidence changed or is ambiguous. Inspect it before linking or reviewing.')
    return resolved, sections


def _operator_candidates(directory, requirements, sections_by_id):
    """Construct inspectable operator claims without interpreting their meaning."""
    by_id = {item['id']: item for item in requirements}
    candidates = {}
    for challenge in requirements:
        target = by_id.get(challenge.get('challenge_for'))
        if target is None:
            continue
        evidence = []
        for item in (target, challenge):
            sections = sections_by_id.get(item['session_id'], [])
            number = item['section'] - 1
            if (number >= len(sections) or not matches_anchor_section(item, *sections[number])):
                break
            body = _evidence_text(item, sections[number][1])
            if not body:
                break
            evidence.append(dict(section_evidence(directory / f"{item['session_id']}.md",
                                                  number + 1, item['role'], item['agent']), quote=body))
        if len(evidence) != 2:
            continue
        # Section offsets and whole-file hashes change on unrelated appends.
        fields = ('id', 'session_id', 'agent', 'role', 'section_sha256', 'unit', 'paragraph', 'quote')
        identity = [{key: item.get(key) for key in fields} for item in (target, challenge)]
        review_id = _hash(json.dumps([identity, challenge['link_note']], sort_keys=True,
                                     ensure_ascii=False).encode())[:20]
        candidate = dict(kind='operator_linked_challenge', method='operator_anchor_link_v1',
                         status='linked', verification='not_checked', review_id=review_id,
                         original=target['quote'], replacement=challenge['quote'], witness=evidence[1],
                         original_sources=[evidence[0]], replacement_sources=[evidence[1]],
                         challenge_requirement_id=challenge['id'], link_note=challenge['link_note'])
        candidates.setdefault(target['id'], []).append(candidate)
    return candidates


def link_challenge(directory, output, identifier, target_id, session_id, section, quote, note,
                   *, unit='section', projects=None):
    """Pin an operator-selected challenge as mandatory evidence, pending review."""
    if any(not isinstance(value, str) or not value.strip() for value in (target_id, quote, note)):
        raise ValueError('An explicit challenge link needs a target id, exact quote, and nonempty note.')
    return pin_requirement(directory, output, identifier, session_id, section, quote, unit=unit,
                           projects=projects, challenge_for=target_id, link_note=note)


def note_source_inspection(directory, output, session_id, snapshot, note, *, projects=None):
    """Record an operator's inspection note against exact source bytes and metadata."""
    if not isinstance(note, str) or not note.strip() or len(note) > 10_000:
        raise ValueError('An inspection needs a nonempty note of at most 10000 characters.')
    with directory_lock(output.parent):
        contract = load_requirements(output)
        identity, sections = read_source(directory, session_id, projects)
        if snapshot != inspection_id(identity):
            raise ValueError('The inspection snapshot is stale. Inspect the current source before recording a note.')
        notes = contract.setdefault('source_inspections', [])
        receipt = dict(identity, note=note.strip(), sections=[section_hash(role, text) for role, text in sections])
        existing = next((item for item in notes if item['session_id'] == session_id), None)
        if existing is not None:
            notes[notes.index(existing)] = receipt
        else:
            notes.append(receipt)
        validate_requirements(contract)
        current_identity, _ = read_source(directory, session_id, projects)
        if identity != current_identity:
            raise StorageError('The source changed while recording its inspection note. Retry with settled exports.')
        atomic_write_text(output, json.dumps(contract, indent=2, ensure_ascii=False) + '\n')
    return dict(session_id=session_id, inspection_id=snapshot, note=note.strip(),
                verification='not_checked', review_candidates_resolved=False)


def pin_requirement(directory: Path, output: Path, identifier: str, session_id: str,
                    section: int, quote=None, unit='section', projects=None,
                    challenge_for=None, link_note=None, view='dialogue'):
    """Append a user-selected anchor, pinned to its exact current export hash."""
    projects = normalize_projects(projects)
    if view == 'evidence':
        from agent_sessions.workspace import _private_root
        _private_root(Path(output).parent)
    validate_session_id(session_id)
    if not identifier.strip() or type(section) is not int or section < 1:
        raise ValueError('Pin needs a nonempty id and positive section number.')
    rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    source = directory / f'{session_id}.md'
    if session_id in rows and not project_matches(rows[session_id], projects):
        raise ValueError('The source session is outside the declared project metadata scope.')
    if session_id not in rows or not source.is_file() or source.is_symlink():
        raise ValueError('Pin needs an indexed regular transcript file.')
    if output.resolve() == source.resolve() or output.resolve().parent == directory.resolve():
        raise ValueError('Keep requirements in a separate private directory, outside the export archive.')
    raw = source.read_bytes()
    sections = sections_for_view(raw.decode('utf-8'), view)
    if section > len(sections):
        raise ValueError('That raw message does not exist.' if view == 'evidence' else
                         'That cleaned conversation section does not exist.')
    text = sections[section - 1][1]
    if view == 'evidence' and unit != 'section':
        raise ValueError('Raw evidence pins retain complete messages; paragraph pins are unsupported.')
    if unit not in ('section', 'paragraph'):
        raise ValueError('Evidence unit must be section or paragraph.')
    if unit == 'paragraph' and quote is None:
        raise ValueError('Paragraph pins need an explicit exact quote.')
    quote = text if quote is None else quote
    if not quote or quote not in text:
        raise ValueError('The exact quote must occur in the selected source unit.')
    role = sections[section - 1][0]
    anchor = dict(id=identifier, session_id=session_id, section=section, quote=quote, source_sha256=_hash(raw),
                  section_sha256=section_hash(role, text), role=role, agent=rows[session_id]['agent'],
                  anchor_method='complete_section_v1', unit=unit)
    if view == 'evidence':
        anchor.update(view='evidence', anchor_method='raw_message_v1')
    if unit == 'paragraph':
        matches = [span for span in paragraph_spans(text) if quote in span['text']]
        if len(matches) != 1:
            raise ValueError('The quote must identify exactly one complete paragraph. Use a more specific quote or section mode.')
        anchor['paragraph'] = {key: matches[0][key] for key in ('start_line', 'end_line', 'sha256')}
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with directory_lock(output.parent):
        contract = load_requirements(output) if output.exists() else dict(version=1, requirements=[])
        if not output.exists() and view == 'evidence':
            contract['view'] = 'evidence'
        if contract.get('view', 'dialogue') != view:
            raise ValueError('Do not mix dialogue sections and raw message coordinates in one contract.')
        if len(contract['requirements']) >= 100:
            raise ValueError('A contract supports at most 100 evidence anchors.')
        if any(item['id'] == identifier for item in contract['requirements']):
            raise ValueError('Requirement id already exists. Choose a different id.')
        if challenge_for is not None or link_note is not None:
            target = next((item for item in contract['requirements'] if item['id'] == challenge_for), None)
            if target is None:
                raise ValueError('The target requirement does not exist. Pin it before linking a challenge.')
            _current_anchor(directory, target, rows, projects)
            anchor.update(challenge_for=challenge_for, link_note=link_note)
        contract['requirements'].append(anchor)
        validate_requirements(contract)
        atomic_write_text(output, json.dumps(contract, indent=2, ensure_ascii=False) + '\n')
    return anchor


def review_requirement(directory: Path, output: Path, identifier: str, candidate_id: str, note: str, projects=None):
    """Record an explicit operator review, without accepting a quoted action."""
    projects = normalize_projects(projects)
    if not note.strip():
        raise ValueError('A review needs a nonempty note.')
    with directory_lock(output.parent):
        contract = load_requirements(output)
        anchor = next((item for item in contract['requirements'] if item['id'] == identifier), None)
        if anchor is None:
            raise ValueError('Requirement id was not found.')
        rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
        row = rows.get(anchor['session_id'])
        if row is not None and not project_matches(row, projects):
            raise ValueError('The requirement session is outside the declared project metadata scope.')
        if row is None or (anchor.get('agent') and anchor['agent'] != row['agent']):
            raise ValueError('The requirement source identity changed. Inspect it before recording a review.')
        path = directory / f"{anchor['session_id']}.md"
        if not path.is_file() or path.is_symlink():
            raise ValueError('Requirement source is missing.')
        raw = path.read_bytes()
        sections = sections_for_view(raw.decode('utf-8'), anchor.get('view', 'dialogue'))
        resolved = resolve_anchor(anchor, _hash(raw), sections)
        if resolved['status'] != 'pending_selection':
            raise ValueError('Requirement evidence changed or is ambiguous. Inspect it before recording a review.')
        relations, warnings, _ = scan_relationships(directory, projects=projects)
        if warnings:
            raise ValueError('The relationship scan is incomplete. Restore missing exports before recording a review.')
        candidates = challenges_for(_evidence_text(resolved, sections[resolved['section'] - 1][1]), relations)
        linked = [item for item in contract['requirements'] if item.get('challenge_for') == identifier]
        linked_requirements = [resolved]
        linked_sections = {anchor['session_id']: sections}
        for challenge in linked:
            current, evidence = _current_anchor(directory, challenge, rows, projects)
            linked_requirements.append(current)
            linked_sections[challenge['session_id']] = evidence
        candidates += _operator_candidates(directory, linked_requirements, linked_sections).get(identifier, [])
        if not any(item['review_id'] == candidate_id for item in candidates):
            raise ValueError('That review candidate does not currently affect this requirement.')
        reviews = anchor.setdefault('reviewed_candidates', [])
        if any(item['id'] == candidate_id for item in reviews):
            raise ValueError('Candidate already has a review note.')
        if len(reviews) >= 100:
            raise ValueError('A requirement supports at most 100 review notes.')
        reviews.append(dict(id=candidate_id, note=note.strip()))
        atomic_write_text(output, json.dumps(contract, indent=2, ensure_ascii=False) + '\n')
    return dict(requirement_id=identifier, candidate_id=candidate_id, note=note.strip(), verification='not_checked')


def compile_handoff(directory: Path, query: str, requirements_path: Path, *,
                    last=5, max_chars=DEFAULT_MAX_CHARS, max_total_chars=64_000, projects=None):
    """Give pinned evidence priority, retaining full sections within hard limits.

    Requirements can pin a section that does not repeat the search query.
    Budget/source-limit failures are explicit and yield an inspectable draft,
    never a ready pack. Selection does not decide which statements are true.
    """
    requested_projects = projects
    projects = normalize_projects(projects)
    if type(max_total_chars) is not int or max_total_chars < 1:
        raise ValueError('Total handoff character budget must be a positive integer.')
    contract = load_requirements(requirements_path)
    view = contract.get('view', 'dialogue')
    if requested_projects is None and contract.get('assistant_review'):
        projects = normalize_projects(contract['assistant_review']['projects'])
    index_snapshot = (directory / 'sessions.json').read_bytes()
    rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    sources = select_sources(directory, query, last, max_chars, projects=projects, view=view)
    scope_info = scope_summary(rows, projects)
    by_id = {s.metadata['id']: s for s in sources}
    requirements = []
    pinned = {}
    snapshots = {}
    relations, scan_warnings, scan_digests = scan_relationships(directory, projects=projects)
    inspections = inspection_summary(rows, scan_digests, contract.get('source_inspections', []), projects)
    for anchor in contract['requirements']:
        item = dict(anchor, status='source_missing')
        requirements.append(item)
        sid = anchor['session_id']
        path = directory / f'{sid}.md'
        if sid in rows and not project_matches(rows[sid], projects):
            item['status'] = 'outside_project_scope'
            continue
        if sid not in rows or not path.is_file() or path.is_symlink():
            continue
        if anchor.get('agent') is not None and anchor['agent'] != rows[sid]['agent']:
            item['status'] = 'source_agent_changed'
            continue
        if sid not in snapshots:
            raw = path.read_bytes()
            snapshots[sid] = (_hash(raw), sections_for_view(raw.decode('utf-8'), view))
        digest, sections = snapshots[sid]
        resolved = resolve_anchor(anchor, digest, sections)
        item.clear()
        item.update(resolved)
        if item['status'] != 'pending_selection':
            continue
        index = item['section'] - 1
        if item.get('unit') == 'paragraph' and _paragraph_for(item, sections[index][1]) is None:
            item['status'] = 'paragraph_changed'
            continue
        pinned.setdefault(sid, set()).add(index)
        if sid not in by_id:
            by_id[sid] = ContextSource(rows[sid], path, sections,
                                      _rank_sections(sections, query.casefold()), {}, digest)
        else:
            # Reuse the same source snapshot for requirements and rendering.
            by_id[sid].source_sha256 = digest
            by_id[sid].sections = sections
            by_id[sid].ranked = _rank_sections(sections, query.casefold())

    operator_candidates = _operator_candidates(directory, requirements,
                                               {sid: snapshot[1] for sid, snapshot in snapshots.items()})
    for item in requirements:
        if item['status'] != 'pending_selection':
            continue
        sections = snapshots[item['session_id']][1]
        item['review_candidates'] = challenges_for(_evidence_text(item, sections[item['section'] - 1][1]), relations)
        item['review_candidates'] += operator_candidates.get(item['id'], [])
        reviewed = {review['id'] for review in item.get('reviewed_candidates', [])}
        item['unreviewed_candidates'] = [candidate for candidate in item['review_candidates']
                                         if candidate['review_id'] not in reviewed]

    ordered = [by_id[sid] for sid in pinned]
    ordered.extend(source for source in sources if source.metadata['id'] not in pinned)
    selected = ordered[:last]
    for source in selected:
        mandatory = pinned.get(source.metadata['id'], set())
        if not mandatory:
            continue
        source.selected = {}
        source.spans = {}
        remaining = max_chars
        # Never partially include a required section and call its anchor kept.
        for i in sorted(mandatory):
            source.ranked[i] = (100, 'required evidence anchor; statement not verified')
            text = source.sections[i][1]
            anchors = [item for item in requirements if item['session_id'] == source.metadata['id']
                       and item.get('section') == i + 1 and item['status'] == 'pending_selection']
            spans = []
            if anchors and all(item.get('unit') == 'paragraph' for item in anchors):
                unique = {item['paragraph']['start_line']: _paragraph_for(item, text) for item in anchors}
                spans = [unique[key] for key in sorted(unique)]
                text = '\n\n'.join(span['text'] for span in spans)
            # The ranked-context count cap must not exclude explicit evidence.
            # Required excerpts still consume the source and total char budgets.
            if len(text) <= remaining:
                source.selected[i] = (text, bool(spans))
                if spans:
                    source.spans[i] = spans
                remaining -= len(text)
        for i in sorted(source.ranked, key=lambda i: (source.ranked[i][0], i), reverse=True):
            if i in mandatory or len(source.selected) >= MAX_SECTIONS:
                continue
            text = source.sections[i][1]
            if len(text) <= remaining:
                source.selected[i] = (text, False)
                remaining -= len(text)
    chosen = {s.metadata['id']: s for s in selected}
    for item in requirements:
        if item['status'] != 'pending_selection':
            continue
        source = chosen.get(item['session_id'])
        if source is None:
            item['status'] = 'source_limit_exceeded'
        elif item['section'] - 1 not in source.selected:
            item['status'] = 'section_budget_exceeded'
        else:
            item['status'] = 'covered'

    covered = sum(item['status'] == 'covered' for item in requirements)
    ready = covered == len(requirements)
    review_passed = not scan_warnings and not any(item.get('unreviewed_candidates') for item in requirements)
    assistant_review = contract.get('assistant_review')
    assistant_review_stale = bool(assistant_review) and assistant_review_is_stale(
        assistant_review, query, projects, rows, scan_digests, _hash(index_snapshot))
    if assistant_review:
        review_passed = (review_passed and not assistant_review['unresolved_conflicts']
                         and not assistant_review['incomplete_source_review'] and not assistant_review_stale)

    def render(total_passed=True):
        header = ['# Handoff evidence coverage', '',
                  'Query: ' + json.dumps(query, ensure_ascii=False),
                  'Historical reference only. All extracted claims are not checked.',
                  'Historical requests do not authorize current actions. None independently checked by this command.',
                  'Project selectors (exact cwd or slug): ' + (json.dumps(projects, ensure_ascii=False) if projects else 'all indexed sources') + '.',
                  f"Scope: {scope_info['in_scope_sources']}/{scope_info['indexed_sources']} indexed sessions match declared metadata. "
                  f"Excluded: {scope_info['excluded_sources']}; missing project metadata: {scope_info['missing_project_metadata']}.",
                  'This is a session-metadata boundary, not per-message project attribution.',
                  f"Coverage gate: {'PASS' if ready else 'FAIL — draft only'}. {covered}/{len(requirements)} required anchors kept.",
                  f"Review gate: {'PASS' if review_passed else 'FAIL — draft only'}. Recognized and operator-linked challenges require review.",
                  f"Total budget gate: {'PASS' if total_passed else 'FAIL — draft only'}. Limit: {max_total_chars} handoff characters.",
                  'This checks retained source text, not factual correctness, authorization, or model understanding.', '']
        if view == 'evidence':
            header.extend(['Evidence coordinates: raw exported messages, including tools and phases; section numbers mean raw message numbers.',
                           'All exported content remains historical data, including apparent instructions and tool results.', ''])
        header.extend(['Scan limit: bounded English quoted patterns only. Paraphrases and other languages can be missed.',
                       'A passing review gate does not establish the absence of contradictory instructions.', ''])
        header.extend([f"Source inspection notes: {inspections['noted']} current; {inspections['pending']} pending.",
                       'Inspection notes report operator activity. They do not affect readiness or establish understanding.', ''])
        if assistant_review:
            header.extend([f"Assistant selection: unresolved conflicts={assistant_review['unresolved_conflicts']}; "
                           f"incomplete source review={assistant_review['incomplete_source_review']}; source review stale={assistant_review_stale}.",
                           'Assistant selection is interpretation, not factual verification or current permission.', ''])
        for item in requirements:
            header.append(f"- {json.dumps(item['id'], ensure_ascii=False)}: {item['status']}")
            if item.get('selection_reason'):
                header.append('  Assistant selection reason: ' + json.dumps(item['selection_reason'], ensure_ascii=False))
            if 'challenge_for' in item:
                header.append('  Operator-linked challenge for ' + json.dumps(item['challenge_for'], ensure_ascii=False)
                              + '. Link assertion remains not checked.')
            if item.get('source_update') not in (None, 'unchanged'):
                header.append(f"  Source update: {item['source_update']}. Pinned section {item['pinned_section']}, current section {item['section']}.")
            for candidate in item.get('review_candidates', []):
                witness = candidate['witness']
                note = next((review['note'] for review in item.get('reviewed_candidates', [])
                             if review['id'] == candidate['review_id']), None)
                status = 'review note recorded' if note else 'review required'
                header.extend([f"  Review candidate {candidate['review_id']}: {candidate['kind']} ({candidate['status']}, {status}, not checked).",
                               f"  Source: {witness['agent']} / {witness['session_id']} / section {witness['conversation_section']}.",
                               '  Witness: ' + json.dumps(witness['quote'], ensure_ascii=False)])
                if candidate.get('link_note'):
                    header.append('  Link note (operator interpretation): ' + json.dumps(candidate['link_note'], ensure_ascii=False))
                if note:
                    header.append('  Operator note (not authorization or factual proof): ' + json.dumps(note, ensure_ascii=False))
        for warning in scan_warnings:
            header.append('Archive scan warning: ' + json.dumps(warning))
        header.extend(['', '## Evidence excerpts', '',
                       'Section numbers count cleaned conversation sections. Local order does not establish authority across agents.', ''])
        return '\n'.join(header + render_sources(selected, heading_level=3)) + '\n'

    text = render()
    while len(text) > max_total_chars:
        optional = [(source.ranked[i][0], -len(source.selected[i][0]), source.metadata['id'], i, source)
                    for source in selected for i in source.selected
                    if i not in pinned.get(source.metadata['id'], set())]
        if not optional:
            break
        _, _, _, index, source = min(optional, key=lambda item: item[:4])
        del source.selected[index]
        if not source.selected and source.metadata['id'] not in pinned:
            selected.remove(source)
        text = render()
    total_passed = len(text) <= max_total_chars
    if not total_passed:
        text = render(total_passed=False)
    bundle_ready = ready and review_passed and total_passed
    excerpt_chars = sum(len(excerpt) for source in selected for excerpt, _ in source.selected.values())
    manifest = dict(version=2, query=query, scope=scope_info, requirements=requirements, coverage_passed=ready,
                    rendering='evidence_excerpts_v1',
                    size_breakdown=dict(selected_excerpt_chars=excerpt_chars,
                                        framing_review_and_citation_chars=len(text) - excerpt_chars),
                    source_inspection=inspections,
                    review_passed=review_passed, total_budget_passed=total_passed, handoff_chars=len(text),
                    ready=bundle_ready, relationship_scan_warnings=scan_warnings,
                    verification='not_checked', handoff_sha256=_hash(text.encode('utf-8')),
                    limits=dict(sources=last,
                                sections_per_source=max([MAX_SECTIONS] + [len(pinned.get(s.metadata['id'], set())) for s in selected]),
                                chars_per_source=max_chars,
                                total_handoff_chars=max_total_chars),
                    sources=[dict(session_id=s.metadata['id'], agent=s.metadata['agent'],
                                  source_sha256=s.source_sha256,
                                  selected_sections=[i + 1 for i in sorted(s.selected)],
                                  selected_evidence=[dict(section=i + 1, role=s.sections[i][0],
                                                         section_sha256=section_hash(*s.sections[i]),
                                                         unit='paragraph' if s.spans.get(i) else 'section',
                                                         paragraphs=[{key: span[key] for key in ('start_line', 'end_line', 'sha256')}
                                                                     for span in s.spans.get(i, [])])
                                                     for i in sorted(s.selected)]) for s in selected])
    if ((directory / 'sessions.json').read_bytes() != index_snapshot
            or any(_hash(source.path.read_bytes()) != source.source_sha256 for source in selected)
            or any(_hash((directory / f'{sid}.md').read_bytes()) != digest
                   for sid, digest in scan_digests.items())):
        raise StorageError('A source changed during handoff compilation. Retry with settled exports.')
    if view == 'evidence':
        manifest['view'] = view
    if assistant_review:
        manifest['assistant_review'] = assistant_review
        manifest['assistant_review_stale'] = assistant_review_stale
    manifest['manifest_sha256'] = _manifest_hash(manifest)
    return text, manifest


def write_bundle(output: Path, text: str, manifest: dict):
    if manifest.get('view') == 'evidence':
        from agent_sessions.workspace import _private_root
        output = _private_root(output)
    if manifest.get('manifest_sha256') != _manifest_hash(manifest) or manifest.get('handoff_sha256') != _hash(text.encode()):
        raise ValueError('Bundle content does not match its manifest identity.')
    if (output / 'sessions.json').exists():
        raise ValueError('Choose a separate private bundle directory, outside the export archive.')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write_many({output / 'handoff.md': text,
                       output / 'manifest.json': json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'})


def read_bundle_snapshot(bundle: Path):
    """Read historical bytes with identity checks, without asserting freshness."""
    if bundle.is_symlink() or (bundle / 'manifest.json').is_symlink() or (bundle / 'handoff.md').is_symlink():
        raise StorageError('Historical bundle paths must not be symlinks.')
    raw = (bundle / 'handoff.md').read_bytes()
    text = raw.decode('utf-8')
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if (not isinstance(manifest, dict) or manifest.get('version') != 2
            or manifest.get('manifest_sha256') != _manifest_hash(manifest)
            or manifest.get('handoff_sha256') != _hash(raw)):
        raise StorageError('Historical bundle identity does not match its content. Restore the snapshot before using it.')
    return text, manifest


def audit_bundle(bundle: Path, directory: Path):
    """Read-only source and bundle integrity audit; never runs a quoted action."""
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or manifest.get('version') != 2:
        raise ValueError('Unsupported handoff manifest.')
    view = manifest.get('view', 'dialogue')
    if view not in ('dialogue', 'evidence'):
        raise ValueError('Source view must be dialogue or evidence.')
    scope = manifest.get('scope', {})
    if not isinstance(scope, dict):
        raise ValueError('Invalid project scope in the handoff manifest.')
    if scope and scope.get('method') != 'exact_session_metadata_v1':
        raise ValueError('Unsupported project metadata scope method.')
    projects = normalize_projects(scope.get('projects'))
    text = (bundle / 'handoff.md').read_bytes()
    findings = []
    notes = []
    if manifest.get('manifest_sha256') != _manifest_hash(manifest):
        findings.append(dict(code='manifest_changed'))
    if _hash(text) != manifest.get('handoff_sha256'):
        findings.append(dict(code='handoff_changed'))
    if any(finding['code'] == 'manifest_changed' for finding in findings):
        return dict(version=1, read_only=True, coverage_passed=False, verification='not_checked',
                    findings=findings, notes=notes, exit_code=1)
    if manifest.get('coverage_passed') is not True:
        findings.append(dict(code='requirements_not_covered'))
    if manifest.get('review_passed') is False:
        findings.append(dict(code='relationship_review_required'))
    if manifest.get('assistant_review'):
        review = manifest['assistant_review']
        if review.get('unresolved_conflicts'):
            findings.append(dict(code='assistant_conflicts_unresolved'))
        if review.get('incomplete_source_review'):
            findings.append(dict(code='assistant_source_review_incomplete'))
    if manifest.get('total_budget_passed') is False:
        findings.append(dict(code='total_budget_exceeded'))
    sources = manifest.get('sources')
    requirements = manifest.get('requirements')
    if not isinstance(sources, list) or not isinstance(requirements, list) or not requirements:
        raise ValueError('Manifest must contain source snapshots and requirements.')
    validation_contract = dict(version=1, requirements=requirements, view=view)
    if 'assistant_review' in manifest:
        validation_contract['assistant_review'] = manifest['assistant_review']
    validate_requirements(validation_contract)
    current = {}
    current_hashes = {}
    current_rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    if not (directory / 'sessions.json').is_file():
        findings.append(dict(code='archive_index_missing'))
    seen_sources = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError('Invalid source snapshot.')
        sid = source.get('session_id')
        validate_session_id(sid)
        if sid in seen_sources:
            raise ValueError('Duplicate source snapshot.')
        seen_sources.add(sid)
        if sid in current_rows and not project_matches(current_rows[sid], projects):
            findings.append(dict(code='source_outside_project_scope', session_id=sid))
            continue
        if sid not in current_rows:
            findings.append(dict(code='source_not_indexed', session_id=sid))
        elif source.get('agent') != current_rows[sid]['agent']:
            findings.append(dict(code='source_agent_changed', session_id=sid))
        selected_sections = source.get('selected_sections')
        if (not isinstance(selected_sections, list)
                or any(type(number) is not int or number < 1 for number in selected_sections)):
            raise ValueError('Invalid selected section numbers.')
        selected_evidence = source.get('selected_evidence')
        if not isinstance(selected_evidence, list):
            raise ValueError('Invalid selected evidence snapshots.')
        for selected in selected_evidence:
            if (not isinstance(selected, dict) or type(selected.get('section')) is not int
                    or selected['section'] not in selected_sections
                    or selected.get('role') not in (('User', 'Assistant', 'Tool', 'System') if view == 'evidence' else ('User', 'Assistant'))
                    or not isinstance(selected.get('section_sha256'), str)):
                raise ValueError('Invalid selected evidence snapshot.')
        path = directory / f'{sid}.md'
        if not path.is_file() or path.is_symlink():
            findings.append(dict(code='source_missing', session_id=sid))
            continue
        raw = path.read_bytes()
        current[sid] = sections_for_view(raw.decode('utf-8'), view)
        current_hashes[sid] = _hash(raw)
        if _hash(raw) != source.get('source_sha256'):
            evidence = source.get('selected_evidence')
            unchanged = isinstance(evidence, list) and bool(evidence)
            for selected in evidence or []:
                if not isinstance(selected, dict) or type(selected.get('section')) is not int:
                    raise ValueError('Invalid selected evidence snapshot.')
                index = selected['section'] - 1
                if (index < 0 or index >= len(current[sid])
                        or section_hash(*current[sid][index]) != selected.get('section_sha256')
                        or current[sid][index][0] != selected.get('role')):
                    unchanged = False
            if unchanged:
                notes.append(dict(code='source_changed_selected_evidence_unchanged', session_id=sid))
            else:
                findings.append(dict(code='source_changed', session_id=sid))
    snapshots = {source['session_id']: source for source in sources}
    for item in requirements:
        if not isinstance(item, dict):
            raise ValueError('Invalid requirement snapshot.')
        sid = item.get('session_id')
        validate_session_id(sid)
        section = item.get('section')
        quote = item.get('quote')
        if type(section) is not int or section < 1 or not isinstance(quote, str) or not quote:
            raise ValueError('Invalid requirement anchor.')
        sections = current.get(sid, [])
        kept = snapshots.get(sid, {}).get('selected_sections', [])
        resolved = resolve_anchor(item, current_hashes[sid], sections) if sid in current_hashes else dict(status='source_missing')
        if (resolved['status'] != 'pending_selection' or resolved.get('section') != section
                or item.get('status') != 'covered' or section not in kept or section > len(sections)
                or quote not in sections[section - 1][1] or quote not in text.decode('utf-8')):
            findings.append(dict(code='required_anchor_not_current', requirement_id=item.get('id'),
                                 anchor_status=resolved['status']))
    relations, scan_warnings, current_digests = scan_relationships(directory, projects=projects)
    findings.extend(scan_warnings)
    if manifest.get('assistant_review'):
        review = manifest['assistant_review']
        if assistant_review_is_stale(review, manifest['query'], projects, current_rows, current_digests,
                                     _hash((directory / 'sessions.json').read_bytes())):
            findings.append(dict(code='assistant_review_stale'))
    captured_inspections = manifest.get('source_inspection')
    if captured_inspections is not None:
        captured = {item['session_id']: item['inspection_id'] for item in captured_inspections['sources']}
        observed = {sid: inspection_id(dict(session_id=sid, agent=row['agent'], cwd=row.get('cwd', ''),
                                           project_slug=row.get('project_slug', ''), source_sha256=current_digests[sid]))
                    if sid in current_digests else None
                    for sid, row in current_rows.items() if project_matches(row, projects)}
        if captured != observed:
            notes.append(dict(code='inspection_queue_snapshot_changed',
                              detail='Captured inspection counts are historical. Run topic inspect for the current queue.'))
    current_relation_ids = {candidate['review_id'] for candidate in relations}
    operator_candidates = _operator_candidates(directory, requirements, current)
    current_relation_ids.update(candidate['review_id'] for candidates in operator_candidates.values() for candidate in candidates)
    for item in requirements:
        for prior in item.get('review_candidates', []):
            if prior.get('review_id') not in current_relation_ids:
                findings.append(dict(code='review_evidence_missing_or_changed', requirement_id=item['id'],
                                     review_id=prior.get('review_id')))
        sections = current.get(item['session_id'], [])
        if item['section'] <= len(sections):
            reviewed = {review['id'] for review in item.get('reviewed_candidates', [])}
            candidates = challenges_for(_evidence_text(item, sections[item['section'] - 1][1]), relations)
            candidates += operator_candidates.get(item['id'], [])
            for candidate in candidates:
                if candidate['review_id'] not in reviewed:
                    code = 'operator_link_requires_review' if candidate['kind'] == 'operator_linked_challenge' else 'quoted_change_requires_review'
                    findings.append(dict(code=code, requirement_id=item['id'],
                                         candidate=candidate))
    return dict(version=1, read_only=True, coverage_passed=not findings, verification='not_checked',
                findings=findings, notes=notes, exit_code=0 if not findings else 1)
