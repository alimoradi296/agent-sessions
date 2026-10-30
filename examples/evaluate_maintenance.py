"""Replay invented source updates against bounded audits and simple hash checks.

All labels and source choices are author-supplied controls. These are software
signals, not a human maintenance study, semantic detector, or pricing evidence.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import (
    audit_bundle, compile_handoff, load_requirements, note_source_inspection, pin_requirement, write_bundle,
)
from agent_sessions.analysis.inspection import inspection_report
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

ORIGINAL = 'Discovery only. Do not implement or publish.'
CASES = [
    ('cited-unrelated-append', False), ('uncited-unrelated-append', False),
    ('new-quoted-challenge', True), ('new-paraphrased-challenge', True),
    ('changed-qualification', True), ('changed-source-agent', True),
]


def _export(archive, session):
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')


def _checkpoint(archive, cited_only=False):
    rows = JsonIndexRenderer.read_entries(archive / 'sessions.json')
    selected = {sid: row for sid, row in rows.items() if not cited_only or sid == 'synthetic-scope'}
    return {sid: dict(agent=row['agent'], cwd=row.get('cwd', ''), project_slug=row.get('project_slug', ''),
                      source_sha256=hashlib.sha256((archive / f'{sid}.md').read_bytes()).hexdigest())
            for sid, row in selected.items()}


def evaluate(root):
    results = []
    for case, should_review in CASES:
        directory = root / case
        archive, requirements = directory / 'exports', directory / 'requirements.json'
        source = Session(id='synthetic-scope', agent=Agent.CODEX, messages=[Message(role='user', text=ORIGINAL)])
        other = Session(id='synthetic-other', agent=Agent.CURSOR,
                        messages=[Message(role='assistant', text='An unrelated naming discussion.')])
        _export(archive, source)
        _export(archive, other)
        pin_requirement(archive, requirements, 'scope', source.id, 1, ORIGINAL)
        # Scripted notes establish the checkpoint. No human inspection occurred.
        for sid in (source.id, other.id):
            view = inspection_report(archive, [], session_id=sid)['selected_source']
            note_source_inspection(archive, requirements, sid, view['inspection_id'],
                                   'Scripted baseline control, not actual human inspection.')
        text, manifest = compile_handoff(archive, 'example cache', requirements)
        if not manifest['ready']:
            raise ValueError('The baseline bundle unexpectedly failed readiness.')
        bundle = directory / 'bundle'
        write_bundle(bundle, text, manifest)
        cited, all_sources = _checkpoint(archive, True), _checkpoint(archive)

        if case == 'cited-unrelated-append':
            source.messages.append(Message(role='assistant', text='A separate naming question remains.'))
            _export(archive, source)
        elif case == 'uncited-unrelated-append':
            other.messages.append(Message(role='assistant', text='A separate naming option remains undecided.'))
            _export(archive, other)
        elif case in ('new-quoted-challenge', 'new-paraphrased-challenge'):
            body = (f'Replace "{ORIGINAL}" with "Implementation is proposed next.".'
                    if case == 'new-quoted-challenge' else
                    'The discovery stage is finished. You may implement and publish now.')
            _export(archive, Session(id='synthetic-new', agent=Agent.CLAUDE,
                                     messages=[Message(role='user', text=body)]))
        elif case == 'changed-qualification':
            source.messages[0].text += '\nThis restriction was rejected in a later review.'
            _export(archive, source)
        elif case == 'changed-source-agent':
            index = archive / 'sessions.json'
            rows = json.loads(index.read_text())
            next(row for row in rows['sessions'] if row['id'] == source.id)['agent'] = 'cursor'
            index.write_text(json.dumps(rows))

        audit = audit_bundle(bundle, archive)
        _, current = compile_handoff(archive, 'example cache', requirements)
        queue = inspection_report(archive, load_requirements(requirements)['source_inspections'])
        results.append(dict(case=case, should_review=should_review,
                            cited_source_checkpoint_changed=cited != _checkpoint(archive, True),
                            archive_checkpoint_changed=all_sources != _checkpoint(archive),
                            audit_requires_attention=audit['exit_code'] != 0,
                            audit_codes=sorted({item['code'] for item in audit['findings']}),
                            current_ready=current['ready'], inspection_pending=queue['pending']))
    summary = {}
    for signal in ('cited_source_checkpoint_changed', 'archive_checkpoint_changed', 'audit_requires_attention'):
        summary[signal] = dict(detected=sum(row['should_review'] and row[signal] for row in results),
                               missed=sum(row['should_review'] and not row[signal] for row in results),
                               nonchallenge_alerts=sum(not row['should_review'] and row[signal] for row in results))
    return dict(synthetic_only=True, labels='Author-defined intended review need; not independent adjudication.',
                baselines='Cited-source and whole-archive byte plus agent/project metadata checkpoints.',
                summary=summary, cases=results,
                limits=['One scripted replay, not actual human maintenance effort.',
                        'Hash checks flag changed inputs without interpreting meaning.',
                        'Bounded audit can miss paraphrased challenges; inspection queue is independent of readiness.',
                        'A saved manual handoff without any check is not treated as the only manual baseline.',
                        'No semantic authority, acceptance, task completion, or commercial demand is established.'])


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-maintenance-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), indent=2))
