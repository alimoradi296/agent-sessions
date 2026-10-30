"""Measure review triggers against labeled, invented conversation updates.

No agents, private histories, services, or model calls are used. Labels describe
the author's scenario intent, not an independently adjudicated benchmark.
"""

import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import compile_handoff, pin_requirement, link_challenge
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

ORIGINAL = 'Discovery only. Do not implement or publish.'
PROJECT = '/workspace/example-project'
CURSOR_PROJECT = 'workspace-example-project'


def summarize(rows):
    counts = dict(detected_challenges=0, missed_challenges=0,
                  unnecessary_reviews=0, quiet_nonchallenges=0)
    for row in rows:
        key = ('detected_challenges' if row['review_triggered'] else 'missed_challenges') if row['should_review'] else (
            'unnecessary_reviews' if row['review_triggered'] else 'quiet_nonchallenges')
        counts[key] += 1
    positives = counts['detected_challenges'] + counts['missed_challenges']
    negatives = counts['unnecessary_reviews'] + counts['quiet_nonchallenges']
    return dict(counts, challenge_detection_rate=counts['detected_challenges'] / positives if positives else None,
                nonchallenge_review_rate=counts['unnecessary_reviews'] / negatives if negatives else None)


def _export(archive, session):
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')


def evaluate(root, cases=None):
    if cases is None:
        fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/review_burden_cases.json'
        cases = json.loads(fixture.read_text(encoding='utf-8'))
    rows = []
    for number, case in enumerate(cases):
        directory = root / str(number)
        archive, requirements = directory / 'exports', directory / 'requirements.json'
        _export(archive, Session(id='synthetic-original', agent=Agent.CODEX, cwd=PROJECT,
                                messages=[Message(role='user', text=ORIGINAL)]))
        pin_requirement(archive, requirements, 'scope', 'synthetic-original', 1, ORIGINAL)
        _export(archive, Session(id='synthetic-update', agent=Agent.CURSOR,
                                project_slug=case.get('project_slug', CURSOR_PROJECT),
                                messages=[Message(role='user', text=case['text'])]))
        scoped_triggered = False
        for mode, projects in [('unscoped', []), ('scoped', [PROJECT, CURSOR_PROJECT]),
                               ('operator_assisted', [PROJECT, CURSOR_PROJECT])]:
            linked = mode == 'operator_assisted' and case['should_review'] and not scoped_triggered
            if linked:
                # An oracle intervention using scenario labels, not automatic detection.
                link_challenge(archive, requirements, 'explicit-challenge', 'scope', 'synthetic-update',
                               1, case['text'], case['rationale'])
            _, manifest = compile_handoff(archive, 'example cache', requirements, projects=projects)
            if not manifest['coverage_passed'] or manifest['relationship_scan_warnings']:
                raise ValueError('Evaluation setup failed: evidence coverage or source scan is incomplete.')
            candidates = manifest['requirements'][0]['unreviewed_candidates']
            if mode == 'scoped':
                scoped_triggered = bool(candidates)
            rows.append(dict(case=case['id'], mode=mode, should_review=case['should_review'],
                             review_triggered=bool(candidates), candidates=len(candidates),
                             operator_links=int(linked),
                             ready=manifest['ready'], rationale=case['rationale']))
    return dict(synthetic_only=True, labeled_cases=len(cases),
                summary={mode: summarize([row for row in rows if row['mode'] == mode])
                         for mode in ('unscoped', 'scoped', 'operator_assisted')},
                operator_intervention=dict(label_guided=True, links=sum(row['operator_links'] for row in rows),
                                           scope='Only labeled challenges missed by the scoped scanner are linked.',
                                           interpretation='Demonstrates explicit-link behavior, not improved automatic detection or measured review effort.'),
                cases=rows,
                limits=['Author-labeled invented cases, not a prevalence sample or independent evaluation.',
                        'Measures review triggers, not agent understanding, review time, or task correctness.',
                        'No semantic conflict detector is implemented. A ready pack can miss a real challenge.'])


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-review-evaluation-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), ensure_ascii=False, indent=2))
