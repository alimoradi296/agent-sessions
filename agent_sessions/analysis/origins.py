"""Text-shape hints, never author authentication or permission decisions.

Keep embedded evidence intact. A User message can include harness material,
quoted conversations, or an explicitly attached skill.
"""

import re

METHOD = 'wrapper_shape_v1'
WRAPPERS = re.compile(
    r'<(?P<tag>skill|manually_attached_skills|available_subagent_types|user_query|send_user_message_question_reply)\b[^>]*>'
    r'.*?</(?P=tag)>', re.I | re.S)
KINDS = dict(skill='embedded_reference', manually_attached_skills='embedded_reference',
             available_subagent_types='harness_reference', user_query='wrapped_query',
             send_user_message_question_reply='wrapped_reply')


def paragraph_origin_hint(body, start_line, end_line):
    """Annotate known wrapper spans without altering quotes or line offsets."""
    lines = body.splitlines(keepends=True)
    start = sum(map(len, lines[:start_line - 1]))
    end = sum(map(len, lines[:end_line]))
    # Paragraph locators exclude their following newline.
    end -= len(lines[end_line - 1]) - len(lines[end_line - 1].rstrip('\r\n'))
    overlaps = [match for match in WRAPPERS.finditer(body) if match.start() < end and match.end() > start]
    if not overlaps:
        return 'unattributed'
    if len(overlaps) != 1 or overlaps[0].start() > start or overlaps[0].end() < end:
        return 'mixed_wrapper_boundary'
    return KINDS[overlaps[0].group('tag').lower()]
