"""Resolve complete-section anchors and locate explicit quoted challenges.

Exact text and speaker matches can relocate evidence. Substrings, recency,
similarity scores, and claimed authority never choose a replacement.
"""

from __future__ import annotations

import hashlib
import json

from agent_sessions.analysis.claims import section_evidence
from agent_sessions.analysis.relations import find_relations
from agent_sessions.analysis.scope import normalize_projects, project_matches
from agent_sessions.analysis.transcript import conversation_sections, export_boundary_variant
from agent_sessions.renderers.json_index import JsonIndexRenderer


def section_hash(role, text):
    return hashlib.sha256(json.dumps([role, text], ensure_ascii=False).encode()).hexdigest()


def paragraph_spans(text):
    """Return complete nonempty paragraphs with original cleaned line ranges."""
    spans = []
    start = None
    lines = text.splitlines()
    for number in range(len(lines) + 1):
        if number < len(lines) and lines[number].strip():
            if start is None:
                start = number
        elif start is not None:
            body = '\n'.join(lines[start:number])
            spans.append(dict(start_line=start + 1, end_line=number, text=body,
                              sha256=hashlib.sha256(body.encode()).hexdigest()))
            start = None
    return spans


def matches_anchor_section(anchor, role, text, *, allow_boundary=True):
    """Match exact content, allowing a declared raw export framing change."""
    if role != anchor.get('role'):
        return False
    expected = anchor.get('section_sha256')
    if section_hash(role, text) == expected:
        return True
    if allow_boundary and anchor.get('view') == 'evidence':
        alternate = export_boundary_variant(text)
        return alternate is not None and section_hash(role, alternate) == expected
    return False


def resolve_anchor(anchor, digest, sections):
    item = dict(anchor, status='pending_selection', observed_source_sha256=digest)
    index = anchor['section'] - 1
    if not anchor.get('section_sha256'):
        if anchor.get('source_sha256') and anchor['source_sha256'] != digest:
            return dict(item, status='source_changed')
        if index >= len(sections):
            return dict(item, status='section_missing')
        if anchor['quote'] not in sections[index][1]:
            return dict(item, status='quote_mismatch')
        return item
    original_digest = anchor.get('source_sha256')
    matches = [i for i, (role, text) in enumerate(sections)
               if matches_anchor_section(anchor, role, text, allow_boundary=digest != original_digest)]
    if digest == original_digest and index in matches:
        resolved = index
    elif not matches:
        return dict(item, status='evidence_changed')
    elif len(matches) != 1:
        return dict(item, status='anchor_ambiguous', candidate_sections=[i + 1 for i in matches])
    else:
        resolved = matches[0]
    if anchor['quote'] not in sections[resolved][1]:
        return dict(item, status='quote_mismatch')
    update = ('unchanged' if digest == original_digest else
              'relocated' if resolved != index else 'unrelated_changes')
    if section_hash(*sections[resolved]) != anchor['section_sha256']:
        if update == 'unrelated_changes':
            update = 'export_boundary_changed'
        item['export_boundary_adjustment'] = 'separator_newline'
    return dict(item, section=resolved + 1, pinned_section=anchor['section'], source_update=update)


def scan_relationships(directory, projects=None):
    """Read all indexed, cleaned dialogue, including sources outside a query.

    This is a bounded English pattern scan, not semantic conflict detection.
    Missing files remain explicit: absence cannot certify no challenges exist.
    """
    sections = []
    projects = normalize_projects(projects)
    warnings = []
    digests = {}
    for sid, row in JsonIndexRenderer.read_entries(directory / 'sessions.json').items():
        if not project_matches(row, projects):
            continue
        path = directory / f'{sid}.md'
        if not path.is_file() or path.is_symlink():
            warnings.append(dict(code='relationship_source_missing', session_id=sid))
            continue
        raw = path.read_bytes()
        digests[sid] = hashlib.sha256(raw).hexdigest()
        for number, (role, text) in enumerate(conversation_sections(raw.decode('utf-8')), 1):
            sections.append((section_evidence(path, number, role, row['agent']), text))
    relations = find_relations(sections)
    for relation in relations:
        # Exclude paths and changing section offsets from the review identity.
        witness = relation['witness']
        key = [relation['kind'], witness['agent'], witness['session_id'], witness['role'], witness['quote'],
               relation['original'], relation['replacement'], relation['status'],
               sorted((source['agent'], source['session_id'], source['role'], source['quote'])
                      for source in relation['original_sources'] + relation['replacement_sources'])]
        relation['review_id'] = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:20]
    return relations, warnings, digests


def challenges_for(text, relations):
    return [relation for relation in relations if relation['original'] in text or (
        relation['kind'] == 'reported_conflict' and relation['replacement'] in text)]
