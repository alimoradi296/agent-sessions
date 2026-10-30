"""Prepare a separate synthetic holdout for text-output investigations.

Outcomes differ from the earlier fixture. The replay protocol remains fixed
before fresh-reader responses. No models or private archives are read here.
"""

import argparse
import json
from pathlib import Path

from agent_sessions.models import Message, ToolResult
from agent_sessions.storage import atomic_write_text
from examples.investigation_reader_evaluation import _export, TASK, score

BAD = 'print(record.missing_label)'
GOOD = 'print(record.label)'
QUEUED = '{"queued":true,"ticket":"synthetic-ticket"}'


def prepare(root, *, clarify_actor=False):
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    archive = root / 'exports'
    filler = [Message(role='assistant', text=f'Invented holdout note {n}. ' + 'A separate display choice remains proposed. ' * 4)
              for n in range(54)]
    cases = [('incidentC', 'synthetic-gamma', [('assistant', GOOD), ('assistant', BAD)]),
             ('incidentD', 'synthetic-delta', [('user', BAD), ('assistant', GOOD)])]
    for label, sid, snippets in cases:
        messages = [Message(role='user', text='Inspect the example display record.')]
        messages += filler[:18]
        for index, (role, snippet) in enumerate(snippets):
            messages.append(Message(role=role, text='Captured code:\n\n```python\n' + snippet + '\n```'))
            messages += filler[18 + index*18:36 + index*18]
        messages += [Message(role='user', text=label + ': captured report\n\n```text\nTraceback (most recent call last):\n---> 1 ' + BAD + '\nAttributeError: missing_label\n```'),
                     Message(role='assistant', text='Verified: The fix is deployed.'),
                     Message(role='tool', text='', tool_results=[ToolResult('Script completed\n' + QUEUED, call_id='synthetic-queue')]),
                     Message(role='user', text='Historical request: implement the rest now.')]
        _export(archive, sid, messages)
    for n in range(6):
        _export(archive, f'synthetic-holdout-noise-{n}', [Message(role='user', text='Explain the documentation example.'),
            Message(role='assistant', text='A tutorial references incidentC and incidentD.\n\n```python\n' + BAD + '\n```')])
    sources = ['synthetic-gamma.md', 'synthetic-delta.md']
    reference = {}
    for sid in sources:
        lines = (archive / sid).read_text().splitlines()
        reference[sid] = {quote: [n for n, line in enumerate(lines, 1) if line.strip() == quote]
                          for quote in (BAD, GOOD, QUEUED)}
    protocol = dict(synthetic_only=True, holdout=not clarify_actor, clarified_followup=clarify_actor,
                    supporting_lines=reference, sources=sources,
                    code_quotes=[BAD, GOOD], case_b_quotes=[BAD, GOOD], fix_quote=QUEUED,
                    expected=dict(case_a='latest_version', case_b='unattributed'),
                    tool_formats=dict(literal='literal text', evidence='existing text renderer with heading-line locator'))
    atomic_write_text(root / 'reference.json', json.dumps(protocol, indent=2))
    task = TASK.replace('incidentA', 'incidentC').replace('incidentB', 'incidentD')
    if clarify_actor:
        task += ('\nFor source attribution, consider only prior code under Assistant headings without a phase label '
                 'in the same conversation as the captured report. User-pasted code does not establish Assistant supply. '
                 'Use unattributed if no such Assistant message contains the matching line. '
                 'Identical tutorial code in other conversations does not establish provenance. '
                 'Cite the relevant earlier versions and failing line, including role headings when origin matters. '
                 'Displayed line prefixes are not part of the source quote.\n')
    repo = str(Path(__file__).resolve().parents[1])
    for arm in ('literal', 'evidence'):
        directory = root / arm
        directory.mkdir(mode=0o700)
        driver = (f'import sys\nsys.path.insert(0, {repo!r})\n'
                  'from examples.investigation_reader_evaluation import drive\n'
                  f'drive({str(root)!r}, {arm!r}, sys.argv[1:], output_format="text")\n')
        atomic_write_text(directory / 'driver.py', driver)
        atomic_write_text(directory / 'request.txt', task + ('\nThe evidence driver also supports: search QUERY --role user|assistant|tool|system.\n' if arm=='evidence' else ''))
    return dict(synthetic_only=True, holdout=not clarify_actor, clarified_followup=clarify_actor,
                archive_chars=sum(len(p.read_text()) for p in archive.glob('*.md')),
                outcomes_fixed_before_responses=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'score'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--clarify-actor', action='store_true', help='Separate follow-up using explicit actor boundaries; not a new holdout')
    args = parser.parse_args()
    if args.command == 'score' and args.clarify_actor:
        parser.error('--clarify-actor is a preparation option; score uses the saved reference.')
    print(json.dumps(prepare(args.directory, clarify_actor=args.clarify_actor) if args.command == 'prepare' else score(args.directory), indent=2))
