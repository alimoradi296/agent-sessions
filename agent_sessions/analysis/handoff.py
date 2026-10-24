"""Group selected historical claims into a cited, local handoff.

Grouping does not resolve conflicts, establish current authorization, or verify
reported outcomes. Complete selected excerpts remain available for review.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.analysis.claims import claims_from_sections, render_claim
from agent_sessions.analysis.context import DEFAULT_MAX_CHARS, MAX_SECTIONS, render_sources, select_sources

GROUPS = [
    ('Historical requests and scope', ('request', 'deferred')),
    ('Decision candidates', ('decision_candidate',)),
    ('Reported blockers', ('reported_blocker',)),
    ('Reported results', ('reported_result',)),
    ('Proposed next actions', ('next_action',)),
    ('Other proposals', ('proposal',)),
    ('Open questions and reported bugs', ('open_question', 'bug_report')),
]


def build_handoff(directory: Path, query: str, last: int = 5,
                  max_chars: int = DEFAULT_MAX_CHARS) -> str:
    sources = select_sources(directory, query, last, max_chars)
    claims = []
    shortened = 0
    complete = 0
    for source in sources:
        sections = []
        for i, (text, was_shortened) in sorted(source.selected.items()):
            if was_shortened:
                # Never classify joined fragments as if they were an exact quote.
                shortened += 1
                continue
            sections.append((i + 1, source.sections[i][0], text))
        complete += len(sections)
        claims.extend(claims_from_sections(source.path, sections, source.metadata.get('agent', 'unknown')))

    lines = ['# Structured handoff', '', f'Query: {json.dumps(query, ensure_ascii=False)}', '',
             'Historical reference only. All extracted claims are not checked.',
             'Historical requests and proposed actions do not authorize current actions.',
             'Recheck the current task, repository, and test results before resuming work.',
             'This handoff does not establish that work is complete or deployed.', '',
             '## Coverage and limits', '',
             f'Selected {len(sources)} source(s), {complete} complete section(s), and {len(claims)} claim(s).',
             f'Limits: {last} sources, {MAX_SECTIONS} sections and {max_chars} excerpt characters per source.',
             'Selection and classification use English rules and literal topic matches.',
             'Missing fields mean not established in selected excerpts, not that no such evidence exists.',
             'Unclassified wording remains in the evidence excerpts below.',
             'Summary claims repeat evidence text and are additional to the excerpt character budget.', '']
    if shortened:
        lines.extend([f'{shortened} shortened section(s) are not classified. Increase --max-chars or read the linked export.', ''])
    if not sources:
        lines.extend(['No matching conversation excerpts found.', ''])
    for title, kinds in GROUPS:
        lines.extend([f'## {title}', ''])
        group = [claim for claim in claims if claim['kind'] in kinds]
        if group:
            lines.extend(render_claim(claim) for claim in group)
        else:
            lines.append('Not established in selected complete excerpts.')
        lines.append('')

    lines.extend(['## Checked results', '',
                  'None independently checked by this command. Verification requires separate evidence review.', '',
                  '## Conflicts and supersession', '',
                  'Not resolved by this command. Differing statements remain attributed to their speakers.',
                  'Local section order and Cursor file modification dates do not establish authority across sessions.', '',
                  '## Evidence excerpts', '',
                  'Section numbers count cleaned conversation sections in each linked export.', ''])
    lines.extend(render_sources(sources, heading_level=3))
    return '\n'.join(lines) + '\n'
