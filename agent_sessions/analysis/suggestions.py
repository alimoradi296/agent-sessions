"""Read-only evidence suggestions for an assistant, never accepted requirements.

Rules nominate complete paragraphs. They do not infer importance, authority,
current permission, semantic contradictions, or complete task coverage.
"""

import hashlib
import json
import re

from agent_sessions.analysis.anchors import paragraph_spans, section_hash
from agent_sessions.analysis.claims import classify, _is_request
from agent_sessions.analysis.scope import normalize_projects, project_matches, scope_summary
from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.analysis.origins import paragraph_origin_hint, METHOD as ORIGIN_METHOD
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.storage import StorageError

SCOPE = re.compile(r'^(?:scope\s*:|(?:discovery|research|review|read)[ -]only\b|out of scope\s*:)', re.I)
CORRECTION = re.compile(r'^(?:correction\s*:|(?:please\s+)?replace\s+["“])', re.I)
QUALIFICATION = re.compile(
    r'\bproposed (?:target|plan)\b|\bnot (?:a |an )?(?:guarantee|approved|verified|implemented|deployed)\b'
    r'|\b(?:remains|is still) (?:unresolved|unverified|unapproved)\b', re.I)
PRIORITY = dict(scope_boundary=100, correction_candidate=90, open_question=80,
                qualification_candidate=75, deferred=70, reported_blocker=60, decision_candidate=50)


def _labels(body, role):
    labels = set()
    for line in body.splitlines():
        line = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', line).strip()
        if SCOPE.search(line) or (line.casefold().startswith('do not ') and _is_request(line)):
            labels.add('scope_boundary')
        if CORRECTION.search(line):
            labels.add('correction_candidate')
        if QUALIFICATION.search(line):
            labels.add('qualification_candidate')
        kind = classify(line, role.lower())
        if kind in PRIORITY:
            labels.add(kind)
    return sorted(labels, key=lambda label: (-PRIORITY[label], label))


def suggest_requirements(directory, query, *, projects=None, limit=10, max_paragraph_chars=2000):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Evidence suggestions need a nonempty literal query.')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Suggestion limit must be between 1 and 100.')
    if type(max_paragraph_chars) is not int or max_paragraph_chars < 1:
        raise ValueError('The paragraph character limit must be positive.')
    projects = normalize_projects(projects)
    if not (directory / 'sessions.json').is_file():
        raise ValueError('Evidence suggestions need an existing archive index.')
    index_snapshot = (directory / 'sessions.json').read_bytes()
    rows = JsonIndexRenderer.read_entries(directory / 'sessions.json')
    candidates, warnings, snapshots, omissions = [], [], {}, []
    oversized = 0
    for sid, row in rows.items():
        if not project_matches(row, projects):
            continue
        path = directory / f'{sid}.md'
        if not path.is_file() or path.is_symlink():
            warnings.append(dict(code='suggestion_source_unavailable', session_id=sid))
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        snapshots[sid] = digest
        sections = conversation_sections(raw.decode('utf-8'))
        query_session = any(query.casefold() in body.casefold() for _, body in sections)
        # Cross-session relevance is only proposed within explicit metadata scope.
        if not projects and not query_session:
            continue
        for number, (role, body) in enumerate(sections, 1):
            section_digest = section_hash(role, body)
            for span in paragraph_spans(body):
                labels = _labels(span['text'], role)
                if not labels:
                    continue
                if len(span['text']) > max_paragraph_chars:
                    oversized += 1
                    if len(omissions) < 100:
                        omissions.append(dict(reason='paragraph_too_large', session_id=sid, agent=row['agent'],
                                              section=number, start_line=span['start_line'], end_line=span['end_line'],
                                              paragraph_chars=len(span['text']), source_sha256=digest,
                                              section_sha256=section_digest))
                    continue
                identity = [sid, row['agent'], section_digest, number, span['start_line'], span['end_line']]
                candidate_id = 'suggested-' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:16]
                anchor = dict(id=candidate_id, session_id=sid, agent=row['agent'], role=role, section=number,
                              quote=span['text'], unit='paragraph', source_sha256=digest,
                              section_sha256=section_digest, anchor_method='complete_section_v1',
                              paragraph={key: span[key] for key in ('start_line', 'end_line', 'sha256')})
                score = max(PRIORITY[label] for label in labels) + (20 if query.casefold() in span['text'].casefold() else 0)
                score += 10 if query_session else 0
                candidates.append(dict(anchor=anchor, reasons=labels, score=score, verification='not_checked',
                                       origin_hint=paragraph_origin_hint(body, span['start_line'], span['end_line']),
                                       topic_relation='literal_query_session' if query_session else 'declared_metadata_scope_only'))
    candidates.sort(key=lambda candidate: (-candidate['score'], candidate['anchor']['session_id'],
                                           candidate['anchor']['section'], candidate['anchor']['paragraph']['start_line']))
    if ((directory / 'sessions.json').read_bytes() != index_snapshot
            or any(hashlib.sha256((directory / f'{sid}.md').read_bytes()).hexdigest() != digest for sid, digest in snapshots.items())):
        raise StorageError('A source changed while suggesting evidence. Retry with settled exports.')
    return dict(method='bounded_paragraph_suggestions_v1', origin_method=ORIGIN_METHOD, read_only=True, ready=False,
                scope=scope_summary(rows, projects), candidates=candidates[:limit], candidates_found=len(candidates),
                candidates_omitted=max(0, len(candidates) - limit), oversized_paragraphs_omitted=oversized,
                omissions=omissions, omission_locators_omitted=max(0, oversized - len(omissions)),
                warnings=warnings, coverage_established=False,
                boundary='Unaccepted assistant-review proposals. No source text is executed and no requirements are written.',
                limits='Bounded English cues. Cross-session candidates require explicit project metadata scope. '
                       'Topic relevance, completeness, factual truth, authorship, and current authorization are not established. '
                       'Origin hints describe wrapper shapes only; embedded constraints remain reviewable evidence.')
