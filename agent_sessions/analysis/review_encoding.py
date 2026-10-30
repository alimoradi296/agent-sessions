"""Exact paragraph-text references; occurrences retain their own metadata."""

import copy
import json

FORMAT = 'adaptive_exact_text_v1'
INSTRUCTIONS = ('Each paragraph text_ref indexes texts. Read all occurrences in their original order; '
                'equal text does not merge roles, context, locators, or authority.\n')


def compact(sources):
    sources = copy.deepcopy(sources)
    texts, indexes = [], {}
    for source in sources:
        for section in source['sections']:
            for paragraph in section['paragraphs']:
                text = paragraph.pop('text')
                if text not in indexes:
                    indexes[text] = len(texts)
                    texts.append(text)
                paragraph['text_ref'] = indexes[text]
    return dict(texts=texts, sources=sources)


def expand(payload):
    sources = copy.deepcopy(payload['sources'])
    for source in sources:
        for section in source['sections']:
            for paragraph in section['paragraphs']:
                ref = paragraph.pop('text_ref')
                if type(ref) is not int or not 0 <= ref < len(payload['texts']):
                    raise ValueError('Invalid paragraph text reference.')
                paragraph['text'] = payload['texts'][ref]
    return sources


def adaptive_prompt(prompt):
    header, separator, body = prompt.partition('\n\n[\n')
    if not separator:
        raise ValueError('Expected a grouped review prompt.')
    sources = json.loads('[\n' + body)
    payload = compact(sources)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    if expand(json.loads(encoded)) != sources:
        raise ValueError('Review encoding changed occurrence evidence.')
    candidate = header + '\n' + INSTRUCTIONS + '\n' + encoded
    return candidate if len(candidate) < len(prompt) else prompt
