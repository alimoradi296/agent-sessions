"""Use optional FailMin to reduce an actual synthetic handoff-selection failure.

No model is run. The oracle calls this repository's real handoff builder.
FailMin remains an optional external tool rather than a package dependency.
"""

import hashlib
import importlib.metadata
import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.handoff import build_handoff
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

SCOPE = 'Discovery only. Do not implement or publish.'


def evaluate():
    try:
        from failmin import RunResult, Trace, TraceEvent, minimize
    except ImportError as exc:
        raise SystemExit('Run this optional probe in an isolated environment with failmin==0.2.0 installed.') from exc
    events = [TraceEvent(id=f'synthetic-detail-{n}', type='user_message',
                         input=f'The example cache naming option {n} remains undecided.') for n in range(20)]
    events.append(TraceEvent(id='synthetic-scope', type='user_message', input=SCOPE))
    trace = Trace(tuple(events), {'synthetic_only': True})

    def replay(candidate):
        with tempfile.TemporaryDirectory(prefix='agent-sessions-failmin-candidate-') as temporary:
            archive = Path(temporary) / 'exports'
            session = Session(id='synthetic-history', agent=Agent.CODEX, title='example cache',
                              messages=[Message(role='user', text=event.input) for event in candidate.events])
            MarkdownRenderer.write(session, archive)
            JsonIndexRenderer.update(session, archive / 'sessions.json')
            handoff = build_handoff(archive, 'example cache', last=1, max_chars=6000)
            return RunResult(output=handoff, metadata=dict(
                required_source_present=any(event.input == SCOPE for event in candidate.events),
                query_source_present=any('example cache' in event.input for event in candidate.events)))

    def fails(result):
        return (result.metadata['required_source_present'] and result.metadata['query_source_present']
                and SCOPE not in result.output)

    result = minimize(trace, replay, fails)
    # Check event-level one-minimality independently of the reducer's report.
    single_deletions_still_fail = []
    for index, event in enumerate(result.minimal.events):
        candidate = Trace(result.minimal.events[:index] + result.minimal.events[index + 1:])
        if fails(replay(candidate)):
            single_deletions_still_fail.append(event.id)
    return dict(synthetic_only=True, failmin_version=importlib.metadata.version('failmin'),
                original_events=len(trace.events), reduced_events=len(result.minimal.events),
                replay_calls=result.replay_calls, evaluations=result.tests_run,
                failure_reproduced=fails(replay(result.minimal)),
                query_source_retained=replay(result.minimal).metadata['query_source_present'],
                single_deletions_still_fail=single_deletions_still_fail,
                reduced_trace_sha256=hashlib.sha256(json.dumps(result.minimal.to_dict(), sort_keys=True).encode()).hexdigest(),
                oracle='Actual build_handoff literal-query selection with one source and 6000 excerpt characters.',
                limits=['Deterministic selection omission only, not a model failure or semantic root cause.',
                        'One-minimal at event granularity is not proof of a globally smallest trace.',
                        'Existing FailMin supplies reduction; no exclusive minimization capability is established.'])


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
