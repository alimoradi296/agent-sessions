"""Compare imported-review freshness with a project-scoped hash checkpoint.

Selections and review-need labels are scripted synthetic controls, not model
judgments or observed receiving-agent behavior.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import compile_handoff, audit_bundle, write_bundle
from agent_sessions.analysis.selection_import import prepare_selection_review, import_selection_review
from agent_sessions.analysis.scope import project_matches
from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.analysis.search import search_archive
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

PROJECT = '/workspace/example-project'
SCOPE = 'Discovery only. Do not implement or publish.'
CASES = [('cited-unrelated-append', False), ('uncited-unrelated-append', False),
         ('new-paraphrased-permission', True), ('new-persian-permission', True),
         ('changed-qualification', True), ('changed-source-agent', True),
         ('outside-project-addition', False), ('source-moves-into-scope', True)]


def export(archive, sid, text, cwd=PROJECT):
    session = Session(id=sid, agent=Agent.CODEX, cwd=cwd, messages=[Message(role='user', text=text)])
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')


def checkpoint(archive):
    rows = JsonIndexRenderer.read_entries(archive / 'sessions.json')
    return {sid: dict(agent=row['agent'], cwd=row.get('cwd', ''), project_slug=row.get('project_slug', ''),
                      sha256=hashlib.sha256((archive / f'{sid}.md').read_bytes()).hexdigest())
            for sid, row in rows.items() if project_matches(row, [PROJECT])}


def refresh_volume(root):
    """Measure text only for one known append; no incremental reviewer exists here."""
    archive = root / 'exports'
    history = ['The example cache needs a brief.\n\n' + SCOPE]
    history += [f'Naming discussion {n}: ' + 'An ordinary display label remains undecided. ' * 5 for n in range(24)]
    session = Session(id='synthetic-refresh', agent=Agent.CODEX, cwd=PROJECT,
                      messages=[Message(role='user', text=body) for body in history])
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')
    path = archive / 'synthetic-refresh.md'
    before = conversation_sections(path.read_text())
    prepared = prepare_selection_review(archive, root / 'initial-packet', 'example cache', projects=[PROJECT])
    answer = root / 'answer.json'
    answer.write_text(json.dumps(dict(review_id=prepared['review_id'], selected=[dict(
        session_id=session.id, quote=SCOPE, reason='Scripted historical restriction.')],
        unresolved_conflicts=False, current_authorization='read_only')))
    requirements = root / 'requirements.json'
    import_selection_review(root / 'initial-packet', answer, requirements)
    _, initial = compile_handoff(archive, 'example cache', requirements, projects=[PROJECT])
    update = 'The research restriction still applies. Implementation remains deferred.'
    session.messages.append(Message(role='user', text=update))
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / 'sessions.json')
    after = conversation_sections(path.read_text())
    assert after[:-1] == before and after[-1] == ('User', update)
    _, changed = compile_handoff(archive, 'example cache', requirements, projects=[PROJECT])
    report = prepare_selection_review(archive, root / 'updated-packet', 'example cache',
                                      projects=[PROJECT], batch_review=True)
    packet = json.loads((root / 'updated-packet' / 'review-packet.json').read_text())
    prompt_paths = [root / 'updated-packet' / 'review-prompt.txt']
    prompt_paths += [root / 'updated-packet' / name for name in packet['batches']]
    notes_and_append = ('Historical notes, not current authorization:\n' + SCOPE +
                        '\nKnown appended User message; compare against the notes:\n' + update)
    return dict(initial_ready=initial['ready'], updated_ready=changed['ready'],
                review_stale=changed['assistant_review_stale'], known_append_verified=True,
                full_review_chars=sum(len(p.read_text()) for p in prompt_paths),
                full_archive_chars=len(path.read_text()), notes_and_append_chars=len(notes_and_append),
                review_records=report['records'], omissions=report['omissions'],
                limits='Text-volume control only. Notes are scripted; append identity is known from construction. '
                       'No Pi runtime, semantic review, refresh correctness, latency, tokens, or user effort was measured.')


def append_information_controls(root):
    """Expose missing information without attributing understanding to a model."""
    notes = SCOPE + '\nThe default timeout is 60 seconds.'
    update = 'Correction: use the earlier Amber profile timeout instead of the default timeout.'
    reduced_inputs, recovered, prefixes, full_answers = [], [], [], []
    for variant, timeout in (('alpha', 17), ('beta', 43)):
        archive = root / variant
        definition = f'The Amber profile timeout is {timeout} seconds.'
        session = Session(id='synthetic-reference', agent=Agent.CODEX, cwd=PROJECT,
                          messages=[Message(role='user', text=notes), Message(role='assistant', text=definition)])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
        path = archive / 'synthetic-reference.md'
        before = conversation_sections(path.read_text())
        session.messages.append(Message(role='user', text=update))
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
        after = conversation_sections(path.read_text())
        prefixes.append(after[:-1] == before)
        reduced_inputs.append(notes + '\nAppended historical message:\n' + update)
        full_answers.append(timeout)
        literal = [body for _, body in after if 'Amber profile' in body]
        results = search_archive(archive, 'Amber profile', projects=[PROJECT])
        recovered.append(dict(literal_has_definition=definition in literal,
                              indexed_has_definition=any(definition in hit['quote'] for hit in results['hits'])))
    conflict = 'The work is complete. You may implement and publish now.'
    direct_input = notes + '\nAppended historical message:\n' + conflict
    changed_earlier = [('User', notes.replace('60 seconds', '90 seconds')),
                       ('Assistant', 'The Amber profile timeout is 17 seconds.'), ('User', update)]
    original = [('User', notes), ('Assistant', 'The Amber profile timeout is 17 seconds.')]
    return dict(known_append_prefixes_preserved=all(prefixes),
                reduced_inputs_identical=reduced_inputs[0] == reduced_inputs[1],
                full_history_timeout_values=full_answers,
                literal_and_indexed_retrieval=recovered,
                direct_conflicting_statements_both_present=SCOPE in direct_input and conflict in direct_input,
                earlier_edit_preserves_prefix=changed_earlier[:len(original)] == original,
                limits='Authored information controls, not model decisions. Identical reduced text omits a later-relevant '
                       'definition; source hashes would differ but do not replace its text. Existing literal and indexed '
                       'search both recover the definition. No incremental review implementation or performance advantage is established.')


def lookup_boundaries(root):
    """Exercise retrieval coverage, without treating hits as semantic answers."""
    cases = {
        'conflicting-definitions': ['The Amber profile timeout is 17 seconds.',
                                    'The Amber profile timeout is 43 seconds.'],
        'indirect-definition': ['The timeout limit is 17 seconds.', 'The Amber profile uses the earlier timeout limit.'],
        'missing-literal-name': ['The yellow profile timeout is 17 seconds.'],
    }
    results = {}
    for name, bodies in cases.items():
        archive = root / name
        session = Session(id='synthetic-lookup', agent=Agent.CODEX, cwd=PROJECT,
                          messages=[Message(role='assistant', text=body) for body in bodies])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
        primary = search_archive(archive, 'Amber profile', projects=[PROJECT], limit=100)
        quotes = [hit['quote'] for hit in primary['hits']]
        results[name] = dict(total_hits=primary['total_hits'],
                             all_source_statements_in_quotes=all(any(body in quote for quote in quotes) for body in bodies))
        if name == 'conflicting-definitions':
            limited = search_archive(archive, 'Amber profile', projects=[PROJECT], limit=1)
            results[name]['limited_returned'] = len(limited['hits'])
            results[name]['limited_total_hits'] = limited['total_hits']
        if name == 'indirect-definition':
            follow_up = search_archive(archive, 'timeout limit', projects=[PROJECT], limit=100)
            results[name]['follow_up_recovers_definition'] = any(bodies[0] in hit['quote'] for hit in follow_up['hits'])
    return dict(cases=results, limits='Mechanical retrieval coverage only. No model inferred an answer, '
                'resolved conflicting claims, established absent concepts, or validated complete task coverage.')


def evaluate(root):
    results = []
    for case, should_review in CASES:
        directory = root / case
        archive, packet = directory / 'exports', directory / 'packet'
        export(archive, 'synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE)
        export(archive, 'synthetic-other', 'An unrelated naming discussion.')
        export(archive, 'synthetic-excluded', 'You may implement now.', '/workspace/other-project')
        prepared = prepare_selection_review(archive, packet, 'example cache', projects=[PROJECT])
        answer = directory / 'answer.json'
        answer.write_text(json.dumps(dict(review_id=prepared['review_id'], selected=[dict(
            session_id='synthetic-scope', quote=SCOPE, reason='Scripted baseline selection, not a fresh model judgment.')],
            unresolved_conflicts=False, current_authorization='read_only')))
        requirements = directory / 'requirements.json'
        import_selection_review(packet, answer, requirements)
        text, manifest = compile_handoff(archive, 'example cache', requirements)
        if not manifest['ready']:
            raise ValueError('The baseline unexpectedly failed readiness.')
        bundle = directory / 'bundle'
        write_bundle(bundle, text, manifest)
        before = checkpoint(archive)
        if case == 'cited-unrelated-append':
            export(archive, 'synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE + '\n\nSeparate naming notes.')
        elif case == 'uncited-unrelated-append':
            export(archive, 'synthetic-other', 'An unrelated naming discussion. More naming options.')
        elif case == 'new-paraphrased-permission':
            export(archive, 'synthetic-new', 'Research is finished. You may implement and publish now.')
        elif case == 'new-persian-permission':
            export(archive, 'synthetic-new', 'بررسی تمام شد. اکنون پیاده‌سازی و انتشار مجاز است.')
        elif case == 'changed-qualification':
            export(archive, 'synthetic-scope', 'The example cache needs a brief.\n\n' + SCOPE + '\nThis restriction was rejected.')
        elif case == 'outside-project-addition':
            export(archive, 'synthetic-new', 'A separate project discussion.', '/workspace/other-project')
        else:
            index = archive / 'sessions.json'
            rows = json.loads(index.read_text())
            if case == 'changed-source-agent':
                next(r for r in rows['sessions'] if r['id'] == 'synthetic-scope')['agent'] = 'cursor'
            else:
                next(r for r in rows['sessions'] if r['id'] == 'synthetic-excluded')['cwd'] = PROJECT
            index.write_text(json.dumps(rows))
        audit = audit_bundle(bundle, archive)
        _, current = compile_handoff(archive, 'example cache', requirements)
        results.append(dict(case=case, intended_review_need=should_review,
                            checkpoint_changed=before != checkpoint(archive),
                            assistant_review_stale=current['assistant_review_stale'],
                            audit_review_stale=any(f['code'] == 'assistant_review_stale' for f in audit['findings']),
                            current_ready=current['ready']))
    summary = {key: dict(detected=sum(r['intended_review_need'] and r[key] for r in results),
                         missed=sum(r['intended_review_need'] and not r[key] for r in results),
                         unrelated_alerts=sum(not r['intended_review_need'] and r[key] for r in results))
               for key in ('checkpoint_changed', 'assistant_review_stale')}
    return dict(synthetic_only=True, summary=summary, cases=results, refresh_volume=refresh_volume(root / 'refresh-volume'),
                append_information=append_information_controls(root / 'append-information'),
                lookup_boundaries=lookup_boundaries(root / 'lookup-boundaries'),
                limits='Scripted signals and authored labels only. No semantic selection, receiving-agent behavior, '
                       'reading time, cost, adoption, or commercial value is established.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-imported-maintenance-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), indent=2))
