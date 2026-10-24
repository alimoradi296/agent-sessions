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

METHOD = 'english_rules_v1'
RULES = [
    ('proposal', r"^(?:proposal|recommendation)\s*:|^(?:I|we)\s+(?:propose|suggest|recommend|could|should|will use)\b|^consider\b"),
    ('decision_candidate', r"^decision\s*:|^(?:we|I)\s+(?:decided|chose)\b|^decided\s+(?:to|on)\b"),
    ('deferred', r"^(?:deferred?|out of scope(?: for now)?|TODO|FIXME)\s*:|^will (?:do|handle|address) (?:this )?later\b"),
    ('bug_report', r"^(?:root cause|bug|issue)\s*:"),
    ('open_question', r"^(?:open question\s*:|should we\b|what about\b|how do\b|why\b).*[?]"),
    ('reported_result', r"^(?:(?:reported|checked) result|result|verified)\s*:|^(?:I|we)\s+(?:ran|tested|verified|checked|implemented|fixed|merged|deployed|reviewed|confirmed|completed)\b|^(?:tests?|checks?|build|CI)\s+(?:passed|failed)\b|^(?:implemented|fixed|merged|deployed|resolved|completed)\b"),
]
RULES = [(kind, re.compile(pattern, re.IGNORECASE)) for kind, pattern in RULES]
REQUEST = re.compile(
    r"^(?:please\b|(?:can|could|would) you\b|I (?:want|need) you to\b|we need to\b|do not\b|"
    r"(?:implement|fix|add|remove|write|review|check|test|verify|run|deploy|merge|update|create)\b)", re.IGNORECASE)
UNDECIDED = re.compile(r"\b(?:not decided|no decision|decision (?:is )?(?:pending|not made))\b", re.IGNORECASE)


def classify(text: str, role: str) -> str | None:
    """Return one candidate label or abstain; a question is never a result."""
    normalized = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)', '', text).strip()
    normalized = normalized.replace('**', '').replace('__', '')
    if role == 'user' and REQUEST.search(normalized):
        return 'request'
    if UNDECIDED.search(normalized):
        return None
    for kind, pattern in RULES:
        if kind == 'reported_result' and ('?' in normalized or re.search(
                r'\b(?:will|would|might|could|should)\b', normalized, re.IGNORECASE)):
            continue
        match = pattern.search(normalized)
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


def claims_from_markdown(path: Path, content: str, agent: str) -> list[dict]:
    claims = []
    for i, (role, text) in enumerate(conversation_sections(content), 1):
        claims.extend(_from_text(text, role.lower(), dict(
            session_id=path.stem, agent=agent, source='export_section',
            conversation_section=i, source_path=str(path.resolve()), source_line=None)))
    return claims


def render_claim(claim: dict) -> str:
    """Render an evidence locator without claiming that it proves the result."""
    evidence = claim['evidence']
    coordinate = (f"message {evidence['message_index']}" if evidence['source'] == 'transcript_message'
                  else f"conversation section {evidence['conversation_section']}")
    if evidence.get('source_line') is not None:
        coordinate += f", source line {evidence['source_line']}"
    source_path = evidence.get('source_path')
    if source_path:
        # Keep paths literal. They are local references, not trusted URLs.
        coordinate += f" in {json.dumps(source_path, ensure_ascii=False)}"
    text = ' '.join(claim['text'].splitlines())
    return (f"- **{claim['kind']}** (not checked): {text}\n"
            f"  Source: {evidence['agent']} / {evidence['session_id']} / {evidence['role']} / {coordinate}.")
