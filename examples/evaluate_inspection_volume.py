"""Measure displayed dialogue volume in a synthetic repeated-use workflow.

Inspection notes are scripted controls. No person reads or judges these cases.
Character counts measure displayed text, not time, correctness, or cost savings.
"""

import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import load_requirements, note_source_inspection, pin_requirement
from agent_sessions.analysis.inspection import inspection_report
from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

PROJECT = '/workspace/example-project'
SCOPE = 'Discovery only. Do not implement or publish.'


def _export(archive, session):
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')


def _volume(sections):
    return dict(sections=len(sections), dialogue_chars=sum(len(section['text']) for section in sections))


def evaluate(root):
    archive, requirements = root / 'exports', root / 'requirements.json'
    sessions = []
    for number in range(12):
        agent = (Agent.CODEX, Agent.CURSOR, Agent.CLAUDE)[number % 3]
        texts = [f'Synthetic source {number}, turn {turn}. A separate example design detail remains under discussion.'
                 for turn in range(24)]
        if number == 0:
            texts[0] = SCOPE
        session = Session(id=f'synthetic-volume-{number}', agent=agent,
                          cwd=PROJECT if number < 8 else '/workspace/other-project',
                          messages=[Message(role='user', text=text) for text in texts])
        sessions.append(session)
        _export(archive, session)
    pin_requirement(archive, requirements, 'scope', sessions[0].id, 1, SCOPE)

    def report(session=None, changed=False):
        notes = load_requirements(requirements).get('source_inspections', [])
        return inspection_report(archive, notes, projects=[PROJECT], session_id=session, changed_only=changed)

    initial = report()
    initial_sections = initial_chars = 0
    for source in initial['sources']:
        view = report(source['session_id'])['selected_source']
        volume = _volume(view['sections'])
        initial_sections += volume['sections']
        initial_chars += volume['dialogue_chars']
        note_source_inspection(archive, requirements, source['session_id'], view['inspection_id'],
                               'Scripted baseline control. No actual human inspection occurred.', projects=[PROJECT])

    mutations = [
        ('appended-instruction', 'A new instruction is appended without repeating the saved topic.'),
        ('edited-qualification', 'An existing qualification changes and its prior text is unavailable.'),
        ('deleted-qualification', 'A qualification disappears, leaving no added dialogue section.'),
        ('metadata-change', 'Only recorded project metadata changes.'),
        ('duplicate-appended', 'A duplicate complete section is appended and must count as a new occurrence.'),
        ('section-reordered', 'Two distinct turns exchange positions without changing their text.'),
    ]
    sessions[0].messages.append(Message(role='user', text='The review stage is finished. Implementation is proposed next.'))
    sessions[1].messages[5].text = 'The timing is a proposed target. It is not an established guarantee.'
    sessions[2].messages.pop(5)
    sessions[3].project_slug = 'workspace-example-project'
    sessions[4].messages.append(Message(role='user', text=sessions[4].messages[5].text))
    sessions[5].messages[5], sessions[5].messages[6] = sessions[5].messages[6], sessions[5].messages[5]
    for session in sessions[:6]:
        _export(archive, session)
    new = Session(id='synthetic-volume-new', agent=Agent.CURSOR, cwd=PROJECT, messages=[
        Message(role='user', text='بررسی تمام شد. اکنون تغییر محدوده پیشنهاد می‌شود.'),
        Message(role='assistant', text='Acceptance of the proposed scope change remains unresolved.')])
    _export(archive, new)
    labels = {sessions[number].id: dict(case=case, rationale=rationale)
              for number, (case, rationale) in enumerate(mutations)}
    labels[new.id] = dict(case='new-conversation', rationale='A new conversation uses different wording and language.')

    current = report()
    rows = []
    for source in current['sources']:
        if source['status'] == 'note_current':
            continue
        full = report(source['session_id'])['selected_source']
        changed = report(source['session_id'], True)['selected_source']
        rows.append(dict(labels[source['session_id']], status=source['status'], full_source=_volume(full['sections']),
                         changed_view=_volume(changed['sections']), removed_sections=changed['removed_sections'],
                         full_view_recommended=changed['changes']['full_view_recommended'],
                         full_view_reasons=changed['changes']['full_view_reasons'],
                         prior_text_available=changed['prior_text_available']))
    archive_sections = [dict(text=text) for source in current['sources']
                        for _, text in conversation_sections((archive / f"{source['session_id']}.md").read_text())]
    return dict(synthetic_only=True, scripted_inspection_notes=True, source_sections_before=24,
                initial_inspection=dict(sources=initial['pending'], sections=initial_sections, dialogue_chars=initial_chars),
                repeated_use=dict(total_in_scope_sources=len(current['sources']), pending_sources=current['pending'],
                                  reread_archive=_volume(archive_sections),
                                  queued_full_sources={key: sum(row['full_source'][key] for row in rows)
                                                       for key in ('sections', 'dialogue_chars')},
                                  changed_view={key: sum(row['changed_view'][key] for row in rows)
                                                for key in ('sections', 'dialogue_chars')},
                                  with_full_view_recommendations={key: sum(row['full_source' if row['full_view_recommended'] else 'changed_view'][key]
                                                                         for row in rows)
                                                                  for key in ('sections', 'dialogue_chars')},
                                  pending_with_no_displayed_update=sum(row['changed_view']['sections'] == 0 for row in rows)),
                cases=rows,
                limits=['Initial inspection still covers every in-scope source.',
                        'Smaller displayed volume is not evidence of less reading time or correct understanding.',
                        'Deleted, reordered, or metadata-only changes can require inspection with no added section.',
                        'Unchanged surrounding dialogue is omitted from the changed view.',
                        'No actual human inspection, discovery success, or pricing feedback was measured.'])


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-inspection-volume-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), ensure_ascii=False, indent=2))
