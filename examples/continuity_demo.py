"""Demonstrate evidence loss and source drift using invented conversations.

Run after installing this package. Output defaults to a new private temporary
directory. This demo never reads developer history, changes hooks, or uploads.
"""

import argparse
import json
import tempfile
from pathlib import Path

from agent_sessions.analysis.continuity import (
    audit_bundle, compile_handoff, pin_requirement, write_bundle, review_requirement,
)
from agent_sessions.analysis.handoff import build_handoff
from agent_sessions.analysis.search import search_archive
from agent_sessions.cli import export_session
from agent_sessions.models import Agent, Message, Session


def run(output: Path):
    archive = output / 'exports'
    sessions = [
        Session(id='synthetic-cache', agent=Agent.CODEX, title='Example cache discovery', messages=[
            Message(role='user', text='Review the example cache plan.'),
            Message(role='assistant', text='Proposal: Use a queue for the example cache.\n'
                    'Verified: All checks passed.')]),
        Session(id='synthetic-scope', agent=Agent.CURSOR, title='Scope clarification', messages=[
            Message(role='user', text='Clarify the allowed work.'),
            Message(role='assistant', text='Discovery only. Do not implement or publish.\n'
                    'Open question: Should manual exclusions survive synchronization?')]),
        Session(id='synthetic-correction', agent=Agent.CLAUDE, title='Timing correction', messages=[
            Message(role='assistant', text='Correction: The timing is a proposed target, not a guarantee.')]),
    ]
    for session in sessions:
        export_session(session, archive)
    results = search_archive(archive, 'discovery publish')
    requirements = output / 'handoff-requirements.json'
    pin_requirement(archive, requirements, 'scope', 'synthetic-scope', 2,
                    'Discovery only. Do not implement or publish.')
    pin_requirement(archive, requirements, 'unresolved', 'synthetic-scope', 2,
                    'Should manual exclusions survive synchronization?')
    pin_requirement(archive, requirements, 'timing', 'synthetic-correction', 1,
                    'The timing is a proposed target, not a guarantee.')
    baseline = build_handoff(archive, 'example cache', last=3)
    small_text, small_manifest = compile_handoff(archive, 'example cache', requirements, max_chars=20)
    write_bundle(output / 'small-budget', small_text, small_manifest)
    text, manifest = compile_handoff(archive, 'example cache', requirements)
    write_bundle(output / 'handoff', text, manifest)
    audit = audit_bundle(output / 'handoff', archive)
    sessions[0].messages.append(Message(role='assistant', text='A separate unrelated follow-up.'))
    export_session(sessions[0], archive)
    unrelated = audit_bundle(output / 'handoff', archive)
    challenge = Session(id='synthetic-reopened', agent=Agent.CURSOR, messages=[Message(role='assistant', text=
        'Correction: Replace "Discovery only. Do not implement or publish." with "Implementation is proposed next.".')])
    export_session(challenge, archive)
    reopened = audit_bundle(output / 'handoff', archive)
    draft_text, draft_manifest = compile_handoff(archive, 'example cache', requirements)
    write_bundle(output / 'review-draft', draft_text, draft_manifest)
    for item in draft_manifest['requirements']:
        for candidate in item.get('unreviewed_candidates', []):
            review_requirement(archive, requirements, item['id'], candidate['review_id'],
                               'Synthetic review: keep both statements. The replacement is an unapproved proposal.')
    reviewed_text, reviewed_manifest = compile_handoff(archive, 'example cache', requirements)
    write_bundle(output / 'reviewed-handoff', reviewed_text, reviewed_manifest)
    reviewed = audit_bundle(output / 'reviewed-handoff', archive)
    # Alter this demo's synthetic export to demonstrate later source drift.
    changed = archive / 'synthetic-correction.md'
    changed.write_text(changed.read_text().replace('proposed target', 'revised proposal'))
    drift = audit_bundle(output / 'reviewed-handoff', archive)
    result = dict(synthetic_only=True, search_hits=results['total_hits'],
                  baseline_retains_scope='Discovery only. Do not implement or publish.' in baseline,
                  small_budget_passed=small_manifest['coverage_passed'],
                  required_anchors_kept=sum(item['status'] == 'covered' for item in manifest['requirements']),
                  audit_before_change=audit['exit_code'], audit_after_change=drift['exit_code'],
                  unrelated_append_audit=unrelated['exit_code'], cross_agent_challenge_audit=reopened['exit_code'],
                  explicit_review_audit=reviewed['exit_code'],
                  reported_results_remain_unchecked=manifest['verification'] == 'not_checked')
    expected = dict(baseline_retains_scope=False, small_budget_passed=False, required_anchors_kept=3,
                    audit_before_change=0, audit_after_change=1, unrelated_append_audit=0,
                    cross_agent_challenge_audit=1, explicit_review_audit=0, reported_results_remain_unchecked=True)
    if any(result[key] != value for key, value in expected.items()):
        raise SystemExit('Synthetic continuity acceptance failed: ' + json.dumps(result))
    print(json.dumps(result, indent=2))
    print(f'Inspect the synthetic bundles in {output}')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New directory for synthetic demo files')
    args = parser.parse_args()
    destination = args.output or Path(tempfile.mkdtemp(prefix='agent-sessions-continuity-'))
    if args.output:
        destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    run(destination)
