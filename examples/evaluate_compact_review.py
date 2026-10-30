"""Measure complete review-preparation commands using synthetic exports only."""

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

from agent_sessions.analysis.review_encoding import expand
from agent_sessions.analysis.selection_import import read_selection_packet
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer

PROJECT = '/workspace/synthetic-review'


def fixture(archive, case, sources, messages):
    repeated = ('Historical reference only. ' + 'The fictional alternatives remain unresolved. ' * 16).strip()
    for number in range(sources):
        records = []
        for ordinal in range(messages):
            unique = (f'Fictional source {number}, observation {ordinal}. ' +
                      'A distinct example describes a proposed option. ' * 16).strip()
            body = repeated if case == 'repeated' or (case == 'mixed' and ordinal % 3) else unique
            records.append(Message(role='user' if ordinal % 2 else 'assistant', text=body))
        session = Session(id=f'synthetic-{number:04d}', agent=Agent.CURSOR if number % 2 else Agent.CODEX,
                          cwd=PROJECT, messages=records)
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')


def verify_display(directory, packet):
    """Check actual serialized prompts against every retained packet occurrence."""
    expected = {(r['session_id'], r['section'], r['paragraph']['start_line']): r for r in packet['records']}
    observed = []
    if len((directory / 'review-prompt.txt').read_text()) > packet['max_prompt_chars']:
        raise ValueError('The routing prompt exceeds its budget.')
    for name in packet.get('batches', {}) or ['review-prompt.txt']:
        text = (directory / name).read_text()
        if len(text) > packet['max_prompt_chars']:
            raise ValueError('A displayed prompt exceeds its budget.')
        _, separator, body = text.partition('\n\n[\n')
        decoded = json.loads('[\n' + body) if separator else expand(json.loads(text.rsplit('\n\n', 1)[1]))
        for source in decoded:
            for section in source['sections']:
                for paragraph in section['paragraphs']:
                    key = (source['session_id'], section['section'], paragraph['start_line'])
                    record = expected[key]
                    if any(source[field] != record[field] for field in ('agent', 'cwd', 'project_slug')):
                        raise ValueError('Displayed source identity changed.')
                    if section['role'] != record['role'] or any(paragraph[field] != record['paragraph'][field]
                            for field in ('text', 'start_line', 'end_line')):
                        raise ValueError('Displayed paragraph or role changed.')
                    if paragraph.get('origin_hint', 'unattributed') != record.get('origin_hint', 'unattributed'):
                        raise ValueError('Displayed origin hint changed.')
                    observed.append(key)
    if observed != list(expected) or len(observed) != len(packet['records']):
        raise ValueError('Displayed occurrence order or coverage differs from the packet.')
    return True


def evaluate(sources=24, messages=40, repeats=3, budget=6000):
    if any(type(n) is not int or n < 1 for n in (sources, messages, repeats)) or type(budget) is not int or budget < 1500:
        raise ValueError('Use positive fixture sizes and a budget of at least 1500 characters.')
    rows = []
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-review-scale-') as temporary:
        root = Path(temporary)
        for case in ('unique', 'repeated', 'mixed'):
            archive = root / case / 'exports'
            fixture(archive, case, sources, messages)
            samples = {'ordinary': [], 'adaptive': []}
            details, previous_ids = {}, {}
            baseline_records = None
            for repetition in range(repeats):
                order = ('ordinary', 'adaptive') if repetition % 2 == 0 else ('adaptive', 'ordinary')
                for mode in order:
                    output = root / case / f'{mode}-{repetition}'
                    argv = [sys.executable, '-m', 'agent_sessions', 'handoff', 'prepare-review',
                            'fictional review', '-d', str(archive), '-o', str(output), '--project', PROJECT,
                            '--max-prompt-chars', str(budget), '--batch-review']
                    if mode == 'adaptive':
                        argv.append('--compact-review')
                    started = time.perf_counter()
                    result = subprocess.run(argv, capture_output=True, text=True, check=True)
                    samples[mode].append(time.perf_counter() - started)
                    report = json.loads(result.stdout)
                    packet = read_selection_packet(output)
                    verify_display(output, packet)
                    if mode in previous_ids and previous_ids[mode] != packet['review_id']:
                        raise ValueError('Unchanged preparation produced a different review identity.')
                    previous_ids[mode] = packet['review_id']
                    retained = {json.dumps(r, sort_keys=True, ensure_ascii=False) for r in packet['records']}
                    if mode == 'ordinary':
                        baseline_records = retained
                    elif baseline_records is not None and not baseline_records <= retained:
                        raise ValueError('Adaptive preparation dropped ordinary evidence.')
                    texts = [(output / name).read_text() for name in packet['batches']]
                    routing_chars = len((output / 'review-prompt.txt').read_text())
                    if (report['total_prompt_chars'] != routing_chars + sum(map(len, texts)) or
                            report['largest_prompt_chars'] != max([routing_chars, *map(len, texts)])):
                        raise ValueError('Reported input size differs from the actual prompt files.')
                    details[mode] = dict(records=len(packet['records']), omissions=len(packet['omissions']),
                        batches=len(texts), total_chars=report['total_prompt_chars'],
                        compact_batches=sum('"texts":[' in text for text in texts),
                        encoding=report.get('review_encoding'), display_verified=True)
            if details['adaptive']['total_chars'] > details['ordinary']['total_chars']:
                raise ValueError('Chosen adaptive plan is larger than ordinary preparation.')
            if details['adaptive']['omissions'] > details['ordinary']['omissions']:
                raise ValueError('Chosen adaptive plan adds omissions.')
            if any(v['records'] + v['omissions'] != sources * messages for v in details.values()):
                raise ValueError('An input occurrence is not retained or explicitly omitted.')
            rows.append(dict(case=case, source_count=sources, input_paragraphs=sources * messages,
                             results=details, cli_runs_seconds=samples,
                             median_cli_seconds={mode: statistics.median(values) for mode, values in samples.items()}))
    return dict(synthetic_only=True, budget_chars=budget, repeats=repeats, cases=rows,
        limits='New Python process per measured CLI call; includes startup, both adaptive plans, writes and selection. '
               'Fixture export, post-command display verification and semantic review excluded. OS caches are not reset. '
               'Characters are not tokens, cost, or reviewer effort. Omissions remain incomplete input, not readiness.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=int, default=24)
    parser.add_argument('--messages', type=int, default=40)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--budget', type=int, default=6000)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.sources, args.messages, args.repeats, args.budget), indent=2))
