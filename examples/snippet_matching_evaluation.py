"""Compare literal search and candidate snippet matching on invented traces.

This measures candidate filtering, not execution attribution, diagnosis time,
model quality, or a production failure. No snippets are executed.
"""

import ast
import json
import re
import tempfile
from pathlib import Path

from agent_sessions.analysis.search import search_archive
from agent_sessions.analysis.transcript import rendered_messages
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

BAD = 'print(entry.caption)'
GOOD = 'print(entry.title)'


def code(statement):
    return 'A supplied example:\n\n```python\n' + statement + '\n```'


def trace(statement):
    return 'Captured output:\n\n```text\nTraceback (most recent call last):\n---> 1 ' + statement + '\nAttributeError: missing caption\n```'


CASES = [
    ('single_prior', [('assistant', code(BAD)), ('user', trace(BAD))], [1]),
    ('revised_then_old_failure', [('assistant', code(BAD)), ('assistant', code(GOOD)), ('user', trace(BAD))], [1]),
    ('repeated_prior', [('assistant', code(BAD)), ('assistant', code(BAD)), ('user', trace(BAD))], [1, 2]),
    ('future_only', [('user', trace(BAD)), ('assistant', code(BAD))], []),
    ('user_supplied_only', [('user', code(BAD)), ('user', trace(BAD))], []),
    ('format_change', [('assistant', code('print( entry.caption )')), ('user', trace(BAD))], [1]),
    ('different_variable', [('assistant', code('print(widget.caption)')), ('user', trace(BAD))], []),
    ('prose_only', [('assistant', 'The phrase print(entry.caption) is discussed, with no supplied code.'), ('user', trace(BAD))], []),
]


def normal(statement):
    try:
        return ast.dump(ast.parse(statement.strip()), include_attributes=False)
    except (SyntaxError, ValueError):
        return None


def prior_candidates(messages, report_index):
    report = messages[report_index]['text']
    match = re.search(r'^\s*-+>\s*\d+\s+(.+)$', report, re.M)
    if not match:
        return []
    target = normal(match.group(1))
    if target is None:
        return []
    found = []
    for index, message in enumerate(messages[:report_index], 1):
        if message['role'] != 'Assistant' or message['phase']:
            continue
        for block in re.findall(r'^```python\s*\n(.*?)^```', message['text'], re.M | re.S):
            for line in block.splitlines():
                if normal(line) == target:
                    found.append(index)
    return found


def evaluate(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive = root / 'exports'
    results = []
    for name, texts, expected in CASES:
        sid = 'synthetic-' + name
        project = '/workspace/' + sid
        session = Session(id=sid, agent=Agent.CODEX, cwd=project,
                          messages=[Message(role=role, text=body) for role, body in texts])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')
        source = (archive / (sid + '.md')).read_text()
        messages = rendered_messages(source)
        failure = next(i for i, message in enumerate(messages) if 'Traceback (most recent call last):' in message['text'])
        literal = [i for i, message in enumerate(messages, 1) if 'caption' in message['text']]
        exact = [i for i, message in enumerate(messages[:failure], 1)
                 if message['role'] == 'Assistant' and BAD in message['text']]
        actual = prior_candidates(messages, failure)
        evidence = search_archive(archive, 'caption', projects=[project], view='evidence', limit=100)
        dialogue = search_archive(archive, 'caption', projects=[project], limit=100)
        for hit in evidence['hits']:
            if source[hit['source_quote_start']:hit['source_quote_end']] != hit['quote']:
                raise ValueError('A search quote no longer matches the source.')
        results.append(dict(case=name, expected_prior_code_messages=expected, candidate_messages=actual,
                            candidate_set_matches=actual == expected,
                            literal_message_hits=len(literal), prior_literal_message_hits=exact,
                            evidence_hits=evidence['total_hits'], dialogue_hits=dialogue['total_hits'],
                            attribution='ambiguous' if len(actual) > 1 else 'single candidate' if actual else 'unattributed'))
    return dict(synthetic_only=True, cases=results,
                limits=['Author-defined labels and one narrow Python traceback shape.',
                        'AST comparison checks syntax shape, not execution, authorship, or semantic equivalence.',
                        'A prior match is only a candidate, never proof the snippet was executed.',
                        'No human effort, diagnosis time, causal accuracy, or commercial value is measured.'])


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='agent-sessions-snippet-matching-') as temporary:
        print(json.dumps(evaluate(Path(temporary)), indent=2))
