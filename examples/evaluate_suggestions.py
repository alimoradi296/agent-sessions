"""Evaluate automatic evidence nomination on authored synthetic cases.

No requirement pins or model calls are used. Labels are scenario intentions,
not independently adjudicated relevance or proof of complete discovery.
"""

import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.suggestions import suggest_requirements
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

PROJECT = '/workspace/example-project'
CASES = [
    ('scope', 'Discovery only. Do not implement or publish.', True, True),
    ('timing', 'The timing is a proposed target, not a guarantee.', True, True),
    ('question', 'Open question: Should manual exclusions survive synchronization?', True, True),
    ('correction', 'Correction: Replace "The timing is guaranteed." with "The timing is a proposal.".', True, True),
    ('paraphrase', 'Research is finished. You may code and publish the feature now.', True, True),
    ('persian', 'بررسی تمام شد. اکنون پیاده‌سازی و انتشار مجاز است.', True, True),
    ('oversized', 'Do not publish.\n' + 'Synthetic qualification details remain relevant. ' * 90, True, True),
    ('neutral', 'The example cache uses a placeholder diagram.', False, True),
    ('other-feature', 'Do not implement the unrelated ledger migration.', False, True),
    ('other-project', 'Do not implement the example cache in another project.', False, False),
    ('claimed-result', 'Verified: All checks passed.', False, True),
]


def evaluate(root):
    archive = root / 'exports'
    for number, (name, body, _, in_scope) in enumerate(CASES):
        context = ('Discussion of the unrelated ledger.' if name == 'other-feature'
                   else 'Discussion of the example cache.')
        session = Session(id=f'synthetic-case-{number}', agent=(Agent.CODEX, Agent.CURSOR, Agent.CLAUDE)[number % 3],
                          cwd=PROJECT if in_scope else '/workspace/other-project',
                          messages=[Message(role='user', text=context + '\n\n' + body)])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
    report = suggest_requirements(archive, 'example cache', projects=[PROJECT], limit=100)
    proposed = {candidate['anchor']['session_id'] for candidate in report['candidates']}
    rows = [dict(case=name, should_propose=expected, proposed=f'synthetic-case-{number}' in proposed)
            for number, (name, _, expected, _) in enumerate(CASES)]
    return dict(synthetic_only=True, manual_pins_created=False, ready=report['ready'],
                labels='One author-labeled paragraph per synthetic source. No independent relevance judgments.',
                detected=sum(row['should_propose'] and row['proposed'] for row in rows),
                missed=sum(row['should_propose'] and not row['proposed'] for row in rows),
                irrelevant_proposals=sum(not row['should_propose'] and row['proposed'] for row in rows),
                oversized_paragraphs_omitted=report['oversized_paragraphs_omitted'],
                actionable_omission_locators=len(report.get('omissions', [])), cases=rows,
                limits='Measures nomination only. No model understanding, accepted requirements, complete discovery, '
                       'human effort, or commercial demand is established.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-suggestion-evaluation-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), indent=2))
