"""Explicit quoted relationship candidates within selected complete evidence.

No semantic conflict detection, date-based precedence, adoption, or authority is
inferred. A linked candidate only means its quoted references were located.
"""

from __future__ import annotations

import hashlib
import json
import re

from agent_sessions.analysis.claims import render_evidence

METHOD = 'explicit_quotes_v1'
MIN_QUOTE_LENGTH = 8
QUOTE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|‘([^’\n]+)’|`([^`\n]+)`|\'([^\'\n]+)\'')


def _relationship(line: str):
    quotes = list(QUOTE.finditer(line))
    if len(quotes) != 2 or '?' in line:
        return None
    left, right = (next(value for value in match.groups() if value is not None) for match in quotes)
    if min(len(left.strip()), len(right.strip())) < MIN_QUOTE_LENGTH or left == right:
        return None
    prefix = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', line[:quotes[0].start()])
    prefix = prefix.replace('**', '').strip()
    middle = ' '.join(line[quotes[0].end():quotes[1].start()].replace('**', '').split())
    # Requiring explicit framing avoids interpreting casual comparisons as links.
    if re.fullmatch(r'(?:Correction:\s*)?(?:Please\s+)?Replace', prefix, re.IGNORECASE) and re.fullmatch(r'with\s*:?', middle, re.IGNORECASE):
        return 'proposed_correction', left, right
    if re.fullmatch(r'(?:Supersession:)?', prefix, re.IGNORECASE) and middle.casefold() == 'supersedes':
        return 'reported_supersession', right, left
    if re.fullmatch(r'(?:Correction:)?', prefix, re.IGNORECASE) and middle.casefold() == 'corrects':
        return 'reported_correction', right, left
    if re.fullmatch(r'(?:Conflict:)?', prefix, re.IGNORECASE) and middle.casefold() == 'conflicts with':
        return 'reported_conflict', left, right
    return None


def find_relations(sections: list[tuple[dict, str]]) -> list[dict]:
    """Link exact, case-sensitive quotes within cleaned complete sections.

    A replacement statement is itself quoted in the witness. Its original target
    must occur outside recognized relationship lines. Conflicts require separate references.
    Multiple source-line matches remain ambiguous, including copied statements.
    """
    lines = [(dict(evidence, section_line=i, quote=line.strip()), line.strip())
             for evidence, text in sections for i, line in enumerate(text.splitlines(), 1) if line.strip()]
    framed = [(evidence, line, _relationship(line)) for evidence, line in lines]
    results = []
    for witness, line, parsed in framed:
        if parsed is None:
            continue
        kind, original, replacement = parsed

        def locate(quote):
            return [dict(evidence, matched_quote=quote) for evidence, text, frame in framed
                    if frame is None and quote in text]

        original_sources = locate(original)
        replacement_sources = (locate(replacement) if kind == 'reported_conflict'
                               else [dict(witness, matched_quote=replacement)])
        if not original_sources or not replacement_sources:
            status = 'unresolved'
        elif len(original_sources) != 1 or len(replacement_sources) != 1:
            status = 'ambiguous'
        else:
            status = 'linked'
        digest = hashlib.sha256(json.dumps([kind, witness, original, replacement], sort_keys=True).encode()).hexdigest()[:16]
        results.append(dict(id=digest, kind=kind, method=METHOD, verification='not_checked', status=status,
                            original=original, replacement=replacement,
                            original_sources=original_sources, replacement_sources=replacement_sources,
                            witness=witness))
    return results


def render_relations(relations: list[dict]) -> list[str]:
    lines = [
        'Not resolved by this command. Relationships below are proposed or reported, not authoritative.',
        'Linked means quoted references were located; it does not establish adoption or correctness.',
        f'Method: {METHOD}; exact quoted references in selected complete excerpts.',
        'Local section order and Cursor file modification dates do not establish authority across sessions.', '',
    ]
    if not relations:
        lines.extend(['No explicit quoted relationships recognized in selected complete excerpts.', ''])
    for relation in relations:
        lines.extend([f"### {relation['kind']} — {relation['status']} (not checked)", '',
                      f"Relationship quote: {json.dumps(relation['witness']['quote'], ensure_ascii=False)}",
                      render_evidence(relation['witness']), '',
                      f"Original statement: {json.dumps(relation['original'], ensure_ascii=False)}"])
        if relation['original_sources']:
            for source in relation['original_sources']:
                lines.extend([f"Context quote: {json.dumps(source['quote'], ensure_ascii=False)}", render_evidence(source)])
        else:
            lines.append('Original reference not found outside recognized relationship lines in selected excerpts.')
        label = 'Other statement' if relation['kind'] == 'reported_conflict' else 'Replacement statement'
        lines.extend(['', f"{label}: {json.dumps(relation['replacement'], ensure_ascii=False)}"])
        if relation['replacement_sources']:
            for source in relation['replacement_sources']:
                lines.extend([f"Context quote: {json.dumps(source['quote'], ensure_ascii=False)}", render_evidence(source)])
        else:
            lines.append('Other reference not found outside recognized relationship lines in selected excerpts.')
        if relation['status'] == 'ambiguous':
            lines.append('Multiple matches remain visible. Review the cited sources before selecting a reference.')
        lines.append('')
    return lines
