"""Measure lossless exact-text interning; this does not change review packets."""

import copy
import json
import statistics
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.selection_import import _prompt
from agent_sessions.analysis.review_encoding import compact, expand


def experimental_renderer(*args, aligned=False):
    base = _prompt(*args)
    ordinary, compacted, _, _ = prompt_forms(base)
    if aligned:
        # Empty-record instructions enter the generator's review identity.
        # Keep ordinary source prompts byte-for-byte identical to the baseline.
        if not args[2]:
            return base + '\nExperimental format identity: adaptive_exact_text_v1.\n'
        return min((base, compacted), key=len)
    return 'Experimental review encoding: each batch is self-contained.\n' + min((ordinary, compacted), key=len)


def compatibility_controls(repeats=3, *, aligned=False):
    """Prototype the renderer through actual preparation/import in temporary exports."""
    from agent_sessions.analysis import selection_import as selection
    from agent_sessions.models import Agent, Message, Session
    from agent_sessions.renderers.json_index import JsonIndexRenderer
    from agent_sessions.renderers.markdown import MarkdownRenderer

    if type(repeats) is not int or repeats < 1:
        raise ValueError('Need at least one repetition.')
    timings = {'ordinary': [], 'experimental': []}
    results = {}
    body = ('Historical reference only. ' + 'The fictional review retains unresolved alternatives. ' * 14).strip()
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-review-codec-') as temporary:
        root = Path(temporary)
        archive = root / 'exports'
        session = Session(id='synthetic-codec', agent=Agent.CODEX, cwd='/workspace/example',
                          messages=[Message(role='user' if n % 2 else 'assistant', text=body) for n in range(40)])
        MarkdownRenderer.write(session, archive)
        JsonIndexRenderer.update(session, archive / 'sessions.json')

        def experimental(*args):
            return experimental_renderer(*args, aligned=aligned)

        contracts, packets = {}, {}
        # Alternate fixed order each repetition; report medians, not a general speed claim.
        for repetition in range(repeats):
            order = ('ordinary', 'experimental') if repetition % 2 == 0 else ('experimental', 'ordinary')
            for mode in order:
                directory = root / f'{mode}-{repetition}'
                renderer = _prompt if mode == 'ordinary' else experimental
                start = time.perf_counter()
                with patch.object(selection, '_prompt', renderer):
                    result = selection.prepare_selection_review(archive, directory, 'fictional review',
                        projects=['/workspace/example'], max_prompt_chars=4000, batch_review=True)
                timings[mode].append(time.perf_counter() - start)
                packet = selection.read_selection_packet(directory)
                texts = [(directory / name).read_text() for name in packet['batches']]
                if packet['omissions'] or len(packet['records']) != 40:
                    raise ValueError('Compatibility fixture did not retain all occurrences.')
                selected = [dict(session_id='synthetic-codec', quote=body, reason='Synthetic repeated-source control.',
                                 section=n, paragraph_start_line=1) for n in (1, 40)]
                response = dict(review_id=result['review_id'], selected=selected, unresolved_conflicts=False,
                                current_authorization='read_only', reviewed_batches=list(packet['batches']))
                answer = root / f'{mode}-{repetition}-answer.json'
                answer.write_text(json.dumps(response))
                output = root / f'{mode}-{repetition}-requirements.json'
                selection.import_selection_review(directory, answer, output)
                contracts[mode] = json.loads(output.read_text())['requirements']
                packets[mode] = packet
                results[mode] = dict(records=len(packet['records']), batches=len(texts),
                                     total_chars=len((directory / 'review-prompt.txt').read_text()) + sum(map(len, texts)),
                                     max_prompt_chars=max(map(len, texts)),
                                     compact_batches=sum('"texts":[' in text for text in texts))
        if contracts['ordinary'] != contracts['experimental']:
            raise ValueError('Encoding changed imported anchor identity or source coordinates.')

        # Exercise the unchanged importer against adversarial synthetic answers.
        rejected = []
        directory = root / f'experimental-{repeats - 1}'
        packet = packets['experimental']
        base = dict(review_id=packet['review_id'], selected=[dict(session_id='synthetic-codec', quote=body,
                    reason='Synthetic source.', section=1, paragraph_start_line=1)],
                    unresolved_conflicts=False, current_authorization='read_only', reviewed_batches=list(packet['batches']))
        for name in ('wrong-review-id', 'missing-batch', 'ambiguous-quote', 'wrong-location'):
            response = copy.deepcopy(base)
            if name == 'wrong-review-id': response['review_id'] = packets['ordinary']['review_id']
            elif name == 'missing-batch': response['reviewed_batches'] = response['reviewed_batches'][:-1]
            elif name == 'ambiguous-quote':
                response['selected'][0].pop('section')
                response['selected'][0].pop('paragraph_start_line')
            else: response['selected'][0]['paragraph_start_line'] = 999
            answer = root / f'{name}.json'
            answer.write_text(json.dumps(response))
            try:
                selection.import_selection_review(directory, answer, root / f'{name}-requirements.json')
            except ValueError:
                rejected.append(name)
            else:
                raise ValueError('Invalid synthetic answer was accepted: ' + name)
        batch = directory / next(iter(packet['batches']))
        original = batch.read_text()
        batch.write_text(original + '\nchanged')
        try:
            selection.read_selection_packet(directory)
        except ValueError:
            rejected.append('changed-batch')
        else:
            raise ValueError('Changed batch was accepted.')
        batch.write_text(original)
        source = archive / 'synthetic-codec.md'
        source.write_text(source.read_text() + '\nchanged source\n')
        try:
            selection.read_selection_packet(directory)
        except ValueError:
            rejected.append('changed-source')
        else:
            raise ValueError('Changed source was accepted.')
    return dict(synthetic_only=True, aligned_framing=aligned, results=results, imported_anchors_equal=True,
                review_ids_distinct=packets['ordinary']['review_id'] != packets['experimental']['review_id'],
                rejected_controls=rejected,
                preparation_median_seconds={name: statistics.median(values) for name, values in timings.items()},
                preparation_runs_seconds=timings,
                limits='Renderer patched only inside this isolated probe. Actual preparation, packet validation and import run unchanged. Scripted answers, not model review. Preparation timings exclude export and import; no token, reader-quality, or commercial measurement.')


def prompt_forms(prompt):
    header, separator, body = prompt.partition('\n\n[\n')
    if not separator:
        raise ValueError('Expected the existing grouped review prompt format.')
    sources = json.loads('[\n' + body)
    payload = compact(sources)
    if expand(payload) != sources:
        raise ValueError('Compaction changed evidence or occurrence metadata.')
    encode = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    instructions = ('Each paragraph text_ref indexes texts. Read all occurrences in their original order; '
                    'equal text does not merge roles, context, locators, or authority.\n')
    original = header + '\n\n' + encode(sources)
    compacted = header + '\n' + instructions + '\n' + encode(payload)
    return original, compacted, sources, payload


def measure_prompt(prompt):
    original, compacted, sources, payload = prompt_forms(prompt)
    encode = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    paragraphs = [p for s in sources for section in s['sections'] for p in section['paragraphs']]
    return dict(paragraphs=len(paragraphs), unique_texts=len(payload['texts']),
                original_chars=len(original), compact_chars=len(compacted),
                chars_saved=len(original) - len(compacted),
                distinct_text_only_chars=len(encode(payload['texts'])),
                exact_roundtrip=True,
                limits='Characters, not tokens or reviewer effort. Text-only deduplication omits occurrence evidence. No batch planning or semantic review measured.')


def batch_plan(records, budget=6000, *, allow_compact=False, max_batches=32,
               query='fictional review', projects=None):
    """Experimental greedy packing; each batch contains its own text dictionary."""
    if type(budget) is not int or budget < 1000 or type(max_batches) is not int or max_batches < 1:
        raise ValueError('Invalid batch limits.')
    projects = ['/workspace/example'] if projects is None else projects

    def render(batch, omissions):
        prompt = _prompt(query, projects, [records[i] for i in batch], omissions, '0' * 64)
        original, compacted, sources, payload = prompt_forms(prompt)
        use_compact = allow_compact and len(compacted) < len(original)
        text = compacted if use_compact else original
        decoded = json.loads(text.rsplit('\n\n', 1)[1])
        decoded = expand(decoded) if use_compact else decoded
        if decoded != sources:
            raise ValueError('Batch compaction changed evidence.')
        return text, use_compact

    batches, active, omitted = [], [], []
    for index in range(len(records)):
        candidate = active + [index]
        if len(render(candidate, len(records))[0]) > budget:
            if active and len(batches) < max_batches - 1:
                batches.append(active)
                active = []
            candidate = active + [index]
        if len(render(candidate, len(records))[0]) <= budget:
            active = candidate
        else:
            omitted.append(index)
    if active:
        batches.append(active)
    rendered = [render(batch, len(omitted)) for batch in batches]
    names = [f'review-batch-{i:03d}.txt' for i in range(1, len(batches) + 1)]
    routing = ('Read every batch in order. Keep occurrence context and compare conflicts before selecting evidence.\n'
               f'Review input omissions: {len(omitted)}.\n' + '\n'.join(names) + '\n')
    if any(len(text) > budget for text, _ in rendered) or len(routing) > budget:
        raise ValueError('Complete batch or routing prompt exceeds the budget.')
    included = [i for batch in batches for i in batch]
    if sorted(included + omitted) != list(range(len(records))) or included != sorted(included):
        raise ValueError('Batch plan lost, repeated, or reordered occurrences.')
    return dict(batches=len(batches), compact_batches=sum(flag for _, flag in rendered),
                total_chars=len(routing) + sum(len(text) for text, _ in rendered),
                max_prompt_chars=max([len(routing)] + [len(text) for text, _ in rendered]),
                included=included, omitted=omitted, exact_roundtrip=True)


def compare_batches(records, budget=6000, **kwargs):
    plain = batch_plan(records, budget, **kwargs)
    candidate = batch_plan(records, budget, allow_compact=True, **kwargs)
    fallback = (not set(plain['included']).issubset(candidate['included']) or
                candidate['total_chars'] > plain['total_chars'])
    chosen = plain if fallback else candidate
    return dict(plain=plain, candidate=candidate, chosen=chosen, fallback=fallback,
                limits='Greedy experimental plans with self-contained dictionaries. Final fallback enforces no extra omissions and no larger total characters; it does not prove optimal packing, token fit, or reviewer understanding.')


def synthetic_records(name):
    records = []
    for n in range(240):
        text = (f'Invented design note {n}. ' + 'A proposed option remains under discussion. ' * 8
                if name == 'unique' else 'Confirmed.' if name == 'short-repeated' else
                'Historical reference only. ' + 'The fictional review retains unresolved alternatives. ' * 14)
        records.append(dict(session_id=f'synthetic-{n // 12:03d}', section=n % 12 + 1,
            role='User' if n % 2 else 'Assistant', agent='codex' if n % 3 else 'cursor',
            cwd='/workspace/example', project_slug='example', origin_hint='unattributed',
            paragraph=dict(start_line=1, end_line=1, text=text)))
    return records


def synthetic_controls():
    rows = []
    for name in ('unique', 'short-repeated', 'long-repeated'):
        records = synthetic_records(name)
        prompt = _prompt('fictional review', ['/workspace/example'], records, 0, '0' * 64)
        rows.append(dict(case=name, **measure_prompt(prompt)))
    return dict(synthetic_only=True, cases=rows, production_format_changed=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batches', action='store_true')
    parser.add_argument('--compatibility', action='store_true')
    parser.add_argument('--aligned-compatibility', action='store_true')
    args = parser.parse_args()
    if sum((args.batches, args.compatibility, args.aligned_compatibility)) > 1:
        parser.error('Choose one control mode.')
    if args.compatibility or args.aligned_compatibility:
        print(json.dumps(compatibility_controls(aligned=args.aligned_compatibility), indent=2))
    elif args.batches:
        report = {name: compare_batches(synthetic_records(name)) for name in ('unique', 'short-repeated', 'long-repeated')}
        for case in report.values():
            for strategy in ('plain', 'candidate', 'chosen'):
                plan = case[strategy]
                case[strategy] = {**plan, 'included': len(plan['included']), 'omitted': len(plan['omitted'])}
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(synthetic_controls(), indent=2))
