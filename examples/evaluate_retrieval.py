"""Evaluate the small labeled synthetic retrieval set in an isolated archive."""

import json
import argparse
import hashlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from agent_sessions.analysis.search import search_archive, render_search
from agent_sessions.analysis.transcript import conversation_sections, rendered_messages
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


def measure_broad_queries(archive, view):
    """Measure broad-query output; grouping is an experiment, not a CLI format."""
    measurements = []
    shared = ('session_id', 'agent', 'title', 'project', 'project_metadata', 'date', 'date_source',
              'source_path', 'source_sha256')
    for limit in (3, 100):
        started = time.perf_counter()
        result = subprocess.run([sys.executable, '-m', 'agent_sessions', 'search', 'historical',
                                 '-d', str(archive), '--view', view, '--limit', str(limit), '--json'],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
        elapsed = time.perf_counter() - started
        report = json.loads(result.stdout)
        sources, hits, source_text, cleaned_sections = {}, [], {}, {}
        for hit in report['hits']:
            sid = hit['session_id']
            if sid not in source_text:
                raw = Path(hit['source_path']).read_bytes()
                if hashlib.sha256(raw).hexdigest() != hit['source_sha256']:
                    raise ValueError('A measured source changed during quote validation.')
                source_text[sid] = raw.decode()
                if view == 'dialogue':
                    cleaned_sections[sid] = conversation_sections(source_text[sid])
            text = source_text[sid]
            if view == 'evidence':
                quote = text[hit['source_quote_start']:hit['source_quote_end']]
            else:
                section = cleaned_sections[sid][hit['section'] - 1][1]
                quote = section[hit['quote_start']:hit['quote_end']]
            if quote != hit['quote']:
                raise ValueError('The measured quote does not match its source coordinates.')
            source = {key: hit[key] for key in shared}
            if sid in sources and sources[sid] != source:
                raise ValueError('Inconsistent source metadata cannot be grouped losslessly.')
            sources[sid] = source
            hits.append(dict(source=sid, **{key: value for key, value in hit.items() if key not in shared}))
        grouped = dict(report, layout='source_table_v1', source_table=sources, hits=hits)
        restored = {key: value for key, value in grouped.items() if key not in ('layout', 'source_table', 'hits')}
        restored['hits'] = [dict(sources[hit['source']], **{k: v for k, v in hit.items() if k != 'source'}) for hit in hits]
        if restored != report:
            raise ValueError('The experimental layout did not preserve the complete search report.')
        compact = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
        measurements.append(dict(limit=limit, seconds=round(elapsed, 4), total_hits=report['total_hits'],
                                 returned=len(report['hits']), pretty_json_chars=len(result.stdout),
                                 minified_json_chars=compact(report), grouped_json_chars=compact(grouped),
                                 text_chars=len(render_search(report)), quotes_verified=True, lossless_grouping_verified=True))
    return measurements


def measure_scale(directory: Path, sources=1000, messages=40, *, view='dialogue', mixed_sizes=False, broad_query=False):
    """Time complete CLI commands; fixtures, source refresh, and query are local."""
    if sources < 1 or messages < 1:
        raise ValueError('Source and message counts must be positive.')
    archive = directory / 'exports'
    archive.mkdir()
    rows = []
    initial_passages = 0
    for n in range(sources):
        bodies = [Message(role='user' if i % 2 == 0 else 'assistant',
                  text=f'Synthetic session {n} passage {i}. ' +
                       'Ordinary implementation discussion remains historical evidence. ' * 4 +
                       (' continuationneedle' if n == 0 and i == 0 else '')) for i in range(messages)]
        if mixed_sizes:
            for i, body in enumerate(bodies):
                body.text += ' Mixed-size historical discussion.' * (1, 4, 16, 64)[i % 4]
                if i and i % 11 == 0:
                    body.role = 'tool'
                elif i and i % 7 == 0:
                    body.text = '```text\n' + body.text + '\n```'
            if n == 0 and messages >= 3:
                bodies[1].text = '```python\nevidenceonlyneedle = 17\n```'
                bodies[2].role, bodies[2].text = 'tool', 'toolonlyneedle captured synthetic output'
        session = Session(id=f'synthetic-scale-{n:04}', agent=Agent.CODEX,
                          cwd='/workspace/example-project', messages=bodies)
        path = MarkdownRenderer.write(session, archive)
        raw = path.read_text()
        initial_passages += len(rendered_messages(raw) if view == 'evidence' else conversation_sections(raw))
        rows.append(JsonIndexRenderer.session_to_dict(session))
    (archive / 'sessions.json').write_text(json.dumps(dict(version=1, count=len(rows), sessions=rows)))
    measurements = []
    for label in ('cold', 'warm-1', 'warm-2', 'warm-3', 'changed-source'):
        if label == 'changed-source':
            path = archive / f'synthetic-scale-{sources - 1:04}.md'
            path.write_text(path.read_text() + '\n## User\n\nAn appended synthetic qualification.\n')
        started = time.perf_counter()
        result = subprocess.run([sys.executable, '-m', 'agent_sessions', 'search', 'continuationneedle',
                                 '-d', str(archive), '--json', '--limit', '3', '--view', view],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
        elapsed = time.perf_counter() - started
        report = json.loads(result.stdout)
        if report['total_hits'] != 1:
            raise ValueError('The measured query did not return the synthetic target.')
        expected_updated = sources if label == 'cold' else 1 if label == 'changed-source' else 0
        expected_passages = initial_passages + (label == 'changed-source')
        if report['index']['updated'] != expected_updated or report['index']['passages'] != expected_passages:
            raise ValueError('The measured refresh did not match the constructed source change.')
        measurements.append(dict(case=label, seconds=round(elapsed, 4), hits=report['total_hits'], index=report['index']))
    coverage = {}
    if mixed_sizes and messages >= 3:
        for query in ('evidenceonlyneedle', 'toolonlyneedle'):
            report = search_archive(archive, query, view=view)
            coverage[query] = report['total_hits']
            if report['total_hits'] != int(view == 'evidence'):
                raise ValueError('Search-view coverage differs from the constructed code and tool controls.')
    return dict(synthetic_only=True, sources=sources, initial_messages=sources * messages, view=view,
                broad_queries=measure_broad_queries(archive, view) if broad_query else [],
                mixed_sizes=mixed_sizes, initial_passages=initial_passages, evidence_controls=coverage,
                source_bytes=sum(p.stat().st_size for p in archive.glob('*.md')), measurements=measurements,
                limits='One local process sequence with OS caches uncontrolled. No model, TUI, '
                       'competitor runtime, or private archive. Not a large-archive compatibility guarantee.')


def evaluate(directory: Path):
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/retrieval_cases.json'
    dataset = json.loads(fixture.read_text(encoding='utf-8'))
    for source in dataset['sources']:
        session = Session(id=source['id'], agent=Agent(source['agent']), title='Synthetic conversation',
                          messages=[Message(role='assistant', text=source['text'])])
        MarkdownRenderer.write(session, directory)
        JsonIndexRenderer.update(session, directory / 'sessions.json')
    outcomes = []
    for case in dataset['queries']:
        result = search_archive(directory, case['query'], limit=3)
        ids = [hit['session_id'] for hit in result['hits']]
        rank = ids.index(case['expected_session']) + 1 if case['expected_session'] in ids else None
        outcomes.append(dict(query=case['query'], expected_session=case['expected_session'], rank=rank))
    return dict(synthetic_only=True, sources=len(dataset['sources']), queries=len(outcomes),
                recall_at_3=sum(item['rank'] is not None for item in outcomes) / len(outcomes),
                mean_reciprocal_rank_at_3=sum(1 / item['rank'] if item['rank'] else 0
                                              for item in outcomes) / len(outcomes), outcomes=outcomes,
                limitation='Eight lexical queries do not establish semantic retrieval or real-user usefulness.')


def measure_mutations(directory, sources=1000, messages=40, *, view='evidence', mixed_sizes=True, batch=400):
    """Exercise additions, replacements, and removals against a populated cache."""
    if not 1 <= batch < sources:
        raise ValueError('The mutation batch must be positive and smaller than the source count.')
    baseline = measure_scale(directory, sources, messages, view=view, mixed_sizes=mixed_sizes)
    archive = directory / 'exports'
    rows = json.loads((archive / 'sessions.json').read_text())['sessions']
    template = (archive / 'synthetic-scale-0001.md').read_text()
    count = lambda text: len(rendered_messages(text) if view == 'evidence' else conversation_sections(text))
    added_passages = batch * count(template)
    original_passages = baseline['measurements'][-1]['index']['passages']
    measurements = []
    for label in ('add', 'replace', 'remove'):
        if label == 'add':
            for n in range(batch):
                sid = f'synthetic-added-{n:04}'
                (archive / f'{sid}.md').write_text(template.replace('synthetic-scale-0001', sid))
                rows.append(dict(rows[1], id=sid, file=f'{sid}.md'))
        elif label == 'replace':
            for n in range(1, batch + 1):
                path = archive / f'synthetic-scale-{n:04}.md'
                path.write_text(path.read_text() + '\n## User\n\nmutationaddedneedle synthetic qualification.\n')
        else:
            for n in range(batch):
                (archive / f'synthetic-added-{n:04}.md').unlink()
            rows = [row for row in rows if not row['id'].startswith('synthetic-added-')]
        (archive / 'sessions.json').write_text(json.dumps(dict(version=1, count=len(rows), sessions=rows)))
        started = time.perf_counter()
        result = subprocess.run([sys.executable, '-m', 'agent_sessions', 'search', 'continuationneedle',
                                 '-d', str(archive), '--json', '--limit', '3', '--view', view],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
        elapsed = time.perf_counter() - started
        report = json.loads(result.stdout)
        expected = original_passages + (added_passages if label != 'remove' else 0) + (batch if label != 'add' else 0)
        if (report['total_hits'] != 1 or report['index']['passages'] != expected
                or report['index']['sessions'] != len(rows)
                or report['index']['updated'] != (batch if label != 'remove' else 0)
                or report['index']['removed'] != (batch if label == 'remove' else 0)):
            raise ValueError('Bulk refresh did not match the constructed archive mutation.')
        measurements.append(dict(case=label, seconds=round(elapsed, 4), index=report['index']))
    final = search_archive(archive, 'mutationaddedneedle', view=view, limit=100)
    if final['total_hits'] != batch:
        raise ValueError('The bulk replacements were not retained exactly once each.')
    return dict(synthetic_only=True, sources=sources, initial_messages=sources * messages, view=view,
                mixed_sizes=mixed_sizes, batch=batch, baseline=baseline, measurements=measurements,
                replacement_hits=final['total_hits'], limits=baseline['limits'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scale', action='store_true', help='Measure complete synthetic CLI searches instead of labeled recall')
    parser.add_argument('--sources', type=int, default=1000)
    parser.add_argument('--messages', type=int, default=40)
    parser.add_argument('--view', choices=('dialogue', 'evidence'), default='dialogue')
    parser.add_argument('--mixed-sizes', action='store_true')
    parser.add_argument('--broad-query', action='store_true', help='Also measure broad-query output and experimental lossless grouping')
    parser.add_argument('--bulk-mutations', action='store_true')
    parser.add_argument('--batch', type=int, default=400)
    args = parser.parse_args()
    if args.sources < 1 or args.messages < 1:
        parser.error('Source and message counts must be positive.')
    with tempfile.TemporaryDirectory(prefix='agent-sessions-retrieval-') as temporary:
        if args.bulk_mutations:
            result = measure_mutations(Path(temporary), args.sources, args.messages, view=args.view,
                                       mixed_sizes=args.mixed_sizes, batch=args.batch)
        else:
            result = measure_scale(Path(temporary), args.sources, args.messages, view=args.view,
                                   mixed_sizes=args.mixed_sizes, broad_query=args.broad_query) if args.scale else evaluate(Path(temporary))
        print(json.dumps(result, indent=2, ensure_ascii=False))
