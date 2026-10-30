"""Read conversation prose without treating tool evidence as dialogue."""

import re


def rendered_messages(markdown: str) -> list[dict]:
    """Read raw rendered message bodies with character coordinates.

    These locators differ from cleaned dialogue sections. Content remains
    untrusted, including headings and phase labels from an exported file.
    """
    messages = []
    current = None
    fence = ''
    offset = 0
    for number, line in enumerate(markdown.splitlines(keepends=True), 1):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            value = marker.group(1)
            if not fence:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = ''
        heading = re.match(r'^## (User|Assistant|Tool|System)\b(.*)', line) if not fence else None
        if heading:
            if current is not None:
                current['text'] = markdown[current['body_start']:offset]
                messages.append(current)
            phase = re.search(r'\((analysis|commentary)\)', heading.group(2))
            current = dict(role=heading.group(1), phase=phase.group(1) if phase else '',
                           heading_line=number, body_start=offset + len(line))
        offset += len(line)
    if current is not None:
        current['text'] = markdown[current['body_start']:]
        messages.append(current)
    return messages


def clean_knowledge_text(text: str) -> str:
    text = re.sub(
        r"<(?P<tag>[\w-]*(?:instructions|context|reminder|rules|guidelines|citation)[\w-]*)\b[^>]*>.*?</(?P=tag)>",
        "", text, flags=re.DOTALL | re.IGNORECASE,
    )
    # Match closing fences of at least the opening length.
    text = re.sub(r"(?m)^[ \t]*(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^[ \t]*(?P=fence)[`~]*[^\n]*$",
                  "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^.*\*\[Tool(?::| result).*?$", "", text)
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))


def conversation_sections(markdown: str) -> list[tuple[str, str]]:
    """Read conversation headings outside code fences and tool evidence."""
    sections = []
    role = ""
    lines: list[str] = []
    fence = ""
    for line in markdown.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            lines.append(line)
            continue
        heading = re.match(r"^## (User|Assistant|Tool|System)\b(.*)$", line) if not fence else None
        if heading:
            if role:
                sections.append((role, '\n'.join(lines)))
            role = heading.group(1)
            if '(commentary)' in heading.group(2) or '(analysis)' in heading.group(2):
                role = 'Excluded'
            lines = []
        else:
            lines.append(line)
    if role:
        sections.append((role, '\n'.join(lines)))
    cleaned = []
    for role, text in sections:
        if role not in ('User', 'Assistant'):
            continue
        # Tool annotations and their payloads do not become context prose.
        text = re.split(r"(?m)^\*\[Tool(?::| result)", text)[0]
        text = clean_knowledge_text(text).strip().strip('-').strip()
        if text:
            cleaned.append((role, text))
    return cleaned


def sections_for_view(markdown: str, view='dialogue') -> list[tuple[str, str]]:
    """Keep dialogue and raw message coordinates explicitly separate."""
    if view == 'dialogue':
        return conversation_sections(markdown)
    if view == 'evidence':
        lines = markdown.splitlines(keepends=True)
        return [(message['role'], lines[message['heading_line'] - 1] + message['text'])
                for message in rendered_messages(markdown)]
    raise ValueError('Source view must be dialogue or evidence.')


def export_boundary_variant(text: str):
    """Offer only the export separator's terminal newline alternative.

    Canonical Markdown ends its last message with one newline and puts two
    before the next heading. Payload bytes and headings are never normalized.
    An unclosed fence cannot establish an export boundary.
    """
    if text.endswith('\n---\n\n'):
        alternate = text[:-1]
    elif text.endswith('\n---\n'):
        alternate = text + '\n'
    else:
        return None
    if len(rendered_messages(text + '\n## System\n')) != 2:
        return None
    return alternate
