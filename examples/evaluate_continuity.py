"""Probe required-tail retention with the same invented source as the Node probe.

This probe sets both per-source and complete handoff character limits.
Rendering and metadata accounting differ between APIs. This script does
not make equal-budget, task-performance, or product-superiority claims.
"""

import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import compile_handoff, pin_requirement
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


def evaluate(directory):
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/continuity_tail_case.json'
    case = json.loads(fixture.read_text())
    body = case['prefix'] + case['detail'] * case['repeat'] + '\n' + case['required_quote']
    archive = directory / 'exports'
    requirements = directory / 'handoff-requirements.json'
    session = Session(id='synthetic-tail-scope', agent=Agent.CODEX, title=case['title'],
                      messages=[Message(role='assistant', text=body)])
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')
    pin_requirement(archive, requirements, 'scope', session.id, 1, case['required_quote'])
    outcomes = []
    for budget in case['budgets']:
        text, manifest = compile_handoff(archive, case['query'], requirements, max_chars=budget, max_total_chars=budget)
        outcomes.append(dict(max_handoff_chars=budget, ready=manifest['ready'],
                             scope_retained=case['required_quote'] in text, handoff_chars=len(text),
                             requirement_status=manifest['requirements'][0]['status']))
    return dict(synthetic_only=True, input_body_chars=len(body), outcomes=outcomes,
                boundary='One invented source. Rendering and character accounting differ between APIs. '
                         'No task-performance or product-superiority claim is established.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-tail-evaluation-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), indent=2))
