"""Conservative English claim labels with conversation evidence.

These rules classify what a speaker says. They do not check the claim, infer
acceptance, or execute commands. checked_result is reserved for future external
verification; conversation text never receives that label.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from agent_sessions.analysis.transcript import clean_knowledge_text, conversation_sections
from agent_sessions.models import Session

METHOD = 'english_rules_v3'
RULES = [
    ('reported_blocker', r"^(?:blocker|blocked(?: by)?|waiting for)\s*:"),
    ('next_action', r"^next (?:action|step)(?:s)?\s*:"),
    ('proposal', r"^(?:proposal|recommendation)\s*:|^(?:I|we)\s+(?:propose|suggest|recommend|could|should|will use)\b|^consider\b"),
    ('decision_candidate', r"^decision\s*:|^(?:we|I)\s+(?:decided|chose)\b|^decided\s+(?:to|on)\b"),
    ('deferred', r"^(?:deferred?|out of scope(?: for now)?|TODO|FIXME)\s*:|^will (?:do|handle|address) (?:this )?later\b"),
    ('bug_report', r"^(?:root cause|bug|issue)\s*:"),
    ('open_question', r"^(?:open question\s*:|should we\b|what about\b|how do\b|why\b).*[?]"),
    ('reported_result', r"^(?:(?:reported|checked) result|result|verified)\s*:|^(?:I|we)\s+(?:ran|tested|verified|checked|implemented|fixed|merged|deployed|reviewed|confirmed|completed)\b|^(?:tests?|checks?|build|CI)\s+(?:passed|failed)\b|^(?:implemented|fixed|merged|deployed|resolved|completed)\b"),
]
RULES = [(kind, re.compile(pattern, re.IGNORECASE)) for kind, pattern in RULES]
REQUEST_PREFIX = re.compile(
    r"^(?:(?:please|(?:can|could|would) you|I (?:want|need) you to|we need to)|(?P<negative>do not))\s+",
    re.IGNORECASE,
)
NEGATED_ACTION = re.compile(
    r"^(?:implement|fix|add|remove|write|review|check|test|verify|run|deploy|merge|update|create|"
    r"publish|post|edit|delete|change|open|copy|use|treat|assume|claim|read|inspect|explain|help|"
    r"decide|keep|preserve|accept|approve|commit|push|execute|stop|continue|proceed|wait)"
    r"(?=\s|[.!?]?$)", re.IGNORECASE,
)
BARE_ACTION = re.compile(
    r"^(?:implement|fix|add|remove|write|review|check|test|verify|run|deploy|merge|update|create)"
    r"(?=\s|[.!?]?$)", re.IGNORECASE,
)
DESCRIPTIVE_SUBJECT = re.compile(
    r"^(?:results?|reports?|coverage|status|summary|notes?|instructions?|details?|logs?|output|counts?)"
    r"\s+(?:is|are|was|were|do|does|has|have|remain|remains|show|shows)\b", re.IGNORECASE,
)
UNDECIDED = re.compile(r"\b(?:not decided|no decision|decision (?:is )?(?:pending|not made))\b", re.IGNORECASE)


def _is_request(text: str) -> bool:
    """Reject paths, empty headings, and negative descriptions as requests."""
    prefix = REQUEST_PREFIX.match(text)
    action_text = text[prefix.end():] if prefix else text
    if prefix is None:
        action = BARE_ACTION.match(action_text)
    elif prefix.group('negative'):
        action = NEGATED_ACTION.match(action_text)
    else:
        # Preserve explicit polite requests with unfamiliar English verbs.
        action = re.match(r"^[a-z]+(?=\s|[.!?]?$)", action_text, re.IGNORECASE)
    if action is None:
        return False
    target = action_text[action.end():].strip().rstrip('.!?').strip()
    if (target and not any(char.isalnum() for char in target)) or DESCRIPTIVE_SUBJECT.match(target):
        return False
    # Polite and negative instructions can be complete without an object.
    # Bare action words alone are ambiguous headings, so abstain.
    return prefix is not None or bool(target)


def classify(text: str, role: str) -> str | None:
    """Return one candidate label or abstain; a question is never a result."""
    normalized = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)', '', text).strip()
    normalized = normalized.replace('**', '').replace('__', '')
    heading = re.match(r'^\s*#{1,6}\s+', text) is not None
    if role == 'user' and not heading and _is_request(normalized):
        return 'request'
    if UNDECIDED.search(normalized):
        return None
    for kind, pattern in RULES:
        if kind == 'reported_result' and ('?' in normalized or re.search(
                r'\b(?:will|would|might|could|should)\b', normalized, re.IGNORECASE)):
            continue
        match = pattern.search(normalized)
        if match and kind in ('reported_blocker', 'next_action') and re.fullmatch(
                r'(?:none|no (?:blockers?|next actions?)|not blocked|resolved)[.!]?',
                normalized[match.end():].strip(), re.IGNORECASE):
            continue
        if match and normalized[match.end():].strip():
            return kind
        if match and kind in ('reported_result', 'open_question') and not normalized.endswith(':'):
            return kind
    return None


def _from_text(text: str, role: str, evidence: dict) -> list[dict]:
    claims = []
    for line in clean_knowledge_text(text).splitlines():
        quote = line.strip()
        kind = classify(quote, role)
        if kind is None:
            continue
        reference = dict(evidence, role=role, quote=quote)
        digest = hashlib.sha256(json.dumps([kind, reference], sort_keys=True).encode()).hexdigest()[:16]
        claims.append(dict(id=digest, kind=kind, text=quote, method=METHOD,
                           verification='not_checked', evidence=reference))
    return claims


def claims_from_session(session: Session) -> list[dict]:
    claims = []
    for i, message in enumerate(session.messages, 1):
        if message.role not in ('user', 'assistant') or message.phase in ('analysis', 'commentary'):
            continue
        claims.extend(_from_text(message.text, message.role, dict(
            session_id=session.id, agent=session.agent.value, source='transcript_message',
            message_index=i, source_path=message.source_path or None,
            source_line=message.source_line)))
    return claims


def section_evidence(path: Path, index: int, role: str, agent: str) -> dict:
    """Locate a cleaned export section without inventing raw transcript lines."""
    return dict(session_id=path.stem, agent=agent, role=role.lower(), source='export_section',
                conversation_section=index, source_path=str(path.resolve()), source_line=None)


def claims_from_sections(path: Path, sections: list[tuple[int, str, str]], agent: str) -> list[dict]:
    """Extract complete sections, retaining their original one-based coordinates."""
    claims = []
    for i, role, text in sections:
        claims.extend(_from_text(text, role.lower(), section_evidence(path, i, role, agent)))
    return claims


def claims_from_markdown(path: Path, content: str, agent: str) -> list[dict]:
    sections = [(i, role, text) for i, (role, text) in enumerate(conversation_sections(content), 1)]
    return claims_from_sections(path, sections, agent)


def render_evidence(evidence: dict) -> str:
    """Render a source coordinate, not independent verification."""
    coordinate = (f"message {evidence['message_index']}" if evidence['source'] == 'transcript_message'
                  else f"conversation section {evidence['conversation_section']}")
    if evidence.get('source_line') is not None:
        coordinate += f", source line {evidence['source_line']}"
    source_path = evidence.get('source_path')
    if source_path:
        # Keep paths literal. They are local references, not trusted URLs.
        coordinate += f" in {json.dumps(source_path, ensure_ascii=False)}"
    if evidence.get('section_line') is not None:
        coordinate += f", cleaned section line {evidence['section_line']}"
    return f"Source: {evidence['agent']} / {evidence['session_id']} / {evidence['role']} / {coordinate}."


def render_claim(claim: dict) -> str:
    """Render an evidence locator without claiming that it proves the result."""
    text = ' '.join(claim['text'].splitlines())
    return f"- **{claim['kind']}** (not checked): {text}\n  {render_evidence(claim['evidence'])}"
