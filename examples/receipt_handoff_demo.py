"""Retain an independent synthetic receipt as mandatory, unverified evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from agent_sessions.analysis.continuity import pin_requirement, compile_handoff, write_bundle, audit_bundle
from agent_sessions.analysis.search import search_archive
from agent_sessions.models import Agent, Session, Message, ToolResult
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


def evaluate(receipt_report=None):
    receipt = dict(synthetic_only=True, hook_event_name='postToolUse', conversation_id='synthetic-conversation',
                   generation_id='synthetic-generation', tool_use_id='synthetic-call', tool_name='Shell',
                   tool_input={'command': 'fictional-check'},
                   tool_output='{"exitCode":0,"stdout":"SYNTHETIC_INNER_ERROR: inconclusive"}')
    report_digest = None
    if receipt_report is not None:
        raw = Path(receipt_report).read_bytes()
        report = json.loads(raw)
        if report.get('synthetic_only') is not True:
            raise ValueError('This demonstration accepts synthetic reports only.')
        receipt = next(r for r in report['receipts'] if 'SYNTHETIC_INNER_ERROR' in r.get('tool_output', ''))
        report_digest = hashlib.sha256(raw).hexdigest()
    payload = json.dumps(receipt, indent=2)
    claim = 'The fictional check is fixed. This is an unverified historical claim.'
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-receipt-handoff-') as temporary:
        root = Path(temporary)
        archive = root / 'exports'
        requirements = root / 'private' / 'requirements.json'
        # The envelope is independent evidence, not an inferred native call/result join.
        session = Session(id='synthetic-receipt-evidence', agent=Agent.CURSOR,
                          title='Authored receipt handoff exercise', messages=[
            Message(role='user', text='Investigate the fictional check using historical evidence only.'),
            Message(role='assistant', text=claim),
            Message(role='tool', text='', tool_results=[ToolResult(payload, receipt['tool_use_id'])])])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
        found = search_archive(archive, 'SYNTHETIC_INNER_ERROR', view='evidence', role='tool')
        if found['total_hits'] != 1:
            raise AssertionError('Expected one independent receipt source.')
        hit = found['hits'][0]
        pin_requirement(archive, requirements, 'receipt', session.id, hit['message'],
                        'SYNTHETIC_INNER_ERROR', view='evidence')
        pin_requirement(archive, requirements, 'historical-claim', session.id, 2, claim, view='evidence')
        text, manifest = compile_handoff(archive, 'fictional-check', requirements)
        if not manifest['ready'] or payload not in text or claim not in text or manifest['verification'] != 'not_checked':
            raise AssertionError('Required evidence was omitted or promoted to verification.')
        bundle = root / 'bundle'
        write_bundle(bundle, text, manifest)
        audit = audit_bundle(bundle, archive)
        if audit['exit_code'] != 0:
            raise AssertionError('Unchanged raw evidence did not audit.')
        baseline = (archive / f'{session.id}.md').read_text()
        if payload not in baseline or claim not in baseline:
            raise AssertionError('The complete-source baseline must retain the same evidence.')
        _, bounded = compile_handoff(archive, 'fictional-check', requirements, max_chars=20)
        if bounded['ready']:
            raise AssertionError('An insufficient evidence budget was accepted.')
        session.messages[-1].tool_results[0].content += '\nChanged receipt fixture.'
        MarkdownRenderer.write(session, archive)
        changed = audit_bundle(bundle, archive)
        if changed['exit_code'] == 0:
            raise AssertionError('Changed receipt evidence passed the old bundle audit.')
        return dict(synthetic_only=True, supplied_report_sha256=report_digest,
                    required_roles=[r['role'] for r in manifest['requirements']],
                    whole_receipt_retained=True, historical_claim_retained=True,
                    unchanged_audit='pass', changed_receipt_audit='fail', insufficient_budget_ready=False,
                    verification=manifest['verification'], handoff_chars=len(text), full_source_chars=len(baseline),
                    full_source_retains_same_evidence=True,
                    limits='Independent authored receipt envelope; no native transcript join or normal agent session. Gates check retained evidence, not a verified fix, receiving-reader quality, investigation time, uniqueness, or commercial value.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt-report', type=Path, help='Optional synthetic native component probe output')
    args = parser.parse_args()
    print(json.dumps(evaluate(args.receipt_report), indent=2))
