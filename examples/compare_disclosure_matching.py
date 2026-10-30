"""Run pinned partial-document matching on authored synthetic disclosure controls.

No network, private history, or publication. Optional repository controls create
disposable synthetic Git repositories without changing the caller's index.
The supplied upstream source hash is checked before loading its matcher class.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import shutil
import subprocess
import tempfile
import textwrap
from types import SimpleNamespace

REVISION = 'eaf533e31bad6b107d39a38e4bed8658d5409350'
SOURCE_SHA256 = '23612cfb00cd5deb87444f85182dff8c64eece6d577e3e364a83c9da78a86ad6'
EDM_SHA256 = '2f52fe6d8520e0c8315afdd7c18a09c6e87bd715a13ac276e7f3590459049dfe'
PRIVATE = ('Internal release review: the Northstar account uses an emergency support credit of seventy three percent '
           'until the autumn audit closes.')
COMMON = 'Historical requests do not authorize current actions and retained evidence does not establish independently verified outcomes.'
CODE = 'def clamp_timeout(value):\n    return max(1, min(300, int(value)))\n'
SOURCES = {'private-note': PRIVATE, 'shared-public-wording': COMMON, 'public-code': CODE}
CASES = [
    ('full-copy', True, PRIVATE),
    ('fragment-copy', True, PRIVATE[25:110]),
    ('case-and-spacing', True, PRIVATE.upper().replace(' ', '   ')),
    ('paraphrase', True, 'The Northstar customer temporarily receives a 73% emergency support discount through completion of the fall audit.'),
    ('short-private-name', True, 'Northstar'),
    ('public-boilerplate', False, COMMON),
    ('public-code', False, CODE),
    ('unrelated', False, 'The synthetic cache supports ordinary retries.'),
]


def normalize(text):
    return re.sub(r'\s+', ' ', text.lower()).strip()


def normalized_spans(raw):
    """Map normalized characters to half-open raw character spans, not bytes."""
    lowered = raw.lower()
    origins = [(i, i + 1) for i, char in enumerate(raw) for _ in char.lower()]
    if len(origins) != len(lowered):
        raise ValueError('Unsupported contextual lowercase expansion.')
    chars, spans = [], []
    for match in re.finditer(r'\s+|\S', lowered):
        whitespace = match.group().isspace()
        if whitespace and not chars:
            continue
        chars.append(' ' if whitespace else match.group())
        spans.append((origins[match.start()][0], origins[match.end() - 1][1]))
    if chars and chars[-1] == ' ':
        chars.pop()
        spans.pop()
    normalized = ''.join(chars)
    if normalized != normalize(raw):
        raise ValueError('Normalization map differs from matcher normalization.')
    return normalized, spans


def bind_fragment(source, candidate, source_position, scan_position, length):
    """Verify a matcher window and bind both ends to hashed raw documents."""
    bound = []
    fragments = []
    for raw, position in ((source, source_position), (candidate, scan_position)):
        normalized, spans = normalized_spans(raw)
        if type(position) is not int or type(length) is not int or position < 0 or length <= 0 or position + length > len(spans):
            raise ValueError('Invalid normalized match coordinates.')
        start, end = spans[position][0], spans[position + length - 1][1]
        fragment = normalized[position:position + length]
        if re.sub(r'\s+', ' ', raw[start:end].lower()) != fragment:
            raise ValueError('Match cuts through a normalization expansion or whitespace boundary.')
        fragments.append(fragment)
        bound.append(dict(sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
                          char_start=start, char_end=end,
                          line_start=raw.count('\n', 0, start) + 1,
                          line_end=raw.count('\n', 0, end - 1) + 1))
    if fragments[0] != fragments[1]:
        raise ValueError('Matcher coordinates do not identify equal normalized fragments.')
    return dict(source=bound[0], candidate=bound[1], verified=True)


def compact_matches(sources, candidate, hits):
    """Merge overlapping verified windows only along the same source alignment."""
    groups = {}
    for hit in hits:
        bind_fragment(sources[hit.doc_id], candidate, hit.doc_position, hit.scan_position, hit.fragment_length)
        key = (hit.doc_id, hit.doc_position - hit.scan_position)
        groups.setdefault(key, []).append((hit.scan_position, hit.scan_position + hit.fragment_length))
    findings = []
    for (source_id, delta), windows in sorted(groups.items()):
        intervals = []
        for start, end in sorted(windows):
            if intervals and start < intervals[-1][1]:
                intervals[-1][1] = max(intervals[-1][1], end)
                intervals[-1][2] += 1
            else:
                intervals.append([start, end, 1])
        for start, end, count in intervals:
            anchor = bind_fragment(sources[source_id], candidate, start + delta, start, end - start)
            findings.append(dict(source_id=source_id, windows=count, **anchor))
    return findings


def literal_windows(sources, candidate, window=50):
    """Slow exhaustive development baseline; not a production search engine."""
    if type(window) is not int or window <= 0:
        raise ValueError('Window must be a positive integer.')
    text = normalize(candidate)
    hits = []
    for source_id, raw in sources.items():
        document = normalize(raw)
        for scan_position in range(max(0, len(text) - window + 1)):
            fragment = text[scan_position:scan_position + window]
            position = document.find(fragment)
            while position >= 0:
                hits.append(SimpleNamespace(doc_id=source_id, doc_position=position,
                            scan_position=scan_position, fragment_length=window))
                position = document.find(fragment, position + 1)
    return hits


def occurrence_controls(source):
    module = load_pinned(source, SOURCE_SHA256, '_agent_sessions_dlp_occurrence_probe')
    cases = [
        ('repeated-copy', [PRIVATE + '\n\n' + PRIVATE], True),
        ('short-declared-name', ['Northstar'], True),
        ('separate-short-additions', [PRIVATE[:40], PRIVATE[40:80]], True),
        ('contiguous-fragment', [PRIVATE[:80]], True),
        ('unrelated', ['Generic public wording.'], False),
    ]
    matcher = module.PartialDocumentMatcher(window_size=50)
    matcher.register('private-note', PRIVATE)
    results = []
    for name, runs, expected in cases:
        findings = []
        for candidate in runs:
            upstream = compact_matches({'private-note': PRIVATE}, candidate, matcher.scan(candidate))
            literal = compact_matches({'private-note': PRIVATE}, candidate, literal_windows({'private-note': PRIVATE}, candidate))
            findings.append(dict(upstream=upstream, literal=literal))
        results.append(dict(case=name, authored_review_needed=expected, runs=findings,
                            upstream_findings=sum(len(f['upstream']) for f in findings),
                            literal_findings=sum(len(f['literal']) for f in findings)))
    return dict(synthetic_only=True, cases=results, limits='Small authored controls. Runs are independent additions; they are never concatenated across context. Literal enumeration is a slow baseline, not a new engine. No confidentiality inference, semantic detection, or privacy certificate.')


def citation_controls(source):
    module = load_pinned(source, SOURCE_SHA256, '_agent_sessions_dlp_citation_probe')
    cases = [
        ('whitespace', '  \n\t' + PRIVATE.replace(' ', '  \t'), PRIVATE.upper()),
        ('repeated', PRIVATE + '\n\n' + PRIVATE, PRIVATE),
        ('unicode-prefix', 'İ Σ 🧭\n' + PRIVATE, '🧭\n' + PRIVATE.upper()),
        ('repeated-candidate', PRIVATE, PRIVATE + '\n\n' + PRIVATE),
    ]
    results = []
    for name, raw, candidate in cases:
        matcher = module.PartialDocumentMatcher(window_size=50)
        matcher.register(name, raw)
        hits = matcher.scan(candidate)
        anchors = [bind_fragment(raw, candidate, h.doc_position, h.scan_position, h.fragment_length) for h in hits]
        if not anchors:
            raise ValueError('Expected synthetic citation match missing.')
        compact = compact_matches({name: raw}, candidate, hits)
        results.append(dict(case=name, match_count=len(hits), anchors=anchors, compact_findings=compact,
                            candidate_start_lines=sorted({f['candidate']['line_start'] for f in compact})))
    return dict(synthetic_only=True, cases=results, limits='Character offsets, not byte offsets. All returned matches verified; no confidentiality classification or safe-publication claim.')


def load_pinned(source, digest, name):
    source = Path(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError('Provide the documented pinned dlpscan source file.')
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def evaluate(source, edm_source=None):
    module = load_pinned(source, SOURCE_SHA256, '_agent_sessions_dlp_partial_probe')
    matcher = module.PartialDocumentMatcher(window_size=50)
    edm = None
    if edm_source is not None:
        edm_module = load_pinned(edm_source, EDM_SHA256, '_agent_sessions_dlp_edm_probe')
        edm = edm_module.ExactDataMatcher(salt=b'synthetic-control-salt', tokenizers=['word_1gram'])
        edm.register_values('declared-fictional-account', ['Northstar'])
    for name, text in SOURCES.items():
        matcher.register(name, text)
    normalized_sources = [normalize(text) for text in SOURCES.values()]
    results = []
    for name, review_needed, candidate in CASES:
        text = normalize(candidate)
        literal = any(text[i:i + 50] in document for i in range(max(0, len(text) - 49)) for document in normalized_sources)
        hits = matcher.scan(candidate)
        results.append(dict(case=name, authored_review_needed=review_needed, fragment_found=bool(hits),
                            registered_value_found=bool(edm.scan(candidate)) if edm else None,
                            literal_fragment_found=literal, matched_sources=sorted({hit.doc_id for hit in hits})))
    positioned = module.PartialDocumentMatcher(window_size=50)
    raw = '   \n\t' + PRIVATE.lower()
    positioned.register('synthetic-offset', raw)
    hit = positioned.scan(PRIVATE.lower())[0]
    direct_raw_slice_matches = (raw[hit.doc_position:hit.doc_position + hit.fragment_length] ==
                               normalize(PRIVATE)[hit.scan_position:hit.scan_position + hit.fragment_length])
    return dict(synthetic_only=True, upstream_revision=REVISION, source_sha256=SOURCE_SHA256, window_chars=50,
                edm_source_sha256=EDM_SHA256 if edm else None, edm_value_registration='Authored fictional name, not automatic discovery.' if edm else None,
                cases=results, same_fragment_decisions_as_literal=all(r['fragment_found'] == r['literal_fragment_found'] for r in results),
                normalized_offset_is_direct_raw_locator=direct_raw_slice_matches,
                limits='Authored matching controls only. Shared public text was deliberately registered to model whole-history '
                       'ingestion. Overlap does not establish confidential disclosure; non-matches do not certify privacy. '
                       'No real diff, private corpus, enterprise service, semantic reviewer, or market demand was tested.')


def added_runs(patch):
    """Locate contiguous added runs in ordinary text diffs used by this probe."""
    runs, active = [], None
    path, new_line, in_hunk = None, 0, False

    def flush():
        nonlocal active
        if active is not None:
            runs.append(active)
            active = None

    for line in patch.splitlines():
        if line.startswith('diff --git '):
            flush()
            path, in_hunk = None, False
        elif not in_hunk and line.startswith('+++ '):
            path = line[4:]
            path = path[2:] if path.startswith('b/') else None
        elif line.startswith('@@ '):
            flush()
            match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if not match:
                raise ValueError('Unsupported probe hunk header.')
            new_line, in_hunk = int(match.group(1)), True
        elif in_hunk and line.startswith('+'):
            if path is None:
                raise ValueError('Added text has no target file.')
            if active is None:
                active = dict(path=path, start_line=new_line, end_line=new_line, diff_lines=[])
            active['end_line'] = new_line
            active['diff_lines'].append(line[1:])
            new_line += 1
        elif in_hunk and line.startswith(' '):
            flush()
            new_line += 1
        elif in_hunk and line.startswith('-'):
            flush()
    flush()
    return runs


def repository_controls(source):
    """Use isolated synthetic Git repositories; never touch the caller's index."""
    module = load_pinned(source, SOURCE_SHA256, '_agent_sessions_dlp_repository_probe')
    git = shutil.which('git')
    if not git:
        raise ValueError('Git is required for the synthetic repository controls.')
    cases = [
        ('new-private-addition', {'notes.md': COMMON + '\n'}, {'notes.md': COMMON + '\n' + PRIVATE + '\n'}, True),
        ('remove-old-private', {'notes.md': PRIVATE + '\n'}, {'notes.md': 'Generic public summary.\n'}, False),
        ('unchanged-private-context', {'notes.md': PRIVATE + '\nLabel alpha.\n'}, {'notes.md': PRIVATE + '\nLabel beta.\n'}, False),
        ('permitted-public-code', {'notes.md': COMMON + '\n'}, {'notes.md': COMMON + '\n' + CODE}, False),
        ('new-copy-now-restricted', {'notes.md': PRIVATE + '\n'}, {'notes.md': PRIVATE + '\n\n' + PRIVATE + '\n'}, True),
        ('mixed-public-and-private', {'notes.md': COMMON + '\n'}, {'notes.md': COMMON + '\n' + COMMON + '\n' + PRIVATE + '\n'}, True),
        ('wrapped-private-addition', {'notes.md': COMMON + '\n'}, {'notes.md': '\n'.join(textwrap.wrap(PRIVATE, 36)) + '\n'}, True),
        ('new-file-private-addition', {'notes.md': COMMON + '\n'}, {'notes.md': COMMON + '\n', 'new.md': PRIVATE + '\n'}, True),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix='agent-sessions-synthetic-disclosure-repos-') as temporary:
        root = Path(temporary)
        home = root / 'home'
        home.mkdir()
        env = dict(HOME=str(home), PATH='/usr/bin:/bin', LANG='C.UTF-8', GIT_CONFIG_NOSYSTEM='1',
                   GIT_CONFIG_GLOBAL='/dev/null', GIT_AUTHOR_NAME='Synthetic Author', GIT_AUTHOR_EMAIL='author@example.invalid',
                   GIT_COMMITTER_NAME='Synthetic Author', GIT_COMMITTER_EMAIL='author@example.invalid',
                   GIT_AUTHOR_DATE='2026-02-03T10:00:00+00:00', GIT_COMMITTER_DATE='2026-02-03T10:00:00+00:00')
        for name, before, after, expected in cases:
            repo = root / name
            repo.mkdir()

            def run(*args):
                return subprocess.run([git, '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                                       '-c', 'core.quotepath=false', *args], cwd=repo, env=env,
                                      capture_output=True, text=True, check=True).stdout

            run('init', '-q')
            for path, text in before.items():
                (repo / path).write_text(text)
            run('add', '--all')
            run('commit', '-q', '-m', 'Synthetic public baseline')
            for path in before.keys() - after.keys():
                (repo / path).unlink()
            for path, text in after.items():
                (repo / path).write_text(text)
            run('add', '--all')
            patch = run('diff', '--cached', '--unified=3', '--no-ext-diff', '--no-textconv', '--no-renames', 'HEAD', '--')
            matcher = module.PartialDocumentMatcher(window_size=50)
            for source_id, text in SOURCES.items():
                matcher.register(source_id, text)
            public = module.PartialDocumentMatcher(window_size=50)
            for path, text in before.items():
                public.register(path, text)
            findings = []
            for run_info in added_runs(patch):
                raw = (repo / run_info['path']).read_bytes()
                lines = raw.decode('utf-8').splitlines(keepends=True)
                text = ''.join(lines[run_info['start_line'] - 1:run_info['end_line']])
                if text.splitlines() != run_info['diff_lines']:
                    raise ValueError('Added-run coordinates do not match target file lines.')
                hits = matcher.scan(text)
                compact = compact_matches(SOURCES, text, hits)
                for finding in compact:
                    finding['candidate']['file_line_start'] = run_info['start_line'] + finding['candidate']['line_start'] - 1
                    finding['candidate']['file_line_end'] = run_info['start_line'] + finding['candidate']['line_end'] - 1
                    finding['candidate']['file_sha256'] = hashlib.sha256(raw).hexdigest()
                findings.append(dict(path=run_info['path'], start_line=run_info['start_line'], end_line=run_info['end_line'],
                                     source_sha256=hashlib.sha256(raw).hexdigest(), matched_sources=sorted({hit.doc_id for hit in hits}),
                                     public_baseline_overlap=bool(public.scan(text)), raw_lines_verified=True,
                                     matcher_windows=len(hits), compact_findings=compact))
            sensitive = lambda finding: 'private-note' in finding['matched_sources']
            results.append(dict(case=name, authored_new_copy_review_needed=expected,
                whole_patch_private_overlap=any(hit.doc_id == 'private-note' for hit in matcher.scan(patch)),
                added_run_private_overlap=any(sensitive(finding) for finding in findings),
                blanket_baseline_exemption_review=any(sensitive(finding) and not finding['public_baseline_overlap'] for finding in findings),
                findings=findings))
    return dict(synthetic_only=True, cases=results,
                limits='Ordinary text diffs in disposable synthetic Git repositories only. Sensitive-source policy labels are '
                       'authored, not discovered. Added-run findings do not certify repository history or publication safety. '
                       'No real repository index, private history, or external service is used.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matcher-source', required=True)
    parser.add_argument('--edm-source', help='Optional pinned edm.py for the declared-value control')
    parser.add_argument('--repository-controls', action='store_true', help='Create disposable synthetic Git repositories for diff-boundary controls')
    parser.add_argument('--citation-controls', action='store_true', help='Verify raw source and candidate anchors on synthetic text')
    parser.add_argument('--occurrence-controls', action='store_true', help='Compare candidate occurrence coverage with exhaustive literal lookup')
    args = parser.parse_args()
    if sum((args.repository_controls, args.citation_controls, args.occurrence_controls)) > 1:
        parser.error('Choose one control mode.')
    if args.occurrence_controls:
        result = occurrence_controls(args.matcher_source)
    elif args.citation_controls:
        result = citation_controls(args.matcher_source)
    elif args.repository_controls:
        result = repository_controls(args.matcher_source)
    else:
        result = evaluate(args.matcher_source, args.edm_source)
    print(json.dumps(result, indent=2))
