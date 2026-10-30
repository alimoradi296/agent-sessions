"""Measure repeated raw-review work against complete-source inspection.

Authored selections and expected evidence are controls, not model judgments.
No model, private archive, hook, deployment, or network service is invoked.
"""
import json
from pathlib import Path
import tempfile

from agent_sessions.analysis.continuity import compile_handoff, write_bundle, audit_bundle
from agent_sessions.topic_review import prepare_topic_review, import_topic_review
from agent_sessions.workspace import initialize_workspace, add_topic, get_topic
from agent_sessions.models import Agent, Session, Message, ToolResult
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer


QUERY = 'fictional rollout'
CLAIM = 'The fictional rollout completed. Historical assistant claim; not independently checked.'
QUEUED = 'SYNTHETIC_QUEUE: HTTP 202; task_id=fictional-job; state=queued'
FAILED = 'SYNTHETIC_FAILURE: task_id=fictional-job; state=failed; artifact not produced'


def evaluate():
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-update-') as temporary:
        root = Path(temporary)
        archive = root / 'exports'
        workspace = root / 'workspace'
        initialize_workspace(workspace, archive)
        topic = add_topic(workspace, 'rollout', QUERY)
        requirements = Path(topic['requirements'])
        session = Session(id='synthetic-rollout-updates', agent=Agent.CODEX,
            title='Authored changing-evidence investigation', messages=[
                Message(role='user', text='Analyze the fictional rollout history only. No external actions.'),
                Message(role='assistant', text=CLAIM),
                Message(role='tool', text='', tool_results=[ToolResult(QUEUED)])])
        stages = []
        previous_bundle = None
        for number, name in enumerate(('queued', 'unrelated_append', 'failed')):
            if name == 'unrelated_append':
                session.messages.append(Message(role='user', text='Unrelated fictional typography discussion.'))
            elif name == 'failed':
                session.messages.append(Message(role='tool', text='', tool_results=[ToolResult(FAILED)]))
            MarkdownRenderer.write(session, archive)
            JsonIndexRenderer.update(session, archive / 'sessions.json')
            stale_audit = audit_bundle(previous_bundle, archive) if previous_bundle else None
            before = compile_handoff(archive, QUERY, requirements)[1] if requirements.exists() else None
            prepared = prepare_topic_review(workspace, 'rollout', view='evidence',
                batch_review=True, compact_review=True, max_total_prompt_chars=32000)
            if prepared.get('status') == 'over_budget' or prepared['omissions']:
                raise AssertionError('The authored complete review unexpectedly exceeded its budget.')
            packet_dir = Path(prepared['output'])
            packet = json.loads((packet_dir / 'review-packet.json').read_text())
            # Explicit author labels: this does not measure automatic relevance.
            selected = [r for r in packet['records'] if r['section'] != 4]
            answer = dict(review_id=packet['review_id'], selected=[dict(
                session_id=r['session_id'], section=r['section'], paragraph_start_line=1,
                quote=r['paragraph']['text'], reason='Authored relevant complete message.') for r in selected],
                unresolved_conflicts=False, current_authorization='read_only')
            if 'batches' in packet:
                answer['reviewed_batches'] = list(packet['batches'])
            answer_path = root / f'answer-{number}.json'
            answer_path.write_text(json.dumps(answer))
            import_topic_review(workspace, 'rollout', packet_dir, answer_path)
            requirements = Path(get_topic(workspace, 'rollout')[2]['requirements'])
            text, manifest = compile_handoff(archive, QUERY, requirements)
            previous_bundle = root / f'bundle-{number}'
            write_bundle(previous_bundle, text, manifest)
            audit = audit_bundle(previous_bundle, archive)
            source = (archive / f'{session.id}.md').read_text()
            expected = [CLAIM, QUEUED] + ([FAILED] if name == 'failed' else [])
            if not all(value in source and value in text for value in expected):
                raise AssertionError('One arm omitted required authored evidence.')
            if not manifest['ready'] or audit['exit_code'] != 0 or manifest['verification'] != 'not_checked':
                raise AssertionError('Refreshed evidence failed integrity or promoted historical observations.')
            if before and (before['ready'] or not before['assistant_review_stale']):
                raise AssertionError('Changed-source review was silently reused.')
            if stale_audit and stale_audit['exit_code'] == 0:
                raise AssertionError('The old assistant review passed after its source changed.')
            stages.append(dict(stage=name, full_source_chars=len(source),
                selection_prompt_chars=prepared['total_prompt_chars'], handoff_chars=len(text),
                selected_messages=len(selected), available_messages=len(packet['records']),
                old_bundle_audit_exit_code=stale_audit['exit_code'] if stale_audit else None,
                before_refresh_ready=before['ready'] if before else None,
                assistant_review_stale=before['assistant_review_stale'] if before else None,
                refreshed_ready=manifest['ready'], refreshed_audit_exit_code=audit['exit_code'],
                both_arms_retain_expected_evidence=True, verification=manifest['verification']))
        return dict(synthetic_only=True, stages=stages,
            total_full_source_chars=sum(s['full_source_chars'] for s in stages),
            total_selection_plus_handoff_chars=sum(s['selection_prompt_chars'] + s['handoff_chars'] for s in stages),
            limits='Authored relevance and evidence-presence controls only. The complete-source baseline is refreshed '
                   'at every stage and has the same evidence. No receiving reader, semantic correctness score, '
                   'tokens, elapsed investigation time, native capture, uniqueness, or demand was measured.')


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
