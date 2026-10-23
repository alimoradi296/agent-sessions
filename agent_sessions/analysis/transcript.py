"""Read conversation prose without treating tool evidence as dialogue."""

import re


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
